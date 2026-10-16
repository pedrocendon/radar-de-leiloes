"""Same report contract, now using the redistributable Windows generator."""
import os
import unittest
from unittest.mock import patch
import test_xlsx
from engine import export,load
from xlsx_export import REPORT_NAME

class PortableExcelTests(test_xlsx.ExcelTests):
    def setUp(self):
        self.environment=patch.dict(os.environ,{'RADAR_PORTABLE_EXCEL':'1','RADAR_NODE_EXE':'missing-node.exe'})
        self.environment.start()
        with patch.object(test_xlsx,'runtime',return_value=None):super().setUp()

    def tearDown(self):
        super().tearDown();self.environment.stop()

    def test_missing_runtime_keeps_previous(self):
        self.store.put('mega','https://example.test/imovel-1',self.data)
        export(self.base)
        previous=(self.base/'exports'/REPORT_NAME).read_bytes()
        with patch('portable_excel.build_report',side_effect=RuntimeError('Gerador indisponível')):
            export(self.base)
        self.assertEqual((self.base/'exports'/REPORT_NAME).read_bytes(),previous)
        self.assertEqual(load(self.base/'exports/situacao-planilha.json')['situacao'],'pendente')
        self.assertTrue((self.base/'exports/resultados.csv').exists())

    def test_formula_and_links(self):
        self.store.put('mega','https://example.test/imovel-1',self.data)
        export(self.base)
        wb=self.workbook(formulas=True)
        self.assertEqual(wb.sheetnames,['Painel','Anúncios','Praças','Áreas','Fontes','Alterações','Guia'])
        self.assertEqual(wb['Praças']['H7'].data_type,'f')
        self.assertEqual(wb['Anúncios']['U6'].value,'https://example.test/imovel-1')
        self.assertEqual(wb['Anúncios'].freeze_panes,'B6')
        self.assertTrue(wb['Anúncios'].tables)
        wb.close()

if __name__=='__main__':unittest.main(verbosity=2)
