# BrisT1D matched neural sequence study v4

Completed: 11 October 2026.

One compact TCN and a matched-information delta XGBoost comparator were
trained locally. Existing v2 forecasts are retained as a reference. This
document reports every method and the important glucose slices; no
dashboard or operational warning model was changed.

## Frozen representation and model

- Two hours of history queried every five minutes: 25 points, seven
  channels (CGM, insulin, logged carbs, HR, steps, distance, calories).
- Each channel carries a freshest available value, fresh mask, new source
  observation flag, bounded age fraction and never-observed flag. Channel
  delays and freshness caps match v1/v2. A carried dose/meal value is
  context, not a second administered dose or consumed meal.
- The history grid is a set of past availability queries. No glucose
  value or missing future endpoint is interpolated. Native fifteen-minute
  streams have fewer new-observation flags; missing meals stay unknown.
- A context branch receives all 152 v2 point features, including historical
  patient fields and existing meal summaries extending to eight hours.
  Both methods receive the same history/context information.
- TCN: three residual blocks, sixteen hidden channels, two left-padded
  convolutions per block, kernel three, dilations 1/2/4, dropout 0.15.
  Its nominal receptive field is 29 samples, covering all 25 input points.
  Context hidden width sixteen and head width thirty-two produce two
  endpoint delta predictions. The output starts at persistence.
- Matched XGBoost uses the flattened identical encoded history and context,
  one fixed delta model per horizon with the prior v1 model parameters.

Masks/age fractions are unchanged by preprocessing. Sequence-value means
and standard deviations (fixed minimum standard deviation one source unit)
and context imputation/scaling are fitted only on the relevant fitting
patients. Missing/stale values are represented by normalized zero plus
their masks; a logged zero has distinct observation/freshness flags.

## Patient roles and training

Sixteen development patients retain the same four outer patient folds.
Four reserved participants were neither opened for sequence preparation
nor scored. The earlier whole-cohort quality audit had inspected all twenty.
All original 625,755 / 612,635 exact 30 / 60-minute evaluation endpoints
are retained, with their original issue times and availability assumptions.

For each outer fold, three of its twelve fitting patients (two five-minute,
one fifteen-minute) are selected by a fixed seed for inner stopping.
Nine fit the inner model. The stopping score averages patient MAE over
both horizons. Maximum fifteen epochs, patience three, minimum improvement
0.01 mg/dL; outer patients never choose epochs. The network is then reset
and refitted on all twelve fitting patients for the selected epoch count.

The final fit uses up to 4,000 deterministic uniformly sampled issues per
patient with at least one exact target. Both methods use these identical
issue samples, masking missing heads. Loss/fit weights give equal total
weight to each patient and head. No sample is chosen from glucose magnitude.
The earlier v2 reference used different per-horizon sampling and fewer
sequence inputs; only the new matched comparator controls those differences.

| Fold | Selected epochs | Final parameters | Final labeled rows 30 / 60 |
|---|---:|---:|---:|
| 1 | 5 | 10,690 | 47,085 / 44,535 |
| 2 | 3 | 10,674 | 47,015 / 44,808 |
| 3 | 5 | 10,690 | 47,294 / 44,452 |
| 4 | 7 | 10,626 | 47,543 / 45,197 |

## Measured errors

| Method | MAE30 / MAE60 | RMSE30 / RMSE60 | Patient-macro MAE30 / MAE60 |
|---|---:|---:|---:|
| persistence | 23.36 / 34.76 | 32.47 / 47.41 | 24.26 / 35.60 |
| v2_xgb_fused | 19.92 / 29.43 | 27.84 / 40.25 | 20.74 / 30.45 |
| matched_xgb | 19.98 / 29.54 | 27.91 / 40.37 | 20.82 / 30.59 |
| tcn | 20.44 / 29.70 | 28.24 / 40.33 | 21.16 / 30.52 |

