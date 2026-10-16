"""One process, one bounded work queue and an isolated data directory per account."""
import os
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit
from engine import load,save,run
from friendly_ui import Service
from web.network import PublicClient,validate_url

SOURCE=Path(__file__).resolve().parent.parent
ALLOWED_ACTIONS={'search','export','filters','sources','schedule','favorite','watch','import',
                 'notifications_settings','favorite_notifications_settings'}


class WebService(Service):
    def __init__(self,base,manager,uid):
        self.manager=manager;self.uid=uid
        super().__init__(base)
        self.notifications_supported=True
        saved=load(self.base/'data/web-runtime.json') if (self.base/'data/web-runtime.json').exists() else {}
        self.last_search=saved.get('last_search',0)
        if self.schedule['enabled']:self.next_run=saved.get('next_run') or self.next_run

    def persist(self):
        save(self.base/'data/web-runtime.json',dict(next_run=self.next_run,last_search=self.last_search))

    def excel_state(self):
        result=super().excel_state()
        if result['pending']:result['message']='Clique em Atualizar planilha para preparar o arquivo com seus dados salvos.'
        return result

    def start(self,kind,task):
        with self.guard:
            if self.job['busy']:raise ValueError('Há uma tarefa em andamento. Aguarde a conclusão.')
            self.job=dict(busy=True,message='Na fila de atualização. Você pode continuar navegando.',started=time.time(),kind=kind,error=False)
        def worker():
            try:
                if not self.manager.enabled(self.uid):return
                task()
                self.note('Busca concluída. Confira a situação de cada site.' if kind=='search' else 'Planilha atualizada. Você já pode baixar o arquivo.')
                if self.excel_state()['pending']:self.note('Dados salvos. A planilha não foi gerada; tente Atualizar planilha.')
            except Exception:
                self.record_error()
                with self.guard:self.job['error']=True
                self.note('Não foi possível concluir. Os dados anteriores foram mantidos. Tente novamente mais tarde.')
            finally:
                with self.guard:
                    self.job['busy']=False
                    self.next_run=time.time()+self.schedule['hours']*3600 if self.schedule['enabled'] else None
                    self.persist()
        self.manager.pool.submit(worker)

    def mutate(self,action,payload):
        if action not in ALLOWED_ACTIONS:raise ValueError('Esta ação não está disponível na versão web.')
        with self.guard:
            if action=='search':
                if self.job['busy']:raise ValueError('Aguarde a busca atual terminar.')
                if time.time()-self.last_search<300:raise ValueError('Aguarde cinco minutos entre buscas para respeitar os sites consultados.')
                config=load(self.base/'config.json')
                if not any(s.get('enabled',True) for s in config['sources']):raise ValueError('Selecione pelo menos um site em Sites consultados.')
                if len(self.store.rows())>=1000:raise ValueError('O limite inicial de 1.000 anúncios desta conta foi atingido. Fale com o responsável pelo Radar.')
                self.last_search=time.time();self.persist()
                self.start('search',lambda:run(self.base,self.note,client=PublicClient(self.manager.hosts)))
                return {'ok':True}
            if action in ('watch','import'):
                validate_url(str(payload.get('url','')),self.manager.hosts)
                config=load(self.base/'config.json')
                if action=='watch' and sum(len(s.get('watch_urls',[])) for s in config['sources'])>=100:
                    raise ValueError('O limite de 100 links acompanhados foi atingido.')
                if action=='import' and len(self.store.rows())>=1000:raise ValueError('O limite de anúncios foi atingido.')
            result=super().mutate(action,payload)
            if action=='filters':
                config=load(self.base/'config.json')
                config['profile']={'kind':'web','cities':config['filters']['cities'],'types':config['filters']['types']}
                save(self.base/'config.json',config)
            if action=='schedule':self.persist()
            return result


class Runtime:
    def __init__(self,root,accounts):
        self.root=Path(root);self.accounts=accounts;self.guard=threading.RLock()
        self.services={};self.closed=threading.Event();self.thread=None
        self.lock=(self.root/'server.lock').open('a+b')
        self.lock.seek(0);self.lock.write(b'0');self.lock.flush();self.lock.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.lock.close();raise RuntimeError('Este diretório já está em uso. Execute somente uma instância do Radar web.') from None
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='radar-web')
        self.template=load(SOURCE/'config.example.json')
        self.hosts={urlsplit(s['root']).hostname for s in self.template['sources']}
        os.environ['RADAR_PORTABLE_EXCEL']='1'

    def enabled(self,uid):return any(u['id']==uid and u['enabled'] for u in self.accounts.users())

    def get(self,uid):
        # uid comes only from the authenticated account database, never request parameters.
        if len(uid)!=32 or any(c not in '0123456789abcdef' for c in uid):raise ValueError('Conta inválida.')
        with self.guard:
            if uid not in self.services:
                base=self.root/'users'/uid;base.mkdir(parents=True,exist_ok=True)
                if not (base/'references.json').exists():save(base/'references.json',[])
                if not (base/'config.json').exists():
                    config=load(SOURCE/'config.example.json')
                    config['profile']={'kind':'web','cities':[],'types':[]}
                    config['suggested_filters']=dict(config['filters'])
                    config['property_overrides']={}
                    for source in config['sources']:source['watch_urls']=[]
                    save(base/'config.json',config)
                self.services[uid]=WebService(base,self,uid)
            return self.services[uid]

    def tick(self):
        for user in self.accounts.users():
            if not user['enabled']:continue
            service=self.get(user['id'])
            with service.guard:
                if service.job['busy']:continue
                try:
                    service.notifications.favorites.capture(load(service.base/'config.json'),dates_only=True)
                    if service.next_run and service.next_run<=time.time():service.mutate('search',{})
                except Exception:
                    service.record_error()
                    # Avoid a failing schedule spinning on every tick.
                    service.next_run=time.time()+service.schedule['hours']*3600 if service.schedule['enabled'] else None
                    service.persist()
                    service.job.update(error=True,started=time.time(),message='Não foi possível executar a busca automática. Confira os sites selecionados ou tente uma busca manual.')

    def start(self):
        def agenda():
            while not self.closed.is_set():
                try:self.tick()
                except Exception:logging.exception('Falha ao verificar a agenda do Radar web; nova tentativa em um minuto.')
                self.closed.wait(60)
        self.thread=threading.Thread(target=agenda,daemon=True,name='radar-agenda');self.thread.start()

    def close(self):
        if self.closed.is_set():return
        self.closed.set()
        if self.thread:self.thread.join(timeout=10)
        self.pool.shutdown(wait=True)
        self.lock.close()
