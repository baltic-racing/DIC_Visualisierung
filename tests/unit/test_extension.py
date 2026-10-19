"""Local profiles, explicit test oracles and API contracts; no firmware shipped."""
import copy
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dic_visualisierung import firmware
from dic_visualisierung import profiles
from dic_visualisierung import server
from dic_visualisierung import verify
def state():
    return dict(values={f['id']: f['default'] for f in server.FIELDS}, raw='204: 06 00 00 00 00 00 00 00', scenario='example', page='any_page')


class ProfileTests(unittest.TestCase):
    def test_complete_lifecycle_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = profiles.Store(tmp, server.FIELDS)
            sample = state()
            sample['values'].update(ams_mode=2, gps_mode=1, diag_mode=1, imd_error=1)
            created = store.change(dict(action='create', name='Training', state=sample))
            key = created['selected']
            restarted = profiles.Store(tmp, server.FIELDS)
            self.assertEqual(restarted.list()[0]['state'], sample)
            changed = copy.deepcopy(sample)
            changed['values']['front'] = 99
            restarted.change(dict(action='save', id=key, state=changed))
            restarted.change(dict(action='rename', id=key, name='Training geändert'))
            self.assertEqual(store.list()[0]['name'], 'Training geändert')
            self.assertEqual(store.list()[0]['state'], changed)
            store.change(dict(action='delete', id=key))
            self.assertEqual(restarted.list(), [])

    def test_json_import_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = profiles.Store(tmp, server.FIELDS)
            export = dict(format='dic-simulation-profile', version=1, name='Import', state=state())
            imported = store.change(dict(action='import', profile=json.loads(json.dumps(export))))
            self.assertEqual(imported['profiles'][0]['state'], state())
            before = store.path.read_bytes()
            for mutation in [dict(format='other'), dict(version=99), dict(name=''), dict(state={}),
                             dict(state=dict(state(), raw='204: 00')),
                             dict(state=dict(state(), values={'front': True})),
                             dict(state=dict(state(), values={'front': 1001})),
                             dict(state=dict(state(), values={'invented': 1}))]:
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    store.change(dict(action='import', profile={**export, **mutation}))
                self.assertEqual(store.path.read_bytes(), before)

    def test_duplicate_and_corrupt_files_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = profiles.Store(tmp, server.FIELDS)
            store.change(dict(action='create', name='Test', state=state()))
            with self.assertRaisesRegex(ValueError, 'bereits'):
                store.change(dict(action='create', name='test', state=state()))
            store.path.write_text('{broken', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'nicht überschrieben'):
                store.change(dict(action='create', name='New', state=state()))
            self.assertEqual(store.path.read_text(), '{broken')

    def test_never_store_inside_firmware(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Firmware'):
                profiles.Store(Path(tmp)/'sub', server.FIELDS, Path(tmp))
            (Path(tmp)/'DIC_23').mkdir()
            (Path(tmp)/'DIC_23/main.c').write_text('/* fixture */')
            with self.assertRaisesRegex(ValueError, 'Firmware'):
                profiles.Store(Path(tmp)/'config', server.FIELDS)


class AdapterTests(unittest.TestCase):
    def test_real_preprocessed_page_order_not_names(self):
        self.assertEqual(firmware.page_names('uintptr_t page_order[] = {&new_name, (uintptr_t)&another};'), ['new_name', 'another'])
        with self.assertRaisesRegex(ValueError, 'Eintrag'):
            firmware.page_names('uintptr_t page_order[] = {get_page()};')

    def test_renderer_name_can_change_and_prototypes_are_preserved(self):
        code = 'void renamed(struct DISPLAY_PAGE *p, struct DISPLAY_STATE *s);\n/* void renamed(x) {} */\nvoid renamed(struct DISPLAY_PAGE *p, struct DISPLAY_STATE *s) {}'
        source = {'main.c': 'int main(void) { renamed(p,s); }', 'new.c': code}
        self.assertEqual(firmware.render_hook(source), ('new.c', 'renamed'))
        updated = firmware.rename_definition(code, 'renamed')
        self.assertIn('void renamed(struct DISPLAY_PAGE *p, struct DISPLAY_STATE *s);', updated)
        self.assertIn('void preview_real_renamed(', updated)

    def test_unadapted_hardware_is_reported(self):
        with self.assertRaisesRegex(ValueError, 'Hardwareadapter'):
            firmware.strip_includes('#include <avr/pgmspace.h>')


class TestOracleTests(unittest.TestCase):
    def backend(self, wrong=False, without_page=False):
        from types import SimpleNamespace
        pages = ['renamed_page'] if without_page else ['dsp_reduced']
        def simulate(query, snapshot=None):
            ams = int(query['ams_error'][0]) or int(query['ams_mode'][0]) == 2
            return dict(rows=[list(map(ord,' '*20)), list(map(ord,'AMS-E: PEC'.ljust(20))), [32]*20, [32]*20],
                        outputs=dict(ams_led=0 if wrong else int(ams), imd_led=int(query['imd_error'][0]), bottom=[int(ams)]*6, tx=[0]*7+[3]))
        return SimpleNamespace(LOCK=threading.RLock(), FIELDS=server.FIELDS,
                               sources=lambda *args: ({}, 'fixture', '', '', 'revision', True),
                               compile_preview=lambda *args: (None, pages), frame=simulate)

    def test_wrong_firmware_result_fails_instead_of_becoming_expected(self):
        result = verify.run_suite(self.backend(wrong=True), test='ams')['results'][0]
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['checks'][0]['expected'], 1)
        self.assertEqual(result['checks'][0]['actual'], 0)

    def test_test_timeline_does_not_block_interactive_backend(self):
        backend = self.backend()
        simulate = backend.frame
        acquired = []
        def independent_reader():
            available = backend.LOCK.acquire(timeout=0.2)
            acquired.append(available)
            if available:
                backend.LOCK.release()
        def timeline(query, snapshot=None):
            reader = threading.Thread(target=independent_reader)
            reader.start()
            reader.join(timeout=1)
            return simulate(query, snapshot)
        backend.frame = timeline
        result = verify.run_suite(backend, test='ams')['results'][0]
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(acquired, [True])

    def test_no_layout_expectation_is_invented_after_page_removed(self):
        result = verify.run_suite(self.backend(without_page=True), test='diagnosis')['results'][0]
        self.assertEqual(result['status'], 'not-configured')

    def test_diagnosis_without_supported_signal_is_not_configured(self):
        result = verify.run_suite(self.backend(), test='diagnosis')['results'][0]
        self.assertEqual(result['status'], 'not-configured')


