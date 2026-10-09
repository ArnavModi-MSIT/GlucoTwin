import unittest,json
from pathlib import Path
import numpy as np,pandas as pd,joblib
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1]

class RbgEndpointTests(unittest.TestCase):
    def test_roles_and_disabled_deployment(self):
        roles=json.loads((ROOT/'configs/rbg_classifier_roles.json').read_text())
        manifest=json.loads((ROOT/'configs/rbg_splits.json').read_text())
        test={p['patient_id'] for p in manifest['participants'] if p['split']=='test'}
        train={p['patient_id'] for p in manifest['participants'] if p['split']=='train'}
        self.assertEqual(len(roles['calibration']),17);self.assertEqual(len(roles['assessment']),17)
        self.assertTrue(set(roles['calibration']).isdisjoint(roles['assessment']))
        self.assertTrue((test|train).isdisjoint(set(roles['calibration'])|set(roles['assessment'])))
        for event in ['high','low']:
            artifact=joblib.load(ROOT/f'artifacts/rbg_{event}_endpoint.joblib')
            self.assertFalse(artifact['probability_display_approved'])
            self.assertFalse(artifact['flag_deployment_approved'])
    def test_saved_model_reproduces_patient_precision_recall(self):
        roles=json.loads((ROOT/'configs/rbg_classifier_roles.json').read_text())
        report=json.loads((ROOT/'reports/rbg_endpoint_assessment.json').read_text())
        base=ROOT/'data/processed/rbg'
        for event in ['high','low']:
            artifact=joblib.load(ROOT/f'artifacts/rbg_{event}_endpoint.joblib')
            pid=roles['assessment'][0]
            with np.load(base/'30/validation'/f'{pid}.npz') as data:X=data['X'];target=data['y']
            columns=artifact['features'];current=X[:,columns.index('cgm_current')]
            mask=current<=180 if event=='high' else current>=70
            actual=(target>180 if event=='high' else target<70)[mask]
            with threadpool_limits(limits=4):
                model=artifact['model']
                if report['events'][event]['operating_score']=='sigmoid':prob=artifact['calibrator'].predict_proba(model.decision_function(X[mask]).reshape(-1,1))[:,1]
                else:prob=model.predict_proba(X[mask])[:,1]
            predicted=prob>=artifact['threshold'];tp=int((predicted&actual).sum());fp=int((predicted&~actual).sum())
            expected=pd.read_csv(base/f'{event}_classifier_patient_metrics.csv').set_index('patient_id').loc[pid]
            self.assertEqual(tp,expected.tp);self.assertEqual(fp,expected.fp)

if __name__=='__main__':unittest.main()
