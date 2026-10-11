"""Opt-in checks for saved event-study artifacts and reported outer scores."""
import sys,json,hashlib,unittest
from pathlib import Path
import joblib,pandas as pd
from local_only import local_only
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from glucotwin.features import make_features,profile_features
from glucotwin.episodes import onsets
from glucotwin.event_study import assess_scores,summarize

@local_only
class OnsetArtifactTests(unittest.TestCase):
    def test_frozen_roles_and_fail_closed_capabilities(self):
        manifest=json.loads((ROOT/'configs/cgmacros_splits.json').read_text())
        reserved={p['patient_id'] for p in manifest['participants'] if p['split']=='test'}
        for study in ('v1','gpu_v2'):
            protocol=(ROOT/'configs'/f'event_study_{study}.json').read_bytes()
            artifact=joblib.load(ROOT/'artifacts'/f'cgmacros_onset_{study}_fold1_fused.joblib')
            self.assertEqual(artifact['protocol_sha256'],hashlib.sha256(protocol).hexdigest())
            roles=artifact['roles'];fit=set(roles['fit']);threshold=set(roles['threshold']);evaluation=set(roles['evaluation'])
            self.assertFalse(fit&threshold or fit&evaluation or threshold&evaluation)
            self.assertFalse(reserved&(fit|threshold|evaluation))
            self.assertFalse(artifact['operational_alerts_approved']);self.assertFalse(artifact['probability_display_approved'])
            self.assertIn('hba1c_pct',artifact['features']);self.assertIn('hr_mean_60m',artifact['features'])
    def test_saved_xgboost_reproduces_outer_fold_episode_counts(self):
        artifact=joblib.load(ROOT/'artifacts/cgmacros_onset_gpu_v2_fold1_fused.joblib')
        report=json.loads((ROOT/'reports/event_study_gpu_v2.json').read_text())
        patients={p['patient_id']:p for p in json.loads((ROOT/'configs/cgmacros_splits.json').read_text())['participants']}
        source=ROOT/'data/raw/cgmacros/CGMacros'
        bio=pd.read_csv(source/'bio.csv');bio.columns=bio.columns.str.strip();bio=bio.set_index('subject')
        records={};scores={}
        for pid in artifact['roles']['evaluation']:
            patient=patients[pid];self.assertNotEqual(patient['split'],'test')
            frame=pd.read_csv(source/f'CGMacros-{pid:03d}/CGMacros-{pid:03d}.csv')
            features=make_features(frame,profile_features(bio.loc[pid]),patient['phase_utc_minutes_mod_5'])
            eligible=features.history_eligible & (features.cgm_current<=180) & (features.index>=pd.Timestamp(patient['minimum_forecast_time']))
            X=features.loc[eligible,artifact['features']]
            records[pid]={'times':X.index,'episodes':onsets(features.cgm_current,'high'),'glucose':features.cgm_current}
            scores[pid]=artifact['model'].predict_proba(X)[:,1]
        actual=summarize(assess_scores(records,scores,artifact['threshold']))
        expected=report['folds'][0]['methods']['fused']['outer_evaluation']
        for key in ['evaluable_episodes','detected_episodes','alarms','false_alarms','unknown_alarms']:
            self.assertEqual(actual[key],expected[key])
