import sys,unittest
from pathlib import Path
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from glucotwin.rbg import rbg_features,supervised_rbg

class RbgFeatureTests(unittest.TestCase):
    def setUp(self):
        self.ts=pd.date_range('2024-01-01',periods=80,freq='5min')
        self.frame=pd.DataFrame({'ts':self.ts,'GlucoseCGM':100+np.arange(80,dtype=float)})
        self.patient={'age_at_enrollment':40.,'sex_f':1,'minimum_forecast_time':str(self.ts[0])}
    def test_delay_and_future_edit_parity(self):
        now=self.ts[30]
        expected=rbg_features(self.frame,self.patient).loc[now]
        self.assertEqual(expected.cgm_current,129.)
        prefix=rbg_features(self.frame[self.frame.ts<=now-pd.Timedelta(minutes=5)],self.patient).loc[now]
        pd.testing.assert_series_equal(expected,prefix)
        changed=self.frame.copy();changed.loc[changed.ts>=now,'GlucoseCGM']=999
        pd.testing.assert_series_equal(expected,rbg_features(changed,self.patient).loc[now])
    def test_exact_horizon_and_missing_targets(self):
        for horizon in [30,60]:
            rows=supervised_rbg(self.frame,self.patient,horizon)
            now=self.ts[30]
            self.assertEqual(rows.loc[now,'target'],100+30+horizon//5)
            changed=self.frame.copy();changed.loc[changed.ts.eq(now+pd.Timedelta(minutes=horizon)),'GlucoseCGM']=np.nan
            self.assertNotIn(now,supervised_rbg(changed,self.patient,horizon).index)
    def test_missing_delayed_current_and_warmup(self):
        self.frame.loc[29,'GlucoseCGM']=np.nan
        self.assertFalse(rbg_features(self.frame,self.patient).loc[self.ts[30],'history_eligible'])
        self.patient['minimum_forecast_time']=str(self.ts[40])
        rows=supervised_rbg(self.frame,self.patient,30)
        self.assertTrue((rows.index>=self.ts[40]).all())
if __name__=='__main__':unittest.main()
