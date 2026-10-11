"""Bind reproducible synthetic and real-artifact checks to a completed study."""
from pathlib import Path
import json
import re
import subprocess
import sys

import joblib
import numpy as np
import pandas as pd

from run_brist1d_study import (ROOT, CACHE, ROLES, PROTOCOL, digest, load_cache,
                               load_development_frame, matrix, patient_rows, summarize, write_json)
from audit_brist1d_cohort import canonical_stream, CHANNELS
from glucotwin.brist1d import make_brist_features, measured_targets


def verify():
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_brist1d*'],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    match = re.search(r'Ran (\d+) tests', result.stdout+result.stderr)
    if match is None:
        raise ValueError('Test count not recorded')
    protocol = json.loads(PROTOCOL.read_text()); manifest = json.loads(ROLES.read_text())
    stamp, records = load_cache(manifest)
    report_path = ROOT/'reports/brist1d_study_v1.json'
    report = json.loads(report_path.read_text())
    if set(report['horizons']) != {'30', '60'} or 'runtime' not in report:
        raise ValueError('Both horizons must finish before verification')
    prepared = {p.stem for p in CACHE.glob('P*.npz')}
    if prepared != set(manifest['development']) or prepared.intersection(manifest['reserved']):
        raise ValueError('Unexpected reserved/unknown feature matrices')
    for cadence in (5, 15):
        pid = next(p for p in manifest['development'] if manifest['participants'][p]['native_minutes'] == cadence)
        frame = load_development_frame(pid, manifest)
        frame = frame.loc[frame.device.fillna('').str.strip().ne('')].copy()
        frame['timestamp'] = pd.to_datetime(frame.timestamp)
        streams = {c: canonical_stream(frame, c)[0] for c in CHANNELS}
        record = records[pid]
        valid = np.flatnonzero(np.isfinite(record['y30']) & np.isfinite(record['y60']))
        position = valid[len(valid)//2]
        issue = pd.Timestamp(record['times'][position])
        prefix = {c: s.loc[s.index <= issue-pd.Timedelta(minutes=protocol['availability_delay_minutes'][c])]
                  for c, s in streams.items()}
        rebuilt = make_brist_features(prefix, manifest['participants'][pid]['profile'], cadence,
                                      pd.DatetimeIndex([issue]), protocol)
        np.testing.assert_allclose(rebuilt[stamp['features']].iloc[0].to_numpy(dtype=float),
                                   record['X'][position].astype(float), rtol=2e-6, atol=2e-5, equal_nan=True)
        for horizon in (30, 60):
            np.testing.assert_allclose(measured_targets(streams['bg'], pd.DatetimeIndex([issue]), horizon)[0],
                                       record['y'+str(horizon)][position], rtol=0, atol=0)
    checked = 0
    worst = None
    for horizon in (30, 60):
        pooled = {}
        for role in manifest['folds']:
            X, y, groups = matrix(records, role['evaluation'], horizon, None, protocol['seed'])
            path = CACHE/'outer_predictions'/str(horizon)/f'fold{role["fold"]}.npz'
            with np.load(path, allow_pickle=False) as saved:
                np.testing.assert_array_equal(saved['actual'], y)
                np.testing.assert_array_equal(saved['groups'], groups)
                if set(groups).intersection(manifest['reserved']):
                    raise ValueError('Reserved predictions found')
                expected_times = np.concatenate([records[p]['times'][np.isfinite(records[p]['y'+str(horizon)])]
                                                 for p in role['evaluation']])
                np.testing.assert_array_equal(saved['issued_at'], expected_times)
                if horizon == 60:
                    error = np.abs(saved['ridge_fused']-saved['actual'])
                    pos = int(np.argmax(error))
                    if worst is None or float(error[pos]) > worst[0]:
                        worst = (float(error[pos]), role, pos)
                for name in saved.files:
                    if name in ('actual', 'groups', 'issued_at'):
                        continue
                    pooled.setdefault(name, []).extend(patient_rows(y, saved[name], groups))
                    if name == 'persistence':
                        continue
                    artifact = joblib.load(ROOT/'artifacts/brist1d_v1'/str(horizon)/f'fold{role["fold"]}'/(name+'.joblib'))
                    indices = [stamp['features'].index(c) for c in artifact['feature_names']]
                    predicted = artifact['model'].predict(X[:8, indices]).astype(float)
                    if artifact['predicts_delta']:
                        predicted += X[:8, stamp['features'].index('cgm_current')]
                    np.testing.assert_allclose(predicted, saved[name][:8], rtol=1e-6, atol=.002)
                    checked += 1
        for name, rows in pooled.items():
            actual = summarize(rows); expected = report['horizons'][str(horizon)]['scores'][name]
            for key in ('mae', 'rmse'):
                np.testing.assert_allclose(actual[key], expected[key], rtol=0, atol=1e-10)
            assert actual['rows'] == expected['rows']
            assert actual['patient_macro_slices'] == expected['patient_macro_slices']
    error, role, position = worst
    X, _, _ = matrix(records, role['evaluation'], 60, None, protocol['seed'])
    artifact = joblib.load(ROOT/'artifacts/brist1d_v1/60'/f'fold{role["fold"]}'/'ridge_fused.joblib')
    indices = [stamp['features'].index(c) for c in artifact['feature_names']]
    model = artifact['model']
    encoded = model[0].transform(X[position:position+1, indices])
    contributions = model[1].transform(encoded)[0]*model[-1].coef_
    names = model[0].get_feature_names_out(artifact['feature_names'])
    strongest = np.argsort(np.abs(contributions))[-5:][::-1]
    checks = {'status': 'passed', 'report_sha256': digest(report_path), 'protocol_sha256': digest(PROTOCOL),
              'cache_manifest_sha256': digest(CACHE/'manifest.json'), 'synthetic_tests_passed': int(match[1]),
              'native_prefix_cadences_checked_minutes': [5, 15], 'exact_target_probe_checks': 4,
              'saved_models_checked': checked, 'prediction_probe_rows_per_model': 8,
              'model_prediction_tolerance': {'relative': 1e-6, 'absolute_mg_dl': .002},
              'aggregate_models_recomputed_per_horizon': 11, 'reserved_feature_matrices': 0,
              'reserved_prediction_groups': 0, 'worst_ridge_60_abs_error_mg_dl': error,
              'worst_ridge_60_largest_linear_terms_mg_dl': {str(names[i]): float(contributions[i]) for i in strongest}}
    write_json(ROOT/'reports/brist1d_study_v1_checks.json', checks)
    print(json.dumps(checks, indent=2))
    return checks


if __name__ == '__main__':
    verify()
