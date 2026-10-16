import argparse,os
from pathlib import Path
from engine import Store,load,run,export
from collectors import canonical,now,browser_text
BASE=Path(__file__).resolve().parent

def run_locked(base,notify=print):
    # OS-released lock survives crashes safely; no stale lockfile rejection.
    lock=Path(base)/'data/consulta.lock';lock.parent.mkdir(exist_ok=True)
    with lock.open('a+b') as f:
        f.seek(0);f.write(b'0');f.flush();f.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise RuntimeError('Outra consulta já está em execução.')
        try:return run(base,notify)
        finally:
            if os.name=='nt':f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(f,fcntl.LOCK_UN)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--once',action='store_true');p.add_argument('--export',action='store_true');p.add_argument('--smoke',action='store_true');p.add_argument('--import-text');p.add_argument('--url');args=p.parse_args()
    if args.once:run_locked(BASE)
    elif args.export:
        from xlsx_export import status_message
        print(export(BASE));print(status_message(BASE))
    elif args.import_text:
        from urllib.parse import urlsplit
        if not args.url:p.error('--import-text exige --url')
        u=canonical(args.url);c=load(BASE/'config.json');source=next((s for s in c['sources'] if s['adapter']=='browser' and urlsplit(s['root']).hostname==urlsplit(u).hostname),None)
        if not source:p.error('Importação assistida disponível somente para Top e Krobel cadastrados.')
        d=browser_text(Path(args.import_text).read_text(encoding='utf-8-sig'),u);d.update(origin='consulta_assistida',checked_at=now());Store(BASE/'data/monitor.sqlite').put(source['id'],u,d,'assistida','Texto fornecido pelo usuário; horário da importação.',c.get('property_overrides'));export(BASE);print('Texto importado e resultados exportados.')
    else:
        from friendly_ui import launch,make_server
        if args.smoke:
            server=make_server(BASE);print('Interface pronta.');server.server_close()
        else:launch(BASE)
