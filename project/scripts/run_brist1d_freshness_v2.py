"""Matched-row feature repair; never opens sensor data or alters v1 outputs."""
from pathlib import Path
import json
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
from run_brist1d_study import (ROOT, CACHE as V1_CACHE, ROLES, PROTOCOL, digest,
    load_cache, matrix, patient_rows, summarize, paired_comparison, write_json)
from glucotwin.brist1d import feature_arms
from glucotwin.brist1d_freshness import repair_freshness

CONFIG = ROOT/'configs/brist1d_freshness_v2.json'
CACHE = ROOT/'data/processed/brist1d_v2'
REPORT = ROOT/'reports/brist1d_study_v2.json'
ARTIFACTS = ROOT/'artifacts/brist1d_v2'


def reference_paths():
    return [PROTOCOL, ROLES, V1_CACHE/'manifest.json', ROOT/'reports/brist1d_study_v1.json',
            ROOT/'reports/brist1d_study_v1_checks.json']


def prepare(config, manifest, stamp, records):
    if set(records) != set(manifest['development']) or set(records) & set(manifest['reserved']):
        raise ValueError('Only frozen development records may be repaired')
    repaired = {}; columns = None
    for pid, record in records.items():
        original = pd.DataFrame(record['X'], columns=stamp['features'])
        fixed = repair_freshness(original, config['freshness_caps_minutes'])
        columns = fixed.columns.tolist()
        repaired[pid] = dict(record, X=fixed.to_numpy(dtype=np.float32))
        CACHE.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(CACHE/(pid+'.npz'), **repaired[pid])
        for key in record:
            if key != 'X': np.testing.assert_array_equal(record[key], repaired[pid][key])
        for arm in config['unchanged_arms']:
            before = stamp['arms'][arm]; after = feature_arms(columns)[arm]
            assert [stamp['features'][i] for i in before] == [columns[i] for i in after]
            np.testing.assert_array_equal(record['X'][:,before], repaired[pid]['X'][:,after])
    new_stamp = {'version': config['version'], 'config_sha256': digest(CONFIG),
                 'v1_protocol_sha256': digest(PROTOCOL), 'v1_manifest_sha256': digest(ROLES),
                 'features': columns, 'arms': feature_arms(columns),
                 'prepared_participants': manifest['development'],
                 'cache_sha256': {pid: digest(CACHE/(pid+'.npz')) for pid in repaired}}
    write_json(CACHE/'manifest.json', new_stamp)
    return new_stamp, repaired


