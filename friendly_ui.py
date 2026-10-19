"""Local browser interface. Uses Python's standard library; no desktop toolkit."""
import argparse
import json
import math
import os
import re
import secrets
import threading
import time
import traceback
import urllib.request
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from collectors import now, canonical, browser_text, norm, NoRedirect
from engine import Store, load, save, export, evaluate, similarity, validate_config

STATUS = {'ok':'Leitura concluída','parcial':'Faltam informações','assistida':'Conferido pelo navegador',
          'bloqueado':'Site bloqueou a consulta','falha_rede':'Não foi possível conectar',
          'redirecionado':'Anúncio mudou de endereço','navegador_necessario':'Precisa de consulta manual',
          'referencia_planilha':'Ainda não conferido no site','erro_interpretacao':'Não foi possível ler a página',
          'desativada':'Não incluído na busca'}
HINTS = {'ok':'Confira as condições e a disponibilidade no anúncio antes de decidir.',
         'parcial':'Abra o anúncio para conferir os campos que o site não informou.',
         'assistida':'Dados copiados do navegador. Este site precisa de nova conferência manual.',
         'bloqueado':'O site impediu a consulta automática. Abra o anúncio para conferir.',
         'falha_rede':'Verifique a conexão e tente uma nova busca. Os dados anteriores foram mantidos.',
         'redirecionado':'O link original redireciona para outra página. Confira no site.',
         'navegador_necessario':'Em Sites consultados, use Conferir anúncio para colar o texto da página.',
         'referencia_planilha':'Estes são os dados da sua planilha original.',
         'erro_interpretacao':'A página pode ter mudado. Abra o anúncio e confira os dados.'}


def br_number(value, label):
    if value is None or str(value).strip()=='': return None
    if isinstance(value, (int,float)) and not isinstance(value,bool): result=float(value)
    else:
        value=str(value).strip().replace('R$','').replace('%','').replace(' ','')
        if not re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?',value):
            raise ValueError(f'{label}: digite como 500.000 ou 500.000,00.')
        result=float(value.replace('.','').replace(',','.'))
    if not math.isfinite(result) or result<0: raise ValueError(f'{label}: informe um valor igual ou maior que zero.')
    return result


def friendly_filters(raw):
    result={}
    for key in ('cities','states','types'):
        value=raw.get(key,[])
        if isinstance(value,str):value=[x.strip() for x in re.split('[,;\n]',value) if x.strip()]
        if not isinstance(value,list) or not all(isinstance(x,str) for x in value):raise ValueError('Confira as cidades e os tipos selecionados.')
        result[key]=list(dict.fromkeys(value))
    result['states']=[v.upper() for v in result['states']]
    for key,label in [('min_price','Preço mínimo'),('max_price','Preço máximo'),('min_discount','Desconto mínimo')]:
        result[key]=br_number(raw.get(key),label)
    for key,label in [('date_from','Data inicial'),('date_to','Data final')]:
        value=raw.get(key) or None
        if value:
            try:datetime.strptime(value,'%Y-%m-%d')
            except (ValueError,TypeError):raise ValueError(f'{label}: escolha uma data válida no calendário.')
        result[key]=value
    result['show_pending']=bool(raw.get('show_pending',True))
    if result['min_discount'] is not None and result['min_discount']>100:raise ValueError('O desconto precisa estar entre 0% e 100%.')
    if result['min_price'] is not None and result['max_price'] is not None and result['min_price']>result['max_price']:raise ValueError('O preço máximo precisa ser maior ou igual ao mínimo.')
    if result['date_from'] and result['date_to'] and result['date_from']>result['date_to']:raise ValueError('A data final precisa ser igual ou posterior à inicial.')
    return result


def has_filters(filters):
    return any(v not in (None,'',[]) for k,v in filters.items() if k!='show_pending')


