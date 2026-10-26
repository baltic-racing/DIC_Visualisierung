"""Resident workers and a deterministic 1 ms session clock (stdlib only)."""
import atexit
import copy
import heapq
import threading
import time
import uuid
from . import scenarios
from . import generators
from . import ams
from .worker import Worker, WorkerError


class Session:
    """No wall clock here: only explicit integer targets and ordered input edges."""
    def __init__(self, backend, snapshot, packet, initial_at=None, replay=None):
        self.backend=backend
        self.snapshot=snapshot
        with backend.LOCK:
            binary,self.pages=backend.compile_preview(snapshot[0],snapshot[4])
            self.compiled_at=backend.CACHE.get('compiled_at')
        self.id=uuid.uuid4().hex
        self.replay=copy.deepcopy(replay)
        self.end_ms=replay['duration_ms'] if replay else None
        self.check_results=[];self.checked=set();self.inspect_page=None
        self.check_passed=0;self.check_failed=0;self.first_failure=None
        initial=copy.deepcopy(packet)
        if replay:
            state=replay['initial'];initial=backend.input_packet({k:[str(v)] for k,v in state['values'].items()}|dict(page=[state['page']],raw=[state['raw']],scenario=[state['scenario']]),snapshot)
        if initial['page'] not in self.pages:
            initial['page']=self.pages[0]
        self.desired_packet=copy.deepcopy(initial)
        self.packet=dict(values={f['id']:f['default'] for f in backend.FIELDS},page=self.pages[0],overrides=[])
        self.worker=Worker(binary,backend.process_environment(),backend.FIELDS,initial['values']['mode'])
        self.events=[]
        self.event_number=0
        self.last_event=None
        self.ams_sender=ams.Sender()
        configs=replay['generators'] if replay else scenarios.defaults(scenarios.MAX_DURATION,bool(initial['values']['ams_sender']))
        if not replay:
            configs=[dict(c,end_ms=0x7fffffffffffffff,_adaptive_ams_period=True) for c in configs]
        self.generators={c['can_id']:generators.Generator(c) for c in configs}
        self.script=[]
        if replay:
            for index,event in enumerate(replay['events']):heapq.heappush(self.script,(event['at_ms'],index,event))
        try:
            if not replay:self.schedule(initial,1 if initial_at is None else initial_at)
            if replay:
                # Initial input settings exist at time zero; no timer or main loop is run.
                self._apply(initial);self.worker.stage(self.packet,self.pages)
                self._at(0,immediate=True)
                self._assert_at(0)
        except Exception:
            self.worker.close()
            raise

    @property
    def now(self):
        return self.worker.latest['time_ms']

    def schedule(self, patch, at=None):
        patch=copy.deepcopy(patch)
        if 'page' in patch and patch['page'] not in self.pages:
            patch['page']=self.pages[0]
        at=self.now+1 if at is None else at
        if type(at) is not int or not self.now<at<=self.now+86400000:
            raise ValueError('Eingabezeit muss nach der aktuellen Zeit liegen (maximal 24 h voraus).')
        if '_can' in patch:
            same=sum(t==at and '_can' in entry for t,_,entry in self.events)+sum(t==at and e['kind']=='can' for t,_,e in self.script)
            if same>=96:raise ValueError('Maximal 96 explizite CAN-Ereignisse je Millisekunde.')
        if self.end_ms is not None and at>self.end_ms:raise ValueError('Ereigniszeit liegt nach dem Replay-Ende.')
        if len(self.events)>=1024:
            raise ValueError('Zu viele geplante Eingabeänderungen (maximal 1024).')
        if '_can' not in patch:
            for key,value in patch.items():
                if key=='values':self.desired_packet['values'].update(copy.deepcopy(value))
                else:self.desired_packet[key]=copy.deepcopy(value)
        self.event_number+=1
        heapq.heappush(self.events,(at,self.event_number,patch))
        return at

    def _apply(self, patch):
        for key,value in patch.items():
            if key=='values':
                self.packet['values'].update(value)
            else:
                if key=='page' and value not in self.pages:value=self.pages[0]
                self.packet[key]=copy.deepcopy(value)

    def _at(self,stamp,immediate=False):
        frames=[];changed=False
        # File controls precede manually scheduled controls at the same timestamp.
        while self.script and self.script[0][0]==stamp:
            _,_,event=heapq.heappop(self.script);kind=event['kind']
            if kind=='can':frames.append({k:event[k] for k in ('can_id','dlc','data')})
            elif kind=='gpio':
                self._apply({'values':{'ts_button' if event['pin']=='TS_ON' else 'r2d_button':int(event['pressed'])}});changed=True
            elif kind=='inputs':
                patch={k:event[k] for k in ('values','page') if k in event}
                if 'raw' in event:patch['overrides']=self.backend.profiles.raw_bytes(event['raw'])
                self._apply(patch);changed=True
            else:
                generator=self.generators[event['can_id']]
                if 'enabled' in event:generator.enabled=event['enabled']
                if 'freeze_counter' in event:generator.freeze=event['freeze_counter']
        while self.events and self.events[0][0]==stamp:
            _,_,patch=heapq.heappop(self.events)
            if '_can' in patch:frames.append(patch['_can'])
            else:self._apply(patch);changed=True
        if changed:
            self.worker.stage(self.packet,self.pages);self.last_event=stamp
        self.ams_sender.update(stamp,self.packet['values'])
        # Explicit arrival frames take precedence over periodic frames in wire order.
        for generator in self.generators.values():
            if generator.next==stamp:
                frame=generator.emit(stamp,self.packet,self.pages,self.ams_sender.latched)
                if generator.next>generator.config['end_ms']:generator.next=None
                if frame is not None:frames.append(frame)
        if frames:self.worker.arrivals(frames,immediate)

    def _next(self,target):
        stamps=[target,self.now+10]
        if self.events:stamps.append(self.events[0][0])
        if self.script:stamps.append(self.script[0][0])
        stamps += [g.next for g in self.generators.values() if g.next is not None]
        deadline=self.ams_sender.deadline()
        if deadline is not None:stamps.append(deadline)
        if self.replay:stamps += [c['at_ms'] for i,c in enumerate(self.replay['assertions']) if i not in self.checked]
        return min(stamps)

    def _assert_at(self,stamp):
        if not self.replay:return
        for index,check in enumerate(self.replay['assertions']):
            if index in self.checked or check['at_ms']!=stamp:continue
            self.checked.add(index);frame=self.frame(checks=False)
            try:
                actual=frame
                for key in check['path'].split('.'):
                    actual=actual[int(key)] if isinstance(actual,list) else actual[key]
                passed=(actual==check['expected']) if check['op']=='eq' else check['expected'] in actual
            except (KeyError,IndexError,TypeError):actual='Prüfpfad nicht verfügbar';passed=False
            result=dict(check,actual=actual,passed=passed)
            self.check_results.append(result)
            if passed:self.check_passed+=1
            else:
                self.check_failed+=1
                if self.first_failure is None:self.first_failure=(len(self.check_results)-1,result)

    def advance_to(self,target):
        if type(target) is not int or not self.now<=target<=self.now+60000 or (self.end_ms is not None and target>self.end_ms):
            raise ValueError('Zielzeit muss zwischen jetzt und 60 s voraus und innerhalb der Replay-Dauer liegen.')
        while self.now<target:
            stamp=self._next(target)
            if stamp>self.now+1:self.worker.advance(stamp-self.now-1)
            self._at(self.now+1)
            self.worker.advance(1)
            self._assert_at(self.now)
        return self.frame()

    def inspect(self,page):
        if page is not None and page not in self.pages:raise ValueError('Unbekannte Diagnoseseite.')
        self.inspect_page=page
        self.worker.command('V '+str(self.pages.index(page) if page is not None else -1))

    def tx_comparison(self):
        if not self.replay or not self.replay['expected_tx']:return dict(configured=False,results=[])
        actual=list(self.worker.tx_history);results=[];complete=self.now>=self.end_ms
        for index,expected in enumerate(self.replay['expected_tx']):
            got=actual[index] if index<len(actual) else None
            if got is None and not complete and self.now<expected['at_ms']+expected['tolerance_ms']:status='pending'
            elif got is None:status='failed'
            else:status='passed' if got['can_id']==expected['can_id'] and got['dlc']==expected['dlc'] and got['data']==expected['data'] and abs(got['at_ms']-expected['at_ms'])<=expected['tolerance_ms'] else 'failed'
            results.append(dict(status=status,expected=expected,actual=got))
        if len(actual)>len(self.replay['expected_tx']):results.append(dict(status='failed',expected='Keine zusätzlichen TX-Frames',actual=len(actual)-len(self.replay['expected_tx'])))
        return dict(configured=True,incomplete_history=bool(self.worker.tx_lost),passed=sum(r['status']=='passed' for r in results),failed=sum(r['status']=='failed' for r in results),pending=sum(r['status']=='pending' for r in results),results=results[-20:])

    def frame(self,checks=True):
        self.worker.alive()
        data=copy.deepcopy(self.worker.latest)
        data.pop('events',None)
        raw=bytes.fromhex(data.pop('rows_hex'));lcd=bytes.fromhex(data.pop('lcd_hex'));glyphs=bytes.fromhex(data.pop('glyphs_hex'))
        outputs=data['outputs'];ports=outputs['ports']
        pins=[('A',4),('A',5),('A',6),('A',7),('G',2)]+[('C',b) for b in range(7,-1,-1)]+[('G',1),('G',0)]
        outputs['top']=[(ports[p]>>b)&1 for p,b in pins]
        outputs['bottom']=[(ports['D']>>b)&1 for b in (0,1,2,3,4,7)]
        for side in ('left','right'):
            outputs[side+'_rgb']=[[(outputs[side]>>b)&1 for b in channels] for channels in ((3,2,4),(0,1,5))]
        src,label,branch,commit,digest,local=self.snapshot
        next_events=([self.events[0][0]] if self.events else [])+([self.script[0][0]] if self.script else [])
        data.update(ok=True,source=label,branch=branch,commit=commit,local=local,revision=digest[:12],
                    pages=self.pages,page=self.desired_packet['page'],active_page=self.pages[data['active_index']],
                    source_files=sorted(src),compiled_at=self.compiled_at,fields=self.backend.FIELDS,
                    rows=[list(lcd[i:i+20]) for i in range(0,80,20)],logical_rows=[list(raw[i:i+20]) for i in range(0,80,20)],logical_page=self.pages[data['buffer_index']],glyphs=[list(glyphs[i:i+8]) for i in range(0,64,8)],
                    session=dict(id=self.id,time_ms=self.now,sys_time=data['sys_time'],last_input_ms=self.last_event,
                                 pending_events=len(self.events)+len(self.script),next_input_ms=min(next_events,default=None)))
        data['input_state']=dict(values=copy.deepcopy(self.desired_packet['values']),page=self.desired_packet['page'],scenario=self.desired_packet.get('scenario','example'),raw='\n'.join(f'{ident:03X}: '+bytes(raw).hex(' ').upper() for ident,raw in self.desired_packet['overrides']))
        data['ams_sender']=self.ams_sender.status(self.packet['values'])
        data['traffic']={kind:list(items) for kind,items in self.worker.recent.items()}
        data['traffic']['can']=self.worker.can_snapshot(self.now)
        data['traffic'].update(counts=data['counts'],history_dropped=self.worker.trace_lost,transport_dropped=data['event_loss'],tx_history_dropped=self.worker.tx_lost)
        if self.replay:
            # Totals cover the entire run, independently of the bounded details.
            summary=dict(total=len(self.replay['assertions']),passed=self.check_passed,
                         failed=self.check_failed,pending=len(self.replay['assertions'])-len(self.check_results))
            earlier_failure=(self.first_failure[1] if self.first_failure is not None and
                             self.first_failure[0]<len(self.check_results)-50 else None)
            data['replay']=dict(name=self.replay['name'],duration_ms=self.end_ms,finished=self.now>=self.end_ms,
                                check_summary=summary,earlier_failure=copy.deepcopy(earlier_failure) if checks else None,
                                checks=copy.deepcopy(self.check_results[-50:]) if checks else [],tx=self.tx_comparison() if checks else {},
                                generator_count=len(self.generators),manual_swc=0x750 in self.generators and 'data' not in self.generators[0x750].config)
        return data

    def close(self):
        self.worker.close()

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()


