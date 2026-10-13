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
    def test_rbg_withheld_outcomes_and_long_gap_window_parity(self):
        from glucotwin.rbg import rbg_features
        from glucotwin.rbg_replay import issue_rbg_forecasts,reveal_rbg_outcomes
        from glucotwin.artifacts import CGM
        start=pd.Timestamp('2026-01-01')
        cutoff=start+pd.Timedelta(hours=12);now=cutoff+pd.Timedelta(minutes=5)
        times=pd.DatetimeIndex([start]).append(pd.date_range(cutoff-pd.Timedelta(minutes=45),cutoff,freq='5min'))
        frame=pd.DataFrame(dict(ts=times,GlucoseCGM=110.))
        patient=dict(split='validation',age_at_enrollment=40.,sex_f=0.,minimum_forecast_time=start+pd.Timedelta(hours=1))
        class Capture:
            def predict(self,x):self.x=x.copy();return np.array([150.])
        model=Capture();artifact=dict(model=model,features=CGM,sensor_delay_minutes=5,horizon_minutes=30)
        result=issue_rbg_forecasts(frame,patient,{30:artifact},now)[0]
        self.assertEqual(result['status'],'Forecast issued')
        full=rbg_features(frame,patient).loc[[now],CGM].to_numpy(dtype=np.float32)
        np.testing.assert_allclose(model.x,full,rtol=1e-7,atol=1e-7,equal_nan=True)
        withheld={**result,'prediction':None,'persistence':None}
        target=pd.DataFrame(dict(ts=[withheld['target_time']],GlucoseCGM=[200.]))
        row=reveal_rbg_outcomes([withheld],target,withheld['available_at']).iloc[0]
        self.assertEqual(row.outcome,'Not evaluated');self.assertTrue(pd.isna(row.actual));self.assertTrue(pd.isna(row.ridge_error))

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

    def test_withheld_attempt_has_no_observed_outcome_or_error(self):
        now=pd.Timestamp('2026-01-01T01:00')
        issued=dict(issued_at=now-pd.Timedelta(minutes=60),target_time=now,prediction=None,status='Insufficient history')
        frame=pd.DataFrame(dict(Timestamp=[now],**{'Dexcom GL':[200.]}))
        for cutoff in [now-pd.Timedelta(minutes=5),now]:
            row=reveal_outcomes([issued],frame,cutoff).iloc[0]
            self.assertEqual(row.outcome,'Not evaluated')
            self.assertTrue(pd.isna(row.actual));self.assertTrue(pd.isna(row.absolute_error))
        self.assertNotIn('outcome',issued)

if __name__=='__main__': unittest.main()
