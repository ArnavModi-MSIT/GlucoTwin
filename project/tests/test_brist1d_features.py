import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'scripts'))
from glucotwin.brist1d import make_brist_features, issue_times, measured_targets, feature_arms, assign_roles
from run_brist1d_study import load_development_frame, paired_comparison, patient_rows, matrix


class BrisFeatureTests(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads((ROOT/'configs/brist1d_contract_v1.json').read_text())
        self.profile = {'age': 24., 'diabetes_duration_exact_years': None, 'gender_category': 'non_binary'}

    def streams(self, cadence=5):
        grid = pd.date_range('2024-01-01', periods=61, freq=f'{cadence}min')
        empty = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
        streams = {channel: empty.copy() for channel in ('bg', 'insulin', 'carbs', 'hr', 'steps', 'dist', 'cals')}
        streams['bg'] = pd.Series(5.+np.arange(len(grid))*.1, index=grid)
        return streams

    def test_forecast_target_is_after_issue_not_data_cutoff(self):
        for cadence in (5, 15):
            streams = self.streams(cadence)
            issues = issue_times(streams['bg'], cadence, 5)
            row = 10
            self.assertEqual(issues[row], streams['bg'].index[row]+pd.Timedelta(minutes=cadence))
            features = make_brist_features(streams, self.profile, cadence, issues, self.protocol)
            self.assertAlmostEqual(features.cgm_current.iloc[row], streams['bg'].iloc[row]*18.0182)
            target = measured_targets(streams['bg'], issues, 30)[row]
            expected = streams['bg'].loc[issues[row]+pd.Timedelta(minutes=30)]*18.0182
            self.assertAlmostEqual(target, expected)
            earlier_target = streams['bg'].loc[streams['bg'].index[row]+pd.Timedelta(minutes=30)]*18.0182
            self.assertNotEqual(target, earlier_target)

    def test_unavailable_readings_cannot_change_current_features(self):
        streams = self.streams()
        grid = streams['bg'].index
        for channel in ('insulin', 'carbs', 'hr', 'steps', 'dist', 'cals'):
            streams[channel] = pd.Series(np.arange(len(grid), dtype=float), index=grid)
        now = grid[30]+pd.Timedelta(minutes=5)
        issues = pd.DatetimeIndex([now])
        expected = make_brist_features(streams, self.profile, 5, issues, self.protocol)
        changed = {channel: values.copy() for channel, values in streams.items()}
        prefix = {}
        for channel, values in streams.items():
            cutoff = now-pd.Timedelta(minutes=self.protocol['availability_delay_minutes'][channel])
            changed[channel].loc[values.index > cutoff] = 99999.
            prefix[channel] = values.loc[values.index <= cutoff]
        pd.testing.assert_frame_equal(expected, make_brist_features(changed, self.profile, 5, issues, self.protocol))
        pd.testing.assert_frame_equal(expected, make_brist_features(prefix, self.profile, 5, issues, self.protocol))

    def test_logged_zero_is_distinct_from_absent_dose_or_meal(self):
        streams = self.streams()
        now = streams['bg'].index[30]+pd.Timedelta(minutes=5)
        issues = pd.DatetimeIndex([now])
        absent = make_brist_features(streams, self.profile, 5, issues, self.protocol).iloc[0]
        self.assertTrue(np.isnan(absent.insulin_sum_60m))
        self.assertEqual(absent.insulin_count_60m, 0)
        self.assertTrue(np.isnan(absent.carbs_sum_60m))
        self.assertEqual(absent.carbs_count_60m, 0)
        streams['insulin'] = pd.Series(0., index=streams['bg'].index)
        recorded = make_brist_features(streams, self.profile, 5, issues, self.protocol).iloc[0]
        self.assertEqual(recorded.insulin_sum_60m, 0)
        self.assertEqual(recorded.insulin_count_60m, 12)
        self.assertEqual(recorded.insulin_fraction_60m, 1)
        self.assertEqual(recorded.profile_gender_non_binary, 1)
        self.assertTrue(np.isnan(recorded.profile_duration_years))

    def test_warmup_missing_targets_and_stale_history(self):
        streams = self.streams(15)
        issues = issue_times(streams['bg'], 15, 5)
        features = make_brist_features(streams, self.profile, 15, issues, self.protocol)
        self.assertFalse(features.history_eligible.iloc[0])
        self.assertTrue(features.history_eligible.iloc[10])
        target_time = issues[10]+pd.Timedelta(minutes=60)
        without_target = streams['bg'].drop(target_time)
        self.assertTrue(np.isnan(measured_targets(without_target, issues, 60)[10]))
        old = {channel: values.loc[values.index <= streams['bg'].index[4]] for channel, values in streams.items()}
        self.assertFalse(make_brist_features(old, self.profile, 15, pd.DatetimeIndex([issues[10]]), self.protocol).history_eligible.iloc[0])

    def test_roles_are_disjoint_and_shared_temporal_features_match(self):
        entries = [{'participant_id': f'P{i:02d}', 'channels': {'bg': {'modal_gap_minutes': 15. if i <= 5 else 5.}}} for i in range(1, 21)]
        roles = assign_roles(entries, 2026)
        self.assertEqual(roles, assign_roles(entries, 2026))
        self.assertEqual(len(roles['reserved']), 4)
        seen = []
        for fold in roles['folds']:
            self.assertEqual(len(fold['fit']), 12)
            self.assertEqual(len(fold['evaluation']), 4)
            self.assertFalse(set(fold['fit']) & set(fold['evaluation']))
            self.assertFalse(set(roles['reserved']) & (set(fold['fit']) | set(fold['evaluation'])))
            seen.extend(fold['evaluation'])
        self.assertEqual(sorted(seen), roles['development'])
        arms = feature_arms(['cgm_current', 'clock_sin', 'profile_age', 'insulin_sum_60m', 'carbs_sum_60m', 'hr_mean_60m'])
        self.assertEqual(arms['cgm_only'], [0, 1])
        self.assertEqual(arms['cgm_profile'], [0, 1, 2])
        self.assertEqual(arms['fused'], list(range(6)))

    def test_reserved_sensor_access_is_refused_before_io(self):
        calls = []
        def forbidden(*args, **kwargs):
            calls.append(args)
            raise AssertionError('Reserved sensor was opened')
        manifest = {'development': ['P01'], 'reserved': ['P02'], 'participants': {}}
        with self.assertRaisesRegex(ValueError, 'Refusing reserved'):
            load_development_frame('P02', manifest, source=Path('does-not-exist'), reader=forbidden)
        self.assertEqual(calls, [])

    def test_train_sampling_and_pairing_use_same_patients_and_targets(self):
        records = {pid: {'X': np.arange(20).reshape(10, 2), 'y30': np.arange(10, dtype=float)} for pid in ('P01', 'P02')}
        first = matrix(records, ['P01', 'P02'], 30, 4, 2026)
        second = matrix(records, ['P01', 'P02'], 30, 4, 2026)
        for left, right in zip(first, second):
            np.testing.assert_array_equal(left, right)
        self.assertEqual(len(first[1]), 8)
        actual = np.array([60., 100., 200., 65., 110., 220.])
        groups = np.array(['P01']*3+['P02']*3)
        reference = patient_rows(actual, actual+10, groups)
        candidate = patient_rows(actual, actual+5, groups)
        comparison = paired_comparison(candidate, reference, 100, 2026)
        self.assertEqual(comparison['all_mae']['mean_difference'], -5.)
        self.assertEqual(comparison['low_mae']['patients'], 2)
        with self.assertRaisesRegex(ValueError, 'Unmatched'):
            paired_comparison(candidate[:1], reference, 100, 2026)


if __name__ == '__main__':
    unittest.main()
