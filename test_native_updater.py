"""Windows helper tests. Optional real Inno installer: RADAR_TEST_INSTALLER (ValidationBuild only)."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from version import VERSION

CSC=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
HARNESS=r'''
using System;using System.IO;using System.Diagnostics;using System.Threading;
class Harness {
 static int Main(string[] a) {
  if(a[0]=="parent"){Thread.Sleep(1500);return 0;}
  using(var parent=Process.Start(new ProcessStartInfo(System.Reflection.Assembly.GetExecutingAssembly().Location,"parent"){UseShellExecute=false,CreateNoWindow=true})) {
   var watch=Stopwatch.StartNew();
   try {
    RadarUpdate.Execute(new string[]{parent.Id.ToString(),a[0],a[1],a[2],a[3],a[4]},s=>{},
     executable=>File.WriteAllText(Path.Combine(a[2],"restart-requested.txt"),executable));
    if(!parent.HasExited || watch.ElapsedMilliseconds<1000)throw new Exception("Did not wait for parent");
    Console.WriteLine("UPDATE_OK");return 0;
   } catch(Exception e){Console.WriteLine(e.Message);return 1;}
   finally{parent.WaitForExit();}
  }
 }
}
'''

@unittest.skipUnless(os.name=='nt' and CSC.exists(),'Windows .NET compiler required')
class NativeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.install=self.root/'program';self.install.mkdir()
        self.build('Radar.exe',0,self.install)
        (self.root/'Harness.cs').write_text(HARNESS)
        subprocess.run([str(CSC),'/nologo','/target:exe','/main:Harness','/out:'+str(self.root/'Harness.exe'),
                        '/reference:System.Windows.Forms.dll','/reference:System.Web.Extensions.dll',
                        str(Path('distribution/Updater.cs').resolve()),str(self.root/'Harness.cs')],check=True,capture_output=True)

    def tearDown(self):
        uninstaller=self.install/'unins000.exe'
        if uninstaller.exists():
            subprocess.run([str(uninstaller),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],timeout=90,check=True)
        self.temp.cleanup()

    def build(self,name,exitcode,folder=None):
        folder=folder or self.root
        src=folder/(name+'.cs')
        src.write_text('using System.Reflection;[assembly:AssemblyVersion("'+VERSION+'.0")]class Stub{static int Main(){return '+str(exitcode)+';}}')
        target=folder/name
        subprocess.run([str(CSC),'/nologo','/target:exe','/out:'+str(target),str(src)],check=True,capture_output=True)
        return target

    def execute(self,installer,digest=None,version=VERSION):
        digest=digest or hashlib.sha256(installer.read_bytes()).hexdigest()
        return subprocess.run([str(self.root/'Harness.exe'),str(installer),digest,str(self.install),version,
                               str(self.root/'resultado.json')],capture_output=True,text=True,timeout=180)

    def test_helper_success_waits_for_parent_and_requests_restart(self):
        setup=self.build('instalador.exe',0)
        result=self.execute(setup)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue((self.install/'restart-requested.txt').exists())
        self.assertFalse(setup.exists())
        self.assertTrue(json.loads((self.root/'resultado.json').read_text(encoding='utf-8-sig'))['success'])

    def test_helper_rejects_modified_installer_before_shutdown(self):
        result=self.execute(self.build('instalador.exe',0),'0'*64)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.root/'pronto.txt').exists())
        self.assertFalse((self.install/'restart-requested.txt').exists())

    def test_helper_rejects_wrong_binary_version(self):
        result=self.execute(self.build('instalador.exe',0),version='0.9.0')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.root/'pronto.txt').exists())

    def test_installer_failure_is_reported_and_previous_app_reopened(self):
        result=self.execute(self.build('instalador.exe',17))
        self.assertNotEqual(result.returncode,0)
        self.assertTrue((self.install/'restart-requested.txt').exists())
        self.assertFalse(json.loads((self.root/'resultado.json').read_text(encoding='utf-8-sig'))['success'])

    @unittest.skipUnless(os.environ.get('RADAR_TEST_INSTALLER'),'Optional isolated Inno installation')
    def test_real_validation_installer(self):
        # Never use a production AppId here: use /DValidationBuild when compiling.
        setup=self.root/'instalador.exe';shutil.copy2(os.environ['RADAR_TEST_INSTALLER'],setup)
        data=self.root/'user-data';data.mkdir();(data/'favorite-marker.txt').write_text('keep')
        from engine import Store
        saved=Store(data/'data/monitor.sqlite')
        saved.put('mega','https://example.test/preserved',dict(title='Favorito preservado',origin='site',stages=[]))
        saved.set_favorite(saved.rows()[0]['id'],True)
        result=self.execute(setup)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((data/'favorite-marker.txt').read_text(),'keep')
        check=subprocess.run([str(self.install/'runtime/python.exe'),'-B',str(self.install/'app/desktop.py'),
                              '--self-test','--data-dir',str(data)],capture_output=True,text=True,timeout=60)
        self.assertEqual(check.returncode,0,check.stdout+check.stderr)
        self.assertTrue(json.loads(check.stdout)['excel'])
        self.assertEqual(json.loads(check.stdout)['listings'],1)
        self.assertTrue(Store(data/'data/monitor.sqlite').rows()[0]['favorited_at'])
        runtime=subprocess.run([str(self.install/'runtime/python.exe'),'-c','import sqlite3;print(sqlite3.sqlite_version)'],capture_output=True,text=True,check=True)
        self.assertEqual(runtime.stdout.strip(),'3.54.1')

if __name__=='__main__':unittest.main()
