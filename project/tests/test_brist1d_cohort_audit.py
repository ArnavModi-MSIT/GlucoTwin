import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_brist1d_cohort import canonical_stream, recent_mask, target_support, metadata_records, aggregate, audit_participant


class CohortAuditTests(unittest.TestCase):
    def test_conflicts_invalid_values_and_logged_zero_are_distinct(self):
        data = pd.DataFrame({'timestamp': pd.to_datetime(['2024-01-01 00:00']*2 + ['2024-01-01 00:15']*2 + ['2024-01-01 00:30']),
                             'device': ['cgm']*5, 'bg': [5., 5., 6., 7., 0.], 'insulin': [np.nan]*4 + [0.]})
        glucose, info = canonical_stream(data, 'bg')
        self.assertEqual(glucose.tolist(), [5.])
        self.assertEqual(info['conflicting_timestamps'], 1)
        self.assertEqual(info['identical_extra_rows'], 1)
        self.assertEqual(info['invalid_rows'], 1)
        insulin, insulin_info = canonical_stream(data, 'insulin')
        self.assertEqual(insulin.tolist(), [0.])
        self.assertEqual(insulin_info['invalid_rows'], 0)

    def test_asof_latency_cannot_use_future_or_unavailable_readings(self):
        anchors = pd.DatetimeIndex(['2024-01-01 00:05', '2024-01-01 00:20'])
        stream = pd.Series([1., 2.], index=pd.DatetimeIndex(['2024-01-01 00:10', '2024-01-01 00:15']))
        np.testing.assert_array_equal(recent_mask(anchors, stream, 5), [False, True])
        np.testing.assert_array_equal(recent_mask(anchors, stream, 30, 10), [False, True])
        np.testing.assert_array_equal(recent_mask(anchors, stream, 30, 15), [False, False])

    def test_native_measured_targets_and_missing_meals_are_not_filled(self):
        times = pd.date_range('2024-01-01', periods=9, freq='15min')
        glucose = pd.Series([5.]*9, index=times)
        support = target_support(glucose, 15)
        self.assertEqual(support['eligible_history_anchors'], 5)
        self.assertEqual(support['horizons']['30']['exact_targets_with_history_screen'], 3)
        self.assertEqual(support['horizons']['60']['exact_targets_with_history_screen'], 1)
        missing = glucose.drop(times[6])
        self.assertEqual(target_support(missing, 15)['horizons']['30']['exact_targets_with_history_screen'], 1)
        frame = pd.DataFrame({'timestamp': times, 'device': 'cgm', 'bg': 5., 'activity': np.nan})
        for channel in ('insulin', 'carbs', 'hr', 'dist', 'steps', 'cals'):
            frame[channel] = np.nan
        report = audit_participant(frame)
        self.assertEqual(report['channels']['carbs']['zero_rows'], 0)
        self.assertEqual(report['channels']['carbs']['retained_timestamps'], 0)
        self.assertEqual(report['overlap']['insulin']['within_past5_minutes'], 0)

    def test_gender_and_approximate_duration_are_not_coerced(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'metadata.csv'
            pd.DataFrame({'Participant Number': ['01', '02'], 'How old are you?': ['24', '21'],
                          'What would you describe your gender as?': ['non binary', 'Cis Female '],
                          'How long have you had type 1 diabetes?': ['Just under 3 years', '15 years']}).to_csv(path, index=False)
            metadata = metadata_records(path)
            self.assertEqual(metadata['P01']['gender_category'], 'non_binary')
            self.assertIsNone(metadata['P01']['diabetes_duration_exact_years'])
            self.assertEqual(metadata['P02']['diabetes_duration_exact_years'], 15.)
            with self.assertRaisesRegex(ValueError, 'Unlinked'):
                aggregate([{'participant_id': 'P99'}], metadata)

    def test_public_aggregate_has_no_linked_participant_details(self):
        times = pd.date_range('2024-01-01', periods=9, freq='15min')
        frame = pd.DataFrame({'timestamp': times, 'device': 'cgm', 'bg': 5., 'activity': np.nan})
        for channel in ('insulin', 'carbs', 'hr', 'dist', 'steps', 'cals'):
            frame[channel] = np.nan
        record = {'participant_id': 'P01', 'source_sha256': 'private-hash', **audit_participant(frame)}
        metadata = {'P01': {'age': 24., 'gender_category': 'non_binary',
                             'diabetes_duration_exact_years': None},
                    'P02': {'age': 21., 'gender_category': 'female',
                             'diabetes_duration_exact_years': 15.}}
        result = aggregate([record], metadata)
        self.assertEqual(result['metadata']['linked_participants'], 1)
        self.assertEqual(result['metadata']['metadata_only_participants'], 1)
        self.assertEqual(result['channels']['bg']['retained_timestamps'], 9)
        self.assertEqual(result['overlap']['insulin']['fraction'], 0.)
        self.assertEqual(result['target_support']['horizons']['30']['exact_targets_with_history_screen'], 3)
        self.assertNotIn('participant_id', str(result))
        self.assertNotIn('P01', str(result))
        self.assertNotIn('private-hash', str(result))


if __name__ == '__main__':
    unittest.main()
