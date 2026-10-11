"""Summarize verified adaptation evidence without promoting a failed rule."""
import json
from run_brist1d_study import ROOT,digest
from run_brist1d_adaptation_v3 import REPORT,CONFIG


def run():
    report=json.loads(REPORT.read_text()); config=json.loads(CONFIG.read_text())
    checks=json.loads((ROOT/'reports/brist1d_adaptation_v3_checks.json').read_text())
    if checks['status']!='passed' or checks['report_sha256']!=digest(REPORT) or checks['config_sha256']!=digest(CONFIG):
        raise ValueError('Matching verified report/config required')
    lines=['# BrisT1D causal residual adaptation v3','', 'Completed: 11 October 2026.', '',
        'The fixed residual-adaptation rule did not improve the strongest full-input',
        'XGBoost baseline overall. It worsened overall errors while slightly reducing',
        'some high/low slice errors. Ridge gains were small, with unresolved tail',
        'and low-target errors. This rule is rejected as a general replacement.',
        'No model or warning change was deployed.', '',
        '## Frozen experiment','',
        'Sixteen held-out development patients retain their four original folds.',
        'Four reserved patients remain unscored. Saved v2 population forecasts and',
        'the same 625,755 / 612,635 exact endpoint rows are used at 30 / 60 minutes.',
        'No model was refitted and no sensor source was opened.', '',
        'Each patient, horizon and method starts with independent zero state:', '',
        '- Schedule the first history-eligible issue, then the first issue at least',
        '  sixty minutes after the preceding scheduled issue. The schedule includes',
        '  issues whose targets later turn out missing; no replacement update is',
        '  chosen after learning target availability.',
        '- A scheduled residual is actual minus the unadapted forecast. It becomes',
        '  usable only at issue + horizon + five-minute target delay. This delay is',
        '  the prior measurement-availability assumption, not the cadence-rounded',
        '  reading-triggered issuance offset.',
        '- Retain matured residuals from the preceding 24 hours, clip each at ±60',
        '  mg/dL and weight by a six-hour time half-life. Divide weighted residual',
        '  sum by weight sum plus four zero-residual prior units.',
        '- Require twelve retained matured updates, and a latest matured update',
        '  within three hours. Otherwise use the unadapted forecast. Clip the final',
        '  correction at ±10 mg/dL and add it to the population forecast.', '',
        'These are fixed research assumptions recorded before execution, not tuned',
        'physiology or optimized settings. Hourly updates remain correlated. Prior',
        'target values from a new patient are used, making this an online-adaptation',
        'estimand distinct from unadapted new-patient forecasting. Whole-record',
        'patient calibration and future target access are prohibited.', '',
        '## All-row measured errors','',
        '| Method | MAE30 / MAE60 | RMSE30 / RMSE60 | Patient-macro MAE30 / MAE60 |',
        '|---|---:|---:|---:|']
    for name in report['horizons']['30']['scores']:
        a,b=[report['horizons'][h]['scores'][name] for h in ('30','60')]
        lines.append(f"| {name} | {a['mae']:.2f} / {b['mae']:.2f} | {a['rmse']:.2f} / {b['rmse']:.2f} | {a['patient_macro_slices']['all']['mean_patient_mae']:.2f} / {b['patient_macro_slices']['all']['mean_patient_mae']:.2f} |")
    lines += ['', 'Units mg/dL. Every method is reported, including the worsening persistence',
        'control. Row-pooled and patient-macro metrics differ.', '',
        '## Error slices and tail performance','',
        '| Method | Low MAE30 / MAE60 | High MAE30 / MAE60 | P95 error30 / error60 |',
        '|---|---:|---:|---:|']
    for name in report['horizons']['30']['scores']:
        a,b=[report['horizons'][h]['scores'][name]['patient_macro_slices'] for h in ('30','60')]
        lines.append(f"| {name} | {a['low']['mean_patient_mae']:.2f} / {b['low']['mean_patient_mae']:.2f} | {a['high']['mean_patient_mae']:.2f} / {b['high']['mean_patient_mae']:.2f} | {a['all']['mean_patient_p95_absolute_error']:.2f} / {b['all']['mean_patient_p95_absolute_error']:.2f} |")
    lines += ['', 'These are patient-macro values. Low/high are exact future targets below',
        '70 / above 180 mg/dL; each slice contains sixteen patients. P95 means',
        'the average of patient quantiles. Adapted XGBoost still has worse low-target',
        'MAE than unadapted persistence, despite its small slice improvements.', '',
        '## Activation and paired evidence','']
    for h in ('30','60'):
        coverage=report['horizons'][h]['coverage']['xgb_delta_fused']
        pair=report['horizons'][h]['paired_adapted_minus_unadapted']['xgb_delta_fused']['all_mae']
        lo,hi=pair['patient_bootstrap95']
        lines.append(f"- {h} minutes: active on {coverage['active_rows']:,}/{coverage['rows']:,} rows ({coverage['active_fraction']*100:.2f}%), all sixteen patients; paired mean-patient MAE change {pair['mean_difference']:+.3f} mg/dL, exploratory bootstrap 95% [{lo:+.3f}, {hi:+.3f}].")
    lines += ['', 'Positive difference means worse. The 30-minute MAE interval excludes zero',
        'in the unfavorable direction; the 60-minute interval includes zero. Some',
        'slice improvements come with worse overall/tail errors. Development patients',
        'have been inspected repeatedly and these are not selection-adjusted final',
        'test intervals. No event recall or warning reliability claim follows.', '',
        'Active-only and inactive-only scores are also retained in the JSON; both',
        'adapted and unadapted predictions are scored on identical masks. Inactive',
        'predictions equal the baseline exactly. High activation coverage describes',
        'long retrospective replay sessions and does not remove initial warm-up',
        'requirements in a new short session.', '',
        '## Verification and runtime','',
        f"{checks['synthetic_tests_passed']} BrisT1D tests passed, including exact maturity boundaries, future-target",
        'perturbation, prefix parity, missing-target scheduling, independent patient',
        'state, clipping, warm-up and outage expiry.', '',
        f"Independent search-based counts and activation checks covered {checks['independent_maturity_count_and_activation_rows_checked']:,}",
        f"patient/method/horizon rows. {checks['independent_direct_weighted_sum_probes']:,} probes independently computed direct weighted sums,",
        'rather than repeating the incremental state implementation. All aggregate',
        'all/active/inactive scores and coverage were recomputed. V1/v2 reference',
        'hashes were unchanged. Reserved matrices and prediction groups: zero.', '',
        f"Adaptation and scoring took {report['runtime']['seconds']:.2f} seconds locally. Sampled RSS was",
        f"{report['runtime']['sampled_peak_rss_mib']:.2f} MiB after loading and at fold boundaries; this is not continuous",
        'peak tracking. No GPU or new model fitting was required.', '',
        '## Decision and next work','',
        'Keep the unadapted repaired v2 XGBoost as the stronger existing benchmark.',
        'Retain v3 as a failed fixed adaptation experiment; do not silently tune its',
        'parameters after seeing held-out results. This outcome does not disprove all',
        'personalization methods. It shows that this simple recent residual rule',
        'does not solve the present accuracy/safety-slice tradeoff.', '',
        'The next planned comparison is one compact neural sequence model against',
        'a tabular comparator with matched information, patient-disjoint inner stopping,',
        'unchanged targets and reserved-patient exclusion. Its representation and',
        'architecture must be frozen first. Neural training has not started.', '',
        '[Fixed adaptation configuration](../configs/brist1d_adaptation_v3.json),',
        '[causal implementation](../src/glucotwin/brist1d_adaptation.py),',
        '[runner](../scripts/run_brist1d_adaptation_v3.py),',
        '[aggregate results](../reports/brist1d_adaptation_v3.json),',
        '[report-bound checks](../reports/brist1d_adaptation_v3_checks.json),',
        '[v2 reference](BRIST1D_STUDY_V2.md).', '',
        'Reproduce from `project` with the existing local v1/v2 caches:', '',
        '```powershell','python scripts/run_brist1d_adaptation_v3.py',
        'python scripts/verify_brist1d_adaptation_v3.py',
        'python scripts/summarize_brist1d_adaptation_v3.py','```','',
        'The runner refuses silent overwrites. Raw data, patient-level prediction',
        'arrays and fitted artifacts remain private. No public push was performed.']
    (ROOT/'docs/BRIST1D_ADAPTATION_V3.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Wrote BRIST1D_ADAPTATION_V3.md')


if __name__=='__main__': run()
