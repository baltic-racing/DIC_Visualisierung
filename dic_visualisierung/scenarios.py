"""Version-1 input timelines and classical timestamped candump import. No DBC."""
import copy
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import json
from pathlib import Path
import re
from . import profiles
MAX_BYTES=5*1024*1024
MAX_EVENTS=100000
MAX_DURATION=600000
MAX_PER_TICK=96
KINDS={'can','gpio','inputs','generator'}


def integer(value,low,high,label):
    if type(value) is not int or not low<=value<=high:
        raise ValueError(label+f': ganze Zahl zwischen {low} und {high} erwartet.')
    return value


def shape(value,allowed,required=()):
    if not isinstance(value,dict) or set(value)-set(allowed) or not set(required)<=value.keys():
        raise ValueError('Ungültige Felder im Szenario; erwartet: '+', '.join(allowed))


def values(value,fields):
    known={f['id']:f for f in fields}
    if not isinstance(value,dict) or value.keys()-known.keys():
        raise ValueError('Unbekannte Fahrzeugwerte im Szenario.')
    return {key:integer(v,known[key]['min'],known[key]['max'],key) for key,v in value.items()}


def can_frame(value,allow_tx=False):
    ident=integer(value.get('can_id'),0,0x7ff,'CAN-ID')
    if ident==0x500 and not allow_tx:
        raise ValueError('0x500 ist DIC-Ausgang; unter expected_tx statt als Empfang angeben.')
    dlc=integer(value.get('dlc'),0,8,'DLC')
    data=value.get('data')
    if not isinstance(data,list) or len(data)!=dlc:
        raise ValueError('DLC muss der Anzahl der Nutzdatenbytes entsprechen.')
    return dict(can_id=ident,dlc=dlc,data=[integer(b,0,255,'CAN-Byte') for b in data])


