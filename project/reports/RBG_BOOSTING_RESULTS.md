# RBG fixed boosting comparison

Measured 9 October 2026 using frozen patient roles, sampling and five-minute availability delay. No configuration sweep. Models trained on 158 patients, scored on 34 validation patients; 34 test patients remain reserved.

| Horizon | Model | MAE | RMSE | Future >180 MAE | Future <70 MAE | Errors >30 |
|---|---|---:|---:|---:|---:|---:|
| 30min | persistence | 20.71 | 29.18 | 25.10 | 19.76 | 22.6% |
| 30min | ridge_cgm | 17.59 | 24.80 | 20.77 | 20.23 | 17.0% |
| 30min | boost_cgm | 17.20 | 24.74 | 21.22 | 22.67 | 17.2% |
| 30min | boost_cgm_profile | 17.21 | 24.75 | 21.21 | 22.74 | 17.2% |
| 60min | persistence | 32.53 | 44.86 | 40.66 | 36.98 | 39.8% |
| 60min | ridge_cgm | 28.89 | 39.15 | 36.12 | 44.21 | 35.9% |
| 60min | boost_cgm | 27.73 | 38.66 | 37.03 | 44.74 | 33.9% |
| 60min | boost_cgm_profile | 27.77 | 38.68 | 37.02 | 45.05 | 34.0% |

## Predeclared gate results

Replacement requires lower overall MAE/RMSE and no worsening in either high/low target MAE versus CGM-only Ridge. This gate does not certify medical usefulness.

- 30 minutes: provisional choice `ridge_cgm`.
  - boost_cgm: mae_improves=pass, rmse_improves=pass, high_not_worse=FAIL, low_not_worse=FAIL.
  - boost_cgm_profile: mae_improves=pass, rmse_improves=pass, high_not_worse=FAIL, low_not_worse=FAIL.
- 60 minutes: provisional choice `ridge_cgm`.
  - boost_cgm: mae_improves=pass, rmse_improves=pass, high_not_worse=FAIL, low_not_worse=FAIL.
  - boost_cgm_profile: mae_improves=pass, rmse_improves=pass, high_not_worse=FAIL, low_not_worse=FAIL.

## Paired patient differences

Exploratory 95% intervals from 2,000 patient bootstrap samples; negative favors boosting over CGM-only Ridge. Development selection uncertainty is not removed by bootstrapping.

- 30 minutes,boost_cgm: mean difference -0.37 mg/dL, interval [-0.47,-0.27],improves32/34 patients.
- 30 minutes,boost_cgm_profile: mean difference -0.37 mg/dL, interval [-0.47,-0.27],improves32/34 patients.
- 60 minutes,boost_cgm: mean difference -1.13 mg/dL, interval [-1.35,-0.89],improves32/34 patients.
- 60 minutes,boost_cgm_profile: mean difference -1.09 mg/dL, interval [-1.30,-0.85],improves32/34 patients.

Runtime 79.1 seconds; sampled peak RSS 357.4 MiB. Fixed 120 iterations, 15 leaves, absolute-error loss, learning rate 0.05, minimum leaf size 80, L2=10, seed 2026, early stopping disabled, four CPU threads. Native missing handling; validation never used for fitting.

No new clinical claims, calibrated probabilities, onset lead-time assessment or dashboard model switch. Age/sex inclusion does not by itself prove a fusion benefit. Glucose target lows/highs are retrospective slices and overlapping rows, not independent episodes. Thresholds and timestamp assumptions are specified in the [contract](../docs/RBG_DATA_CONTRACT.md).
