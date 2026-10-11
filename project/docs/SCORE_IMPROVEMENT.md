# Score improvement experiments

An optional [event research replay](EVENT_REPLAY.md) now serves the frozen
CGMacros v2 onset models on their excluded evaluation patients. This integration
does not improve the study scores, enable operational alerts or change the
offline DCLP3 numerical models.

The [DCLP3 fixed CPU study](DCLP3_STUDY_V2.md) now evaluates 134 development
participants, with 34 reserved. CGM-only XGBoost participant MAE is 17.53/27.47
at 30/60 minutes versus persistence 20.92/32.32. Historical clinical additions
show no convincing gain. In the matched 100-person pump subset, insulin adds
only 0.105/0.222 mg/dL improvement to clinical + CGM XGBoost. Low-target errors
still exceed persistence; the dataset switch has not resolved warning quality.
Eighty artifacts/preprocessors and 1,280 inference probes were verified, and
all aggregate/paired scores recomputed. No dashboard replacement or alerts.

Scope: improve prediction quality before adding dashboard capabilities. Run locally
first; cloud execution is unnecessary for these experiments. Preserve previous
results, event definitions, evaluation gates, and the six reserved CGMacros patients.

## Method comparisons

The v3 onset study adds causal glucose lags, 2/4/24-hour summaries, recent
acceleration, deviation from the trailing daily mean, and clock features. It selects
models using episode F1 divided by max(1, false alarms per eligible day), rather
than row-level average precision. Each inner split separates fitting, cutoff
selection, and evaluation patients. Outer boundaries and endpoint rules match v2.
The fused method includes clock features; the CGM-only comparator excludes them.
Consequently, differences cannot be attributed solely to historical clinical fields.
This is another exploratory comparison on previously inspected development patients.

Completed locally in 595 seconds, sampled peak process RSS 286 MiB. The revised
fused onset method detected 173/336 episodes: recall 51.5%, precision 53.9%,
0.72 false alarms per eligible day, median lead 10 minutes. Previous XGBoost v2
detected 229/336: recall 68.2%, precision 52.8%, 0.98 false alarms per eligible
day, median lead 10 minutes. The revised method failed the unchanged pooled gate;
fewer false alarms came with many more missed events. Reject v3 as an overall
improvement and preserve v2 as the stronger event research reference, without
enabling warnings. All methods remain unapproved for operational alerts.

The regression comparison evaluates original-feature Ridge, longer-history
HistGradientBoosting and XGBoost, then a separately versioned XGBoost method that
predicts future glucose minus current glucose. Training gives each patient equal
total weight. Three separate patients select the minimum mean patient MAE; nine
patients per outer fold evaluate that selection. Every development patient is
evaluated once. Inputs are causal, but the published CGMacros grid itself is
reconstructed, retaining its existing provenance limitations.

| CGMacros method | 30-minute MAE | 60-minute MAE | 30-minute RMSE | 60-minute RMSE |
|---|---:|---:|---:|---:|
| Persistence | 13.26 | 19.97 | 20.59 | 30.71 |
| Ridge with original features | 12.13 | 17.97 | 18.12 | 26.40 |
| XGBoost with longer history | 12.07 | 18.14 | 18.86 | 28.47 |
| XGBoost predicting glucose change | 11.73 | 17.46 | 18.24 | 27.32 |
| Method selected on separate patients, v4 | 11.91 | 17.77 | 18.35 | 27.28 |

Units: mg/dL. These results are not directly comparable to earlier RBG numbers:
the cohorts, targets and splits differ. The residual XGBoost configuration lowers
pooled MAE approximately 3.2% and 2.8% versus Ridge, but worsens RMSE. Its paired
patient-mean MAE difference intervals include zero at both horizons. Selection
among methods yields a smaller gain. This is not sufficient evidence to replace
the dashboard model, or claim fewer severe errors. Low/high-glucose slices still
need separate assessment before any promotion. Detailed aggregate results are in
`reports/regression_methods_v3.json`, `reports/regression_methods_v4.json`, and
`reports/regression_methods_v4_paired.json`; record-level outputs remain private.

## Dataset audit

