import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from engine import load,save,export,similarity
from web.accounts import Accounts,digest
from web.server import create_app
from web.network import PublicClient,PublicConnection,public_addresses,validate_url

PASSWORD='uma senha de teste longa 2026'
ORIGIN='https://radar.example'


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.app=create_app(self.root,ORIGIN,start_scheduler=False)
        self.accounts=self.app.extensions['accounts'];self.runtime=self.app.extensions['radar']
        self.a=self.app.test_client();self.b=self.app.test_client()
        for client,email in [(self.a,'ana@example.com'),(self.b,'bia@example.com')]:
            invite=self.accounts.invite(email)
            self.assertEqual(self.post(client,'/auth/register',dict(invite=invite,name=email[:3].title(),password=PASSWORD)).status_code,200)
        self.ua=self.accounts.users()[0]['id'];self.ub=self.accounts.users()[1]['id']

    def tearDown(self):self.runtime.close();self.temp.cleanup()

    def get(self,client,path):return client.get(path,base_url=ORIGIN)

    def post(self,client,path,data=None,csrf=True,**headers):
        h={'Origin':ORIGIN,'X-Radar-Web':'1'}
        if csrf:
            info=self.get(client,'/auth/session')
            if info.status_code==200:h['X-Radar-Token']=info.json['csrf']
        h.update(headers)
        return client.post(path,base_url=ORIGIN,json=data or {},headers=h)

    def seed(self,uid):
        service=self.runtime.get(uid)
        url='https://www.megaleiloes.com.br/imoveis/apartamento-teste-j12345'
        data=dict(title='Imóvel privado de teste',city='São Paulo',uf='SP',type='apartamento',valuation=500000,
                  origin='site',auction_external_id='12345',stages=[dict(number=1,date='2030-12-01',minimum_bid=300000)])
        service.store.put('mega',url,data,'ok','Teste')
        return service,service.store.rows()[0]['id']

    def test_new_accounts_are_empty(self):
        for client,uid in [(self.a,self.ua),(self.b,self.ub)]:
            state=self.get(client,'/api/state').json
            self.assertEqual(state['listings'],[])
            self.assertEqual(load(self.runtime.get(uid).base/'references.json'),[])
            self.assertFalse(state['schedule']['enabled'])
            self.assertEqual(state['filters']['cities'],[])

    def test_filters_and_files_are_isolated(self):
        self.assertEqual(self.post(self.a,'/api/filters',{'cities':'São Paulo','max_price':'600.000,00'}).status_code,200)
        self.assertEqual(self.get(self.a,'/api/state').json['filters']['max_price'],600000)
        self.assertIsNone(self.get(self.b,'/api/state').json['filters']['max_price'])
        service,lid=self.seed(self.ua)
        export(service.base)
        self.assertEqual(self.get(self.a,'/api/excel').status_code,200)
        self.assertIn('Imóvel privado de teste',self.get(self.a,'/api/csv').data.decode('utf-8-sig'))
        self.assertEqual(self.get(self.b,'/api/excel?user='+self.ua).status_code,404)
        self.assertEqual(self.get(self.b,'/api/state').json['listings'],[])

    def test_favorite_id_cannot_access_other_account(self):
        service,lid=self.seed(self.ua)
        self.assertEqual(self.post(self.b,'/api/favorite',{'id':lid,'favorite':True}).status_code,400)
        self.assertEqual(self.post(self.a,'/api/favorite',{'id':lid,'favorite':True}).status_code,200)
        self.assertTrue(self.get(self.a,'/api/state').json['listings'][0]['favorite'])
        self.assertEqual(self.get(self.b,'/api/state').json['listings'],[])

    def test_unauthenticated_cannot_read_api_or_files(self):
        c=self.app.test_client()
        for path in ('/api/state','/api/excel','/api/csv','/auth/session','/web-data/accounts.sqlite','/config.json'):
            self.assertEqual(self.get(c,path).status_code,401,path)
        self.assertEqual(self.get(c,'/').status_code,302)
        with self.get(c,'/login') as response:self.assertEqual(response.status_code,200)

    def test_identical_listing_ids_have_independent_favorites(self):
        _,lid=self.seed(self.ua);_,other=self.seed(self.ub)
        self.assertEqual(lid,other)
        self.post(self.a,'/api/favorite',{'id':lid,'favorite':True})
        self.assertFalse(self.get(self.b,'/api/state').json['listings'][0]['favorite'])

    def test_no_desktop_control_endpoints(self):
        for action in ('close','open_excel','notifications_claim','startup_settings','update_install'):
            self.assertEqual(self.post(self.a,'/api/'+action).status_code,404)

    def test_csrf_and_cross_origin(self):
        self.assertEqual(self.post(self.a,'/api/schedule',{'enabled':True},csrf=False).status_code,403)
        self.assertEqual(self.post(self.a,'/api/export',Origin='https://attacker.example').status_code,403)
        self.assertEqual(self.post(self.a,'/api/export',**{'Sec-Fetch-Site':'cross-site'}).status_code,403)
        self.assertEqual(self.post(self.a,'/api/export',**{'X-Radar-Web':'0'}).status_code,403)
        self.assertEqual(self.a.post('/auth/login',base_url=ORIGIN,data={'email':'ana@example.com','password':PASSWORD}).status_code,403)

    def test_headers_secure_cookie_and_no_host_spoof(self):
        response=self.post(self.a,'/auth/login',{'email':'ana@example.com','password':PASSWORD})
        cookie=response.headers['Set-Cookie']
        for item in ('Secure','HttpOnly','SameSite=Lax'):self.assertIn(item,cookie)
        html=self.get(self.a,'/')
        self.assertIn('frame-ancestors',html.headers['Content-Security-Policy'])
        self.assertEqual(html.headers['Cache-Control'],'no-store')
        self.assertNotIn('__RADAR_CSRF__',html.text)
        self.assertEqual(self.a.get('/api/state',base_url='https://attacker.example').status_code,400)

    def test_invitation_is_single_use_expiring_and_no_plain_token(self):
        token=self.accounts.invite('terceira@example.com')
        with self.accounts.db() as db:
            self.assertEqual(db.execute('SELECT token FROM invites').fetchone()[0],digest(token))
            db.execute('UPDATE invites SET expires=0')
        with self.assertRaises(ValueError):self.accounts.register(token,'Pessoa',PASSWORD)
        token=self.accounts.invite('terceira@example.com')
        self.accounts.register(token,'Pessoa',PASSWORD)
        with self.assertRaises(ValueError):self.accounts.register(token,'Pessoa',PASSWORD)

    def test_password_change_revokes_all_sessions(self):
        c=self.app.test_client()
        self.post(c,'/auth/login',{'email':'ana@example.com','password':PASSWORD})
        self.assertEqual(self.post(self.a,'/auth/password',{'current':PASSWORD,'password':'nova senha comprida de teste'}).status_code,200)
        self.assertEqual(self.get(c,'/api/state').status_code,401)
        self.assertEqual(self.get(self.a,'/api/state').status_code,401)
        self.assertEqual(self.post(c,'/auth/login',{'email':'ana@example.com','password':PASSWORD}).status_code,401)

    def test_logout_revokes_cookie_replay(self):
        cookie=self.a.get_cookie('radar_session',domain='radar.example').value
        self.assertEqual(self.post(self.a,'/auth/logout').status_code,200)
        self.a.set_cookie('radar_session',cookie,domain='radar.example')
        self.assertEqual(self.get(self.a,'/api/state').status_code,401)

    def test_disabled_account_revokes_access_and_schedule(self):
        service=self.runtime.get(self.ua);service.next_run=1
        self.accounts.set_enabled(self.ua,False)
        self.assertEqual(self.get(self.a,'/api/state').status_code,401)
        with patch.object(service,'mutate') as mutate:self.runtime.tick();mutate.assert_not_called()

    def test_expired_session(self):
        with self.accounts.db() as db:db.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.get(self.a,'/api/state').status_code,401)

    def test_login_rate_limit_and_generic_error(self):
        c=self.app.test_client()
        for _ in range(10):self.assertEqual(self.post(c,'/auth/login',{'email':'missing@example.com','password':'incorrect'}).status_code,401)
        self.assertEqual(self.post(c,'/auth/login',{'email':'missing@example.com','password':'incorrect'}).status_code,429)

    def test_oversized_body_and_invalid_payload(self):
        self.assertEqual(self.post(self.a,'/api/filters',{'cities':'a'*210000}).status_code,413)
        response=self.a.post('/api/filters',base_url=ORIGIN,json=[],headers={'X-Radar-Web':'1','X-Radar-Token':self.get(self.a,'/auth/session').json['csrf']})
        self.assertEqual(response.status_code,400)

    def test_watch_rejects_ports_and_untrusted_hosts(self):
        for url in ('http://127.0.0.1/private','https://www.megaleiloes.com.br:1234/imoveis/ap-j123',
                    'https://www.megaleiloes.com.br.attacker.example/imoveis/ap-j123','https://user@www.megaleiloes.com.br/imoveis/ap-j123'):
            self.assertEqual(self.post(self.a,'/api/watch',{'url':url}).status_code,400,url)

    def test_search_uses_hardened_collector_and_keeps_other_account_idle(self):
        with patch('web.runtime.run') as run:
            self.assertEqual(self.post(self.a,'/api/search').status_code,200)
            self.runtime.pool.submit(lambda:None).result(timeout=10)
            run.assert_called_once()
            self.assertIsInstance(run.call_args.kwargs['client'],PublicClient)
        self.assertFalse(self.get(self.b,'/api/state').json['job']['busy'])
        self.assertEqual(self.post(self.a,'/api/search').status_code,400)

    def test_export_job_downloads_real_workbook(self):
        service,_=self.seed(self.ua)
        self.assertEqual(self.post(self.a,'/api/export').status_code,200)
        self.runtime.pool.submit(lambda:None).result(timeout=20)
        response=self.get(self.a,'/api/excel')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.data.startswith(b'PK'))

    def test_busy_export_cannot_download_partial_csv(self):
        service=self.runtime.get(self.ua);service.job['busy']=True
        self.assertEqual(self.get(self.a,'/api/csv').status_code,409)

    def test_schedule_runs_without_logged_in_browser_and_survives_restart(self):
        self.post(self.a,'/api/schedule',{'enabled':True,'hours':6})
        service=self.runtime.get(self.ua);service.next_run=time.time()-1;service.persist()
        self.post(self.a,'/auth/logout')
        self.runtime.close()
        self.app=create_app(self.root,ORIGIN,start_scheduler=False);self.runtime=self.app.extensions['radar']
        with patch('web.runtime.run') as run:
            self.runtime.tick();self.runtime.pool.submit(lambda:None).result(timeout=10)
            run.assert_called_once()
        self.assertGreater(self.runtime.get(self.ua).next_run,time.time())

    def test_same_directory_rejects_second_instance(self):
        with self.assertRaises(RuntimeError):create_app(self.root,ORIGIN,start_scheduler=False)

    def test_new_web_profiles_do_not_reuse_original_spreadsheet_assumptions(self):
        self.assertEqual(similarity({'type':'apartamento'},{'kind':'web','cities':[],'types':[]}),(0,[]))
        self.assertEqual(similarity({'type':'casa'},{'kind':'web','cities':[],'types':['casa']})[0],1)

    def test_http_only_allowed_for_loopback(self):
        with self.assertRaises(ValueError):create_app(self.root,'http://public.example',False)


