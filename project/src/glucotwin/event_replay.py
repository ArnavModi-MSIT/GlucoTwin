"""Frozen CGMacros onset research replay; no fitting or operational alerts."""
from pathlib import Path
import hashlib
import json
import math
import importlib.metadata
import numpy as np
import pandas as pd
from glucotwin.features import make_features, STATIC, HR
from glucotwin.episodes import onsets


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_event_artifact(artifact, patient, role, protocol_hash, input_hash, columns, threshold):
    """Do not replay a patient through a model fitted/tuned on that patient."""
    pid = patient['patient_id']
    if patient['split'] == 'test':
        raise ValueError('Reserved test patients cannot be replayed')
    roles = [set(role[key]) for key in ('fit', 'threshold', 'evaluation')]
    if any(roles[a] & roles[b] for a, b in ((0, 1), (0, 2), (1, 2))):
        raise ValueError('Event roles overlap')
    if pid not in roles[2] or pid in roles[0] | roles[1]:
        raise ValueError('Event model requires an outer-evaluation patient')
    if artifact.get('roles') != role or artifact.get('method') != 'fused':
        raise ValueError('Event artifact roles or method changed')
    if artifact.get('protocol_sha256') != protocol_hash or artifact.get('input_manifest_sha256') != input_hash:
        raise ValueError('Event artifact fingerprint changed')
    if artifact.get('features') != columns or not set(STATIC + HR).issubset(columns):
        raise ValueError('Event artifact does not match fused features')
    cutoff = float(artifact.get('threshold', float('nan')))
    if not math.isfinite(cutoff) or cutoff != threshold:
        raise ValueError('Event cutoff changed')
    if artifact.get('probability_display_approved') is not False or artifact.get('operational_alerts_approved') is not False:
        raise ValueError('Only non-operational research artifacts can be replayed')
    if artifact.get('score_kind') != 'uncalibrated ranking score' or artifact.get('model') is None:
        raise ValueError('Unsupported event score/model')
    return artifact


def load_event_artifact(root, patient):
    """Load a trusted local model after validating the frozen study and sources."""
    import joblib
    root = Path(root)
    protocol_path = root / 'configs/event_study_gpu_v2.json'
    protocol = json.loads(protocol_path.read_text())
    if protocol['version'] != 'cgmacros-onset-gpu-v2' or protocol['warning_window_minutes'] != [5, 30]:
        raise ValueError('Unsupported event protocol')
    if importlib.metadata.version('xgboost') != protocol['xgboost_version']:
        raise ValueError('Pinned event model dependency is required')
    protocol_hash = sha(protocol_path)
    frozen = json.loads((root / 'configs/cgmacros_event_roles_gpu_v2.json').read_text())
    manifest_hash = sha(root / 'configs/cgmacros_splits.json')
    if frozen['protocol_sha256'] != protocol_hash or frozen['source_manifest_sha256'] != manifest_hash:
        raise ValueError('Frozen event protocol or patient manifest changed')
    pid = patient['patient_id']
    if patient['split'] == 'test':
        raise ValueError('Reserved test patients cannot be replayed')
    matching = [(i, r) for i, r in enumerate(frozen['roles']) if pid in r['evaluation']]
    if len(matching) != 1:
        raise ValueError('Patient has no unique event evaluation fold')
    fold, role = matching[0]
    input_path = root / 'data/processed/cgmacros_event_inputs_gpu_v2.json'
    inputs = json.loads(input_path.read_text())
    if inputs['frozen'] != frozen:
        raise ValueError('Event input manifest changed')
    base = root / 'data/raw/cgmacros/CGMacros'
    if (sha(base / 'bio.csv') != inputs['source_sha256']['bio'] or
            sha(base / f'CGMacros-{pid:03d}/CGMacros-{pid:03d}.csv') != inputs['source_sha256'][str(pid)]):
        raise ValueError('Event replay source differs from frozen study')
    report = json.loads((root / 'reports/event_study_gpu_v2.json').read_text())
    if (report['protocol_sha256'] != protocol_hash or report['source_manifest_sha256'] != manifest_hash or
            report['input_manifest_sha256'] != sha(input_path)):
        raise ValueError('Event report fingerprint changed')
    fold_report = report['folds'][fold]
    if fold_report['fold'] != fold + 1:
        raise ValueError('Event fold order changed')
    artifact = joblib.load(root / f'artifacts/cgmacros_onset_gpu_v2_fold{fold+1}_fused.joblib')
    validate_event_artifact(artifact, patient, role, protocol_hash, sha(input_path),
                            inputs['columns'], fold_report['methods']['fused']['threshold'])
    return artifact, {'fold': fold + 1, 'version': protocol['version'],
                      'cutoff_criteria_met': bool(fold_report['methods']['fused']['threshold_gate_passed']),
                      'fit_patients': len(role['fit']), 'cutoff_patients': len(role['threshold']),
                      'evaluation_patients': len(role['evaluation'])}


