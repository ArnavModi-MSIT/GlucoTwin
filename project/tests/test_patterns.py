"""Past-only descriptive summaries, missing coverage and patient sampling phase."""
import sys
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from glucotwin.patterns import historical_patterns


class PatternTests(unittest.TestCase):
    def setUp(self):
        self.times=pd.date_range('2024-01-01',periods=3*288,freq='5min')
        self.values=np.full(len(self.times),100.)

    def test_future_changes_and_prefix_give_identical_summary(self):
        cutoff=self.times[300]
        a=historical_patterns(self.times,self.values,cutoff)
        changed=self.values.copy();changed[301:]=400
        self.assertEqual(a,historical_patterns(self.times,changed,cutoff))
        self.assertEqual(a,historical_patterns(self.times[:301],self.values[:301],cutoff))
        self.assertEqual(a['observed_samples'],301)
        self.assertEqual(a['daily'][-1]['expected'],13)

    def test_recurrence_requires_two_covered_complete_periods(self):
        self.values[:72]=200;self.values[288:360]=200
        a=historical_patterns(self.times,self.values,self.times[-1])
        self.assertEqual(a['periods'][0]['description'],'Repeated high readings')
        self.assertEqual(a['periods'][0]['high_days'],2)
        self.values[288:310]=np.nan
        b=historical_patterns(self.times,self.values,self.times[-1])
        self.assertEqual(b['periods'][0]['eligible_days'],2)
        self.assertEqual(b['periods'][0]['high_days'],1)
        self.assertNotEqual(b['periods'][0]['description'],'Repeated high readings')

    def test_reference_boundaries_and_missing_denominator(self):
        a=historical_patterns(self.times[:5],[69,70,180,181,np.nan],self.times[4])
        r=a['daily'][0]
        self.assertEqual((r['samples'],r['expected'],r['coverage']),(4,5,.8))
        self.assertEqual((r['low_fraction'],r['reference_fraction'],r['high_fraction']),(.25,.5,.25))

    def test_patient_phase_and_seven_dates(self):
        times=pd.date_range('2024-01-01T00:03',periods=10*288,freq='5min')
        a=historical_patterns(times,np.full(len(times),100),times[-1])
        self.assertEqual(len(a['daily']),7)
        self.assertTrue(all(r['samples']==r['expected']==288 for r in a['daily']))

    def test_no_history_and_unknown_values(self):
        self.assertEqual(historical_patterns(self.times,self.values,'2023-01-01')['daily'],[])
        a=historical_patterns(self.times,np.full(len(self.times),np.nan),self.times[-1])
        self.assertEqual(a['observed_samples'],0)
        self.assertIsNone(a['daily'][0]['mean'])
        self.assertTrue(all(r['eligible_days']==0 for r in a['periods']))


if __name__=='__main__':unittest.main()
