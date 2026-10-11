"""Render the completed fixed BrisT1D study without fitting or changing scores."""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'data/processed/mpl_cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def summarize():
    report = json.loads((ROOT/'reports/brist1d_study_v1.json').read_text())
    if set(report['horizons']) != {'30', '60'} or 'runtime' not in report:
        raise ValueError('Study has not completed both horizons')
    checks = None
    checks_path = ROOT/'reports/brist1d_study_v1_checks.json'
    if checks_path.exists():
        candidate = json.loads(checks_path.read_text())
        report_hash = hashlib.sha256((ROOT/'reports/brist1d_study_v1.json').read_bytes()).hexdigest()
        if candidate.get('status') == 'passed' and candidate.get('report_sha256') == report_hash:
            checks = candidate
    diagnostic_lines = ['Detailed saved-model diagnostics have not been verified against this report.']
    verification_lines = ['There is no matching verification artifact for this report. Run',
                          '`python scripts/verify_brist1d_study.py` before making verification claims.']
    if checks is not None:
        terms = checks['worst_ridge_60_largest_linear_terms_mg_dl']
        strongest = max(terms, key=lambda name: abs(terms[name]))
        diagnostic_lines = [
            f'A saved-model diagnostic traced the worst 60-minute Ridge case '
            f'({checks["worst_ridge_60_abs_error_mg_dl"]:.1f} mg/dL absolute error) to large linear',
            f'extrapolation: `{strongest}` alone contributed {terms[strongest]:.1f} mg/dL.',
            'A single such case does not explain every error.']
        verification_lines = [
            f'{checks["synthetic_tests_passed"]} BrisT1D synthetic tests passed. Real-source checks verified prefix',
            'parity and exact issue+horizon labels for both native cadences.',
            f'All {checks["saved_models_checked"]} saved fold models reproduced '
            f'{checks["prediction_probe_rows_per_model"]} checked held-out prediction probes each.',
            'Held-out arrays, aggregate error arithmetic and exclusion of reserved',
            'participants were verified for both horizons. Existing dashboard models',
            'were unchanged. These are correctness checks, not clinical validation.',
            '[Report-bound verification artifact](../reports/brist1d_study_v1_checks.json).']
    lines = [
        '# BrisT1D fixed CPU input study v1', '',
        'The full-input XGBoost method gives a small average improvement over its',
        'CGM/profile counterpart. It still has substantial errors and worse low-target',
        'MAE than persistence. This dataset/method round did not resolve the project\'s',
        'adverse-event prediction problem. No dashboard model was replaced.', '',
        'Sixteen development patients were evaluated once each in four patient-disjoint',
        'folds. Four patients remain reserved. Availability assumptions, native cadence,',
        'feature admission and targets were frozen before fitting in the',
        '[data contract](BRIST1D_DATA_CONTRACT.md). All methods share evaluation rows.', '',
        '## Overall measured errors', '',
        '| Fixed method / inputs | MAE30 | MAE60 | RMSE30 | RMSE60 |',
        '|---|---:|---:|---:|---:|',
    ]
    for name in report['horizons']['30']['scores']:
        first = report['horizons']['30']['scores'][name]
        second = report['horizons']['60']['scores'][name]
        label = name.replace('xgb_delta_', 'Delta XGBoost / ').replace('ridge_', 'Ridge / ').replace('_', ' ')
        lines.append(f'| {label} | {first["mae"]:.2f} | {second["mae"]:.2f} | {first["rmse"]:.2f} | {second["rmse"]:.2f} |')
    lines += ['', 'Units: mg/dL. These are row-pooled errors over 625,755 exact 30-minute',
              'and 612,635 exact 60-minute targets. Each person contributes overlapping',
              'windows; the number of independent patients is sixteen.', '',
              '## Important error slices', '',
              '| Method | Patient-macro low MAE30 / MAE60 | Patient-macro high MAE30 / MAE60 | Patient-macro P95 error30 / error60 |',
              '|---|---:|---:|---:|']
    keys = ['persistence', 'ridge_cgm_profile', 'xgb_delta_cgm_profile', 'xgb_delta_fused']
    for name in keys:
        slices = [report['horizons'][h]['scores'][name]['patient_macro_slices'] for h in ('30', '60')]
        low = ' / '.join(f'{s["low"]["mean_patient_mae"]:.2f}' for s in slices)
        high = ' / '.join(f'{s["high"]["mean_patient_mae"]:.2f}' for s in slices)
        p95 = ' / '.join(f'{s["all"]["mean_patient_p95_absolute_error"]:.2f}' for s in slices)
        lines.append(f'| {name} | {low} | {high} | {p95} |')
    lines += ['', 'Low and high slices use exact targets below 70 and above 180 mg/dL.',
              'Each slice has observations from all sixteen development patients.',
              'These are averages of patient metrics; P95 is the mean of sixteen',
              'patient quantiles, not the pooled-row quantile.', '',
              '## Does adding inputs help?', '']
    for horizon in ('30', '60'):
        item = report['horizons'][horizon]['paired_input_comparisons']['xgb_delta_fused_versus_xgb_delta_cgm_profile']
        delta = item['all_mae']; interval = delta['patient_bootstrap95']
        lines.append(f'- {horizon} minutes: full inputs minus CGM/profile mean patient MAE '
                     f'{delta["mean_difference"]:.3f} mg/dL; exploratory paired patient-bootstrap '
                     f'95% interval [{interval[0]:.3f}, {interval[1]:.3f}].')
    lines += ['', 'Negative favors full inputs. The typical-error gain is small. High/low-target',
              'MAE difference intervals include zero at both horizons; severe-error gains',
              'remain weak. The 60-minute P95 difference interval also includes zero.',
              'There is no selection-adjusted final-test or clinical-validation claim.', '',
              'Ridge plus all inputs is rejected as a useful replacement in this study:',
              'its errors deteriorated sharply.', *diagnostic_lines, 'Source streams',
              'have long outages; v1 includes unbounded recency features, and its failed',
              'results are retained. A separately versioned experiment should bound recency',
              'and mask stale measurements, rather than silently rewrite these scores.', '',
              '## Interpretation and next work', '',
              'This is a young Type 1 cohort with mixed five-/15-minute CGM cadence and',
              'explicit input delays. Its absolute scores are not a controlled comparison',
              'with the existing RBG or reconstructed CGMacros dashboard results.',
              'Recorded meals/doses do not prove prospective entry/upload availability.',
              'No false-alarm, event recall, treatment or probability claim is made.', '',
              'Next test bounded/freshness-aware action features in a named new version',
              'and causal patient adaptation using only already matured outcomes. Preserve',
              'these results and the four reserved patients; do not run another broad sweep.', '',
              '## Runtime and verification', '',
              f'CPU training/evaluation: {report["runtime"]["seconds"]:.2f} seconds, '
              f'{report["runtime"]["sampled_peak_rss_mib"]:.2f} MiB sampled peak RSS, '
              f'{report["runtime"]["threads"]} threads. There were 80 fixed fits '
              '(two models, five arms, four folds, two horizons), not 80 tuned configurations.', '',
              *verification_lines, '',
              '[Full aggregate JSON](../reports/brist1d_study_v1.json),',
              '[preparation counts](../reports/brist1d_preparation.json), and',
              '[CPU study runner](../scripts/run_brist1d_study.py).', '',
              'Selected methods are shown below; the failed full-input Ridge results',
              'remain in the complete table above.', '',
              '![Development error comparison](../reports/brist1d_study_v1.png)', '']
    (ROOT/'docs/BRIST1D_STUDY_V1.md').write_text('\n'.join(lines), encoding='utf-8')
    colors = ['#8797a4', '#397ca3', '#12877d', '#e48743']
    labels = ['Persistence', 'Ridge\nCGM + profile', 'XGBoost\nCGM + profile', 'XGBoost\nAll inputs']
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    positions = np.arange(len(keys)); width = .36
    for column, ax in enumerate(axes):
        for j, horizon in enumerate(('30', '60')):
            values = []
            for name in keys:
                score = report['horizons'][horizon]['scores'][name]
                values.append(score['mae'] if column == 0 else score['patient_macro_slices']['low']['mean_patient_mae'])
            bars = ax.bar(positions+(j-.5)*width, values, width, color=colors,
                          alpha=.55 if j == 0 else 1., hatch='//' if j == 0 else None,
                          edgecolor='white', label=horizon+' min')
            ax.bar_label(bars, fmt='%.1f', fontsize=8, padding=3)
        ax.set_xticks(positions, labels, fontsize=9)
        ax.set_ylabel('Absolute error (mg/dL)')
        ax.set_title('Overall row-weighted MAE' if column == 0 else 'Low-target patient-macro MAE')
        ax.set_ylim(0, 80 if column == 1 else 42)
        ax.grid(axis='y', alpha=.2); ax.set_axisbelow(True)
        ax.spines[['top', 'right']].set_visible(False)
        ax.legend(title='Horizon', fontsize=8, frameon=False)
    fig.suptitle('BrisT1D fixed development study · 16 patients · lower error is better\n'
                 'Four reserved patients were not scored; availability delays are assumptions.', fontsize=12)
    fig.savefig(ROOT/'reports/brist1d_study_v1.png', dpi=160)
    plt.close(fig)
    print('Wrote docs/BRIST1D_STUDY_V1.md and reports/brist1d_study_v1.png')


if __name__ == '__main__':
    summarize()
