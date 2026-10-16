import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from engine import Store, run
from notifications import Notifications


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.store=Store(self.base/'data/monitor.sqlite')
        self.config={'filters':{'cities':['São Paulo'],'states':['SP'],'max_price':600,'show_pending':True},
                     'sources':[{'id':'x','enabled':True},{'id':'y','enabled':True}]}
        self.data={'title':'Apartamento de teste','city':'São Paulo','uf':'SP','type':'apartamento','origin':'site',
                   'valuation':1000,'stages':[{'number':1,'date':'2099-10-01','minimum_bid':500}]}
        self.center=Notifications(self.store);self.center.begin(self.config)
    def tearDown(self):self.temp.cleanup()
    def put(self,n=1,data=None,status='ok',source='x',overrides=None):
        url='https://'+source+'.test/'+str(n)
        self.store.put(source,url,copy.deepcopy(self.data if data is None else data),status,overrides=overrides)
        return url
    def capture(self):return self.center.capture(self.config)
    def test_new_matching_only_once_across_restart(self):
        self.put();self.assertEqual(self.capture(),1)
        notice=self.center.claim();self.assertIn('1 novo imóvel',notice['text']);self.assertIsNone(self.center.claim())
        self.center=Notifications(self.store);self.center.begin(self.config);self.put()
        self.assertEqual(self.capture(),0);self.assertIsNone(self.center.claim())
    def test_existing_database_migrates_without_backlog(self):
        with self.store.connect() as db:
            db.execute('DELETE FROM notification_settings')
        self.put();self.center=Notifications(self.store);self.center.begin(self.config)
        self.assertEqual(self.capture(),0)
    def test_aggregates_several_properties_into_one_notice(self):
        self.put(1);self.put(2);self.assertEqual(self.capture(),2)
        self.assertIn('2 novos imóveis',self.center.claim()['text']);self.assertIsNone(self.center.claim())
    def test_known_duplicate_sources_preserve_both_links(self):
        overrides={'https://x.test/1':'same','https://y.test/2':'same'}
        self.put(1,overrides=overrides);self.put(2,source='y',overrides=overrides)
        self.assertEqual(self.capture(),1)
        self.assertEqual(len(self.center.state()['events'][0]['items'][0]['listings']),2)
    def test_new_source_for_known_property_is_not_new_property(self):
        overrides={'https://x.test/1':'same','https://y.test/2':'same'}
        self.put(1,overrides=overrides);self.capture();self.center.claim()
        self.put(2,source='y',overrides=overrides);self.assertEqual(self.capture(),0)
    def test_similar_address_is_not_silently_merged(self):
        self.put(1);self.put(2);self.assertEqual(self.capture(),2)
    def test_outside_filter_does_not_notify_after_price_change(self):
        data=copy.deepcopy(self.data);data['stages'][0]['minimum_bid']=1000
        self.put(data=data);self.assertEqual(self.capture(),0)
        self.put();self.assertEqual(self.capture(),0)
    def test_pending_waits_for_data_even_when_show_pending_enabled(self):
        data=copy.deepcopy(self.data);data['stages'][0]['minimum_bid']=None
        self.put(data=data,status='parcial');self.assertEqual(self.capture(),0)
        self.put();self.assertEqual(self.capture(),1)
    def test_failed_read_never_uses_preserved_matching_data(self):
        url=self.put();self.store.put('x',url,status='falha_rede')
        self.assertEqual(self.capture(),0);self.put();self.assertEqual(self.capture(),1)
    def test_filters_must_match_same_stage(self):
        self.config['filters']['date_to']='2099-10-02';self.center.begin(self.config)
        data=copy.deepcopy(self.data);data['stages']=[{'number':1,'date':'2099-10-01','minimum_bid':900},
                                                    {'number':2,'date':'2099-10-03','minimum_bid':500}]
        self.put(data=data);self.assertEqual(self.capture(),0)
    def test_expired_matching_stage_does_not_qualify_future_expensive_stage(self):
        data=copy.deepcopy(self.data);data['stages']=[{'number':1,'date':'2000-01-01','minimum_bid':100},
                                                    {'number':2,'date':'2099-01-01','minimum_bid':900}]
        self.put(data=data);self.assertEqual(self.capture(),0)
    def test_expired_and_inactive_are_not_notified(self):
        for i,status in enumerate(('Encerrado','Arrematado','Inativo','Suspenso','Cancelado')):
            data=copy.deepcopy(self.data);data['status']=status;self.put(i,data=data)
        data=copy.deepcopy(self.data);data['stages'][0]['date']='2000-01-01';self.put(100,data=data)
        self.assertEqual(self.capture(),0)
    def test_disabled_sources_and_assisted_import_do_not_notify(self):
        self.config['sources'][0]['enabled']=False;self.center.begin(self.config);self.put()
        data=copy.deepcopy(self.data);data['origin']='consulta_assistida';self.put(2,source='y',data=data)
        self.assertEqual(self.capture(),0)
    def test_filter_change_cancels_pending_and_does_not_realert_old_rows(self):
        self.put();self.capture();self.config['filters']['max_price']=900;self.center.begin(self.config)
        self.assertIsNone(self.center.claim());self.assertEqual(self.capture(),0)
        self.put(2);self.assertEqual(self.capture(),1)
    def test_disabled_then_reenabled_does_not_backfill(self):
        self.put();self.capture();self.center.configure(False);self.assertIsNone(self.center.claim())
        self.put(2);self.capture();self.put(3);self.center.configure(True)
        self.assertEqual(self.capture(),0);self.put(4);self.assertEqual(self.capture(),1)
    def test_no_filters_does_not_send_everything(self):
        self.config['filters']={'show_pending':True};self.center.begin(self.config);self.put()
        self.assertEqual(self.capture(),0)
    def test_history_remains_after_claim_and_records_filter_snapshot(self):
        self.put();self.capture();self.center.claim();state=self.center.state()
        self.assertEqual(state['events'][0]['filters']['max_price'],600);self.assertEqual(state['pending'],0)
    def test_test_notice_is_explicit_and_rate_limited(self):
        self.center.test();self.assertIn('Teste',self.center.claim()['title'])
        self.assertEqual(self.center.state()['events'],[])
        with self.assertRaises(ValueError):self.center.test()
    def test_concurrent_claims_only_one_delivery(self):
        self.put();self.capture();results=[]
        threads=[threading.Thread(target=lambda:results.append(self.center.claim())) for _ in range(2)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sum(r is not None for r in results),1)
    def test_capture_precedes_excel_failure_in_real_search_flow(self):
        config=json.loads(Path('config.example.json').read_text(encoding='utf-8'))
        config['filters'].update(self.config['filters']);config['sources']=[dict(id='x',name='Teste',adapter='mega',root='https://x.test/',
            enabled=True,detail_pattern='/1$',discovery_urls=['https://x.test/'],watch_urls=[],note='')]
        (self.base/'config.json').write_text(json.dumps(config));(self.base/'references.json').write_text('[]')
        with patch('engine.Client') as client,patch('engine.discover',return_value=(['https://x.test/1'],[])),patch('engine.parse',return_value=self.data),patch('engine.export',side_effect=OSError('Excel failed')):
            client.return_value.get.return_value='page'
            with self.assertRaises(OSError):run(self.base)
        self.assertEqual(len(self.center.state()['events']),1)

if __name__=='__main__':unittest.main()
