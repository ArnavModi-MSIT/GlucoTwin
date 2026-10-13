"""Causal research decisions, frozen roles and delayed event outcomes."""
import copy
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from glucotwin.features import make_features
from glucotwin.event_replay import issue_event, reveal_events, validate_event_artifact


class ScoreModel:
    def __init__(self, score=.8):
        self.score = score
        self.seen = None
    def predict_proba(self, features):
        self.seen = features.copy()
        return np.array([[1 - self.score, self.score]])


class EventReplayTests(unittest.TestCase):
    def setUp(self):
        times = pd.date_range('2024-01-01', periods=150, freq='min')
        self.frame = pd.DataFrame({'Timestamp': times, 'Dexcom GL': 120., 'HR': 70.})
        self.now = times[60]
        self.patient = {'patient_id': 1, 'split': 'validation', 'phase_utc_minutes_mod_5': 0,
                        'minimum_forecast_time': self.now.isoformat()}
        self.profile = dict(age=40., gender_f=1., bmi=23., hba1c_pct=5.4, fasting_glucose=100.)
        self.columns = list(make_features(self.frame, self.profile, 0).drop(columns='history_eligible'))
        self.role = {'fit': [2], 'threshold': [3], 'evaluation': [1]}
        self.artifact = dict(model=ScoreModel(), features=self.columns, threshold=.5,
                             roles=self.role, method='fused', protocol_sha256='protocol',
                             input_manifest_sha256='inputs', probability_display_approved=False,
                             operational_alerts_approved=False, score_kind='uncalibrated ranking score')

    def issue(self, frame=None, now=None, ledger=None):
        return issue_event(self.frame if frame is None else frame, self.profile, self.patient,
                           self.artifact, self.now if now is None else now, ledger or [])

    def test_future_sensor_changes_do_not_change_features_or_score(self):
        original = self.issue()
        first = self.artifact['model'].seen.copy()
        changed = self.frame.copy()
        changed.loc[changed.Timestamp > self.now, ['Dexcom GL', 'HR']] = [999., -999.]
        replay = self.issue(changed)
        pd.testing.assert_frame_equal(first, self.artifact['model'].seen)
        self.assertEqual(original, replay)
        self.assertTrue(all(c in first for c in ('age', 'hba1c_pct', 'cgm_current', 'hr_mean_60m')))

    def test_frozen_score_and_cooldown_boundary(self):
        first = self.issue()
        self.assertTrue(first['research_flag'])
        self.assertEqual(self.issue(now=self.now+pd.Timedelta(minutes=30), ledger=[first])['status'], 'Cooldown')
        self.assertTrue(self.issue(now=self.now+pd.Timedelta(minutes=60), ledger=[first])['research_flag'])
        self.artifact['model'].score = .1
        self.assertEqual(first['score'], .8)
        self.assertEqual(self.issue()['status'], 'Below cutoff')

    def test_sustained_onset_reveals_only_at_45_minutes_and_does_not_mutate(self):
        frame = self.frame.copy()
        onset = self.now + pd.Timedelta(minutes=20)
        frame.loc[frame.Timestamp.between(onset, onset+pd.Timedelta(minutes=15)), 'Dexcom GL'] = 210.
        issued = self.issue(frame)
        frozen = copy.deepcopy(issued)
        for minutes in (0, 30, 40, 44):
            shown = reveal_events([issued], frame, self.patient, self.now+pd.Timedelta(minutes=minutes))[0]
            self.assertEqual(shown['outcome'], 'Pending')
            self.assertIsNone(shown['event_at'])
            self.assertIsNone(shown['lead_minutes'])
        shown = reveal_events([issued], frame, self.patient, self.now+pd.Timedelta(minutes=45))[0]
        self.assertEqual(shown['outcome'], 'Qualifying onset observed')
        self.assertEqual(shown['event_at'], onset)
        self.assertEqual(shown['lead_minutes'], 20.)
        self.assertEqual(issued, frozen)

    def test_negative_missing_and_no_interpolation(self):
        row = self.issue()
        due = self.now + pd.Timedelta(minutes=45)
        self.assertEqual(reveal_events([row], self.frame, self.patient, due)[0]['outcome'], 'No qualifying onset')
        broken = self.frame.loc[self.frame.Timestamp != self.now+pd.Timedelta(minutes=25)]
        self.assertEqual(reveal_events([row], broken, self.patient, due)[0]['outcome'], 'Incomplete observations')
        short = self.frame.copy()
        short.loc[short.Timestamp == self.now+pd.Timedelta(minutes=20), 'Dexcom GL'] = 230.
        self.assertEqual(reveal_events([row], short, self.patient, due)[0]['outcome'], 'No qualifying onset')

    def test_warmup_high_and_missing_history_withhold_decisions(self):
        self.patient['minimum_forecast_time'] = (self.now+pd.Timedelta(minutes=5)).isoformat()
        self.assertEqual(self.issue()['status'], '24-hour warm-up')
        self.patient['minimum_forecast_time'] = self.now.isoformat()
        high = self.frame.copy(); high.loc[high.Timestamp == self.now, 'Dexcom GL'] = 181.
        row = self.issue(high)
        self.assertEqual(row['status'], 'Already above high threshold')
        self.assertIsNone(row['score'])
        self.assertEqual(reveal_events([row], high, self.patient, self.now)[0]['outcome'], 'Not evaluated')
        missing = self.frame.copy(); missing.loc[missing.Timestamp <= self.now, 'Dexcom GL'] = np.nan
        self.assertIsNone(self.issue(missing)['score'])

    def test_frozen_roles_hashes_cutoff_and_fusion_are_enforced(self):
        def validate(a):
            return validate_event_artifact(a, self.patient, self.role, 'protocol', 'inputs', self.columns, .5)
        self.assertIs(validate(self.artifact), self.artifact)
        for key, value in [('threshold', .6), ('protocol_sha256', 'changed'),
                           ('input_manifest_sha256', 'changed'), ('operational_alerts_approved', True),
                           ('probability_display_approved', True), ('features', ['cgm_current']), ('method', 'cgm_only')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(dict(self.artifact, **{key: value}))
        self.role['fit'].append(1)
        with self.assertRaisesRegex(ValueError, 'overlap'):validate(self.artifact)

    def test_reserved_and_fitting_patients_cannot_be_scored(self):
        self.patient['split'] = 'test'
        with self.assertRaisesRegex(ValueError, 'Reserved'):self.issue()
        self.patient['split'] = 'train'; self.patient['patient_id'] = 2
        with self.assertRaisesRegex(ValueError, 'outer-evaluation'):self.issue()


if __name__ == '__main__':
    unittest.main()
