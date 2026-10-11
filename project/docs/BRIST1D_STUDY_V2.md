# BrisT1D freshness repair study v2

Freshness repair recovered the failed full-input Ridge model. XGBoost
changed very little and its low-target errors remain worse than persistence.
This is a successful failure-mechanism repair, not a convincing new accuracy
or adverse-event warning result. Dashboard models and warnings are unchanged.

Sixteen development patients, four fixed folds and four reserved patients
were retained from v1. Targets, issue times, admission, training samples and
evaluation rows are identical. No raw sensor files were opened in this study.
The reserved sources were previously quality-audited before role freezing;
they were not prepared or scored in v2.

## Fixed feature-only repair

Caps: thirty minutes for insulin/HR/steps/distance/calories observations,
480 minutes for recorded carbohydrate events. These are engineering freshness
assumptions written before fitting, not physiological action durations.
Age is measured from issue time to the latest available source timestamp.
Cap numeric age, mask stale latest values, add stale/unobserved flags, retain
all past-window amounts/counts/fractions and actual logged zeros. Unknown
meal logs remain unknown. The boundary age equal to a cap is fresh.

CGM/profile arms and their predictions are unchanged. The other three arms
were refitted with the same fixed Ridge/XGBoost configurations. The twelve
new flags give 152 full-input features. The comparison changes multiple
feature details together; it does not isolate the effect of clipping alone.

## Matched row-pooled errors

| Method | v1 MAE30 / MAE60 | v2 MAE30 / MAE60 | v2 RMSE30 / RMSE60 |
|---|---:|---:|---:|
| persistence | 23.36 / 34.76 | 23.36 / 34.76 | 32.47 / 47.41 |
| ridge_cgm_only | 20.70 / 30.72 | 20.70 / 30.72 | 28.47 / 41.22 |
| ridge_cgm_profile | 20.76 / 30.85 | 20.76 / 30.85 | 28.51 / 41.29 |
| ridge_cgm_profile_insulin | 20.86 / 31.16 | 20.86 / 31.11 | 28.57 / 41.56 |
| ridge_cgm_profile_insulin_carbs | 38.88 / 62.44 | 20.86 / 30.94 | 28.60 / 41.38 |
| ridge_fused | 37.47 / 60.99 | 20.87 / 30.96 | 28.57 / 41.33 |
| xgb_delta_cgm_only | 20.10 / 29.62 | 20.10 / 29.62 | 28.14 / 40.49 |
| xgb_delta_cgm_profile | 20.07 / 29.63 | 20.07 / 29.63 | 28.07 / 40.42 |
| xgb_delta_cgm_profile_insulin | 19.97 / 29.59 | 19.98 / 29.55 | 27.96 / 40.41 |
| xgb_delta_cgm_profile_insulin_carbs | 19.94 / 29.57 | 19.95 / 29.52 | 27.92 / 40.39 |
| xgb_delta_fused | 19.92 / 29.46 | 19.92 / 29.43 | 27.84 / 40.25 |

All units mg/dL. The same 625,755 / 612,635 endpoint rows cover
30 / 60 minutes. Overlapping rows are not independent patients.

## Patient-macro slices

| v2 method | Low MAE30 / MAE60 | High MAE30 / MAE60 | P95 error30 / error60 |
|---|---:|---:|---:|
| persistence | 29.79 / 54.30 | 31.48 / 47.98 | 70.38 / 100.79 |
| ridge_fused | 33.09 / 63.43 | 28.44 / 45.12 | 61.19 / 86.49 |
| xgb_delta_cgm_profile | 34.90 / 60.32 | 28.60 / 46.31 | 61.11 / 85.85 |
| xgb_delta_fused | 34.46 / 59.80 | 28.37 / 46.30 | 60.65 / 85.54 |

Each high/low slice contains sixteen patients. P95 is the mean of
patient quantiles. Low/high means use exact targets below 70 / above 180.

Full-input XGBoost v2-minus-v1 paired mean-patient MAE differences:

- 30 minutes: -0.0064 mg/dL; exploratory patient bootstrap 95% [-0.0202, 0.0072].
- 60 minutes: -0.0006 mg/dL; exploratory patient bootstrap 95% [-0.0507, 0.0510].

Both intervals include zero. Development patients have been inspected
repeatedly; these intervals are not selection-adjusted final-test evidence.

## What the diagnostics show

| Diagnostic | 30 min | 60 min |
|---|---:|---:|
| v1 Ridge: row MAE with insulin observation age >360 min | 169.32 | 296.25 |
| v2 Ridge: same original-age rows | 22.58 | 34.65 |
| v2 XGBoost: five-minute cadence row MAE | 19.39 | 28.87 |
| v2 XGBoost: fifteen-minute cadence row MAE | 25.60 | 36.76 |
| v2 XGBoost: bias when current glucose <70 | -12.72 | -18.86 |
| v2 XGBoost: bias when actual target <70 | 34.36 | 59.79 |

Bias is predicted minus actual. Insulin age >360 minutes has six
patients and 70,713 / 70,267 rows; this supports the outage-extrapolation
diagnosis. Five-/fifteen-minute strata contain twelve/four different patients;
cadence differences do not establish a causal cadence effect.

Current-low and future-low rows have opposite bias signs. This shows why
target-conditioned error and issue-time calibration must be distinguished.
It does not by itself prove regression to the mean or identify the missing
predictive signal. Current-low XGBoost bias is still nonzero.

Mean patient predicted-delta / realized-delta variance ratios for v2
full-input XGBoost are 0.220 / 0.252. Lower dispersion is descriptive; unpredictable outcomes also contribute
to realized variance, so the ratio does not prove an estimator defect.

The full diagnostic report includes current/predicted bins, past-slope
strata, uncapped insulin/carbs/HR age groups, low-slice support and
per-patient low-MAE distribution summaries. Sparse bins are descriptive.

## Runtime and verification

48 new fixed fits, 99.04 seconds including cache repair,
1535.86 MiB sampled peak process RSS, eight CPU threads.

19 BrisT1D tests passed. All sixteen repaired matrices were recomputed;
fit samples and evaluation arrays matched v1. Forty-eight saved models
reproduced eight prediction probes each. Eleven aggregate methods per
horizon were recomputed. Diagnostic counts/error aggregates were checked.
V1 reference hashes and all unchanged-arm predictions were unchanged.
Reserved feature matrices and prediction groups: zero.

## Next decision

Retain v2 as the repaired experimental baseline. Do not replace the
dashboard or claim low-event reliability from this round. Next predeclare
a small matured-outcome residual adaptation comparator, reporting its
warm-up and activation coverage separately. A compact neural experiment
and a frozen event-onset contract remain later hypotheses, not completed
work. No additional dataset claims were verified in this round.

[Review adjudication](MAE_REVIEW_ACTIONS_V2.md),
[v1 reference](BRIST1D_STUDY_V1.md),
[v2 aggregate JSON](../reports/brist1d_study_v2.json),
[diagnostic JSON](../reports/brist1d_freshness_diagnostics_v2.json),
[report-bound checks](../reports/brist1d_study_v2_checks.json),
[configuration](../configs/brist1d_freshness_v2.json).

Reproduce from `project` with local v1 caches and experiment dependencies:

```powershell
python scripts/run_brist1d_freshness_v2.py
python scripts/diagnose_brist1d_freshness.py
python scripts/verify_brist1d_freshness_v2.py
python scripts/summarize_brist1d_freshness_v2.py
```

The v2 runner refuses silent overwrites of existing study outputs.
No public push or reserved evaluation was performed.
