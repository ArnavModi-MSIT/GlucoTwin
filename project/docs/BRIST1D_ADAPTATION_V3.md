# BrisT1D causal residual adaptation v3

Completed: 11 October 2026.

The fixed residual-adaptation rule did not improve the strongest full-input
XGBoost baseline overall. It worsened overall errors while slightly reducing
some high/low slice errors. Ridge gains were small, with unresolved tail
and low-target errors. This rule is rejected as a general replacement.
No model or warning change was deployed.

## Frozen experiment

Sixteen held-out development patients retain their four original folds.
Four reserved patients remain unscored. Saved v2 population forecasts and
the same 625,755 / 612,635 exact endpoint rows are used at 30 / 60 minutes.
No model was refitted and no sensor source was opened.

Each patient, horizon and method starts with independent zero state:

- Schedule the first history-eligible issue, then the first issue at least
  sixty minutes after the preceding scheduled issue. The schedule includes
  issues whose targets later turn out missing; no replacement update is
  chosen after learning target availability.
- A scheduled residual is actual minus the unadapted forecast. It becomes
  usable only at issue + horizon + five-minute target delay. This delay is
  the prior measurement-availability assumption, not the cadence-rounded
  reading-triggered issuance offset.
- Retain matured residuals from the preceding 24 hours, clip each at ±60
  mg/dL and weight by a six-hour time half-life. Divide weighted residual
  sum by weight sum plus four zero-residual prior units.
- Require twelve retained matured updates, and a latest matured update
  within three hours. Otherwise use the unadapted forecast. Clip the final
  correction at ±10 mg/dL and add it to the population forecast.

These are fixed research assumptions recorded before execution, not tuned
physiology or optimized settings. Hourly updates remain correlated. Prior
target values from a new patient are used, making this an online-adaptation
estimand distinct from unadapted new-patient forecasting. Whole-record
patient calibration and future target access are prohibited.

## All-row measured errors

| Method | MAE30 / MAE60 | RMSE30 / RMSE60 | Patient-macro MAE30 / MAE60 |
|---|---:|---:|---:|
| unadapted_persistence | 23.36 / 34.76 | 32.47 / 47.41 | 24.26 / 35.60 |
| adapted_persistence | 23.93 / 35.79 | 33.25 / 48.75 | 24.83 / 36.59 |
| unadapted_ridge_fused | 20.87 / 30.96 | 28.57 / 41.33 | 21.85 / 32.34 |
| adapted_ridge_fused | 20.85 / 30.79 | 28.64 / 41.36 | 21.69 / 31.96 |
| unadapted_xgb_delta_fused | 19.92 / 29.43 | 27.84 / 40.25 | 20.74 / 30.45 |
| adapted_xgb_delta_fused | 20.14 / 29.54 | 28.07 / 40.33 | 20.93 / 30.49 |

Units mg/dL. Every method is reported, including the worsening persistence
control. Row-pooled and patient-macro metrics differ.

## Error slices and tail performance

| Method | Low MAE30 / MAE60 | High MAE30 / MAE60 | P95 error30 / error60 |
|---|---:|---:|---:|
| unadapted_persistence | 29.79 / 54.30 | 31.48 / 47.98 | 70.38 / 100.79 |
| adapted_persistence | 28.51 / 53.30 | 32.16 / 49.17 | 72.14 / 103.50 |
| unadapted_ridge_fused | 33.09 / 63.43 | 28.44 / 45.12 | 61.19 / 86.49 |
| adapted_ridge_fused | 31.14 / 61.64 | 27.98 / 44.92 | 61.47 / 86.91 |
| unadapted_xgb_delta_fused | 34.46 / 59.80 | 28.37 / 46.30 | 60.65 / 85.54 |
| adapted_xgb_delta_fused | 33.29 / 59.20 | 28.02 / 45.41 | 61.16 / 85.83 |

These are patient-macro values. Low/high are exact future targets below
70 / above 180 mg/dL; each slice contains sixteen patients. P95 means
the average of patient quantiles. Adapted XGBoost still has worse low-target
MAE than unadapted persistence, despite its small slice improvements.

## Activation and paired evidence

- 30 minutes: active on 610,983/625,755 rows (97.64%), all sixteen patients; paired mean-patient MAE change +0.188 mg/dL, exploratory bootstrap 95% [+0.115, +0.262].
- 60 minutes: active on 587,069/612,635 rows (95.83%), all sixteen patients; paired mean-patient MAE change +0.045 mg/dL, exploratory bootstrap 95% [-0.105, +0.202].

Positive difference means worse. The 30-minute MAE interval excludes zero
in the unfavorable direction; the 60-minute interval includes zero. Some
slice improvements come with worse overall/tail errors. Development patients
have been inspected repeatedly and these are not selection-adjusted final
test intervals. No event recall or warning reliability claim follows.

Active-only and inactive-only scores are also retained in the JSON; both
adapted and unadapted predictions are scored on identical masks. Inactive
predictions equal the baseline exactly. High activation coverage describes
long retrospective replay sessions and does not remove initial warm-up
requirements in a new short session.

## Verification and runtime

25 BrisT1D tests passed, including exact maturity boundaries, future-target
perturbation, prefix parity, missing-target scheduling, independent patient
state, clipping, warm-up and outage expiry.

Independent search-based counts and activation checks covered 3,715,170
patient/method/horizon rows. 3,072 probes independently computed direct weighted sums,
rather than repeating the incremental state implementation. All aggregate
all/active/inactive scores and coverage were recomputed. V1/v2 reference
hashes were unchanged. Reserved matrices and prediction groups: zero.

Adaptation and scoring took 17.43 seconds locally. Sampled RSS was
549.73 MiB after loading and at fold boundaries; this is not continuous
peak tracking. No GPU or new model fitting was required.

## Decision and next work

Keep the unadapted repaired v2 XGBoost as the stronger existing benchmark.
Retain v3 as a failed fixed adaptation experiment; do not silently tune its
parameters after seeing held-out results. This outcome does not disprove all
personalization methods. It shows that this simple recent residual rule
does not solve the present accuracy/safety-slice tradeoff.

The next planned comparison is one compact neural sequence model against
a tabular comparator with matched information, patient-disjoint inner stopping,
unchanged targets and reserved-patient exclusion. Its representation and
architecture must be frozen first. Neural training has not started.

[Fixed adaptation configuration](../configs/brist1d_adaptation_v3.json),
[causal implementation](../src/glucotwin/brist1d_adaptation.py),
[runner](../scripts/run_brist1d_adaptation_v3.py),
[aggregate results](../reports/brist1d_adaptation_v3.json),
[report-bound checks](../reports/brist1d_adaptation_v3_checks.json),
[v2 reference](BRIST1D_STUDY_V2.md).

Reproduce from `project` with the existing local v1/v2 caches:

```powershell
python scripts/run_brist1d_adaptation_v3.py
python scripts/verify_brist1d_adaptation_v3.py
python scripts/summarize_brist1d_adaptation_v3.py
```

The runner refuses silent overwrites. Raw data, patient-level prediction
arrays and fitted artifacts remain private. No public push was performed.
