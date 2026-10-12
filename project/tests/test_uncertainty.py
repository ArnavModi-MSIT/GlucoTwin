import json
import sys
import tempfile
import unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from glucotwin.uncertainty import residual_radius,load_intervals,attach_interval,fingerprint
from glucotwin.rbg_replay import reveal_rbg_outcomes


class UncertaintyTests(unittest.TestCase):
    def test_finite_sample_rank_and_bad_inputs(self):
        self.assertEqual(residual_radius(range(1,11),.8),9)
        for values in ([],[float('nan')],[[1,2]],[1]):
            with self.assertRaises(ValueError):residual_radius(values)

    def test_optional_file_scope_and_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'artifacts').mkdir()
            self.assertEqual(load_intervals(root,'rbg','a')[0],{})
            model=root/'artifacts/model.joblib';model.write_bytes(b'trusted model fingerprint fixture')
            item=dict(horizon=30,radius=20.,nominal=.9,calibration_patients=['c'],assessment_patients=['a'],model_path='artifacts/model.joblib',model_sha256=fingerprint(model),assessment=dict(coverage=.85,patients=1))
            path=root/'artifacts/forecast_intervals.json'
            path.write_text(json.dumps(dict(version='residual-interval-v1',cohorts=dict(rbg=[item]))))
            self.assertIn(30,load_intervals(root,'rbg','a')[0])
            self.assertEqual(load_intervals(root,'rbg','c')[0],{})
            model.write_bytes(b'changed model')
            self.assertEqual(load_intervals(root,'rbg','a')[0],{})

    def test_bounds_frozen_until_outcome_available(self):
        interval=dict(radius=30.,nominal=.9,assessment=dict(coverage=.88,patients=17))
        row=dict(issued_at=pd.Timestamp('2024-01-01'),target_time=pd.Timestamp('2024-01-01 00:30'),available_at=pd.Timestamp('2024-01-01 00:35'),prediction=20.,persistence=20.)
        attach_interval(row,interval)
        self.assertEqual(row['interval_lower'],-10.)  # no cosmetic clipping
        frame=pd.DataFrame(dict(ts=[row['target_time']],GlucoseCGM=[999.]))
        pending=reveal_rbg_outcomes([row],frame,'2024-01-01 00:30').iloc[0]
        self.assertTrue(pd.isna(pending.actual));self.assertEqual(pending.interval_upper,50.)
        revealed=reveal_rbg_outcomes([row],frame,'2024-01-01 00:35').iloc[0]
        self.assertEqual(revealed.actual,999.);self.assertEqual(revealed.interval_upper,50.)
        self.assertNotIn('interval_lower',attach_interval({'prediction':None},interval))
        self.assertNotIn('interval_lower',attach_interval({'prediction':10.},None))
