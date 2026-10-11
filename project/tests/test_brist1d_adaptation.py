import json
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from glucotwin.brist1d_adaptation import adapt_forecasts,scheduled_updates,MINUTE_NS


class AdaptationTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT/'configs/brist1d_adaptation_v3.json').read_text())

    def run_case(self,times,actual=None,baseline=None,full=None,horizon=30,config=None):
        times = np.asarray(times,dtype=np.int64)*MINUTE_NS
        return adapt_forecasts(times,np.full(len(times),130.) if actual is None else actual,
            np.full(len(times),100.) if baseline is None else baseline,
            times if full is None else np.asarray(full,dtype=np.int64)*MINUTE_NS,
            horizon,config or self.config)

    def test_no_update_before_exact_availability_boundary_at_both_horizons(self):
        config = dict(self.config,minimum_matured_updates=1)
        for horizon in (30,60):
            times = [0,horizon+4,horizon+5]
            result = self.run_case(times,horizon=horizon,config=config)
            self.assertEqual(result['correction'][1],0.)
            self.assertGreater(result['correction'][2],0.)
            self.assertEqual(result['matured_count'][2],1)

    def test_future_targets_and_prefix_do_not_change_past_predictions(self):
        times = np.arange(0,1441,5)
        actual = np.full(len(times),130.)
        cutoff = 800
        before = self.run_case(times,actual=actual)
        changed = actual.copy(); changed[times+35>cutoff] = 99999.
        after = self.run_case(times,actual=changed)
        np.testing.assert_array_equal(before['predicted'][times<=cutoff],after['predicted'][times<=cutoff])
        prefix = self.run_case(times[times<=cutoff],actual=actual[times<=cutoff])
        np.testing.assert_array_equal(before['predicted'][times<=cutoff],prefix['predicted'])

    def test_missing_target_never_shifts_the_update_schedule(self):
        full = [0,5,60,65,120,125]
        np.testing.assert_array_equal(scheduled_updates(np.array(full)*MINUTE_NS,60)/MINUTE_NS,[0,60,120])
        result = self.run_case([5,60,65,120,125],full=full,config=dict(self.config,minimum_matured_updates=1))
        self.assertEqual(result['all_scheduled_updates'],3)
        self.assertEqual(result['scheduled_updates_with_exact_targets'],2)
        self.assertEqual(result['correction'][1],0.)

    def test_warmup_expiry_and_large_gap_fall_back_to_baseline(self):
        times = [0,60,120,155,336,2000]
        result = self.run_case(times,config=dict(self.config,minimum_matured_updates=3))
        self.assertFalse(result['active'][2])
        self.assertTrue(result['active'][3])
        self.assertFalse(result['active'][4])
        self.assertFalse(result['active'][5])
        self.assertEqual(result['matured_count'][5],0)
        self.assertEqual(result['predicted'][5],100.)

    def test_clipping_sign_shrinkage_and_independent_patient_state(self):
        times = np.arange(0,1441,5)
        pos = self.run_case(times,actual=np.full(len(times),99999.))
        neg = self.run_case(times,actual=np.full(len(times),-99999.))
        self.assertTrue((np.abs(pos['correction'])<=10).all())
        self.assertTrue((np.abs(neg['correction'])<=10).all())
        self.assertGreater(pos['correction'][-1],0)
        self.assertLess(neg['correction'][-1],0)
        self.assertEqual(self.run_case([0])['correction'][0],0)
        small = self.run_case(times,actual=np.full(len(times),102.))
        self.assertGreater(small['correction'][-1],0)
        self.assertLess(small['correction'][-1],2)

    def test_invalid_times_and_rules_fail_closed(self):
        with self.assertRaises(ValueError): self.run_case([5,0])
        with self.assertRaises(ValueError): self.run_case([0,0])
        with self.assertRaises(ValueError): self.run_case([0,5],full=[0])
        with self.assertRaises(ValueError): self.run_case([0],config=dict(self.config,half_life_minutes=0))
        with self.assertRaises(ValueError): self.run_case([0],horizon=0)


if __name__=='__main__': unittest.main()
