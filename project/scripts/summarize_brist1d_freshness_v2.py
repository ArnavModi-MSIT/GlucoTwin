"""Write a reviewable summary from aggregate v1/v2 evidence, not guessed scores."""
import json
from run_brist1d_study import ROOT, digest


def run():
    p1 = ROOT/'reports/brist1d_study_v1.json'; p2 = ROOT/'reports/brist1d_study_v2.json'
    pd = ROOT/'reports/brist1d_freshness_diagnostics_v2.json'
    v1 = json.loads(p1.read_text()); v2 = json.loads(p2.read_text()); diag = json.loads(pd.read_text())
    checks = json.loads((ROOT/'reports/brist1d_study_v2_checks.json').read_text())
    if checks['status']!='passed' or checks['report_sha256']!=digest(p2) or checks['diagnostics_sha256']!=digest(pd):
        raise ValueError('Matching verification of this report and diagnostics is required')
    lines = ['# BrisT1D freshness repair study v2', '',
        'Freshness repair recovered the failed full-input Ridge model. XGBoost',
        'changed very little and its low-target errors remain worse than persistence.',
        'This is a successful failure-mechanism repair, not a convincing new accuracy',
        'or adverse-event warning result. Dashboard models and warnings are unchanged.', '',
        'Sixteen development patients, four fixed folds and four reserved patients',
        'were retained from v1. Targets, issue times, admission, training samples and',
        'evaluation rows are identical. No raw sensor files were opened in this study.',
        'The reserved sources were previously quality-audited before role freezing;',
        'they were not prepared or scored in v2.', '',
        '## Fixed feature-only repair', '',
        'Caps: thirty minutes for insulin/HR/steps/distance/calories observations,',
        '480 minutes for recorded carbohydrate events. These are engineering freshness',
        'assumptions written before fitting, not physiological action durations.',
        'Age is measured from issue time to the latest available source timestamp.',
        'Cap numeric age, mask stale latest values, add stale/unobserved flags, retain',
        'all past-window amounts/counts/fractions and actual logged zeros. Unknown',
        'meal logs remain unknown. The boundary age equal to a cap is fresh.', '',
        'CGM/profile arms and their predictions are unchanged. The other three arms',
        'were refitted with the same fixed Ridge/XGBoost configurations. The twelve',
        'new flags give 152 full-input features. The comparison changes multiple',
        'feature details together; it does not isolate the effect of clipping alone.', '',
        '## Matched row-pooled errors', '',
        '| Method | v1 MAE30 / MAE60 | v2 MAE30 / MAE60 | v2 RMSE30 / RMSE60 |',
        '|---|---:|---:|---:|']
    for name in v2['horizons']['30']['scores']:
        a = [v1['horizons'][h]['scores'][name] for h in ('30','60')]
        b = [v2['horizons'][h]['scores'][name] for h in ('30','60')]
        lines.append(f"| {name} | {a[0]['mae']:.2f} / {a[1]['mae']:.2f} | {b[0]['mae']:.2f} / {b[1]['mae']:.2f} | {b[0]['rmse']:.2f} / {b[1]['rmse']:.2f} |")
    lines += ['', 'All units mg/dL. The same 625,755 / 612,635 endpoint rows cover',
        '30 / 60 minutes. Overlapping rows are not independent patients.', '',
        '## Patient-macro slices', '',
        '| v2 method | Low MAE30 / MAE60 | High MAE30 / MAE60 | P95 error30 / error60 |',
        '|---|---:|---:|---:|']
    for name in ('persistence','ridge_fused','xgb_delta_cgm_profile','xgb_delta_fused'):
        a,b = [v2['horizons'][h]['scores'][name]['patient_macro_slices'] for h in ('30','60')]
        lines.append(f"| {name} | {a['low']['mean_patient_mae']:.2f} / {b['low']['mean_patient_mae']:.2f} | {a['high']['mean_patient_mae']:.2f} / {b['high']['mean_patient_mae']:.2f} | {a['all']['mean_patient_p95_absolute_error']:.2f} / {b['all']['mean_patient_p95_absolute_error']:.2f} |")
    lines += ['', 'Each high/low slice contains sixteen patients. P95 is the mean of',
        'patient quantiles. Low/high means use exact targets below 70 / above 180.', '',
        'Full-input XGBoost v2-minus-v1 paired mean-patient MAE differences:', '']
    for h in ('30','60'):
        value = v2['horizons'][h]['paired_v2_minus_v1']['xgb_delta_fused']['all_mae']
        lo,hi = value['patient_bootstrap95']
        lines.append(f"- {h} minutes: {value['mean_difference']:.4f} mg/dL; exploratory patient bootstrap 95% [{lo:.4f}, {hi:.4f}].")
    lines += ['', 'Both intervals include zero. Development patients have been inspected',
        'repeatedly; these intervals are not selection-adjusted final-test evidence.', '',
        '## What the diagnostics show', '',
        '| Diagnostic | 30 min | 60 min |', '|---|---:|---:|']
    for label,method,slice_name,metric in [
        ('v1 Ridge: row MAE with insulin observation age >360 min','v1_ridge_fused','insulin_age_360_to_inf','row_mae'),
        ('v2 Ridge: same original-age rows','v2_ridge_fused','insulin_age_360_to_inf','row_mae'),
        ('v2 XGBoost: five-minute cadence row MAE','v2_xgb_delta_fused','cadence_5min','row_mae'),
        ('v2 XGBoost: fifteen-minute cadence row MAE','v2_xgb_delta_fused','cadence_15min','row_mae'),
        ('v2 XGBoost: bias when current glucose <70','v2_xgb_delta_fused','current_-inf_to_70','patient_macro_bias'),
        ('v2 XGBoost: bias when actual target <70','v2_xgb_delta_fused','actual_low','patient_macro_bias')]:
        a,b = [diag['horizons'][h][method]['slices'][slice_name][metric] for h in ('30','60')]
        lines.append(f'| {label} | {a:.2f} | {b:.2f} |')
    lines += ['', 'Bias is predicted minus actual. Insulin age >360 minutes has six',
        'patients and 70,713 / 70,267 rows; this supports the outage-extrapolation',
        'diagnosis. Five-/fifteen-minute strata contain twelve/four different patients;',
        'cadence differences do not establish a causal cadence effect.', '',
        'Current-low and future-low rows have opposite bias signs. This shows why',
        'target-conditioned error and issue-time calibration must be distinguished.',
        'It does not by itself prove regression to the mean or identify the missing',
        'predictive signal. Current-low XGBoost bias is still nonzero.', '',
        'Mean patient predicted-delta / realized-delta variance ratios for v2',
        'full-input XGBoost are '+ ' / '.join(f"{diag['horizons'][h]['v2_xgb_delta_fused']['mean_patient_delta_variance_ratio']:.3f}" for h in ('30','60')) +
        '. Lower dispersion is descriptive; unpredictable outcomes also contribute',
        'to realized variance, so the ratio does not prove an estimator defect.', '',
        'The full diagnostic report includes current/predicted bins, past-slope',
        'strata, uncapped insulin/carbs/HR age groups, low-slice support and',
        'per-patient low-MAE distribution summaries. Sparse bins are descriptive.', '',
        '## Runtime and verification', '',
        f"{v2['runtime']['new_fixed_fits']} new fixed fits, {v2['runtime']['seconds']:.2f} seconds including cache repair,",
        f"{v2['runtime']['sampled_peak_rss_mib']:.2f} MiB sampled peak process RSS, eight CPU threads.", '',
        f"{checks['synthetic_tests_passed']} BrisT1D tests passed. All sixteen repaired matrices were recomputed;",
        'fit samples and evaluation arrays matched v1. Forty-eight saved models',
        'reproduced eight prediction probes each. Eleven aggregate methods per',
        'horizon were recomputed. Diagnostic counts/error aggregates were checked.',
        'V1 reference hashes and all unchanged-arm predictions were unchanged.',
        'Reserved feature matrices and prediction groups: zero.', '',
        '## Next decision', '',
        'Retain v2 as the repaired experimental baseline. Do not replace the',
        'dashboard or claim low-event reliability from this round. Next predeclare',
        'a small matured-outcome residual adaptation comparator, reporting its',
        'warm-up and activation coverage separately. A compact neural experiment',
        'and a frozen event-onset contract remain later hypotheses, not completed',
        'work. No additional dataset claims were verified in this round.', '',
        '[Review adjudication](MAE_REVIEW_ACTIONS_V2.md),',
        '[v1 reference](BRIST1D_STUDY_V1.md),',
        '[v2 aggregate JSON](../reports/brist1d_study_v2.json),',
        '[diagnostic JSON](../reports/brist1d_freshness_diagnostics_v2.json),',
        '[report-bound checks](../reports/brist1d_study_v2_checks.json),',
        '[configuration](../configs/brist1d_freshness_v2.json).', '',
        'Reproduce from `project` with local v1 caches and experiment dependencies:', '',
        '```powershell', 'python scripts/run_brist1d_freshness_v2.py',
        'python scripts/diagnose_brist1d_freshness.py', 'python scripts/verify_brist1d_freshness_v2.py',
        'python scripts/summarize_brist1d_freshness_v2.py', '```', '',
        'The v2 runner refuses silent overwrites of existing study outputs.',
        'No public push or reserved evaluation was performed.']
    target = ROOT/'docs/BRIST1D_STUDY_V2.md'
    target.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Wrote',target.name)


if __name__=='__main__': run()
