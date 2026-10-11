import sys,unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_brist1d_streams import audit


class BrisAuditTests(unittest.TestCase):
    def test_asynchronous_duplicates_and_missing_actions(self):
        frame=pd.DataFrame({'timestamp':['2024-01-01 00:00']*3+['2024-01-01 00:15']*2,
                            'device':['cgm','cgm','pump','cgm','cgm'],
                            'bg':[5.,5.,np.nan,6.,7.], 'insulin':[np.nan,np.nan,0.,np.nan,np.nan],
                            'carbs':[np.nan]*5,'hr':[np.nan]*5})
        result=audit(frame)
        self.assertEqual(result['channels']['bg']['retained_unambiguous_timestamps'],1)
        self.assertEqual(result['channels']['bg']['conflicting_timestamp_values'],1)
        self.assertEqual(result['channels']['insulin']['zero_rows'],1)
        self.assertEqual(result['channels']['carbs']['zero_rows'],0)
        self.assertEqual(result['past_observation_overlap']['hr']['matched'],0)

    def test_future_sensor_is_not_matched(self):
        frame=pd.DataFrame({'timestamp':['2024-01-01 00:00','2024-01-01 00:05'],
                            'device':['cgm','pump'],'bg':[5.,np.nan],'insulin':[np.nan,1.],
                            'carbs':[np.nan,np.nan],'hr':[np.nan,np.nan]})
        self.assertEqual(audit(frame)['past_observation_overlap']['insulin']['matched'],0)
