import sys,unittest
from pathlib import Path
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from glucotwin.episodes import onsets,alarm_times,assess

class EpisodeTests(unittest.TestCase):
    def setUp(self):self.ts=pd.date_range('2024-01-01',periods=40,freq='5min')
    def test_sustained_onset_and_gap_break(self):
        g=pd.Series(100.,index=self.ts);g.iloc[10:15]=200
        self.assertEqual(list(onsets(g,'high')),[self.ts[10]])
        g.iloc[12]=np.nan;self.assertEqual(len(onsets(g,'high')),0)
    def test_past_only_cooldown(self):
        scores=np.ones(40)
        alarms=alarm_times(self.ts,scores,.5)
        self.assertEqual(list(alarms),list(self.ts[[0,12,24,36]]))
    def test_one_match_unknown_and_false(self):
        g=pd.Series(100.,index=self.ts);g.iloc[10:15]=200
        episodes=onsets(g,'high')
        alarms=pd.DatetimeIndex([self.ts[4],self.ts[5],self.ts[25],self.ts[39]])
        result=assess(alarms,episodes,self.ts,g)
        self.assertEqual(result['detected_episodes'],1)
        self.assertEqual(result['redundant_alarms'],1)
        self.assertEqual(result['false_alarms'],1)
        self.assertEqual(result['unknown_alarms'],1)
        self.assertEqual(result['median_lead_minutes'],30)
    def test_missing_future_does_not_make_negative(self):
        g=pd.Series(100.,index=self.ts);g.iloc[8]=np.nan
        result=assess(pd.DatetimeIndex([self.ts[0]]),pd.DatetimeIndex([]),self.ts,g)
        self.assertEqual(result['unknown_alarms'],1);self.assertEqual(result['false_alarms'],0)

if __name__=='__main__':unittest.main()
