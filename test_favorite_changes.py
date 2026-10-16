import copy
import json
import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from engine import ident, Store, run
from notifications import Notifications
from favorite_changes import situation
import test_favorite_notifications as helpers


class FavoriteChangeTests(unittest.TestCase):
    url = helpers.FavoriteNotificationTests.url
    put = helpers.FavoriteNotificationTests.put
    capture = helpers.FavoriteNotificationTests.capture
    kinds = helpers.FavoriteNotificationTests.kinds
    tearDown = helpers.FavoriteNotificationTests.tearDown
    def setUp(self):
        helpers.FavoriteNotificationTests.setUp(self)
        self.data['status']='Aberto';self.put()
        self.center.favorites.configure(dict(price=False,dates=False,days=3,date_changes=True,status_changes=True))
    def change(self,date=None,status=None,auction='A'):
        data=copy.deepcopy(self.data);data['auction_external_id']=auction
        if date is not None:data['stages'][0]['date']=date
        if status is not None:data['status']=status
        self.put(data);return self.capture()
    def test_rescheduled_date_before_after_once(self):
        self.assertEqual(self.change(date='2026-10-22T15:00:00-03:00'),1)
        event=self.center.state()['events'][0];self.assertEqual(event['kind'],'favorite_rescheduled')
        self.assertEqual(event['items'][0]['previous_date'],self.data['stages'][0]['date'])
        self.assertIn('19/10/2026 às 15:00 para 22/10/2026 às 15:00',self.center.claim()['text'])
        self.assertEqual(self.capture(),0);self.assertIsNone(self.center.claim())
    def test_hour_change(self):
        self.assertEqual(self.change(date='2026-10-19T17:00:00-03:00'),1)
    def test_timezone_equivalence_does_not_notify(self):
        self.assertEqual(self.change(date='2026-10-19T18:00:00+00:00'),0)
    def test_precision_only_does_not_notify(self):
        self.assertEqual(self.change(date='2026-10-19'),0)
        self.assertEqual(self.change(date='2026-10-19T15:00:00-03:00'),0)
    def test_missing_invalid_and_removed_stage_preserve_baseline(self):
        for date in [None,'','2026-02-30','not a date']:
            data=copy.deepcopy(self.data);data['stages'][0]['date']=date;self.put(data);self.assertEqual(self.capture(),0)
        data['stages']=[];self.put(data);self.assertEqual(self.capture(),0)
        self.put();self.assertEqual(self.capture(),0)
        self.assertEqual(self.change(date='2026-10-22'),1)
    def test_unknown_first_date_is_not_a_change(self):
        self.store.set_favorite(ident(self.url()),False);self.center.favorites.sync()
        data=copy.deepcopy(self.data);data['stages'][0]['date']=None;self.put(data)
        self.store.set_favorite(ident(self.url()),True);self.center.favorites.sync()
        self.put();self.assertEqual(self.capture(),0)
    def test_new_stage_and_new_auction_do_not_compare(self):
        data=copy.deepcopy(self.data);data['stages'][0]['number']=2;self.put(data);self.assertEqual(self.capture(),0)
        self.assertEqual(self.change(date='2026-10-25',auction='B',status='Suspenso'),0)
    def test_unknown_auction_can_track_same_listing_but_known_identity_loss_waits(self):
        self.assertEqual(self.change(date='2026-10-25',auction=None),0)
        self.assertEqual(self.change(date='2026-10-25',auction='A'),1)
    def test_suspend_cancel_and_repeated_status(self):
        self.assertEqual(self.change(status='Suspenso'),1)
        self.assertIn('suspenso',self.center.claim()['text'])
        self.assertEqual(self.change(status='Leilão suspenso'),0)
        self.assertEqual(self.change(status='Cancelado'),1)
        self.assertIn('cancelado',self.center.claim()['text'])
        self.assertEqual(self.capture(),0)
    def test_missing_status_does_not_reset_suspension(self):
        self.change(status='Suspenso');self.center.claim()
        data=copy.deepcopy(self.data);data['status']=None;self.put(data);self.assertEqual(self.capture(),0)
        self.assertEqual(self.change(status='Suspenso'),0)
    def test_resumed_then_suspended_again_is_new(self):
        self.change(status='Suspenso');self.center.claim()
        self.assertEqual(self.change(status='Em andamento'),0)
        self.assertEqual(self.change(status='Suspenso'),1)
    def test_failures_and_assisted_never_mean_cancelled(self):
        self.change(status='Aberto')
        for status in ['http_404','falha_rede','bloqueado']:
            self.store.put('x',self.url(),status=status);self.assertEqual(self.capture(),0)
        data=copy.deepcopy(self.data);data['origin']='consulta_assistida';data['status']='Cancelado'
        self.put(data);self.assertEqual(self.capture(),0)
        self.assertEqual(self.change(status='Cancelado'),1)
    def test_unfavorited_disabled_sources_and_dates_only(self):
        self.config['sources'][0]['enabled']=False;self.assertEqual(self.change(status='Suspenso'),0)
        self.config['sources'][0]['enabled']=True;self.assertEqual(self.capture(),0)
        data=copy.deepcopy(self.data);data['status']='Cancelado';self.put(data)
        self.assertEqual(self.center.favorites.capture(self.config,dates_only=True),0)
        self.store.set_favorite(ident(self.url()),False);self.center.favorites.sync();self.assertEqual(self.capture(),0)
    def test_disable_enable_without_backlog_preserves_other_preferences(self):
        self.change(status='Suspenso')
        self.center.favorites.configure(dict(date_changes=False,status_changes=False))
        self.assertIsNone(self.center.claim())
        self.change(date='2026-10-25',status='Cancelado')
        self.center.favorites.configure(dict(date_changes=True,status_changes=True))
        self.assertEqual(self.capture(),0)
        self.assertFalse(self.center.favorites.settings()['price'])
    def test_restart_no_duplicate_and_existing_migration_no_backlog(self):
        self.change(date='2026-10-25',status='Cancelado');self.center.claim();self.center.claim()
        self.center=Notifications(self.store);self.center.begin(self.config)
        self.assertEqual(self.capture(),0);self.assertIsNone(self.center.claim())
        with self.store.connect() as db:db.execute('DROP TABLE favorite_change_baselines')
        self.center=Notifications(self.store);self.center.begin(self.config)
        self.assertEqual(self.capture(),0)
    def test_migration_from_083_preserves_old_settings(self):
        with self.store.connect() as db:
            db.execute('DROP TABLE favorite_notice_settings')
            db.execute('CREATE TABLE favorite_notice_settings(id INTEGER PRIMARY KEY,price INTEGER,dates INTEGER,days INTEGER)')
            db.execute('INSERT INTO favorite_notice_settings VALUES(1,0,0,7)')
        settings=Notifications(self.store).favorites.settings()
        self.assertEqual(settings,dict(price=False,dates=False,days=7,date_changes=True,status_changes=True))
    def test_stale_superseded_or_unfavorited_not_delivered(self):
        self.change(date='2026-10-22',status='Suspenso')
        self.put();self.assertIsNone(self.center.claim())
        self.change(date='2026-10-25',status='Cancelado')
        self.store.set_favorite(ident(self.url()),False);self.assertIsNone(self.center.claim())
        self.assertEqual(len(self.center.state()['events']),4)
    def test_status_notice_delivers_even_without_dates(self):
        data=copy.deepcopy(self.data);data['stages']=[];data['status']='Cancelado';self.put(data)
        self.assertEqual(self.capture(),1);self.assertIn('cancelado',self.center.claim()['text'])
    def test_no_confusion_between_prose_and_explicit_status(self):
        for value in ['Não suspenso','Cancelamento solicitado','Pode ser cancelado','Suspenso ou cancelado',4,None,'Não cancelado']:
            self.assertIsNone(situation(value))
        self.assertEqual(situation('Situação: Leilão suspenso'),'suspenso')
        self.assertEqual(situation('Pregão cancelado'),'cancelado')
    def test_simultaneous_changes_have_separate_events_status_first(self):
        self.assertEqual(self.change(date='2026-10-25',status='Cancelado'),2)
        self.assertIn('cancelamento',self.center.claim()['title'])
        self.assertIn('data',self.center.claim()['title'])
    def test_duplicate_sources_group_and_keep_links(self):
        overrides={self.url():'P',self.url(2,'y'):'P'}
        self.put(overrides=overrides);self.put(n=2,source='y',overrides=overrides)
        self.store.set_favorite(ident(self.url(2,'y')),True);self.center.favorites.sync()
        data=copy.deepcopy(self.data);data['status']='Cancelado';data['stages'][0]['date']='2026-10-25'
        self.put(data,overrides=overrides);self.put(data,n=2,source='y',overrides=overrides)
        self.assertEqual(self.capture(),2)
        for e in self.center.state()['events']:self.assertEqual(len(e['items'][0]['listings']),2)
    def test_concurrent_claim_only_one_delivery(self):
        self.change(status='Suspenso');results=[]
        threads=[threading.Thread(target=lambda:results.append(self.center.claim())) for _ in range(2)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sum(r is not None for r in results),1)
    def test_invalid_options_rejected(self):
        for payload in [dict(date_changes='true'),dict(status_changes=1)]:
            with self.assertRaises(ValueError):self.center.favorites.configure(payload)
    def test_mega_panel_status_is_read_without_treating_generic_text_as_status(self):
        from collectors import mega
        for value in ['Suspenso','Cancelado']:
            html=f'<h1>Apartamento - São Paulo - SP</h1><div id="tab-description">Imóvel. O edital poderá ser cancelado.</div><div class="summary-info"><span class="instance-text">{value}</span></div>'
            result=mega(html,'https://www.megaleiloes.com.br/imovel-j123')
            self.assertEqual(situation(result['status']),value.lower())
        result=mega('<h1>Imóvel</h1><div id="tab-description">Leilão cancelado se houver decisão.</div>','https://www.megaleiloes.com.br/imovel-j123')
        self.assertIsNone(result['status'])
    def test_real_collection_flow_captures_cancelled_status(self):
        base=Path(self.temp.name);store=Store(base/'data/monitor.sqlite')
        store.put('x',self.url(),self.data,'ok');store.set_favorite(ident(self.url()),True)
        config=json.loads(Path('config.example.json').read_text(encoding='utf-8'))
        config['sources']=[dict(id='x',name='Teste',adapter='mega',root='https://x.test/',enabled=True,
            detail_pattern='/1$',discovery_urls=[],watch_urls=[],note='')]
        (base/'config.json').write_text(json.dumps(config));(base/'references.json').write_text('[]')
        changed=copy.deepcopy(self.data);changed['status']='Cancelado'
        with patch('engine.Client'),patch('engine.parse',return_value=changed),patch('engine.export',side_effect=OSError('Excel unavailable')):
            with self.assertRaises(OSError):run(base)
        self.assertEqual(Notifications(store).state()['events'][0]['kind'],'favorite_status')


if __name__=='__main__':unittest.main()