[BrisT1D original release](https://data.bris.ac.uk/data/dataset/33z5jc8fa6tob21ptrugzqog08)
contains an open processed release, demographic data, and CC BY 4.0 licensing.
Its [original schema](https://data.bris.ac.uk/datasets/33z5jc8fa6tob21ptrugzqog08/README.txt)
includes insulin, carbohydrates, glucose and wearable streams. Raw exports are
restricted. This is a candidate for stronger inputs, not a claim of better scores.

One participant pilot and metadata were downloaded, not the entire cohort. The
pilot has 136,220 rows but only 18,975 glucose observations, with insulin and
carbohydrate entries present. Devices occupy separate rows: 62,038 repeated
timestamps and six repeated glucose timestamps require explicit reconciliation.
Do not treat every row as a synchronized complete reading or fill missing food
entries with zero. Demographics require cp1252 decoding. Event-entry availability,
sensor gaps, device synchronization, units (glucose mmol/L), and clinical linkage
must pass audit before training. No pilot model was trained and no BrisT1D result
has been substituted for the existing benchmarks.

Decision: the current method changes do not provide a reliable overall win.
Prioritize an audit of synchronized insulin/carbohydrate inputs and their
availability in BrisT1D before another modeling round. Maintain a separate Type 1
cohort benchmark; do not pool it blindly with CGMacros or claim improvement merely
because its absolute MAE differs. Subsequent selection stays within development
patients and any final evaluation requires a frozen protocol.

## Full processed cohort now audited

The full downloaded release has since been audited: 20 sensor participants,
2,875,613 source rows and 847,956 reconciled glucose observations. Five
participants have 15-minute CGM cadence; 15 have five-minute cadence. Full-cohort
insulin/HR overlap within the preceding five minutes is 80.66%/59.00%, much less
complete than the pilot. One participant has no insulin stream. See the
[full-cohort audit](BRIST1D_COHORT_AUDIT.md) for quality rules, exact target support,
metadata linkage and availability caveats. The earlier pilot report and all
prediction benchmarks remain unchanged. Next freeze a separate role/availability
contract, then run matched input ablations; no BrisT1D model has been trained.

### Follow-up fixed CPU study completed

The subsequent [BrisT1D v1 study](BRIST1D_STUDY_V1.md) froze native-cadence issue
times, explicit input delays, sixteen development patients in four folds and
four reserved patients. All arms share evaluation rows. Full-input XGBoost
MAE was 19.92/29.46 mg/dL at 30/60 minutes, versus CGM/profile XGBoost
20.07/29.63. Typical-error improvements are small, high/low difference intervals
include zero, and low-target errors still exceed persistence. Linear Ridge
failed badly with the additional inputs; a stale insulin-age term dominated one
extreme prediction. The reserved patients were not prepared or scored. These
numbers do not prove better performance than the separate RBG/CGMacros cohorts.
Next examine bounded recency/freshness handling and causal patient adaptation
under a new version, retaining the failed v1 results and existing dashboard models.

## Reproduce locally

The subsequent [v2 freshness study](BRIST1D_STUDY_V2.md) keeps all v1 opportunities,
targets and fit samples fixed. Thirty-minute observation caps for regularly
sampled action/wearable feeds and a 480-minute cap for meal logs prevent unbounded
recency extrapolation, with stale-value masking and explicit flags. Full-input
Ridge MAE recovered from 37.47/60.99 to 20.87/30.96; full-input XGBoost changed
from 19.92/29.46 to 19.92/29.43. Its low-target patient-macro MAE remains
34.46/59.80 versus persistence 29.79/54.30. All comparisons preserve rows and
four reserved patients. Nineteen BrisT1D tests and all 48 newly saved model probes
passed. This addresses the diagnosed linear failure, not reliable warning quality.
See [the review decisions](MAE_REVIEW_ACTIONS_V2.md) and descriptive diagnostic
report for the cadence/input-age/current-versus-target bias evidence. Next freeze
a causal residual-adaptation comparator before fitting it.

That comparator has since run as [causal adaptation v3](BRIST1D_ADAPTATION_V3.md).
Only already matured, hourly-scheduled outcomes entered bounded/shrunk personal
corrections. XGBoost pooled MAE worsened from 19.92/29.43 to 20.14/29.54;
low-target macro MAE improved from 34.46/59.80 to 33.29/59.20 but still exceeded
persistence. Ridge gains were small and did not beat unadapted XGBoost. The fixed
rule was rejected as a general replacement. All evaluation opportunities were
preserved; no population model was refitted. Twenty-five BrisT1D tests passed,
3,715,170 maturity/count/activation rows and 3,072 direct weighted-sum probes
were independently checked. Four reserved patients remain unused. A compact
sequence model with matched information and inner patient-disjoint stopping is
the next unrun hypothesis; do not keep tuning adaptation on the same outer scores.

The [matched sequence v4 study](BRIST1D_SEQUENCE_V4.md) has since completed.
One small TCN (about 10,600 parameters) with two-hour causal masked histories
and all v2 context features scored MAE 20.44/29.70; matched-input XGBoost scored
19.98/29.54 and the v2 reference 19.92/29.43. TCN mean-patient MAE was worse at
30 minutes; its small 60-minute macro advantage over matched XGBoost had an
interval crossing zero. Low-target MAE remained worse than persistence. Thirty-one
BrisT1D tests, real prefix histories, final training-only scalers, role/epoch
checks and 256 saved prediction probes per method passed. All original evaluation
arrays were preserved. No replacement was deployed. Local CPU fitting/evaluation
took 641.28 seconds with sampled peak RSS 3538.55 MiB; a cloud GPU was unnecessary.
Retain the failed architecture rather than tune more variants on outer scores.
The proposed fixed damped-trend comparator and action-response diagnostics remain
unrun; a new event task needs a separate frozen coverage/episode contract.

```powershell
python scripts/run_event_study.py --study methods_v3 --device cpu
python scripts/compare_regression_methods.py --study v3
python scripts/compare_regression_methods.py --study v4
```

Install `requirements-experiments.txt` and use the locally prepared CGMacros
source/manifest. New causal-feature tests check prefix invariance, future-value
perturbations, lag alignment, missingness, and separation of all three inner
patient roles. The full local suite passed all 56 tests, including saved-artifact
and replay checks. HTTP tests required localhost access outside the restricted
sandbox.
