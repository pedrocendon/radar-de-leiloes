import copy,json,tempfile,threading,time,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from engine import load,Store,ident
from friendly_ui import br_number,friendly_filters,listing_view,make_server,Service

class InputTests(unittest.TestCase):
    def test_brazilian_money(self):
        self.assertEqual(br_number('R$ 800.000,50','Preço'),800000.5)
        self.assertEqual(br_number('800.000','Preço'),800000)
        self.assertIsNone(br_number('','Preço'))
        for v in ['oitocentos','12,2,3','-50',float('nan')]:
            with self.assertRaises(ValueError):br_number(v,'Preço')
    def test_filter_validation(self):
        f=friendly_filters({'cities':'São Paulo; Itapema','states':'sp,sc','max_price':'800.000','date_from':'2026-10-02'})
        self.assertEqual(f['max_price'],800000);self.assertEqual(f['states'],['SP','SC'])
        for f in [{'min_price':'900','max_price':'800'},{'date_from':'2026-11-03','date_to':'2026-10-03'},{'min_discount':'101'},{'date_from':'2026-02-30'}]:
            with self.assertRaises(ValueError):friendly_filters(f)
    def test_price_belongs_to_displayed_stage(self):
        c=load(Path(__file__).parent/'config.json');c['filters']=friendly_filters({'max_price':'600'})
        r={'id':'a','source':'mega','url':'https://example.test/a','collection_status':'ok','last_attempt':None,'last_success':None,
           'data':{'title':'Apartamento','stages':[{'number':1,'date':'2026-09-01','minimum_bid':10},{'number':2,'date':'2026-10-14','minimum_bid':1000},{'number':3,'date':'2026-11-01','minimum_bid':500}]}}
        with patch('friendly_ui.now',return_value='2026-10-02T15:00:00-03:00'):result=listing_view(r,c)
        self.assertEqual(result['next_stage']['minimum_bid'],1000)
        self.assertFalse(result['stages'][1]['matches']);self.assertTrue(result['stages'][2]['matches'])

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.config=load(Path(__file__).parent/'config.json')
        (self.base/'config.json').write_text(json.dumps(self.config),encoding='utf-8')
        (self.base/'references.json').write_text('[]',encoding='utf-8')
        self.server=make_server(self.base);self.service=self.server.service
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}/api/'
    def tearDown(self):
        self.service.closed.set();self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,path,payload=None,token=True,origin=None):
        headers={'Content-Type':'application/json'}
        if token:headers['X-Radar-Token']=self.server.token
        if origin:headers['Origin']=origin
        req=urllib.request.Request(self.url+path,headers=headers,data=None if payload is None else json.dumps(payload).encode())
        with urllib.request.urlopen(req,timeout=5) as r:return json.load(r)
    def test_local_auth_and_origin(self):
        for token,origin in [(False,None),(True,'https://untrusted.example')]:
            with self.assertRaises(urllib.error.HTTPError) as ctx:self.request('state',token=token,origin=origin)
            self.assertEqual(ctx.exception.code,403)
        self.assertEqual(self.request('state')['listings'],[])
    def test_save_filters(self):
        self.request('filters',{'cities':'Itapema','max_price':'800.000','show_pending':True})
        self.assertEqual(load(self.base/'config.json')['filters']['max_price'],800000)
        self.assertEqual(self.request('state')['filters']['cities'],['Itapema'])
    def add_listing(self):
        url='https://www.megaleiloes.com.br/imoveis/apartamentos/sp/favorito-j123'
        self.service.store.put('mega',url,{'title':'Apartamento de teste','city':'São Paulo','uf':'SP','stages':[]})
        return ident(url),url
    def test_favorites_roundtrip_and_idempotency(self):
        listing_id,_=self.add_listing()
        self.assertFalse(self.request('state')['listings'][0]['favorite'])
        result=self.request('favorite',{'id':listing_id,'favorite':True})
        again=self.request('favorite',{'id':listing_id,'favorite':True})
        self.assertEqual(result,again)
        self.assertTrue(result['favorited_at'])
        row=self.request('state')['listings'][0]
        self.assertTrue(row['favorite'])
        self.assertEqual(row['favorited_at'],result['favorited_at'])
        reopened=Service(self.base)
        self.assertTrue(reopened.state()['listings'][0]['favorite'])
    def test_favorite_survives_collector_updates_failures_and_filters(self):
        listing_id,url=self.add_listing()
        self.service.job['busy']=True
        self.request('favorite',{'id':listing_id,'favorite':True})
        other_store=Store(self.base/'data/monitor.sqlite')
        other_store.put('mega',url,{'title':'Apartamento atualizado','city':'São Paulo','stages':[{'number':1,'minimum_bid':900000}]})
        other_store.put('mega',url,status='falha_rede')
        self.service.job['busy']=False
        self.request('filters',{'cities':'Curitiba'})
        row=self.request('state')['listings'][0]
        self.assertTrue(row['favorite']);self.assertEqual(row['title'],'Apartamento atualizado')
        self.assertEqual(row['match'],'fora');self.assertEqual(row['status'],'falha_rede')
    def test_remove_favorite_keeps_listing_and_history(self):
        listing_id,_=self.add_listing()
        self.request('favorite',{'id':listing_id,'favorite':True})
        self.request('favorite',{'id':listing_id,'favorite':False})
        self.request('favorite',{'id':listing_id,'favorite':False})
        rows=self.request('state')['listings']
        self.assertEqual(len(rows),1);self.assertFalse(rows[0]['favorite'])
        self.assertIsNone(rows[0]['favorited_at'])
        with self.service.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM observations').fetchone()[0],1)
    def test_favorites_reject_invalid_requests_and_unauthorized_writes(self):
        listing_id,_=self.add_listing()
        for payload in [{'id':listing_id,'favorite':'true'},{'id':listing_id,'favorite':1},{'id':listing_id},{'id':['bad'],'favorite':True},{'id':'missing','favorite':True}]:
            with self.assertRaises(urllib.error.HTTPError) as ctx:self.request('favorite',payload)
            self.assertEqual(ctx.exception.code,400)
        for token,origin in [(False,None),(True,'https://untrusted.example')]:
            with self.assertRaises(urllib.error.HTTPError) as ctx:self.request('favorite',{'id':listing_id,'favorite':True},token=token,origin=origin)
            self.assertEqual(ctx.exception.code,403)
        self.assertFalse(self.request('state')['listings'][0]['favorite'])
    def test_existing_database_gains_favorites_without_changing_listings(self):
        listing_id,_=self.add_listing()
        with self.service.store.connect() as db:db.execute('DROP TABLE favorites')
        migrated=Store(self.base/'data/monitor.sqlite')
        self.assertEqual(migrated.rows()[0]['id'],listing_id)
        self.assertIsNone(migrated.rows()[0]['favorited_at'])
        migrated.set_favorite(listing_id,True)
        self.assertTrue(migrated.rows()[0]['favorited_at'])
    def test_background_status_is_authenticated_and_tracks_schedule(self):
        with self.assertRaises(urllib.error.HTTPError):self.request('background',token=False)
        self.assertEqual(set(self.request('background')),{'job','schedule','updates'})
        self.assertFalse(self.request('background')['updates']['supported'])
        for action in ('update_check','update_install','update_settings','startup_settings'):
            with self.assertRaises(urllib.error.HTTPError) as denied:self.request(action,{},token=False)
            self.assertEqual(denied.exception.code,403)
        self.request('schedule',{'enabled':True,'hours':6})
        status=self.request('background')
        self.assertTrue(status['schedule']['enabled']);self.assertIsNotNone(status['schedule']['next_run'])
        self.service.job.update(busy=True,kind='search',message='Consultando fonte')
        self.assertTrue(self.request('background')['job']['busy'])
        with self.assertRaises(urllib.error.HTTPError):self.request('close',{})
        self.assertFalse(self.service.closed.is_set())
        self.service.job.update(busy=False)
        self.request('schedule',{'enabled':False,'hours':6})
        self.assertIsNone(self.request('background')['schedule']['next_run'])
    def test_busy_keeps_settings(self):
        self.service.job['busy']=True
        with self.assertRaises(urllib.error.HTTPError):self.request('filters',{'cities':'Outra cidade'})
        self.assertEqual(load(self.base/'config.json'),self.config)
    def test_schedule_off_by_default_and_persists(self):
        self.assertFalse(self.request('state')['schedule']['enabled'])
        self.request('schedule',{'enabled':True,'hours':6})
        self.assertEqual(load(self.base/'data/preferencias.json'),{'enabled':True,'hours':6})
        self.request('schedule',{'enabled':False,'hours':6})
        self.assertIsNone(self.request('state')['schedule']['next_run'])
    def test_no_enabled_sites_has_helpful_error(self):
        self.request('sources',{'enabled':[]})
        with self.assertRaises(urllib.error.HTTPError) as ctx:self.request('search',{})
        self.assertIn('Selecione pelo menos',ctx.exception.read().decode('utf-8'))
    def test_watch_link_supported_only(self):
        u='https://www.megaleiloes.com.br/imoveis/apartamentos/sp/teste-j123'
        self.request('watch',{'url':u});self.request('watch',{'url':u})
        self.assertEqual(load(self.base/'config.json')['sources'][0]['watch_urls'],[u])
        for u in ['http://127.0.0.1/private','https://www.megaleiloes.com.br/','file:///C:/x']:
            with self.assertRaises(urllib.error.HTTPError):self.request('watch',{'url':u})
    def test_job_error_is_friendly(self):
        with patch('friendly_ui.export',side_effect=RuntimeError('technical stack details')):
            self.request('export',{})
            deadline=time.time()+3
            while self.service.job['busy'] and time.time()<deadline:time.sleep(.01)
        job=self.request('state')['job']
        self.assertFalse(job['busy']);self.assertTrue(job['error']);self.assertNotIn('technical stack details',job['message'])
        self.assertTrue((self.base/'data/ajuda-tecnica.log').exists())
    def test_download_missing_workbook(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:self.request('excel')
        self.assertEqual(ctx.exception.code,404)

if __name__=='__main__':unittest.main(verbosity=2)
