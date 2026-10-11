import unittest,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from glucotwin.endpoint import calibration_score,endpoint_probability

class EndpointUnitTests(unittest.TestCase):
    def test_unapproved_probability_never_calls_model(self):
        with self.assertRaisesRegex(RuntimeError,'disabled'):endpoint_probability(None,{})
    def test_score_contract_and_extreme_probability_clipping(self):
        class Model:
            def decision_function(self,X):return np.array([-2.,2.])
            def predict_proba(self,X):return np.array([[1.,0.],[0.,1.]])
        artifact={'model':Model()}
        np.testing.assert_array_equal(calibration_score(None,artifact).ravel(),[-2.,2.])
        artifact['calibration_input']='clipped_log_odds'
        score=calibration_score(None,artifact).ravel()
        self.assertTrue(np.isfinite(score).all());self.assertLess(score[0],0);self.assertGreater(score[1],0)
        artifact['calibration_input']='unknown'
        with self.assertRaises(ValueError):calibration_score(None,artifact)
