"""Descriptive matched-prediction diagnostics; no fitting or model selection."""
import json
import numpy as np
import pandas as pd
from run_brist1d_study import (ROOT, CACHE as V1_CACHE, ROLES, PROTOCOL, load_cache,
    matrix, write_json, digest)
from run_brist1d_freshness_v2 import CACHE as V2_CACHE, REPORT
from glucotwin.brist1d_freshness import diagnostic_masks
from glucotwin.regression_diagnostics import error_summary


def summarize_slices(rows):
    result = {}
    names = sorted({name for r in rows for name in r['slices']})
    for name in names:
        available = [r['slices'][name] for r in rows if r['slices'][name]['n']]
        n = sum(r['n'] for r in available)
        result[name] = {'patients_with_rows':len(available), 'rows':n,
                        'row_mae':sum(r['n']*r['mae'] for r in available)/n if n else None,
                        'row_bias':sum(r['n']*r['bias'] for r in available)/n if n else None,
                        'patient_macro_mae':float(np.mean([r['mae'] for r in available])) if n else None,
                        'patient_macro_bias':float(np.mean([r['bias'] for r in available])) if n else None,
                        'mean_patient_p95':float(np.mean([r['p95_absolute_error'] for r in available])) if n else None}
    low = [r['slices']['actual_low']['mae'] for r in rows if r['slices']['actual_low']['n']]
    ratios = [r['delta_variance_ratio'] for r in rows if r['delta_variance_ratio'] is not None]
    return {'slices':result,
            'patient_low_mae_distribution': {'patients':len(low), 'quantiles_min_p25_median_p75_max':
                np.quantile(low,[0,.25,.5,.75,1]).tolist() if low else None},
            'mean_patient_delta_variance_ratio':float(np.mean(ratios)) if ratios else None,
            'delta_ratio_patients':len(ratios)}


def run():
    protocol = json.loads(PROTOCOL.read_text()); manifest = json.loads(ROLES.read_text())
    stamp, records = load_cache(manifest)
    report = json.loads(REPORT.read_text())
    private = {}; public = {'version':'brist1d-freshness-diagnostics-v2',
        'v1_report_sha256':digest(ROOT/'reports/brist1d_study_v1.json'),
        'v2_report_sha256':digest(REPORT), 'independent_development_patients':16,
        'bias_definition':'predicted minus actual; positive means overprediction',
        'age_source':'original uncapped v1 input ages; diagnoses never change eligibility or model inputs',
        'slope_bins_mg_dl_per_minute':{'falling':'< -0.5','stable':'-0.5 through +0.5','rising':'> +0.5'},
        'interpretation':'descriptive bins are not model gates; target-conditioned errors and variance ratios cannot identify a causal mechanism by themselves',
        'selection':'no thresholds, caps, model configurations or prediction changes selected from these diagnostics',
        'horizons':{}}
    for horizon in (30,60):
        totals = {}
        for role in manifest['folds']:
            X,y,groups = matrix(records,role['evaluation'],horizon,None,protocol['seed'])
            features = pd.DataFrame(X,columns=stamp['features'])
            paths = [(V1_CACHE,'v1'),(V2_CACHE,'v2')]
            for cache,version in paths:
                with np.load(cache/'outer_predictions'/str(horizon)/f'fold{role["fold"]}.npz',allow_pickle=False) as archive:
                    np.testing.assert_array_equal(archive['actual'],y)
                    np.testing.assert_array_equal(archive['groups'],groups)
                    names = ['persistence','ridge_fused','xgb_delta_cgm_profile','xgb_delta_fused'] if version=='v1' else ['ridge_fused','xgb_delta_fused']
                    for name in names:
                        predicted = archive[name]
                        masks = diagnostic_masks(features,y,predicted)
                        for pid in role['evaluation']:
                            patient = groups==pid
                            slices = {key:error_summary(y[mask & patient],predicted[mask & patient]) for key,mask in masks.items()}
                            current = features.cgm_current.to_numpy()[patient]
                            true_delta = y[patient]-current
                            predicted_delta = predicted[patient]-current
                            denominator = float(np.var(true_delta))
                            ratio = float(np.var(predicted_delta)/denominator) if denominator>0 else None
                            totals.setdefault(version+'_'+name,[]).append({'patient_id':pid,'slices':slices,
                                                                         'delta_variance_ratio':ratio})
        private[str(horizon)] = totals
        public['horizons'][str(horizon)] = {name:summarize_slices(rows) for name,rows in totals.items()}
        for values in public['horizons'][str(horizon)].values():
            assert values['slices']['all']['rows']==report['horizons'][str(horizon)]['scores']['persistence']['rows']
    write_json(V2_CACHE/'diagnostics_private.json',private)
    write_json(ROOT/'reports/brist1d_freshness_diagnostics_v2.json',public)
    print('Wrote descriptive diagnostics for six version/method pairs at both horizons')
    return public


if __name__ == '__main__': run()
