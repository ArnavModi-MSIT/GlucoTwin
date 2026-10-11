from pathlib import Path
import sys
import unittest

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from glucotwin.dclp3_study import matrix, equal_patient_weights, patient_rows, summarize, paired_comparison, row_digest


class StudyTests(unittest.TestCase):
    def records(self):
        return {pid: {'X': np.arange(30, dtype=np.float32).reshape(10, 3),
                      'y30': np.arange(10, dtype=float)+100,
                      'times': np.arange(10, dtype=np.int64),
                      'strict30': np.arange(10)%2 == 0} for pid in ('1', '2')}

    def test_reserve_rejected_before_record_lookup(self):
        with self.assertRaises(ValueError):
            matrix({}, ['3'], 30, 4, 2026, ['1', '2'])

    def test_sampling_identical_for_common_patients_across_cohorts(self):
        records = self.records()
        full = matrix(records, ['2', '1'], 30, 4, 2026, ['1', '2'])
        pump = matrix(records, ['1'], 30, 4, 2026, ['1', '2'])
        for key in ('X', 'y', 'times', 'strict'):
            np.testing.assert_array_equal(full[key][full['groups'] == '1'], pump[key])
        self.assertEqual(row_digest(full), row_digest(matrix(records, ['1', '2'], 30, 4, 2026, ['1', '2'])))
        altered = dict(full)
        altered['times'] = full['times']+1
        self.assertNotEqual(row_digest(full), row_digest(altered))

    def test_equal_patient_mass_with_unequal_counts(self):
        groups = np.array(['1', '1', '2'])
        weights = equal_patient_weights(groups)
        self.assertAlmostEqual(weights[groups == '1'].sum(), weights[groups == '2'].sum())
        self.assertAlmostEqual(weights.mean(), 1)

    def test_pooled_macro_strict_and_pairing(self):
        y = np.array([60., 100., 200.])
        pred = np.array([70., 120., 230.])
        groups = np.array(['1', '1', '2'])
        rows = patient_rows(y, pred, y, groups, np.array([True, False, True]))
        scores = summarize(rows)
        self.assertEqual(scores['mae'], 20)
        self.assertEqual(scores['patient_macro_slices']['all']['mean_patient_mae'], 22.5)
        self.assertEqual(scores['pooled_slices']['strict']['rows'], 2)
        self.assertEqual(scores['pooled_slices']['strict']['mae'], 20)
        self.assertEqual(scores['pooled_slices']['low']['mae'], 10)
        same = paired_comparison(rows, rows)
        self.assertEqual(same['all_mae']['mean_difference'], 0)
        with self.assertRaises(ValueError):
            paired_comparison(rows, rows[:1])

    def test_eval_outlier_does_not_enter_preprocessing(self):
        train = np.array([[1., np.nan], [2., 10.], [3., 20.]])
        pipe = make_pipeline(SimpleImputer(strategy='median', add_indicator=True), StandardScaler(), Ridge(alpha=10))
        pipe.fit(train, [100., 110., 120.])
        median, mean = pipe[0].statistics_.copy(), pipe[1].mean_.copy()
        pipe.predict(np.array([[1e9, -1e9]]))
        np.testing.assert_array_equal(pipe[0].statistics_, median)
        np.testing.assert_array_equal(pipe[1].mean_, mean)
        self.assertEqual(median[1], 15)


if __name__ == '__main__':
    unittest.main()
