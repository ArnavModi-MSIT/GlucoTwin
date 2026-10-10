"""Validate the supported replay contract after loading trusted local artifacts.

This does not make pickle/joblib safe to load from an untrusted source.
"""
import sklearn
from glucotwin.features import STATIC,HR

CGM=['cgm_current']+[f'cgm_{stat}_{minutes}m' for minutes in (15,30,60)
    for stat in ('mean','std','min','max','count','change')]+[
    'cgm_slope_30m','cgm_missing_fraction_60m','cgm_max_gap_60m']

def validate_replay_artifact(artifact,cohort,horizon):
    if cohort not in ('rbg','cgmacros'):raise ValueError('Unknown artifact cohort')
    expected=CGM if cohort=='rbg' else CGM+STATIC+HR
    if artifact.get('features')!=expected:raise ValueError('Artifact feature schema mismatch')
    if artifact.get('horizon_minutes')!=horizon:raise ValueError('Artifact horizon mismatch')
    if cohort=='rbg':
        if artifact.get('sensor_delay_minutes')!=5:raise ValueError('Artifact delay mismatch')
        if artifact.get('version')!='rbg-baseline-v0.1':raise ValueError('Artifact version mismatch')
    else:
        if horizon!=60 or artifact.get('dataset')!='CGMacros reconstructed grid':raise ValueError('Artifact cohort mismatch')
        if artifact.get('version')!='baseline-v0.1':raise ValueError('Artifact version mismatch')
        if artifact.get('sklearn_version')!=sklearn.__version__:raise ValueError('Artifact sklearn version mismatch')
    if getattr(artifact.get('model'),'n_features_in_',None)!=len(expected):raise ValueError('Artifact model input mismatch')
    return artifact
