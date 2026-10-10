"""Exercise the HTTP replay engine with a deterministic synthetic patient."""
import sys,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np,pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import serve_dashboard as web

class ReplayLifecycleTests(unittest.TestCase):
    def test_end_of_record_is_idempotent_and_reset_recovers(self):
        class Model:
            def predict(self,X):return np.full(len(X),120.)
        times=pd.date_range('2024-01-01',periods=100,freq='5min')
        frame=pd.DataFrame({'ts':times,'GlucoseCGM':110.})
        patient={'patient_id':'synthetic','split':'validation','age_at_enrollment':40.,'sex_f':0.,'minimum_forecast_time':str(times[20])}
        models={h:{'model':Model(),'features':['cgm_current'],'sensor_delay_minutes':5,'horizon_minutes':h} for h in (30,60)}
        with patch.object(web,'catalog',return_value={'synthetic':patient}),patch.object(web,'records',return_value=(frame,{'age':40.,'sex':'M'})),patch.object(web,'models',return_value=models):
            replay=web.Replay('rbg','synthetic');initial=replay.snapshot()
            replay.position=len(replay.clock)-1;replay.issue();count=len(replay.ledger)
            for _ in range(3):replay.advance(60)
            self.assertEqual(len(replay.ledger),count);self.assertTrue(replay.snapshot()['at_end'])
            replay.reset();self.assertEqual(replay.snapshot()['issue_time'],initial['issue_time']);self.assertEqual(len(replay.ledger),2)
