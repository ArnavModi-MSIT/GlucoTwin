import unittest,json
from pathlib import Path
import joblib,numpy as np,pandas as pd
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1]

class RbgBoostTests(unittest.TestCase):
    def test_saved_model_matches_reported_patient_error(self):
        base=ROOT/'data/processed/rbg'
        columns=json.loads((base/'features.json').read_text())
        scores=pd.read_csv(base/'boosting_validation_patient_metrics.csv')
        for horizon in [30,60]:
            artifact=joblib.load(ROOT/f'artifacts/rbg_boost_cgm_{horizon}.joblib')
            self.assertFalse(artifact['model'].early_stopping)
            self.assertEqual(artifact['sensor_delay_minutes'],5)
            file=sorted((base/str(horizon)/'validation').glob('*.npz'))[0]
            with np.load(file) as data:X=data['X'];y=data['y']
            indices=[columns.index(c) for c in artifact['features']]
            with threadpool_limits(limits=4):pred=artifact['model'].predict(X[:,indices])
            expected=scores[(scores.horizon==horizon)&scores.model.eq('boost_cgm')&scores.patient_id.eq(file.stem)].mae.iloc[0]
            self.assertAlmostEqual(float(np.abs(pred-y).mean()),expected,places=5)
            self.assertFalse((base/str(horizon)/'test').exists())

if __name__=='__main__':unittest.main()
