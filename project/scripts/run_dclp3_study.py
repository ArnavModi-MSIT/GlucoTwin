"""Run fixed DCLP3 CPU baselines without scoring any reserved participants."""
from collections import defaultdict
import json
import threading
import time

import joblib
import numpy as np
import psutil
import sklearn
import xgboost
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from xgboost import XGBRegressor

from prepare_dclp3 import ROOT, CACHE, PROTOCOL, ROLES, digest, write
from glucotwin.dclp3_study import matrix, row_digest, equal_patient_weights, patient_rows, summarize, paired_comparison

REPORT = ROOT/'reports/dclp3_study_v2.json'
ARTIFACTS = ROOT/'artifacts/dclp3_v2'


def load_cache(protocol, roles):
    stamp = json.loads((CACHE/'manifest.json').read_text())
    checks = json.loads((ROOT/'reports/dclp3_preparation_checks_v2.json').read_text())
    if checks['status'] != 'passed' or checks['contract_sha256'] != digest(PROTOCOL):
        raise ValueError('Preparation checks do not match current contract')
    if stamp['protocol_sha256'] != digest(PROTOCOL) or stamp['manifest_sha256'] != digest(ROLES):
        raise ValueError('Frozen roles/preparation contract changed')
    if set(stamp['prepared_participants']) != set(roles['development']) or set(roles['reserved']) & set(stamp['prepared_participants']):
        raise ValueError('Prepared roles are invalid')
    records = {}
    for pid in roles['development']:
        path = CACHE/(pid+'.npz')
        if digest(path) != stamp['cache_sha256'][pid]:
            raise ValueError('Prepared participant cache changed')
        with np.load(path, allow_pickle=False) as archive:
            records[pid] = {key: archive[key] for key in archive.files}
    return stamp, records


def execution_manifest(protocol, stamp):
    execution = {'protocol_sha256': digest(PROTOCOL), 'roles_sha256': digest(ROLES),
        'cache_manifest_sha256': digest(CACHE/'manifest.json'),
        'runner_sha256': digest(__file__), 'metrics_sha256': digest(ROOT/'src/glucotwin/dclp3_study.py'),
        'versions': {'sklearn': sklearn.__version__, 'xgboost': xgboost.__version__},
        'cohorts': {'all_clinical': ['cgm_only', 'cgm_profile'],
                    'pump_linked': ['cgm_only', 'cgm_profile', 'cgm_profile_insulin']},
        'methods': ['persistence', 'ridge', 'xgb_delta'], 'bootstrap_repetitions': 2000,
        'delta_definition': 'XGBoost predicts target minus latest available CGM; Ridge predicts target directly',
        'sampling': 'sample each patient once per horizon with identical RNG in both cohorts',
        'features': stamp['features']}
    path = CACHE/'study_execution.json'
    if path.exists() and json.loads(path.read_text()) != execution:
        raise ValueError('Existing execution configuration differs; use a new study version')
    write(path, execution)
    return execution, digest(path)


def public_scores(accumulated, roles):
    scores = {name: summarize(rows) for name, rows in accumulated.items()}
    grouped = {}
    for treatment in ('CLC', 'SAP'):
        grouped[treatment] = {name: summarize([r for r in rows if roles['strata'][r['patient_id']].startswith(treatment+'_')])
                              for name, rows in accumulated.items()}
    comparisons = {}
    for kind in ('ridge', 'xgb_delta'):
        profile, base = kind+'_cgm_profile', kind+'_cgm_only'
        if profile in accumulated:
            comparisons[profile+'_versus_'+base] = paired_comparison(accumulated[profile], accumulated[base])
        insulin = kind+'_cgm_profile_insulin'
        if insulin in accumulated:
            comparisons[insulin+'_versus_'+profile] = paired_comparison(accumulated[insulin], accumulated[profile])
        for name in [k for k in accumulated if k.startswith(kind+'_')]:
            comparisons[name+'_versus_persistence'] = paired_comparison(accumulated[name], accumulated['persistence'])
    return {'scores': scores, 'by_treatment_group': grouped, 'paired_comparisons': comparisons}


