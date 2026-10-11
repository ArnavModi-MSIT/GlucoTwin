import sys,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import json
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prepare_features


class PreparationBoundaryTests(unittest.TestCase):
    def test_reserved_sensor_file_is_never_opened(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'configs').mkdir();(root/'reports').mkdir()
            participant={'patient_id':1,'split':'train','a1c_group':'normal','phase_utc_minutes_mod_5':0,'minimum_forecast_time':'2024-01-01'}
            reserved={**participant,'patient_id':99,'split':'test'}
            (root/'configs/cgmacros_splits.json').write_text(json.dumps({'participants':[participant,reserved]}))
            bio=pd.DataFrame({'subject':[1],'Age':[40],'Gender':['F'],'BMI':[22],'A1c PDL (Lab)':[5.],'Fasting GLU - PDL (Lab)':[90]})
            frame=pd.DataFrame({'Timestamp':pd.date_range('2024-01-01',periods=50,freq='5min'),'Dexcom GL':100.,'HR':60.})
            calls=[]
            def read(path):
                calls.append(str(path))
                if '099' in str(path):raise AssertionError('Reserved sensor opened')
                return bio.copy() if Path(path).name=='bio.csv' else frame.copy()
            with patch.object(prepare_features,'ROOT',root),patch.object(prepare_features.pd,'read_csv',side_effect=read):prepare_features.run()
            self.assertEqual(len(calls),2)
