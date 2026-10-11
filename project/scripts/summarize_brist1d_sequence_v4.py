"""Write a verified sequence comparison with complete error-slice evidence."""
import json
from run_brist1d_study import ROOT,digest
from run_brist1d_sequence_v4 import REPORT,CONFIG


def run():
    report=json.loads(REPORT.read_text()); config=json.loads(CONFIG.read_text())
    checks=json.loads((ROOT/'reports/brist1d_sequence_v4_checks.json').read_text())
    if checks['status']!='passed' or checks['report_sha256']!=digest(REPORT) or checks['config_sha256']!=digest(CONFIG):
        raise ValueError('Matching verified report/config required')
    lines=['# BrisT1D matched neural sequence study v4','', 'Completed: 11 October 2026.', '',
        'One compact TCN and a matched-information delta XGBoost comparator were',
        'trained locally. Existing v2 forecasts are retained as a reference. This',
        'document reports every method and the important glucose slices; no',
        'dashboard or operational warning model was changed.', '',
        '## Frozen representation and model','',
        '- Two hours of history queried every five minutes: 25 points, seven',
        '  channels (CGM, insulin, logged carbs, HR, steps, distance, calories).',
        '- Each channel carries a freshest available value, fresh mask, new source',
        '  observation flag, bounded age fraction and never-observed flag. Channel',
        '  delays and freshness caps match v1/v2. A carried dose/meal value is',
        '  context, not a second administered dose or consumed meal.',
        '- The history grid is a set of past availability queries. No glucose',
        '  value or missing future endpoint is interpolated. Native fifteen-minute',
        '  streams have fewer new-observation flags; missing meals stay unknown.',
        '- A context branch receives all 152 v2 point features, including historical',
        '  patient fields and existing meal summaries extending to eight hours.',
        '  Both methods receive the same history/context information.',
        '- TCN: three residual blocks, sixteen hidden channels, two left-padded',
        '  convolutions per block, kernel three, dilations 1/2/4, dropout 0.15.',
        '  Its nominal receptive field is 29 samples, covering all 25 input points.',
        '  Context hidden width sixteen and head width thirty-two produce two',
        '  endpoint delta predictions. The output starts at persistence.',
        '- Matched XGBoost uses the flattened identical encoded history and context,',
        '  one fixed delta model per horizon with the prior v1 model parameters.', '',
        'Masks/age fractions are unchanged by preprocessing. Sequence-value means',
        'and standard deviations (fixed minimum standard deviation one source unit)',
        'and context imputation/scaling are fitted only on the relevant fitting',
        'patients. Missing/stale values are represented by normalized zero plus',
        'their masks; a logged zero has distinct observation/freshness flags.', '',
        '## Patient roles and training','',
        'Sixteen development patients retain the same four outer patient folds.',
        'Four reserved participants were neither opened for sequence preparation',
        'nor scored. The earlier whole-cohort quality audit had inspected all twenty.',
        'All original 625,755 / 612,635 exact 30 / 60-minute evaluation endpoints',
        'are retained, with their original issue times and availability assumptions.', '',
        'For each outer fold, three of its twelve fitting patients (two five-minute,',
        'one fifteen-minute) are selected by a fixed seed for inner stopping.',
        'Nine fit the inner model. The stopping score averages patient MAE over',
        'both horizons. Maximum fifteen epochs, patience three, minimum improvement',
        '0.01 mg/dL; outer patients never choose epochs. The network is then reset',
        'and refitted on all twelve fitting patients for the selected epoch count.', '',
        'The final fit uses up to 4,000 deterministic uniformly sampled issues per',
        'patient with at least one exact target. Both methods use these identical',
        'issue samples, masking missing heads. Loss/fit weights give equal total',
        'weight to each patient and head. No sample is chosen from glucose magnitude.',
        'The earlier v2 reference used different per-horizon sampling and fewer',
        'sequence inputs; only the new matched comparator controls those differences.', '',
        '| Fold | Selected epochs | Final parameters | Final labeled rows 30 / 60 |',
        '|---|---:|---:|---:|']
    for fold in report['folds']:
        rows=fold['sampled_final_fit_rows_by_horizon']
        lines.append(f"| {fold['fold']} | {fold['selected_epochs']} | {fold['parameter_count']:,} | {rows['30']:,} / {rows['60']:,} |")
    lines += ['', '## Measured errors','',
        '| Method | MAE30 / MAE60 | RMSE30 / RMSE60 | Patient-macro MAE30 / MAE60 |',
        '|---|---:|---:|---:|']
    for name in ('persistence','v2_xgb_fused','matched_xgb','tcn'):
        a,b=[report['horizons'][h]['scores'][name] for h in ('30','60')]
        lines.append(f"| {name} | {a['mae']:.2f} / {b['mae']:.2f} | {a['rmse']:.2f} / {b['rmse']:.2f} | {a['patient_macro_slices']['all']['mean_patient_mae']:.2f} / {b['patient_macro_slices']['all']['mean_patient_mae']:.2f} |")
    lines += ['', 'Units mg/dL. Hundreds of thousands of overlapping rows come from only',
        'sixteen independent development patients.', '',
        '| Method | Patient-macro low MAE30 / MAE60 | High MAE30 / MAE60 | P95 error30 / error60 |',
        '|---|---:|---:|---:|']
    for name in ('persistence','v2_xgb_fused','matched_xgb','tcn'):
        a,b=[report['horizons'][h]['scores'][name]['patient_macro_slices'] for h in ('30','60')]
        lines.append(f"| {name} | {a['low']['mean_patient_mae']:.2f} / {b['low']['mean_patient_mae']:.2f} | {a['high']['mean_patient_mae']:.2f} / {b['high']['mean_patient_mae']:.2f} | {a['all']['mean_patient_p95_absolute_error']:.2f} / {b['all']['mean_patient_p95_absolute_error']:.2f} |")
    lines += ['', 'Low/high slices use actual exact endpoints below 70 / above 180 mg/dL.',
        'All sixteen patients contribute to each slice. P95 is the mean of individual',
        'patient quantiles, not a pooled quantile. Full tail fractions and biases',
        'are retained in the aggregate JSON.', '',
        '## Paired TCN versus matched XGBoost evidence','',
        '| Metric: mean patient difference | 30 min [bootstrap 95%] | 60 min [bootstrap 95%] |',
        '|---|---:|---:|']
    for metric in ('all_mae','all_rmse','all_p95_absolute_error','high_mae','low_mae'):
        values=[report['horizons'][h]['paired_tcn_minus_matched_xgb'][metric] for h in ('30','60')]
        formatted=[]
        for v in values:
            lo,hi=v['patient_bootstrap95']
            formatted.append(f"{v['mean_difference']:+.3f} [{lo:+.3f}, {hi:+.3f}]")
        lines.append(f"| {metric} | {formatted[0]} | {formatted[1]} |")
    lines += ['', 'Negative favors TCN. These are exploratory intervals over repeatedly',
        'inspected development patients, not selection-adjusted final test evidence.',
        'Different outer folds share fitting patients. A small typical-error gain',
        'does not establish reliable event warnings or better severe-error behavior.', '',
        '## Interpretation','']
    comparisons=[report['horizons'][h]['paired_tcn_minus_matched_xgb'] for h in ('30','60')]
    if all(c['all_mae']['mean_difference']<0 for c in comparisons):
        lines += ['TCN improved mean-patient typical MAE against the matched comparator',
                  'at both horizons in this fixed study. Inspect the slice/tail results',
                  'and interval support above before interpreting that as an overall win.']
    else:
        lines += ['TCN did not improve mean-patient typical MAE against the matched',
                  'comparator at both horizons. This fixed architecture is not an',
                  'overall replacement on the evidence shown here.']
    persistence=[report['horizons'][h]['scores']['persistence']['patient_macro_slices']['low']['mean_patient_mae'] for h in ('30','60')]
    low=[report['horizons'][h]['scores']['tcn']['patient_macro_slices']['low']['mean_patient_mae'] for h in ('30','60')]
    if any(a>b for a,b in zip(low,persistence)):
        lines.append('TCN low-target errors still exceed persistence at one or both horizons.')
    lines += ['No final held-out test or event operating/calibration gate was evaluated.',
        'No architecture/loss/seed sweep was run, and the result does not establish',
        'that every possible neural model would behave similarly.', '',
        '## Verification and runtime','',
        f"{checks['synthetic_tests_passed']} BrisT1D tests executed, including neural causality and head masking.",
        f"{checks['real_native_prefix_sequence_probes']} real prefix probes at both native cadences matched cached histories.",
        'All four final-fit preprocessing objects were recomputed from fitting',
        'patients, and inner roles/epoch selection/final samples were verified.',
        f"Saved TCN and matched XGBoost reproduced {checks['neural_prediction_probe_rows']} / {checks['matched_xgb_prediction_probe_rows']}",
        'endpoint prediction probes. Original evaluation arrays and every aggregate',
        'method were recomputed. Reserved sequence matrices and prediction groups: zero.', '',
        f"CPU training and evaluation: {report['runtime']['seconds']:.2f} seconds,",
        f"{report['runtime']['sampled_peak_rss_mib']:.2f} MiB sampled peak RSS, eight threads.",
        'Sequence preparation is reported separately. CPU-only PyTorch was installed',
        'in an optional project-local environment using the',
        '[official previous-version installation source](https://pytorch.org/get-started/previous-versions/).', '',
        '[Frozen config](../configs/brist1d_sequence_v4.json),',
        '[sequence encoding](../src/glucotwin/brist1d_sequence.py),',
        '[TCN](../src/glucotwin/brist1d_tcn.py),',
        '[runner](../scripts/run_brist1d_sequence_v4.py),',
        '[aggregate results](../reports/brist1d_sequence_v4.json),',
        '[report-bound checks](../reports/brist1d_sequence_v4_checks.json),',
        '[preparation counts](../reports/brist1d_sequence_preparation_v4.json).', '',
        'Reproduce from `project` in the optional CPU torch environment:', '',
        '```powershell','python scripts/prepare_brist1d_sequence_v4.py',
        'python scripts/run_brist1d_sequence_v4.py','python scripts/verify_brist1d_sequence_v4.py',
        'python scripts/summarize_brist1d_sequence_v4.py','```','',
        'Completed cache/report preparation refuses silent overwrites. Source data,',
        'sequence arrays and neural/model artifacts remain private. No push was performed.']
    (ROOT/'docs/BRIST1D_SEQUENCE_V4.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Wrote BRIST1D_SEQUENCE_V4.md')


if __name__=='__main__': run()