def listing_view(row, config):
    d=row['data'];match,_=evaluate(d,config['filters']);score,reasons=similarity(d,config['profile'])
    stages=sorted([dict(s,matches=has_filters(config['filters']) and evaluate(dict(d,stages=[s]),config['filters'])[0]=='corresponde') for s in d.get('stages',[])],key=lambda s:(s.get('date') or '9999',s.get('number') or 0))
    next_stage=next((s for s in stages if s.get('date') and s['date'][:10]>=now()[:10]),None)
    return dict(id=row['id'],favorite=bool(row.get('favorited_at')),favorited_at=row.get('favorited_at'),title=d.get('title') or 'Anúncio ainda sem informações',city=d.get('city'),uf=d.get('uf'),
                source=row['source'],status=row['collection_status'],status_label=STATUS.get(row['collection_status'],'Consulta não concluída'),
                hint=HINTS.get(row['collection_status'],'Abra o anúncio para conferir.'),match=match,
                match_label=({'corresponde':'Uma etapa atende à sua busca','pendente':'Faltam dados para comparar','fora':'Fora dos filtros'}[match] if has_filters(config['filters']) else 'Sem filtros de busca'),
                reasons=reasons,score=score,next_stage=next_stage,stages=stages,url=row['url'],
                address=d.get('address'),type=d.get('type'),occupancy=d.get('occupancy'),valuation=d.get('valuation'),
                personal_ceiling=d.get('personal_ceiling'),auctioneer=d.get('auctioneer'),published_status=d.get('status'),
                areas=d.get('areas',[]),notices=d.get('notice_links',[]),warnings=d.get('warnings',[]),
                last_attempt=row['last_attempt'],last_success=row['last_success'],checked_at=d.get('checked_at'),origin=d.get('origin'))


