"""Authenticated web entry point; never exposes the desktop control API."""
import atexit
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask,request,g,jsonify,redirect,send_file,make_response
from werkzeug.exceptions import HTTPException
from web.accounts import Accounts,SESSION_SECONDS
from web.runtime import Runtime,SOURCE,ALLOWED_ACTIONS

WEB=Path(__file__).parent
COOKIE='radar_session'


def create_app(root=None,origin=None,start_scheduler=True):
    origin=(origin or os.environ.get('RADAR_WEB_ORIGIN','http://127.0.0.1:8080')).rstrip('/')
    parts=urlsplit(origin)
    if (parts.scheme not in ('http','https') or not parts.hostname or parts.path or parts.query or parts.fragment or parts.username
        or (parts.scheme=='http' and parts.hostname not in ('127.0.0.1','localhost'))):
        raise ValueError('Configure RADAR_WEB_ORIGIN com a URL HTTPS do site, ou HTTP somente para teste local.')
    secure=parts.scheme=='https'
    root=Path(root or os.environ.get('RADAR_WEB_DATA',SOURCE/'web-data')).resolve()
    app=Flask(__name__,static_folder=None)
    app.config.update(MAX_CONTENT_LENGTH=200_000,TRUSTED_HOSTS=[parts.hostname])
    accounts=Accounts(root);runtime=Runtime(root,accounts)
    app.extensions.update(accounts=accounts,radar=runtime)
    if start_scheduler:runtime.start()
    atexit.register(runtime.close)

    @app.before_request
    def access():
        if request.host!=parts.netloc:return jsonify(error='Endereço de acesso inválido.'),400
        if request.method not in ('GET','HEAD','POST'):return jsonify(error='Método não permitido.'),405
        if request.method=='POST':
            if request.headers.get('Origin') not in (None,origin) or request.headers.get('Sec-Fetch-Site')=='cross-site':
                return jsonify(error='Solicitação de outra página recusada.'),403
            if not request.is_json or request.headers.get('X-Radar-Web')!='1':
                return jsonify(error='Atualize a página e tente novamente.'),403
        g.account=accounts.session(request.cookies.get(COOKIE))
        public=request.path in ('/login','/login.js','/web.css','/style.css','/healthz','/auth/login','/auth/register')
        if not public and not g.account:
            if request.path=='/':return redirect('/login')
            return jsonify(error='Sua sessão terminou. Entre novamente.'),401
        if request.method=='POST' and g.account and request.path not in ('/auth/login','/auth/register'):
            if not secrets.compare_digest(request.headers.get('X-Radar-Token',''),g.account['csrf']):
                return jsonify(error='A página expirou. Atualize e tente novamente.'),403

    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
            'Referrer-Policy':'no-referrer','X-Frame-Options':'DENY',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'"})
        if secure:response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc,HTTPException):return jsonify(error='Solicitação inválida.'),exc.code
        if isinstance(exc,(ValueError,KeyError,TypeError)):return jsonify(error=str(exc)),400
        app.logger.exception('Falha na versão web')
        return jsonify(error='Não foi possível concluir. Tente novamente mais tarde.'),500

    def payload():
        data=request.get_json()
        if not isinstance(data,dict):raise ValueError('Confira os campos e tente novamente.')
        return data

    def signed_in(token):
        accounts.logout(request.cookies.get(COOKIE))
        response=jsonify(ok=True)
        response.set_cookie(COOKIE,token,max_age=SESSION_SECONDS,secure=secure,httponly=True,samesite='Lax',path='/')
        return response

    @app.get('/healthz')
    def health():return jsonify(ok=True)

    @app.get('/login')
    def login_page():return send_file(WEB/'login.html')

    @app.post('/auth/<action>')
    def auth(action):
        data=payload()
        if action in ('login','register'):
            # Fixed proxy configuration: no trust in client-supplied forwarded IP headers.
            if accounts.limited('ip:'+str(request.remote_addr),60,900):return jsonify(error='Muitas tentativas. Aguarde 15 minutos.'),429
            if action=='login':
                email=str(data.get('email','')).strip().lower()
                if len(email)>254:raise ValueError('Informe seu e-mail.')
                if accounts.limited('email:'+email,10,900):return jsonify(error='Muitas tentativas. Aguarde 15 minutos.'),429
                token=accounts.login(email,data.get('password'))
                if not token:return jsonify(error='E-mail ou senha incorretos, ou conta desativada.'),401
            else:
                uid=accounts.register(data.get('invite'),data.get('name'),data.get('password'))
                token=accounts.new_session(uid)
            return signed_in(token)
        if action=='password':
            if accounts.limited('password:'+g.account['id'],5,900):return jsonify(error='Aguarde 15 minutos para tentar novamente.'),429
            accounts.change_password(g.account['id'],data.get('current'),data.get('password'))
        elif action!='logout':return jsonify(error='Ação não encontrada.'),404
        accounts.logout(request.cookies.get(COOKIE));response=jsonify(ok=True)
        response.delete_cookie(COOKIE,path='/',secure=secure,httponly=True,samesite='Lax')
        return response

    @app.get('/auth/session')
    def session_info():return jsonify(name=g.account['name'],email=g.account['email'],csrf=g.account['csrf'])

    @app.get('/')
    def index():
        html=(WEB/'index.html').read_text(encoding='utf-8').replace('__RADAR_CSRF__',g.account['csrf'])
        return make_response(html)

    @app.get('/<asset>')
    def asset(asset):
        files={'ui.js':SOURCE/'ui/ui.js','style.css':SOURCE/'ui/style.css','web.js':WEB/'web.js','login.js':WEB/'login.js','web.css':WEB/'web.css'}
        if asset not in files:return jsonify(error='Página não encontrada.'),404
        return send_file(files[asset])

    @app.get('/api/state')
    def state():
        service=runtime.get(g.account['id'])
        with service.guard:result=service.state()
        result['web']={'name':g.account['name'],'email':g.account['email']}
        return jsonify(result)

    @app.get('/api/<kind>')
    def download(kind):
        files={'excel':('Radar-de-Leiloes.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
               'csv':('resultados.csv','text/csv; charset=utf-8'),'history':('alteracoes.csv','text/csv; charset=utf-8')}
        if kind not in files:return jsonify(error='Página não encontrada.'),404
        service=runtime.get(g.account['id']);name,mime=files[kind]
        with service.guard:
            if service.job['busy']:return jsonify(error='Aguarde a atualização terminar para baixar.'),409
            path=service.base/'exports'/name
            if not path.is_file():return jsonify(error='Clique em Atualizar planilha antes de baixar.'),404
            # Snapshot bytes while locked: a new export must not change a file mid-download.
            response=make_response(path.read_bytes())
        response.headers['Content-Type']=mime
        response.headers['Content-Disposition']='attachment; filename="'+name+'"'
        return response

    @app.post('/api/<action>')
    def mutate(action):
        if action not in ALLOWED_ACTIONS:return jsonify(error='Ação não disponível na web.'),404
        if accounts.limited('actions:'+g.account['id'],120,60):return jsonify(error='Aguarde um minuto antes de tentar novamente.'),429
        return jsonify(runtime.get(g.account['id']).mutate(action,payload()))

    return app


def main():
    from waitress import serve
    bind=os.environ.get('RADAR_WEB_BIND','127.0.0.1')
    if bind not in ('127.0.0.1','localhost','::1') and not os.environ.get('RADAR_WEB_ORIGIN','').startswith('https://'):
        raise ValueError('Para escutar na rede interna do proxy, configure primeiro RADAR_WEB_ORIGIN com HTTPS.')
    app=create_app()
    try:serve(app,host=bind,port=int(os.environ.get('PORT','8080')),
              threads=8,max_request_body_size=200_000,clear_untrusted_proxy_headers=True)
    finally:app.extensions['radar'].close()


if __name__=='__main__':main()