def issue_event(frame, profile, patient, artifact, now, ledger):
    """Predict from a visible prefix only; preserve score/cutoff/decision at issue."""
    if patient['split'] == 'test':
        raise ValueError('Reserved test patients cannot be replayed')
    now = pd.Timestamp(now)
    roles = artifact['roles']
    pid = patient['patient_id']
    if pid not in roles['evaluation'] or pid in roles['fit'] + roles['threshold']:
        raise ValueError('Event model requires an outer-evaluation patient')
    features = make_features(frame.loc[pd.to_datetime(frame.Timestamp) <= now], profile,
                             patient['phase_utc_minutes_mod_5'])
    row = {'issued_at': now, 'window_start': now + pd.Timedelta(minutes=5),
           'window_end': now + pd.Timedelta(minutes=30), 'available_at': now + pd.Timedelta(minutes=45),
           'score': None, 'cutoff': float(artifact['threshold']), 'research_flag': False,
           'status': 'Insufficient history', 'model_inputs': list(artifact['features'])}
    if now not in features.index:
        return row
    f = features.loc[now]
    if now < pd.Timestamp(patient['minimum_forecast_time']):
        row['status'] = '24-hour warm-up'
    elif not f.history_eligible:
        pass
    elif f.cgm_current > 180:
        row['status'] = 'Already above high threshold'
    else:
        score = float(artifact['model'].predict_proba(features.loc[[now], artifact['features']])[0, 1])
        if not math.isfinite(score):
            raise ValueError('Non-finite event score')
        row['score'] = score
        flags = [pd.Timestamp(r['issued_at']) for r in ledger if r['research_flag']]
        cooldown = bool(flags and now < flags[-1] + pd.Timedelta(minutes=60))
        row['research_flag'] = bool(score >= row['cutoff'] and not cooldown)
        row['status'] = ('Research flag' if row['research_flag'] else
                         'Cooldown' if score >= row['cutoff'] and cooldown else 'Below cutoff')
    return row


def reveal_events(ledger, frame, patient, now):
    """Reveal only matured windows from visible observations, never future labels."""
    now = pd.Timestamp(now)
    visible = frame.loc[pd.to_datetime(frame.Timestamp) <= now].copy()
    visible.Timestamp = pd.to_datetime(visible.Timestamp)
    phase = patient['phase_utc_minutes_mod_5']
    minutes = visible.Timestamp.astype('int64') // 60_000_000_000
    glucose = pd.to_numeric(visible.loc[minutes % 5 == phase].set_index('Timestamp')['Dexcom GL'], errors='coerce')
    episodes = onsets(glucose, 'high') if len(glucose) else pd.DatetimeIndex([])
    output = []
    for issued in ledger:
        row = dict(issued)
        row.update(outcome='Not evaluated', event_at=None, lead_minutes=None)
        if row['score'] is not None:
            row['outcome'] = 'Pending'
            if pd.Timestamp(row['available_at']) <= now:
                matches = episodes[(episodes >= row['window_start']) & (episodes <= row['window_end'])]
                if len(matches):
                    row.update(outcome='Qualifying onset observed', event_at=matches[0],
                               lead_minutes=float((matches[0] - row['issued_at']).total_seconds() / 60))
                else:
                    future = glucose.reindex(pd.date_range(row['window_start'], row['available_at'], freq='5min'))
                    row['outcome'] = 'No qualifying onset' if np.isfinite(future).all() else 'Incomplete observations'
        output.append(row)
    return output
