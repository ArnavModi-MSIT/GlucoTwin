from local_only import local_only
import unittest,json
from pathlib import Path
import numpy as np,joblib
ROOT=Path(__file__).resolve().parents[1]

@local_only
class RbgArtifactTests(unittest.TestCase):
    def test_no_test_matrices_and_training_sampling(self):
        base=ROOT/'data/processed/rbg'
        for horizon in [30,60]:
            self.assertFalse((base/str(horizon)/'test').exists())
            files=list((base/str(horizon)/'train').glob('*.npz'))
            self.assertEqual(len(files),158)
            for file in files:
                with np.load(file) as data:self.assertLessEqual(len(data['y']),2000)
    def test_imputation_uses_training_medians(self):
        base=ROOT/'data/processed/rbg'
        arrays=[]
        for file in sorted((base/'30/train').glob('*.npz')):
            with np.load(file) as data:arrays.append(data['X'])
        training=np.concatenate(arrays)
        artifact=joblib.load(ROOT/'artifacts/rbg_ridge_cgm_profile_30.joblib')
        np.testing.assert_allclose(artifact['model'].named_steps['imputer'].statistics_,np.nanmedian(training,axis=0),rtol=1e-6)
        self.assertEqual(artifact['sensor_delay_minutes'],5)

if __name__=='__main__':unittest.main()