Units mg/dL. Hundreds of thousands of overlapping rows come from only
sixteen independent development patients.

| Method | Patient-macro low MAE30 / MAE60 | High MAE30 / MAE60 | P95 error30 / error60 |
|---|---:|---:|---:|
| persistence | 29.79 / 54.30 | 31.48 / 47.98 | 70.38 / 100.79 |
| v2_xgb_fused | 34.46 / 59.80 | 28.37 / 46.30 | 60.65 / 85.54 |
| matched_xgb | 34.36 / 60.62 | 28.53 / 45.76 | 60.69 / 85.66 |
| tcn | 33.93 / 59.73 | 28.94 / 46.01 | 61.14 / 85.78 |

Low/high slices use actual exact endpoints below 70 / above 180 mg/dL.
All sixteen patients contribute to each slice. P95 is the mean of individual
patient quantiles, not a pooled quantile. Full tail fractions and biases
are retained in the aggregate JSON.

## Paired TCN versus matched XGBoost evidence

| Metric: mean patient difference | 30 min [bootstrap 95%] | 60 min [bootstrap 95%] |
|---|---:|---:|
| all_mae | +0.347 [+0.025, +0.765] | -0.076 [-0.564, +0.366] |
| all_rmse | +0.333 [-0.081, +0.827] | -0.028 [-0.654, +0.513] |
| all_p95_absolute_error | +0.444 [-0.461, +1.320] | +0.127 [-1.335, +1.372] |
| high_mae | +0.412 [-0.443, +1.262] | +0.246 [-1.240, +1.721] |
| low_mae | -0.427 [-3.121, +2.366] | -0.898 [-5.101, +2.788] |

Negative favors TCN. These are exploratory intervals over repeatedly
inspected development patients, not selection-adjusted final test evidence.
Different outer folds share fitting patients. A small typical-error gain
does not establish reliable event warnings or better severe-error behavior.

## Interpretation

TCN did not improve mean-patient typical MAE against the matched
comparator at both horizons. This fixed architecture is not an
overall replacement on the evidence shown here.
TCN low-target errors still exceed persistence at one or both horizons.
No final held-out test or event operating/calibration gate was evaluated.
No architecture/loss/seed sweep was run, and the result does not establish
that every possible neural model would behave similarly.

## Verification and runtime

31 BrisT1D tests executed, including neural causality and head masking.
6 real prefix probes at both native cadences matched cached histories.
All four final-fit preprocessing objects were recomputed from fitting
patients, and inner roles/epoch selection/final samples were verified.
Saved TCN and matched XGBoost reproduced 256 / 256
endpoint prediction probes. Original evaluation arrays and every aggregate
method were recomputed. Reserved sequence matrices and prediction groups: zero.

CPU training and evaluation: 641.28 seconds,
3538.55 MiB sampled peak RSS, eight threads.
Sequence preparation is reported separately. CPU-only PyTorch was installed
in an optional project-local environment using the
[official previous-version installation source](https://pytorch.org/get-started/previous-versions/).

[Frozen config](../configs/brist1d_sequence_v4.json),
[sequence encoding](../src/glucotwin/brist1d_sequence.py),
[TCN](../src/glucotwin/brist1d_tcn.py),
[runner](../scripts/run_brist1d_sequence_v4.py),
[aggregate results](../reports/brist1d_sequence_v4.json),
[report-bound checks](../reports/brist1d_sequence_v4_checks.json),
[preparation counts](../reports/brist1d_sequence_preparation_v4.json).

Reproduce from `project` in the optional CPU torch environment:

```powershell
python scripts/prepare_brist1d_sequence_v4.py
python scripts/run_brist1d_sequence_v4.py
python scripts/verify_brist1d_sequence_v4.py
python scripts/summarize_brist1d_sequence_v4.py
```

Completed cache/report preparation refuses silent overwrites. Source data,
sequence arrays and neural/model artifacts remain private. No push was performed.
