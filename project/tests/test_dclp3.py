"""Timing, censoring, pump state and disjoint-role regression checks."""
from pathlib import Path
import json
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from glucotwin.dclp3 import assign_roles, basal_integral, canonical_cgm, issue_times, make_features, measured_targets

PROTOCOL = json.loads((Path(__file__).resolve().parents[1]/'configs/dclp3_contract_v2.json').read_text())


class DCLP3Tests(unittest.TestCase):
    def test_native_issues_preserve_sensor_phase(self):
        raw = pd.Series([100., 105., 110.], index=pd.date_range('2001-01-01 00:02:44', periods=3, freq='5min'))
        issues = issue_times(raw, PROTOCOL)
        pd.testing.assert_index_equal(issues, raw.index+pd.Timedelta(minutes=5))
        self.assertEqual(issues[0].second, 44)

    def test_roles_disjoint_stratified_and_stable(self):
        ids = [str(i) for i in range(168)]
        roster = pd.DataFrame({'PtID': ids, 'RandDt': ['2001-01-01']*168,
                               'trtGroup': ['CLC']*112+['SAP']*56})
        pump_ids = set(ids[:125])
        roles = assign_roles(roster, pump_ids, PROTOCOL)
        self.assertEqual(roles, assign_roles(roster.sample(frac=1, random_state=99), pump_ids, PROTOCOL))
        self.assertEqual(len(roles['development']), 134)
        self.assertEqual(len(roles['reserved']), 34)
        evaluated = []
        for fold in roles['folds']:
            self.assertFalse(set(fold['fit']) & set(fold['evaluation']))
            self.assertFalse(set(roles['reserved']) & set(fold['fit']+fold['evaluation']))
            self.assertEqual(set(fold['fit']+fold['evaluation']), set(roles['development']))
            evaluated.extend(fold['evaluation'])
        self.assertEqual(sorted(evaluated), roles['development'])

    def test_measured_matching_ties_boundary_missing_and_delay(self):
        target = pd.Timestamp('2001-01-01 12:30:00')
        raw = pd.Series([110., 120., 39., 401.], index=pd.DatetimeIndex([
            target-pd.Timedelta(seconds=20), target+pd.Timedelta(seconds=20),
            target+pd.Timedelta(minutes=5), target+pd.Timedelta(minutes=10)]))
        issues = pd.DatetimeIndex([target-pd.Timedelta(minutes=30),
            target-pd.Timedelta(minutes=25), target-pd.Timedelta(minutes=20),
            target-pd.Timedelta(minutes=15)])
        out = measured_targets(raw, issues, 30, PROTOCOL)
        self.assertEqual(out['y'][0], 110.)
        self.assertEqual(out['offset_seconds'][0], -20)
        self.assertTrue(np.isnan(out['y'][1:]).all())
        np.testing.assert_array_equal(out['boundary'], [False, True, True, False])
        self.assertEqual(out['matched_time_ns'][0], (target-pd.Timedelta(seconds=20)).value)
        # Outcome reveal must use this actual timestamp + delay, not nominal time.
        reveal = pd.Timestamp(out['matched_time_ns'][0])+pd.Timedelta(minutes=5)
        self.assertEqual(reveal, target+pd.Timedelta(minutes=4, seconds=40))

    def test_conflict_is_barrier_and_identical_duplicates_reconcile(self):
        t = pd.date_range('2001-01-01', periods=3, freq='5min')
        raw, info = canonical_cgm([t[0], t[0], t[1], t[1], t[2]], [100, 100, 110, 111, 401], PROTOCOL)
        self.assertEqual(info['extra_identical_rows'], 1)
        self.assertEqual(info['conflicting_timestamps'], 1)
        self.assertTrue(np.isnan(raw.loc[t[1]]))
        self.assertEqual(raw.loc[t[2]], 401)

    def test_basal_expiry_known_zero_and_future_invariance(self):
        start = pd.Timestamp('2001-01-01')
        rate = pd.Series([2., 0.], index=pd.DatetimeIndex([start, start+pd.Timedelta(minutes=10)]))
        queries = pd.DatetimeIndex([start+pd.Timedelta(minutes=20), start+pd.Timedelta(minutes=60)])
        units, fraction = basal_integral(rate, queries, 30, 30)
        self.assertAlmostEqual(units[0], 2/6)
        self.assertAlmostEqual(fraction[0], 20/30)
        self.assertAlmostEqual(units[1], 0)
        self.assertAlmostEqual(fraction[1], 10/30)
        later = pd.concat([rate, pd.Series([20.], index=pd.DatetimeIndex([start+pd.Timedelta(minutes=61)]))])
        for a, b in zip(basal_integral(rate, queries, 30, 30), basal_integral(later, queries, 30, 30)):
            np.testing.assert_allclose(a, b, equal_nan=True)
        unknown_units, coverage = basal_integral(rate, pd.DatetimeIndex([start+pd.Timedelta(minutes=80)]), 30, 30)
        self.assertTrue(np.isnan(unknown_units[0]))
        self.assertEqual(coverage[0], 0)

    def test_features_ignore_future_and_mask_late_clinical_results(self):
        index = pd.date_range('2001-01-01', periods=45, freq='5min')
        raw = pd.Series(np.arange(45)+100., index=index)
        raw.iloc[25] = 401
        issue = pd.DatetimeIndex([index[30]])
        cut = issue[0]-pd.Timedelta(minutes=5)
        basal = pd.Series([1., 100.], index=pd.DatetimeIndex([index[20], index[31]]))
        bolus = pd.DataFrame({'amount': [2., 100.], 'kind': ['Standard', 'Extended']},
                             index=pd.DatetimeIndex([index[20], index[31]]))
        profile = {'hba1c': {'value': 15., 'available_at': index[31].isoformat()},
                   'age': {'value': 30., 'available_at': index[0].isoformat()}}
        full = make_features(raw, issue, profile, basal, bolus, PROTOCOL)
        prefix = make_features(raw.loc[:cut], issue, profile, basal.loc[:cut], bolus.loc[:cut], PROTOCOL)
        pd.testing.assert_frame_equal(full, prefix)
        self.assertTrue(np.isnan(full.profile_hba1c.iloc[0]))
        self.assertEqual(full.profile_age.iloc[0], 30)
        self.assertEqual(full.cgm_current.iloc[0], raw.loc[cut])
        self.assertTrue(full.history_eligible.iloc[0])

    def test_latest_conflict_withholds_and_boundary_proxy_retains_history(self):
        index = pd.date_range('2001-01-01', periods=30, freq='5min')
        raw = pd.Series(100., index=index)
        empty = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
        doses = pd.DataFrame(columns=['amount', 'kind'], index=pd.DatetimeIndex([]))
        issue = pd.DatetimeIndex([index[-1]+pd.Timedelta(minutes=5)])
        raw.iloc[-1] = np.nan
        result = make_features(raw, issue, {}, empty, doses, PROTOCOL)
        self.assertFalse(result.history_eligible.iloc[0])
        raw.iloc[-1] = 39
        result = make_features(raw, issue, {}, empty, doses, PROTOCOL)
        self.assertTrue(result.history_eligible.iloc[0])
        self.assertEqual(result.cgm_current.iloc[0], 40)
        self.assertEqual(result.cgm_current_code_low.iloc[0], 1)


if __name__ == '__main__':
    unittest.main()
