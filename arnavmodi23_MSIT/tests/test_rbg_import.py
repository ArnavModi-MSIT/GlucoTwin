import unittest,sys,tempfile,zipfile
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from import_rbg import extract_subset,audit_subset,CSV_NAME

class RbgImportTests(unittest.TestCase):
    def test_exact_source_filter_and_streamed_grid(self):
        header='ts,PtID,GlucoseCGM,Age,Sex,Hba1c,DiagAge,Race,HeightCm,WeightKg,Database\n'
        rows=['2024-01-01T00:00:00,1.0_RBG,100,40,F,,10,White,170,70,RBG\n','2024-01-01T00:05:00,1.0_RBG,,40,F,,10,White,170,70,RBG\n','2024-01-01T00:10:00,1.0_RBG,105,40,F,,10,White,170,70,RBG\n','2024-01-01T00:00:00,1.0_CITY,100,40,F,,10,White,170,70,CITY\n']
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);archive=folder/'source.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr(CSV_NAME,header+''.join(rows))
            partial,count=extract_subset(archive,folder/'rbg.csv')
            self.assertEqual(count,3);self.assertNotIn(b'CITY',partial.read_bytes())
            result=audit_subset(partial,chunksize=2)
            self.assertEqual(result['1.0_RBG']['rows'],3);self.assertEqual(result['1.0_RBG']['glucose_rows'],2)
    def test_invalid_chunk_boundary_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'bad.csv'
            pd.DataFrame({'ts':['2024-01-01 00:00','2024-01-01 00:05','2024-01-01 00:05'],'PtID':['1.0_RBG']*3,'GlucoseCGM':[100,101,102]}).to_csv(path,index=False)
            with self.assertRaises(ValueError):audit_subset(path,chunksize=2)

if __name__=='__main__':unittest.main()
