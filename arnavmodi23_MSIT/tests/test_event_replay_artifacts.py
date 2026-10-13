"""Opt-in parity checks against saved outer-fold models, using development only."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from local_only import local_only
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import serve_dashboard as web
from glucotwin.features import make_features
from glucotwin.event_replay import issue_event


@local_only
class EventReplayArtifactTests(unittest.TestCase):
    def test_all_six_replay_patients_use_excluded_fold_and_prefix_parity(self):
        for pid in web.catalog('cgmacros'):
            replay = web.Replay('cgmacros', pid)
            self.assertIsNotNone(replay.event_artifact, replay.event_error)
            a = replay.event_artifact
            self.assertIn(pid, a['roles']['evaluation'])
            self.assertNotIn(pid, a['roles']['fit'] + a['roles']['threshold'])
            features = make_features(replay.frame, replay.profile, replay.patient['phase_utc_minutes_mod_5'])
            x = features.loc[features.history_eligible & (features.cgm_current <= 180) &
                             (features.index >= replay.clock[replay.start]), a['features']]
            for index in sorted(set([0, len(x)//2, len(x)-1])):
                now = x.index[index]
                expected = float(a['model'].predict_proba(x.iloc[[index]])[0, 1])
                result = issue_event(replay.frame, replay.profile, replay.patient, a, now, [])
                self.assertAlmostEqual(result['score'], expected, places=7)
                poisoned = replay.frame.copy()
                poisoned.loc[poisoned.Timestamp > now, ['Dexcom GL', 'HR']] = [999., -999.]
                self.assertEqual(result, issue_event(poisoned, replay.profile, replay.patient, a, now, []))

    def test_missing_optional_event_artifact_keeps_numerical_replay_working(self):
        with patch.object(web, 'load_event_artifact', side_effect=FileNotFoundError):
            replay = web.Replay('cgmacros', next(iter(web.catalog('cgmacros'))))
            result = replay.snapshot()
        self.assertFalse(result['event_research']['available'])
        self.assertEqual(result['event_research']['ledger'], [])
        self.assertTrue(np.isfinite(result['forecasts'][0]['prediction']))


if __name__ == '__main__':
    unittest.main()