def run():
    started = time.perf_counter()
    protocol, roles = json.loads(PROTOCOL.read_text()), json.loads(ROLES.read_text())
    stamp, records = load_cache(protocol, roles)
    execution, execution_sha = execution_manifest(protocol, stamp)
    columns, arms = stamp['features'], stamp['arms']
    current_column = columns.index('cgm_current')
    public = {'version': protocol['version'], 'status': 'running', 'units': 'mg/dL',
        'execution_sha256': execution_sha, 'protocol_sha256': digest(PROTOCOL),
        'roles_sha256': digest(ROLES), 'versions': execution['versions'],
        'reserved_patients_scored': 0, 'development_patients': len(roles['development']),
        'target_interpretation': 'observed values within +/-30 seconds; strict zero-offset subset reported separately; boundary-coded target values omitted from point scores',
        'availability': protocol['availability_interpretation'], 'horizons': {},
        'selection': 'all fixed methods reported; no outer-score-driven tuning or model promotion',
        'operational_alerts_approved': False}
    private = {'execution_sha256': execution_sha, 'horizons': {}}
    stop, peak = threading.Event(), [psutil.Process().memory_info().rss]
    def sample_memory():
        process = psutil.Process()
        while not stop.wait(.25):
            peak[0] = max(peak[0], process.memory_info().rss)
    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    try:
        pump_ids = set(roles['pump_participants']) & set(roles['development'])
        for horizon in protocol['horizons_minutes']:
            public['horizons'][str(horizon)], private['horizons'][str(horizon)] = {}, {}
            for cohort, arm_names in execution['cohorts'].items():
                accumulated, fold_summaries = defaultdict(list), []
                for fold in roles['folds']:
                    fit_ids, eval_ids = fold['fit'], fold['evaluation']
                    if cohort == 'pump_linked':
                        fit_ids = [p for p in fit_ids if p in pump_ids]
                        eval_ids = [p for p in eval_ids if p in pump_ids]
                    fit = matrix(records, fit_ids, horizon, protocol['fit_row_cap_per_patient'], protocol['seed'], roles['development'])
                    evaluation = matrix(records, eval_ids, horizon, None, protocol['seed'], roles['development'])
                    fit_sha, evaluation_sha = row_digest(fit), row_digest(evaluation)
                    weights = equal_patient_weights(fit['groups'])
                    current = evaluation['X'][:, current_column].astype(float)
                    predictions = {'actual': evaluation['y'], 'groups': evaluation['groups'],
                        'issued_at': evaluation['times'], 'strict': evaluation['strict'], 'persistence': current}
                    accumulated['persistence'].extend(patient_rows(evaluation['y'], current, current, evaluation['groups'], evaluation['strict']))
                    for kind in ('ridge', 'xgb_delta'):
                        for arm in arm_names:
                            indices = arms[arm]
                            name = kind+'_'+arm
                            imputer = SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)
                            if kind == 'ridge':
                                model = make_pipeline(imputer, StandardScaler(), Ridge(**protocol['models']['ridge']))
                                response = fit['y']
                            else:
                                model = make_pipeline(imputer, XGBRegressor(**protocol['models']['xgb_delta'],
                                    n_jobs=protocol['threads'], random_state=protocol['seed']))
                                response = fit['y']-fit['X'][:, current_column]
                            path = ARTIFACTS/cohort/str(horizon)/f'fold{fold["fold"]}'/(name+'.joblib')
                            metadata = {'execution_sha256': execution_sha, 'fit_row_sha256': fit_sha,
                                'evaluation_row_sha256': evaluation_sha, 'feature_names': [columns[i] for i in indices],
                                'predicts_delta': kind == 'xgb_delta'}
                            model_started = time.perf_counter()
                            with threadpool_limits(limits=protocol['threads']):
                                if path.exists():
                                    artifact = joblib.load(path)
                                    if any(artifact[key] != value for key, value in metadata.items()):
                                        raise ValueError('Existing model belongs to different rows/execution')
                                    model = artifact['model']
                                else:
                                    final = list(model.named_steps)[-1]
                                    model.fit(fit['X'][:, indices], response, **{final+'__sample_weight': weights})
                                    path.parent.mkdir(parents=True, exist_ok=True)
                                    joblib.dump({'model': model, **metadata}, path)
                                predicted = model.predict(evaluation['X'][:, indices]).astype(float)
                            if kind == 'xgb_delta':
                                predicted += current
                            if not np.isfinite(predicted).all():
                                raise ValueError('Nonfinite predictions; no silent scoring-row removal')
                            accumulated[name].extend(patient_rows(evaluation['y'], predicted, current, evaluation['groups'], evaluation['strict']))
                            predictions[name] = predicted
                            print(f'{horizon}m {cohort} fold{fold["fold"]}/4 {name}: {time.perf_counter()-model_started:.1f}s', flush=True)
                    folder = CACHE/'outer_predictions'/cohort/str(horizon)
                    folder.mkdir(parents=True, exist_ok=True)
                    np.savez_compressed(folder/f'fold{fold["fold"]}.npz', **predictions)
                    fold_summaries.append({'fold': fold['fold'], 'fit_patients': len(fit_ids),
                        'evaluation_patients': len(eval_ids), 'sampled_fit_rows': len(fit['y']),
                        'evaluation_rows': len(evaluation['y']), 'fit_row_sha256': fit_sha,
                        'evaluation_row_sha256': evaluation_sha})
                    del fit, evaluation, predictions
                    public['horizons'][str(horizon)][cohort] = {'completed_folds': len(fold_summaries),
                        'folds': fold_summaries, **public_scores(accumulated, roles)}
                    private['horizons'][str(horizon)][cohort] = dict(accumulated)
                    write(CACHE/'study_private_v2.json', private)
                    write(REPORT, public)
                print(f'{horizon}m {cohort} complete: '+json.dumps({name: round(summarize(rows)['mae'], 3) for name, rows in accumulated.items()}), flush=True)
        public.update({'status': 'complete', 'runtime': {'seconds': round(time.perf_counter()-started, 2),
                       'sampled_peak_rss_mib': round(peak[0]/1048576, 2), 'threads': protocol['threads']}})
        write(REPORT, public)
    finally:
        stop.set()
        sampler.join(timeout=2)
    return public


if __name__ == '__main__':
    run()