class NetworkTests(unittest.TestCase):
    def test_private_and_mixed_dns_addresses_refused(self):
        for ips in (['127.0.0.1'],['169.254.169.254'],['10.0.0.1'],['::1'],['8.8.8.8','192.168.1.2']):
            answers=[(2,1,6,'',(ip,443)) for ip in ips]
            with patch('web.network.socket.getaddrinfo',return_value=answers),self.assertRaises(OSError):public_addresses('example.com')

    def test_https_connect_pins_ip_but_verifies_original_tls_host(self):
        conn=PublicConnection('www.megaleiloes.com.br');conn._context=Mock()
        with patch('web.network.public_addresses',return_value=['8.8.8.8']),patch('web.network.socket.create_connection') as connect:
            conn.connect()
            self.assertEqual(connect.call_args.args[0],('8.8.8.8',443))
            self.assertEqual(conn._context.wrap_socket.call_args.kwargs['server_hostname'],'www.megaleiloes.com.br')

    def test_strict_hosts_and_ports(self):
        validate_url('https://www.megaleiloes.com.br/imoveis/ap-j123',{'www.megaleiloes.com.br'})
        for url in ('ftp://www.megaleiloes.com.br','https://www.megaleiloes.com.br:81','https://elsewhere.com'):
            with self.assertRaises(ValueError):validate_url(url,{'www.megaleiloes.com.br'})


if __name__=='__main__':unittest.main()
