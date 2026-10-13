"""Audit frozen high-onset models on their cutoff patients only. No fitting/tuning."""
from pathlib import Path
from collections import Counter
import sys,json,hashlib,importlib.metadata
import numpy as np
import pandas as pd
import joblib
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from glucotwin.event_audit import audit_errors
from glucotwin.event_study import summarize
from glucotwin.event_replay import validate_event_artifact
from glucotwin.features import make_features,profile_features
from glucotwin.episodes import onsets


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root=ROOT):
    protocol_path=root/'configs/event_study_gpu_v2.json'
    manifest_path=root/'configs/cgmacros_splits.json'
    input_path=root/'data/processed/cgmacros_event_inputs_gpu_v2.json'
    report_path=root/'reports/event_study_gpu_v2.json'
    roles_path=root/'configs/cgmacros_event_roles_gpu_v2.json'
    frozen=json.loads(roles_path.read_text());inputs=json.loads(input_path.read_text())
    study=json.loads(report_path.read_text());protocol=json.loads(protocol_path.read_text())
    if importlib.metadata.version('xgboost')!=protocol['xgboost_version']:
        raise ValueError('Install the pinned event dependency')
    if frozen!=inputs['frozen'] or frozen['protocol_sha256']!=sha(protocol_path) or frozen['source_manifest_sha256']!=sha(manifest_path):
        raise ValueError('Frozen inputs or role manifest changed')
    for key,path in [('protocol_sha256',protocol_path),('source_manifest_sha256',manifest_path),('input_manifest_sha256',input_path)]:
        if study[key]!=sha(path):raise ValueError('Source study fingerprint changed')
    entries={p['patient_id']:p for p in json.loads(manifest_path.read_text())['participants']}
    reserved={pid for pid,p in entries.items() if p['split']=='test'}
    selected=set()
    for role in frozen['roles']:
        groups=[set(role[k]) for k in ('fit','threshold','evaluation')]
        if any(reserved & g for g in groups) or any(groups[a]&groups[b] for a,b in ((0,1),(0,2),(1,2))):
            raise ValueError('Invalid patient roles')
        selected.update(role['threshold'])
    base=root/'data/raw/cgmacros/CGMacros';bio_path=base/'bio.csv'
    if sha(bio_path)!=inputs['source_sha256']['bio']:raise ValueError('Profile source changed')
    # Source profile table is loaded, but only cutoff-patient rows are accessed.
    bio=pd.read_csv(bio_path);bio.columns=bio.columns.str.strip();bio=bio.set_index('subject')
    records={}
    for pid in sorted(selected):
        patient=entries[pid]
        path=base/f'CGMacros-{pid:03d}/CGMacros-{pid:03d}.csv'
        if sha(path)!=inputs['source_sha256'][str(pid)]:raise ValueError('Sensor source changed')
        features=make_features(pd.read_csv(path),profile_features(bio.loc[pid]),patient['phase_utc_minutes_mod_5'])
        glucose=features.cgm_current.copy()
        eligible=features.history_eligible & (features.cgm_current<=180) & (features.index>=pd.Timestamp(patient['minimum_forecast_time']))
        X=features.loc[eligible].drop(columns='history_eligible')
        records[pid]=dict(X=X,times=X.index,glucose=glucose,episodes=onsets(glucose,'high'))
    folds=[];all_metrics=[];alarms=Counter();episodes=Counter();artifacts=[]
    for i,role in enumerate(frozen['roles']):
        path=root/f'artifacts/cgmacros_onset_gpu_v2_fold{i+1}_fused.joblib'
        artifact=joblib.load(path)  # Trusted locally trained artifacts only.
        saved=study['folds'][i]['methods']['fused']
        # Verify the artifact contract without reading any evaluation-patient sensors.
        validate_event_artifact(artifact,entries[role['evaluation'][0]],role,sha(protocol_path),sha(input_path),inputs['columns'],saved['threshold'])
        artifacts.append(dict(fold=i+1,sha256=sha(path)))
        metrics=[];fold_alarms=Counter();fold_episodes=Counter()
        for pid in role['threshold']:
            r=records[pid]
            with threadpool_limits(limits=8):scores=artifact['model'].predict_proba(r['X'][artifact['features']])[:,1]
            result=audit_errors(r,scores,artifact['threshold'])
            metrics.append(result['metrics']);fold_alarms.update(result['alarm_categories']);fold_episodes.update(result['episode_categories'])
        aggregate=summarize(metrics)
        for key,value in saved['threshold_setting'].items():
            actual=aggregate[key]
            if value is None:
                if actual is not None:raise AssertionError(f'Fold {i+1}: {key} changed')
            elif not np.isclose(actual,value,rtol=1e-10,atol=1e-10):raise AssertionError(f'Fold {i+1}: {key} changed')
        folds.append(dict(fold=i+1,cutoff_patients=len(role['threshold']),metrics=aggregate,
                          alarm_categories=dict(fold_alarms),episode_categories=dict(fold_episodes)))
        all_metrics.extend(metrics);alarms.update(fold_alarms);episodes.update(fold_episodes)
        print(f'Fold {i+1}: frozen cutoff metrics reproduced',flush=True)
    return dict(version='high-event-cutoff-audit-v1',scope='Cutoff patients only; no fitting, cutoff changes, outer-evaluation scoring or reserved sensor reads.',
        unique_patients=len(selected),patient_fold_exposures=len(all_metrics),folds=folds,
        pooled_exposures=summarize(all_metrics),alarm_categories=dict(alarms),episode_categories=dict(episodes),
        fingerprints=dict(source_report=sha(report_path),protocol=sha(protocol_path),input_manifest=sha(input_path),
                          audit_script=sha(Path(__file__)),audit_module=sha(root/'src/glucotwin/event_audit.py'),models=artifacts),
        limitations=['Cutoffs were selected on these same patients; these are diagnostic results, not validation.',
                     'A patient can contribute to multiple folds; pooled values describe patient-fold exposures.',
                     'Error categories use future outcomes retrospectively, never as model inputs or revised labels.',
                     'False-alarm category priority: recent onset in [-30,0], later onset in (30,60], high reading in [5,30], no high reading.',
                     'High readings without qualifying onset can be brief excursions or fail the prior-normal requirement.',
                     'The source profile table includes reserved rows; only cutoff profiles are selected. Reserved sensor files are never opened.'])


if __name__=='__main__':
    output=ROOT/'reports/high_event_audit_v1.json'
    if output.exists():raise SystemExit('Audit checkpoint exists; do not overwrite it. Version a new audit.')
    result=run();output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('unique_patients','patient_fold_exposures','alarm_categories','episode_categories')},indent=2))
