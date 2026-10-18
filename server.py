#!/usr/bin/env python3
"""Read-only firmware preview. All generated host files stay beside this script."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
import settings

ROOT = Path(__file__).resolve().parent
REPO = None
CONFIG_DIR = None
BUILD_ROOT = None
REF = 'origin/TY26_Test'
FILES = ['main.c', 'candata.c', 'candata.h', 'canlib.h', 'display.c', 'display.h', 'portextender.h', 'portextender.c', 'port_definitions.c', 'port_definitions.h']
LOCK = threading.Lock()
CACHE = {}

# Values passed to the C harness use integer CAN units; divisor affects only UI units.
FIELDS = [
    dict(id=k, label=label, group=group, default=default, min=minimum, max=maximum, divisor=divisor, options=options)
    for k,label,group,default,minimum,maximum,divisor,options in [
        ('front','Bremsdruck vorne · Anzeigewert','Fahren',42,0,1000,1,None),
        ('rear','Bremsdruck hinten · Anzeigewert','Fahren',30,0,1000,1,None),
        ('apps1','Gaspedal APPS1 · %','Fahren',750,0,1000,10,None),
        ('apps2','Gaspedal APPS2 · %','Fahren',760,0,1000,10,None),
        ('steering','Lenkwinkel · vorzeichenbehafteter CAN-Wert','Fahren',12,-128,127,1,None),
        ('speed','Geschwindigkeit · km/h','Fahren',523,0,9999,10,None),
        ('gps_mode','GPS-Empfang','Fahren',0,0,1,1,[(0,'Aktuell'),(1,'Nach 0,5 s keine neuen Daten')]),
        ('ts','Hochvoltspannung · V','AMS / Akku',54000,0,65535,100,None),
        ('accu','Akkutemperatur · Anzeige °C¹','AMS / Akku',32400,0,65535,1000,None),
        ('ams_error','AMS-Fehlerbit','AMS / Akku',0,0,1,1,[(0,'Kein Fehler'),(1,'Fehler gesetzt')]),
        ('imd_error','IMD-Fehlerbit','AMS / Akku',0,0,1,1,[(0,'Kein Fehler'),(1,'Fehler gesetzt')]),
        ('diag','AMS-Diagnosecode · Byte 0','AMS / Akku',0,0,255,1,None),
        ('diag_mode','AMS-Diagnoseempfang','AMS / Akku',0,0,1,1,[(0,'Aktuell'),(1,'Nach 0,5 s keine neuen Daten')]),
        ('ams_mode','AMS-Lebenszeichen / Empfang','AMS / Akku',0,0,2,1,[(0,'Zähler läuft'),(1,'Zähler bleibt stehen'),(2,'Nach 0,5 s keine AMS-Daten')]),
        ('precharge','Vorladung · Statusbit','AMS / Akku',0,0,1,1,[(0,'Aus'),(1,'Aktiv')]),
        ('can_ok','CAN_OK · Statusbit','AMS / Akku',1,0,1,1,[(0,'0'),(1,'1')]),
        ('ts_ready','TS_RDY · Statusbit','AMS / Akku',0,0,1,1,[(0,'0'),(1,'1')]),
        ('soc','Ladezustand · CAN-Rohwert²','AMS / Akku',0,0,65535,1,None),
        ('current','Strom · CAN-Rohwert²','AMS / Akku',0,0,65535,1,None),
        ('inv0','Invertertemperatur · Nachricht 0x44A · °C','Temperaturen / Versorgung',456,0,65535,10,None),
        ('inv1','Invertertemperatur · Nachricht 0x453 · °C','Temperaturen / Versorgung',430,0,65535,10,None),
        ('motor0','Motortemperatur · Nachricht 0x44A · °C','Temperaturen / Versorgung',723,0,65535,10,None),
        ('motor1','Motortemperatur · Nachricht 0x453 · °C','Temperaturen / Versorgung',700,0,65535,10,None),
        ('lv','Niedervoltspannung · Anzeige V¹','Temperaturen / Versorgung',128,0,65535,10,None),
        ('cooling','Kühlung · CAN-Rohwert²','Temperaturen / Versorgung',0,0,65535,1,None),
        ('fan','Akku-Lüfter · Fusebox Byte 6 Bit 0','Fusebox / SDC',0,0,1,1,[(0,'Aus'),(1,'An')]),
        ('fuse','Sicherungsstatus · Fusebox Byte 7 · Rohwert','Fusebox / SDC',0,0,255,1,None),
        *[(key,label,'Fusebox / SDC',1,0,1,1,[(0,'Low'),(1,'High')]) for key,label in [('sdc15','B_DB'),('sdc14','INER'),('sdc13','BOTS'),('sdc12','B_L'),('sdc11','DIST'),('sdc8','TSAC'),('sdc7','B_R'),('sdc6','TSMS')]],
        ('ts_button','Lokaler TS_ON-Taster','Bedienung / Zeit',0,0,1,1,[(0,'Nicht gedrückt'),(1,'Gedrückt')]),
        ('r2d_button','Lokaler Ready-to-Drive-Taster','Bedienung / Zeit',0,0,1,1,[(0,'Nicht gedrückt'),(1,'Gedrückt')]),
        ('mode','Anfänglicher Fahrmodus','Bedienung / Zeit',3,0,5,1,[(0,'Accel'),(1,'Skidpad'),(2,'Autocross'),(3,'Endurance'),(4,'Fun 1'),(5,'Fun 2')]),
        ('buttons','Lenkradtasten · Bitmaske 0–15','Bedienung / Zeit',0,0,15,1,None),
        ('duration','Simulierte Laufzeit nach Start · s','Bedienung / Zeit',3200,100,10000,1000,None),
    ]
]


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
        result = subprocess.run([sys.executable, str(ROOT / 'choose_folder.py')], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
        if result.returncode:
            raise ValueError('Ordnerdialog konnte nicht geöffnet werden. Bitte den Pfad manuell eingeben.')
        value = json.loads(result.stdout)
        if value.get('error'):
            raise ValueError(value['error'])
        return value
    except subprocess.TimeoutExpired:
        raise ValueError('Ordnerdialog nach 120 Sekunden beendet. Bitte erneut öffnen oder den Pfad eingeben.') from None


def uncomment(s):
    return re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*',
                  lambda m: m[0] if not m[0].startswith('/') else ' ', s, flags=re.S)


def strip_includes(s):
    return re.sub(r'^\s*#\s*include[^\n]*', '', s, flags=re.M)


def replace_body(s, name, body):
    """Replace only the host copy of a hardware function, respecting C strings/comments."""
    match = re.search(r'\bvoid\s+' + name + r'\s*\([^)]*\)\s*\{', s)
    if not match:
        raise ValueError(f'Hardwareadapter: Funktion {name} nicht gefunden')
    depth = 1
    token = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*|[{}]', re.S)
    for part in token.finditer(s, match.end()):
        if part[0] == '{':
            depth += 1
        elif part[0] == '}':
            depth -= 1
        if depth == 0:
            return s[:match.end()] + '\n' + body + '\n' + s[part.start():]
    raise ValueError(f'Unvollständige Funktion: {name}')


def sources(mode, ref=None):
    if REPO is None:
        raise ValueError('Bitte zuerst den Firmware-Ordner auswählen.')
    settings.validate_firmware(str(REPO), FILES)
    branch, commit = branch_info()
    local = mode in ('auto', 'local')
    if local:
        contents = {name: (REPO / 'DIC_23' / name).read_bytes() for name in FILES}
        label = f'Arbeitsordner · {branch or "detached HEAD"} · gespeicherte Dateien'
    else:
        selected_ref = ref if mode == 'ref' else REF
        if selected_ref not in refs():
            raise ValueError('Dieser Git-Stand ist lokal nicht verfügbar. Bitte einen vorhandenen Branch auswählen.')
        contents = {name: subprocess.check_output(['git', '-C', str(REPO), 'show', f'{selected_ref}:DIC_23/{name}'], stderr=subprocess.PIPE, timeout=8) for name in FILES}
        commit = git('rev-parse', '--short', selected_ref)
        label = f'{selected_ref} · {commit} · lokal gespeicherter Git-Stand'
    digest = hashlib.sha256(b'host-adapter-v6' + b''.join(contents.values())).hexdigest()
    return {k: v.decode('utf-8', errors='replace') for k, v in contents.items()}, label, branch, commit, digest, local


PRELUDE = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#define wait preview_wait
#define RXOK 0
#define MOBNB0 4
uint8_t PINA=255, CANPAGE=0, SPCR=0, SPDR=0;
#define SPE 6
#define SPIE 7
#define MSTR 4
#define SPR0 0
#define ISR(vector) void preview_##vector(void)
static uint8_t preview_rx_status(uint8_t page);
#define CANSTMOB preview_rx_status(CANPAGE)
volatile unsigned long sys_time=20000;
volatile uint8_t draw_data=1;
static unsigned requested_page;
static uint8_t extender_latch[2]={255,255};
static uint8_t tx_bytes[8];
struct RAW_OVERRIDE {unsigned id; uint8_t data[8];};
static struct RAW_OVERRIDE overrides[16];
static unsigned override_count=0;
static jmp_buf finished;
static uint8_t captured[4][20], glyphs[8][8];
static int glyph_address=-1;
void sys_timer_config(void) {}
void sei(void) {}
'''

STUBS = r'''
void can_cfg(void) {}
void can_tx(struct CAN_MOB *m, uint8_t *data) {(void)m;memcpy(tx_bytes,data,8);}
static void little16(uint8_t *p, unsigned n) {p[0]=n&255;p[1]=(n>>8)&255;}
static void big16(uint8_t *p, unsigned n) {p[0]=(n>>8)&255;p[1]=n&255;}
static uint8_t preview_rx_status(uint8_t page) {
    if(sys_time<20500)return 1;
    if((page>>MOBNB0)==11 && input_gps_mode)return 0;
    if((page>>MOBNB0)==12 && input_diag_mode)return 0;
    return 1;
}
void can_rx(struct CAN_MOB *m, uint8_t *data) {
    if(input_ams_mode==2 && sys_time>=20500 && (m->mob_id==0x200||m->mob_id==0x201))return;
    if(sys_time>=20500 && ((m->mob_id==0x797 && input_gps_mode)||(m->mob_id==0x204 && input_diag_mode)))return;
    memset(data,0,8);
    switch(m->mob_id) {
        case 0x200:
            little16(data,input_ts);little16(data+2,input_current);little16(data+4,input_soc);
            data[6]=(input_ams_error<<7)|(input_imd_error<<6)|(input_can_ok<<5)|(input_precharge<<4)|(input_ts_ready<<3);
            data[7]=input_ams_mode==1?1:((sys_time/10)&255);break;
        case 0x201: little16(data+6,input_accu);break;
        case 0x204: data[0]=input_diag;break;
        case 0x401: little16(data,input_front*10);little16(data+2,input_rear*10);break;
        case 0x400: data[7]=(uint8_t)(int8_t)input_steering;break;
        case 0x420: little16(data,input_cooling);break;
        case 0x300: little16(data,input_apps1);little16(data+2,input_apps2);break;
        case 0x600:
            little16(data+2,input_lv);
            little16(data+4,(input_sdc15<<15)|(input_sdc14<<14)|(input_sdc13<<13)|(input_sdc12<<12)|(input_sdc11<<11)|(input_sdc8<<8)|(input_sdc7<<7)|(input_sdc6<<6));
            data[6]=input_fan;data[7]=input_fuse;break;
        case 0x750:
            data[1]=requested_page;data[2]=input_buttons&1;data[3]=(input_buttons>>1)&1;
            data[4]=!((input_buttons>>2)&1);data[6]=!((input_buttons>>3)&1);break;
        case 0x44a: big16(data,input_inv0);big16(data+2,input_motor0);break;
        case 0x453: big16(data,input_inv1);big16(data+2,input_motor1);break;
        case 0x797: big16(data+6,input_speed);break;
    }
    for(unsigned n=0;n<override_count;n++)if(overrides[n].id==m->mob_id)memcpy(data,overrides[n].data,8);
}
'''

SPI_WRITE = r'''
    (void)control;
    if ((reg==PE_OLAT || reg==PE_GPIO) && (unsigned)extender<2)
        extender_latch[extender]=data;
    spi_state=0;
'''

DISPLAY_WRITE = r'''
    if (!rs) {
        glyph_address = (data>=0x40 && data<0x80) ? (data&0x3f) : -1;
    } else if (glyph_address>=0 && glyph_address<64) {
        glyphs[glyph_address/8][glyph_address%8]=data&31;
        glyph_address++;
    }
'''

HOOK = r'''
void draw_char(struct DISPLAY_PAGE *display,struct DISPLAY_STATE *state) {
    firmware_draw_char(display,state);
    memcpy(captured,display->data,sizeof captured);
    sys_time++;
    draw_data=1;
    if (sys_time>=20000+(unsigned)input_duration) longjmp(finished,1);
}
'''

ENTRY = r'''
int main(int argc,char **argv) {
    if(argc>1)requested_page=strtoul(argv[1],0,10);
    for(unsigned i=0;i<INPUT_COUNT;i++)if(argc>(int)i+2)inputs[i]=strtol(argv[i+2],0,10);
    if(argc>(int)INPUT_COUNT+2) {
        char *entry=strtok(argv[INPUT_COUNT+2],";");
        while(entry && override_count<16) {
            unsigned id,values[8];
            if(sscanf(entry,"%x:%2x%2x%2x%2x%2x%2x%2x%2x",&id,&values[0],&values[1],&values[2],&values[3],&values[4],&values[5],&values[6],&values[7])==9) {
                overrides[override_count].id=id;
                for(int b=0;b<8;b++)overrides[override_count].data[b]=values[b];
                override_count++;
            }
            entry=strtok(0,";");
        }
    }
    PINA=255;
    if(input_ts_button)PINA&=~(1<<PA0);
    if(input_r2d_button)PINA&=~(1<<PA1);
    active_mode=selected_mode=input_mode;
    if(!setjmp(finished))firmware_main();
    for(int r=0;r<4;r++)for(int c=0;c<20;c++)printf("%02x",captured[r][c]);
    putchar('\n');
    for(int r=0;r<8;r++)for(int c=0;c<8;c++)printf("%02x",glyphs[r][c]);
    putchar('\n');
    printf("{\"ams_led\":%u,\"imd_led\":%u,\"left\":%u,\"right\":%u,\"ports\":{\"A\":%u,\"C\":%u,\"D\":%u,\"G\":%u},\"tx\":[",!!(PORTD&0x9f),(PORTA>>PA2)&1,(uint8_t)~extender_latch[0],(uint8_t)~extender_latch[1],PORTA,PORTC,PORTD,PORTG);
    for(int i=0;i<8;i++)printf("%s%u",i?",":"",tx_bytes[i]);
    printf("]");
#ifdef PREVIEW_HAS_AMS_DIAG
    printf(",\"ams_diagnostic_code\":%u,\"ams_diagnostic_valid\":%u",ams_diagnostic_code,ams_diagnostic_valid);
#endif
    puts("}");
    return 0;
}
'''


def compile_preview(src, digest):
    if CACHE.get('digest') == digest:
        return CACHE['binary'], CACHE['pages']
    clean_main = uncomment(src['main.c'])
    order = re.search(r'\bpage_order\s*\[[^]]*\]\s*=\s*\{(.*?)\}', clean_main, re.S)
    if not order:
        raise ValueError('Seitenreihenfolge page_order nicht gefunden. Adapter muss an die neue Struktur angepasst werden.')
    pages = re.findall(r'&\s*(\w+)', order[1])
    if not pages:
        raise ValueError('Keine Displayseiten gefunden')
    headers = '\n'.join(strip_includes(src[n]) for n in ['canlib.h','candata.h','display.h','portextender.h','port_definitions.h'])
    led_source = strip_includes(src['portextender.c'])
    led_source = replace_body(led_source,'configure_spi_bus','spi_state=0;')
    led_source = replace_body(led_source,'send_data',SPI_WRITE)
    led_source = replace_body(led_source,'send_data_blocking',SPI_WRITE)
    display = strip_includes(src['display.c'])
    display = replace_body(display, 'display_write_data', DISPLAY_WRITE)
    display = re.sub(r'\bvoid\s+draw_char\s*\(', 'void firmware_draw_char(', display, count=1)
    main = strip_includes(src['main.c'])
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
    main = re.sub(r'\buint32_t(?=\s+page_order\b)', 'uintptr_t', main)
    # The firmware leaves this local uninitialized; deterministic simulated clock origin.
    main = re.sub(r'(volatile\s+unsigned\s+long\s+sys_time_old)\s*;', r'\1 = sys_time;', main)
    main = re.sub(r'\bint\s+main\s*\(', 'int firmware_main(', main, count=1)
    inputs = f'#define INPUT_COUNT {len(FIELDS)}\nstatic long inputs[INPUT_COUNT];\n'
    inputs += '\n'.join(f'#define input_{f["id"]} inputs[{i}]' for i,f in enumerate(FIELDS))
    diagnostic_source = uncomment(src['candata.c'])
    if all(re.search(r'\buint8_t\s+' + name + r'\s*=', diagnostic_source) for name in ('ams_diagnostic_code','ams_diagnostic_valid')):
        inputs += '\n#define PREVIEW_HAS_AMS_DIAG 1\n'
    gpio = '\n'.join(f'#define P{port}{bit} {bit}' for port in 'ABCDEFG' for bit in range(8))
    gpio += '\n' + '\n'.join(f'uint8_t PORT{port}=0, DDR{port}=0;' for port in 'ABCDEFG')
    combined = '\n'.join([gpio,PRELUDE,inputs,headers,STUBS,strip_includes(src['port_definitions.c']),led_source,strip_includes(src['candata.c']),display,HOOK,main,ENTRY])
    # GPIO declarations need stdint before the prelude too.
    combined = '#include <stdint.h>\n' + combined
    if BUILD_ROOT is None:
        raise ValueError('Temporärer Build-Ordner ist nicht eingerichtet. Bitte über start.py starten.')
    build = BUILD_ROOT
    if REPO is not None and (build.resolve() == REPO or REPO in build.resolve().parents):
        raise ValueError('Build-Ordner darf nicht im Firmware-Repository liegen.')
    build.mkdir(exist_ok=True)
    generated = build / 'host-preview.c'
    generated.write_text(combined, encoding='utf-8')
    binary = build / ('host-preview.exe' if sys.platform == 'win32' else 'host-preview')
    result = subprocess.run([compiler(),'-std=gnu11','-O0','-Wno-int-conversion',str(generated),'-o',str(binary)], capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20,env=process_environment(),cwd=build)
    if result.returncode:
        raise ValueError('Vorschau konnte nicht kompiliert werden. Es wird kein alter Stand angezeigt.\n'+result.stderr[-10000:])
    CACHE.update(digest=digest,binary=binary,pages=pages,compiled_at=time.time())
    return binary,pages


def frame(query):
    mode=query.get('source',['auto'])[0]
    if mode not in ('auto','local','test','ref'):
        raise ValueError('Unbekannte Quelle')
    with LOCK:
        src,label,branch,commit,digest,local=sources(mode,query.get('ref',[None])[0])
        binary,pages=compile_preview(src,digest)
        selected=query.get('page',[pages[1] if len(pages)>1 else pages[0]])[0]
        if selected not in pages:
            selected=pages[0]
        zero=query.get('scenario',['example'])[0]=='zero'
        values={}
        for f in FIELDS:
            v=int(query.get(f['id'],[str(f['default'])])[0])
            if not f['min']<=v<=f['max']:raise ValueError('Wert außerhalb des Bereichs: '+f['label'])
            values[f['id']]=v
        if zero:
            for f in FIELDS:
                if f['group']!='Bedienung / Zeit': values[f['id']]=0
        overrides=[]
        for line in query.get('raw',[''])[0].splitlines():
            line=line.strip()
            if not line:continue
            match=re.fullmatch(r'(?:0x)?([0-9a-fA-F]{1,3})\s*:\s*((?:[0-9a-fA-F]{2}\s*){8})',line)
            if not match:raise ValueError('CAN-Zeile erwartet z. B. 204: 01 00 00 00 00 00 00 00')
            canid=int(match[1],16)
            if canid not in (0x200,0x201,0x204,0x300,0x400,0x401,0x420,0x44a,0x453,0x600,0x750,0x797):raise ValueError('Unbekannte CAN-ID für Testdaten')
            payload=bytes.fromhex(match[2]);overrides.append((canid,payload))
        if len(overrides)>16:raise ValueError('Maximal 16 CAN-Zeilen')
        # Car indexes a 14-byte array with this legacy expression; avoid undefined host memory writes.
        fuse=next((p[7] for i,p in reversed(overrides) if i==0x600),values['fuse'])
        if 'fr_values[fuse_readout]' in uncomment(src['candata.c']) and ((fuse & 11111110)//10)>=14:
            raise ValueError('Dieser Fusebox-Rohwert würde im vorhandenen Car-Code außerhalb des Sicherungsarrays zugreifen. Bitte Byte 7 ändern.')
        args=[str(binary),str(pages.index(selected))]+[str(values[f['id']]) for f in FIELDS]
        args.append(';'.join(f'{i:x}:{p.hex()}' for i,p in overrides))
        run=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=3,env=process_environment(),cwd=binary.parent)
        if run.returncode: raise ValueError('Fehler bei der Ausführung des Display-Codes: '+run.stderr[-2000:])
        lines=run.stdout.strip().splitlines()
        if len(lines)!=3 or len(lines[0])!=160: raise ValueError('Ungültige Ausgabe des Display-Codes')
        raw=bytes.fromhex(lines[0]); glyphs=bytes.fromhex(lines[1])
        outputs=json.loads(lines[2])
        ports=outputs['ports']
        top_pins=[('A',4),('A',5),('A',6),('A',7),('G',2)]+[('C',b) for b in range(7,-1,-1)]+[('G',1),('G',0)]
        outputs['top']=[(ports[p]>>b)&1 for p,b in top_pins]
        outputs['bottom']=[(ports['D']>>b)&1 for b in (0,1,2,3,4,7)]
        # Channel ordering from portextender.h; emitter positions remain schematic.
        for side in ('left','right'):
            mask=outputs[side]
            outputs[side+'_rgb']=[[(mask>>b)&1 for b in channels] for channels in ((3,2,4),(0,1,5))]
        return dict(ok=True,source=label,branch=branch,commit=commit,local=local,revision=digest[:12],pages=pages,page=selected,compiled_at=CACHE.get('compiled_at'),
                    rows=[list(raw[i:i+20]) for i in range(0,80,20)],glyphs=[list(glyphs[i:i+8]) for i in range(0,64,8)],outputs=outputs,fields=FIELDS,
                    notes='Jede Änderung startet einen neuen simulierten Durchlauf. Fehler bleiben nur innerhalb dieses Durchlaufs gespeichert. ¹ Skaliert passend zur aktuellen Anzeige; die CAN-Einheit ist damit nicht bestätigt. ² Rohwerte können vom aktuellen Firmwarestand ungenutzt bleiben. Diagnosekürzel im Test-Code: 0 OK, 1 OV, 2 UV, 3 OT, 4 UT, 5 NTC, 6 PEC, 7 IVT, 8 ALV, 9 IMD; weitere Codes entsprechend Firmware.')


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
        elif url.path == '/api/config':
            self.respond(200, configuration())
        elif url.path == '/api/frame':
            try:
                self.respond(200, frame(parse_qs(url.query)))
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
            if not 0 <= length <= 65536:
                raise ValueError('Anfrage zu groß.')
            data = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(data, dict):
                raise ValueError('JSON-Objekt erwartet.')
            if self.path == '/api/config':
                self.respond(200, dict(ok=True, **configure(data.get('path'))))
            elif self.path == '/api/choose-folder':
                self.respond(200, dict(ok=True, **choose_folder()))
            else:
                self.respond(404, {'ok': False, 'error': 'Nicht gefunden.'})
        except (ValueError, OSError) as exc:
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
        with http:
            print(f'DIC_Visualisierung: {http.origin}/', flush=True)
            print('Nur lokal. Dieses Fenster geöffnet lassen; Strg+C beendet die Vorschau.', flush=True)
            if open_browser and not args.no_browser:
                webbrowser.open(http.origin + '/')
            try:
                http.serve_forever()
            except KeyboardInterrupt:
                pass
        BUILD_ROOT = None


if __name__ == '__main__':
    main()
