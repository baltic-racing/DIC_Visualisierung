"""Simulator format contracts; no firmware behavior oracle is learned here."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dic_visualisierung import profiles
from dic_visualisierung import scenarios
from dic_visualisierung import server
def sample():
    return dict(format='dic-scenario',version=1,name='Fixture',duration_ms=3000,
                initial=dict(values={},page='dsp_main'),generators=scenarios.defaults(3000),events=[])


class ScenarioFormatTests(unittest.TestCase):
    def test_library_uses_utf8_under_windows_legacy_codepage(self):
        expected='Prüfung · Kühlung außen'
        definition=sample();definition['name']=expected
        original=Path.read_text
        def windows_read(path,encoding=None,errors=None):
            return original(path,encoding=encoding or 'cp1252',errors=errors)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'examples/scenarios';folder.mkdir(parents=True)
            (folder/'unicode.scenario.json').write_text(json.dumps(definition,ensure_ascii=False),encoding='utf-8')
            with patch.object(Path,'read_text',windows_read):
                library=scenarios.Library(root,server.FIELDS)
        self.assertEqual(library.listing()[0]['name'],expected)

    def test_discipline_examples_are_reproducible_valid_and_use_existing_modes(self):
        from examples.generators import create_disciplines as demo
        for kind,mode in [('acceleration',0),('skidpad',1),('autocross',2),('endurance',3),('efficiency',3)]:
            with self.subTest(kind=kind):
                saved=json.loads((server.ROOT/f'examples/scenarios/fs-{kind}.scenario.json').read_text(encoding='utf-8'))
                self.assertEqual(saved,demo.build(kind))
                definition=scenarios.validate(saved,server.FIELDS)
                self.assertEqual(definition['initial']['values']['mode'],mode)
                self.assertEqual(definition['initial']['page'],'dsp_debug')
                frames=[e for e in definition['events'] if e['kind']=='inputs']
                self.assertGreater(max(e['values']['speed'] for e in frames),0)
                self.assertEqual(frames[-1]['values']['speed'],0)
                self.assertTrue(all(not(e['values']['front'] and e['values']['apps1']) for e in frames))
                self.assertTrue(all(abs(b['values']['speed']-a['values']['speed'])/3.6<=10
                                    for a,b in zip(frames,frames[1:])))
                self.assertLess((server.ROOT/f'examples/scenarios/fs-{kind}.scenario.json').stat().st_size,scenarios.MAX_BYTES)
                if kind in ('endurance','efficiency'):
                    origin=definition['origin']
                    pit=[e for e in frames if origin['pit_start_ms']<=e['at_ms']<=origin['pit_end_ms']]
                    self.assertTrue(pit)
                    self.assertTrue(all(e['values']['speed']==0 for e in pit))
                    self.assertTrue(any(e['values']['speed']>0 and e['at_ms']>origin['pit_end_ms'] for e in frames))

    def test_acceleration_input_integrates_to_75_m_and_skidpad_changes_direction(self):
        from examples.generators import create_disciplines as demo
        accel=demo.build('acceleration')
        frames=[e for e in accel['events'] if e['kind']=='inputs' and 16000<=e['at_ms']<=21000]
        distance=sum((b['at_ms']-a['at_ms'])*(a['values']['speed']+b['values']['speed'])/72000
                     for a,b in zip(frames,frames[1:]))
        self.assertAlmostEqual(distance,75,delta=0.02)
        skid=demo.build('skidpad')
        right=[e for e in skid['events'] if e['kind']=='inputs' and 19000<=e['at_ms']<=29300]
        left=[e for e in skid['events'] if e['kind']=='inputs' and 30200<=e['at_ms']<=40500]
        self.assertTrue(all(e['values']['speed']==400 and e['values']['steering']==32 for e in right))
        self.assertTrue(all(e['values']['speed']==400 and e['values']['steering']==-32 for e in left))

    def test_bispingen_fixture_is_reproducible_and_has_bounded_changing_signals(self):
        from examples.generators import create_bispingen as demo
        saved = json.loads((server.ROOT/'examples/scenarios/bispingen.scenario.json').read_text(encoding='utf-8'))
        self.assertEqual(saved, demo.build())
        validated = scenarios.validate(saved, server.FIELDS)
        self.assertEqual(validated['initial']['page'], 'dsp_debug')
        values = [event for event in validated['events'] if event['kind'] == 'inputs']
        lap = [e for e in values if demo.START_MS <= e['at_ms'] <= demo.START_MS+demo.LAP_MS]
        distance = sum((b['at_ms']-a['at_ms'])*(a['values']['speed']+b['values']['speed'])/72000
                       for a,b in zip(lap,lap[1:]))
        self.assertAlmostEqual(distance, 1000, delta=1)
        self.assertEqual(max(e['values']['speed'] for e in lap), 700)
        self.assertTrue(any(e['values']['steering'] < 0 for e in lap))
        self.assertTrue(any(e['values']['steering'] > 0 for e in lap))
        self.assertTrue(any(e['values']['front'] > 0 for e in lap))
        self.assertTrue(all(not (e['values']['front'] and e['values']['apps1']) for e in values))
        self.assertTrue(all(abs(b['values']['speed']-a['values']['speed']) / 3.6 <= 4.5
                            for a,b in zip(lap,lap[1:])))

    def test_version_roundtrip_and_reject_unknown_migration(self):
        validated=scenarios.validate(sample(),server.FIELDS)
        self.assertEqual(validated,scenarios.validate(json.loads(json.dumps(validated)),server.FIELDS))
        for key,value in [('version',2),('version',True),('format','other'),('duration_ms',True),('duration_ms',600001),('events',None),('expected_tx',None),('assertions',None)]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):scenarios.validate({**sample(),key:value},server.FIELDS)

    def test_invalid_event_and_generator_fields(self):
        bad=[dict(at_ms=1,kind='can',can_id=0x500,dlc=0,data=[]),
             dict(at_ms=1,kind='can',can_id=0x800,dlc=1,data=[0]),
             dict(at_ms=1,kind='can',can_id=0x200,dlc=1,data=[]),
             dict(at_ms=1,kind='can',can_id=0x200,dlc=1,data=[True]),
             dict(at_ms=1,kind='gpio',pin='UNKNOWN',pressed=True),
             dict(at_ms=1,kind='gpio',pin='R2D',pressed=1),
             dict(at_ms=1,kind='inputs',values=dict(invented=1)),
             dict(at_ms=1,kind='generator',can_id=123,enabled=False),
             dict(at_ms=4000,kind='inputs',values={})]
        for event in bad:
            with self.subTest(event=event),self.assertRaises(ValueError):scenarios.validate({**sample(),'events':[event]},server.FIELDS)
        for generator in [dict(can_id=512,period_ms=0),dict(can_id=512,period_ms=10,enabled=1),dict(can_id=123,period_ms=10),dict(can_id=512,period_ms=10,data=[0],counter=dict(byte=7))]:
            with self.subTest(generator=generator),self.assertRaises(ValueError):scenarios.validate({**sample(),'generators':[generator]},server.FIELDS)

    def test_payload_size_count_and_per_tick_limits(self):
        with self.assertRaisesRegex(ValueError,'5 MiB'):scenarios.import_text('x'*(scenarios.MAX_BYTES+1),'candump',server.FIELDS)
        event=dict(kind='can',at_ms=11,can_id=512,dlc=0,data=[])
        with self.assertRaisesRegex(ValueError,'96'):scenarios.validate({**sample(),'events':[event]*97},server.FIELDS)
        with patch.object(scenarios,'MAX_EVENTS',1),self.assertRaisesRegex(ValueError,'Eingabeereignisse'):scenarios.validate({**sample(),'events':[event,event]},server.FIELDS)
        with self.assertRaises(ValueError):scenarios.validate({**sample(),'assertions':[dict(at_ms=0,path='__class__',expected=0)]},server.FIELDS)

    def test_stable_same_time_order(self):
        events=[dict(kind='can',at_ms=12,can_id=512,dlc=1,data=[3]),dict(kind='can',at_ms=11,can_id=512,dlc=1,data=[1]),dict(kind='can',at_ms=11,can_id=512,dlc=1,data=[2])]
        value=scenarios.validate({**sample(),'events':events},server.FIELDS)
        self.assertEqual([e['data'][0] for e in value['events']],[1,2,3])

    def test_profiles_remain_v1_unmodified_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=profiles.Store(tmp,server.FIELDS)
            state=profiles.validate_state(dict(values=dict(front=9),raw='204: 06 00 00 00 00 00 00 00',page='dsp_debug'),server.FIELDS)
            store.change(dict(action='create',name='Old profile',state=state));before=store.path.read_bytes()
            scenarios.validate(sample(),server.FIELDS)
            self.assertEqual(profiles.Store(tmp,server.FIELDS).list()[0]['state'],state)
            self.assertEqual(store.path.read_bytes(),before)

    def test_example_library_is_bounded_and_import_does_not_write_files(self):
        library=scenarios.Library(server.ROOT,server.FIELDS)
        self.assertEqual({item['id'] for item in library.listing()}, {'normal.scenario','can-loss.scenario','ams-temperature.scenario','ams-delayed.scenario','imd-latch.scenario','bispingen.scenario',
                         'fs-acceleration.scenario','fs-skidpad.scenario','fs-autocross.scenario',
                         'fs-endurance.scenario','fs-efficiency.scenario'})
        with tempfile.TemporaryDirectory() as tmp:
            empty=scenarios.Library(tmp,server.FIELDS);empty.add(scenarios.validate(sample(),server.FIELDS))
            self.assertEqual(list(Path(tmp).iterdir()),[])


class CandumpTests(unittest.TestCase):
    def parse(self,text,**args):return scenarios.import_text(text,'candump',server.FIELDS,**args)

    def test_epoch_resolution_sorting_ties_and_tx_separation(self):
        parsed=self.parse('(1000.000000) can0 200#01\n(1000.001800) can0 201#02\n(1000.001100) can0 204#03\n(1000.001100) can0 204#04\n(1000.100000) can0 500#0000000000000003',offset_ms=10)
        self.assertEqual([e['at_ms'] for e in parsed['events']],[10,12,12,12])
        self.assertEqual([e['data'][0] for e in parsed['events']],[1,3,4,2])
        self.assertEqual(parsed['expected_tx'][0]['at_ms'],110)
        self.assertEqual(parsed['generators'],[])
        self.assertEqual(parsed['origin']['epoch_seconds'],'1000.000000')

    def test_invalid_or_unsupported_logs_are_not_silently_skipped(self):
        for text,message in [('', 'keine CAN'),('(1.0) can0 200##100','CAN FD'),('(1.0) can0 200#R8','RTR'),('(1.0) can0 00000200#00','Extended'),('(1.0) can0 20000001#00','Error'),('(1.0) can0 800#00','CAN-ID'),('(1.0) can0 200#0','Datenbytes'),('(1.0) can0 200#'+'00'*9,'Datenbytes'),('garbage','Zeile'),('(1.0) can0 200#\n(1.1) can1 200#','Interfaces'),('(1.0) can0 200#\n(602.0) can0 200#','10 Minuten')]:
            with self.subTest(text=text),self.assertRaisesRegex(ValueError,message):self.parse(text)

    def test_zero_dlc_and_synthetic_example(self):
        self.assertEqual(self.parse('(1.0) can0 200#')['events'][0]['data'],[])
        parsed=self.parse((server.ROOT/'examples/logs/minimal.candump').read_text(encoding='utf-8'))
        self.assertEqual(len(parsed['events']),2);self.assertEqual(len(parsed['expected_tx']),1)
