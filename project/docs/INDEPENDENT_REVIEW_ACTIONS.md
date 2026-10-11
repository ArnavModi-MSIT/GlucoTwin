# Independent review findings and verified actions

Reviewed 10 October 2026: the supplied independent review document and all three
pasted reviews. Their recommendations are review evidence, not binding project
instructions. Original texts remain private; this document records adjudication.
No reserved patient evaluation or public push was performed.

## Implemented and verified

| Finding | Decision and action |
|---|---|
| Expiry test assumes monotonic uptime exceeds one hour | Confirmed fixture bug. Mock creation and expiry times explicitly, including the exact 3,600-second boundary. Service policy was correct. |
| CGMacros preparation materializes reserved targets | Confirmed risk, not demonstrated training leakage. Future default preparation opens only train/validation sensor files; a synthetic test refuses any reserved sensor read. Existing historical files/reports were not silently rewritten. |
| Missing lead-time and complete alarm accounting | Added descriptive diagnostics from frozen saved predictions, with quartiles, recall at minimum lead 10/15/20/25, verified false/unknown/redundant/total counts and unmatched alarms per eligible day. Existing results and gates remain unchanged. |
| Three-patient cutoff flag waives full support | Confirmed. New runner output explicitly states operating criteria with support waived, full-support status and cutoff patient count. A separate diagnostic explains old fields; old JSONs stay unchanged. |
| Fusion architecture selected on fused features; v3 clock mismatch | Confirmed comparison limitation. New `fair_v4` protocol independently selects each CGM / CGM+clinical / CGM+HR / fused arm using identical candidate budgets and shared temporal inputs. Machinery tested; this new onset study has not been fitted or scored. |
| Regression optimized MAE without tail guardrails | Confirmed design limitation. New v5 compares absolute, squared and pseudo-Huber losses on the same delta target and matched extended features, with Ridge as reference. Selection uses only cutoff-role patients and requires no worsening in patient-macro RMSE, P90, high/low MAE. Insufficient slice support prevents promotion. |
| Missing severe-error and glucose-slice diagnostics | Added patient-macro RMSE, bias, P90/P95/P99, >40/>60 error fractions, high/low support counts and paired patient-bootstrap intervals. Macro quantiles mean the average of patient quantiles, not pooled quantiles. Private patient summaries remain private. |
| BrisT1D asynchronous device rows and likely 15-minute CGM cadence | Confirmed locally for one pilot. New stream audit reports measured cadence, duplicate conflicts and past-only overlap, without interpolation or fitting. Six conflicting glucose timestamps are excluded from descriptive overlap rather than silently averaged. |

## New measured evidence

Frozen XGBoost v2 primary scores are unchanged. Additional diagnostics:

- Lead quartiles: 5 / 10 / 15 minutes.
- Recall with at least 10 / 15 / 20 / 25 minutes lead: 36.6% / 17.9% / 9.5% / 4.8%.
- 205 unmatched alarms / 205.23 eligible monitoring days = 1.00 unmatched/day;
  verified false rate remains 201 / 205.23 = 0.98/day. Days are at-risk coverage.
- Of 201 verified false alarms, 40 had any high reading in the next 30 minutes;
  only five had sustained highs starting in that window when the prior-normal
  requirement was omitted. These remain false under the original endpoint.
  This secondary description does not demonstrate a contaminated training label.

Local v5 loss study took 37.5 seconds. Rows, patient roles and horizons match v4.

| Method | MAE30 / RMSE30 | MAE60 / RMSE60 |
|---|---|---|
| Ridge | 12.13 / 18.12 | 17.97 / 26.40 |
| Absolute-loss delta XGBoost | 11.73 / 18.24 | 17.46 / 27.32 |
| Squared-loss delta XGBoost | 12.08 / 18.05 | 18.39 / 27.14 |
| Pseudo-Huber delta XGBoost | 11.74 / 18.07 | 17.61 / 27.35 |

Units mg/dL; pooled row MAE/RMSE shown for continuity, with separately labeled
patient-macro metrics in the JSON. The stricter, tuning-only guarded selection
retained Ridge for all three folds at both horizons. This is not proof every
candidate is inferior: tuning has only three patients and some slices lack
support. At 60 minutes the absolute-loss delta model's high-target patient-macro
MAE is 55.26 versus Ridge 49.68, despite its better overall MAE. At 30 minutes its
high/low patient-macro MAE is 29.83/37.43 versus Ridge 28.02/35.57. Typical-error
gain does not establish better extreme-glucose forecasting.

BrisT1D pilot: unambiguous glucose median/modal cadence is 15 minutes; insulin
and HR cadence is five minutes. All 18,963 retained glucose timestamps have a
recorded insulin observation within the past five minutes, and 96.1% have HR.
This is timestamp overlap, not verified prospective ingestion. No entry/upload
time is present in the schema. Missing carbohydrate rows remain unreported.
Only one participant was audited; no full-cohort import or prediction occurred.

