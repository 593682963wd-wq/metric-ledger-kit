"""作者：Wangyuan；日期：2026-11-08。职责：通过合成输入复验已确认缺陷。"""
import unittest,tempfile,json,os,sqlite3,csv,io
from pathlib import Path
from datetime import datetime
from openpyxl import Workbook,load_workbook
from metrics import PointLedger,export_csv
from workbooks import read_xlsx,fill_template,export_xlsx
class ReleaseTests(unittest.TestCase):
 def test_datetime_json_serializable(self) -> None:
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'data.xlsx';w=Workbook();w.active.append(['date']);w.active.append([datetime(2030,1,1,10)]);w.save(p);w.close()
   self.assertIn('2030-01-01T10:00:00',json.dumps(read_xlsx(p,'Sheet',{'time':'date'})))
 def test_hardlink_template_rejected(self) -> None:
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'input.xlsx';q=Path(d)/'output.xlsx';w=Workbook();w.active.append(['id','value']);w.active.append(['a','old']);w.save(p);w.close();os.link(p,q);before=p.read_bytes()
   with self.assertRaises(ValueError):fill_template(p,q,'Sheet',[{'id':'a','value':'new'}],'id',{'value':'value'})
   self.assertEqual(p.read_bytes(),before)
 def test_csv_and_xlsx_headers_not_formulas(self) -> None:
  self.assertEqual(next(csv.reader(io.StringIO(export_csv([],["=1+1"])))),["'=1+1"])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'out.xlsx';export_xlsx([],['=1+1'],p);w=load_workbook(p);self.assertNotEqual(w.active['A1'].data_type,'f');w.close()
 def test_identity_revision_audit_retains_both_values(self) -> None:
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger.sqlite';l=PointLedger(p);l.record('source','old','2030-01','1','a',confirmed=True);l.record('source','new','2030-02','2','a',expected_version=1,confirmed=True)
   with sqlite3.connect(p) as con:r=con.execute('SELECT old_person,old_month,old_score,new_person,new_month,new_score FROM audit_changes WHERE version=2').fetchone()
   self.assertEqual(r,('old','2030-01','1','new','2030-02','2'))