class Interactive:
    """Wall pacing, source watcher and one interactive session; tests never use it."""
    def __init__(self, backend, background=True, clock=time.monotonic):
        self.backend=backend
        self.lock=threading.RLock()
        self.clock=clock
        self.session=None
        self.scenario=None
        self.query={}
        self.source_key=None
        self.observed=None
        self.status='idle'
        self.error=''
        self.notice='Noch keine Sitzung. Start beginnt bei 0 ms.'
        self.generation=0
        self.running=False
        self.speed=1.0
        self.budget=0.0
        self.wall=clock()
        self.last_watch=0
        self.stopped=threading.Event()
        self.thread=None
        if background:
            self.thread=threading.Thread(target=self._loop,daemon=True)
            self.thread.start()
        atexit.register(self.close)

    def _source(self):
        with self.backend.LOCK:
            return self.backend.sources(self.query.get('source',['auto'])[0],self.query.get('ref',[None])[0])

    def _new(self, snapshot, reason, at=None):
        if self.session:
            self.session.close()
        self.session=None
        self.running=False
        self.budget=0
        self.generation+=1
        self.notice=reason+' Neue Sitzung bei 0 ms, pausiert.'
        self.observed=(snapshot[4],snapshot[1])
        self.source_key=(str(self.backend.REPO),self.query.get('source',['auto'])[0],self.query.get('ref',[''])[0])
        try:
            packet=self.backend.input_packet(self.query,snapshot)
            self.session=Session(self.backend,snapshot,packet,at,replay=self.scenario)
            self.status='paused'
            self.error=''
        except Exception as exc:
            self.status='error'
            self.error=str(exc)
            raise
        finally:
            self.wall=self.clock()

    def watch(self,force=False):
        with self.lock,self.backend.LOCK:
            now=self.clock()
            if not self.source_key or (not force and now-self.last_watch<0.5):
                return
            self.last_watch=now
            snapshot=None
            try:
                snapshot=self._source()
                if self.observed!=(snapshot[4],snapshot[1]) or self.source_key[0]!=str(self.backend.REPO):
                    self._new(snapshot,'Firmware-Quelldateien oder Branch geändert; bisherige Sitzung beendet.')
            except Exception as exc:
                if snapshot is None:
                    self.observed=None
                if self.session:
                    self.session.close();self.session=None
                self.running=False;self.status='error';self.error=str(exc)
                self.notice='Quellprüfung oder Kompilierung fehlgeschlagen. Kein alter Firmware-Stand wird weitergeführt.'

    def pump(self):
        with self.lock:
            now=self.clock()
            elapsed=max(0,now-self.wall)
            self.wall=now
            if self.session:
                self.session.worker.alive()
            if not self.running or not self.session:
                return
            self.budget+=elapsed*1000*self.speed
            # Bounded work, retain ALL excess budget. Do not drop virtual ticks.
            count=min(int(self.budget+1e-7),1000)
            if self.session.end_ms is not None:count=min(count,self.session.end_ms-self.session.now)
            if count:
                self.session.advance_to(self.session.now+count)
                self.budget-=count
            if self.session.end_ms is not None and self.session.now>=self.session.end_ms:
                self.running=False;self.status='finished';self.budget=0

    def _loop(self):
        while not self.stopped.wait(0.02):
            try:
                self.watch()
                self.pump()
            except Exception as exc:
                with self.lock:
                    self.running=False;self.status='error';self.error=str(exc)
                    if self.session:
                        self.session.close()
                    self.notice='Worker-Fehler. Reset startet eine neue Sitzung; die alte wird nicht automatisch ersetzt.'

    def inputs(self,query,at=None):
        with self.lock,self.backend.LOCK:
            key=(str(self.backend.REPO),query.get('source',['auto'])[0],query.get('ref',[''])[0])
            if key!=self.source_key:
                # Reject invalid controls before committing a new selection or
                # closing a valid session. Otherwise a bad first packet becomes
                # the reset packet and even correcting it cannot recover.
                snapshot=self.backend.sources(query.get('source',['auto'])[0],query.get('ref',[None])[0])
                self.backend.input_packet(query,snapshot)
                if self.scenario is None and at is not None and (type(at) is not int or not 0<at<=86400000):
                    raise ValueError('Eingabezeit muss nach der aktuellen Zeit liegen (maximal 24 h voraus).')
                self.query=copy.deepcopy(query)
                self.source_key=key
                self._new(snapshot,'Codequelle ausgewählt; Kaltstart.',at)
            else:
                # Validate without reading mutable firmware again: this session owns a snapshot.
                if not self.session or self.status=='error':
                    raise WorkerError(self.error or 'Keine laufende Sitzung. Reset erforderlich.')
                packet=self.backend.input_packet(query,self.session.snapshot)
                self.session.schedule(packet,at)
                self.query=copy.deepcopy(query)
            return self.frame()

    def control(self,action,**data):
        with self.lock,self.backend.LOCK:
            if action=='scenario':
                definition=data.get('definition')
                self.scenario=scenarios.validate(definition,self.backend.FIELDS) if definition is not None else None
                if not self.source_key:raise ValueError('Zuerst Firmware auswählen.')
                self._new(self._source(),'Szenario gewählt; expliziter Kaltstart.')
            elif action=='reset':
                if not self.source_key:
                    raise ValueError('Zuerst Firmware und Eingaben auswählen.')
                self._new(self._source(),'Reset angefordert; Firmware-RAM verworfen.')
            elif not self.session or self.status=='error':
                raise WorkerError(self.error or 'Zuerst Firmware auswählen.')
            elif action in ('start','resume'):
                finished=self.session.end_ms is not None and self.session.now>=self.session.end_ms
                self.running=not finished;self.status='finished' if finished else 'running';self.wall=self.clock()
            elif action=='pause':
                self.pump();self.running=False;self.status='paused';self.wall=self.clock()
            elif action=='speed':
                value=data.get('speed')
                if type(value) not in (int,float) or value not in (0.25,0.5,1,2,4,8):
                    raise ValueError('Ungültige Abspielgeschwindigkeit.')
                # Accrue old speed up to the change; preserve outstanding budget.
                self.pump();self.speed=float(value);self.wall=self.clock()
            elif action in ('step','advance'):
                self.running=False;self.status='paused'
                target=self.session.now+1 if action=='step' else data.get('target_ms')
                self.session.advance_to(target)
                self.wall=self.clock();self.budget=0
            elif action=='inspect':
                self.session.inspect(data.get('page'))
            elif action=='can':
                event=data.get('event');scenarios.shape(event,('can_id','dlc','data'),('can_id','dlc','data'))
                self.session.schedule({'_can':scenarios.can_frame(event)},data.get('at_ms'))
            elif action=='pulse':
                button=data.get('button');start=data.get('at_ms',self.session.now+1);duration=data.get('duration_ms',100)
                if button not in ('ts_button','r2d_button') or type(duration) is not int or not 1<=duration<=60000:
                    raise ValueError('Ungültiger lokaler Tastendruck.')
                if type(start) is not int or not self.session.now<start or start+duration>self.session.now+86400000 or len(self.session.events)>1022:
                    raise ValueError('Ungültige Tasterzeit oder zu viele Ereignisse.')
                if self.session.end_ms is not None and start+duration>self.session.end_ms:raise ValueError('Tasterimpuls endet nach dem Replay-Ende.')
                self.session.schedule({'values':{button:1}},start)
                self.session.schedule({'values':{button:0}},start+duration)
            else:
                raise ValueError('Unbekannte Sitzungsaktion.')
            if self.session.end_ms is not None and self.session.now>=self.session.end_ms:self.running=False;self.status='finished'
            return self.frame()

    def frame(self):
        with self.lock:
            if self.status=='error':
                raise WorkerError(self.notice+'\n'+self.error)
            if not self.session:
                raise ValueError('Noch keine Firmware-Sitzung. Firmware auswählen.')
            # Pure read: no source scan, tick, worker restart, or input changes.
            result=self.session.frame()
            requested=self.query.get('page',[result['page']])[0]
            if self.scenario is None:result['page']=requested if requested in result['pages'] else result['pages'][0]
            result['session']['selection']=dict(source=self.query.get('source',['auto'])[0],ref=self.query.get('ref',[''])[0],scenario=result['input_state']['scenario'])
            result['session'].update(status='running' if self.running else self.status,speed=self.speed,
                                     generation=self.generation,notice=self.notice,backlog_ms=int(self.budget))
            return result

    def close(self):
        self.stopped.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=4)
        with self.lock:
            if self.session:
                self.session.close();self.session=None
        atexit.unregister(self.close)
