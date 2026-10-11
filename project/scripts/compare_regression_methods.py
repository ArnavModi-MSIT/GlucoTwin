"""Local fixed-method comparison on CGMacros development patients, never reserved sensors."""
from pathlib import Path
import sys, json, time, argparse
import hashlib
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits
from xgboost import XGBRegressor
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from glucotwin.features import make_features, profile_features
from glucotwin.research_features import extend_history
from run_event_study import freeze_roles
from glucotwin.regression_diagnostics import sliced_errors,patient_macro,select_guarded


def run(study='v3'):
    start = time.perf_counter()
    protocol = json.loads((ROOT / f'configs/regression_methods_{study}.json').read_text())
    manifest = json.loads((ROOT / 'configs/cgmacros_splits.json').read_text())
    entries, roles = freeze_roles(manifest, protocol)
    if study=='v5':
        run_manifest={'protocol_sha256':hashlib.sha256((ROOT / f'configs/regression_methods_{study}.json').read_bytes()).hexdigest(),
                      'source_manifest_sha256':hashlib.sha256((ROOT/'configs/cgmacros_splits.json').read_bytes()).hexdigest(),
                      'roles':roles}
        path=ROOT/'configs/regression_roles_v5.json'
        if path.exists() and json.loads(path.read_text())!=run_manifest:raise RuntimeError('Frozen regression protocol changed')
        path.write_text(json.dumps(run_manifest,indent=2),encoding='utf-8')
    source = ROOT / 'data/raw/cgmacros/CGMacros'
    bio = pd.read_csv(source / 'bio.csv'); bio.columns = bio.columns.str.strip(); bio = bio.set_index('subject')
    records = {}
    for patient in entries:
        pid = patient['patient_id']
        frame = pd.read_csv(source / f'CGMacros-{pid:03d}/CGMacros-{pid:03d}.csv')
        base = make_features(frame, profile_features(bio.loc[pid]), patient['phase_utc_minutes_mod_5'])
        extended = extend_history(base)
        eligible = base.history_eligible & (base.index >= pd.Timestamp(patient['minimum_forecast_time']))
        records[pid] = {'base': base.drop(columns='history_eligible'),
                        'extended': extended.drop(columns='history_eligible'), 'eligible': eligible}
    output = {'protocol': protocol, 'status': 'exploratory development comparison; no reserved-test evaluation', 'horizons': {}}
    for horizon in protocol['horizons_minutes']:
        rows = []
        for fold, role in enumerate(roles):
            models = {
                'ridge_original': make_pipeline(SimpleImputer(), StandardScaler(), Ridge(alpha=10)),
                'hist_extended': make_pipeline(SimpleImputer(add_indicator=True), HistGradientBoostingRegressor(
                    loss='absolute_error', max_iter=300, max_leaf_nodes=15, min_samples_leaf=40,
                    learning_rate=.04, l2_regularization=10, early_stopping=False, random_state=2026)),
                'xgb_extended': make_pipeline(SimpleImputer(add_indicator=True), XGBRegressor(
                    objective='reg:absoluteerror', n_estimators=600, max_depth=3, learning_rate=.03,
                    min_child_weight=10, subsample=.8, colsample_bytree=.8, reg_lambda=10,
                    tree_method='hist', device='cpu', n_jobs=8, random_state=2026))}
            if 'xgb_delta_extended' in protocol['candidates']:
                from sklearn.base import clone
                models['xgb_delta_extended'] = clone(models['xgb_extended'])
            if study=='v5':
                from sklearn.base import clone
                for name,objective in [('xgb_delta_squared','reg:squarederror'),('xgb_delta_huber','reg:pseudohubererror')]:
                    models[name]=clone(models['xgb_extended']).set_params(xgbregressor__objective=objective)
                models['xgb_delta_huber'].set_params(xgbregressor__huber_slope=10.)
                models={k:v for k,v in models.items() if k in protocol['candidates']}
            def data(ids, kind):
                parts = []; targets = []; groups = []
                for pid in ids:
                    r = records[pid]; target = r['base'].cgm_current.shift(-horizon // 5)
                    mask = r['eligible'] & target.notna()
                    parts.append(r[kind].loc[mask]); targets.append(target[mask].to_numpy()); groups.extend([pid] * int(mask.sum()))
                return pd.concat(parts), np.concatenate(targets), np.array(groups)
            tuning = {}; evaluation = {}
            for name, model in models.items():
                kind = 'base' if name == 'ridge_original' else 'extended'
                X, y, groups = data(role['fit'], kind)
                unique, counts = np.unique(groups, return_counts=True); sizes = dict(zip(unique, counts))
                weights = np.array([1 / sizes[p] for p in groups]); weights *= len(weights) / weights.sum()
                final = list(model.named_steps)[-1]
                fitted_y = y - X.cgm_current.to_numpy() if name.startswith('xgb_delta') else y
                with threadpool_limits(limits=8): model.fit(X, fitted_y, **{final + '__sample_weight': weights})
                for ids, destination in ((role['threshold'], tuning), (role['evaluation'], evaluation)):
                    X, y, groups = data(ids, kind)
                    with threadpool_limits(limits=8): prediction = model.predict(X)
                    if name.startswith('xgb_delta'): prediction += X.cgm_current.to_numpy()
                    error = np.abs(prediction - y)
                    destination[name] = [{'patient_id': int(pid), 'n': int((groups == pid).sum()),
                        'absolute_error_sum': float(error[groups == pid].sum()),
                        'squared_error_sum': float(((prediction[groups == pid] - y[groups == pid]) ** 2).sum()),
                        'mae': float(error[groups == pid].mean())} for pid in ids]
                    if study=='v5':
                        for row in destination[name]:
                            mask=groups==row['patient_id'];row['diagnostics']=sliced_errors(y[mask],prediction[mask])
            if study=='v5':chosen,guardrails=select_guarded(tuning,protocol['guardrails'])
            else:chosen = min(tuning, key=lambda name: np.mean([r['mae'] for r in tuning[name]]))
            X, y, groups = data(role['evaluation'], 'base'); error = np.abs(X.cgm_current.to_numpy() - y)
            evaluation['persistence'] = [{'patient_id': int(pid), 'n': int((groups == pid).sum()),
                'absolute_error_sum': float(error[groups == pid].sum()), 'squared_error_sum': float((error[groups == pid] ** 2).sum()),
                'mae': float(error[groups == pid].mean())} for pid in role['evaluation']]
            if study=='v5':
                for row in evaluation['persistence']:
                    mask=groups==row['patient_id'];row['diagnostics']=sliced_errors(y[mask],X.cgm_current.to_numpy()[mask])
            rows.append({'fold': fold + 1, 'selected': chosen, 'tuning_patient_mae': {k: float(np.mean([r['mae'] for r in v])) for k, v in tuning.items()}, 'evaluation': evaluation})
            if study=='v5':rows[-1]['tuning_guardrails']=guardrails
            print(horizon, 'fold', fold + 1, 'selected', chosen, flush=True)
        aggregate = {}
        for name in list(models) + ['persistence', 'selected']:
            values = [r for f in rows for r in f['evaluation'][f['selected'] if name == 'selected' else name]]
            n = sum(r['n'] for r in values)
            aggregate[name] = {'rows': n, 'mae': sum(r['absolute_error_sum'] for r in values) / n,
                'rmse': float(np.sqrt(sum(r['squared_error_sum'] for r in values) / n)),
                'mean_patient_mae': float(np.mean([r['mae'] for r in values]))}
            if study=='v5':
                aggregate[name]['patient_macro_slices']={s:patient_macro(values,s) for s in ['all','high','low']}
                aggregate[name]['tail_interpretation']='mean of patient quantiles, not a pooled row quantile'
        output['horizons'][str(horizon)] = {'aggregate': aggregate, 'folds': rows}
        print(horizon, json.dumps(aggregate), flush=True)
    output['runtime_seconds'] = time.perf_counter() - start
    (ROOT / f'data/processed/regression_methods_{study}_private.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    for horizon in output['horizons'].values():
        for fold in horizon['folds']:
            del fold['evaluation']
    (ROOT / f'reports/regression_methods_{study}.json').write_text(json.dumps(output, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--study', choices=['v3', 'v4','v5'], default='v3')
    run(parser.parse_args().study)
