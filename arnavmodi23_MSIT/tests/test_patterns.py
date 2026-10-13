"""Past-only descriptive summaries, missing coverage and patient sampling phase."""
import sys
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from glucotwin.patterns import historical_patterns,descriptive_profile,observed_excursions


class PatternTests(unittest.TestCase):
    def setUp(self):
        self.times=pd.date_range('2024-01-01',periods=3*288,freq='5min')
        self.values=np.full(len(self.times),100.)

    def test_hourly_partial_current_hour_and_missing_coverage(self):
        values=np.array([69,70,180,181]+[np.nan]*8+[100])
        summary=historical_patterns(self.times[:13],values,self.times[12])
        first,current=summary['hourly']
        self.assertEqual((first['samples'],first['expected']),(4,12))
        self.assertEqual(first['mean'],125.)
        self.assertEqual((first['minimum'],first['maximum']),(69.,181.))
        self.assertEqual((first['low_fraction'],first['reference_fraction'],first['high_fraction']),(.25,.5,.25))
        self.assertTrue(first['complete_hour']);self.assertFalse(first['comparable'])
        self.assertEqual((current['hour'],current['samples'],current['expected']),(1,1,1))
        self.assertFalse(current['complete_hour']);self.assertFalse(current['comparable'])
        self.assertTrue(all(pd.Timestamp(r['last_checkpoint'])<=self.times[12] for r in summary['hourly']))

    def test_observed_runs_require_four_readings_and_strict_band_boundaries(self):
        values=[180,181,200,201,181,180,70,69,60,59,69,70,181,181,181,180]
        rows=historical_patterns(self.times[:16],values,self.times[15])['excursions']
        self.assertEqual([r['kind'] for r in rows],['high','low'])
        self.assertTrue(all(r['samples']==4 and r['observed_span_minutes']==15 for r in rows))
        self.assertTrue(all(r['start_boundary']=='observed_crossing' and r['end_boundary']=='observed_exit' for r in rows))
        self.assertEqual(rows[0]['confirmed_at'],self.times[4].isoformat())
        self.assertEqual((rows[0]['minimum'],rows[0]['maximum'],rows[0]['mean']),(181.,201.,190.75))
        self.assertEqual(rows[1]['extreme_at'],self.times[9].isoformat())
        self.assertEqual(len(rows[0]['points']),6)
        self.assertEqual(rows[0]['next_observed_at'],self.times[5].isoformat())

    def test_observed_runs_split_on_missing_data_without_claiming_recovery(self):
        values=[100]+[200]*4+[np.nan]+[210]*4+[100]
        rows=historical_patterns(self.times[:11],values,self.times[10])['excursions']
        self.assertEqual(len(rows),2)
        self.assertEqual((rows[0]['start_boundary'],rows[0]['end_boundary']),('observed_crossing','gap'))
        self.assertEqual((rows[1]['start_boundary'],rows[1]['end_boundary']),('gap','observed_exit'))
        self.assertIsNone(rows[0]['next_observed_at'])
        self.assertEqual(rows[0]['points'][-1]['time'],self.times[4].isoformat())
        self.assertTrue(all(np.isfinite(p['glucose']) for r in rows for p in r['points']))
        times=self.times[:11].delete(5)
        self.assertEqual(rows,historical_patterns(times,[100]+[200]*4+[210]*4+[100],self.times[10])['excursions'])

    def test_observed_run_censors_history_start_and_current_cutoff(self):
        rows=historical_patterns(self.times[:4],[65]*4,self.times[3])['excursions']
        self.assertEqual((rows[0]['start_boundary'],rows[0]['end_boundary']),('history_boundary','cutoff'))
        self.assertIsNone(rows[0]['next_observed_at'])
        self.assertEqual(rows[0]['extreme_at'],self.times[0].isoformat())
        self.assertEqual(historical_patterns(self.times[:4],[65]*4,self.times[2])['excursions'],[])
        later=historical_patterns(self.times[:5],[65]*4+[70],self.times[4])['excursions'][0]
        self.assertEqual(later['id'],rows[0]['id']);self.assertEqual(later['end_boundary'],'observed_exit')

    def test_observed_runs_respect_patient_phase_midnight_and_seven_date_boundary(self):
        times=pd.date_range('2024-01-01T00:03',periods=8*288,freq='5min')
        values=np.full(len(times),200.)
        rows=historical_patterns(times,values,times[-1])['excursions']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['first_observed'],'2024-01-02T00:03:00')
        self.assertEqual(rows[0]['last_observed'],times[-1].isoformat())
        self.assertEqual(rows[0]['samples'],7*288)
        self.assertEqual(rows[0]['observed_span_minutes'],(7*288-1)*5)
        self.assertEqual(rows[0]['start_boundary'],'history_boundary')

    def test_observed_runs_ignore_empty_nonfinite_and_short_gap_fragments(self):
        self.assertEqual(observed_excursions(pd.Series(dtype=float)),[])
        self.assertEqual(historical_patterns(self.times[:9],[np.inf,np.nan,100,200,200,200,np.nan,200,200],self.times[8])['excursions'],[])
        self.assertEqual(historical_patterns(self.times[:9],np.full(9,np.nan),self.times[8])['excursions'],[])
        self.assertEqual(historical_patterns(self.times,self.values,'2023-01-01')['excursions'],[])

    def test_hourly_phase_admission_and_no_interpolation(self):
        times=pd.date_range('2024-01-01T00:03',periods=13,freq='5min')
        times=times.delete(2)
        first=historical_patterns(times,np.full(len(times),100.),times[-1])['hourly'][0]
        self.assertEqual((first['samples'],first['expected']),(11,12))
        self.assertEqual(first['first_checkpoint'],'2024-01-01T00:03:00')
        self.assertEqual(first['last_checkpoint'],'2024-01-01T00:58:00')
        self.assertTrue(first['comparable'])
        partial=historical_patterns(self.times[3:13],np.full(10,100.),self.times[12])['hourly'][0]
        self.assertEqual(partial['expected'],9);self.assertFalse(partial['complete_hour'])
        self.assertEqual(historical_patterns(self.times,self.values,'2023-01-01')['hourly'],[])

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

    def test_extended_profile_prefix_phase_and_missing_denominator(self):
        times=pd.date_range('2024-01-01T00:03',periods=15*288,freq='5min')
        values=np.full(len(times),100.)
        cutoff=times[13*288-1]
        a=descriptive_profile(times,values,cutoff)
        self.assertEqual(a,descriptive_profile(times[times<=cutoff],values[times<=cutoff],cutoff))
        self.assertEqual(a['mean'],100.);self.assertEqual(a['coefficient_variation_pct'],0.)
        self.assertTrue(all(r['covered_days']>=3 and r['median']==100 for r in a['hours']))
        values[10:]=np.nan
        b=descriptive_profile(times,values,cutoff)
        self.assertTrue(all(r['median'] is None for r in b['hours']))
        self.assertEqual(b['samples'],10)
        self.assertIsNone(descriptive_profile(times,np.full(len(times),np.nan),cutoff)['overnight']['below70_fraction'])


if __name__=='__main__':unittest.main()
