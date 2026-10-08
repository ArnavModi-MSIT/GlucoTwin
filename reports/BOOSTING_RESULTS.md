# Gradient boosting comparison and model decision

Run: 8 October 2026. Six development validation patients, 15,217 identical admissible rows. Final test model scores remain reserved. All samples are reconstructed CGMacros data with the limitations in `DATA_CONTRACT.md`.

## Configuration

One CPU HistGradientBoostingRegressor configuration, no parameter search: absolute-error loss, 120 iterations, learning rate 0.05, 15 maximum leaves, minimum 80 samples per leaf, L2=10, seed 2026, four threads. Early stopping disabled to avoid an internal random validation split among overlapping windows. Native missing-value support; no test-fitted preprocessing.

## Validation results

| Model | Overall MAE | Overall RMSE | High-target MAE | Low-target MAE |
|---|---:|---:|---:|---:|
| Persistence | 19.99 | 31.52 | 47.39 | 20.26 |
| Ridge CGM + clinical + HR | 19.00 | 28.13 | 44.85 | 38.80 |
| Boost CGM only | 18.45 | 29.72 | 49.90 | 43.51 |
| Boost CGM + clinical | 18.79 | 30.54 | 54.10 | 43.32 |
| Boost CGM + clinical + HR | 18.96 | 30.81 | 55.04 | 43.05 |

All errors are mg/dL. High-target slice: 2,538 rows with actual +60 glucose >180. Low-target slice: only 39 rows with actual +60 glucose <70. These are overlapping rows, not independent clinical episodes.

**Decision:** retain the fused Ridge as the provisional dashboard point forecaster. Fused boosting improves its overall MAE by only 0.035 mg/dL, while worsening RMSE by 2.68 and high-target MAE by 10.19. This matches the protocol's preference for simplicity and concern about materially worse error slices. The nominal best overall-MAE model is CGM-only boosting, but it omits the required historical clinical inputs and worsens high/low error slices. It is a comparison, not the chosen fused forecaster.

This is a development decision, not a successful final adverse-event system. A separate classifier must be evaluated before displaying a calibrated future-high probability. Regression alone has substantial high-glucose errors, and no model supports reliable hypoglycemia claims here.

## Fusion and patient differences

- Boosting gains average accuracy over persistence, but adding clinical and HR features worsens this configuration. Do not claim clinical fusion always helps.
- CGM-only and fully fused boosting improve average MAE on all six validation patients; clinical-only-added boosting improves five. This does not imply better high/low performance within those patients.
- Exploratory patient-bootstrap intervals for mean MAE delta versus persistence exclude zero for these configurations. With only six patients, repeated development comparisons and no selection-adjusted uncertainty, they are not robust clinical/generalization evidence.
- Type 2 slice, two validation patients: fused Ridge MAE 26.24; CGM-only boost 26.39; fully fused boost 27.35. This is another reason not to promote fused boosting.

## High-glucose forecast bias

On true high endpoints, fused Ridge mean signed error is -39.65 mg/dL; fused boosting -53.24. Thresholding numerical forecasts at 180 identifies 59.0% and 44.3% of those high endpoints respectively. Persistence identifies 65.8% in this broad slice, which includes already-high current readings. These fractions are descriptive endpoint recall, not new-onset recall, probabilities, alert utility or advance-warning lead times. Precision and eligible-new-high evaluation must accompany any future classification claim.

The pattern is consistent with regression toward typical glucose values and the MAE objective favoring conditional medians; it is an interpretation, not a proven physiological explanation. Do not select a model solely from overall MAE for the adverse-event objective.

## Efficiency and verification

All three boosting fit/predict runs together took 2.49 seconds; sampled peak process RSS 250.76 MiB. Individual runs took 0.47–1.06 seconds. CPU only; no GPU dependency. Hardware/runtime constraints are feasible at this scale.

Seven tests passed, including earlier temporal/target checks, saved-boosting prediction parity and confirming Ridge's imputation statistics match training-only medians. These do not verify raw sensor timing or clinical effectiveness.

Artifacts: numerical metrics in `reports/boosting_validation.json`; per-patient metrics in `reports/boosting_validation_patient_metrics.csv`; bias analysis in `reports/forecast_error_analysis.json`. Locally saved model artifacts and patient-level prediction files are Git-ignored.

Reproduce: `python scripts/train_boosting.py`, then `python -m unittest discover -s tests -v` in the training environment. No further modeling/tuning was performed after this comparison.

## Next step

Freeze the regression choice and assess a small endpoint classifier on development patients with separate tuning/calibration roles established before classifier fitting. Report at-risk endpoint performance, prevalence and reliability. If calibration support is insufficient, display a numerical forecast and clearly labelled derived threshold flag, without a probability. Keep final test model scores reserved until regression/classification choices and app parity are frozen.
