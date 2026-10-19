"""Synthetic heating trace for the explicitly limited AMS TY26 sender model."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dic_visualisierung import scenarios


def build():
    duration=45000
    values=dict(ams_sender=1,ams_thermal=1,accu=32400,accu_min=25000,
                cell_min=37000,cell_max=40000,soc=1000,ams_error=0,imd_error=0,
                ams_mode=0,can_ok=0,diag=0,speed=0,apps1=0,apps2=0,front=0,rear=0,steering=0)
    points=[(16001,40000,400,300),(20001,48000,500,400),(24001,55000,600,500),
            (26001,58000,500,300),(28001,59000,400,200),(30001,61000,0,0),
            (35001,45000,0,0),(40001,32000,0,0)]
    events=[dict(at_ms=at,kind='inputs',values=dict(accu=temp,speed=speed,apps1=pedal,apps2=pedal))
            for at,temp,speed,pedal in points]
    checks=[]
    def expect(at,path,value):checks.append(dict(at_ms=at,path=path,expected=value))
    expect(0,'outputs.ams_led',1)
    expect(2000,'outputs.ams_led',0)
    expect(28000,'outputs.ams_led',0)
    expect(29000,'state.bms_max_temp',590)
    expect(29200,'state.ams_error_counter1',0)
    expect(29220,'state.ams_error_counter1',1)
    expect(29700,'state.ams_error_counter1',49)
    expect(29700,'outputs.ams_led',0)
    expect(29710,'outputs.ams_led',1)
    expect(29710,'outputs.bottom',[1]*6)
    expect(35010,'outputs.ams_diagnostic_valid',0)
    expect(45000,'state.bms_max_temp',320)
    expect(45000,'outputs.ams_led',1)
    expect(45000,'outputs.bottom',[1]*6)
    expect(45000,'outputs.imd_led',0)
    return dict(format='dic-scenario',version=1,name='Akku wird heiß · AMS-Übertemperatur',
                duration_ms=duration,initial=dict(values=values,page='dsp_main'),
                generators=scenarios.defaults(duration,ams_sender=True),events=events,assertions=checks,
                origin=dict(format='synthetic-ams-ty26-subset-v1',
                    note='Beschleunigte Beispielerwärmung, kein thermisches Akkumodell. Feste heißeste Zelle: über 58,611 °C ab 28,001 s, AMS-Verriegelung nach 1,2 s. CAN 0x200 überträgt das Bit; DIC schaltet seine LEDs nach 50 Prüfungen. Abkühlung löscht keine Verriegelung. Keine Diagnose 0x204; kein Modell für IVT, PEC, IMD, ADC oder den Abschaltkreis.'))


if __name__=='__main__':
    target=Path(__file__).resolve().parents[1]/'scenarios/ams-temperature.scenario.json'
    target.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
