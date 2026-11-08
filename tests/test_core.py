"""作者：Wangyuan；日期：2026-10-29；职责：仅以从零合成输入验证核心与异常路径。"""

import tempfile, unittest
from pathlib import Path
from metrics import *
class MetricTests(unittest.TestCase):
    def test_decimal_counts_and_invalids(self):
        self.assertEqual(count(str(10**30)),10**30)
        for value in [True,None,'NaN','Infinity','1.2',-1]:
            with self.assertRaises(ValueError): count(value)
    def test_procurement_precision_caps_and_receipt(self):
        catalog=[{'id':'a','units_per_pack':3,'package_price':'0.30','specification':'3件','category':'c'}]
        result=procurement(catalog,[{'id':'a','packs':3,'received':2}],price_caps={'c':'0.09'})
        self.assertEqual(result['total'],'0.90'); self.assertEqual(result['lines'][0]['unit_price'],'0.10'); self.assertFalse(result['ready'])
        self.assertEqual(len(result['lines'][0]['issues']),2)
    def test_ratio_zero_missing_and_invalid(self):
        self.assertEqual(ratio(0,0)['state'],'not_applicable'); self.assertEqual(ratio(None,10)['state'],'missing')
        self.assertEqual(ratio(5,10)['ratio'],'0.5')
        with self.assertRaises(ValueError): ratio(11,10)
    def test_join_dedup_and_missing_not_zero(self):
        row={'source_id':'x','person':'p1','month':'2030-01','metric':'m','score':'2.5'}
        result=join_scores([{'id':'p1'},{'id':'p2'}],[row,row],{'m':'2'},'0','2030-01')
        self.assertEqual(result['rows'][0]['total'],'5.0'); self.assertIsNone(result['rows'][1]['total'])
        with self.assertRaises(ValueError): join_scores([{'id':'p1'}],[row,{**row,'score':'3'}],{'m':'1'},'0','2030-01')
    def test_rank_ties_and_missing(self):
        result=rank_scores([{'id':'a','score':'10'},{'id':'b','score':'10'},{'id':'c','score':'9'},{'id':'d','score':None}],[{'minimum':'10','name':'tier-A'}])
        self.assertEqual([x['rank'] for x in result],[1,1,3,None]); self.assertEqual(result[0]['tier'],'tier-A')
    def test_point_ledger_revision_and_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=PointLedger(Path(tmp)/'x.sqlite'); self.assertEqual(ledger.record('s','p','2030-01','2','reviewer',confirmed=True)['version'],1)
            self.assertTrue(ledger.record('s','p','2030-01','2','reviewer',confirmed=True)['reused'])
            with self.assertRaises(ValueError): ledger.record('s','p','2030-01','3','reviewer',confirmed=True)
            ledger.record('s','p','2030-01','3','reviewer',expected_version=1,confirmed=True)
            self.assertEqual(ledger.monthly('2030-01',['p','q'])['missing_people'],['q'])
    def test_price_validity_and_no_automatic_decision(self):
        row={'item':'a','unit':'piece','price':'1.20','captured_at':'2030-01-01T00:00:00+00:00','valid_until':'2030-01-02T00:00:00+00:00','evidence':'synthetic-ref'}
        result=compare_prices(row,{**row,'price':'1.10'},'2030-01-01T12:00:00+00:00'); self.assertEqual(result['delta'],'-0.10'); self.assertEqual(result['state'],'candidate')
        with self.assertRaises(ValueError): compare_prices(row,row,'2030-01-03T00:00:00+00:00')
    def test_xlsx_dynamic_headers_and_formula_preservation(self):
        from workbooks import read_xlsx, fill_template, export_xlsx
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Font
        with tempfile.TemporaryDirectory() as tmp:
            template=Path(tmp)/'template.xlsx'; output=Path(tmp)/'output.xlsx'
            book=Workbook(); sheet=book.active; sheet.title='data'; sheet.append(['ID','Points','Formula']); sheet.append(['p1',None,'=B2*2']); sheet['B2'].font=Font(bold=True); book.save(template); book.close()
            self.assertIsNone(read_xlsx(template,'data',{'id':'ID','score':'Points'})[0]['score'])
            fill_template(template,output,'data',[{'id':'p1','score':3}],'ID',{'score':'Points'})
            book=load_workbook(output); self.assertEqual(book['data']['B2'].value,3); self.assertTrue(book['data']['B2'].font.bold); self.assertEqual(book['data']['C2'].value,'=B2*2'); book.close()
            with self.assertRaises(ValueError): fill_template(template,output,'data',[{'id':'unknown','score':3}],'ID',{'score':'Points'})
            export_xlsx([{'id':'=1+1'}],['id'],Path(tmp)/'neutral.xlsx')
            book=load_workbook(Path(tmp)/'neutral.xlsx'); self.assertEqual(book.active['A2'].data_type,'s'); book.close()
    def test_csv_formula_escape(self):
        self.assertIn("'=1+1",export_csv([{'value':'=1+1'}],['value']))

if __name__ == "__main__":
    unittest.main()
