"""Check training-only preprocessing, saved inference and every reported score."""
from collections import defaultdict
import json
import warnings

import joblib
import numpy as np
from threadpoolctl import threadpool_limits

from run_dclp3_study import ROOT, CACHE, PROTOCOL, ROLES, REPORT, ARTIFACTS, digest, load_cache
from glucotwin.dclp3_study import matrix, row_digest, patient_rows, summarize, paired_comparison
from prepare_dclp3 import write


def close_tree(left, right):
    if isinstance(left, dict):
        assert set(left) == set(right)
        for key in left:
            close_tree(left[key], right[key])
    elif isinstance(left, list):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            close_tree(a, b)
    elif isinstance(left, (int, float)) and not isinstance(left, bool):
        np.testing.assert_allclose(left, right, rtol=1e-9, atol=1e-8)
    else:
        assert left == right


def verify():
    protocol, roles = json.loads(PROTOCOL.read_text()), json.loads(ROLES.read_text())
    report = json.loads(REPORT.read_text())
    execution_path = CACHE/'study_execution.json'
    execution = json.loads(execution_path.read_text())
    assert report['status'] == 'complete'
    assert report['reserved_patients_scored'] == 0
    assert report['execution_sha256'] == digest(execution_path)
    assert report['protocol_sha256'] == execution['protocol_sha256'] == digest(PROTOCOL)
    assert report['roles_sha256'] == execution['roles_sha256'] == digest(ROLES)
    assert execution['cache_manifest_sha256'] == digest(CACHE/'manifest.json')
    assert execution['runner_sha256'] == digest(ROOT/'scripts/run_dclp3_study.py')
    assert execution['metrics_sha256'] == digest(ROOT/'src/glucotwin/dclp3_study.py')
    stamp, records = load_cache(protocol, roles)
    columns, arms = stamp['features'], stamp['arms']
    pump_ids = set(roles['pump_participants']) & set(roles['development'])
    artifact_checks = prediction_probes = preprocessing_checks = 0
    scoring_rows, cohorts_verified = {}, []
    for h in protocol['horizons_minutes']:
        for cohort, arm_names in execution['cohorts'].items():
            accumulated = defaultdict(list)
            scored_ids = []
            expected_model_names = [kind+'_'+arm for kind in ('ridge', 'xgb_delta') for arm in arm_names]
            for fold in roles['folds']:
                fit_ids, eval_ids = fold['fit'], fold['evaluation']
                if cohort == 'pump_linked':
                    fit_ids = [p for p in fit_ids if p in pump_ids]
                    eval_ids = [p for p in eval_ids if p in pump_ids]
                fit = matrix(records, fit_ids, h, protocol['fit_row_cap_per_patient'], protocol['seed'], roles['development'])
                evaluation = matrix(records, eval_ids, h, None, protocol['seed'], roles['development'])
                fit_sha, eval_sha = row_digest(fit), row_digest(evaluation)
                predictions_path = CACHE/'outer_predictions'/cohort/str(h)/f'fold{fold["fold"]}.npz'
                with np.load(predictions_path, allow_pickle=False) as pred:
                    assert set(pred.files) == {'actual', 'groups', 'issued_at', 'strict', 'persistence', *expected_model_names}
                    np.testing.assert_array_equal(pred['groups'], evaluation['groups'])
                    np.testing.assert_array_equal(pred['issued_at'], evaluation['times'])
                    np.testing.assert_array_equal(pred['actual'], evaluation['y'])
                    np.testing.assert_array_equal(pred['strict'], evaluation['strict'])
                    assert not set(pred['groups']) & set(roles['reserved'])
                    current = evaluation['X'][:, columns.index('cgm_current')].astype(float)
                    np.testing.assert_array_equal(pred['persistence'], current)
                    expected_preprocessing = {}
                    for arm in arm_names:
                        x = fit['X'][:, arms[arm]]
                        with warnings.catch_warnings():
                            warnings.simplefilter('ignore', RuntimeWarning)
                            median = np.nanmedian(x, axis=0)
                        median[np.isnan(median)] = 0
                        missing_columns = np.flatnonzero(np.isnan(x).any(axis=0))
                        expected_preprocessing[arm] = (median, missing_columns)
                    for name in ['persistence', *expected_model_names]:
                        p = pred[name]
                        assert p.shape == pred['actual'].shape and np.isfinite(p).all()
                        accumulated[name].extend(patient_rows(pred['actual'], p, current, pred['groups'], pred['strict']))
                        if name == 'persistence':
                            continue
                        kind, arm = next((k, a) for k in ('ridge', 'xgb_delta') for a in arm_names if name == k+'_'+a)
                        path = ARTIFACTS/cohort/str(h)/f'fold{fold["fold"]}'/(name+'.joblib')
                        artifact = joblib.load(path)
                        assert artifact['execution_sha256'] == report['execution_sha256']
                        assert artifact['fit_row_sha256'] == fit_sha and artifact['evaluation_row_sha256'] == eval_sha
                        assert artifact['feature_names'] == [columns[i] for i in arms[arm]]
                        assert artifact['predicts_delta'] == (kind == 'xgb_delta')
                        model = artifact['model']
                        expected_params = protocol['models'][kind]
                        final_params = model[-1].get_params()
                        for key, value in expected_params.items():
                            assert final_params[key] == value, 'Fitted model parameters differ from contract'
                        median, missing_columns = expected_preprocessing[arm]
                        np.testing.assert_allclose(model[0].statistics_, median, rtol=1e-6, atol=1e-5)
                        np.testing.assert_array_equal(model[0].indicator_.features_, missing_columns)
                        if kind == 'ridge':
                            imputed = model[0].transform(fit['X'][:, arms[arm]])
                            np.testing.assert_allclose(model[1].mean_, imputed.mean(axis=0, dtype=float), rtol=1e-6, atol=1e-6)
                            np.testing.assert_allclose(model[1].var_, imputed.var(axis=0, dtype=float), rtol=1e-6, atol=1e-6)
                            del imputed
                        positions = np.linspace(0, len(p)-1, 16, dtype=int)
                        with threadpool_limits(limits=protocol['threads']):
                            actual_pred = model.predict(evaluation['X'][positions][:, arms[arm]]).astype(float)
                        if artifact['predicts_delta']:
                            actual_pred += current[positions]
                        np.testing.assert_allclose(actual_pred, p[positions], rtol=1e-6, atol=1e-4)
                        artifact_checks += 1
                        prediction_probes += len(positions)
                        preprocessing_checks += 1
                    scored_ids.extend(eval_ids)
                del fit, evaluation
            expected_ids = sorted(pump_ids) if cohort == 'pump_linked' else roles['development']
            assert sorted(scored_ids) == expected_ids
            published = report['horizons'][str(h)][cohort]
            assert published['completed_folds'] == 4
            assert set(published['scores']) == set(accumulated)
            for name, rows in accumulated.items():
                close_tree(summarize(rows), published['scores'][name])
                # Separately recompute pooled errors from per-patient sufficient
                # sums, without relying on the pooled-slice implementation.
                n = sum(r['n'] for r in rows)
                np.testing.assert_allclose(sum(r['absolute_error_sum'] for r in rows)/n, published['scores'][name]['mae'])
                np.testing.assert_allclose(np.sqrt(sum(r['squared_error_sum'] for r in rows)/n), published['scores'][name]['rmse'])
                for treatment in ('CLC', 'SAP'):
                    treatment_rows = [r for r in rows if roles['strata'][r['patient_id']].startswith(treatment+'_')]
                    close_tree(summarize(treatment_rows), published['by_treatment_group'][treatment][name])
            for comparison, expected in published['paired_comparisons'].items():
                candidate, reference = comparison.split('_versus_')
                close_tree(paired_comparison(accumulated[candidate], accumulated[reference]), expected)
            scoring_rows[f'{cohort}_{h}'] = published['scores']['persistence']['rows']
            cohorts_verified.append({'cohort': cohort, 'horizon': h, 'patients': len(scored_ids)})
            print(f'Verified {h}m {cohort}: matched scores, preprocessing and inference', flush=True)
    result = {'status': 'passed', 'execution_sha256': report['execution_sha256'],
        'model_artifacts_verified': artifact_checks, 'saved_prediction_probes': prediction_probes,
        'training_only_preprocessors_verified': preprocessing_checks,
        'cohorts_verified': cohorts_verified, 'scoring_rows': scoring_rows,
        'reserved_participants_scored': 0,
        'scope': 'matched caches, sampled fit rows, trained preprocessing, inference parity, all overall/slice/treatment scores and paired intervals recomputed'}
    write(ROOT/'reports/dclp3_study_v2_checks.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    verify()
