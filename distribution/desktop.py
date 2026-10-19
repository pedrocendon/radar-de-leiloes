"""Entry point for the self-contained per-user Windows installation."""
import argparse
import ctypes
import json
import os
import shutil
import sys
import time
import traceback
import urllib.request
import subprocess
import threading
from pathlib import Path

APP=Path(__file__).resolve().parent

class TrayCompanion:
    def __init__(self,server,show=True):
        self.server=server
        server.service.notifications_supported=True
        from startup import WindowsStartup
        server.service.startup=WindowsStartup(APP.parent/'Radar.exe')
        # Resume an enabled search soon after sign-in, even on computers used less than 24 h/day.
        if not show and server.service.schedule.get('enabled'):
            server.service.next_run=time.time()+30
        from updater import Updater
        server.service.updater=Updater(server.service,APP.parent,server.shutdown)
        threading.Thread(target=server.service.updater.agenda,daemon=True).start()
        self.session=server.service.base/'data/sessao-interface.json'
        self.process=self.spawn(show)
        self.watcher=threading.Thread(target=self.watch,daemon=True)
        self.watcher.start()

    def spawn(self,show=False):
        return subprocess.Popen([str(APP.parent/'RadarTray.exe'),str(self.session),str(os.getpid()),'show' if show else 'hidden'],
                                creationflags=subprocess.CREATE_NO_WINDOW)

    def watch(self):
        while not self.server.service.closed.wait(3):
            if self.process.poll() is not None:
                try:self.process=self.spawn()
                except OSError:self.server.service.record_error()

    def close(self):
        self.watcher.join(timeout=4)
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.terminate()

def user_base():
    return Path(os.environ['LOCALAPPDATA'])/'RadarLeiloes'

def initialize(base):
    base.mkdir(parents=True,exist_ok=True)
    (base/'data').mkdir(exist_ok=True)
    for name in ('config.json','references.json'):
        destination=base/name
        if not destination.exists():shutil.copy2(APP/'defaults'/name,destination)
    (base/'ui').mkdir(exist_ok=True)
    for source in (APP/'ui').iterdir():
        if source.is_file():shutil.copy2(source,base/'ui'/source.name)
    os.environ['RADAR_PORTABLE_EXCEL']='1'

def open_existing(base,open_browser):
    for _ in range(60):
        try:
            session=json.loads((base/'data/sessao-interface.json').read_text(encoding='utf-8'))
            from friendly_ui import local_health
            health=local_health(session['url'],session['token'])
            if health.get('base')==str(base.resolve()):
                if open_browser:
                    subprocess.run([str(APP.parent/'RadarTray.exe'),'--show',str(base/'data/sessao-interface.json')],
                                   creationflags=subprocess.CREATE_NO_WINDOW,timeout=10,check=True)
                return
        except (OSError,ValueError,KeyError):time.sleep(.1)
    raise RuntimeError('O Radar ainda está iniciando. Aguarde alguns segundos e tente novamente.')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--data-dir',type=Path)
    args=parser.parse_args()
    args.no_browser=args.no_browser or os.environ.get('RADAR_NO_BROWSER')=='1'
    base=(args.data_dir or user_base()).resolve()
    mutex=None
    try:
        # Inno Setup detects this mutex and asks the user to close the program.
        if not args.self_test:
            import hashlib
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
            kernel.CreateMutexW.restype=ctypes.c_void_p
            name='Local\\RadarLeiloes.Desktop' if not args.data_dir else 'Local\\RadarLeiloes.Test.'+hashlib.sha256(str(base).encode()).hexdigest()[:16]
            mutex=kernel.CreateMutexW(None,False,name)
            if not mutex:raise ctypes.WinError(ctypes.get_last_error())
            if ctypes.get_last_error()==183:
                open_existing(base,not args.no_browser)
                return
        initialize(base)
        from engine import export
        from friendly_ui import launch,make_server
        if not (base/'exports/Radar-de-Leiloes.xlsx').exists() or args.self_test:
            export(base)
            result=json.loads((base/'exports/situacao-planilha.json').read_text(encoding='utf-8'))
            if result['situacao']!='atualizada':raise RuntimeError(result['mensagem'])
        if args.self_test:
            server=make_server(base)
            state=server.service.state();server.server_close()
            print(json.dumps({'ok':True,'python':sys.version.split()[0],'base':str(base),'listings':len(state['listings']),'excel':state['excel']['exists']},ensure_ascii=False))
        else:launch(base,open_browser=False,background=lambda server:TrayCompanion(server,show=not args.no_browser))
    except Exception:
        (base/'data').mkdir(parents=True,exist_ok=True)
        log=base/'data/erro-ao-abrir.log';log.write_text(traceback.format_exc(),encoding='utf-8')
        if args.self_test:raise
        ctypes.windll.user32.MessageBoxW(None,'Não foi possível abrir o Radar. Tente novamente.\n\nDetalhes para o suporte:\n'+str(log),'Radar de Leilões',0x10)
    finally:
        if mutex:
            kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(mutex)

if __name__=='__main__':main()
