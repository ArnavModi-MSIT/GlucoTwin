"""Synthetic tests for onset labels, patient roles and threshold separation."""
import sys,unittest
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from glucotwin.event_study import onset_labels,choose_event_threshold,choose_threshold_for_patients,gate,summarize
from glucotwin.episodes import onsets
from run_event_study import freeze_roles
from unittest.mock import patch
import run_event_study

SETTINGS={'minimum_evaluable_episodes':30,'minimum_patients_with_evaluable_episodes':5,
          'episode_recall':.6,'precision_lower_bound':.5,'maximum_false_alarms_per_eligible_day':1.,'minimum_median_lead_minutes':10}

class EventStudyTests(unittest.TestCase):
    def test_feature_arms_have_matched_clock_and_independent_selection(self):
        columns=['cgm_current','clock_sin','age','hr_mean_15m']
        arms=run_event_study.matched_feature_arms(columns)
        self.assertIn('clock_sin',arms['cgm_only']);self.assertIn('clock_sin',arms['fused'])
        self.assertNotIn('age',arms['cgm_only']);self.assertNotIn('hr_mean_15m',arms['cgm_only'])
        with patch.object(run_event_study,'inner_select',return_value=('candidate',{})) as select:
            result=run_event_study.select_feature_arms({},[1,2],{},arms,['candidate'],{})
        self.assertEqual(set(result),set(arms));self.assertEqual(select.call_count,4)
        self.assertEqual([call.args[3] for call in select.call_args_list],list(arms.values()))
        self.assertTrue(all(call.args[1]==[1,2] for call in select.call_args_list))

    def test_episode_selection_separates_all_inner_roles(self):
        ids=list(range(15)); bands={p:str(p//5) for p in ids}; records={p:{} for p in ids}
        seen=[]
        def fake_fit(records, patients, columns, name):
            seen.append({'fit':set(patients)}); return object()
        def fake_predict(model, records, patients, columns):
            return {p:np.array([.5]) for p in patients}
        def fake_threshold(subset, scores, settings, quantiles):
            seen[-1]['threshold']=set(subset); return .5,{},False
        def fake_assess(subset, scores, cutoff):
            seen[-1]['evaluation']=set(subset); return []
        with patch.object(run_event_study,'fit',side_effect=fake_fit), patch.object(run_event_study,'predict',side_effect=fake_predict), patch.object(run_event_study,'choose_event_threshold',side_effect=fake_threshold), patch.object(run_event_study,'assess_scores',side_effect=fake_assess), patch.object(run_event_study,'summarize',return_value={'episode_recall':.5,'precision_lower_bound':.5,'false_per_eligible_day':.5}):
            chosen,_=run_event_study.inner_select(records,ids,bands,[],['candidate'],{'seed':2026,'episode_selection':True,'engineering_gate':SETTINGS,'threshold_quantiles':11})
        self.assertEqual(chosen,'candidate'); self.assertEqual(len(seen),3)
        for role in seen:
            a,b,c=role['fit'],role['threshold'],role['evaluation']
            self.assertFalse(a&b or a&c or b&c)
            self.assertEqual(a|b|c,set(ids)); self.assertEqual(len(b),3)

    def test_empty_threshold_support_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError,'No threshold-setting'):
            choose_event_threshold({}, {}, SETTINGS)

    def setUp(self):
        self.times=pd.date_range('2026-01-01',periods=60,freq='5min')
        self.g=pd.Series(100.,index=self.times);self.g.iloc[10:14]=200.
    def test_window_boundaries_and_sustained_labels(self):
        labels,known=onset_labels(self.g,self.times[[3,4,9,10]])
        np.testing.assert_array_equal(labels,[0,1,1,0]);self.assertTrue(known.all())
        self.g.iloc[12]=100.
        self.assertFalse(onset_labels(self.g,self.times[[4]])[0][0])
    def test_missing_future_is_unknown_not_negative_training_data(self):
        self.g.iloc[7]=np.nan
        labels,known=onset_labels(self.g,self.times[[4]])
        self.assertFalse(known[0])
    def test_roles_are_patient_disjoint_and_reserved_excluded(self):
        entries=[{'patient_id':i,'a1c_group':str(i//9),'split':'train'} for i in range(27)]
        entries.append({'patient_id':99,'a1c_group':'0','split':'test'})
        patients,roles=freeze_roles({'participants':entries},{'seed':2026})
        self.assertEqual(len(patients),27);seen=[]
        for role in roles:
            fit,threshold,evaluation=map(set,[role['fit'],role['threshold'],role['evaluation']])
            self.assertFalse(fit&threshold or fit&evaluation or threshold&evaluation)
            self.assertNotIn(99,fit|threshold|evaluation);seen.extend(evaluation)
        self.assertEqual(sorted(seen),list(range(27)))
    def test_threshold_setting_does_not_take_evaluation_records(self):
        record={'times':self.times[:9],'glucose':self.g,'episodes':onsets(self.g,'high')}
        scores=np.array([0.,0.,0.,0.,.9,.9,.9,.9,.9])
        class Protected(dict):
            def __getitem__(self,key):
                if key==99:raise AssertionError('Evaluation labels accessed while setting threshold')
                return super().__getitem__(key)
        records=Protected({1:record,99:None});values=Protected({1:scores,99:None})
        first=choose_threshold_for_patients(records,values,[1],SETTINGS,11)
        records[99]={'invalid_evaluation_record':True};values[99]=np.array([999.])
        second=choose_threshold_for_patients(records,values,[1],SETTINGS,11)
        self.assertEqual(first,second)
        self.assertFalse(gate(first[1],SETTINGS,True)) # One patient cannot clear support.

if __name__=='__main__':unittest.main()
