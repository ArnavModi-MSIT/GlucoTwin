"""Synthetic feature -> fit -> trusted artifact -> HTTP replay checks.

These check implementation wiring, not research or medical performance.
"""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.request
from unittest.mock import patch
import numpy as np
import pandas as pd
import sklearn
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import serve_dashboard as web
from glucotwin.features import make_features,STATIC,HR
from glucotwin.artifacts import CGM,save_model_artifact,load_model_artifact,validate_replay_artifact


class PipelineSmokeTests(unittest.TestCase):
    def test_synthetic_numerical_pipeline_reveals_only_matured_targets(self):
        times=pd.date_range('2026-01-01',periods=30*60+1,freq='min')
        values=120+20*np.sin(np.arange(len(times))/45)
        frame=pd.DataFrame({'Timestamp':times,'Dexcom GL':values,'HR':65.})
        profile=dict(age=40.,gender_f=0.,bmi=25.,hba1c_pct=6.,fasting_glucose=100.)
        columns=CGM+STATIC+HR
        built=make_features(frame,profile,0)
        target=frame.set_index('Timestamp')['Dexcom GL'].reindex(built.index+pd.Timedelta(minutes=60)).to_numpy()
        selected=built.history_eligible.to_numpy() & np.isfinite(target)
        model=Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),('scale',StandardScaler()),('ridge',Ridge(alpha=10))])
        model.fit(built.loc[selected,columns],target[selected])
        artifact=dict(model=model,features=columns,horizon_minutes=60,dataset='CGMacros reconstructed grid',version='baseline-v0.1',sklearn_version=sklearn.__version__)
        # A separate fictional evaluation patient; no source files are needed.
        evaluation=frame.copy();evaluation['Dexcom GL']+=5
        patient=dict(patient_id=7,split='validation',phase_utc_minutes_mod_5=0,minimum_forecast_time=str(times[24*60]))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);save_model_artifact(root,'artifacts/model.joblib',artifact)
            loaded=validate_replay_artifact(load_model_artifact(root,'artifacts/model.joblib'),'cgmacros',60)
            with patch.object(web,'ROOT',root),patch.object(web,'service',web.Service()),patch.object(web,'catalog',return_value={7:patient}),patch.object(web,'records',return_value=(evaluation,profile)),patch.object(web,'models',return_value={60:loaded}),patch.object(web,'load_event_artifact',side_effect=FileNotFoundError):
                server=web.ThreadingHTTPServer(('127.0.0.1',0),web.Handler)
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                url=f'http://127.0.0.1:{server.server_port}'
                token=''
                def post(path,body):
                    nonlocal token
                    req=urllib.request.Request(url+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-GlucoTwin-Session':token})
                    with urllib.request.urlopen(req) as response:
                        token=response.headers.get('X-GlucoTwin-Session',token)
                        return json.load(response)
                try:
                    first=post('/api/session',dict(cohort='cgmacros',patient_id=7))
                    self.assertEqual(first['ledger'][0]['outcome'],'Pending')
                    self.assertIsNone(first['ledger'][0]['actual']);self.assertTrue(np.isfinite(first['forecasts'][0]['prediction']))
                    later=post('/api/advance',dict(minutes=60))
                    self.assertEqual(later['ledger'][0]['prediction'],first['ledger'][0]['prediction'])
                    self.assertEqual(later['ledger'][0]['outcome'],'Observed')
                    self.assertTrue(all(p['time']<=later['data_cutoff'] for p in later['chart']))
                finally:
                    server.shutdown();server.server_close();thread.join()

    @unittest.skipUnless(importlib.util.find_spec('xgboost'),'Optional XGBoost is not installed')
    def test_optional_xgboost_cpu_fit_and_artifact_roundtrip(self):
        from xgboost import XGBClassifier
        rng=np.random.default_rng(17);x=rng.normal(size=(40,4));y=(x[:,0]>0).astype(int)
        model=XGBClassifier(n_estimators=8,max_depth=2,n_jobs=2,tree_method='hist',device='cpu')
        model.fit(x,y)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);save_model_artifact(root,'artifacts/event.joblib',dict(model=model,sklearn_version=sklearn.__version__))
            restored=load_model_artifact(root,'artifacts/event.joblib')
            np.testing.assert_array_equal(restored['model'].predict_proba(x),model.predict_proba(x))
