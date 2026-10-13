"""Validate the supported replay contract after loading trusted local artifacts.

This does not make pickle/joblib safe to load from an untrusted source.
"""
import hashlib
import io
import json
import importlib.metadata
from pathlib import Path
import warnings
import joblib
import sklearn
from sklearn.exceptions import InconsistentVersionWarning
from glucotwin.features import STATIC,HR

CGM=['cgm_current']+[f'cgm_{stat}_{minutes}m' for minutes in (15,30,60)
    for stat in ('mean','std','min','max','count','change')]+[
    'cgm_slope_30m','cgm_missing_fraction_60m','cgm_max_gap_60m']


def model_path(root, path):
    root = Path(root).resolve()
    path = Path(path)
    path = (root/path if not path.is_absolute() else path).resolve()
    if not path.is_relative_to(root/'artifacts'):
        raise ValueError('Model must stay inside the local artifacts directory')
    return path, path.relative_to(root).as_posix()


def load_model_artifact(root, path):
    """Check trusted manifest bytes before deserialization; never trust uploads."""
    path, relative = model_path(root,path)
    requirements=Path(root)/'requirements.txt'
    if requirements.exists():
        for line in requirements.read_text(encoding='utf-8').splitlines():
            if '==' not in line:continue
            name,expected=line.strip().split('==',1)
            if name in ('numpy','pandas','scikit-learn','joblib') and importlib.metadata.version(name)!=expected:
                raise ValueError('Pinned research model dependencies are required')
    entries = {}
    for manifest in [Path(root)/'configs/replay_artifact_hashes.json', Path(root)/'artifacts/replay_hashes.json']:
        if manifest.exists():
            payload = json.loads(manifest.read_text(encoding='utf-8'))
            if payload['version'] != 'replay-artifact-hashes-v1':
                raise ValueError('Unsupported model hash manifest')
            entries.update(payload['models'])
    if relative not in entries:
        raise ValueError('Model has no trusted preparation fingerprint')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entries[relative]:
        raise ValueError('Model fingerprint mismatch; prepare trusted local models again')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',InconsistentVersionWarning)
            return joblib.load(io.BytesIO(data))
    except InconsistentVersionWarning as exc:
        raise ValueError('Model sklearn version mismatch') from exc


def save_model_artifact(root, path, artifact):
    """Called by trusted training scripts, never by model-upload/import routes."""
    path, relative = model_path(root,path)
    manifest = Path(root)/'artifacts/replay_hashes.json'
    payload = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else dict(version='replay-artifact-hashes-v1',models={})
    if payload['version'] != 'replay-artifact-hashes-v1':
        raise ValueError('Unsupported model hash manifest')
    path.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump(artifact,path)
    payload['models'][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    temporary = manifest.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    temporary.replace(manifest)


def validate_replay_artifact(artifact,cohort,horizon,profile_fusion=False):
    if cohort not in ('rbg','cgmacros'):raise ValueError('Unknown artifact cohort')
    expected=(CGM+['age_at_enrollment','sex_f'] if profile_fusion else CGM) if cohort=='rbg' else CGM+STATIC+HR
    if artifact.get('features')!=expected:raise ValueError('Artifact feature schema mismatch')
    if artifact.get('horizon_minutes')!=horizon:raise ValueError('Artifact horizon mismatch')
    if cohort=='rbg':
        if artifact.get('sensor_delay_minutes')!=5:raise ValueError('Artifact delay mismatch')
        if artifact.get('version')!='rbg-baseline-v0.1':raise ValueError('Artifact version mismatch')
        # Legacy RBG files have no explicit field; the loader rejects the
        # serialized estimators' sklearn version warnings for those files.
        if artifact.get('sklearn_version',sklearn.__version__)!=sklearn.__version__:raise ValueError('Artifact sklearn version mismatch')
    else:
        if horizon!=60 or artifact.get('dataset')!='CGMacros reconstructed grid':raise ValueError('Artifact cohort mismatch')
        if artifact.get('version')!='baseline-v0.1':raise ValueError('Artifact version mismatch')
        if artifact.get('sklearn_version')!=sklearn.__version__:raise ValueError('Artifact sklearn version mismatch')
    if getattr(artifact.get('model'),'n_features_in_',None)!=len(expected):raise ValueError('Artifact model input mismatch')
    return artifact
