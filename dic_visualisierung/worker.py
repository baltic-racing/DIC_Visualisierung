"""Bounded C-process transport, watchdog, diagnostics and event observation."""
from collections import deque
import copy
import json
import os
from pathlib import Path
import queue
import subprocess
import threading


class WorkerError(ValueError):
    pass


class Worker:
    """One firmware invocation. Protocol is private, bounded, and synchronous.

    stdin: S / I page <all values> count <id eight bytes>* / A ticks delta / Q.
    stdout: one DIC1 JSON line per command; firmware stdout goes to stderr.
    No pickle, eval, shell, platform-specific pipe polling or persistent RAM files.
    """
    def __init__(self, binary, environment, fields, mode=3, timeout=3):
        self.fields = fields
        self.timeout = timeout
        self.trace=deque(maxlen=4096);self.tx_history=deque(maxlen=10000)
        self.recent={kind:deque(maxlen=20) for kind in ('rx','tx','drop','lcd')}
        # Read-only observation of transport events, never a receive queue.
        # Standard CAN IDs bound each direction to at most 2048 entries.
        self.can_latest={kind:{} for kind in ('rx','tx','drop')}
        self.trace_lost=0;self.tx_lost=0;self.last_seq=0
        self.lock = threading.RLock()
        self.replies = queue.Queue(maxsize=2)
        self.diagnostics = deque(maxlen=8)
        self.process = subprocess.Popen([str(binary),str(mode)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        cwd=Path(binary).parent, env=environment, bufsize=0)
        self.closed = False
        self.readers = [threading.Thread(target=self._read, daemon=True),
                        threading.Thread(target=self._diagnostics, daemon=True)]
        for reader in self.readers:
            reader.start()
        try:
            self.latest = self._reply()
        except Exception:
            self.close()
            raise

    def _deliver(self, value):
        try:
            self.replies.put_nowait(value)
        except queue.Full:
            self.process.kill()

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(65537)
                if not line:
                    self._deliver(WorkerError('Firmware-Worker beendet oder abgestürzt.'))
                    return
                if len(line)>65536 or not line.endswith(b'\n') or not line.startswith(b'DIC1 '):
                    self._deliver(WorkerError('Ungültige oder zu große Worker-Protokollausgabe.'))
                    self.process.kill()
                    return
                self._deliver(json.loads(line[5:]))
        except (OSError,ValueError) as exc:
            self._deliver(WorkerError('Worker-Protokollfehler: '+str(exc)))

    def _diagnostics(self):
        try:
            while True:
                chunk = os.read(self.process.stderr.fileno(),1024)
                if not chunk:
                    break
                self.diagnostics.append(chunk.decode('utf-8',errors='replace'))
        except (OSError,ValueError):
            pass

    def _reply(self):
        try:
            result = self.replies.get(timeout=self.timeout)
        except queue.Empty:
            self.close()
            raise WorkerError('Firmware-Worker hängt: Zeitlimit überschritten. Reset erforderlich.') from None
        if isinstance(result, Exception):
            self.close()
            raise WorkerError(str(result)+'\n'+''.join(self.diagnostics))
        if not isinstance(result,dict) or not {'time_ms','sys_time','rows_hex','glyphs_hex','outputs','state','active_index'} <= result.keys():
            self.close()
            raise WorkerError('Worker-Schnappschuss unvollständig.')
        if len(result['rows_hex'])!=160 or len(result['glyphs_hex'])!=128:
            self.close()
            raise WorkerError('Ungültige Displaygeometrie im Worker-Protokoll.')
        for event in result.get('events',[]):
            if event['seq']<=self.last_seq:continue
            self.last_seq=event['seq'];event=copy.deepcopy(event)
            event['kind']={1:'rx',2:'tx',3:'drop',4:'lcd'}[event['kind']]
            event['reason_text']={0:'',1:'MOb belegt / noch nicht wieder aktiviert',2:'Kein passender ID-Filter',3:'Noch kein Empfangs-MOb scharfgeschaltet',4:'CAN-Controller deaktiviert'}[event['reason']]
            if len(self.trace)==self.trace.maxlen:self.trace_lost+=1
            self.trace.append(event);self.recent[event['kind']].append(event)
            if event['kind'] in self.can_latest:
                messages=self.can_latest[event['kind']]
                previous=messages.get(event['can_id'])
                messages[event['can_id']]=dict(event,
                    count=previous['count']+1 if previous else 1,
                    interval_ms=event['at_ms']-previous['at_ms'] if previous else None)
            if event['kind']=='tx':
                if len(self.tx_history)==self.tx_history.maxlen:self.tx_lost+=1
                self.tx_history.append(event)
        return result

    def can_snapshot(self, now):
        return {kind:[dict(copy.deepcopy(messages[ident]),age_ms=now-messages[ident]['at_ms'])
                      for ident in sorted(messages)] for kind,messages in self.can_latest.items()}

    def arrivals(self,frames,immediate=False):
        if not frames or len(frames)>128:raise ValueError('1 bis 128 Ankunftsereignisse erwartet.')
        parts=['B' if immediate else 'F',str(len(frames))]
        for frame in frames:parts += [str(frame['can_id']),str(frame['dlc'])]+[str(b) for b in frame['data']]
        return self.command(' '.join(parts))

    def alive(self):
        if self.closed or self.process.poll() is not None:
            raise WorkerError('Firmware-Worker beendet oder abgestürzt. Reset zum Wiederherstellen.')

    def command(self, line):
        with self.lock:
            self.alive()
            packet=(line+'\n').encode('ascii')
            if len(packet)>8191:
                raise ValueError('Worker-Eingaben zu groß.')
            try:
                self.process.stdin.write(packet)
                self.process.stdin.flush()
            except (BrokenPipeError,OSError):
                self.close()
                raise WorkerError('Verbindung zum Firmware-Worker unterbrochen.') from None
            self.latest=self._reply()
            return copy.deepcopy(self.latest)

    def stage(self, packet, pages):
        parts=['I',str(pages.index(packet['page']))]
        parts += [str(packet['values'][f['id']]) for f in self.fields]
        parts += [str(len(packet['overrides']))]
        for ident, data in packet['overrides']:
            parts += [str(ident)]+[str(b) for b in data]
        return self.command(' '.join(parts))

    def advance(self, ticks, delta=1):
        if type(ticks) is not int or not 1<=ticks<=10000 or type(delta) is not int or not 1<=delta<=0xffffffff:
            raise ValueError('Ungültiger Timerfortschritt.')
        return self.command(f'A {ticks} {delta}')

    def close(self):
        if self.closed:
            return
        self.closed=True
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process.wait(timeout=2)
        for stream in (self.process.stdin,self.process.stdout,self.process.stderr):
            if stream:
                stream.close()
        for reader in self.readers:
            if reader is not threading.current_thread():
                reader.join(timeout=1)

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()

