import copy
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from collectors import TZ
from engine import Store, ident
from notifications import Notifications


class FavoriteNotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name)/'data.sqlite')
        self.current = datetime(2026, 10, 16, 12, tzinfo=TZ)
        self.clock = patch('favorite_notifications.clock', side_effect=lambda:self.current);self.clock.start()
        self.time = patch('engine.now', side_effect=lambda:self.current.isoformat());self.time.start()
        self.config = {'sources':[{'id':'x','enabled':True},{'id':'y','enabled':True}], 'filters':{'cities':['Outra cidade']}}
        self.data = dict(title='FAVORITO DE TESTE', city='São Paulo', uf='SP', origin='site', auction_external_id='A',
                         stages=[dict(number=1,date='2026-10-19T15:00:00-03:00',minimum_bid=500000)])
        self.center = Notifications(self.store)
        self.center.begin(self.config)
        self.center.favorites.configure(dict(price=True,dates=True,days=3,date_changes=False,status_changes=False))
        self.put()
        self.store.set_favorite(ident(self.url()),True);self.center.favorites.sync()
    def tearDown(self):
        self.clock.stop();self.time.stop();self.temp.cleanup()
    def url(self,n=1,source='x'):return f'https://{source}.test/{n}'
    def put(self,data=None,n=1,source='x',status='ok',overrides=None):
        self.store.put(source,self.url(n,source),copy.deepcopy(self.data if data is None else data),status,overrides=overrides)
    def update(self,value):
        data=copy.deepcopy(self.data);data['stages'][0]['minimum_bid']=value;self.put(data)
    def capture(self):return self.center.favorites.capture(self.config)
    def kinds(self):return [e['kind'] for e in self.center.state()['events']]
    def settings(self,price=True,dates=True,days=3):self.center.favorites.configure(dict(price=price,dates=dates,days=days))
    def test_first_capture_reminds_but_does_not_invent_price_drop(self):
        self.assertEqual(self.capture(),1);self.assertEqual(self.kinds(),['favorite_date'])
        self.assertIn('em 3 dias',self.center.claim()['text'])
    def test_drop_outside_search_filters_even_with_new_property_notices_disabled(self):
        self.center.configure(False);self.settings(dates=False);self.update(450000)
        self.center.capture(self.config)
        self.assertEqual(self.kinds(),['favorite_price'])
        notice=self.center.claim();self.assertIn('R$ 500.000,00 para R$ 450.000,00',notice['text'])
        self.assertIsNone(self.center.claim());self.assertEqual(self.capture(),0)
    def test_restart_does_not_repeat_price_or_date(self):
        self.update(450000);self.capture();self.center.claim();self.center.claim()
        self.center=Notifications(self.store);self.center.begin(self.config)
        self.assertEqual(self.capture(),0);self.assertIsNone(self.center.claim())
    def test_additional_reduction_and_increase_then_reduction(self):
        self.settings(dates=False)
        for price,expected in [(450000,1),(450000,0),(430000,1),(460000,0),(450000,1)]:
            self.update(price);self.assertEqual(self.capture(),expected)
    def test_different_stages_are_never_compared(self):
        self.settings(dates=False)
        data=copy.deepcopy(self.data);data['stages']=[dict(number=2,date='2026-10-20',minimum_bid=100000)]
        self.put(data);self.assertEqual(self.capture(),0)
    def test_new_auction_or_rescheduled_date_resets_price_comparison(self):
        self.settings(dates=False)
        for field,value in [('auction_external_id','B'),('date','2026-10-20')]:
            data=copy.deepcopy(self.data);data['stages'][0]['minimum_bid']=100000
            if field=='date':data['stages'][0]['date']=value
            else:data[field]=value
            self.put(data);self.assertEqual(self.capture(),0)
    def test_missing_or_invalid_prices_do_not_invent_zero_drop(self):
        self.settings(dates=False)
        for value in [None,0,-10,'300000',float('inf'),True]:
            self.update(value);self.assertEqual(self.capture(),0)
        self.update(450000);self.assertEqual(self.capture(),1)
    def test_failure_then_recovery_uses_last_confirmed_price(self):
        self.settings(dates=False);self.update(450000)
        self.store.put('x',self.url(),status='falha_rede');self.assertEqual(self.capture(),0)
        self.update(450000);self.assertEqual(self.capture(),1)
    def test_cancelled_sold_assisted_disabled_source_no_alert(self):
        for status in ['Encerrado','Suspenso','Arrematado','Cancelado','Vendido']:
            data=copy.deepcopy(self.data);data['status']=status;data['stages'][0]['minimum_bid']=100000
            self.put(data);self.assertEqual(self.capture(),0)
        data['status']='';data['origin']='consulta_assistida';self.put(data);self.assertEqual(self.capture(),0)
        self.update(100000);self.config['sources'][0]['enabled']=False;self.assertEqual(self.capture(),0)
    def test_disabled_price_reenabled_without_backlog(self):
        self.settings(price=False,dates=False);self.update(450000);self.capture()
        self.update(400000);self.settings(price=True,dates=False)
        self.assertEqual(self.capture(),0);self.update(390000);self.assertEqual(self.capture(),1)
    def test_reminder_ticks_without_new_search(self):
        self.settings(days=1);self.assertEqual(self.capture(),0)
        self.current+=timedelta(days=2)
        self.assertEqual(self.center.favorites.capture(self.config,dates_only=True),1)
        self.assertIn('amanhã',self.center.claim()['text'])
    def test_old_data_does_not_remind_until_refreshed(self):
        self.settings(days=1);self.current+=timedelta(days=2,seconds=1)
        self.assertEqual(self.capture(),0);self.put();self.assertEqual(self.capture(),1)
    def test_dates_exact_time_and_date_only_today(self):
        for value in ['2026-10-16T11:00:00-03:00','2026-10-15','garbage','2026-02-30']:
            data=copy.deepcopy(self.data);data['stages'][0]['date']=value;self.put(data)
            self.assertEqual(self.capture(),0)
        data['stages'][0]['date']='2026-10-16';self.put(data);self.assertEqual(self.capture(),1)
        self.assertIn('hoje',self.center.claim()['text'])
    def test_new_date_gets_new_reminder(self):
        self.capture();self.center.claim()
        data=copy.deepcopy(self.data);data['stages'][0]['date']='2026-10-18';self.put(data)
        self.assertEqual(self.capture(),1);self.assertEqual(self.capture(),0)
    def test_remove_favorite_cancels_pending_but_keeps_history(self):
        self.update(450000);self.capture();self.store.set_favorite(ident(self.url()),False);self.center.favorites.sync()
        self.assertIsNone(self.center.claim());self.assertEqual(len(self.kinds()),2)
        self.store.set_favorite(ident(self.url()),True);self.center.favorites.sync();self.assertEqual(self.capture(),0)
    def test_cancel_after_capture_prevents_delivery(self):
        self.update(450000);self.capture();data=copy.deepcopy(self.data);data['status']='Cancelado';self.put(data)
        self.assertIsNone(self.center.claim())
    def test_reschedule_prevents_old_date_delivery(self):
        self.capture();data=copy.deepcopy(self.data);data['stages'][0]['date']='2027-01-01';self.put(data)
        self.assertIsNone(self.center.claim())
    def test_settings_and_filter_change_do_not_cancel_favorite_events(self):
        self.capture();self.center.configure(False);self.config['filters']['cities']=[];self.center.begin(self.config)
        self.assertIsNotNone(self.center.claim())
    def test_known_duplicate_favorites_group_date_and_keep_links(self):
        overrides={self.url():'P',self.url(2,'y'):'P'}
        self.put(overrides=overrides);self.put(n=2,source='y',overrides=overrides)
        self.store.set_favorite(ident(self.url(2,'y')),True);self.center.favorites.sync()
        self.assertEqual(self.capture(),1)
        self.assertEqual(len(self.center.state()['events'][0]['items'][0]['listings']),2)
    def test_all_disabled_no_test_and_no_delivery(self):
        self.capture();self.settings(price=False,dates=False);self.center.configure(False)
        self.assertIsNone(self.center.claim())
        with self.assertRaises(ValueError):self.center.test()
    def test_late_delivery_uses_current_days_remaining(self):
        self.capture();self.current+=timedelta(days=1)
        self.assertIn('em 2 dias',self.center.claim()['text'])
    def test_unfavorited_listing_never_notifies(self):
        self.store.set_favorite(ident(self.url()),False);self.update(100000)
        self.assertEqual(self.capture(),0)
    def test_no_date_and_no_auction_identity_cannot_compare(self):
        self.settings(dates=False);data=copy.deepcopy(self.data)
        data.pop('auction_external_id');data['stages'][0]['date']=None
        self.put(data);self.capture();data['stages'][0]['minimum_bid']=100000
        self.put(data);self.assertEqual(self.capture(),0)
    def test_duplicate_favorites_group_price_changes(self):
        self.settings(dates=False);overrides={self.url():'P',self.url(2,'y'):'P'}
        self.put(overrides=overrides);self.put(n=2,source='y',overrides=overrides)
        self.store.set_favorite(ident(self.url(2,'y')),True);self.center.favorites.sync()
        data=copy.deepcopy(self.data);data['stages'][0]['minimum_bid']=400000
        self.put(data,overrides=overrides);self.put(data,n=2,source='y',overrides=overrides)
        self.assertEqual(self.capture(),1)
        self.assertEqual(len(self.center.state()['events'][0]['items'][0]['listings']),2)
    def test_validate_settings_strictly(self):
        for values in [dict(price='true',dates=True,days=3),dict(price=True,dates=True,days=True),dict(price=True,dates=True,days=2)]:
            with self.assertRaises(ValueError):self.center.favorites.configure(values)
        self.settings(days=7);self.assertEqual(Notifications(self.store).favorites.settings()['days'],7)
    def test_duplicate_stage_identity_skips_price_comparison(self):
        self.settings(dates=False);data=copy.deepcopy(self.data);data['stages']*=2
        data['stages'][0]['minimum_bid']=100000;self.put(data);self.assertEqual(self.capture(),0)


if __name__=='__main__':unittest.main()
