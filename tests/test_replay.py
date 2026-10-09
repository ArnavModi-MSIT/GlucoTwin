import sys, unittest
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from glucotwin.replay import issue_forecast, reveal_outcomes
from test_features import PROFILE

class ConstantModel:
    def predict(self, features):
        return np.full(len(features),150.)

class ReplayTests(unittest.TestCase):
    def test_hidden_outcome_and_immutable_forecast(self):
        times=pd.date_range('2026-01-01',periods=181,freq='min')
        frame=pd.DataFrame({'Timestamp':times,'Dexcom GL':100.,'HR':60.})
        patient={'split':'validation','phase_utc_minutes_mod_5':0,'minimum_forecast_time':str(times[60])}
        artifact={'model':ConstantModel(),'features':['cgm_current']}
        issued=issue_forecast(frame,PROFILE,patient,artifact,times[120])
        changed=frame.copy()
        changed.loc[changed.Timestamp>times[120],'Dexcom GL']=900.
        self.assertEqual(issued,issue_forecast(changed,PROFILE,patient,artifact,times[120]))
        pending=reveal_outcomes([issued],changed,times[120]).iloc[0]
        self.assertTrue(pd.isna(pending.actual))
        self.assertEqual(pending.outcome,'Pending')
        observed=reveal_outcomes([issued],changed,times[180]).iloc[0]
        self.assertEqual(observed.actual,900.)
        self.assertEqual(observed.prediction,150.)
        self.assertNotIn('actual',issued)
        patient['split']='test'
        with self.assertRaises(ValueError): issue_forecast(frame,PROFILE,patient,artifact,times[120])

    def test_missing_target_is_not_filled(self):
        issued={'issued_at':pd.Timestamp('2026-01-01'),'target_time':pd.Timestamp('2026-01-01 01:00'), 'prediction':150.}
        frame=pd.DataFrame({'Timestamp':pd.to_datetime(['2026-01-01 00:59','2026-01-01 01:01']),'Dexcom GL':[100,200]})
        row=reveal_outcomes([issued],frame,'2026-01-01 01:02').iloc[0]
        self.assertEqual(row.outcome,'Missing observation')
        self.assertTrue(pd.isna(row.actual))

if __name__=='__main__': unittest.main()
