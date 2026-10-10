import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from glucotwin.artifacts import CGM,validate_replay_artifact

class ArtifactContractTests(unittest.TestCase):
    def test_wrong_horizon_delay_and_feature_order_rejected(self):
        class Model:n_features_in_=len(CGM)
        artifact={'model':Model(),'features':CGM.copy(),'horizon_minutes':30,
                  'sensor_delay_minutes':5,'version':'rbg-baseline-v0.1'}
        validate_replay_artifact(artifact,'rbg',30)
        for key,value in [('horizon_minutes',60),('sensor_delay_minutes',0),('features',list(reversed(CGM)))]:
            with self.assertRaises(ValueError):validate_replay_artifact({**artifact,key:value},'rbg',30)
