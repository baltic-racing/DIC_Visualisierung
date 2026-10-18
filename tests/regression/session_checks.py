"""Etappe 1: independent expectations against the supplied local firmware.

Usage: python3 tests/regression/session_checks.py /path/to/DIC_Firmware
All firmware mutations, Git fixtures, builds and settings are temporary.
No origin/TY26_Test, browser, installed Node or extra Python package required.
"""
import copy
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from dic_visualisierung import profiles
from dic_visualisierung import server
from dic_visualisierung import simulation
from dic_visualisierung import verify
FIRMWARE=None


class SessionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=FIRMWARE.resolve()
        cls.hashes={str(p.relative_to(cls.original)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (cls.original/'DIC_23').rglob('*') if p.is_file()}
        server.REPO=cls.original
        cls.sources={name:code.replace('\r\n','\n') for name,code in server.sources('local')[0].items()}
        cls.tmp=tempfile.TemporaryDirectory(prefix='DIC-stage1-tests-')
        cls.root=Path(cls.tmp.name)
        server.BUILD_ROOT=cls.root/'build'
        cls.fixture=cls.root/'firmware'
        server.CONFIG_DIR=cls.root/'settings'

    @classmethod
    def tearDownClass(cls):
        after={str(p.relative_to(cls.original)):hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (cls.original/'DIC_23').rglob('*') if p.is_file()}
        assert after==cls.hashes,'Original firmware changed'
        server.CACHE.clear();server.BUILDS.clear()
        cls.tmp.cleanup()

    def setUp(self):
        import shutil
        if self.fixture.exists():
            shutil.rmtree(self.fixture)
        (self.fixture/'DIC_23').mkdir(parents=True)
        for name,source in self.sources.items():
            path=self.fixture/'DIC_23'/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(source)
        server.REPO=self.fixture
        self.snapshot=server.sources('local')
        self.sessions=[]

    def tearDown(self):
        for session in self.sessions:
            session.close()

    def query(self,**values):
        return {k:[str(v)] for k,v in dict(source='local',page='dsp_main',**values).items()}

    def session(self,**values):
        session=simulation.Session(server,self.snapshot,server.input_packet(self.query(**values),self.snapshot))
        self.sessions.append(session)
        return session

    def manager(self,**values):
        self.clock=0.0
        manager=simulation.Interactive(server,background=False,clock=lambda:self.clock)
        self.sessions.append(manager)
        manager.inputs(self.query(**values))
        return manager

    def test_cold_start_and_2000_15000_ms_boundaries(self):
        session=self.session(ts_button=1)
        first=session.frame()
        self.assertEqual((first['time_ms'],first['sys_time'],first['active_page']),(0,0,'dsp_startup'))
        self.assertEqual(first['state']['sys_time_old'],0)
        self.assertEqual(first['outputs']['imd_led'],1)  # intentional boot lamp test
        self.assertEqual(session.advance_to(1999)['state']['led_test'],1)
        at=session.advance_to(2000)
        self.assertEqual((at['state']['led_test'],at['outputs']['imd_led'],at['active_page']),(0,0,'dsp_main'))
        self.assertEqual(session.advance_to(2001)['outputs']['imd_led'],0)
        self.assertEqual(session.advance_to(14999)['state']['TS_ON'],0)
        self.assertEqual(session.advance_to(15000)['outputs']['tx'][0],1)
        self.assertEqual(session.advance_to(15001)['state']['TS_ON'],1)

    def test_imd_latch_across_inputs_reads_and_reset(self):
        session=self.session()
        session.advance_to(2000)
        session.schedule({'values':{'imd_error':1}},2001)
        self.assertEqual(session.advance_to(3999)['outputs']['imd_led'],0)
        self.assertEqual(session.advance_to(4000)['outputs']['imd_led'],1)
        session.schedule({'values':{'imd_error':0,'front':15,'diag':0}},4001)
        frame=session.advance_to(5000)
        self.assertEqual(frame['state']['IMD_LED_ON'],1)
        self.assertEqual(frame['outputs']['imd_led'],1)
        for _ in range(100):
            self.assertEqual(session.frame(),frame)
            self.assertEqual(session.worker.command('S')['time_ms'],5000)
        fresh=self.session()
        self.assertEqual(fresh.advance_to(5000)['outputs']['imd_led'],0)
        self.assertEqual(fresh.worker.latest['state']['IMD_LED_ON'],0)

    def test_ams_latch_and_low_brake_sum_remain_original(self):
        session=self.session(front=50,rear=20)
        self.assertEqual(session.advance_to(2000)['state']['brake_balance_front'],83)
        session.schedule({'values':{'ams_error':1}},2001)
        self.assertEqual(session.advance_to(2499)['outputs']['ams_led'],0)
        self.assertEqual(session.advance_to(2500)['state']['bms_error_active'],1)
        session.schedule({'values':{'ams_error':0,'front':0,'rear':0}},2501)
        frame=session.advance_to(3000)
        self.assertEqual(frame['outputs']['ams_led'],1)
        self.assertEqual((frame['state']['brake_balance_front'],frame['state']['brake_balance_rear']),(83,16))

    def test_mode_confirmation_keeps_wait_set(self):
        query=self.query();query['page']=['dsp_modes']
        session=simulation.Session(server,self.snapshot,server.input_packet(query,self.snapshot))
        self.sessions.append(session)
        session.advance_to(2000)
        session.schedule({'values':{'buttons':2}},2001)
        self.assertEqual(session.advance_to(2010)['state']['wait'],1)
        session.schedule({'values':{'buttons':1},'page':'dsp_debug'},2011)
        frame=session.advance_to(2020)
        self.assertEqual((frame['state']['wait'],frame['state']['active_mode'],frame['state']['mode_selection_active']),(1,2,0))
        self.assertEqual(frame['active_page'],'dsp_modes')
        session.schedule({'values':{'buttons':12}},2021)
        self.assertEqual(session.advance_to(2030)['state']['wait'],0)

    def test_call_based_diagnostic_and_gps_aging(self):
        session=self.session(diag=6)
        session.advance_to(2000)
        session.schedule({'values':{'gps_mode':1,'diag_mode':1}},2001)
        frame=session.advance_to(2999)
        self.assertEqual((frame['state']['gps_age_ticks'],frame['state']['ams_diag_age_ticks']),(99,99))
        self.assertEqual(frame['outputs']['ams_diagnostic_valid'],1)
        frame=session.advance_to(3000)
        self.assertEqual((frame['state']['gps_age_ticks'],frame['state']['ams_diag_age_ticks']),(100,100))
        self.assertEqual(frame['outputs']['ams_diagnostic_valid'],0)

    def test_pause_step_resume_target_and_repeatable_reset(self):
        manager=self.manager()
        self.clock=100;manager.pump()
        self.assertEqual(manager.frame()['time_ms'],0)
        self.assertEqual(manager.control('step')['time_ms'],1)
        self.assertEqual(manager.control('advance',target_ms=2200)['time_ms'],2200)
        manager.control('resume');self.clock+=0.123;manager.pump()
        self.assertEqual(manager.frame()['time_ms'],2323)
        manager.control('pause');self.clock+=20;manager.pump()
        self.assertEqual(manager.frame()['time_ms'],2323)
        one=manager.control('reset');two=manager.control('reset')
        for key in ('time_ms','sys_time','rows','glyphs','outputs','state'):
            self.assertEqual(one[key],two[key])
        self.assertNotEqual(one['session']['id'],two['session']['id'])

    def test_local_button_pulses_apply_at_exact_virtual_times(self):
        manager=self.manager()
        manager.control('advance',target_ms=14999)
        manager.control('pulse',button='ts_button',at_ms=15000,duration_ms=100)
        manager.control('pulse',button='r2d_button',at_ms=15000,duration_ms=100)
        self.assertEqual(manager.frame()['outputs']['tx'][:2],[0,0])
        self.assertEqual(manager.control('advance',target_ms=15000)['outputs']['tx'][:2],[1,1])
        self.assertEqual(manager.control('advance',target_ms=15099)['state']['TS_ON'],1)
        self.assertEqual(manager.control('advance',target_ms=15100)['outputs']['tx'][:2],[0,0])

    def test_speed_poll_rate_and_overload_do_not_change_results(self):
        outputs=[]
        for speed,polls in ((0.25,0),(1,50),(8,200)):
            manager=self.manager()
            manager.inputs(self.query(imd_error=1),at=2500)
            manager.control('pulse',button='r2d_button',at_ms=4100,duration_ms=123)
            manager.control('speed',speed=speed)
            manager.control('resume')
            self.clock+=5/speed
            manager.pump()
            self.assertEqual(manager.frame()['time_ms'],1000)
            self.assertEqual(manager.frame()['session']['backlog_ms'],4000)
            while manager.budget>=1:
                for _ in range(polls):manager.frame()
                manager.pump()
            frame=manager.frame()
            self.assertEqual(frame['time_ms'],5000)
            outputs.append({key:frame[key] for key in ('time_ms','sys_time','outputs','rows','glyphs','state')})
        self.assertEqual(outputs[0],outputs[1]);self.assertEqual(outputs[1],outputs[2])

    def test_time_progress_without_display_draws(self):
        path=self.fixture/'DIC_23/main.c'
        path.write_text(self.sources['main.c'].replace('if (draw_data)','if (0 && draw_data)'))
        snapshot=server.sources('local')
        with simulation.Session(server,snapshot,server.input_packet(self.query(),snapshot)) as session:
            frame=session.advance_to(3000)
            self.assertEqual(frame['time_ms'],3000)
            self.assertEqual(frame['state']['display_column'],0)
            self.assertEqual(frame['outputs']['imd_led'],0)

    def test_32_bit_wrap_and_missed_ticks_count_once(self):
        session=self.session()
        session.advance_to(1)
        frame=session.worker.advance(1,0xfffffffe)  # explicit coalesced timer test only
        self.assertEqual(frame['sys_time'],0xffffffff)
        self.assertEqual(frame['state']['time_10ms'],2)
        frame=session.worker.advance(1)
        self.assertEqual((frame['time_ms'],frame['sys_time'],frame['state']['sys_time_old']),(0x100000000,0,0))
        self.assertEqual(frame['state']['time_10ms'],3)

    def test_source_compile_failure_recovery_and_git_switch(self):
        manager=self.manager()
        manager.control('advance',target_ms=3000)
        previous=manager.frame()['session']['id']
        process=manager.session.worker.process
        path=self.fixture/'DIC_23/main.c'
        path.write_text(self.sources['main.c']+'\n#error EXPECTED_STAGE1_ERROR\n')
        manager.watch(force=True)
        self.assertIsNotNone(process.poll())
        with self.assertRaisesRegex(ValueError,'EXPECTED_STAGE1_ERROR'):manager.frame()
        path.write_text(self.sources['main.c'])
        manager.watch(force=True)
        self.assertEqual(manager.frame()['time_ms'],0)
        self.assertNotEqual(manager.frame()['session']['id'],previous)
        self.assertIn('geändert',manager.frame()['session']['notice'])
        for args in (['init','-q'],['add','.'],['-c','user.name=Fixture','-c','user.email=fixture@localhost','commit','-qm','Fixture']):
            subprocess.run(['git','-C',str(self.fixture),*args],check=True,capture_output=True)
        branch=server.git('branch','--show-current')
        query=self.query();query.update(source=['ref'],ref=[branch])
        before=manager.frame()['session']['id'];manager.inputs(query)
        self.assertFalse(manager.frame()['local'])
        self.assertNotEqual(manager.frame()['session']['id'],before)
        path.write_text(self.sources['main.c']+'\n#error LOCAL_ONLY\n')
        manager.watch(force=True)
        self.assertEqual(manager.frame()['session']['status'],'paused')

    def test_worker_crash_hang_cleanup_and_diagnostic_separation(self):
        manager=self.manager();process=manager.session.worker.process
        process.kill();process.wait(timeout=2)
        with self.assertRaisesRegex(ValueError,'abgestürzt'):manager.frame()
        self.assertEqual(manager.control('reset')['time_ms'],0)
        path=self.fixture/'DIC_23/main.c'
        path.write_text(self.sources['main.c'].replace('int main(void)\n{','int main(void)\n{\n printf("DIAGNOSTIC_ONLY\\n");'))
        snap=server.sources('local')
        with simulation.Session(server,snap,server.input_packet(self.query(),snap)) as session:
            self.assertEqual(session.advance_to(100)['time_ms'],100)
            self.assertIn('DIAGNOSTIC_ONLY',''.join(session.worker.diagnostics))
        self.assertIsNotNone(session.worker.process.poll())
        path.write_text(self.sources['main.c'].replace('while (1)\n\t{','while (1)\n\t{\n if(sys_time==1){for(;;){}}'))
        snap=server.sources('local')
        with simulation.Session(server,snap,server.input_packet(self.query(),snap)) as session:
            session.worker.timeout=0.2
            with self.assertRaisesRegex(ValueError,'hängt'):session.advance_to(1)
            self.assertIsNotNone(session.worker.process.poll())

    def test_profile_v1_is_inputs_not_ram_and_tests_are_isolated(self):
        session=self.session(imd_error=1)
        session.advance_to(5000)
        values={f['id']:f['default'] for f in server.FIELDS}
        state=dict(values=values,raw='',scenario='example',page='dsp_main')
        store=profiles.Store(self.root/'profile-fixture',server.FIELDS,self.fixture)
        store.change(dict(action='create',name='Legacy v1',state=state))
        before=store.path.read_bytes()
        loaded=profiles.Store(self.root/'profile-fixture',server.FIELDS,self.fixture).list()[0]['state']
        session.schedule({'values':loaded['values']},5001)
        self.assertEqual(session.advance_to(5100)['outputs']['imd_led'],1)
        previous=session.frame()
        results=verify.run_suite(server)
        self.assertTrue(all(r['status']=='passed' for r in results['results']),results)
        self.assertEqual(session.frame(),previous)
        self.assertEqual(store.path.read_bytes(),before)

    def test_browser_reads_are_pure_and_inputs_are_scheduled_via_post(self):
        manager=self.manager()
        with patch.object(server,'INTERACTIVE',manager):
            http=server.LocalServer(('127.0.0.1',0))
            thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
            def request(method,path,data=None):
                conn=HTTPConnection('127.0.0.1',http.server_port,timeout=5)
                conn.request(method,path,None if data is None else json.dumps(data),{'Content-Type':'application/json','X-DIC-Token':http.token})
                response=conn.getresponse();status=response.status;body=json.loads(response.read());conn.close()
                return status,body
            try:
                for _ in range(20):
                    status,frame=request('GET','/api/frame?imd_error=1&duration=10000')
                    self.assertEqual((status,frame['time_ms']),(200,0))
                query={k:v[0] for k,v in self.query(imd_error=1).items()}
                status,frame=request('POST','/api/session',dict(action='inputs',query=query,at_ms=2500))
                self.assertEqual((status,frame['time_ms'],frame['session']['next_input_ms']),(200,0,1))
                status,frame=request('POST','/api/session',dict(action='advance',target_ms=5000))
                self.assertEqual((status,frame['outputs']['imd_led']),(200,1))
                self.assertEqual(request('POST','/api/session',dict(action='advance',target_ms=True))[0],422)
            finally:
                http.shutdown();http.server_close();thread.join(timeout=3)

    def test_background_runs_and_watches_without_browser_requests(self):
        manager=simulation.Interactive(server)
        self.sessions.append(manager)
        manager.inputs(self.query())
        manager.control('resume')
        deadline=time.monotonic()+3
        while manager.session.now<50 and time.monotonic()<deadline:
            threading.Event().wait(0.01)
        self.assertGreaterEqual(manager.session.now,50)
        generation=manager.generation
        path=self.fixture/'DIC_23/main.c'
        path.write_text(self.sources['main.c']+'\n/* watched without browser */\n')
        deadline=time.monotonic()+3
        while manager.generation==generation and time.monotonic()<deadline:
            threading.Event().wait(0.01)
        with manager.lock:
            self.assertGreater(manager.generation,generation)
            self.assertFalse(manager.running)
            self.assertEqual(manager.frame()['time_ms'],0)
            process=manager.session.worker.process
        manager.close()
        self.assertIsNotNone(process.poll())

    def test_separate_avr_clock_patch_applies_and_runs_in_host(self):
        patchfile=server.ROOT/'docs/Firmware-Zeitkorrektur.patch'
        for args in (['--check',str(patchfile)],[str(patchfile)]):
            subprocess.run(['git','-C',str(self.fixture),'apply',*args],check=True,capture_output=True)
        snapshot=server.sources('local')
        self.assertIn('ATOMIC_BLOCK',snapshot[0]['sys_timer.c'])
        with simulation.Session(server,snapshot,server.input_packet(self.query(),snapshot)) as session:
            self.assertEqual(session.advance_to(2000)['outputs']['imd_led'],0)
            self.assertEqual(session.frame()['state']['sys_time_old'],2000)


if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('Aufruf: python3 tests/regression/session_checks.py /Pfad/zur/DIC_Firmware')
    FIRMWARE=Path(sys.argv.pop())
    unittest.main(verbosity=2)
