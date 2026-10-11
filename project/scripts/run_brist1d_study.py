"""Freeze, prepare and run bounded native-cadence BrisT1D CPU ablations."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import threading
import time

import joblib
import numpy as np
import pandas as pd
import psutil
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from glucotwin.brist1d import issue_times, make_brist_features, measured_targets, feature_arms, assign_roles
from glucotwin.regression_diagnostics import sliced_errors, patient_macro
from audit_brist1d_cohort import canonical_stream, CHANNELS

SOURCE = ROOT/'data/raw/33z5jc8fa6tob21ptrugzqog08/device_data/processed_state'
PROTOCOL = ROOT/'configs/brist1d_contract_v1.json'
ROLES = ROOT/'configs/brist1d_roles_v1.json'
CACHE = ROOT/'data/processed/brist1d_v1'
PRIVATE_AUDIT = ROOT/'data/processed/brist1d_cohort_audit_private.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')


def freeze():
    protocol = json.loads(PROTOCOL.read_text())
    entries = json.loads(PRIVATE_AUDIT.read_text())['participants']
    assignments = assign_roles(entries, protocol['seed'])
    rows = {r['participant_id']: {'profile': r['profile'], 'source_sha256': r['source_sha256'],
                                'native_minutes': r['channels']['bg']['modal_gap_minutes']} for r in entries}
    manifest = {'version': protocol['version'], 'protocol_sha256': digest(PROTOCOL),
                'cohort_audit_sha256': digest(PRIVATE_AUDIT), **assignments, 'participants': rows}
    if ROLES.exists() and json.loads(ROLES.read_text()) != manifest:
        raise ValueError('Existing frozen roles/source/protocol differ; refusing overwrite')
    write_json(ROLES, manifest)
    write_json(ROOT/'reports/brist1d_contract_summary.json', {
        'version': protocol['version'], 'protocol_sha256': digest(PROTOCOL),
        'manifest_sha256': digest(ROLES), 'seed': protocol['seed'],
        'patients': 20, 'development': 16, 'reserved_test': 4,
        'development_folds': 4, 'fit_per_fold': 12, 'evaluation_per_fold': 4,
        'cadence_per_group': {'5min': 3, '15min': 1},
        'reserved_status': 'quality-audited previously; no feature matrices or prediction scores generated',
        'status': 'roles and availability assumptions frozen before fitting'})
    return protocol, manifest


def load_development_frame(pid, manifest, source=SOURCE, reader=pd.read_csv):
    if pid not in manifest['development'] or pid in manifest['reserved']:
        raise ValueError('Refusing reserved or unknown participant sensor access')
    path = source/(pid+'.csv')
    if digest(path) != manifest['participants'][pid]['source_sha256']:
        raise ValueError('Participant source changed after cohort audit')
    return reader(path, dtype={'device': 'string', 'activity': 'string'})


def prepare(protocol, manifest):
    started = time.perf_counter()
    counts = []
    columns = None
    for i, pid in enumerate(manifest['development'], 1):
        source = load_development_frame(pid, manifest)
        device_ok = source.device.fillna('').str.strip().ne('')
        dropped_device_rows = int((~device_ok).sum())
        source = source.loc[device_ok].copy()
        source['timestamp'] = pd.to_datetime(source.timestamp, errors='raise')
        streams = {channel: canonical_stream(source, channel)[0] for channel in CHANNELS}
        patient = manifest['participants'][pid]
        issues = issue_times(streams['bg'], patient['native_minutes'], protocol['availability_delay_minutes']['bg'])
        features = make_brist_features(streams, patient['profile'], patient['native_minutes'], issues, protocol)
        selected = features.loc[features.history_eligible].drop(columns='history_eligible')
        names = selected.columns.tolist()
        if columns is not None and columns != names:
            raise ValueError('Feature column drift between participants')
        columns = names
        targets = {str(h): measured_targets(streams['bg'], selected.index, h) for h in protocol['horizons_minutes']}
        CACHE.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(CACHE/(pid+'.npz'), X=selected.to_numpy(dtype=np.float32),
                            times=selected.index.to_numpy(dtype='datetime64[ns]').astype('int64'),
                            **{'y'+h: values for h, values in targets.items()})
        counts.append({'participant_id': pid, 'source_glucose': len(streams['bg']),
                       'excluded_missing_device_rows': dropped_device_rows, 'potential_issue_times': len(issues),
                       'history_eligible': len(selected), 'target_rows': {h: int(np.isfinite(y).sum()) for h, y in targets.items()}})
        print(f'Prepared development participant {i}/16', flush=True)
    stamp = {'protocol_sha256': digest(PROTOCOL), 'manifest_sha256': digest(ROLES),
             'features': columns, 'arms': feature_arms(columns),
             'prepared_participants': manifest['development'], 'cache_sha256': {
                 pid: digest(CACHE/(pid+'.npz')) for pid in manifest['development']}}
    write_json(CACHE/'manifest.json', stamp)
    write_json(CACHE/'counts_private.json', counts)
    aggregate = {'version': protocol['version'], 'development_patients': len(counts),
                 'reserved_patients_prepared': 0, 'features': len(columns),
                 'arm_feature_counts': {name: len(indices) for name, indices in stamp['arms'].items()},
                 'source_glucose': sum(r['source_glucose'] for r in counts),
                 'potential_issue_times': sum(r['potential_issue_times'] for r in counts),
                 'history_eligible': sum(r['history_eligible'] for r in counts),
                 'excluded_missing_device_rows': sum(r['excluded_missing_device_rows'] for r in counts),
                 'target_rows': {str(h): sum(r['target_rows'][str(h)] for r in counts) for h in protocol['horizons_minutes']},
                 'seconds': round(time.perf_counter()-started, 2), 'protocol_sha256': digest(PROTOCOL),
                 'note': 'Targets are exact measured values at issue+horizon, not cutoff+horizon; no resampling or future imputation.'}
    write_json(ROOT/'reports/brist1d_preparation.json', aggregate)
    print(json.dumps(aggregate), flush=True)


def load_cache(manifest):
    stamp = json.loads((CACHE/'manifest.json').read_text())
    if stamp['protocol_sha256'] != digest(PROTOCOL) or stamp['manifest_sha256'] != digest(ROLES):
        raise ValueError('Prepared cache contract differs from frozen study')
    if sorted(stamp['prepared_participants']) != manifest['development']:
        raise ValueError('Prepared participant role mismatch')
    records = {}
    for pid in manifest['development']:
        path = CACHE/(pid+'.npz')
        if digest(path) != stamp['cache_sha256'][pid]:
            raise ValueError('Prepared cache changed')
        with np.load(path, allow_pickle=False) as archive:
            records[pid] = {key: archive[key] for key in archive.files}
    return stamp, records


def matrix(records, ids, horizon, cap, seed):
    parts, targets, groups = [], [], []
    for pid in ids:
        record = records[pid]
        target = record['y'+str(horizon)]
        positions = np.flatnonzero(np.isfinite(target))
        if cap is not None and len(positions) > cap:
            rng = np.random.default_rng(seed+int(pid[1:])*1000+horizon)
            positions = np.sort(rng.choice(positions, size=cap, replace=False))
        if not len(positions):
            raise ValueError('Participant has no eligible measured targets')
        parts.append(record['X'][positions]); targets.append(target[positions])
        groups.extend([pid]*len(positions))
    return np.concatenate(parts), np.concatenate(targets), np.asarray(groups)


def patient_rows(actual, predicted, groups):
    result = []
    for pid in np.unique(groups):
        mask = groups == pid
        error = predicted[mask]-actual[mask]
        result.append({'patient_id': str(pid), 'n': int(mask.sum()),
                       'absolute_error_sum': float(np.abs(error).sum()), 'squared_error_sum': float((error**2).sum()),
                       'diagnostics': sliced_errors(actual[mask], predicted[mask])})
    return result


def summarize(rows):
    n = sum(row['n'] for row in rows)
    return {'patients': len(rows), 'rows': n, 'mae': sum(r['absolute_error_sum'] for r in rows)/n,
            'rmse': float(np.sqrt(sum(r['squared_error_sum'] for r in rows)/n)),
            'patient_macro_slices': {name: patient_macro(rows, name) for name in ('all', 'high', 'low')},
            'tail_interpretation': 'mean of patient quantiles, not a pooled row quantile'}


def paired_comparison(candidate, reference, repetitions, seed):
    left = {r['patient_id']: r for r in candidate}; right = {r['patient_id']: r for r in reference}
    if set(left) != set(right) or any(left[p]['n'] != right[p]['n'] for p in left):
        raise ValueError('Unmatched participant/row comparison')
    output = {}
    rng = np.random.default_rng(seed)
    for slice_name, key in (('all', 'mae'), ('all', 'rmse'), ('all', 'p95_absolute_error'), ('high', 'mae'), ('low', 'mae')):
        support = [p for p in sorted(left) if left[p]['diagnostics'][slice_name]['n'] and right[p]['diagnostics'][slice_name]['n']]
        values = np.array([left[p]['diagnostics'][slice_name][key]-right[p]['diagnostics'][slice_name][key] for p in support])
        if not len(values):
            output[slice_name+'_'+key] = {'patients': 0, 'mean_difference': None, 'patient_bootstrap95': None}
            continue
        samples = rng.choice(values, size=(repetitions, len(values)), replace=True).mean(axis=1)
        output[slice_name+'_'+key] = {'patients': len(values), 'mean_difference': float(values.mean()),
                                    'patient_bootstrap95': np.quantile(samples, [.025, .975]).tolist()}
    return output


def train(protocol, manifest):
    from xgboost import XGBRegressor
    import xgboost
    import sklearn
    started = time.perf_counter()
    stop = threading.Event()
    peak = [psutil.Process().memory_info().rss]
    def sample_memory():
        process = psutil.Process()
        while not stop.wait(.25):
            peak[0] = max(peak[0], process.memory_info().rss)
    sampler = threading.Thread(target=sample_memory, daemon=True); sampler.start()
    try:
        stamp, records = load_cache(manifest)
        columns = stamp['features']; arms = stamp['arms']
        public = {'version': protocol['version'], 'protocol_sha256': digest(PROTOCOL),
                  'manifest_sha256': digest(ROLES), 'units': 'mg/dL',
                  'status': 'fixed-method development ablation; no reserved-test scores or model deployment',
                  'development_patients': len(manifest['development']), 'reserved_patients_scored': 0,
                  'versions': {'sklearn': sklearn.__version__, 'xgboost': xgboost.__version__},
                  'horizons': {}, 'availability': protocol['availability_interpretation'],
                  'limitation': 'Whole-cohort source quality was inspected before role assignment. Development results do not establish clinical reliability or improvement over a different dataset.'}
        private = {'manifest': manifest, 'horizons': {}}
        artifact_root = ROOT/'artifacts/brist1d_v1'
        for horizon in protocol['horizons_minutes']:
            accumulated = {}; fold_summary = []
            for role in manifest['folds']:
                Xfit, yfit, gfit = matrix(records, role['fit'], horizon, protocol['fit_row_cap_per_patient'], protocol['seed'])
                Xeval, yeval, geval = matrix(records, role['evaluation'], horizon, None, protocol['seed'])
                counts = {pid: int((gfit == pid).sum()) for pid in role['fit']}
                weights = np.array([1/counts[pid] for pid in gfit]); weights *= len(weights)/weights.sum()
                baseline = patient_rows(yeval, Xeval[:, columns.index('cgm_current')].astype(float), geval)
                accumulated.setdefault('persistence', []).extend(baseline)
                predictions = {'actual': yeval, 'issued_at': np.concatenate([
                    records[pid]['times'][np.isfinite(records[pid]['y'+str(horizon)])] for pid in role['evaluation']]),
                    'persistence': Xeval[:, columns.index('cgm_current')], 'groups': geval}
                for kind in protocol['models']:
                    for arm, indices in arms.items():
                        imputer = SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)
                        if kind == 'ridge':
                            model = make_pipeline(imputer, StandardScaler(), Ridge(**protocol['models']['ridge']))
                            fitted_y = yfit
                        else:
                            model = make_pipeline(imputer, XGBRegressor(**protocol['models']['xgb_delta'],
                                n_jobs=protocol['threads'], random_state=protocol['seed']))
                            fitted_y = yfit-Xfit[:, columns.index('cgm_current')]
                        final = list(model.named_steps)[-1]
                        with threadpool_limits(limits=protocol['threads']):
                            model.fit(Xfit[:, indices], fitted_y, **{final+'__sample_weight': weights})
                            predicted = model.predict(Xeval[:, indices]).astype(float)
                        if kind == 'xgb_delta':
                            predicted += Xeval[:, columns.index('cgm_current')]
                        name = kind+'_'+arm
                        accumulated.setdefault(name, []).extend(patient_rows(yeval, predicted, geval))
                        predictions[name] = predicted
                        path = artifact_root/str(horizon)/f'fold{role["fold"]}'/(name+'.joblib')
                        path.parent.mkdir(parents=True, exist_ok=True)
                        joblib.dump({'model': model, 'feature_names': [columns[i] for i in indices],
                                     'predicts_delta': kind == 'xgb_delta', 'protocol_sha256': digest(PROTOCOL)}, path)
                        print(f'{horizon}min fold {role["fold"]}/4 {name}: done', flush=True)
                folder = CACHE/'outer_predictions'/str(horizon); folder.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(folder/f'fold{role["fold"]}.npz', **predictions)
                fold_summary.append({'fold': role['fold'], 'fit_patients': len(role['fit']), 'evaluation_patients': len(role['evaluation']),
                                     'sampled_fit_rows': len(yfit), 'evaluation_rows': len(yeval)})
            private['horizons'][str(horizon)] = accumulated
            comparisons = {}
            for kind in protocol['models']:
                for i, arm in enumerate(protocol['arms'][1:], 1):
                    name = kind+'_'+arm; prior = kind+'_'+protocol['arms'][i-1]
                    comparisons[name+'_versus_'+prior] = paired_comparison(accumulated[name], accumulated[prior],
                        protocol['bootstrap_repetitions'], protocol['seed'])
                name = kind+'_fused'; prior = kind+'_cgm_profile'
                comparisons[name+'_versus_'+prior] = paired_comparison(accumulated[name], accumulated[prior],
                    protocol['bootstrap_repetitions'], protocol['seed'])
            public['horizons'][str(horizon)] = {'scores': {name: summarize(rows) for name, rows in accumulated.items()},
                'paired_input_comparisons': comparisons, 'folds': fold_summary,
                'selection': 'all fixed methods reported; no post-hoc winner promoted'}
            write_json(CACHE/'study_private.json', private)
            write_json(ROOT/'reports/brist1d_study_v1.json', public)
            print(f'{horizon}min aggregate: '+json.dumps({name: round(summarize(rows)['mae'], 3) for name, rows in accumulated.items()}), flush=True)
        public['runtime'] = {'seconds': round(time.perf_counter()-started, 2),
                             'sampled_peak_rss_mib': round(peak[0]/1048576, 2), 'threads': protocol['threads']}
        write_json(ROOT/'reports/brist1d_study_v1.json', public)
        return public
    finally:
        stop.set(); sampler.join(timeout=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', choices=['freeze', 'prepare', 'train', 'all'], default='all')
    args = parser.parse_args()
    protocol, manifest = freeze()
    if args.action in ('prepare', 'all'):
        prepare(protocol, manifest)
    if args.action in ('train', 'all'):
        train(protocol, manifest)
