"""Reproducible synthetic DIC input scenarios, not vehicle physics or race timing."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dic_visualisierung import scenarios

START = 16000
RULES = 'https://www.formulastudent.de/fileadmin/user_upload/all/2026/rules/FS-Rules_2026_v1.1.pdf'
AUTOCROSS = [(0,0),(4,35),(10,85),(12,85),(15,30),(18,30),
             (25,65),(27,65),(30,25),(34,25),(42,80),(45,80),
             (48,35),(52,35),(60,90),(64,90),(66,40),(70,0)]
LAP = [(0,40),(4,65),(7,65),(10,30),(14,30),(20,75),(23,75),
       (26,35),(30,35),(36,70),(39,70),(42,30),(46,30),(50,40)]
SPECS = {
    'acceleration': dict(name='FS · Acceleration · 75 m (synthetisch)', mode=0, duration=28000),
    'skidpad': dict(name='FS · Skidpad · Rechts / links (synthetisch)', mode=1, duration=48000),
    'autocross': dict(name='FS · Autocross · Handlingrunde (synthetisch)', mode=2, duration=89000),
    'endurance': dict(name='FS · Endurance · Ausschnitt mit Halt (synthetisch)', mode=3, duration=307000),
    'efficiency': dict(name='FS · Efficiency · Sanfter Fahrstil (synthetisch)', mode=3, duration=357000),
}


def curve(knots, seconds):
    if seconds < 0:
        return 0.0, 0.0
    for (ta,va),(tb,vb) in zip(knots,knots[1:]):
        if seconds <= tb:
            return va+(vb-va)*(seconds-ta)/(tb-ta), (vb-va)/(tb-ta)/3.6
    return float(knots[-1][1]), 0.0


def turn(t, start, end, peak):
    if start <= t <= end:
        return peak*(1-abs(2*(t-start)/(end-start)-1))
    return 0.0


def endurance_phases(kind):
    lap = 60 if kind == 'efficiency' else 50
    # Standing launch, three laps, pit entry, stationary change, relaunch, two laps.
    pit_entry = 5 + 3*lap
    pit_start = pit_entry + 3
    pit_end = pit_start + 20
    second = pit_end + 5
    finish = second + 2*lap
    return lap, pit_entry, pit_start, pit_end, second, finish


def motion(kind, t):
    if t < 0:
        return 0.0, 0.0, 0.0
    if kind == 'acceleration':
        speed,accel = curve([(0,0),(5,108),(9,0),(12,0)],t)
        return speed,accel,0.0
    if kind == 'skidpad':
        speed,accel = curve([(0,0),(3,40),(24.6,40),(28,0),(32,0)],t)
        steering = 0.0
        if 2.6 <= t < 3:steering=32*(t-2.6)/0.4
        elif 3 <= t < 13.4:steering=32
        elif 13.4 <= t < 14.2:steering=32-64*(t-13.4)/0.8
        elif 14.2 <= t < 24.6:steering=-32
        elif 24.6 <= t < 25:steering=-32*(25-t)/0.4
        return speed,accel,steering
    if kind == 'autocross':
        speed,accel=curve(AUTOCROSS,t)
        steering=sum(turn(t,a,b,peak) for a,b,peak in
                     [(12,18,35),(27,34,-36),(45,52,30),(64,68,-28)])
        # A short slalom is an input pattern, not a measured steering-angle map.
        if 18<t<25:steering=turn(t,18,20,18)+turn(t,20,22,-18)+turn(t,22,24,18)
        return speed,accel,steering
    lap,pit_entry,pit_start,pit_end,second,finish=endurance_phases(kind)
    scale=5/6 if kind=='efficiency' else 1
    if t <= 5:
        speed,accel=curve([(0,0),(5,40*scale)],t)
        return speed,accel,0.0
    if pit_entry <= t < second:
        speed,accel=curve([(pit_entry,40*scale),(pit_start,0),(pit_end,0),(second,40*scale)],t)
        return speed,accel,0.0
    if t >= finish:
        speed,accel=curve([(finish,40*scale),(finish+5,0)],t)
        return speed,accel,0.0
    phase=(t-(5 if t < pit_entry else second)) % lap
    u=phase*50/lap
    speed,accel=curve(LAP,u)
    steering=sum(turn(u,a,b,peak) for a,b,peak in [(7,14,28),(23,30,-30),(39,46,26)])
    return speed*scale,accel*scale*50/lap,steering


def signals(kind, stamp):
    spec=SPECS[kind]
    t=(stamp-START)/1000
    speed,accel,steering=motion(kind,t)
    front=round(min(85,max(0,-accel)*8))
    throttle=0 if front or speed==0 else (650 if kind=='efficiency' else 980) if accel>0.05 else 300 if steering else 650
    heat=max(0,min(1,t/((spec['duration']-START)/1000)))
    temperature_rise=6500 if kind=='endurance' else 4000 if kind=='efficiency' else 1200
    return dict(speed=round(speed*10),apps1=throttle,apps2=throttle,
                front=front,rear=round(front*0.72),steering=round(steering),
                accu=round(32400+temperature_rise*heat),
                motor0=round(550+(100 if kind=='endurance' else 60)*heat),
                motor1=round(550+(95 if kind=='endurance' else 55)*heat),
                inv0=round(450+50*heat),inv1=round(450+45*heat),
                ts=54000-round((1200 if kind=='endurance' else 800)*heat)-round(throttle*0.6),
                lv=1260,ams_error=0,imd_error=0,diag=0)


def build(kind):
    spec=SPECS[kind];end=spec['duration'];mode=spec['mode']
    values=signals(kind,0);values['mode']=mode
    events=[dict(at_ms=t,kind='inputs',values=signals(kind,t))
            for t in range(START,end+1,100)]
    events += [dict(at_ms=t,kind='gpio',pin=pin,pressed=pressed) for t,pin,pressed in
               [(15001,'TS_ON',True),(15101,'TS_ON',False),(15201,'R2D',True),(15301,'R2D',False)]]
    checks=[dict(at_ms=0,path='state.active_mode',expected=mode),
            dict(at_ms=15020,path='state.TS_ON',expected=1),
            dict(at_ms=15220,path='state.Ready_2_Drive',expected=1),
            dict(at_ms=end,path='state.speed_kmh',expected=0),
            dict(at_ms=end,path='state.active_mode',expected=mode),
            dict(at_ms=end,path='outputs.tx.7',expected=mode),
            dict(at_ms=end,path='outputs.ams_led',expected=0),
            dict(at_ms=end,path='outputs.imd_led',expected=0)]
    # Explicit reviewed constants, not captured from a simulator result.
    samples={'acceleration':(21020,108),'skidpad':(25020,40),
             'autocross':(26020,85),'endurance':(26020,65),'efficiency':(26020,54)}
    at,speed=samples[kind]
    checks += [dict(at_ms=at,path='state.speed_kmh',expected=speed),
               dict(at_ms=at,path='state.speed_valid',expected=1)]
    origin=dict(format='synthetic-demo',discipline=kind,source=RULES,
                note='Synthetische DIC-Eingaben; keine gemessenen Fahrzeugdaten, keine Punktwertung und kein vollständiges Fahrzeugmodell.')
    if kind=='acceleration':origin.update(timed_start_ms=16000,timed_finish_ms=21000,assumed_distance_m=75)
    if kind in ('endurance','efficiency'):
        _,_,pit_start,pit_end,_,_=endurance_phases(kind)
        origin.update(excerpt=True,pit_start_ms=START+round(pit_start*1000),pit_end_ms=START+round(pit_end*1000),
                      note='Mehrminütiger Ausschnitt mit fünf synthetischen Runden und Halt, kein vollständiger 22-km-Lauf. Halt ersetzt keinen realen HV-/Fahrerwechselablauf. Keine Energie- oder Effizienzbewertung.')
        checks.append(dict(at_ms=origin['pit_start_ms']+1000,path='state.speed_kmh',expected=0))
    return dict(format='dic-scenario',version=1,name=spec['name'],duration_ms=end,
                initial=dict(values=values,page='dsp_debug'),generators=scenarios.defaults(end),
                events=events,assertions=checks,origin=origin)


if __name__=='__main__':
    for kind in SPECS:
        path=Path(__file__).resolve().parents[1]/('scenarios/fs-'+kind+'.scenario.json')
        path.write_text(json.dumps(build(kind),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(path.name)
