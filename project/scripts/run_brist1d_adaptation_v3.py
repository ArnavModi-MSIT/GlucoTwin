"""Fixed causal residual adaptation of saved v2 forecasts; no refitting."""
import json
import time
import numpy as np
import psutil
from run_brist1d_study import (ROOT,CACHE as V1_CACHE,ROLES,PROTOCOL,load_cache,digest,
    patient_rows,summarize,paired_comparison,write_json)
from run_brist1d_freshness_v2 import CACHE as V2_CACHE,REPORT as V2_REPORT
from glucotwin.brist1d_adaptation import adapt_forecasts

CONFIG = ROOT/'configs/brist1d_adaptation_v3.json'
CACHE = ROOT/'data/processed/brist1d_v3'
REPORT = ROOT/'reports/brist1d_adaptation_v3.json'


def reference_hashes():
    paths = [PROTOCOL,ROLES,V1_CACHE/'manifest.json',V2_REPORT,
             ROOT/'reports/brist1d_study_v2_checks.json']
    paths += sorted((V2_CACHE/'outer_predictions').glob('*/*.npz'))
    return {str(p.relative_to(ROOT)):digest(p) for p in paths}


def load_reference():
    manifest = json.loads(ROLES.read_text()); protocol = json.loads(PROTOCOL.read_text())
    checks = json.loads((ROOT/'reports/brist1d_study_v2_checks.json').read_text())
    if checks['status']!='passed' or checks['report_sha256']!=digest(V2_REPORT):
        raise ValueError('Matching passed v2 verification required')
    _,records = load_cache(manifest)
    if set(records)&set(manifest['reserved']) or set(records)!=set(manifest['development']):
        raise ValueError('Unexpected reference patient roles')
    return protocol,manifest,records