## Claims corrected or not accepted

1. **Adding current glucose amplifies delta error:** false. With current value
   `g`, predicted change `d` and future value `y`, `(g+d)-y = d-(y-g)`.
   MAE and RMSE of reconstructed levels equal those of the corresponding change
   residuals. It is valid to report absolute-level RMSE after reconstruction.
   A synthetic test verifies this. Training a different target changes learning
   geometry; adding an extreme baseline does not multiply the residual.
2. **Absolute-target versus delta XGBoost used different losses:** false for v4;
   both used `reg:absoluteerror`. Ridge versus those models does differ in loss.
   New v5 isolates losses with a shared delta target/feature set. Causes of tail
   failures cannot be proved just by naming the loss.
3. **No balanced candidate was tested:** false. V1 includes balanced histogram
   boosting; v2 includes balanced XGBoost. V3 itself lacks balanced variants.
4. **Early long-window means use only a few initial points:** overstated. Model
   opportunities already require 24-hour warm-up, but gaps can still reduce long
   history support. Longer-window fractions exist. Coverage masking warrants a
   separately versioned sensitivity study, not rewriting v3 scores.
5. **336/366 means 30 episodes were removed by missing prior samples:** incorrect
   attribution. Both counts already satisfy the strict onset rule; the 30 are
   qualifying episodes without an eligible advance issue opportunity. Prior gaps
   can exclude other excursions before either denominator is constructed.
6. **Threshold flicker makes the existing negatives wrong:** not a demonstrated
   bug. The strict endpoint deliberately excludes these excursions; clinical
   utility may require a different task. Any alternative endpoint must be named
   and versioned separately, retaining the current primary result.
7. **Food timestamps before a rise prove causal availability:** false. They do
   not reveal when an entry/upload became available. One review's timing
   pseudocode also reverses the sign of `meal_time - rise_time`. Do not adopt it,
   or arbitrary 50%/80% proximity criteria as proof of real-time availability.
8. **Full BrisT1D work requires restricted raw data:** false. The processed open
   cohort can be audited separately; raw timestamps may still be needed for
   stronger availability claims. Its separate device rows alone do not prove
   device clock desynchronization.
9. **Patient-equal training and row-pooled reporting are inherently incorrect:**
   no. These measure different objectives. Both estimands must be labeled and
   patient-macro results shown. Independently evaluated selected-method rows are
   valid evaluation of that selection procedure; the best fixed arm chosen after
   reading evaluation results is not an independently selected final winner.
10. **Only missing meals can explain failure, or sequence models must overfit:**
    unsupported certainty. Missing interventions are plausible; unresolved timing,
    model bias, sample size, targets and selection also remain possible factors.
11. **Bootstrap within three bands containing one cutoff patient each:** resampling
    one person per band gives the same people every time, so it cannot measure
    threshold uncertainty. A valid future sensitivity protocol must vary patient
    composition and disclose weak support, without using outer outcomes to tune.
12. **Cross-fitted cutoff transfers automatically after final refitting:** not
    guaranteed. Refitting can change score scales; specify how calibration or the
    frozen prediction ensemble preserves the threshold's scoring system.

## Next work, not represented as completed

Prioritize the full processed BrisT1D audit before further large model searches.
Preserve its native modality cadence and audit participant linkage, conflicts,
gaps and conservative availability scenarios. Freeze a separate Type 1 task
before fitting. A fair onset v4 comparison is ready, but its execution and cutoff
sensitivity study are pending. The previous v1/v2/v3 and regression v3/v4 reports
remain historical exploratory evidence. Do not spend reserved test patients to
select between experiments. Operational alerts/probabilities remain disabled.

## Files and verification

- `scripts/diagnose_saved_onset.py` → `reports/onset_review_diagnostics.json`.
- `scripts/audit_brist1d_streams.py` → `reports/brist1d_stream_audit.json`.
- `scripts/compare_regression_methods.py --study v5` → v5 aggregate/private reports.
- `scripts/summarize_regression_diagnostics.py` → v5 paired diagnostic intervals.
- `configs/event_study_fair_v4.json` and tested per-arm selection in the runner.
- `src/glucotwin/regression_diagnostics.py` contains selection and metric helpers.

All 65 local tests passed, including saved artifacts, replay/HTTP boundaries,
deterministic uptime/expiry, past-only stream overlap, delta residual
identity, missing slice support, tail guards and reserved sensor exclusion. No
cloud computation, medical validation, new operational model or final test score.
The six original onset/regression result files were byte-compared with the shared
ZIP snapshot and remain unchanged. The public-file scan reviewed 138 files with
no detected credentials, raw/model artifacts, private paths or discovery wording.
Documentation for the robust objective:
[XGBoost parameters](https://xgboost.readthedocs.io/en/stable/parameter.html).
