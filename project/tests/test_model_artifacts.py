from local_only import local_only
import sys,unittest
from pathlib import Path
import numpy as np
import pandas as pd
import joblib

ROOT=Path(__file__).resolve().parents[1]

@local_only
class ArtifactTests(unittest.TestCase):
    def test_saved_boosting_reproduces_validation_predictions(self):
        data=pd.read_csv(ROOT/'data/processed/cgmacros_features.csv')
        val=data[data.split.eq('validation')]
        reference=pd.read_csv(ROOT/'data/processed/boosting_validation_predictions.csv')
        for name in ('boost_cgm_only','boost_cgm_clinical','boost_cgm_clinical_hr'):
            artifact=joblib.load(ROOT/f'artifacts/{name}.joblib')
            self.assertEqual(artifact['horizon_minutes'],60)
            self.assertFalse({'patient_id','target_glucose_60m','target_time','split','high_endpoint','new_high_endpoint'} & set(artifact['features']))
            actual=artifact['model'].predict(val[artifact['features']].iloc[:100])
            np.testing.assert_allclose(actual,reference[name].iloc[:100],rtol=1e-10,atol=1e-10)

    def test_ridge_imputer_fit_on_training_only(self):
        frame=pd.read_csv(ROOT/'data/processed/cgmacros_features.csv')
        train=frame[frame.split.eq('train')]
        artifact=joblib.load(ROOT/'artifacts/ridge_cgm_clinical_hr.joblib')
        expected=train[artifact['features']].median().fillna(0).to_numpy()
        np.testing.assert_allclose(artifact['model'].named_steps['imputer'].statistics_,expected)

if __name__=='__main__': unittest.main()