def run():
    from xgboost import XGBRegressor
    if REPORT.exists() or (CACHE/'manifest.json').exists():
        raise ValueError('V2 outputs already exist; refusing silent experiment overwrite')
    config = json.loads(CONFIG.read_text()); protocol = json.loads(PROTOCOL.read_text())
    manifest = json.loads(ROLES.read_text())
    snapshots = {str(p.relative_to(ROOT)): digest(p) for p in reference_paths()}
    stamp, records = load_cache(manifest)
    started = time.perf_counter(); stop = threading.Event()
    peak = [psutil.Process().memory_info().rss]
    def sample():
        while not stop.wait(.25): peak[0] = max(peak[0], psutil.Process().memory_info().rss)
    sampler = threading.Thread(target=sample, daemon=True); sampler.start()
    try:
        new_stamp, repaired = prepare(config, manifest, stamp, records)
        print('Prepared identical v1 rows/targets with bounded freshness features', flush=True)
        public = {'version': config['version'], 'units': 'mg/dL',
                  'config_sha256': digest(CONFIG), 'v1_reference_hashes': snapshots,
                  'development_patients': 16, 'reserved_patients_prepared': 0,
                  'reserved_patients_scored': 0, 'features': len(new_stamp['features']),
                  'caps_minutes': config['freshness_caps_minutes'],
                  'status': 'fixed feature-only repair; no row admission changes; no deployment',
                  'reuse': 'CGM-only/profile model predictions copied exactly from v1; other three arms refitted',
                  'horizons': {}}
        private = {'horizons': {}}; model_count = 0
        for horizon in protocol['horizons_minutes']:
            totals = {}; old_totals = {}; folds = []
            for role in manifest['folds']:
                fold = role['fold']
                Xfit,yfit,gfit = matrix(repaired, role['fit'], horizon, protocol['fit_row_cap_per_patient'], protocol['seed'])
                X,y,groups = matrix(repaired, role['evaluation'], horizon, None, protocol['seed'])
                _, old_y, old_groups = matrix(records, role['evaluation'], horizon, None, protocol['seed'])
                np.testing.assert_array_equal(y,old_y); np.testing.assert_array_equal(groups,old_groups)
                times = np.concatenate([records[p]['times'][np.isfinite(records[p]['y'+str(horizon)])] for p in role['evaluation']])
                old_path = V1_CACHE/'outer_predictions'/str(horizon)/f'fold{fold}.npz'
                with np.load(old_path, allow_pickle=False) as archive:
                    old = {name: archive[name] for name in archive.files}
                np.testing.assert_array_equal(old['actual'],y); np.testing.assert_array_equal(old['groups'],groups)
                np.testing.assert_array_equal(old['issued_at'],times)
                predictions = {'actual': y, 'groups': groups, 'issued_at': times, 'persistence': old['persistence']}
                for name in old:
                    if name not in ('actual','groups','issued_at'):
                        old_totals.setdefault(name,[]).extend(patient_rows(y,old[name],groups))
                totals.setdefault('persistence',[]).extend(patient_rows(y,old['persistence'],groups))
                counts = {p: int((gfit==p).sum()) for p in role['fit']}
                weights = np.array([1/counts[p] for p in gfit]); weights *= len(weights)/weights.sum()
                current = new_stamp['features'].index('cgm_current')
                for kind in protocol['models']:
                    for arm, indices in new_stamp['arms'].items():
                        name = kind+'_'+arm
                        if arm in config['unchanged_arms']:
                            predicted = old[name].copy()
                        else:
                            imputer = SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)
                            if kind == 'ridge':
                                model = make_pipeline(imputer, StandardScaler(), Ridge(**protocol['models'][kind]))
                                target = yfit
                            else:
                                model = make_pipeline(imputer, XGBRegressor(**protocol['models'][kind],
                                    n_jobs=protocol['threads'], random_state=protocol['seed']))
                                target = yfit-Xfit[:,current]
                            final = list(model.named_steps)[-1]
                            with threadpool_limits(limits=protocol['threads']):
                                model.fit(Xfit[:,indices],target,**{final+'__sample_weight':weights})
                                predicted = model.predict(X[:,indices]).astype(float)
                            if kind == 'xgb_delta': predicted += X[:,current]
                            path = ARTIFACTS/str(horizon)/f'fold{fold}'/(name+'.joblib')
                            path.parent.mkdir(parents=True,exist_ok=True)
                            joblib.dump({'model':model,'feature_names':[new_stamp['features'][i] for i in indices],
                                         'predicts_delta':kind=='xgb_delta','config_sha256':digest(CONFIG)},path)
                            model_count += 1
                            print(f'{horizon}min fold {fold}/4 {name}: done',flush=True)
                        predictions[name] = predicted
                        totals.setdefault(name,[]).extend(patient_rows(y,predicted,groups))
                folder = CACHE/'outer_predictions'/str(horizon); folder.mkdir(parents=True,exist_ok=True)
                np.savez_compressed(folder/f'fold{fold}.npz',**predictions)
                folds.append({'fold':fold,'fit_patients':12,'evaluation_patients':4,
                              'sampled_fit_rows':len(yfit),'evaluation_rows':len(y)})
            public['horizons'][str(horizon)] = {
                'scores': {name:summarize(rows) for name,rows in totals.items()}, 'folds':folds,
                'paired_v2_minus_v1': {name:paired_comparison(rows,old_totals[name],
                    protocol['bootstrap_repetitions'],protocol['seed']) for name,rows in totals.items()},
                'paired_fused_minus_profile': {kind:paired_comparison(totals[kind+'_fused'],
                    totals[kind+'_cgm_profile'],protocol['bootstrap_repetitions'],protocol['seed']) for kind in protocol['models']}}
            private['horizons'][str(horizon)] = totals
            print(f'{horizon}min MAE: '+json.dumps({n:round(summarize(r)['mae'],3) for n,r in totals.items()}),flush=True)
        for path in reference_paths():
            if digest(path) != snapshots[str(path.relative_to(ROOT))]: raise ValueError('V1 reference changed')
        public['runtime'] = {'seconds':round(time.perf_counter()-started,2),
                             'sampled_peak_rss_mib':round(peak[0]/1048576,2),'threads':protocol['threads'],
                             'new_fixed_fits':model_count}
        write_json(CACHE/'study_private.json',private); write_json(REPORT,public)
        print(json.dumps(public['runtime']),flush=True)
        return public
    finally:
        stop.set(); sampler.join(timeout=2)


if __name__ == '__main__': run()
