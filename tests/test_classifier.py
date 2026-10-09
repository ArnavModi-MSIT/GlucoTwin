from pathlib import Path
import json,sys,unittest
import joblib,numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from glucotwin.endpoint import endpoint_probability

class ClassifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact=joblib.load(ROOT/'artifacts/endpoint_classifier.joblib')
        cls.data=pd.read_csv(ROOT/'data/processed/cgmacros_features.csv')

    def test_probability_is_disabled_after_failed_gate(self):
        assessment=json.loads((ROOT/'reports/classifier_assessment.json').read_text())
        self.assertFalse(assessment['calibration_gate_passed'])
        self.assertFalse(self.artifact['probability_display_approved'])
        with self.assertRaisesRegex(RuntimeError,'disabled'):
            endpoint_probability(self.data.iloc[:1],self.artifact)

    def test_fit_roles_are_patient_disjoint(self):
        roles=self.artifact['roles']
        tune=set(roles['tuning']);cal=set(roles['calibration'])
        self.assertFalse(tune&cal)
        self.assertEqual(len(tune),3);self.assertEqual(len(cal),3)
        development=tune|cal
        train=set(self.data.loc[self.data.split.eq('train'),'patient_id'])
        test=set(self.data.loc[self.data.split.eq('test'),'patient_id'])
        self.assertFalse(development&train);self.assertFalse(development&test)
        expected=self.data.loc[self.data.split.eq('train'),self.artifact['features']].median().fillna(0).to_numpy()
        np.testing.assert_allclose(self.artifact['model'].named_steps['imputer'].statistics_,expected)

    def test_saved_classifier_reproduces_development_probabilities(self):
        reference=pd.read_csv(ROOT/'data/processed/classifier_tuning_predictions.csv')
        tune=self.data[self.data.patient_id.isin(self.artifact['roles']['tuning'])]
        np.testing.assert_array_equal(tune.patient_id,reference.patient_id)
        X=tune[self.artifact['features']].iloc[:100]
        p=self.artifact['model'].predict_proba(X)[:,1]
        score=self.artifact['model'].decision_function(X).reshape(-1,1)
        calibrated=self.artifact['calibrator'].predict_proba(score)[:,1]
        np.testing.assert_allclose(p,reference.raw_probability.iloc[:100],rtol=1e-10,atol=1e-10)
        np.testing.assert_allclose(calibrated,reference.calibrated_probability.iloc[:100],rtol=1e-10,atol=1e-10)

if __name__=='__main__':unittest.main()