def validate(value,fields):
    shape(value,('format','version','name','duration_ms','initial','generators','events','expected_tx','assertions','origin'),('format','version','name','duration_ms'))
    if value['format']!='dic-scenario' or type(value['version']) is not int or value['version']!=1:
        raise ValueError('Szenarioformat dic-scenario Version 1 erwartet; keine automatische Migration.')
    name=profiles.valid_name(value['name'])
    duration=integer(value['duration_ms'],1,MAX_DURATION,'Gesamtlaufzeit ms')
    initial=profiles.validate_state(value.get('initial',{'values':{}}),fields)
    generators=value.get('generators',[])
    if not isinstance(generators,list) or len(generators)>32:
        raise ValueError('Maximal 32 periodische Generatoren.')
    checked=[]
    for gen in generators:
        shape(gen,('can_id','period_ms','start_ms','end_ms','enabled','data','dlc','counter'),('can_id','period_ms'))
        ident=integer(gen['can_id'],0,0x7ff,'Generator-ID')
        if ident==0x500 or any(g['can_id']==ident for g in checked):
            raise ValueError('Doppelte Generator-ID oder DIC-Ausgang 0x500.')
        item=dict(can_id=ident,period_ms=integer(gen['period_ms'],1,MAX_DURATION,'Periode'),
                  start_ms=integer(gen.get('start_ms',11),0,duration,'Generatorstart'),
                  end_ms=integer(gen.get('end_ms',duration),0,duration,'Generatorende'),enabled=gen.get('enabled',True))
        if type(item['enabled']) is not bool or item['end_ms']<item['start_ms']:
            raise ValueError('Ungültiger Generatorbereich oder enabled-Wert.')
        if 'data' in gen:
            item.update(can_frame(dict(can_id=ident,dlc=gen.get('dlc',len(gen['data']) if isinstance(gen['data'],list) else -1),data=gen['data'])))
        elif ident not in profiles.CAN_IDS:
            raise ValueError('Generator für unbekannte ID benötigt explizite Nutzdaten.')
        elif 'dlc' in gen:
            raise ValueError('DLC ohne explizite Generator-Nutzdaten ist nicht zulässig.')
        if 'counter' in gen:
            counter=gen['counter'];shape(counter,('byte','start','step'),('byte',))
            byte=integer(counter['byte'],0,item.get('dlc',8)-1,'Zählerbyte')
            item['counter']=dict(byte=byte,start=integer(counter.get('start',0),0,255,'Zählerstart'),step=integer(counter.get('step',1),0,255,'Zählerschritt'))
        checked.append(item)
    events=value.get('events',[])
    if not isinstance(events,list) or len(events)>MAX_EVENTS:
        raise ValueError(f'Maximal {MAX_EVENTS} Eingabeereignisse.')
    result=[];density={}
    for event in events:
        if not isinstance(event,dict) or event.get('kind') not in KINDS:
            raise ValueError('Unbekannte Ereignisart.')
        at=integer(event.get('at_ms'),0,duration,'Ereigniszeit ms');kind=event['kind']
        item=dict(at_ms=at,kind=kind)
        if kind=='can':
            shape(event,('at_ms','kind','can_id','dlc','data'),('at_ms','kind','can_id','dlc','data'))
            item.update(can_frame(event));density[at]=density.get(at,0)+1
            if density[at]>MAX_PER_TICK:raise ValueError('Zu viele CAN-Frames im selben 1-ms-Zeitfenster (maximal 96).')
        elif kind=='gpio':
            shape(event,('at_ms','kind','pin','pressed'),('pin','pressed'))
            if event['pin'] not in ('TS_ON','R2D') or type(event['pressed']) is not bool:
                raise ValueError('GPIO erwartet TS_ON oder R2D und pressed als booleschen Wert.')
            item.update(pin=event['pin'],pressed=event['pressed'])
        elif kind=='inputs':
            shape(event,('at_ms','kind','values','raw','page'),('values',))
            item['values']=values(event['values'],fields)
            if 'raw' in event:
                profiles.raw_bytes(event['raw']);item['raw']=event['raw']
            if 'page' in event:
                if not isinstance(event['page'],str) or len(event['page'])>160:raise ValueError('Ungültige SWC-Seite.')
                item['page']=event['page']
        else:
            shape(event,('at_ms','kind','can_id','enabled','freeze_counter'),('can_id',))
            ident=integer(event['can_id'],0,0x7ff,'Generator-ID')
            if not any(g['can_id']==ident for g in checked):raise ValueError('Ereignis verweist auf nicht vorhandenen Generator.')
            item['can_id']=ident
            if not {'enabled','freeze_counter'}&event.keys():raise ValueError('Generatorereignis benötigt enabled oder freeze_counter.')
            for key in ('enabled','freeze_counter'):
                if key in event:
                    if type(event[key]) is not bool:raise ValueError('Generatorzustand muss boolesch sein.')
                    item[key]=event[key]
        result.append(item)
    expected=[]
    if not isinstance(value.get('expected_tx',[]),list) or not isinstance(value.get('assertions',[]),list):raise ValueError('expected_tx und assertions müssen Listen sein.')
    if len(value.get('expected_tx',[]))+len(value.get('assertions',[]))+len(result)>MAX_EVENTS:raise ValueError('Zu viele Ereignisse und Erwartungen.')
    for tx in value.get('expected_tx',[]):
        shape(tx,('at_ms','can_id','dlc','data','tolerance_ms'),('at_ms','can_id','dlc','data'))
        frame=can_frame(tx,True)
        if frame['can_id']!=0x500:raise ValueError('expected_tx unterstützt DIC-ID 0x500.')
        expected.append(dict(frame,at_ms=integer(tx['at_ms'],0,duration,'TX-Zeit'),tolerance_ms=integer(tx.get('tolerance_ms',0),0,10000,'TX-Toleranz')))
    assertions=[]
    for check in value.get('assertions',[]):
        shape(check,('at_ms','path','op','expected'),('at_ms','path','expected'))
        path=check['path'];op=check.get('op','eq')
        if not isinstance(path,str) or len(path)>100 or not re.fullmatch(r'(?:outputs|state|rows|logical_rows)(?:\.[A-Za-z0-9_]+)+|active_page|time_ms|sys_time',path) or op not in ('eq','contains'):
            raise ValueError('Ungültiger Prüfpfad oder Vergleich.')
        expected_value=check['expected']
        if len(json.dumps(expected_value,allow_nan=False))>4096:raise ValueError('Erwarteter Prüfwert ist zu groß.')
        assertions.append(dict(at_ms=integer(check['at_ms'],0,duration,'Prüfzeit'),path=path,op=op,expected=copy.deepcopy(expected_value)))
    if len(expected)+len(assertions)+len(result)>MAX_EVENTS:raise ValueError('Zu viele Ereignisse und Erwartungen.')
    emissions=sum(max(0,(g['end_ms']-g['start_ms'])//g['period_ms']+1) for g in checked)
    if emissions+len(result)>1000000:raise ValueError('Szenario würde mehr als eine Million Ereignisse erzeugen.')
    origin=value.get('origin')
    if origin is not None and (not isinstance(origin,dict) or len(json.dumps(origin,allow_nan=False))>4096):raise ValueError('Ungültige Importherkunft.')
    return dict(format='dic-scenario',version=1,name=name,duration_ms=duration,initial=initial,generators=checked,
                events=sorted(result,key=lambda e:e['at_ms']),expected_tx=sorted(expected,key=lambda e:e['at_ms']),
                assertions=sorted(assertions,key=lambda e:e['at_ms']),**({'origin':copy.deepcopy(origin)} if origin else {}))


def import_text(text,kind,fields,name='Import',offset_ms=0):
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_BYTES:
        raise ValueError('Importdatei zu groß: maximal 5 MiB.')
    if kind=='scenario':
        try:return validate(json.loads(text),fields)
        except (json.JSONDecodeError,RecursionError):raise ValueError('Ungültige Szenario-JSON-Datei.') from None
    if kind!='candump':raise ValueError('Importart scenario oder candump erwartet.')
    integer(offset_ms,0,MAX_DURATION-1,'Startversatz ms')
    parsed=[];interfaces=set()
    for number,line in enumerate(text.splitlines(),1):
        if not line.strip():continue
        if '##' in line:raise ValueError(f'Zeile {number}: CAN FD wird nicht unterstützt.')
        match=re.fullmatch(r'\((\d+\.\d{1,9})\)\s+([\w.-]{1,32})\s+([0-9a-fA-F]{1,8})#(\S*)\s*',line)
        if not match:raise ValueError(f'Zeile {number}: klassisches candump-Format (Zeit) can0 200#… erwartet.')
        ident_text=match[3];payload=match[4]
        if len(ident_text)>3:
            raise ValueError(f'Zeile {number}: Extended-/Error-Frames werden nicht unterstützt.')
        if payload.upper().startswith('R'):raise ValueError(f'Zeile {number}: RTR-Frames werden nicht unterstützt.')
        if not re.fullmatch(r'(?:[0-9a-fA-F]{2}){0,8}',payload):raise ValueError(f'Zeile {number}: 0 bis 8 vollständige Datenbytes erwartet.')
        try:stamp=Decimal(match[1])
        except InvalidOperation:raise ValueError(f'Zeile {number}: ungültiger Zeitstempel.') from None
        if len(match[1])>30:raise ValueError('Zeitstempel zu groß.')
        frame=can_frame(dict(can_id=int(ident_text,16),dlc=len(payload)//2,data=list(bytes.fromhex(payload))),True)
        parsed.append((stamp,number,frame));interfaces.add(match[2])
        if len(parsed)>MAX_EVENTS:raise ValueError('Zu viele Log-Frames (maximal 100000).')
    if not parsed:raise ValueError('Die Logdatei enthält keine CAN-Datenframes.')
    if len(interfaces)>1:raise ValueError('Mehrere CAN-Interfaces im Log: bitte einen Bus getrennt exportieren.')
    parsed.sort(key=lambda row:(row[0],row[1]));epoch=parsed[0][0]
    events=[];expected=[];last=0
    for stamp,_,frame in parsed:
        at=int(((stamp-epoch)*1000).to_integral_value(rounding=ROUND_CEILING))+offset_ms
        if at>MAX_DURATION:raise ValueError('Logdauer mit Versatz überschreitet 10 Minuten.')
        last=max(last,at)
        if frame['can_id']==0x500:expected.append(dict(frame,at_ms=at,tolerance_ms=0))
        else:events.append(dict(frame,kind='can',at_ms=at))
    scenario=dict(format='dic-scenario',version=1,name=profiles.valid_name(name),duration_ms=max(1,last),
                  generators=[],events=events,expected_tx=expected,
                  origin=dict(format='candump',epoch_seconds=str(epoch),offset_ms=offset_ms,quantization='ceil-1ms',interface=next(iter(interfaces))))
    return validate(scenario,fields)


def defaults(duration=5000,ams_sender=False):
    return [dict(can_id=ident,period_ms=({0x200:20,0x201:100}.get(ident,10) if ams_sender else 10),
                 start_ms=11,end_ms=duration,enabled=True) for ident in sorted(profiles.CAN_IDS)]


class Library:
    """Bundled examples plus in-memory imports; no automatic user-file writes."""
    def __init__(self,root,fields):
        self.fields=fields;self.items={}
        for path in sorted((Path(root)/'examples/scenarios').glob('*.scenario.json')):
            self.items[path.stem]=validate(json.loads(path.read_text(encoding='utf-8')),fields)

    def add(self,scenario):
        if len(self.items)>=30:raise ValueError('Maximal 30 Szenarien je Serverlauf.')
        key='import-'+str(len(self.items)+1);self.items[key]=copy.deepcopy(scenario);return key

    def listing(self):
        return [dict(id=key,name=value['name'],duration_ms=value['duration_ms']) for key,value in self.items.items()]
