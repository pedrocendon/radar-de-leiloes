import copy
import hashlib
import io
import json
import sqlite3
import tempfile
import threading
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from friendly_ui import Service
from updater import API, Updater, SafeRedirect, allowed_url, backup_data, download, release_candidate, version_tuple
from version import VERSION


def release(version='0.9.0', content=b'installer'):
    name=f'Instalar-Radar-de-Leiloes-{version}-Windows.exe'
    return dict(draft=False,prerelease=False,tag_name='v'+version,body='Novidades',assets=[dict(
        name=name,state='uploaded',size=len(content),digest='sha256:'+hashlib.sha256(content).hexdigest(),
        browser_download_url=f'https://github.com/pedrocendon/radar-de-leiloes/releases/download/v{version}/{name}')])


class ReleaseTests(unittest.TestCase):
    def test_numeric_versions_and_no_downgrades(self):
        self.assertGreater(version_tuple('0.10.0'),version_tuple('0.9.0'))
        self.assertIsNone(release_candidate(release(VERSION)))
        self.assertIsNone(release_candidate(release('0.7.0')))
        for value in ('0.8','0.8.1-beta','../1.0.0','01.0.0','v1.0.0'):
            with self.assertRaises(ValueError):version_tuple(value)

    def test_requires_stable_release(self):
        for field in ('draft','prerelease'):
            r=release();r[field]=True
            with self.assertRaises(ValueError):release_candidate(r)

    def test_rejects_invalid_assets(self):
        for field,value in [('digest',''),('digest','sha256:bad'),('size',True),('size',0),('size',300*1024*1024),
                            ('state','new'),('name','malware.exe'),('browser_download_url','https://example.com/setup.exe')]:
            r=release();r['assets'][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):release_candidate(r)
        r=release();r['assets']*=2
        with self.assertRaises(ValueError):release_candidate(r)

    def test_legacy_asset_name(self):
        r=release();r['assets'][0]['name']=r['assets'][0]['name'].replace('0.9.0','0.9')
        r['assets'][0]['browser_download_url']=r['assets'][0]['browser_download_url'].replace('0.9.0-Windows','0.9-Windows')
        self.assertEqual(release_candidate(r)['version'],'0.9.0')

    def test_redirect_allowlist(self):
        for url in ('http://github.com/x','https://github.com.evil.test/x','https://github.com@evil.test/x',
                    'https://127.0.0.1/a','file:///C:/test.exe','https://github.com:444/x'):
            self.assertFalse(allowed_url(url))
            with self.assertRaises(ValueError):SafeRedirect().redirect_request(None,None,302,'',{},url)
        self.assertTrue(allowed_url(API))
        self.assertTrue(allowed_url('https://release-assets.githubusercontent.com/file?signature=123'))

    def test_download_only_promotes_verified_bytes(self):
        for content in (b'installer',b'wrongfile',b'short',b'installer plus extra'):
            with self.subTest(content=content),tempfile.TemporaryDirectory() as directory:
                folder=Path(directory);candidate=release_candidate(release())
                if content==b'installer':
                    path=download(candidate,folder,lambda _:None,opener=lambda _:io.BytesIO(content))
                    self.assertEqual(path.read_bytes(),content)
                else:
                    with self.assertRaises(ValueError):download(candidate,folder,lambda _:None,opener=lambda _:io.BytesIO(content))
                    self.assertFalse((folder/'instalador.exe').exists())
                self.assertFalse((folder/'instalador.part').exists())


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.base.joinpath('config.json').write_bytes(Path('config.example.json').read_bytes())
        self.base.joinpath('references.json').write_text('[]')
        self.service=Service(self.base)
        self.stop=Mock()
        self.manager=Updater(self.service,self.base/'program',self.stop)
        self.service.updater=self.manager

    def tearDown(self):
        self.service.closed.set();self.temp.cleanup()

    def test_check_success_and_error_do_not_claim_current(self):
        with patch('updater.open_url',return_value=io.BytesIO(json.dumps(release()).encode())):
            self.manager._check()
        self.assertEqual(self.manager.state()['status'],'available')
        with patch('updater.open_url',side_effect=OSError('offline')):
            self.manager._check()
        self.assertEqual(self.manager.state()['status'],'error')
        self.assertIsNone(self.manager.release)

    def test_busy_search_blocks_install(self):
        self.manager.release=release_candidate(release());self.manager.data['status']='available'
        self.service.job['busy']=True
        with self.assertRaises(ValueError):self.service.mutate('update_install',{})

    def test_updating_blocks_favorites_settings_and_search(self):
        self.service.job.update(busy=True,kind='software')
        for action in ('favorite','schedule','filters','search','update_install'):
            with self.assertRaises(ValueError):self.service.mutate(action,{})

    def test_failed_download_never_starts_installer(self):
        self.service.job.update(busy=True,kind='software')
        with patch('updater.download',side_effect=OSError('offline')),patch('updater.subprocess.Popen') as start:
            self.manager._install(release_candidate(release()))
        start.assert_not_called();self.stop.assert_not_called()
        self.assertFalse(self.service.job['busy']);self.assertFalse(self.service.closed.is_set())

    def test_preferences_survive_restart(self):
        self.service.mutate('update_settings',{'automatic':False})
        self.assertFalse(Updater(self.service,self.base/'program',self.stop).state()['automatic'])
        with self.assertRaises(ValueError):self.service.mutate('update_settings',{'automatic':'yes'})

    def test_backup_restores_database_and_excludes_token(self):
        with sqlite3.connect(self.base/'data/monitor.sqlite') as db:
            db.execute('CREATE TABLE backup_test(value TEXT)');db.execute("INSERT INTO backup_test VALUES ('favorite preserved')")
        db.close()
        (self.base/'data/sessao-interface.json').write_text('SECRET TOKEN')
        backup=self.base/'copy.zip';backup_data(self.base,backup)
        with zipfile.ZipFile(backup) as archive:
            self.assertNotIn('data/sessao-interface.json',archive.namelist())
            self.assertEqual(archive.read('config.json'),(self.base/'config.json').read_bytes())
            restored=self.base/'restored.sqlite';restored.write_bytes(archive.read('data/monitor.sqlite'))
        with closing(sqlite3.connect(restored)) as db:
            self.assertEqual(db.execute('SELECT value FROM backup_test').fetchone()[0],'favorite preserved')

    def test_install_handshake_backup_then_shutdown(self):
        program=self.base/'program';program.mkdir();(program/'RadarUpdate.exe').write_bytes(b'helper')
        candidate=release_candidate(release())
        def fake_download(candidate,folder,progress):
            path=folder/'instalador.exe';path.write_bytes(b'installer');return path
        def fake_spawn(args,**kwargs):
            folder=Path(args[0]).parent
            self.assertTrue((folder/'dados-antes-da-atualizacao.zip').exists())
            (folder/'pronto.txt').write_text('1')
            return Mock(poll=lambda:None)
        with patch('updater.download',side_effect=fake_download),patch('updater.subprocess.Popen',side_effect=fake_spawn),patch('updater.time.sleep'):
            self.manager._install(candidate)
        self.stop.assert_called_once();self.assertTrue(self.service.closed.is_set())
        self.assertEqual(self.manager.state()['status'],'installing')

    def test_version_metadata_matches_build(self):
        self.assertIn('AssemblyVersion("'+VERSION+'.0")',Path('distribution/Launcher.cs').read_text())
        self.assertIn('AppVersion='+VERSION,Path('distribution/radar.iss').read_text())


if __name__=='__main__':unittest.main()