class ExtensionHTTPTests(unittest.TestCase):
    def test_profiles_and_tests_endpoints_use_existing_security_and_local_storage(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(server, 'CONFIG_DIR', Path(tmp)), patch.object(server, 'REPO', None):
            http = server.LocalServer(('127.0.0.1', 0))
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            def request(method, path, data=None, token=True):
                conn = HTTPConnection('127.0.0.1', http.server_port, timeout=10)
                headers = {'Content-Type': 'application/json'}
                if token:
                    headers['X-DIC-Token'] = http.token
                conn.request(method, path, None if data is None else json.dumps(data), headers)
                response = conn.getresponse()
                body = response.read()
                status = response.status
                conn.close()
                return status, body
            try:
                for path in ('/api/profiles', '/api/tests'):
                    self.assertEqual(request('GET', path, token=False)[0], 403)
                self.assertEqual(request('POST', '/api/profiles', {}, token=False)[0], 403)
                
                for asset in ('lcd.js','app.js','profiles.js','tests.js','session.js','replay.js','styles.css'):
                    self.assertEqual(request('GET', '/'+asset)[0], 200)
                status, body = request('POST', '/api/profiles', dict(action='create', name='API', state=state()))
                self.assertEqual(status, 200)
                self.assertTrue((Path(tmp)/'profiles.json').exists())
                self.assertEqual(json.loads(request('GET','/api/profiles')[1])['profiles'][0]['state'], state())
                status, body = request('POST', '/api/tests', dict(test='ams'))
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)['results'][0]['status'], 'failed')
                self.assertEqual(request('POST', '/api/tests', dict(test='unknown'))[0], 422)
            finally:
                http.shutdown();http.server_close();thread.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
