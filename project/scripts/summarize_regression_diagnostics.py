"""Paired patient bootstrap of v5 diagnostics; no refitting or selection."""
from pathlib import Path
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]


def run():
    private=json.loads((ROOT/'data/processed/regression_methods_v5_private.json').read_text());rng=np.random.default_rng(2026)
    result={'scope':'exploratory paired patient-macro differences versus Ridge; overlapping rows are not bootstrap units', 'horizons':{}}
    for horizon,data in private['horizons'].items():
        comparisons={}
        for name in ['xgb_delta_extended','xgb_delta_squared','xgb_delta_huber']:
            comparisons[name]={}
            for slice_name in ['all','high','low']:
                pairs=[]
                for fold in data['folds']:
                    baseline={r['patient_id']:r for r in fold['evaluation']['ridge_original']}
                    for row in fold['evaluation'][name]:
                        ref=baseline[row['patient_id']]['diagnostics'][slice_name];candidate=row['diagnostics'][slice_name]
                        if ref['n'] and candidate['n']:pairs.append((candidate,ref))
                metrics={}
                for key in ['mae','rmse','p90_absolute_error','fraction_error_gt40','fraction_error_gt60','bias']:
                    differences=np.array([a[key]-b[key] for a,b in pairs])
                    if not len(differences):continue
                    samples=rng.choice(differences,size=(2000,len(differences)),replace=True).mean(axis=1)
                    metrics[key]={'mean_difference':float(differences.mean()),'patient_bootstrap95':np.quantile(samples,[.025,.975]).tolist()}
                comparisons[name][slice_name]={'paired_patients':len(pairs),'metrics':metrics}
        result['horizons'][horizon]=comparisons
    (ROOT/'reports/regression_methods_v5_paired.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Saved paired MAE/RMSE/tail/slice diagnostics for both horizons')


if __name__=='__main__':run()
