import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from contextlib import nullcontext
from startup import WindowsStartup, RUN_KEY, VALUE_NAME
from friendly_ui import Service
from distribution import desktop


class FakeRegistry:
    HKEY_CURRENT_USER=1;KEY_READ=2;KEY_SET_VALUE=4;KEY_WOW64_64KEY=8;REG_SZ=1
    def __init__(self):self.values={'AnotherApp':('leave alone',1)};self.writes=0;self.denied=False
    def OpenKey(self,hive,path,reserved,access):
        assert hive==self.HKEY_CURRENT_USER and path==RUN_KEY
        if self.denied:raise PermissionError('denied')
        return nullcontext('key')
    CreateKeyEx=OpenKey
    def QueryValueEx(self,key,name):
        if name not in self.values:raise FileNotFoundError(name)
        return self.values[name]
    def SetValueEx(self,key,name,reserved,kind,value):self.values[name]=(value,kind);self.writes+=1
    def DeleteValue(self,key,name):
        if name not in self.values:raise FileNotFoundError(name)
        del self.values[name];self.writes+=1


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.exe=self.base/'Radar.exe';self.exe.write_bytes(b'fixture')
        self.reg=FakeRegistry();self.startup=WindowsStartup(self.exe,self.reg)
    def tearDown(self):self.temp.cleanup()
    def test_default_off_and_read_does_not_enable(self):
        self.assertFalse(self.startup.state()['enabled']);self.assertEqual(self.reg.writes,0)
    def test_enable_quotes_path_and_uses_background(self):
        self.assertTrue(self.startup.configure({'enabled':True})['enabled'])
        self.assertEqual(self.reg.values[VALUE_NAME],('"'+str(self.exe)+'" --background',self.reg.REG_SZ))
    def test_disable_is_idempotent_and_preserves_other_apps(self):
        self.startup.configure({'enabled':True});self.startup.configure({'enabled':False});self.startup.configure({'enabled':False})
        self.assertEqual(self.reg.values,{'AnotherApp':('leave alone',1)})
    def test_state_reflects_external_removal(self):
        self.startup.configure({'enabled':True});del self.reg.values[VALUE_NAME]
        self.assertFalse(self.startup.state()['enabled'])
    def test_state_survives_restart_and_different_install_requires_choice(self):
        self.startup.configure({'enabled':True})
        self.assertTrue(WindowsStartup(self.exe,self.reg).state()['enabled'])
        self.assertFalse(WindowsStartup(self.base/'different/Radar.exe',self.reg).state()['enabled'])
    def test_denied_read_is_unknown_not_disabled(self):
        self.reg.denied=True;s=self.startup.state()
        self.assertTrue(s['error']);self.assertIsNone(s['enabled'])
        with self.assertRaises(ValueError):self.startup.configure({'enabled':True})
    def test_invalid_payload_and_missing_executable_do_not_write(self):
        for value in (None,'true',1,[]):
            with self.assertRaises(ValueError):self.startup.configure({'enabled':value})
        self.exe.unlink()
        with self.assertRaises(ValueError):self.startup.configure({'enabled':True})
        self.assertEqual(self.reg.writes,0)
    def test_service_does_not_accept_executable_from_browser(self):
        (self.base/'config.json').write_bytes(Path('config.example.json').read_bytes());(self.base/'references.json').write_text('[]')
        service=Service(self.base);service.startup=self.startup
        service.mutate('startup_settings',{'enabled':True,'executable':'evil.exe'})
        self.assertEqual(self.reg.values[VALUE_NAME][0],self.startup.command)
        service.job.update(busy=True,kind='software')
        with self.assertRaises(ValueError):service.mutate('startup_settings',{'enabled':False})
    def test_hidden_start_schedules_search_only_when_enabled(self):
        for enabled in (True,False):
            service=Mock(base=self.base,schedule={'enabled':enabled},next_run=9999)
            server=Mock(service=service)
            with patch('startup.WindowsStartup'),patch('updater.Updater'),patch.object(desktop.threading,'Thread'),patch.object(desktop.TrayCompanion,'spawn'),patch.object(desktop.time,'time',return_value=100):
                desktop.TrayCompanion(server,show=False)
            self.assertEqual(service.next_run,130 if enabled else 9999)
    def test_existing_hidden_instance_does_not_open_window(self):
        (self.base/'data').mkdir();(self.base/'data/sessao-interface.json').write_text(json.dumps({'url':'http://127.0.0.1:12345/','token':'test'}))
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        with patch.object(desktop.urllib.request,'urlopen',return_value=response),patch.object(desktop.json,'load',return_value={'base':str(self.base.resolve())}),patch.object(desktop.subprocess,'run') as show:
            desktop.open_existing(self.base,False);show.assert_not_called()
            desktop.open_existing(self.base,True);self.assertEqual(show.call_args.args[0][1],'--show')

    @unittest.skipUnless(os.name=='nt','Windows launcher')
    def test_native_launcher_only_background_switch(self):
        source=self.base/'Harness.cs';target=self.base/'Harness.exe'
        source.write_text(r'''using System;class Harness{static int Main(){
        var normal=Launcher.StartInfo(@"C:\Program Files\Radar",new string[0]);
        var hidden=Launcher.StartInfo(@"C:\Program Files\Radar",new[]{"--background"});
        if(normal.Arguments.Contains("--no-browser") || !hidden.Arguments.EndsWith(" --no-browser"))return 1;
        if(!hidden.CreateNoWindow || hidden.UseShellExecute || !hidden.FileName.EndsWith("pythonw.exe"))return 2;
        try{Launcher.StartInfo("C:\\Radar",new[]{"--background","evil"});return 3;}catch(ArgumentException){}
        Console.WriteLine("OK");return 0;}}''')
        compiler='C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        result=subprocess.run([compiler,'/nologo','/target:exe','/main:Harness','/reference:System.Windows.Forms.dll',
                              '/out:'+str(target),str(Path('distribution/Launcher.cs').resolve()),str(source)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        result=subprocess.run([str(target)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
