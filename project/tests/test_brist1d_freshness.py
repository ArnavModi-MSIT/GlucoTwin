import json
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'scripts'))
from glucotwin.brist1d_freshness import repair_freshness, diagnostic_masks
from glucotwin.brist1d import make_brist_features, issue_times, feature_arms
from glucotwin.regression_diagnostics import error_summary
from diagnose_brist1d_freshness import summarize_slices


class FreshnessTests(unittest.TestCase):
    def test_cap_boundary_unknown_zero_and_nonmutation(self):
        frame = pd.DataFrame({'insulin_age_minutes': [30., 31., 1e6, np.nan],
                              'insulin_latest_observed': [0., 2., 3., np.nan],
                              'insulin_sum_120m': [0., 2., np.nan, np.nan],
                              'cgm_current': [100.]*4})
        before = frame.copy(deep=True)
        fixed = repair_freshness(frame, {'insulin': 30})
        np.testing.assert_allclose(fixed.insulin_age_minutes, [30, 30, 30, np.nan], equal_nan=True)
        np.testing.assert_array_equal(fixed.insulin_stale, [0, 1, 1, 0])
        np.testing.assert_array_equal(fixed.insulin_unobserved, [0, 0, 0, 1])
        self.assertEqual(fixed.insulin_latest_observed.iloc[0], 0)
        self.assertTrue(fixed.insulin_latest_observed.iloc[1:].isna().all())
        pd.testing.assert_series_equal(fixed.insulin_sum_120m, frame.insulin_sum_120m)
        pd.testing.assert_frame_equal(frame, before)

    def test_invalid_rules_and_age_fail(self):
        frame = pd.DataFrame({'hr_age_minutes': [5.], 'hr_latest_observed': [60.]})
        for cap in (0, -1, np.inf, np.nan):
            with self.assertRaises(ValueError): repair_freshness(frame, {'hr': cap})
        for age in (-1, np.inf):
            frame.hr_age_minutes = age
            with self.assertRaises(ValueError): repair_freshness(frame, {'hr': 30})

    def test_native_cadences_future_insertion_and_shared_rows(self):
        protocol = json.loads((ROOT/'configs/brist1d_contract_v1.json').read_text())
        caps = json.loads((ROOT/'configs/brist1d_freshness_v2.json').read_text())['freshness_caps_minutes']
        profile = {'age': 24., 'diabetes_duration_exact_years': None, 'gender_category': 'non_binary'}
        for cadence in (5, 15):
            grid = pd.date_range('2024-01-01', periods=61, freq=f'{cadence}min')
            streams = {c: pd.Series(np.ones(len(grid)), index=grid) for c in ('bg', 'insulin', 'carbs', 'hr', 'steps', 'dist', 'cals')}
            issues = issue_times(streams['bg'], cadence, 5)[:30]
            old = make_brist_features(streams, profile, cadence, issues, protocol)
            fixed = repair_freshness(old, caps)
            changed = {c: s.copy() for c, s in streams.items()}
            for channel in streams:
                changed[channel].loc[issues[-1]+pd.Timedelta(days=10)] = 99999.
            rebuilt = repair_freshness(make_brist_features(changed, profile, cadence, issues, protocol), caps)
            pd.testing.assert_frame_equal(fixed, rebuilt)
            pd.testing.assert_series_equal(fixed.history_eligible, old.history_eligible)
            pd.testing.assert_index_equal(fixed.index, old.index)
            names = old.drop(columns='history_eligible').columns.tolist()
            new_names = fixed.drop(columns='history_eligible').columns.tolist()
            for arm in ('cgm_only', 'cgm_profile'):
                old_columns = [names[i] for i in feature_arms(names)[arm]]
                new_columns = [new_names[i] for i in feature_arms(new_names)[arm]]
                self.assertEqual(old_columns, new_columns)
                pd.testing.assert_frame_equal(fixed[new_columns], old[old_columns])

    def test_diagnostics_partition_and_current_not_future_bins(self):
        features = pd.DataFrame({'cgm_current': [60., 100., 200.], 'cgm_native_cadence_minutes': [5,15,5],
                                 'cgm_slope_15m': [-1.,0.,1.], 'insulin_age_minutes': [30.,360.,np.nan],
                                 'carbs_age_minutes': [31.,361.,np.nan], 'hr_age_minutes': [30.,120.,np.nan]})
        masks = diagnostic_masks(features, np.array([200.,60.,100.]), np.array([70.,80.,180.]))
        bins = [mask for name, mask in masks.items() if name.startswith('current_')]
        np.testing.assert_array_equal(np.sum(bins, axis=0), np.ones(3))
        np.testing.assert_array_equal(masks['current_-inf_to_70'], [True,False,False])
        np.testing.assert_array_equal(masks['actual_low'], [False,True,False])
        ages = [mask for name, mask in masks.items() if name.startswith('insulin_age_') or name == 'insulin_never_observed']
        np.testing.assert_array_equal(np.sum(ages, axis=0), np.ones(3))

    def test_diagnostic_macro_is_not_row_weighted_and_bias_sign(self):
        small = error_summary(np.array([60.]), np.array([70.]))
        large = error_summary(np.array([60.]*9), np.array([90.]*9))
        rows = [{'slices': {'all': small, 'actual_low': small}, 'delta_variance_ratio': None},
                {'slices': {'all': large, 'actual_low': large}, 'delta_variance_ratio': .2}]
        result = summarize_slices(rows)
        self.assertEqual(result['slices']['all']['row_mae'],28.)
        self.assertEqual(result['slices']['all']['row_bias'],28.)
        self.assertEqual(result['slices']['all']['patient_macro_mae'],20.)
        self.assertEqual(result['slices']['all']['patients_with_rows'],2)
        self.assertEqual(result['patient_low_mae_distribution']['quantiles_min_p25_median_p75_max'][2],20.)
        self.assertEqual(result['delta_ratio_patients'],1)


if __name__ == '__main__': unittest.main()
