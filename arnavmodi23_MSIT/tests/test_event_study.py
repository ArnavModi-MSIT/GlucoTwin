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
    def test_inner_selection_keeps_patient_roles_separate(self):
        ids=list(range(15));bands={p:str(p//5) for p in ids}
        records={p:{'known':np.array([True,True]),'y':np.array([0,1])} for p in ids}
        seen=[]
        def fit(records,patients,columns,name):
            seen.append({'fit':set(patients)});return object()
        def predict(model,records,patients,columns):
            seen[-1]['validation']=set(patients)
            return {p:np.array([.1,.9]) for p in patients}
        with patch.object(run_event_study,'fit',side_effect=fit),patch.object(run_event_study,'predict',side_effect=predict):
            chosen,_=run_event_study.inner_select(records,ids,bands,[],['xgb_600_d3'])
        self.assertEqual(chosen,'xgb_600_d3');self.assertEqual(len(seen),3)
        for role in seen:
            self.assertFalse(role['fit']&role['validation'])
            self.assertEqual(role['fit']|role['validation'],set(ids))

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
