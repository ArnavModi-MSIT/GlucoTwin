import sys,unittest
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from glucotwin.rbg_replay import issue_rbg_forecasts,reveal_rbg_outcomes

class ConstantModel:
    def predict(self,X):return np.full(len(X),150.)

class RbgReplayTests(unittest.TestCase):
    def setUp(self):
        self.ts=pd.date_range('2024-01-01',periods=100,freq='5min')
        self.frame=pd.DataFrame({'ts':self.ts,'GlucoseCGM':100+np.arange(100,dtype=float)})
        self.patient={'split':'validation','age_at_enrollment':40.,'sex_f':0,'minimum_forecast_time':str(self.ts[0])}
        self.artifacts={h:{'model':ConstantModel(),'features':['cgm_current'],'horizon_minutes':h,'sensor_delay_minutes':5} for h in [30,60]}
    def test_delayed_prefix_forecasts_and_outcome_reveal(self):
        now=self.ts[30]
        issued=issue_rbg_forecasts(self.frame,self.patient,self.artifacts,now)
        self.assertEqual(issued[0]['persistence'],129.)
        changed=self.frame.copy();changed.loc[changed.ts>=now,'GlucoseCGM']=999.
        self.assertEqual(issued,issue_rbg_forecasts(changed,self.patient,self.artifacts,now))
        at_target=reveal_rbg_outcomes(issued,self.frame,now+pd.Timedelta(minutes=30))
        self.assertEqual(at_target.iloc[0].outcome,'Pending')
        after=reveal_rbg_outcomes(issued,self.frame,now+pd.Timedelta(minutes=35))
        self.assertEqual(after.iloc[0].actual,136.)
        self.assertEqual(after.iloc[0].ridge_error,14.)
        self.assertEqual(after.iloc[0].persistence_error,7.)
        self.assertEqual(after.iloc[1].outcome,'Pending')
        self.assertNotIn('actual',issued[0])
    def test_missing_current_abstains_and_test_rejected(self):
        self.frame.loc[29,'GlucoseCGM']=np.nan
        issued=issue_rbg_forecasts(self.frame,self.patient,self.artifacts,self.ts[30])
        self.assertIsNone(issued[0]['prediction'])
        self.patient['split']='test'
        with self.assertRaises(ValueError):issue_rbg_forecasts(self.frame,self.patient,self.artifacts,self.ts[30])
if __name__=='__main__':unittest.main()
