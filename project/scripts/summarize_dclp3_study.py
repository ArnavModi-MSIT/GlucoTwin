"""Publish all fixed DCLP3 methods, matched input comparisons and limitations."""
import json

from prepare_dclp3 import ROOT


def main():
    report = json.loads((ROOT/'reports/dclp3_study_v2.json').read_text())
    checks = json.loads((ROOT/'reports/dclp3_study_v2_checks.json').read_text())
    if report['status'] != 'complete' or checks['status'] != 'passed' or checks['execution_sha256'] != report['execution_sha256']:
        raise ValueError('A complete, verified study is required')
    lines = ['# DCLP3 fixed CPU comparison', '',
        'Completed 11 October 2026. Four patient-disjoint development folds; '
        '134 participants for clinical fusion and a matched 100-person pump subset. '
        'The 34 reserved participants were not scored. Units mg/dL.', '',
        'Every model uses the same evaluation rows within its cohort/horizon. '
        'Training uses at most 4,000 uniformly sampled rows per patient with equal '
        'patient total weight. Ridge predicts the endpoint directly; XGBoost '
        'predicts the change from the latest available glucose. Model settings '
        'were fixed before fitting; no parameter sweep or model promotion occurred.', '',
        'Nominal +30/+60-minute targets are observed readings within ±30 seconds. '
        'There is no label interpolation. Five-minute input delay means approximately '
        '35/65-minute lookahead from the latest measurement. Boundary-coded '
        'targets are counted separately and omitted from point-error scores.', '',
        '## What the results establish', '',
        'CGM-only XGBoost has the lowest overall participant MAE in the full cohort '
        '(17.53/27.47 at 30/60 minutes), versus persistence 20.92/32.32. '
        'Clinical-profile additions show no convincing overall gain: their paired '
        'intervals include zero. In the matched pump subset, adding insulin to '
        'clinical + CGM XGBoost reduces participant MAE by 0.105/0.222 mg/dL '
        '(95% intervals [-0.128,-0.084]/[-0.279,-0.171]). These are small '
        'point-forecast gains, conditional on this fixed configuration.', '',
        'Low-target errors remain a major weakness. Full-cohort CGM-only XGBoost '
        'has low-target participant MAE 29.13/54.31 versus persistence 26.68/50.04. '
        'Ridge has lower 30-minute low/high-target errors and RMSE than XGBoost, '
        'despite slightly worse overall MAE. The numerical MAE winner does not '
        'dominate every error metric. This dataset switch has not established '
        'reliable adverse-event prediction.', '',
        '## All development participants', '',
        '| Horizon | Method | Pooled MAE | Participant MAE | Participant RMSE | Low-target MAE | High-target MAE | Strict-subset MAE |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for h, cohorts in report['horizons'].items():
        for name, score in cohorts['all_clinical']['scores'].items():
            macro = score['patient_macro_slices']
            values = [score['mae'], macro['all']['mean_patient_mae'], macro['all']['mean_patient_rmse'],
                      macro['low']['mean_patient_mae'], macro['high']['mean_patient_mae'],
                      macro['strict']['mean_patient_mae']]
            lines.append(f'| {h} min | {name} | '+' | '.join(f'{v:.2f}' for v in values)+' |')
    lines += ['', '## Pump-linked participants only', '',
        'All three input arms below fit and evaluate within the same 100-person '
        'subset (89 CLC, 11 SAP). Do not interpret a difference between this table '
        'and the 134-person table as an insulin-input gain.', '',
        '| Horizon | Method | Pooled MAE | Participant MAE | Participant RMSE | Low-target MAE | High-target MAE | Strict-subset MAE |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for h, cohorts in report['horizons'].items():
        for name, score in cohorts['pump_linked']['scores'].items():
            macro = score['patient_macro_slices']
            values = [score['mae'], macro['all']['mean_patient_mae'], macro['all']['mean_patient_rmse'],
                      macro['low']['mean_patient_mae'], macro['high']['mean_patient_mae'],
                      macro['strict']['mean_patient_mae']]
            lines.append(f'| {h} min | {name} | '+' | '.join(f'{v:.2f}' for v in values)+' |')
    lines += ['', '## Paired effects of additional inputs', '',
        'Differences are candidate minus reference in participant MAE; negative '
        'means improvement. Intervals use 2,000 participant bootstrap samples, '
        'conditional on these fitted models. They do not capture all variability '
        'from refitting the training cohort.', '',
        '| Horizon | Cohort | Comparison | Overall difference (95% interval) | Low-target difference | High-target difference |',
        '|---|---|---|---:|---:|---:|']
    for h, cohorts in report['horizons'].items():
        for cohort, data in cohorts.items():
            for name, diff in data['paired_comparisons'].items():
                if name.endswith('_versus_persistence'):
                    continue
                all_diff = diff['all_mae']
                lo, hi = all_diff['patient_bootstrap95']
                lines.append(f'| {h} min | {cohort} | {name} | '
                    f'{all_diff["mean_difference"]:+.3f} [{lo:+.3f}, {hi:+.3f}] | '
                    f'{diff["low_mae"]["mean_difference"]:+.3f} | {diff["high_mae"]["mean_difference"]:+.3f} |')
    lines += ['', '## Treatment-group context', '',
        '| Horizon | Cohort | Treatment | Method | Participants | Participant MAE |',
        '|---|---|---|---|---:|---:|']
    for h, cohorts in report['horizons'].items():
        for cohort, data in cohorts.items():
            for group, scores in data['by_treatment_group'].items():
                for name, score in scores.items():
                    if name == 'persistence' or name.startswith('xgb_delta_'):
                        lines.append(f'| {h} min | {cohort} | {group} | {name} | '
                            f'{score["patients"]} | {score["patient_macro_slices"]["all"]["mean_patient_mae"]:.2f} |')
    lines += ['', '## Reproduce', '', 'From the `project` directory, after preparing v2:', '',
        '```powershell', 'python scripts/run_dclp3_study.py',
        'python scripts/verify_dclp3_study.py', 'python scripts/summarize_dclp3_study.py', '```', '',
        'The runner freezes its implementation, cache, role and configuration '
        'fingerprints before fitting. Matching saved local models can be reused '
        'on rerun; changed execution fingerprints are rejected. Source records, '
        'participant predictions and model files stay local and ignored by Git.', '',
        '## Verification and limits', '',
        f'Training completed locally in {report["runtime"]["seconds"]:.1f} seconds '
        f'with {report["runtime"]["threads"]} threads. Sampled peak resident memory '
        f'was {report["runtime"]["sampled_peak_rss_mib"]:.1f} MiB. '
        f'{checks["model_artifacts_verified"]} saved models and '
        f'{checks["training_only_preprocessors_verified"]} training-only preprocessors '
        f'were checked, with {checks["saved_prediction_probes"]} inference parity probes. '
        'Overall, low/high-target, current-glucose, strict-timestamp and treatment-group '
        'scores and paired intervals were recomputed from matched predictions.', '',
        'These are retrospective development results, not medical validation. '
        'Point MAE is distinct from episode recall, false alarms and useful warning '
        'lead time. No adverse-event classifier, calibrated probability or operational '
        'alert was enabled. No dashboard model was replaced.', '',
        'The pump subset is dominated by closed-loop therapy; stable commanded '
        'basal states may be hidden by the conservative 30-minute freshness rule. '
        'Meal logs are absent. Clinical and sensor availability delays are assumptions. '
        'Lower errors on DCLP3 than on a different cohort do not establish that '
        'the model itself improved. The ±30-second subset and omitted boundary-coded '
        'targets must accompany point-error claims.', '',
        '[Complete aggregate results](../reports/dclp3_study_v2.json), '
        '[verification](../reports/dclp3_study_v2_checks.json), '
        '[frozen preparation contract](DCLP3_CONTRACT.md).', '']
    (ROOT/'docs/DCLP3_STUDY_V2.md').write_text('\n'.join(lines), encoding='utf-8')
    print('Wrote docs/DCLP3_STUDY_V2.md')


if __name__ == '__main__':
    main()
