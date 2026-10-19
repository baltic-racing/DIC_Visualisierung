"""Rebuild the synthetic, roughly 1 km demonstration using scenario format v1.

This is a signal fixture, not a vehicle/track dynamics model or measured lap.
No firmware or user configuration is read or written.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dic_visualisierung import scenarios

START_MS = 16000
LAP_MS = 80800
END_MS = 104000
# Generic straights and five alternating slow turns; not surveyed track geometry.
KNOTS = [(0, 0), (4, 30), (10, 65), (14, 65), (17, 28), (21, 28),
         (27, 60), (29, 60), (32, 24), (36, 24), (42, 60), (45, 60),
         (48, 32), (52, 32), (59, 70), (62, 70), (66, 27), (70, 27),
         (76, 60), (80, 60), (83, 30), (86, 30), (91, 65), (94, 65)]
TURNS = [(14, 21, 30), (29, 36, -34), (45, 52, 25),
         (62, 70, -32), (80, 86, 30)]


def signals(stamp):
    elapsed = max(0, stamp - START_MS)
    t = min(elapsed, LAP_MS) * 94 / LAP_MS
    speed = 0.0
    accel = 0.0
    for (ta, va), (tb, vb) in zip(KNOTS, KNOTS[1:]):
        if t <= tb:
            speed = va + (vb - va) * (t - ta) / (tb - ta)
            accel = (vb - va) / ((tb - ta) * LAP_MS / 94000) / 3.6
            break
    if elapsed > LAP_MS:
        speed = max(0, 65 * (1 - (elapsed - LAP_MS) / 5200))
        accel = -65 / 5.2 / 3.6 if speed else 0
    steering = 0.0
    for ta, tb, peak in TURNS:
        if ta <= t <= tb and elapsed <= LAP_MS:
            u = (t - ta) / (tb - ta)
            steering = peak * (1 - abs(2 * u - 1))
    if stamp < START_MS:
        speed = accel = 0
    # Existing display-scaled brake values; no calibrated bar/pedal-force claim.
    front = round(min(75, max(0, -accel) * 16))
    rear = round(front * 0.72)
    throttle = 0 if front or speed == 0 else round(950 if accel > 0.05 else 300 if steering else 650)
    heat = min(elapsed / LAP_MS, 1)
    return dict(speed=round(speed * 10), apps1=throttle, apps2=throttle,
                front=front, rear=rear, steering=round(steering),
                accu=round(32400 + 1200 * heat), motor0=round(550 + 60 * heat),
                motor1=round(550 + 55 * heat), inv0=round(450 + 40 * heat),
                inv1=round(450 + 35 * heat), ts=54000 - round(throttle * 0.6),
                lv=1260, diag=0, ams_error=0, imd_error=0)


def build():
    initial = signals(0)
    events = [dict(at_ms=t, kind='inputs', values=signals(t))
              for t in range(START_MS, END_MS + 1, 100)]
    events += [dict(at_ms=15001, kind='gpio', pin='TS_ON', pressed=True),
               dict(at_ms=15101, kind='gpio', pin='TS_ON', pressed=False),
               dict(at_ms=15201, kind='gpio', pin='R2D', pressed=True),
               dict(at_ms=15301, kind='gpio', pin='R2D', pressed=False)]
    return dict(format='dic-scenario', version=1,
                name='Bispingen · Außenrunde (synthetisch)', duration_ms=END_MS,
                initial=dict(values=initial, page='dsp_debug'),
                generators=scenarios.defaults(END_MS), events=events,
                origin=dict(format='synthetic-demo', track='Ralf Schumacher Kartcenter · Bispingen',
                            source='https://rs-kartcenter.de/infos/ueber-uns/',
                            assumed_distance_m=1000, lap_start_ms=START_MS,
                            lap_duration_ms=LAP_MS,
                            note='Generische Fahrkurve für ungefähr 1 km; keine echten Messdaten oder exakte Streckengeometrie. CAN-Sendeperioden und Bremswerte sind Testannahmen.'),
                assertions=[dict(at_ms=15020, path='state.TS_ON', expected=1),
                            dict(at_ms=15220, path='state.Ready_2_Drive', expected=1),
                            dict(at_ms=20020, path='state.speed_valid', expected=1),
                            dict(at_ms=20020, path='state.speed_kmh', expected=34),
                            dict(at_ms=25020, path='state.speed_kmh', expected=65),
                            dict(at_ms=END_MS, path='state.speed_kmh', expected=0),
                            dict(at_ms=END_MS, path='outputs.ams_led', expected=0),
                            dict(at_ms=END_MS, path='outputs.imd_led', expected=0)])


if __name__ == '__main__':
    path = Path(__file__).resolve().parents[1]/'scenarios/bispingen.scenario.json'
    path.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(path.name)