def run():
    if REPORT.exists() or (CACHE/'study_private.json').exists():
        raise ValueError('Adaptation outputs exist; refusing silent overwrite')
    config = json.loads(CONFIG.read_text()); snapshots = reference_hashes()
    protocol,manifest,records = load_reference()
    if config['target_availability_delay_minutes']!=protocol['availability_delay_minutes']['bg']:
        raise ValueError('Target delay differs from v1/v2 availability contract')
    v2 = json.loads(V2_REPORT.read_text())
    started = time.perf_counter(); peak = psutil.Process().memory_info().rss
    public = {'version':config['version'],'units':'mg/dL','config_sha256':digest(CONFIG),
        'reference_hashes':snapshots,'development_patients':16,'reserved_patients_scored':0,
        'models_refitted':0,'status':'fixed online adaptation research track; no deployment',
        'estimand':'new-patient forecasts with matured personal outcome history, distinct from unadapted population forecasting',
        'limitation':'overlapping residuals remain correlated; hourly scheduling does not establish independent updates; source delays are assumptions',
        'horizons':{}}
    private = {'horizons':{}}
    for horizon in (30,60):
        totals = {}; active_totals = {}; inactive_totals = {}; coverage = {name:[] for name in config['methods']}
        for role in manifest['folds']:
            path = V2_CACHE/'outer_predictions'/str(horizon)/f'fold{role["fold"]}.npz'
            with np.load(path,allow_pickle=False) as archive:
                saved = {name:archive[name] for name in archive.files}
            y,groups,times = saved['actual'],saved['groups'],saved['issued_at']
            expected_y = np.concatenate([records[p]['y'+str(horizon)][np.isfinite(records[p]['y'+str(horizon)])] for p in role['evaluation']])
            expected_times = np.concatenate([records[p]['times'][np.isfinite(records[p]['y'+str(horizon)])] for p in role['evaluation']])
            expected_groups = np.concatenate([np.repeat(p,np.isfinite(records[p]['y'+str(horizon)]).sum()) for p in role['evaluation']])
            for a,b in [(y,expected_y),(times,expected_times),(groups,expected_groups)]: np.testing.assert_array_equal(a,b)
            if set(groups)&set(manifest['reserved']): raise ValueError('Reserved forecast access')
            output = {'actual':y,'groups':groups,'issued_at':times}
            for name in config['methods']:
                baseline = saved[name]; adapted = baseline.astype(float).copy()
                active = np.zeros(len(y),dtype=bool); corrections = np.zeros(len(y)); counts = np.zeros(len(y),dtype=np.int32)
                for pid in role['evaluation']:
                    mask = groups==pid
                    result = adapt_forecasts(times[mask],y[mask],baseline[mask],records[pid]['times'],horizon,config)
                    adapted[mask] = result['predicted']; active[mask] = result['active']
                    corrections[mask] = result['correction']; counts[mask] = result['matured_count']
                    coverage[name].append({'patient_id':pid,'rows':int(mask.sum()),'active_rows':int(result['active'].sum()),
                        'all_scheduled_updates':result['all_scheduled_updates'],
                        'scheduled_updates_with_exact_targets':result['scheduled_updates_with_exact_targets'],
                        'matured_updates_by_last_issue':result['matured_updates_by_last_issue']})
                for label,predicted in [('unadapted_'+name,baseline),('adapted_'+name,adapted)]:
                    totals.setdefault(label,[]).extend(patient_rows(y,predicted,groups))
                    if active.any(): active_totals.setdefault(label,[]).extend(patient_rows(y[active],predicted[active],groups[active]))
                    if (~active).any(): inactive_totals.setdefault(label,[]).extend(patient_rows(y[~active],predicted[~active],groups[~active]))
                    output[label] = predicted
                output['active_'+name] = active; output['correction_'+name] = corrections; output['matured_count_'+name] = counts
                np.testing.assert_array_equal(adapted[~active],baseline[~active])
            folder = CACHE/'outer_predictions'/str(horizon); folder.mkdir(parents=True,exist_ok=True)
            np.savez_compressed(folder/f'fold{role["fold"]}.npz',**output)
            peak = max(peak,psutil.Process().memory_info().rss)
            print(f'{horizon}min fold {role["fold"]}/4 adapted three fixed methods',flush=True)
        public['horizons'][str(horizon)] = {
            'scores':{name:summarize(rows) for name,rows in totals.items()},
            'active_subset_scores':{name:summarize(rows) for name,rows in active_totals.items()},
            'inactive_subset_scores':{name:summarize(rows) for name,rows in inactive_totals.items()},
            'paired_adapted_minus_unadapted':{name:paired_comparison(totals['adapted_'+name],totals['unadapted_'+name],
                protocol['bootstrap_repetitions'],protocol['seed']) for name in config['methods']},
            'coverage':{name:{'patients':len(rows),'patients_with_active_rows':sum(r['active_rows']>0 for r in rows),
                'rows':sum(r['rows'] for r in rows),'active_rows':sum(r['active_rows'] for r in rows),
                'active_fraction':sum(r['active_rows'] for r in rows)/sum(r['rows'] for r in rows),
                'scheduled_updates':sum(r['all_scheduled_updates'] for r in rows),
                'scheduled_updates_with_exact_targets':sum(r['scheduled_updates_with_exact_targets'] for r in rows),
                'matured_updates_by_last_issue':sum(r['matured_updates_by_last_issue'] for r in rows)} for name,rows in coverage.items()}}
        for name in config['methods']:
            result = public['horizons'][str(horizon)]['scores']['unadapted_'+name]
            assert result==v2['horizons'][str(horizon)]['scores'][name], 'Reference scores differ'
        private['horizons'][str(horizon)] = {'scores':totals,'active_scores':active_totals,'inactive_scores':inactive_totals,'coverage':coverage}
        print(f'{horizon}min MAE '+json.dumps({name:round(summarize(rows)['mae'],3) for name,rows in totals.items()}),flush=True)
    if reference_hashes()!=snapshots: raise ValueError('Reference evidence changed during adaptation')
    public['runtime'] = {'seconds':round(time.perf_counter()-started,2),
        'sampled_peak_rss_mib':round(peak/1048576,2),'memory_sampling':'after load and each fold; not continuous peak tracking'}
    write_json(CACHE/'study_private.json',private); write_json(REPORT,public)
    print(json.dumps(public['runtime']),flush=True)
    return public


if __name__=='__main__': run()
