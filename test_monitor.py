import unittest,tempfile,copy,json
from pathlib import Path
from unittest.mock import patch
from collectors import canonical,money,mega,saraiva,CollectError,Client
from engine import Store,evaluate,safe_cell,duplicate_candidates,validate_config,load
class CoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.db=Store(Path(self.tmp.name)/'test.sqlite')
  self.d={'title':'Apartamento 201','city':'São Paulo','uf':'SP','type':'apartamento','origin':'site','valuation':1000,'auction_external_id':'A','stages':[{'number':1,'date':'2026-10-01','minimum_bid':1000},{'number':2,'date':'2026-11-01','minimum_bid':500}]}
 def tearDown(self):self.tmp.cleanup()
 def test_urls_tracking(self):self.assertEqual(canonical('https://x.test/lote/1?utm_source=a&id=9#x'),'https://x.test/lote/1?id=9')
 def test_numbers(self):self.assertEqual(money('R$ 1.713.525,38'),1713525.38);self.assertIsNone(money('não informado'))
 def test_same_stage(self):self.assertEqual(evaluate(self.d,{'max_price':600,'date_to':'2026-10-15'})[0],'fora')
 def test_missing_not_zero(self):
  d=copy.deepcopy(self.d);d['valuation']=None
  self.assertEqual(evaluate(d,{'min_discount':35})[0],'pendente')
 def test_zero_valuation(self):
  d=copy.deepcopy(self.d);d['valuation']=0
  self.assertEqual(evaluate(d,{'min_discount':35})[0],'pendente')
 def test_matching_stage(self):self.assertEqual(evaluate(self.d,{'max_price':600,'min_discount':50,'date_from':'2026-10-15'})[0],'corresponde')
 def test_failure_preserves(self):
  self.db.put('x','https://x.test/1',self.d);before=self.db.rows()[0]['data'];self.db.put('x','https://x.test/1',status='bloqueado',detail='403')
  r=self.db.rows()[0];self.assertEqual(r['data'],before);self.assertEqual(r['collection_status'],'bloqueado');self.assertTrue(r['last_success'])
 def test_history_and_editions(self):
  self.db.put('x','https://x.test/1',self.d);d=copy.deepcopy(self.d);d['stages'][1]['date']='2026-11-03';self.db.put('x','https://x.test/1',d)
  self.assertEqual(len([x for x in self.db.history() if x['field']=='stages']),1)
  d['auction_external_id']='B';self.db.put('x','https://x.test/1',d)
  with self.db.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM auctions').fetchone()[0],2);self.assertEqual(db.execute('SELECT COUNT(*) FROM stages WHERE current=1').fetchone()[0],2)
 def test_personal_ceiling_preserved(self):
  d=copy.deepcopy(self.d);d['personal_ceiling']=750;d['origin']='planilha';self.db.put('x','https://x.test/1',d);self.db.put('x','https://x.test/1',self.d)
  self.assertEqual(self.db.rows()[0]['data']['personal_ceiling'],750)
 def test_canonical_dedupe(self):
  self.db.put('x','https://x.test/1?utm_source=a',self.d);self.db.put('x','https://x.test/1?utm_source=b',self.d);self.assertEqual(len(self.db.rows()),1)
 def test_similar_not_merged(self):
  self.db.put('x','https://x.test/1',self.d);self.db.put('x','https://x.test/2',self.d)
  self.assertEqual(len({r['property_id'] for r in self.db.rows()}),2);self.assertEqual(len(duplicate_candidates(self.db.rows())),1)
 def test_manual_consolidation_preserves_links(self):
  overrides={'https://x.test/1':'imovel-1','https://y.test/2':'imovel-1'}
  self.db.put('x','https://x.test/1',self.d,overrides=overrides);self.db.put('y','https://y.test/2',self.d,overrides=overrides)
  self.assertEqual(len({r['property_id'] for r in self.db.rows()}),1);self.assertEqual(len(self.db.rows()),2)
 def test_csv_injection(self):self.assertEqual(safe_cell('=1+1'),"'=1+1");self.assertEqual(safe_cell(None),'');self.assertEqual(safe_cell(100),100)
 def test_config_dates(self):
  c=load(Path(__file__).parent/'config.json');c['filters']['date_from']='2026-13-01'
  with self.assertRaises(ValueError):validate_config(c)
  c['filters']['date_from']=None;c['filters']['max_price']=float('nan')
  with self.assertRaises(ValueError):validate_config(c)
 def test_robots_blocks_before_fetch(self):
  c=Client()
  with patch.object(c,'raw',return_value='User-agent: *\nDisallow: /private') as raw:
   with self.assertRaises(CollectError):c.get('https://x.test/private')
   self.assertEqual(raw.call_count,1)
 def test_robots_html_not_success(self):
  c=Client()
  with patch.object(c,'raw',return_value='<html>app</html>'):
   with self.assertRaises(CollectError):c.get('https://x.test/1')
 def test_related_cards_not_auction_stages(self):
  html='<h1>Apartamento - São Paulo - SP</h1><div class="main-info">Valor de Avaliação R$ 1.000,00</div><div id="tab-description">Apartamento 101.</div><div class="summary-info"><div class="instance"><b>1ª Praça:</b> 10/10/2026 às 14:00 <span class="card-instance-value">R$ 1.000,00</span></div></div><div class="card"><div class="instance"><b>1ª Praça:</b> 20/10/2026 às 14:00 <span class="card-instance-value">R$ 50,00</span></div></div>'
  d=mega(html,'https://x.test/apartamento-j123');self.assertEqual(len(d['stages']),1);self.assertEqual(d['stages'][0]['minimum_bid'],1000)
if __name__=='__main__':unittest.main(verbosity=2)