class Service:
    def __init__(self,base):
        self.base=Path(base).resolve();self.store=Store(self.base/'data/monitor.sqlite')
        config=load(self.base/'config.json')
        if not self.store.rows():
            for r in load(self.base/'references.json'):self.store.put(r['source'],r['url'],r,'referencia_planilha','Ainda não confirmado no site')
        self.guard=threading.RLock();self.job={'busy':False,'message':'Pronto para consultar.','started':None,'kind':None,'error':False}
        pref=self.base/'data/preferencias.json'
        self.schedule=load(pref) if pref.exists() else {'enabled':False,'hours':24}
        self.next_run=time.time()+self.schedule['hours']*3600 if self.schedule.get('enabled') else None
        self.closed=threading.Event()
        self.updater=None
        self.startup=None
        from notifications import Notifications
        self.notifications=Notifications(self.store)
        self.notifications.begin(config)
        self.notifications_supported=False

    def startup_state(self):
        return self.startup.state() if self.startup else dict(supported=False,enabled=False,error=False,
            message='A inicialização com o Windows está disponível na versão instalada do Radar.')

    def update_state(self):
        from version import VERSION
        return self.updater.state() if self.updater else dict(supported=False,current_version=VERSION,
            status='unsupported',message='A atualização pelo programa está disponível na versão instalada para Windows.')

    def note(self,message):
        with self.guard:self.job['message']=message

    def record_error(self):
        with (self.base/'data/ajuda-tecnica.log').open('a',encoding='utf-8') as f:
            f.write(now()+'\n'+traceback.format_exc()+'\n')

    def start(self,kind,task):
        with self.guard:
            if self.job['busy']:raise ValueError('Uma atualização já está em andamento. Aguarde a conclusão.')
            self.job={'busy':True,'message':'Buscando novidades nos sites…' if kind=='search' else 'Preparando sua planilha…','started':time.time(),'kind':kind,'error':False}
        def worker():
            try:
                task()
                excel=self.excel_state()
                prefix='Busca concluída. Confira os avisos dos sites.' if kind=='search' else 'Dados salvos.'
                self.note(prefix+' '+excel['message'])
            except Exception:
                self.record_error()
                with self.guard:self.job['error']=True
                self.note('Não foi possível concluir. Seus dados anteriores foram mantidos. Tente novamente ou consulte a seção Ajuda.')
            finally:
                with self.guard:
                    self.job['busy']=False
                    if self.schedule['enabled']:self.next_run=time.time()+self.schedule['hours']*3600
        threading.Thread(target=worker,daemon=True).start()

    def excel_state(self):
        from xlsx_export import REPORT_NAME
        p=self.base/'exports/situacao-planilha.json'
        status=load(p) if p.exists() else {}
        message='A planilha está pronta.' if status.get('situacao')=='atualizada' else 'A planilha precisa ser atualizada. Feche o Excel e clique em Atualizar planilha.'
        if 'indisponível' in status.get('mensagem',''):message='O componente que gera o Excel não está disponível. Os anúncios continuam salvos. Consulte Ajuda.'
        return {'exists':(self.base/'exports'/REPORT_NAME).exists(),'updated':status.get('ultima_atualizacao'),'pending':status.get('situacao')!='atualizada','message':message}

    def state(self):
        config=load(self.base/'config.json');rows=self.store.rows();runs=self.store.runs()
        listing=sorted([listing_view(r,config) for r in rows],key=lambda r:(-r['score'],r['title']))
        sources=[]
        for s in config['sources']:
            run=next((r for r in runs if r['source']==s['id']),{})
            mode={'browser':'Precisa da sua conferência','blocked':'Consulta automática indisponível'}.get(s['adapter'],'Busca automática')
            sources.append(dict(id=s['id'],name=s['name'],root=s['root'],enabled=s.get('enabled',True),mode=mode,adapter=s['adapter'],
                                status=STATUS.get(run.get('status'),'Ainda não consultado'),at=run.get('at'),
                                count=sum(r['source']==s['id'] for r in rows),note=s['note']))
        with self.guard:job=dict(self.job);schedule=dict(self.schedule,next_run=self.next_run)
        cities={norm(c):c for c in config['profile']['cities']}
        for r in listing:
            if r['city']:cities.setdefault(norm(r['city']),r['city'])
        return dict(today=now()[:10],listings=listing,sources=sources,filters=config['filters'],suggested=config['suggested_filters'],
                    cities=sorted(cities.values()),
                    job=job,schedule=schedule,notifications=self.notifications.state(self.notifications_supported),startup=self.startup_state(),updates=self.update_state(),excel=self.excel_state(),last_attempt=max((r['last_attempt'] or '' for r in rows),default=None))

    def mutate(self,action,payload):
        # Serialize starts/settings/imports. Workers read their configuration after save.
        with self.guard:
            if action=='notifications_claim':
                return {'notice':self.notifications.claim(load(self.base/'config.json')) if self.notifications_supported and not self.job['busy'] else None}
            if self.job['busy'] and self.job['kind']=='software':raise ValueError('Aguarde a atualização do Radar terminar antes de alterar os dados.')
            if self.job['busy'] and action not in ('open_excel','favorite'):raise ValueError('A atualização está em andamento. Aguarde antes de alterar as opções.')
            if action in ('notifications_settings','notifications_test','favorite_notifications_settings'):
                if not self.notifications_supported:raise ValueError('Use a versão instalada do Radar para receber avisos no Windows.')
                if action=='notifications_settings':self.notifications.configure(payload.get('enabled'))
                elif action=='favorite_notifications_settings':self.notifications.favorites.configure(payload)
                else:self.notifications.test()
            elif action=='startup_settings':
                if not self.startup:raise ValueError('Use a versão instalada do Radar para configurar a inicialização com o Windows.')
                self.startup.configure(payload)
            elif action in ('update_check','update_install','update_settings'):
                if not self.updater:raise ValueError('Use a versão instalada do Radar para atualizar pelo programa.')
                if action=='update_check':self.updater.check()
                elif action=='update_install':self.updater.install()
                else:self.updater.configure(payload)
            elif action=='favorite':
                listing_id=payload.get('id');enabled=payload.get('favorite')
                if not isinstance(listing_id,str) or not listing_id or type(enabled) is not bool:
                    raise ValueError('Escolha um anúncio e informe se deseja favoritar ou remover dos favoritos.')
                at=self.store.set_favorite(listing_id,enabled)
                self.notifications.favorites.sync()
                return {'ok':True,'id':listing_id,'favorite':enabled,'favorited_at':at}
            elif action=='search':
                if not any(s.get('enabled',True) for s in load(self.base/'config.json')['sources']):raise ValueError('Selecione pelo menos um site em Sites consultados antes de buscar.')
                from app import run_locked
                self.start('search',lambda:run_locked(self.base,self.note))
            elif action=='export':self.start('export',lambda:export(self.base))
            elif action=='filters':
                config=load(self.base/'config.json');config['filters']=friendly_filters(payload)
                validate_config(config);save(self.base/'config.json',config)
                self.notifications.begin(config)
            elif action=='sources':
                config=load(self.base/'config.json');selected=payload.get('enabled')
                if not isinstance(selected,list) or any(x not in [s['id'] for s in config['sources']] for x in selected):raise ValueError('Escolha os sites disponíveis na lista.')
                for s in config['sources']:s['enabled']=s['id'] in selected
                save(self.base/'config.json',config)
                self.notifications.begin(config)
            elif action=='schedule':
                hours=payload.get('hours',24)
                if hours not in (1,6,12,24):raise ValueError('Escolha um dos intervalos da lista.')
                self.schedule={'enabled':payload.get('enabled') is True,'hours':hours}
                self.next_run=time.time()+hours*3600 if self.schedule['enabled'] else None
                save(self.base/'data/preferencias.json',self.schedule)
            elif action in ('watch','import'):
                config=load(self.base/'config.json');url=canonical(str(payload.get('url','')))
                source=next((s for s in config['sources'] if urlsplit(url).hostname==urlsplit(s['root']).hostname),None)
                if not source:raise ValueError('Use um anúncio de um dos sites já cadastrados. Novos sites precisam de um leitor compatível.')
                if not re.search(source['detail_pattern'],urlsplit(url).path):raise ValueError('Cole o endereço completo de um imóvel, em vez da página inicial do site.')
                if action=='watch':
                    if not source.get('enabled',True):raise ValueError('Marque este site em Sites consultados e salve antes de adicionar o link.')
                    if source['adapter'] in ('browser','blocked'):raise ValueError('Este site não tem busca automática disponível. Use Conferir anúncio quando disponível.')
                    source.setdefault('watch_urls',[])
                    if url not in source['watch_urls']:source['watch_urls'].append(url)
                    save(self.base/'config.json',config)
                else:
                    if source['adapter']!='browser':raise ValueError('Esta conferência é para Top e Krobel. Nos outros sites, use Buscar novidades.')
                    content=str(payload.get('text','')).strip()
                    if len(content)<80:raise ValueError('Copie o texto completo da página do imóvel e cole no campo abaixo.')
                    d=browser_text(content,url)
                    if not d.get('stages'):raise ValueError('Não encontrei as etapas do leilão nesse texto. Confira se copiou a página completa do imóvel.')
                    d.update(origin='consulta_assistida',checked_at=now())
                    self.store.put(source['id'],url,d,'assistida','Texto copiado do navegador pelo usuário.',config.get('property_overrides'))
                    self.start('export',lambda:export(self.base))
            elif action=='open_excel':
                from xlsx_export import REPORT_NAME
                p=self.base/'exports'/REPORT_NAME
                if not p.exists():raise ValueError('Clique em Atualizar planilha primeiro. Depois você poderá abri-la.')
                try:os.startfile(str(p))
                except OSError:raise ValueError('Não foi possível abrir o Excel. Use Baixar planilha e abra com seu aplicativo de planilhas.')
            else:raise ValueError('Ação desconhecida. Atualize a página e tente novamente.')
        return {'ok':True}

    def agenda(self):
        next_reminder=0
        while not self.closed.wait(15):
            with self.guard:
                if not self.job['busy'] and time.time()>=next_reminder:
                    try:self.notifications.favorites.capture(load(self.base/'config.json'),dates_only=True)
                    except Exception:self.record_error()
                    next_reminder=time.time()+60
                if self.next_run and time.time()>=self.next_run and not self.job['busy']:
                    self.mutate('search',{})


