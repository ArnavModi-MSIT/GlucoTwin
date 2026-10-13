"""Independent synthetic cases for retrospective alarm and miss descriptions."""
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
import json
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from glucotwin.episodes import onsets
from glucotwin.event_audit import audit_errors
from local_only import local_only


class EventAuditTests(unittest.TestCase):
    def setUp(self):
        self.times=pd.date_range('2024-01-01',periods=60,freq='5min')
        self.g=pd.Series(100.,index=self.times)
        self.g.iloc[20:24]=200.

    def audit(self,indices,opportunities=None):
        times=self.times if opportunities is None else opportunities
        scores=np.array([.9 if t in self.times[indices] else .1 for t in times])
        return audit_errors(dict(times=times,glucose=self.g,episodes=onsets(self.g,'high')),scores,.5)

    def test_warning_window_boundaries(self):
        for index in (14,19):
            result=self.audit([index])
            self.assertEqual(result['alarm_categories'],{'matched':1})
            self.assertEqual(result['episode_categories'],{'detected':1})
        self.assertEqual(self.audit([13])['alarm_categories'],{'false_before_later_onset':1})

    def test_cooldown_can_suppress_a_later_useful_crossing(self):
        result=self.audit([10,17])
        self.assertEqual(result['metrics']['alarms'],1)
        self.assertEqual(result['alarm_categories'],{'false_before_later_onset':1})
        self.assertEqual(result['episode_categories'],{'missed_with_cutoff_crossing_during_cooldown':1})

    def test_late_no_high_and_unknown_categories(self):
        self.assertEqual(self.audit([25])['alarm_categories'],{'false_after_recent_onset':1})
        self.assertEqual(self.audit([2])['alarm_categories'],{'false_no_high_reading_in_window':1})
        self.g.iloc[5]=np.nan
        self.assertEqual(self.audit([2])['alarm_categories'],{'unknown':1})

    def test_brief_high_is_not_relabelled_a_true_event(self):
        self.g.iloc[:]=100.;self.g.iloc[12:14]=200.
        result=self.audit([10])
        self.assertEqual(result['alarm_categories'],{'false_high_readings_without_qualifying_onset':1})
        self.assertEqual(result['metrics']['detected_episodes'],0)

    def test_missed_below_cutoff_and_ineligible_episode(self):
        self.assertEqual(self.audit([])['episode_categories'],{'missed_below_cutoff':1})
        self.assertEqual(self.audit([],self.times[:10])['episode_categories'],{'no_eligible_opportunity':1})

    def test_inputs_not_mutated(self):
        original=self.g.copy();self.audit([10,17]);pd.testing.assert_series_equal(self.g,original)


@local_only
class EventAuditArtifactTests(unittest.TestCase):
    def test_reproduction_and_sensor_read_boundary(self):
        root=Path(__file__).resolve().parents[1]
        sys.path.insert(0,str(root/'scripts'))
        from audit_high_events import run
        frozen=json.loads((root/'configs/cgmacros_event_roles_gpu_v2.json').read_text())
        cutoff={p for role in frozen['roles'] for p in role['threshold']}
        base=root/'data/raw/cgmacros/CGMacros'
        allowed={base/'bio.csv'} | {base/f'CGMacros-{p:03d}/CGMacros-{p:03d}.csv' for p in cutoff}
        seen=set();reader=pd.read_csv
        def guarded(path,*args,**kwargs):
            source=Path(path)
            self.assertIn(source,allowed,'Unexpected patient source read')
            seen.add(source)
            return reader(path,*args,**kwargs)
        with patch.object(pd,'read_csv',side_effect=guarded):result=run(root)
        self.assertEqual(seen,allowed)
        self.assertEqual(result,json.loads((root/'reports/high_event_audit_v1.json').read_text()))
