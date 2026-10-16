"""Prepare an empty local profile and run the development interface."""
import argparse,json,os,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def prepare():
    if not (ROOT/'config.json').exists():shutil.copy2(ROOT/'config.example.json',ROOT/'config.json')
    if not (ROOT/'references.json').exists():(ROOT/'references.json').write_text('[]\n',encoding='utf-8')
    (ROOT/'data').mkdir(exist_ok=True)

def main():
    p=argparse.ArgumentParser(description='Radar de Leilões — ambiente de desenvolvimento')
    modes=p.add_mutually_exclusive_group()
    modes.add_argument('--prepare',action='store_true',help='Criar configuração vazia sem abrir o programa')
    modes.add_argument('--once',action='store_true',help='Executar uma consulta')
    modes.add_argument('--export',action='store_true',help='Exportar os dados locais')
    p.add_argument('--no-browser',action='store_true')
    args=p.parse_args();prepare();os.environ['RADAR_PORTABLE_EXCEL']='1'
    if args.prepare:return
    from engine import export
    if args.once:
        from app import run_locked
        run_locked(ROOT)
    elif args.export:export(ROOT)
    else:
        from friendly_ui import launch
        if not (ROOT/'exports/Radar-de-Leiloes.xlsx').exists():export(ROOT)
        launch(ROOT,open_browser=not args.no_browser)

if __name__=='__main__':main()
