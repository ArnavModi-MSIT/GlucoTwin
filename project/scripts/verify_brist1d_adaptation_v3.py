"""Independent maturity/count checks and direct weighted-sum prediction probes."""
import json
import re
import subprocess
import sys
import numpy as np
from run_brist1d_study import ROOT,digest,write_json,patient_rows,summarize
from run_brist1d_freshness_v2 import CACHE as V2_CACHE
from run_brist1d_adaptation_v3 import CONFIG,CACHE,REPORT,load_reference,reference_hashes
from glucotwin.brist1d_adaptation import MINUTE_NS


def independent_schedule(times,interval):
    chosen = []; threshold = None
    for value in times:
        if threshold is None or value>=threshold:
            chosen.append(value); threshold=value+interval*MINUTE_NS
    return np.asarray(chosen,dtype=np.int64)


def verify():
    tests = subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_brist1d*'],
        cwd=ROOT,capture_output=True,text=True,check=True)
    count = int(re.search(r'Ran (\d+) tests',tests.stdout+tests.stderr)[1])
    config = json.loads(CONFIG.read_text()); report = json.loads(REPORT.read_text())
    protocol,manifest,records = load_reference()
    assert report['config_sha256']==digest(CONFIG)
    assert report['reference_hashes']==reference_hashes()
    assert set(report['horizons'])=={'30','60'} and 'runtime' in report
    probes = 0; row_checks = 0; snapshots = {}
    for horizon in (30,60):
        totals = {}; active_totals = {}; inactive_totals = {}; coverage = {n:[] for n in config['methods']}
        for role in manifest['folds']:
            path = CACHE/'outer_predictions'/str(horizon)/f'fold{role["fold"]}.npz'
            snapshots[str(path.relative_to(ROOT))] = digest(path)
            with np.load(path,allow_pickle=False) as archive: saved={k:archive[k] for k in archive.files}
            with np.load(V2_CACHE/'outer_predictions'/str(horizon)/f'fold{role["fold"]}.npz',allow_pickle=False) as reference:
                for key in ('actual','groups','issued_at'): np.testing.assert_array_equal(saved[key],reference[key])
                for name in config['methods']: np.testing.assert_array_equal(saved['unadapted_'+name],reference[name])
            y,groups,times = saved['actual'],saved['groups'],saved['issued_at']
            assert set(groups)==set(role['evaluation']) and not set(groups)&set(manifest['reserved'])
            for name in config['methods']:
                base = saved['unadapted_'+name]; adapted = saved['adapted_'+name]
                correction = saved['correction_'+name]; active = saved['active_'+name]
                np.testing.assert_allclose(adapted,base+correction,rtol=0,atol=1e-10)
                np.testing.assert_array_equal(adapted[~active],base[~active])
                assert np.abs(correction).max()<=config['correction_clip_mg_dl']
                for pid in role['evaluation']:
                    mask = groups==pid; t=times[mask]; actual=y[mask]; b=base[mask]
                    selected = independent_schedule(records[pid]['times'],config['update_interval_minutes'])
                    positions = np.flatnonzero(np.isin(t,selected))
                    arrivals = t[positions]+(horizon+config['target_availability_delay_minutes'])*MINUTE_NS
                    right=np.searchsorted(arrivals,t,side='right')
                    left=np.searchsorted(arrivals,t-config['history_minutes']*MINUTE_NS,side='left')
                    counts=right-left
                    np.testing.assert_array_equal(counts,saved['matured_count_'+name][mask])
                    latest = arrivals[np.maximum(right-1,0)] if len(arrivals) else np.zeros(len(t),dtype=np.int64)
                    expected_active=(counts>=config['minimum_matured_updates']) & (right>0) & (
                        t-latest<=config['maximum_latest_update_age_minutes']*MINUTE_NS)
                    np.testing.assert_array_equal(expected_active,active[mask])
                    row_checks += len(t)
                    for i in np.linspace(0,len(t)-1,32,dtype=int):
                        usable=positions[left[i]:right[i]]
                        expected=0.
                        if expected_active[i]:
                            ages=(t[i]-arrivals[left[i]:right[i]])/MINUTE_NS
                            weights=np.exp2(-ages/config['half_life_minutes'])
                            residuals=np.clip(actual[usable]-b[usable],-config['residual_clip_mg_dl'],config['residual_clip_mg_dl'])
                            expected=np.clip(np.sum(weights*residuals)/(weights.sum()+config['prior_weight_zero_residual']),
                                -config['correction_clip_mg_dl'],config['correction_clip_mg_dl'])
                        np.testing.assert_allclose(correction[mask][i],expected,rtol=0,atol=1e-8)
                        probes += 1
                    coverage[name].append({'rows':len(t),'active_rows':int(expected_active.sum()),
                        'scheduled_updates':len(selected),'scheduled_updates_with_exact_targets':len(positions),
                        'matured_updates_by_last_issue':int(right[-1])})
                for label,predicted in [('unadapted_'+name,base),('adapted_'+name,adapted)]:
                    totals.setdefault(label,[]).extend(patient_rows(y,predicted,groups))
                    if active.any(): active_totals.setdefault(label,[]).extend(patient_rows(y[active],predicted[active],groups[active]))
                    if (~active).any(): inactive_totals.setdefault(label,[]).extend(patient_rows(y[~active],predicted[~active],groups[~active]))
        h = report['horizons'][str(horizon)]
        for field,source in [('scores',totals),('active_subset_scores',active_totals),('inactive_subset_scores',inactive_totals)]:
            for name,rows in source.items(): assert summarize(rows)==h[field][name]
        for name,rows in coverage.items():
            public=h['coverage'][name]
            for key in ('rows','active_rows','scheduled_updates','scheduled_updates_with_exact_targets','matured_updates_by_last_issue'):
                assert sum(r[key] for r in rows)==public[key]
            assert public['patients_with_active_rows']==sum(r['active_rows']>0 for r in rows)
            assert public['active_fraction']==public['active_rows']/public['rows']
    assert not list(CACHE.glob('P*.npz')), 'Adaptation should not create patient feature matrices'
    assert not any('"'+pid+'"' in REPORT.read_text() for pid in manifest['participants'])
    checks={'status':'passed','report_sha256':digest(REPORT),'config_sha256':digest(CONFIG),
        'reference_hashes_unchanged':True,'synthetic_tests_passed':count,
        'independent_maturity_count_and_activation_rows_checked':row_checks,
        'independent_direct_weighted_sum_probes':probes,'weighted_sum_probe_absolute_tolerance':1e-8,
        'all_row_active_inactive_aggregate_scores_and_coverage_recomputed':True,
        'prediction_hashes':snapshots,'reserved_feature_matrices':0,'reserved_prediction_groups':0}
    write_json(ROOT/'reports/brist1d_adaptation_v3_checks.json',checks)
    print(json.dumps({k:v for k,v in checks.items() if k!='prediction_hashes'},indent=2))
    return checks


if __name__=='__main__': verify()
