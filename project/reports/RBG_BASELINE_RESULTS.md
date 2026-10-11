# RBG baseline results

Measured 9 October 2026. Training158patients; validation34; reservedtest34. Test targets/predictions not generated. Artificial study dates, rounded sensor timestamps and assumed enrollment-profile availability make this a research benchmark, not clinical validation.
## Point forecasting

All models use the same five-minute sensor availability delay. Each horizon trained on316,000 uniformly sampled rows (2,000/patient); all eligible validation rows evaluated.

| Horizon | Model | Validation MAE | RMSE | Patient-macro MAE | Errors >30 mg/dL |
|---|---|---:|---:|---:|---:|
| 30 min | persistence | 20.71 | 29.18 | 20.63 | 22.6% |
| 30 min | slope | 23.94 | 35.34 | 23.82 | 27.5% |
| 30 min | ridge_cgm | 17.59 | 24.80 | 17.51 | 17.0% |
| 30 min | ridge_cgm_profile | 17.59 | 24.80 | 17.51 | 17.0% |
| 60 min | persistence | 32.53 | 44.86 | 32.43 | 39.8% |
| 60 min | slope | 45.81 | 66.37 | 45.59 | 49.9% |
| 60 min | ridge_cgm | 28.89 | 39.15 | 28.77 | 35.9% |
| 60 min | ridge_cgm_profile | 28.89 | 39.15 | 28.78 | 36.0% |

## Error slices

| Horizon | Model | Future >180 MAE | Future <70 MAE |
|---|---|---:|---:|
| 30 min | persistence | 25.10 | 19.76 |
| 30 min | ridge_cgm | 20.77 | 20.23 |
| 30 min | ridge_cgm_profile | 20.79 | 20.26 |
| 60 min | persistence | 40.66 | 36.98 |
| 60 min | ridge_cgm | 36.12 | 44.21 |
| 60 min | ridge_cgm_profile | 36.17 | 44.26 |

## Paired patient uncertainty

Exploratory95% bootstrap intervals,2,000 resamples of the34validation patient MAE differences. Negative differences favor CGM-only Ridge. These are development intervals; model selection and cohort assumptions limit generalization.

- 30min: mean patient MAE difference -3.13 mg/dL; interval [-3.46, -2.81]; Ridge improves 34/34 patients.
- 60min: mean patient MAE difference -3.66 mg/dL; interval [-4.14, -3.20]; Ridge improves 34/34 patients.

## Interpretation

CGM history gives useful average improvement over delayed persistence, but residual error remains substantial. Age/sex do not provide a meaningful predictive gain; do not advertise a proven fusion benefit. The60minute low-target error worsens from36.98 to44.21mg/dL with CGM-only Ridge. Average error improvement does not establish safe event warning. At30minutes, approximately17% of forecasts still miss by more than30mg/dL.

The30minute task is easier and can be a candidate for the next comparison; the60minute task must remain reported. No event classifier, episode sensitivity, lead time, medical error-grid assessment or independent clinical validation was performed here. No changes were made to the CGMacros dashboard/model.

Fit/scoring runtime 21.5seconds; sampled peak process memory 373.6MiB. Preparation took190.4seconds in bounded patient batches. Six RBG tests passed: delay/future-edit parity, exact/missing targets, warm-up/abstention, split/profile checks, training-row cap/test matrix exclusion, train-only imputation.

Next: predeclare a small CPU boosting comparison at both horizons and test whether it improves low/high slices as well as average errors. Keep34testpatients reserved. Clinical-profile benefit needs stronger verified historical inputs; HbA1c inclusion remains blocked on availability provenance.

See [RBG contract](../docs/RBG_DATA_CONTRACT.md), [aggregate preparation](rbg_preparation.json), and [validation metrics](rbg_baseline_validation.json).
