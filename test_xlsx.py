"""Integration checks for automatic workbook refresh. Needs the bundled generator."""
import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from engine import Store, export, load, run
from xlsx_export import REPORT_NAME, runtime


class ExcelTests(unittest.TestCase):
    def setUp(self):
        runtime()
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        source = Path(__file__).parent
        shutil.copy2(source/'report_builder.mjs', self.base/'report_builder.mjs')
        self.config = load(source/'config.json')
        self.config['sources'] = [dict(self.config['sources'][0], discovery_urls=[], watch_urls=['https://example.test/imovel-1'])]
        self.config['filters'] = dict(cities=[], states=[], types=[], max_price=600, min_discount=50,
                                     date_from='2026-10-15', date_to=None, min_price=None, show_pending=True)
        (self.base/'config.json').write_text(json.dumps(self.config), encoding='utf-8')
        (self.base/'references.json').write_text('[]', encoding='utf-8')
        self.store = Store(self.base/'data/monitor.sqlite')
        self.data = {'title':'Apartamento de teste', 'city':'São Paulo', 'uf':'SP', 'type':'apartamento',
                     'valuation':1000, 'origin':'site', 'auction_external_id':'leilao1',
                     'stages':[{'number':1,'date':'2026-10-01','minimum_bid':1000},
                               {'number':2,'date':'2026-11-01T14:00:00-03:00','minimum_bid':500}]}

    def tearDown(self):
        self.temp.cleanup()

    def workbook(self, formulas=False):
        from openpyxl import load_workbook
        return load_workbook(self.base/'exports'/REPORT_NAME, data_only=not formulas)

    def test_collection_refresh_and_changes(self):
        with patch('engine.Client.get', return_value='<html/>'), patch('engine.parse', return_value=self.data):
            run(self.base)
        wb=self.workbook()
        self.assertEqual(wb['Painel']['H7'].value,1)
        self.assertEqual(wb['Painel']['H9'].value,2)
        self.assertEqual(wb['Praças']['H7'].value,0.5)
        self.assertEqual(wb['Praças']['L6'].value,'Fora dos filtros')
        self.assertEqual(wb['Praças']['L7'].value,'Atende aos filtros')
        self.assertEqual(wb['Praças']['E7'].value.hour,14)
        wb.close()
        changed=copy.deepcopy(self.data)
        changed['stages'][1]['minimum_bid']=400
        changed['stages'][1]['date']='2026-11-03T15:30:00-03:00'
        with patch('engine.Client.get',return_value='<html/>'),patch('engine.parse',return_value=changed):
            run(self.base)
        wb=self.workbook()
        self.assertEqual(wb['Praças']['F7'].value,400)
        self.assertEqual(wb['Praças']['E7'].value.day,3)
        self.assertAlmostEqual(wb['Praças']['H7'].value,0.6)
        self.assertTrue(any(x['field']=='stages' for x in self.store.history()))
        wb.close()

    def test_missing_values_failure_and_literal_title(self):
        self.data['valuation']=None
        self.data['title']='=1+1'
        self.data['stages'][0]['minimum_bid']=None
        self.store.put('mega','https://example.test/imovel-1',self.data)
        self.store.put('mega','https://example.test/imovel-1',status='falha_rede',detail='Sem conexão')
        export(self.base)
        wb=self.workbook()
        self.assertEqual(wb['Anúncios']['E6'].value,'Falha de rede')
        self.assertIsNone(wb['Praças']['G6'].value)
        self.assertIsNone(wb['Praças']['F6'].value)
        self.assertIn(wb['Praças']['H7'].value,(None,''))
        self.assertEqual(wb['Praças']['F7'].value,500)
        wb.close()
        formulas=self.workbook(formulas=True)
        self.assertEqual(formulas['Anúncios']['B6'].data_type,'s')
        formulas.close()

    def test_empty_database(self):
        export(self.base)
        self.assertEqual(load(self.base/'exports/situacao-planilha.json')['situacao'],'atualizada')
        wb=self.workbook()
        self.assertEqual(wb['Painel']['H7'].value,0)
        self.assertEqual(wb['Painel']['H9'].value,0)
        wb.close()

    def test_missing_runtime_keeps_previous(self):
        self.store.put('mega','https://example.test/imovel-1',self.data)
        export(self.base)
        previous=(self.base/'exports'/REPORT_NAME).read_bytes()
        with patch.dict(os.environ, {'RADAR_NODE_EXE':str(self.base/'missing.exe')}):
            export(self.base)
        self.assertEqual((self.base/'exports'/REPORT_NAME).read_bytes(),previous)
        state=load(self.base/'exports/situacao-planilha.json')
        self.assertEqual(state['situacao'],'pendente')
        self.assertTrue(state['ultima_atualizacao'])
        self.assertTrue((self.base/'exports/resultados.csv').exists())

    @unittest.skipUnless(os.name=='nt','Windows Excel locking behavior')
    def test_open_excel_preserves_report(self):
        import ctypes
        from ctypes import wintypes
        self.store.put('mega','https://example.test/imovel-1',self.data)
        export(self.base)
        target=self.base/'exports'/REPORT_NAME
        previous=target.read_bytes()
        create=ctypes.windll.kernel32.CreateFileW
        create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        create.restype=wintypes.HANDLE
        handle=create(str(target),0x80000000,1,None,3,0,None)
        self.assertNotEqual(handle,wintypes.HANDLE(-1).value)
        try:
            export(self.base)
            self.assertEqual(load(self.base/'exports/situacao-planilha.json')['situacao'],'pendente')
        finally:
            ctypes.windll.kernel32.CloseHandle.argtypes=[wintypes.HANDLE]
            ctypes.windll.kernel32.CloseHandle(handle)
        self.assertEqual(target.read_bytes(),previous)


if __name__=='__main__':
    unittest.main(verbosity=2)
