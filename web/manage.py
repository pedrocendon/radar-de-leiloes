"""Server administrator commands. Passwords are read without terminal echo."""
import argparse
import getpass
import os
from pathlib import Path
from web.accounts import Accounts


def main():
    parser=argparse.ArgumentParser(description='Gerenciar contas do Radar web')
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('list',help='Listar contas')
    for action in ('invite','disable','enable','password'):
        command=sub.add_parser(action);command.add_argument('email')
    args=parser.parse_args()
    root=Path(os.environ.get('RADAR_WEB_DATA',Path(__file__).resolve().parent.parent/'web-data'))
    accounts=Accounts(root)
    try:
        if args.action=='invite':
            token=accounts.invite(args.email)
            origin=os.environ.get('RADAR_WEB_ORIGIN','http://127.0.0.1:8080').rstrip('/')
            print('Convite pessoal: válido por 24 horas, utilizável uma única vez. Compartilhe somente com o destinatário.')
            print(origin+'/login#convite='+token)
        elif args.action=='list':
            for user in accounts.users():print(user['email']+' | '+user['name']+' | '+('ativa' if user['enabled'] else 'desativada'))
        else:
            user=next((u for u in accounts.users() if u['email']==args.email.strip().lower()),None)
            if not user:raise ValueError('Conta não encontrada.')
            if args.action=='password':
                password=getpass.getpass('Nova senha (pelo menos 12 caracteres): ')
                if password!=getpass.getpass('Repita a senha: '):raise ValueError('As senhas não conferem.')
                accounts.reset_password(user['id'],password)
            else:accounts.set_enabled(user['id'],args.action=='enable')
            print('Conta atualizada. As sessões anteriores foram encerradas.')
    except ValueError as exc:parser.exit(1,str(exc)+'\n')


if __name__=='__main__':main()
