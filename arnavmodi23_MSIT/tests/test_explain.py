import sys
import unittest
from pathlib import Path
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from glucotwin.explain import explain_ridge


class ExplanationTests(unittest.TestCase):
    def test_reconstructs_prediction_with_missingness_and_correlated_features(self):
        X=np.array([[80,30,60],[100,np.nan,65],[120,50,70],[140,60,np.nan]],float)
        y=np.array([90,105,115,130],float)
        model=Pipeline([('imputer',SimpleImputer(add_indicator=True,keep_empty_features=True)),('scale',StandardScaler()),('ridge',Ridge(alpha=10))]).fit(X,y)
        artifact=dict(model=model,features=['cgm_current','age','hr_mean_60m'])
        row=np.array([110,np.nan,67.])
        e=explain_ridge(artifact,row,110.)
        self.assertAlmostEqual(e['reconstructed_prediction'],model.predict([row])[0])
        self.assertAlmostEqual(110+e['reference_offset']+sum(e['groups'].values()),e['reconstructed_prediction'])
        self.assertEqual(e['imputed'],['age'])
        self.assertIn('do not establish',e['note'])

    def test_unsupported_model_is_explicitly_unavailable(self):
        self.assertIsNone(explain_ridge(dict(model=object(),features=['cgm_current']),[100],100))
