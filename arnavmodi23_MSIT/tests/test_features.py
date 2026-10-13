import sys, unittest
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from glucotwin.features import make_features
from local_only import local_only

PROFILE = {'age':40.,'gender_f':0.,'bmi':26.,'hba1c_pct':6.,'fasting_glucose':100.}

class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.times = pd.date_range('2026-01-01',periods=181,freq='min')
        self.frame = pd.DataFrame({'Timestamp':self.times,'Dexcom GL':100+np.arange(181)*.5,'HR':60+np.arange(181)%5})

    def test_future_changes_and_prefix_parity(self):
        t = self.times[120]
        original = make_features(self.frame,PROFILE,0).loc[t]
        prefix = make_features(self.frame[self.frame.Timestamp<=t],PROFILE,0).loc[t]
        changed = self.frame.copy()
        changed.loc[changed.Timestamp>t,['Dexcom GL','HR']] = 999
        altered = make_features(changed,PROFILE,0).loc[t]
        pd.testing.assert_series_equal(original,prefix)
        pd.testing.assert_series_equal(original,altered)
        self.assertAlmostEqual(original.cgm_slope_30m,.5)
        self.assertAlmostEqual(original.cgm_change_60m,30)
        self.assertEqual(original.cgm_count_60m,13)

    def test_clock_drift_is_rejected_without_dropping_minute_rate_hr_rows(self):
        drift=self.frame.copy()
        drift.loc[0,'Timestamp']+=pd.Timedelta(seconds=1)
        with self.assertRaisesRegex(ValueError,'whole minutes'):make_features(drift,PROFILE,0)
        for phase in range(5):
            built=make_features(self.frame,PROFILE,phase)
            self.assertEqual(len(built),37 if phase==0 else 36)
            self.assertGreater(built.hr_fraction_60m.iloc[-1],.99)

    def test_bounded_replay_window_matches_full_features_with_gaps_and_all_phases(self):
        from glucotwin.replay import issue_forecast
        class Capture:
            def predict(self,values):self.row=values.iloc[0].copy();return np.array([150.])
        times=pd.date_range('2026-01-01',periods=14*1440,freq='min')
        rng=np.random.default_rng(11)
        frame=pd.DataFrame({'Timestamp':times,'Dexcom GL':100+np.sin(np.arange(len(times))/40)*30+rng.normal(0,.5,len(times)),'HR':60+rng.normal(0,3,len(times))})
        frame.loc[frame.index%37==0,['Dexcom GL','HR']]=np.nan
        for phase in range(5):
            now=times[-60+phase]
            full=make_features(frame.loc[frame.Timestamp<=now],PROFILE,phase).loc[now]
            features=[c for c in full.index if c!='history_eligible'];model=Capture()
            patient=dict(split='validation',phase_utc_minutes_mod_5=phase,minimum_forecast_time=str(times[1440]))
            result=issue_forecast(frame,PROFILE,patient,dict(model=model,features=features),now)
            self.assertEqual(result['status'],'Forecast issued')
            pd.testing.assert_series_equal(model.row,full[features],check_dtype=False,rtol=1e-8,atol=1e-8)

    def test_missing_current_abstains(self):
        self.frame.loc[self.frame.Timestamp.eq(self.times[120]),'Dexcom GL'] = np.nan
        row = make_features(self.frame,PROFILE,0).loc[self.times[120]]
        self.assertFalse(row.history_eligible)

    def test_internal_gap_abstains(self):
        self.frame.loc[self.frame.Timestamp.between(self.times[75],self.times[85]),'Dexcom GL'] = np.nan
        row = make_features(self.frame,PROFILE,0).loc[self.times[120]]
        self.assertEqual(row.cgm_count_60m,10)
        self.assertEqual(row.cgm_max_gap_60m,20)
        self.assertFalse(row.history_eligible)

    def test_grid_follows_clock_not_row_positions(self):
        irregular = self.frame.drop(index=[1,2,3])
        actual = make_features(irregular,PROFILE,0).loc[self.times[120]]
        expected = make_features(self.frame,PROFILE,0).loc[self.times[120]]
        pd.testing.assert_series_equal(actual,expected)

    @local_only
    def test_prepared_targets_and_patient_splits(self):
        frame = pd.read_csv(ROOT/'data/processed/cgmacros_features.csv')
        self.assertTrue(frame.groupby('patient_id').split.nunique().eq(1).all())
        self.assertTrue((pd.to_datetime(frame.target_time)-pd.to_datetime(frame.prediction_time)).eq(pd.Timedelta(minutes=60)).all())
        row = frame.iloc[len(frame)//2]
        source = pd.read_csv(ROOT/f'data/raw/cgmacros/CGMacros/CGMacros-{int(row.patient_id):03d}/CGMacros-{int(row.patient_id):03d}.csv')
        source.Timestamp = pd.to_datetime(source.Timestamp)
        actual = source.loc[source.Timestamp.eq(pd.Timestamp(row.target_time)),'Dexcom GL'].iloc[0]
        self.assertAlmostEqual(actual,row.target_glucose_60m)

if __name__=='__main__': unittest.main()