def make_server(base,port=0):
    service=Service(base);token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,status,body,content_type='application/json; charset=utf-8',extra=None):
            if isinstance(body,(dict,list)):body=json.dumps(body,ensure_ascii=False).encode('utf-8')
            if isinstance(body,str):body=body.encode('utf-8')
            self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            for k,v in (extra or {}).items():self.send_header(k,v)
            self.end_headers();self.wfile.write(body)
        def allowed(self,auth=True):
            expected='127.0.0.1:'+str(self.server.server_port)
            if self.headers.get('Host')!=expected:return False
            if self.headers.get('Origin') not in (None,'http://'+expected):return False
            return not auth or secrets.compare_digest(self.headers.get('X-Radar-Token',''),token)
        def do_GET(self):
            route=urlsplit(self.path).path
            if not self.allowed(route.startswith('/api/')):return self.respond(403,{'error':'Abra o programa novamente pelo atalho para recuperar o acesso.'})
            try:
                if route=='/api/state':return self.respond(200,service.state())
                if route=='/api/background':
                    with service.guard:
                        return self.respond(200,dict(job=dict(service.job),schedule=dict(service.schedule,next_run=service.next_run),updates=service.update_state(),notifications_pending=service.notifications.pending()))
                if route=='/api/health':return self.respond(200,{'ok':True,'base':str(service.base)})
                if route=='/api/excel':
                    from xlsx_export import REPORT_NAME
                    p=service.base/'exports'/REPORT_NAME
                    if not p.exists():return self.respond(404,{'error':'Atualize a planilha antes de baixar.'})
                    return self.respond(200,p.read_bytes(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',{'Content-Disposition':'attachment; filename="Radar-de-Leiloes.xlsx"'})
                assets={'/':('index.html','text/html; charset=utf-8'),'/ui.js':('ui.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
                if route not in assets:return self.respond(404,{'error':'Página não encontrada.'})
                name,mime=assets[route];return self.respond(200,(service.base/'ui'/name).read_bytes(),mime)
            except Exception:
                service.record_error();return self.respond(500,{'error':'Não foi possível carregar os dados. Reabra o programa ou consulte Ajuda.'})
        def do_POST(self):
            if not self.allowed():return self.respond(403,{'error':'Abra o programa novamente pelo atalho.'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length<0 or length>1_000_000:return self.respond(413,{'error':'O texto é muito grande. Copie apenas a página do anúncio.'})
                payload=json.loads(self.rfile.read(length) or b'{}')
                if not isinstance(payload,dict):raise ValueError('Confira os campos e tente novamente.')
                action=urlsplit(self.path).path.removeprefix('/api/')
                if action=='close':
                    with service.guard:
                        if service.job['busy']:raise ValueError('Aguarde a atualização terminar antes de encerrar.')
                        service.closed.set()
                    self.respond(200,{'ok':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
                return self.respond(200,service.mutate(action,payload))
            except (ValueError,KeyError,TypeError) as exc:return self.respond(400,{'error':str(exc)})
            except Exception:
                service.record_error();return self.respond(500,{'error':'Não foi possível concluir a ação. Seus dados estão salvos. Consulte Ajuda.'})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.service=service;server.token=token
    return server


def local_health(url,token):
    """Never forward a session token through a proxy or an HTTP redirect."""
    if not isinstance(url,str) or not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}/',url):
        raise ValueError('Sessão local inválida.')
    if not 1<=urlsplit(url).port<=65535:
        raise ValueError('Porta da sessão inválida.')
    if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}',token):
        raise ValueError('Chave da sessão inválida.')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect)
    request=urllib.request.Request(url+'api/health',headers={'X-Radar-Token':token})
    with opener.open(request,timeout=1) as response:raw=response.read(16385)
    if len(raw)>16384:raise ValueError('Resposta local muito grande.')
    result=json.loads(raw)
    if not isinstance(result,dict):raise ValueError('Resposta local inválida.')
    return result


def launch(base,open_browser=True,port=0,background=None):
    base=Path(base).resolve();session=base/'data/sessao-interface.json'
    if session.exists():
        try:
            previous=load(session);url=previous['url']
            existing=local_health(url,previous['token'])
            if existing.get('base')==str(base):
                if open_browser:webbrowser.open(url+'#'+previous['token'])
                return
        except (OSError,ValueError,KeyError):pass
    server=make_server(base,port);url=f'http://127.0.0.1:{server.server_port}/'
    save(session,{'url':url,'token':server.token})
    threading.Thread(target=server.service.agenda,daemon=True).start()
    companion=None
    try:
        if background:companion=background(server)
        if open_browser:webbrowser.open(url+'#'+server.token)
        server.serve_forever(poll_interval=0.5)
    finally:
        server.service.closed.set();server.server_close()
        if session.exists() and load(session).get('token')==server.token:session.unlink()
        if companion:companion.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--no-browser',action='store_true');p.add_argument('--port',type=int,default=0)
    args=p.parse_args();launch(Path(__file__).parent,not args.no_browser,args.port)
