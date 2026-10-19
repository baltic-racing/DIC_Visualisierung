"""Independent sender contracts from the inspected AMS source; no C oracle learning."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dic_visualisierung import ams, fields, generators, profiles, scenarios


def packet(**changes):
    values={f['id']:f['default'] for f in fields.FIELDS};values.update(changes)
    return dict(values=values,page='dsp_main',overrides=[])


class AMSContracts(unittest.TestCase):
    def test_strict_temperature_threshold_delay_and_persistent_latch(self):
        model=ams.Sender();v=packet(ams_thermal=1)['values']
        v['accu']=58611;model.update(0,v);model.update(5000,v)
        self.assertFalse(model.latched);self.assertIsNone(model.deadline())
        v['accu']=58612;model.update(5001,v)
        self.assertEqual(model.deadline(),6201)
        model.update(6200,v);self.assertFalse(model.latched)
        model.update(6201,v);self.assertTrue(model.latched)
        v['accu']=32000;model.update(7000,v);self.assertTrue(model.latched)
        self.assertFalse(ams.Sender().latched)

    def test_cooling_before_delay_restarts_timer_and_disabled_model_does_not_trip(self):
        model=ams.Sender();v=packet(ams_thermal=1,accu=60000)['values']
        model.update(100,v);v['accu']=58000;model.update(1299,v)
        v['accu']=60000;model.update(1300,v);model.update(2499,v)
        self.assertFalse(model.latched)
        v['ams_thermal']=0;model.update(2500,v);self.assertFalse(model.latched)
        v['ams_thermal']=1;v['ams_sender']=0;model.update(10000,v)
        self.assertFalse(model.latched)

    def test_payload_order_isolation_status_and_complete_ams1(self):
        p=packet(ams_error=0,can_ok=1,soc=1000,cell_min=37000,cell_max=40000,accu_min=25000,accu=59000)
        config=dict(can_id=0x200,period_ms=20,start_ms=11,end_ms=10000)
        out=generators.Generator(config).emit(11,p,['dsp_main'],True)
        self.assertEqual(out['data'],[240,210,0,0,232,3,128,0])
        self.assertEqual(generators.encode(p,0x201,['dsp_main']),[136,144,64,156,168,97,120,230])
        p['values']['ams_error']=1
        self.assertEqual(generators.Generator(config).emit(11,p,['dsp_main'])['data'][6],128)

    def test_ams_counter_skips_255_but_explicit_custom_counter_does_not(self):
        config=dict(can_id=0x200,period_ms=20,start_ms=11,end_ms=10000)
        p=packet();g=generators.Generator(config)
        actual=[g.emit(i,p,['dsp_main'])['data'][7] for i in range(257)]
        self.assertEqual(actual,list(range(255))+[0,1])
        g=generators.Generator(dict(config,counter=dict(byte=7,start=254,step=1)))
        self.assertEqual([g.emit(i,p,['dsp_main'])['data'][7] for i in range(3)],[254,255,0])
        p['values']['ams_sender']=0;g=generators.Generator(config)
        self.assertEqual([g.emit(i,p,['dsp_main'])['data'][7] for i in range(256)],list(range(1,256))+[0])

    def test_diagnosis_requires_legacy_sender_or_explicit_bytes_and_override_wins(self):
        p=packet(diag=3);config=dict(can_id=0x204,period_ms=10,start_ms=11,end_ms=1000)
        self.assertIsNone(generators.Generator(config).emit(11,p,['dsp_main']))
        p['values']['ams_sender']=0
        self.assertEqual(generators.Generator(config).emit(11,p,['dsp_main'])['data'][0],3)
        p['values']['ams_sender']=1;p['overrides']=[(0x204,bytes([6]+[0]*7))]
        self.assertEqual(generators.Generator(config).emit(11,p,['dsp_main'])['data'][0],6)
        p['overrides']=[(0x200,bytes(8))]
        out=generators.Generator(dict(config,can_id=0x200)).emit(11,p,['dsp_main'],True)
        self.assertEqual(out['data'],[0]*8)

    def test_interactive_intervals_and_explicit_scenario_intervals(self):
        configs={c['can_id']:c for c in scenarios.defaults(1000,ams_sender=True)}
        self.assertEqual((configs[0x200]['period_ms'],configs[0x201]['period_ms']),(20,100))
        g=generators.Generator(dict(configs[0x201],_adaptive_ams_period=True))
        g.emit(11,packet(),['dsp_main']);self.assertEqual(g.next,111)
        g.emit(111,packet(ams_sender=0),['dsp_main']);self.assertEqual(g.next,121)
        g=generators.Generator(dict(configs[0x201],period_ms=37))
        g.emit(11,packet(),['dsp_main']);self.assertEqual(g.next,48)

    def test_old_profiles_and_scenarios_keep_legacy_without_modifying_input(self):
        old=dict(values=dict(soc=1234,diag=6),raw='',page='dsp_main');before=copy.deepcopy(old)
        state=profiles.validate_state(old,fields.FIELDS)
        self.assertEqual(old,before)
        self.assertEqual((state['values']['ams_sender'],state['values']['soc'],state['values']['diag']),(0,1234,6))

    def test_example_reproducible_and_valid(self):
        from examples.generators.create_ams_temperature import build
        path=Path(__file__).resolve().parents[2]/'examples/scenarios/ams-temperature.scenario.json'
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')),build())
        definition=scenarios.validate(build(),fields.FIELDS)
        self.assertEqual(definition['initial']['values']['ams_sender'],1)
        self.assertTrue(all('ams_error' not in e['values'] for e in definition['events']))


if __name__=='__main__':unittest.main()
