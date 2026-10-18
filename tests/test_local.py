"""No firmware fixtures are shipped. These tests need only Python's standard library."""
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
import settings
import choose_folder


class FolderDialogTests(unittest.TestCase):
    def test_macos_path_and_cancel(self):
        with patch.object(choose_folder.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='/Volumes/Team Daten/Firmware ä/\n',stderr='')) as run:
            self.assertEqual(choose_folder.choose_macos(),{'path':'/Volumes/Team Daten/Firmware ä/'})
            self.assertEqual(run.call_args.args[0][0],'/usr/bin/osascript')
            self.assertEqual(run.call_args.kwargs['timeout'],110)
        with patch.object(choose_folder.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='User canceled. (-128)')):
            self.assertEqual(choose_folder.choose_macos(),{'path':''})

    def test_macos_failure_timeout_and_no_tk(self):
        with patch.object(choose_folder.subprocess,'run',side_effect=OSError('missing')):
            self.assertIn('error',choose_folder.choose_macos())
        with patch.object(choose_folder.subprocess,'run',side_effect=choose_folder.subprocess.TimeoutExpired('osascript',110)):
            self.assertIn('error',choose_folder.choose_macos())
        with patch.object(sys,'platform','darwin'),patch.object(choose_folder,'choose_macos',return_value={'path':''}),patch.object(choose_folder,'choose_tk',side_effect=AssertionError('Tk must not start on macOS')),patch('builtins.print') as output:
            choose_folder.main()
            self.assertEqual(json.loads(output.call_args.args[0]),{'path':''})


class SettingsTests(unittest.TestCase):
    def test_first_start_invalid_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertEqual(settings.load(root/'config'),{})
            with self.assertRaisesRegex(ValueError,'fehlen'):
                settings.validate_firmware(str(root),['main.c'])
            (root/'firmware/DIC_23').mkdir(parents=True)
            (root/'firmware/DIC_23/main.c').write_text('/* synthetic validation fixture */',encoding='utf-8')
            firmware=settings.validate_firmware(str(root/'firmware/DIC_23'),['main.c'])
            self.assertEqual(firmware,(root/'firmware').resolve())
            settings.save_firmware(firmware,root/'config')
            self.assertEqual(settings.load(root/'config')['firmware_path'],str(firmware))
            self.assertFalse((firmware/'settings.json').exists())
            with self.assertRaisesRegex(ValueError,'nicht im Firmware'):
                settings.save_firmware(firmware,firmware/'settings')

    def test_corrupt_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'settings.json').write_text('{broken',encoding='utf-8')
            self.assertEqual(settings.load(root),{})

    def test_platform_paths(self):
        with patch.dict(os.environ,{'LOCALAPPDATA':'local-data','XDG_CONFIG_HOME':'xdg'},clear=True):
            with patch.object(sys,'platform','win32'):
                self.assertEqual(settings.settings_directory(),Path('local-data/DIC_Visualisierung'))
            with patch.object(sys,'platform','darwin'):
                self.assertEqual(settings.settings_directory(),Path.home()/'Library/Application Support/DIC_Visualisierung')
            with patch.object(sys,'platform','linux'):
                self.assertEqual(settings.settings_directory(),Path('xdg/DIC_Visualisierung'))

    def test_compiler_override_and_windows_fallback(self):
        with patch.dict(os.environ,{'DIC_CC':'missing-compiler'}),patch('shutil.which',return_value=None):
            with self.assertRaisesRegex(ValueError,'DIC_CC'):
                server.compiler()
        with patch.dict(os.environ,{},clear=True),patch.object(sys,'platform','win32'),patch('pathlib.Path.is_file',return_value=False),patch('shutil.which',side_effect=lambda name:'gcc.exe' if name=='gcc' else None):
            self.assertEqual(server.compiler(),'gcc.exe')

    def test_unconfigured_frame(self):
        with patch.object(server,'REPO',None):
            with self.assertRaisesRegex(ValueError,'Firmware-Ordner'):
                server.frame({})


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=server.LocalServer(('127.0.0.1',0))
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join(timeout=3)

    def request(self,method,path,headers=None,body=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        connection.request(method,path,body=body,headers=headers or {})
        response=connection.getresponse();result=response.status,response.read(),dict(response.getheaders())
        connection.close();return result

    def token(self,**extra):
        return {'X-DIC-Token':self.http.token,**extra}

    def test_html_session_and_headers(self):
        status,body,headers=self.request('GET','/')
        self.assertEqual(status,200)
        self.assertIn(self.http.token.encode(),body)
        self.assertNotIn(b'__DIC_TOKEN__',body)
        self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
        self.assertNotIn('Access-Control-Allow-Origin',headers)

    def test_api_token_required(self):
        self.assertEqual(self.request('GET','/api/config')[0],403)
        self.assertEqual(self.request('GET','/api/config',self.token())[0],200)

    def test_cross_origin_and_dns_rebinding_denied(self):
        self.assertEqual(self.request('GET','/api/config',self.token(Origin='http://foreign.invalid'))[0],403)
        self.assertEqual(self.request('GET','/',{'Host':'foreign.invalid'})[0],403)
        self.assertEqual(self.request('GET','/api/config',self.token(**{'Sec-Fetch-Site':'cross-site'}))[0],403)
        self.assertEqual(self.request('OPTIONS','/api/config')[0],403)

    def test_post_validation_and_no_configuration_mutation(self):
        self.assertEqual(self.request('POST','/api/config',self.token(**{'Content-Type':'text/plain'}),'{}')[0],415)
        self.assertEqual(self.request('POST','/api/config',self.token(**{'Content-Type':'application/json'}),'not json')[0],422)
        self.assertEqual(self.request('POST','/api/config',self.token(**{'Content-Type':'application/json'}),'{}')[0],422)

    def test_dialog_contract_without_opening_os_dialog(self):
        with patch.object(server,'choose_folder',return_value={'path':''}) as choose:
            status,body,_=self.request('POST','/api/choose-folder',self.token(**{'Content-Type':'application/json'}),'{}')
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)['path'],'')
            choose.assert_called_once()

    def test_configure_via_http_and_reload_local_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            firmware=root/'trusted fixture with spaces'
            (firmware/'DIC_23').mkdir(parents=True)
            for name in server.FILES:
                (firmware/'DIC_23'/name).write_text('/* synthetic fixture */',encoding='utf-8')
            with patch.object(server,'REPO',None),patch.object(server,'CONFIG_DIR',root/'config'):
                status,body,_=self.request('POST','/api/config',self.token(**{'Content-Type':'application/json'}),json.dumps({'path':str(firmware)}))
                self.assertEqual(status,200)
                self.assertTrue(json.loads(body)['configured'])
                saved=settings.load(root/'config')
                self.assertEqual(saved['firmware_path'],str(firmware.resolve()))
                self.assertEqual(server.REPO,firmware.resolve())
                self.assertEqual(sorted(p.name for p in (firmware/'DIC_23').iterdir()),sorted(server.FILES))
                self.assertEqual(self.request('POST','/api/config',self.token(**{'Content-Type':'application/json'}),json.dumps({'path':str(root/'missing')}))[0],422)
                self.assertEqual(server.REPO,firmware.resolve())


if __name__=='__main__':
    unittest.main()
