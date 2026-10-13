import sys,unittest,tempfile,json,warnings,sklearn
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from glucotwin.artifacts import CGM,validate_replay_artifact,load_model_artifact,save_model_artifact
from sklearn.exceptions import InconsistentVersionWarning

class ArtifactContractTests(unittest.TestCase):
    def test_hash_verification_precedes_deserialization_and_paths_stay_local(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'artifacts').mkdir()
            path=root/'artifacts/model.joblib';path.write_bytes(b'not a pickle')
            with patch('glucotwin.artifacts.joblib.load',side_effect=AssertionError('must not deserialize')) as load:
                with self.assertRaisesRegex(ValueError,'fingerprint'):load_model_artifact(root,path)
                (root/'configs').mkdir();(root/'configs/replay_artifact_hashes.json').write_text(json.dumps(dict(version='replay-artifact-hashes-v1',models={'artifacts/model.joblib':'wrong'})))
                with self.assertRaisesRegex(ValueError,'fingerprint'):load_model_artifact(root,path)
                with self.assertRaisesRegex(ValueError,'inside'):load_model_artifact(root,root/'outside.joblib')
                load.assert_not_called()

    def test_training_manifest_roundtrip_and_legacy_sklearn_warning_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);relative='artifacts/model.joblib'
            save_model_artifact(root,relative,{'fixture':123})
            self.assertEqual(load_model_artifact(root,relative),{'fixture':123})
            def incompatible(*args):
                warnings.warn(InconsistentVersionWarning(estimator_name='Ridge',current_sklearn_version=sklearn.__version__,original_sklearn_version='0.0'))
            with patch('glucotwin.artifacts.joblib.load',side_effect=incompatible):
                with self.assertRaisesRegex(ValueError,'sklearn version'):load_model_artifact(root,relative)
            (root/relative).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'fingerprint'):load_model_artifact(root,relative)

    def test_runtime_drift_blocks_research_loading_before_deserialization(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);save_model_artifact(root,'artifacts/model.joblib',{'fixture':1})
            (root/'requirements.txt').write_text('scikit-learn==0.0\n')
            with patch('glucotwin.artifacts.joblib.load') as load:
                with self.assertRaisesRegex(ValueError,'dependencies'):load_model_artifact(root,'artifacts/model.joblib')
                load.assert_not_called()

    def test_fusion_contract_requires_historical_features(self):
        class Model:n_features_in_=len(CGM)+2
        artifact={'model':Model(),'features':CGM+['age_at_enrollment','sex_f'],'horizon_minutes':30,'sensor_delay_minutes':5,'version':'rbg-baseline-v0.1'}
        validate_replay_artifact(artifact,'rbg',30,profile_fusion=True)
        with self.assertRaises(ValueError):validate_replay_artifact({**artifact,'features':CGM},'rbg',30,profile_fusion=True)

    def test_wrong_horizon_delay_and_feature_order_rejected(self):
        class Model:n_features_in_=len(CGM)
        artifact={'model':Model(),'features':CGM.copy(),'horizon_minutes':30,
                  'sensor_delay_minutes':5,'version':'rbg-baseline-v0.1'}
        validate_replay_artifact(artifact,'rbg',30)
        for key,value in [('horizon_minutes',60),('sensor_delay_minutes',0),('features',list(reversed(CGM)))]:
            with self.assertRaises(ValueError):validate_replay_artifact({**artifact,key:value},'rbg',30)
        with self.assertRaisesRegex(ValueError,'sklearn version'):validate_replay_artifact({**artifact,'sklearn_version':'0.0'},'rbg',30)
