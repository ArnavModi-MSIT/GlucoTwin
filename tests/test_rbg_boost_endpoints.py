import unittest,json
from pathlib import Path
import numpy as np,pandas as pd,joblib
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1]

class RbgBoostEndpointTests(unittest.TestCase):
    def test_saved_models_reproduce_assessment_patient_flags(self):
        roles=json.loads((ROOT/'configs/rbg_classifier_roles.json').read_text())
        report=json.loads((ROOT/'reports/rbg_boost_endpoint_assessment.json').read_text())
        base=ROOT/'data/processed/rbg'
        for event in ['high','low']:
            artifact=joblib.load(ROOT/f'artifacts/rbg_{event}_boost_endpoint.joblib')
            self.assertFalse(artifact['probability_display_approved']);self.assertFalse(artifact['flag_deployment_approved'])
            self.assertEqual(artifact['model'].n_iter_,120);self.assertFalse(artifact['model'].early_stopping)
            self.assertEqual(artifact['calibration_input'],'clipped_log_odds')
            pid=roles['assessment'][0]
            with np.load(base/'30/validation'/f'{pid}.npz') as d:X=d['X'];target=d['y']
            current=X[:,artifact['features'].index('cgm_current')]
            mask=current<=180 if event=='high' else current>=70
            y=(target>180 if event=='high' else target<70)[mask]
            with threadpool_limits(limits=4):
                p=artifact['model'].predict_proba(X[mask])[:,1]
                if report['events'][event]['operating_score']=='sigmoid':
                    p=np.clip(p,1e-6,1-1e-6)
                    p=artifact['calibrator'].predict_proba(np.log(p/(1-p)).reshape(-1,1))[:,1]
            flag=p>=artifact['threshold']
            expected=pd.read_csv(base/f'{event}_boost_classifier_patient_metrics.csv').set_index('patient_id').loc[pid]
            self.assertEqual(int((flag&y).sum()),expected.tp)
            self.assertEqual(int((flag&~y).sum()),expected.fp)
            self.assertFalse((base/'30/test').exists())

if __name__=='__main__':unittest.main()
