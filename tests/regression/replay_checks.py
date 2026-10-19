"""Simulator contracts and independent firmware timeline oracles, kept separate.

python3 -B tests/regression/replay_checks.py /path/to/DIC_Firmware
Only isolated source copies, builds, settings and Git fixtures are used.
"""
import copy
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dic_visualisierung import server
from dic_visualisierung import scenarios
from dic_visualisierung import simulation
from dic_visualisierung import replay
FIRMWARE=None


def frame(at,ident,data):return dict(kind='can',at_ms=at,can_id=ident,dlc=len(data),data=data)


def scene(duration=6000,events=None,automatic=True,**extra):
    return scenarios.validate(dict(format='dic-scenario',version=1,name='Fixture',duration_ms=duration,
        initial=dict(values={},page='dsp_main'),generators=scenarios.defaults(duration) if automatic else [],
        events=events or [],**extra),server.FIELDS)


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=FIRMWARE.resolve();server.REPO=cls.original
        cls.hashes={str(p.relative_to(cls.original)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (cls.original/'DIC_23').rglob('*') if p.is_file()}
        cls.source={k:v.replace('\r\n','\n') for k,v in server.sources('local')[0].items()}
        cls.temp=tempfile.TemporaryDirectory(prefix='DIC-replay-checks-');cls.root=Path(cls.temp.name)
        server.BUILD_ROOT=cls.root/'build';server.CACHE.clear();server.BUILDS.clear()

    @classmethod
    def tearDownClass(cls):
        after={str(p.relative_to(cls.original)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (cls.original/'DIC_23').rglob('*') if p.is_file()}
        assert after==cls.hashes,'Original firmware changed'
        server.CACHE.clear();server.BUILDS.clear();cls.temp.cleanup()

    def setUp(self):
        self.firmware=self.root/'fixture'
        for name,code in self.source.items():
            path=self.firmware/'DIC_23'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(code)
        server.REPO=self.firmware;server.CONFIG_DIR=self.root/'config'
        self.sessions=[]

    def tearDown(self):
        for item in self.sessions:item.close()

    def make(self,definition=None,**values):
        snap=server.sources('local');query={k:[str(v)] for k,v in values.items()};query['page']=['dsp_main']
        result=simulation.Session(server,snap,server.input_packet(query,snap),replay=definition)
        self.sessions.append(result);return result

    def manager(self,definition):
        self.clock=0.0
        manager=simulation.Interactive(server,background=False,clock=lambda:self.clock);self.sessions.append(manager)
        manager.inputs(dict(source=['local'],page=['dsp_main']))
        manager.control('scenario',definition=definition)
        return manager


class SimulatorContracts(Fixture):

    def test_pending_event_summary_includes_replay_and_manual_arrivals(self):
        definition=scene(100,[frame(11,0x204,[6]),
            dict(kind='inputs',at_ms=50,values={'front':10}),
            dict(kind='gpio',at_ms=70,pin='TS_ON',pressed=True)],automatic=False)
        session=self.make(definition)
        def pending():
            state=session.frame()['session']
            return state['pending_events'],state['next_input_ms']
        self.assertEqual(pending(),(3,11))
        self.assertEqual(pending(),(3,11))  # observation consumes no events
        session.schedule({'values':{'rear':5}},20)
        self.assertEqual(pending(),(4,11))
        session.advance_to(11)
        self.assertEqual(pending(),(3,20))
        session.advance_to(20)
        self.assertEqual(pending(),(2,50))
        session.advance_to(100)
        self.assertEqual(pending(),(0,None))
    def test_can_monitor_separates_arrivals_queries_drops_and_identical_frames(self):
        session=self.make(scene(120,[frame(11,0x204,[6]),frame(12,0x204,[7]),frame(21,0x204,[6])],False))
        at=session.advance_to(11)
        rx=at['traffic']['can']['rx'][0]
        self.assertEqual((rx['can_id'],rx['dlc'],rx['data'],rx['count'],rx['age_ms'],rx['interval_ms']),
                         (0x204,1,[6],1,0,None))
        self.assertEqual(at['outputs']['ams_diagnostic_valid'],0)  # RX precedes C processing.
        at=session.advance_to(12)
        self.assertEqual(at['traffic']['can']['rx'][0]['data'],[6])
        self.assertEqual(at['traffic']['can']['drop'][0]['data'],[7])
        self.assertEqual(at['traffic']['can']['drop'][0]['reason'],1)
        at=session.advance_to(30)
        self.assertEqual((at['traffic']['can']['rx'][0]['count'],at['traffic']['can']['rx'][0]['interval_ms']),(2,10))
        self.assertEqual(at,session.frame())  # Observations never mutate counters/time.
        at['traffic']['can']['rx'][0]['data'][0]=99
        self.assertEqual(session.frame()['traffic']['can']['rx'][0]['data'],[6])
        at=session.advance_to(120)
        self.assertEqual((at['traffic']['can']['rx'][0]['count'],at['traffic']['can']['rx'][0]['age_ms']),(2,99))
        self.assertEqual((at['traffic']['can']['tx'][0]['can_id'],at['traffic']['can']['tx'][0]['at_ms']),(0x500,100))

    def test_can_monitor_retains_last_id_after_recent_trace_expires_and_resets(self):
        events=[frame(11,0x204,[6])]+[frame(t,0x797,[0,0,0,0,0,0,0,10]) for t in range(21,282,10)]
        definition=scene(300,events,False)
        session=self.make(definition)
        at=session.advance_to(300)
        self.assertFalse(any(e['can_id']==0x204 for e in at['traffic']['rx']))
        rx={e['can_id']:e for e in at['traffic']['can']['rx']}
        self.assertEqual((rx[0x204]['data'],rx[0x204]['count'],rx[0x204]['age_ms']),([6],1,289))
        self.assertEqual(rx[0x797]['count'],27)
        self.assertEqual(self.make(definition).frame()['traffic']['can'],dict(rx=[],tx=[],drop=[]))

    def test_first_arm_rxok_reactivation_and_preserved_old_bytes(self):
        session=self.make(scene(50,[frame(5,0x204,[6]),frame(11,0x204,[6]),frame(12,0x204,[7]),frame(21,0x204,[6])],False))
        at=session.advance_to(5)
        self.assertEqual(at['traffic']['counts']['rx'],0);self.assertEqual(at['traffic']['drop'][-1]['reason'],3)
        self.assertEqual(session.advance_to(10)['mobs'][12]['enabled'],1)
        at=session.advance_to(11)
        self.assertEqual((at['mobs'][12]['enabled'],at['mobs'][12]['status']),(0,0xa0))  # RXOK bit 5 + DLCW bit 7
        self.assertEqual(at['outputs']['ams_diagnostic_valid'],0)  # arrival is not a firmware query
        at=session.advance_to(12);self.assertEqual(at['traffic']['drop'][-1]['reason'],1)
        self.assertEqual(at['mobs'][12]['data'][0],6)
        at=session.advance_to(20)
        self.assertEqual((at['mobs'][12]['enabled'],at['mobs'][12]['status']),(1,0))
        self.assertEqual(at['outputs']['ams_diagnostic_code'],6)
        self.assertEqual(session.advance_to(30)['state']['ams_diag_age_ticks'],0)  # identical new frame at 21
        at=session.advance_to(40)
        self.assertEqual(at['state']['ams_diag_age_ticks'],1)
        self.assertEqual(at['mobs'][12]['data'][0],6)

    def test_same_timestamp_first_frame_wins_and_short_dlc_retains_tail(self):
        session=self.make(scene(40,[frame(11,0x204,[6,8,9]),frame(11,0x204,[7,0,0]),frame(21,0x204,[1]),frame(22,0x123,[3])],False))
        at=session.advance_to(19)
        self.assertEqual(at['mobs'][12]['data'][:3],[6,8,9]);self.assertEqual(at['traffic']['counts']['drop'],1)
        at=session.advance_to(29)
        self.assertEqual(at['mobs'][12]['data'][:3],[1,8,9])
        self.assertEqual(at['traffic']['drop'][-1]['reason'],2)

    def test_controller_disable_rejects_arrivals_without_overwriting_buffer(self):
        path=self.firmware/'DIC_23/main.c'
        path.write_text(self.source['main.c'].replace('if((sys_time - sys_time_old)', 'if(sys_time==12)CANGCON=0;\nif((sys_time - sys_time_old)'))
        session=self.make(scene(30,[frame(11,0x204,[6]),frame(13,0x204,[7])],False))
        at=session.advance_to(19)
        self.assertEqual(at['mobs'][12]['data'][0],6)
        self.assertEqual(at['traffic']['drop'][-1]['reason'],4)

    def test_actual_driver_mask_and_lowest_mob_priority(self):
        path=self.firmware/'DIC_23/candata.c'
        path.write_text(self.source['candata.c'].replace('ams_diag_mob.mob_id = AMS_DIAG_MOB_ID;','ams_diag_mob.mob_id = GPS_MOB_ID;'))
        session=self.make(scene(30,[frame(11,0x797,[0,0,0,0,0,0,2,11])],False))
        at=session.advance_to(19)
        self.assertEqual(at['traffic']['rx'][-1]['mob'],11)
        self.assertEqual(at['mobs'][12]['enabled'],1)
        self.assertEqual(session.advance_to(20)['state']['speed_kmh'],52)

    def test_byte_writes_cgram_lcd_and_logical_buffer_are_different(self):
        session=self.make()
        cold=session.frame()
        self.assertEqual(cold['rows'],[[32]*20 for _ in range(4)])
        self.assertEqual(cold['glyphs'][7],[0,0,0,0,0,31,31,31])
        at=session.advance_to(1)
        self.assertEqual(at['rows'][0],[ord('|')]+[32]*19)
        self.assertNotEqual(at['rows'],at['logical_rows'])
        self.assertEqual(session.advance_to(80)['rows'],session.frame()['logical_rows'])
        at=session.advance_to(2000)
        self.assertEqual(at['active_page'],'dsp_main');self.assertNotEqual(at['rows'],at['logical_rows'])
        self.assertEqual(session.advance_to(2001)['rows'][0][0],ord('I'))
        at=session.advance_to(2080);self.assertEqual(at['rows'][0][5],32)  # written before first main-page update at 2010
        at=session.advance_to(2160);self.assertEqual(at['rows'],at['logical_rows'])
        before=copy.deepcopy(at)
        session.inspect('dsp_debug');after=session.frame()
        self.assertEqual((after['time_ms'],after['active_page'],after['mobs'][7]['data'][1]),(2160,'dsp_main',1))
        self.assertEqual(after['rows'],before['rows']);self.assertEqual(after['logical_page'],'dsp_debug')
        self.assertNotEqual(after['logical_rows'],before['logical_rows'])

    def test_transferred_custom_character_and_display_enable(self):
        path=self.firmware/'DIC_23/main.c'
        code=self.source['main.c'].replace('struct DISPLAY_PAGE dsp_debug =','dsp_startup.data[0][0]=7;\nstruct DISPLAY_PAGE dsp_debug =')
        code=code.replace('if((sys_time - sys_time_old)', 'if(sys_time==2)display_write_data(0x08,0);\nif(sys_time==4)display_write_data(0x0c,0);\nif((sys_time - sys_time_old)')
        path.write_text(code)
        session=self.make()
        self.assertEqual(session.advance_to(1)['rows'][0][0],7)
        at=session.advance_to(2);self.assertEqual(at['lcd_on'],0);self.assertEqual(at['rows'][0],[32]*20)
        at=session.advance_to(4);self.assertEqual(at['lcd_on'],1);self.assertEqual(at['rows'][0][0],7)
        self.assertTrue(any(e['data']==[0,8] for e in session.worker.trace if e['kind']=='lcd'))

    def test_generator_manual_and_explicit_arrival_precedence(self):
        events=[dict(kind='inputs',at_ms=11,values=dict(ams_error=1)),frame(11,0x200,[0,0,0,0,0,0,0x20,77])]
        session=self.make(scene(40,events))
        session.schedule({'values':{'ams_error':0}},11)  # manual settings after file settings
        at=session.advance_to(19)
        self.assertEqual(at['mobs'][0]['data'][7],77)
        self.assertEqual(at['traffic']['counts']['drop'],1)  # generator could not overwrite explicit frame
        self.assertEqual(at['mobs'][0]['data'][6],0x20)
        at=session.advance_to(21);self.assertEqual(at['mobs'][0]['data'][6],0x20)

    def test_raw_template_last_line_wins_and_is_not_an_event_list(self):
        session=self.make(raw='204: 01 00 00 00 00 00 00 00\n204: 06 00 00 00 00 00 00 00')
        at=session.advance_to(30)
        received=[e for e in session.worker.trace if e['kind']=='rx' and e['can_id']==0x204]
        self.assertEqual([e['data'][0] for e in received],[6,6])
        self.assertEqual([e['at_ms'] for e in received],[11,21])
        self.assertEqual(at['outputs']['ams_diagnostic_code'],6)

    def test_replay_pause_step_reset_speed_and_defined_assertion_failure(self):
        definition=scene(500,assertions=[dict(at_ms=200,path='outputs.tx.7',expected=99)])
        outputs=[]
        for speed in (0.25,1,8):
            manager=self.manager(definition)
            manager.control('speed',speed=speed);manager.control('resume');self.clock+=0.1/speed;manager.pump()
            at=manager.control('pause');self.assertEqual(at['time_ms'],100)
            self.clock+=10;manager.pump();self.assertEqual(manager.frame()['time_ms'],100)
            self.assertEqual(manager.control('step')['time_ms'],101)
            old=manager.frame()['session']['id'];manager.control('reset');self.assertEqual(manager.frame()['time_ms'],0)
            self.assertNotEqual(manager.frame()['session']['id'],old)
            at=manager.control('advance',target_ms=500)
            self.assertFalse(at['replay']['checks'][0]['passed']);self.assertEqual(at['replay']['checks'][0]['actual'],3)
            self.assertEqual(at['session']['status'],'finished')
            outputs.append({k:at[k] for k in ('rows','logical_rows','state','outputs','counts')})
        self.assertEqual(outputs[0],outputs[1]);self.assertEqual(outputs[1],outputs[2])

    def test_candump_output_is_expectation_not_rx_and_mismatch_fails(self):
        definition=scenarios.import_text((server.ROOT/'examples/logs/minimal.candump').read_text(),'candump',server.FIELDS)
        result=replay.run(server,definition)
        self.assertEqual(result['tx_comparison']['failed'],0)
        self.assertEqual([(e['at_ms'],e['can_id']) for e in result['tx']],[(100,0x500)])
        self.assertFalse(any(e['can_id']==0x500 for e in result['traffic']['rx']))
        broken=copy.deepcopy(definition);broken['expected_tx'][0]['at_ms']=99
        self.assertEqual(replay.run(server,broken)['tx_comparison']['failed'],1)

    def test_http_security_scenario_import_and_isolated_replay(self):
        manager=self.manager(scene(500))
        with patch.object(server,'INTERACTIVE',manager),patch.object(server,'SCENARIOS',scenarios.Library(server.ROOT,server.FIELDS)):
            http=server.LocalServer(('127.0.0.1',0));thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
            def request(method,path,data=None,token=True):
                conn=HTTPConnection('127.0.0.1',http.server_port,timeout=15)
                headers={'Content-Type':'application/json'}
                if token:headers['X-DIC-Token']=http.token
                conn.request(method,path,None if data is None else json.dumps(data),headers)
                response=conn.getresponse();status=response.status;body=response.read();conn.close()
                return status,json.loads(body) if 'api/' in path else body
            try:
                self.assertEqual(request('GET','/api/scenarios',token=False)[0],403)
                before=manager.frame()
                status,data=request('POST','/api/scenarios',dict(action='import',kind='candump',name='Example',text=(server.ROOT/'examples/logs/minimal.candump').read_text()))
                self.assertEqual(status,200);self.assertEqual(manager.frame(),before)
                imported=data['selected'];self.assertEqual(request('POST','/api/session',dict(action='scenario',id=imported))[0],200)
                self.assertEqual(request('POST','/api/session',dict(action='advance',target_ms=100))[1]['replay']['tx']['failed'],0)
                self.assertEqual(request('POST','/api/scenarios',dict(action='import',kind='scenario',text='broken'))[0],422)
                self.assertEqual(request('POST','/api/session',dict(action='can',event=dict(can_id=0x500,dlc=0,data=[])))[0],422)
                self.assertEqual(request('GET','/replay.js')[0],200)
            finally:http.shutdown();http.server_close();thread.join(timeout=3)


class FirmwareTimelineOracles(Fixture):
    def test_synthetic_lap_changes_can_speed_brakes_and_actual_lcd(self):
        definition=scenarios.validate(json.loads((server.ROOT/'examples/scenarios/bispingen.scenario.json').read_text()),server.FIELDS)
        session=self.make(definition)
        accelerating=session.advance_to(20020)
        self.assertEqual(accelerating['state']['speed_kmh'],34)
        self.assertEqual(accelerating['state']['APPS1'],95)
        self.assertEqual(accelerating['state']['BPSF'],0)
        cruising=session.advance_to(25020)
        self.assertEqual(cruising['state']['speed_kmh'],65)
        self.assertEqual(bytes(cruising['rows'][3][2:5]),b'065')
        braking=session.advance_to(30120)
        self.assertEqual(braking['state']['APPS1'],0)
        self.assertEqual(braking['state']['BPSF'],64)
        self.assertEqual(braking['state']['BPSR'],46)
        self.assertEqual(bytes(braking['rows'][0][17:19]),b'64')
        rx=[e for e in cruising['traffic']['rx'] if e['can_id']==0x797]
        self.assertTrue(rx)
        self.assertTrue(any(e['data'][6:8]==[2,138] for e in rx))  # 65.0 km/h big-endian.
        session.advance_to(90000)
        result=session.advance_to(104000)
        self.assertEqual(result['state']['speed_kmh'],0)
        self.assertEqual(result['outputs']['ams_led'],0)
        self.assertTrue(all(check['passed'] for check in result['replay']['checks']))

    def test_counter_runs_freezes_and_resumes_with_latched_warning(self):
        session=self.make()
        session.advance_to(2200);old=session.frame()['state']['last_ams_counter']
        session.schedule({'values':{'ams_mode':1}},2201)
        self.assertEqual(session.advance_to(3199)['outputs']['ams_led'],0)
        at=session.advance_to(3200)
        self.assertEqual(at['outputs']['ams_led'],1);self.assertEqual(at['state']['last_ams_counter'],old)
        self.assertTrue(any(e['can_id']==0x200 for e in at['traffic']['rx']))
        session.schedule({'values':{'ams_mode':0}},3201)
        at=session.advance_to(3210)
        self.assertNotEqual(at['state']['last_ams_counter'],old);self.assertEqual(at['outputs']['ams_led'],1)

    def test_ams_complete_loss_and_return_are_not_identical_frames(self):
        session=self.make();session.advance_to(2200)
        before=sum(e['can_id']==0x200 for e in session.worker.trace if e['kind']=='rx')
        session.schedule({'values':{'ams_mode':2}},2201)
        self.assertEqual(session.advance_to(3199)['outputs']['ams_led'],0)
        self.assertEqual(session.advance_to(3200)['outputs']['ams_led'],1)
        self.assertFalse(any(e['can_id']==0x200 and e['at_ms']>=2201 for e in session.worker.trace if e['kind']=='rx'))
        session.schedule({'values':{'ams_mode':0}},3201)
        at=session.advance_to(3210)
        self.assertEqual(at['state']['ams_disconnect_timestamp'],3210)
        self.assertEqual(at['outputs']['ams_led'],1)

    def test_generator_outage_event_and_return(self):
        events=[dict(kind='generator',at_ms=2201,can_id=0x200,enabled=False),dict(kind='generator',at_ms=3201,can_id=0x200,enabled=True)]
        session=self.make(scene(3500,events))
        self.assertEqual(session.advance_to(3200)['outputs']['ams_led'],1)
        at=session.advance_to(3210);self.assertEqual(at['state']['ams_disconnect_timestamp'],3210)

    def test_delayed_ams_example_is_received_over_can_and_latches_leds(self):
        definition=scenarios.validate(json.loads((server.ROOT/'examples/scenarios/ams-delayed.scenario.json').read_text(encoding='utf-8')),server.FIELDS)
        session=self.make(definition)
        def received(state):return {event['can_id']:event for event in state['traffic']['can']['rx']}
        before=received(session.advance_to(19999))
        self.assertEqual(before[0x200]['data'][6]&0x80,0)
        active=received(session.advance_to(20001))
        self.assertEqual(active[0x200]['at_ms'],20001)
        self.assertEqual(active[0x200]['data'][6]&0x80,0x80)
        self.assertEqual(active[0x204]['data'][0],6)
        next_frame=received(session.advance_to(20011))
        self.assertNotEqual(next_frame[0x200]['data'][7],active[0x200]['data'][7])
        warning=session.advance_to(20600)
        self.assertEqual(warning['outputs']['bottom'],[1]*6)
        self.assertIn('PEC',''.join(chr(c) for c in warning['rows'][1]))
        cleared=session.advance_to(25600)
        self.assertEqual(received(cleared)[0x200]['data'][6]&0x80,0)
        self.assertEqual(received(cleared)[0x204]['data'][0],0)
        self.assertIn('OK',''.join(chr(c) for c in cleared['rows'][1]))
        self.assertEqual(cleared['outputs']['bottom'],[1]*6)
        final=session.advance_to(30000)
        self.assertEqual(final['outputs']['imd_led'],0)
        self.assertEqual(len(session.check_results),14)
        self.assertTrue(all(check['passed'] for check in session.check_results),session.check_results)

    def test_ams_49_and_50_calls_and_short_pulse(self):
        held=self.make(ams_error=1)
        self.assertEqual(held.advance_to(2499)['state']['ams_error_counter1'],49)
        self.assertEqual(held.frame()['outputs']['ams_led'],0)
        self.assertEqual(held.advance_to(2500)['outputs']['ams_led'],1)
        held.schedule({'values':{'ams_error':0}},2501)
        self.assertEqual(held.advance_to(5000)['outputs']['ams_led'],1)
        short=self.make(ams_error=1);short.schedule({'values':{'ams_error':0}},2491)
        at=short.advance_to(3000);self.assertEqual(at['outputs']['ams_led'],0);self.assertEqual(at['state']['ams_error_counter1'],0)

    def test_imd_199_and_200_calls_latch_after_input_clears(self):
        held=self.make(imd_error=1)
        self.assertEqual(held.advance_to(3999)['state']['imd_error_count'],199)
        self.assertEqual(held.frame()['outputs']['imd_led'],0)
        self.assertEqual(held.advance_to(4000)['outputs']['imd_led'],1)
        held.schedule({'values':{'imd_error':0}},4001)
        self.assertEqual(held.advance_to(5000)['outputs']['imd_led'],1)
        short=self.make(imd_error=1);short.schedule({'values':{'imd_error':0}},3991)
        self.assertEqual(short.advance_to(4500)['outputs']['imd_led'],0)

    def test_99_100_empty_gps_diagnostic_cycles_and_return(self):
        session=self.make(diag=6);session.advance_to(2000)
        session.schedule({'values':{'gps_mode':1,'diag_mode':1}},2001)
        at=session.advance_to(2999)
        self.assertEqual((at['state']['gps_age_ticks'],at['state']['ams_diag_age_ticks']),(99,99))
        self.assertEqual((at['state']['speed_valid'],at['outputs']['ams_diagnostic_valid']),(1,1))
        at=session.advance_to(3000)
        self.assertEqual((at['state']['gps_age_ticks'],at['state']['ams_diag_age_ticks']),(100,100))
        self.assertEqual((at['state']['speed_valid'],at['outputs']['ams_diagnostic_valid']),(0,0))
        session.schedule({'values':{'gps_mode':0,'diag_mode':0}},3001)
        at=session.advance_to(3010)
        self.assertEqual((at['state']['speed_valid'],at['outputs']['ams_diagnostic_valid']),(1,1))

    def test_identical_diagnostic_frames_are_new_reception_not_missing(self):
        repeated=self.make(diag=6)
        at=repeated.advance_to(4000)
        self.assertEqual(at['state']['ams_diag_age_ticks'],0);self.assertEqual(at['outputs']['ams_diagnostic_valid'],1)
        missing=self.make(scene(4000,[frame(11,0x204,[6])],False))
        at=missing.advance_to(1020)
        self.assertEqual(at['state']['ams_diag_age_ticks'],100);self.assertEqual(at['mobs'][12]['data'][0],6)
        self.assertEqual(at['outputs']['ams_diagnostic_valid'],0)

    def test_brake_arithmetic_signed_steering_and_low_sum_preserve_values(self):
        session=self.make(raw='401: FF FF FF FF 00 00 00 00\n400: 00 00 00 00 00 00 00 80')
        at=session.advance_to(2100)
        self.assertEqual((at['state']['BPSF'],at['state']['BPSR']),(6553,6553))
        self.assertEqual((at['state']['brake_balance_front'],at['state']['brake_balance_rear']),(66,33))
        self.assertEqual(at['state']['SAS_abs'],128)
        session.schedule({'overrides':[],'values':{'front':0,'rear':0}},2101)
        at=session.advance_to(5000)
        self.assertEqual((at['state']['brake_balance_front'],at['state']['brake_balance_rear']),(66,33))
        session.schedule({'values':{'front':1,'rear':3}},5001)  # sum exactly 10 keeps old result
        self.assertEqual(session.advance_to(5010)['state']['brake_balance_front'],66)
        session.schedule({'values':{'front':1,'rear':4}},5011)  # sum 12 recomputes
        self.assertEqual(session.advance_to(5020)['state']['brake_balance_front'],33)

    def test_actual_44a_decoding_despite_erpm_comment(self):
        session=self.make(raw='44A: 01 C8 02 D3 00 00 00 00\n453: 00 00 00 00 00 00 00 00')
        at=session.advance_to(2100)
        self.assertEqual((at['state']['mcu_temp'],at['state']['motor_temp']),(456,723))

    def test_mode_confirmation_wait_gpio_and_tx_temporal_order(self):
        session=self.make();session.schedule({'page':'dsp_modes','values':{'buttons':2}},2001)
        self.assertEqual(session.advance_to(2010)['state']['wait'],0)  # selects modes at end of iteration
        self.assertEqual(session.advance_to(2020)['state']['wait'],1)
        session.schedule({'page':'dsp_debug','values':{'buttons':1}},2021)
        at=session.advance_to(2030)
        self.assertEqual((at['state']['wait'],at['state']['active_mode'],at['active_page']),(1,2,'dsp_modes'))
        self.assertEqual(session.advance_to(6000)['state']['wait'],1)
        session.schedule({'values':{'buttons':12}},6001)
        self.assertEqual(session.advance_to(6010)['state']['wait'],0)
        definition=scene(250,[dict(kind='gpio',at_ms=100,pin='R2D',pressed=True),dict(kind='gpio',at_ms=101,pin='R2D',pressed=False)],False,
            expected_tx=[dict(at_ms=100,can_id=0x500,dlc=8,data=[0,1,0,0,0,0,0,3]),dict(at_ms=200,can_id=0x500,dlc=8,data=[0,0,0,0,0,0,0,3])])
        result=replay.run(server,definition)
        self.assertEqual(result['tx_comparison']['failed'],0)
        self.assertEqual([e['at_ms'] for e in result['tx']],[100,200])

    def test_firmware_leds_do_not_follow_diagnosis_text(self):
        session=self.make(diag=6)
        at=session.advance_to(5000)
        self.assertEqual(at['outputs']['ams_diagnostic_code'],6)
        self.assertEqual(at['outputs']['ams_led'],0);self.assertEqual(at['outputs']['bottom'],[0]*6)


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Aufruf: python3 tests/regression/replay_checks.py /Pfad/zur/DIC_Firmware')
    FIRMWARE=Path(sys.argv.pop());unittest.main(verbosity=2)
