"""Check feature-only repair, exact pairings and every newly saved model."""
import json
import re
import subprocess
import sys
import joblib
import numpy as np
import pandas as pd
from run_brist1d_study import (ROOT, CACHE as V1_CACHE, PROTOCOL, ROLES, load_cache,
    matrix, digest, patient_rows, summarize, write_json)
from run_brist1d_freshness_v2 import CONFIG, CACHE, REPORT, ARTIFACTS
from glucotwin.brist1d_freshness import repair_freshness


def run():
    tests = subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_brist1d*'],
                           cwd=ROOT,capture_output=True,text=True,check=True)
    count = int(re.search(r'Ran (\d+) tests',tests.stdout+tests.stderr)[1])
    protocol = json.loads(PROTOCOL.read_text()); config = json.loads(CONFIG.read_text())
    manifest = json.loads(ROLES.read_text()); report = json.loads(REPORT.read_text())
    if set(report['horizons']) != {'30','60'} or 'runtime' not in report: raise ValueError('Incomplete study')
    for name,value in report['v1_reference_hashes'].items():
        assert digest(ROOT/name)==value, 'V1 evidence changed'
    assert report['config_sha256']==digest(CONFIG)
    stamp,records = load_cache(manifest)
    fresh_stamp = json.loads((CACHE/'manifest.json').read_text())
    assert fresh_stamp['config_sha256']==digest(CONFIG)
    assert fresh_stamp['v1_protocol_sha256']==digest(PROTOCOL)
    assert fresh_stamp['v1_manifest_sha256']==digest(ROLES)
    assert set(fresh_stamp['prepared_participants'])==set(manifest['development'])
    assert {p.stem for p in CACHE.glob('P*.npz')}==set(manifest['development'])
    repaired = {}
    for pid,record in records.items():
        path = CACHE/(pid+'.npz'); assert digest(path)==fresh_stamp['cache_sha256'][pid]
        with np.load(path,allow_pickle=False) as archive: repaired[pid]={k:archive[k] for k in archive.files}
        expected = repair_freshness(pd.DataFrame(record['X'],columns=stamp['features']),config['freshness_caps_minutes'])
        assert expected.columns.tolist()==fresh_stamp['features']
        np.testing.assert_array_equal(expected.to_numpy(dtype=np.float32),repaired[pid]['X'])
        for key in record:
            if key!='X': np.testing.assert_array_equal(record[key],repaired[pid][key])
    checked = 0; probes = 8
    for horizon in (30,60):
        totals = {}
        for role in manifest['folds']:
            X,y,groups = matrix(repaired,role['evaluation'],horizon,None,protocol['seed'])
            _,old_y,old_groups = matrix(records,role['evaluation'],horizon,None,protocol['seed'])
            np.testing.assert_array_equal(y,old_y); np.testing.assert_array_equal(groups,old_groups)
            new_fit = matrix(repaired,role['fit'],horizon,protocol['fit_row_cap_per_patient'],protocol['seed'])
            old_fit = matrix(records,role['fit'],horizon,protocol['fit_row_cap_per_patient'],protocol['seed'])
            for i in (1,2): np.testing.assert_array_equal(new_fit[i],old_fit[i])
            with np.load(V1_CACHE/'outer_predictions'/str(horizon)/f'fold{role["fold"]}.npz',allow_pickle=False) as old:
                with np.load(CACHE/'outer_predictions'/str(horizon)/f'fold{role["fold"]}.npz',allow_pickle=False) as saved:
                    for key in ('actual','groups','issued_at','persistence'):
                        np.testing.assert_array_equal(saved[key],old[key])
                    assert not set(groups)&set(manifest['reserved'])
                    for kind in protocol['models']:
                        for arm in fresh_stamp['arms']:
                            name = kind+'_'+arm
                            totals.setdefault(name,[]).extend(patient_rows(y,saved[name],groups))
                            if arm in config['unchanged_arms']:
                                np.testing.assert_array_equal(saved[name],old[name]); continue
                            artifact = joblib.load(ARTIFACTS/str(horizon)/f'fold{role["fold"]}'/(name+'.joblib'))
                            assert artifact['config_sha256']==digest(CONFIG)
                            indices = [fresh_stamp['features'].index(c) for c in artifact['feature_names']]
                            positions = np.linspace(0,len(X)-1,probes,dtype=int)
                            pred = artifact['model'].predict(X[positions][:,indices]).astype(float)
                            if artifact['predicts_delta']: pred += X[positions,fresh_stamp['features'].index('cgm_current')]
                            np.testing.assert_allclose(pred,saved[name][positions],atol=.002,rtol=1e-6)
                            checked += 1
                    totals.setdefault('persistence',[]).extend(patient_rows(y,saved['persistence'],groups))
        for name,rows in totals.items():
            calculated = summarize(rows); expected = report['horizons'][str(horizon)]['scores'][name]
            assert calculated['rows']==expected['rows']
            for metric in ('mae','rmse'): np.testing.assert_allclose(calculated[metric],expected[metric],atol=1e-10,rtol=0)
            assert calculated['patient_macro_slices']==expected['patient_macro_slices']
    assert checked==48
    diagnostic_path = ROOT/'reports/brist1d_freshness_diagnostics_v2.json'
    diagnostics = json.loads(diagnostic_path.read_text())
    assert diagnostics['v1_report_sha256']==digest(ROOT/'reports/brist1d_study_v1.json')
    assert diagnostics['v2_report_sha256']==digest(REPORT)
    v1_report = json.loads((ROOT/'reports/brist1d_study_v1.json').read_text())
    for horizon,methods in diagnostics['horizons'].items():
        for method,values in methods.items():
            version,name = method.split('_',1)
            source = v1_report if version=='v1' else report
            score = source['horizons'][horizon]['scores'][name]
            slices = values['slices']
            assert slices['all']['rows']==score['rows']
            assert slices['all']['patients_with_rows']==16
            np.testing.assert_allclose(slices['all']['row_mae'],score['mae'],atol=1e-10,rtol=0)
            np.testing.assert_allclose(slices['actual_low']['patient_macro_mae'],
                score['patient_macro_slices']['low']['mean_patient_mae'],atol=1e-10,rtol=0)
            assert sum(slices[n]['rows'] for n in ('cadence_5min','cadence_15min'))==score['rows']
            for prefix in ('current_','predicted_','slope_','insulin_age_','carbs_age_','hr_age_'):
                names = [n for n in slices if n.startswith(prefix)]
                if prefix.endswith('_age_'): names += [prefix.replace('_age_','_never_observed')]
                assert sum(slices[n]['rows'] for n in names)==score['rows']
    assert not any('"'+pid+'"' in diagnostic_path.read_text() for pid in manifest['participants'])
    checks = {'status':'passed','report_sha256':digest(REPORT),'config_sha256':digest(CONFIG),
              'v1_reference_hashes_unchanged':True,'all_16_repaired_matrices_recomputed':True,
              'all_fit_samples_and_evaluation_rows_targets_groups_times_matched':True,
              'unchanged_predictions_exactly_equal':True,'new_saved_models_checked':checked,
              'prediction_probe_rows_per_model':probes,'synthetic_tests_passed':count,
              'reserved_feature_matrices':0,'reserved_prediction_groups':0,
              'aggregate_methods_recomputed_per_horizon':11}
    checks['diagnostics_sha256'] = digest(diagnostic_path)
    checks['diagnostic_aggregate_error_support_partitions_verified'] = True
    write_json(ROOT/'reports/brist1d_study_v2_checks.json',checks)
    print(json.dumps(checks,indent=2))
    return checks


if __name__=='__main__': run()
