#!/usr/bin/env python3
"""Read-only firmware preview. Generated host builds live in temporary directories."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from . import settings
from . import profiles
from . import firmware
from . import host_can
from . import host_session
from . import simulation
from . import scenarios
from .firmware import uncomment, strip_includes, replace_body

from .paths import PROJECT_ROOT as ROOT
REPO = None
CONFIG_DIR = None
BUILD_ROOT = None
REF = 'origin/TY26_Test'
FILES = ['main.c', 'candata.c', 'candata.h', 'canlib.h', 'display.c', 'display.h', 'portextender.h', 'portextender.c', 'port_definitions.c', 'port_definitions.h']
LOCK = threading.RLock()
CACHE = {}
BUILDS = {}
INTERACTIVE = None
SCENARIOS = None

from .fields import FIELDS


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args], stderr=subprocess.PIPE, timeout=8).decode('utf-8', errors='replace').strip()


def branch_info():
    try:
        return git('branch', '--show-current'), git('rev-parse', '--short', 'HEAD')
    except (OSError, subprocess.SubprocessError):
        return '', 'Git nicht verfügbar'


def refs():
    if REPO is None:
        return []
    try:
        return [r for r in git('for-each-ref', '--format=%(refname:short)', 'refs/heads/', 'refs/remotes/').splitlines() if not r.endswith('/HEAD')]
    except (OSError, subprocess.SubprocessError):
        return []


def compiler():
    custom = os.environ.get('DIC_CC')
    if custom:
        found = shutil.which(custom)
        if not found:
            raise ValueError('DIC_CC verweist auf keinen verfügbaren Compiler. Erwartet wird ein ausführbarer Dateipfad ohne zusätzliche Argumente.')
        return found
    if sys.platform == 'win32':
        candidates = [Path(os.environ.get('MSYS2_ROOT', 'C:/msys64')) / 'ucrt64/bin/gcc.exe']
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        names = ('gcc', 'clang')
    else:
        names = ('clang', 'gcc')
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    raise ValueError('Kein C-Compiler gefunden. macOS: Apple Command Line Tools installieren. Windows: MSYS2 UCRT64 mit mingw-w64-ucrt-x86_64-gcc installieren. Siehe README.')


def process_environment():
    env = os.environ.copy()
    env['PATH'] = str(Path(compiler()).parent) + os.pathsep + env.get('PATH', '')
    return env


def configure(path):
    global REPO
    root = settings.validate_firmware(path, FILES)
    with LOCK:
        settings.save_firmware(root, CONFIG_DIR)
        REPO = root
        CACHE.clear()
    return configuration()


def configuration():
    valid = False
    error = ''
    if REPO is not None:
        try:
            settings.validate_firmware(str(REPO), FILES)
            valid = True
        except ValueError as exc:
            error = str(exc)
    try:
        cc = compiler()
    except ValueError as exc:
        cc = None
        error = error or str(exc)
    branch, commit = branch_info() if valid else ('', '')
    working_files = None
    if valid:
        try:
            working_files = git('--no-optional-locks', 'status', '--porcelain', '--untracked-files=no').splitlines()
        except (OSError, subprocess.SubprocessError):
            pass
    return dict(configured=valid, path=str(REPO) if REPO else '', refs=refs() if valid else [], branch=branch, commit=commit, compiler=cc, error=error, working_files=working_files)


def choose_folder():
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('choose_folder.py'))], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
        if result.returncode:
            raise ValueError('Ordnerdialog konnte nicht geöffnet werden. Bitte den Pfad manuell eingeben.')
        value = json.loads(result.stdout)
        if value.get('error'):
            raise ValueError(value['error'])
        return value
    except subprocess.TimeoutExpired:
        raise ValueError('Ordnerdialog nach 120 Sekunden beendet. Bitte erneut öffnen oder den Pfad eingeben.') from None


def sources(mode, ref=None):
    if REPO is None:
        raise ValueError('Bitte zuerst den Firmware-Ordner auswählen.')
    settings.validate_firmware(str(REPO), FILES)
    branch, commit = branch_info()
    local = mode in ('auto', 'local')
    if local:
        base = (REPO / 'DIC_23').resolve()
        def checked(name):
            path = (base / name).resolve()
            if base not in path.parents:
                raise ValueError('Include außerhalb von DIC_23 wird nicht unterstützt: ' + name)
            return path
        exists = lambda name: checked(name).is_file()
        read = lambda name: checked(name).read_bytes()
        label = f'Arbeitsordner · {branch or "detached HEAD"} · gespeicherte Dateien'
    else:
        selected_ref = ref if mode == 'ref' else REF
        if selected_ref not in refs():
            raise ValueError('Dieser Git-Stand ist lokal nicht verfügbar. Bitte einen vorhandenen Branch auswählen.')
        exact = git('rev-parse', selected_ref)
        available = set(git('ls-tree', '-r', '--name-only', exact, '--', 'DIC_23').splitlines())
        def exists(name):
            if name.startswith('/') or '..' in Path(name).parts:
                raise ValueError('Include außerhalb von DIC_23 wird nicht unterstützt: ' + name)
            return 'DIC_23/' + name in available
        read = lambda name: subprocess.check_output(['git', '-C', str(REPO), 'show', f'{exact}:DIC_23/{name}'], stderr=subprocess.PIPE, timeout=8)
        commit = exact[:7]
        label = f'{selected_ref} · {commit} · lokal gespeicherter Git-Stand'
    def read_snapshot():
        result=firmware.discover(read, exists, FILES)
        for name in ('sys_timer.c','sys_timer.h','canlib.c'):
            if not exists(name):
                raise ValueError('Benötigte Firmware-Datei fehlt: DIC_23/'+name)
            result[name]=read(name).decode('utf-8',errors='replace')
        return result
    contents = read_snapshot()
    if local and contents != read_snapshot():
        raise ValueError('Firmware-Dateien wurden während des Einlesens geändert. Bitte Speichern abschließen.')
    digest = hashlib.sha256(b'host-adapter-replay-v1' + b''.join(k.encode() + b'\0' + v.encode() + b'\0' for k,v in sorted(contents.items()))).hexdigest()
    return contents, label, branch, commit, digest, local


PRELUDE = host_session.PRELUDE



SPI_WRITE = r'''
    (void)control;
    if ((reg==PE_OLAT || reg==PE_GPIO) && (unsigned)extender<2)
        extender_latch[extender]=data;
    spi_state=0;
'''

DISPLAY_WRITE = 'preview_lcd_write(data,rs);'


HOOK = r'void draw_char(struct DISPLAY_PAGE *display,struct DISPLAY_STATE *state) { firmware_draw_char(display,state); }'


def compile_preview(src, digest):
    if digest in BUILDS:
        CACHE.clear(); CACHE.update(BUILDS[digest])
        return CACHE['binary'], CACHE['pages']
    CACHE.clear()  # A failed rebuild must not leave a cached executable reusable.
    render_file, render_name = firmware.render_hook(src)
    adapted = {name: host_session.time_types(firmware.host_page_table(code)) for name,code in src.items()}
    adapted[render_file] = firmware.rename_definition(adapted[render_file], render_name)
    headers = firmware.headers(adapted)
    led_source = strip_includes(adapted['portextender.c'])
    led_source = replace_body(led_source,'configure_spi_bus','spi_state=0;',required=False)
    led_source = replace_body(led_source,'send_data',SPI_WRITE,required=False)
    led_source = replace_body(led_source,'send_data_blocking',SPI_WRITE,required=False)
    display = strip_includes(adapted['display.c'])
    display = replace_body(display, 'display_write_data', DISPLAY_WRITE)
    main = strip_includes(adapted['main.c'])
    # Car uses a GCC nested fan-LED function. It captures no outer locals;
    # move it to file scope only in the generated host copy for Apple clang.
    main = re.sub(r'\bvoid\s+Akku_fan_LED\s*\(\s*Akku_fan_status\s*\)',
                  'void Akku_fan_LED(uint8_t Akku_fan_status)', main)
    fan = re.search(r'\bvoid\s+Akku_fan_LED\s*\([^)]*\)\s*\{', main)
    if fan:
        depth = 1
        token = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*|[{}]', re.S)
        for part in token.finditer(main, fan.end()):
            if part[0] == '{': depth += 1
            elif part[0] == '}': depth -= 1
            if depth == 0:
                end = part.end()
                function = main[fan.start():end]
                main = function + '\n' + main[:fan.start()] + main[end:]
                break
    # Host-only portability: AVR pointers are 16 bit, macOS pointers are 64 bit.
    main = re.sub(r'\b(?:uint16_t|uint32_t|unsigned\s+long)(?=\s+page_order\b)', 'uintptr_t', main)
    # The firmware leaves this local uninitialized; deterministic simulated clock origin.
    main = re.sub(r'(volatile\s+uint32_t\s+sys_time_old)\s*;', r'\1 = sys_time;', main)
    main = re.sub(r'\bint\s+main\s*\(', 'int firmware_main(', main, count=1)
    main = host_session.instrument_main(main)
    inputs = f'#define INPUT_COUNT {len(FIELDS)}\nstatic long inputs[INPUT_COUNT];\n'
    inputs += '\n'.join(f'#define input_{f["id"]} inputs[{i}]' for i,f in enumerate(FIELDS))
    diagnostic_source = uncomment(src['candata.c'])
    if all(re.search(r'\buint8_t\s+' + name + r'\s*=', diagnostic_source) for name in ('ams_diagnostic_code','ams_diagnostic_valid')):
        inputs += '\n#define PREVIEW_HAS_AMS_DIAG 1\n'
    gpio = '\n'.join(f'#define P{port}{bit} {bit}' for port in 'ABCDEFG' for bit in range(8))
    gpio += '\n' + '\n'.join(f'uint8_t PORT{port}=0, DDR{port}=0;' for port in 'ABCDEFG')
    extra = '\n'.join(firmware.unit(name, strip_includes(code)) for name,code in adapted.items() if name.endswith('.c') and name not in ('main.c','candata.c','display.c','portextender.c','port_definitions.c','sys_timer.c','canlib.c'))
    hook = HOOK.replace('draw_char', render_name).replace('firmware_' + render_name, 'preview_real_' + render_name)
    hook_prototype = 'void ' + render_name + '(struct DISPLAY_PAGE *,struct DISPLAY_STATE *);'
    combined = '\n'.join([gpio,PRELUDE,inputs,headers,host_can.REGISTERS,host_session.PROTOTYPE,hook_prototype,firmware.unit('canlib.c',host_can.driver(adapted['canlib.c'])),firmware.unit('port_definitions.c',strip_includes(adapted['port_definitions.c'])),firmware.unit('portextender.c',led_source),firmware.unit('candata.c',strip_includes(adapted['candata.c'])),extra,firmware.unit('display.c',display),hook,firmware.unit('main.c',main),host_session.entry(src,FIELDS)])
    # GPIO declarations need stdint before the prelude too.
    combined = '#include <stdint.h>\n' + combined
    if BUILD_ROOT is None:
        raise ValueError('Temporärer Build-Ordner ist nicht eingerichtet. Bitte über start.py starten.')
    build = BUILD_ROOT / digest[:20]
    if REPO is not None and (build.resolve() == REPO or REPO in build.resolve().parents):
        raise ValueError('Build-Ordner darf nicht im Firmware-Repository liegen.')
    build.mkdir(parents=True,exist_ok=True)
    generated = build / 'host-preview.c'
    generated.write_text(combined, encoding='utf-8')
    binary = build / ('host-preview.exe' if sys.platform == 'win32' else 'host-preview')
    preprocess = subprocess.run([compiler(),'-std=gnu11','-E','-P',str(generated)], capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20,env=process_environment(),cwd=build)
    if preprocess.returncode:
        raise ValueError('Vorschau konnte nicht kompiliert werden (Präprozessor).\n' + preprocess.stderr[-10000:])
    pages = firmware.page_names(preprocess.stdout)
    assertion = '\n_Static_assert(sizeof(page_order)/sizeof(page_order[0]) == ' + str(len(pages)) + ', \"page_order: Arraygroesse und Seiteneintraege stimmen nicht ueberein\");'
    combined = re.sub(r'(\bpage_order\s*\[[^]]*\]\s*=\s*\{.*?\}\s*;)', lambda m: m[0] + assertion, combined, count=1, flags=re.S)
    generated.write_text(combined, encoding='utf-8')
    result = subprocess.run([compiler(),'-std=gnu11','-O0','-Wno-int-conversion','-Werror=implicit-function-declaration',str(generated),'-o',str(binary),'-lm'], capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20,env=process_environment(),cwd=build)
    if result.returncode:
        raise ValueError('Vorschau konnte nicht kompiliert werden. Es wird kein alter Stand angezeigt.\nNeue C-Dateien werden über eingebundene lokale Header und gleichnamige .c-Dateien erkannt. Unbekannte Hardwarefunktionen benötigen einen Host-Adapter.\n'+result.stderr[-10000:])
    CACHE.update(digest=digest,binary=binary,pages=pages,compiled_at=time.time())
    BUILDS[digest]=dict(CACHE)
    return binary,pages


def input_packet(query, snapshot):
    src=snapshot[0]
    values={}
    for f in FIELDS:
        v=int(query.get(f['id'],[str(f['default'])])[0])
        if not f['min']<=v<=f['max']:
            raise ValueError('Wert außerhalb des Bereichs: '+f['label'])
        values[f['id']]=v
    scenario=query.get('scenario',['example'])[0]
    if scenario not in ('example','zero'):
        raise ValueError('Unbekanntes Eingabeszenario.')
    if scenario=='zero':
        for f in FIELDS:
            if f['group']!='Bedienung / Zeit': values[f['id']]=0
    overrides=profiles.raw_bytes(query.get('raw',[''])[0])
    fuse=next((p[7] for i,p in reversed(overrides) if i==0x600),values['fuse'])
    if 'fr_values[fuse_readout]' in uncomment(src['candata.c']) and ((fuse & 11111110)//10)>=14:
        raise ValueError('Dieser Fusebox-Rohwert greift im alten Car-Code außerhalb des Arrays zu.')
    return dict(values=values,page=query.get('page',['dsp_startup'])[0],overrides=overrides,scenario=scenario)


def frame(query, snapshot=None):
    """Isolated compatibility runner for CLI/tests, never used by browser GETs.

    A genuine cold start followed by every single 1 ms tick. Duration is elapsed
    since zero, no hidden 20-second clock offset. Each caller owns its worker.
    """
    mode=query.get('source',['auto'])[0]
    if mode not in ('auto','local','test','ref'):
        raise ValueError('Unbekannte Quelle')
    with LOCK:
        snapshot=snapshot or sources(mode,query.get('ref',[None])[0])
        packet=input_packet(query,snapshot)
        session=simulation.Session(sys.modules[__name__],snapshot,packet)
    with session:
        return session.advance_to(packet['values']['duration'])


def interactive():
    global INTERACTIVE
    with LOCK:
        if INTERACTIVE is None:
            INTERACTIVE=simulation.Interactive(sys.modules[__name__])
        return INTERACTIVE


def scenario_library():
    global SCENARIOS
    with LOCK:
        if SCENARIOS is None:SCENARIOS=scenarios.Library(ROOT,FIELDS)
        return SCENARIOS


def session_request(data):
    action=data.get('action')
    if action=='scenario' and 'id' in data:
        key=data['id']
        if not isinstance(key,str) or (key and key not in scenario_library().items):raise ValueError('Unbekanntes Szenario.')
        return interactive().control('scenario',definition=scenario_library().items[key] if key else None)
    if action=='inputs':
        query=data.get('query')
        if not isinstance(query,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in query.items()):
            raise ValueError('Eingaben müssen ein Objekt mit Textwerten sein.')
        if query.get('source','auto') not in ('auto','local','test','ref'):
            raise ValueError('Unbekannte Codequelle.')
        return interactive().inputs({k:[v] for k,v in query.items()},data.get('at_ms'))
    return interactive().control(action,**{k:v for k,v in data.items() if k!='action'})


def profile_store():
    return profiles.Store(CONFIG_DIR or settings.settings_directory(), FIELDS, REPO)


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address):
        self.token = secrets.token_urlsafe(32)
        super().__init__(address, Handler)
        self.origin = f'http://127.0.0.1:{self.server_port}'


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, payload, mime='application/json; charset=utf-8'):
        body = json.dumps(payload).encode('utf-8') if not isinstance(payload, bytes) else payload
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self, api=False):
        expected_host = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != expected_host:
            self.respond(403, {'ok': False, 'error': 'Ungültiger lokaler Host.'})
            return False
        origin = self.headers.get('Origin')
        if (origin is not None and origin != self.server.origin) or self.headers.get('Sec-Fetch-Site') == 'cross-site':
            self.respond(403, {'ok': False, 'error': 'Fremde Browseranfrage abgelehnt.'})
            return False
        if api and not secrets.compare_digest(self.headers.get('X-DIC-Token', ''), self.server.token):
            self.respond(403, {'ok': False, 'error': 'Sitzung abgelaufen. Bitte diese Vorschauseite neu laden.'})
            return False
        return True

    def do_GET(self):
        url = urlparse(self.path)
        if not self.authorized(api=url.path.startswith('/api/')):
            return
        if url.path in ('/', '/index.html'):
            html = (ROOT / 'web/index.html').read_text(encoding='utf-8')
            self.respond(200, html.replace('__DIC_TOKEN__', self.server.token).encode('utf-8'), 'text/html; charset=utf-8')
        elif url.path in ('/lcd.js','/app.js','/profiles.js','/tests.js','/session.js','/replay.js'):
            self.respond(200, (ROOT / 'web' / url.path[1:]).read_bytes(), 'text/javascript; charset=utf-8')
        elif url.path == '/styles.css':
            self.respond(200, (ROOT / 'web/styles.css').read_bytes(), 'text/css; charset=utf-8')
        elif url.path == '/api/scenarios':
            with LOCK:self.respond(200,dict(ok=True,scenarios=scenario_library().listing()))
        elif url.path == '/api/config':
            self.respond(200, configuration())
        elif url.path == '/api/profiles':
            try:
                self.respond(200, dict(ok=True, profiles=profile_store().list(), fields=FIELDS))
            except (ValueError, OSError) as exc:
                self.respond(422, dict(ok=False, error=str(exc)))
        elif url.path == '/api/tests':
            from . import verify
            self.respond(200, dict(ok=True, tests=verify.catalog()))
        elif url.path == '/api/frame':
            try:
                self.respond(200, interactive().frame())
            except subprocess.TimeoutExpired:
                self.respond(422, {'ok': False, 'error': 'Zeitlimit beim Lesen, Kompilieren oder Simulieren erreicht. Bitte den C-Code prüfen.'})
            except Exception as exc:
                self.respond(422, {'ok': False, 'error': str(exc)})
        else:
            self.respond(404, {'ok': False, 'error': 'Nicht gefunden.'})

    def do_POST(self):
        if not self.authorized(api=True):
            return
        try:
            if self.headers.get_content_type() != 'application/json':
                self.respond(415, {'ok': False, 'error': 'JSON-Anfrage erwartet.'})
                return
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= (8*1024*1024 if self.path=='/api/scenarios' else 65536):
                raise ValueError('Anfrage zu groß.')
            data = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(data, dict):
                raise ValueError('JSON-Objekt erwartet.')
            if self.path == '/api/config':
                self.respond(200, dict(ok=True, **configure(data.get('path'))))
            elif self.path == '/api/scenarios':
                with LOCK:
                    if data.get('action')=='export':
                        key=data.get('id')
                        if not isinstance(key,str) or key not in scenario_library().items:raise ValueError('Unbekanntes Szenario.')
                        self.respond(200,dict(ok=True,scenario=scenario_library().items[key]))
                    elif data.get('action')=='import':
                        definition=scenarios.import_text(data.get('text'),data.get('kind'),FIELDS,data.get('name','Log-Import'),data.get('offset_ms',0))
                        key=scenario_library().add(definition)
                        self.respond(200,dict(ok=True,selected=key,scenarios=scenario_library().listing()))
                    else:raise ValueError('Unbekannte Szenarioaktion.')
            elif self.path == '/api/session':
                self.respond(200, session_request(data))
            elif self.path == '/api/profiles':
                self.respond(200, profile_store().change(data))
            elif self.path == '/api/tests':
                from . import verify
                self.respond(200, verify.run_suite(sys.modules[__name__], data.get('source', 'auto'), data.get('ref'), data.get('test', 'all')))
            elif self.path == '/api/choose-folder':
                self.respond(200, dict(ok=True, **choose_folder()))
            else:
                self.respond(404, {'ok': False, 'error': 'Nicht gefunden.'})
        except (ValueError, OSError, subprocess.SubprocessError, RecursionError) as exc:
            self.respond(422, {'ok': False, 'error': str(exc)})

    def do_OPTIONS(self):
        self.respond(403, {'ok': False, 'error': 'Keine fremden Browseranfragen erlaubt.'})

    def log_message(self, *args):
        # Do not log local paths, data bytes or tokens.
        pass


def main(open_browser=False):
    global CONFIG_DIR, REPO, BUILD_ROOT
    parser = argparse.ArgumentParser(description='Lokale DIC-Visualisierung')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--config-dir', type=Path)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    CONFIG_DIR = args.config_dir or settings.settings_directory()
    saved = settings.load(CONFIG_DIR).get('firmware_path')
    if isinstance(saved, str) and saved:
        REPO = Path(saved).expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix='DIC_Visualisierung-') as build:
        BUILD_ROOT = Path(build)
        try:
            http = LocalServer(('127.0.0.1', args.port))
        except OSError as exc:
            import errno
            if exc.errno != errno.EADDRINUSE and getattr(exc, 'winerror', None) != 10048:
                raise
            http = LocalServer(('127.0.0.1', 0))
        def stop_signal(signum,frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,stop_signal)
        try:
            with http:
                print(f'DIC_Visualisierung: {http.origin}/', flush=True)
                print('Nur lokal. Dieses Fenster geöffnet lassen; Strg+C beendet die Vorschau.', flush=True)
                if open_browser and not args.no_browser:
                    webbrowser.open(http.origin + '/')
                try:
                    http.serve_forever()
                except KeyboardInterrupt:
                    pass
        finally:
            if INTERACTIVE is not None:
                INTERACTIVE.close()
            CACHE.clear(); BUILDS.clear()
            BUILD_ROOT = None



if __name__ == '__main__':
    main()
