import unittest
import numpy as np
import pandas as pd
from glucotwin.research_features import extend_history


class ResearchFeatureTests(unittest.TestCase):
    def test_future_changes_do_not_change_past_features(self):
        index = pd.date_range('2024-01-01', periods=400, freq='5min')
        frame = pd.DataFrame({'cgm_current': np.arange(400, dtype=float)}, index=index)
        full = extend_history(frame)
        prefix = extend_history(frame.iloc[:300])
        pd.testing.assert_frame_equal(full.iloc[:300], prefix)
        changed = frame.copy(); changed.iloc[300:] = 9999
        pd.testing.assert_frame_equal(full.iloc[:300], extend_history(changed).iloc[:300])

    def test_lags_and_missingness_are_preserved(self):
        index = pd.date_range('2024-01-01', periods=30, freq='5min')
        frame = pd.DataFrame({'cgm_current': np.arange(30, dtype=float)}, index=index)
        frame.iloc[3] = np.nan
        result = extend_history(frame)
        self.assertTrue(np.isnan(result.cgm_lag_5m.iloc[4]))
        self.assertEqual(result.cgm_lag_120m.iloc[29], 5.)
        self.assertTrue(np.isnan(result.cgm_lag_120m.iloc[0]))


if __name__ == '__main__':
    unittest.main()
