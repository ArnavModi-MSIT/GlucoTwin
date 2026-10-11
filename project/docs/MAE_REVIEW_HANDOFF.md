# GlucoTwin: prediction experiments and review request

Updated: 11 October 2026. This document is self-contained so it can be shared
with an independent reviewer. Completed experiments and proposed experiments
are explicitly separated. All errors below are in mg/dL.

The new [DCLP3 fixed CPU comparison](DCLP3_STUDY_V2.md) is complete. It uses
134 development participants and 34 reserved participants, with four
patient-disjoint folds. CGM-only XGBoost pooled MAE is 17.44/27.32 and
participant MAE is 17.53/27.47, versus persistence participant MAE 20.92/32.32.
Clinical-profile additions show no convincing overall gain. In a separate,
matched 100-person pump subset, fully fused XGBoost participant MAE is
17.19/26.73; adding insulin to clinical + CGM improves it by only 0.105/0.222.
Full-cohort XGBoost low-target MAE is 29.13/54.31 versus persistence 26.68/50.04.
Larger data has not resolved the warning problem; comparisons to BrisT1D are
not controlled because cohorts and timing differ. Meal logs are absent.
All 80 artifacts/preprocessors, 1,280 inference probes and aggregate/paired
scores were verified. Runtime 2,206.14 seconds, sampled peak RSS 4,509.82 MiB.
No reserved scoring, dashboard replacement, GPU use or alert enablement.

Follow-up after the external reviews: the planned feature-only freshness repair
has now been implemented and tested as [v2](BRIST1D_STUDY_V2.md). Full-input Ridge
MAE improved from 37.47/60.99 to 20.87/30.96; XGBoost barely changed from
19.92/29.46 to 19.92/29.43. Low-target XGBoost errors still exceed persistence.
V1 evidence below is retained. In the original plan below, freshness repair is
now complete. Adaptation and neural follow-ups are recorded below; a new event
endpoint remains unrun.
See [review adjudication](MAE_REVIEW_ACTIONS_V2.md) for accepted and corrected claims.

The subsequent [causal adaptation v3](BRIST1D_ADAPTATION_V3.md) has also completed.
One fixed hourly-update, bounded residual rule increased XGBoost MAE from
19.92/29.43 to 20.14/29.54, despite modest low/high slice improvements. Low-target
MAE still exceeded persistence. The rule was rejected as a general replacement.
The original proposed adaptation below is now a completed failed experiment;
At that stage neural models and new event endpoints remained unrun. Twenty-five BrisT1D tests
and independent maturity/weighted-sum checks passed. No reserved evaluation.

The [matched TCN sequence study v4](BRIST1D_SEQUENCE_V4.md) has now completed too.
TCN pooled MAE was 20.44/29.70 versus matched-information XGBoost 19.98/29.54 and
the existing v2 reference 19.92/29.43. Low-target macro MAE was 33.93/59.72,
still worse than persistence 29.79/54.30. This fixed architecture is not promoted.
One seed/architecture, inner patient-disjoint early stopping and identical
evaluation rows were used. Thirty-one tests and saved-model/scaler/prefix checks
passed; reserved patients remain unscored. New event endpoints remain unrun.

## What we are building and what is currently wrong

GlucoTwin is a patient research dashboard with glucose replay and fixed future
forecasts. The intended model combines historical patient information with
time-series sensor/action inputs and eventually predicts adverse glucose events
in advance. Numerical endpoint forecasts are implemented, but reliable event
prediction has not been achieved. Operational alerts and risk probabilities
remain disabled. Better overall MAE alone will not solve that problem.

The dashboard still uses saved Ridge models for its separate RBG and CGMacros
cohorts. The newer BrisT1D study is an offline experiment; it has not replaced
the dashboard model. Do not interpret dashboard session MAE as a cohort benchmark.

We want to improve prediction quality before adding more product features.
Local hardware has 32 GB RAM; local GPU capability is not established here.
Run experiments locally first. Kaggle/Colab GPUs are available if local training
struggles. One compact neural comparison has now completed locally; see v4 above.

## How to interpret the evidence

- Persistence predicts the latest available glucose at the future endpoint.
- Row-pooled MAE gives each eligible row equal weight. Patient-macro MAE averages
  individual patient MAEs. These are different estimands.
- Low/high slices below use actual future glucose below 70 / above 180 mg/dL.
- Patient-macro P95 means the average of individual patient error quantiles,
  not the quantile of all pooled errors.
- Numerous overlapping windows do not constitute numerous independent patients.
- Scores from different datasets, patient splits, availability assumptions or
  horizons cannot establish a controlled improvement over one another.
- Development results have been inspected repeatedly. They are exploratory;
  reserved patients must remain untouched until the final protocol is frozen.

## Completed: CGMacros model and method changes

This cohort combines clinical profile fields, CGM and heart rate. Its published
CGM samples are reconstructed, limiting prospective claims. The regression
comparison used 27 development patients and excluded six reserved patients.
Selection used separate patients within development folds; evaluation patients
were not used to select methods. Training gave each patient equal total weight.

We tried the original Ridge features, longer-history nonlinear methods,
XGBoost predicting absolute glucose, XGBoost predicting glucose change, and
selection between candidate methods. Extended features included glucose lags,
2/4/24-hour summaries, acceleration, deviation from a trailing daily mean and
clock features. HistGradientBoosting was also included in the method study;
see the aggregate reports for its detailed results.

| Method | MAE30 | MAE60 | RMSE30 | RMSE60 |
|---|---:|---:|---:|---:|
| Persistence | 13.26 | 19.97 | 20.59 | 30.71 |
| Original-feature Ridge | 12.13 | 17.97 | 18.12 | 26.40 |
| Longer-history XGBoost | 12.07 | 18.14 | 18.86 | 28.47 |
| Absolute-loss delta XGBoost | 11.73 | 17.46 | 18.24 | 27.32 |
| Separately selected method, v4 | 11.91 | 17.77 | 18.35 | 27.28 |

These are row-pooled errors. Delta XGBoost lowered MAE but worsened RMSE versus
Ridge. Paired patient-mean MAE difference intervals included zero at both
horizons. This was insufficient evidence to replace the dashboard model.

### Completed: changing the regression loss, v5

The next experiment held the delta target and extended features fixed while
comparing absolute, squared and pseudo-Huber losses.

| Method | MAE30 | MAE60 | RMSE30 | RMSE60 |
|---|---:|---:|---:|---:|
| Ridge reference | 12.13 | 17.97 | 18.12 | 26.40 |
| Absolute-loss delta XGBoost | 11.73 | 17.46 | 18.24 | 27.32 |
| Squared-loss delta XGBoost | 12.08 | 18.39 | 18.05 | 27.14 |
| Pseudo-Huber delta XGBoost | 11.74 | 17.61 | 18.07 | 27.35 |

Tuning-only guardrails required no worsening in patient-macro RMSE, P90 error,
high-target MAE or low-target MAE, with minimum slice support. Guarded selection
retained Ridge at all three folds and both horizons. Small tuning groups and
missing slice support also limited promotion; this is not proof that every
nonlinear model is universally worse.

At 60 minutes, absolute-loss delta XGBoost high-target patient-macro MAE was
55.26 versus Ridge 49.68 despite its lower overall MAE. At 30 minutes its
high/low MAE was 29.83/37.43 versus Ridge 28.02/35.57. Changing loss has therefore
already been tried; it is not an unexplored guaranteed fix.

## Completed: RBG reference and boosting experiment

RBG has a much larger Type 1 cohort, with a historical split of 158 fitting,
34 validation and 34 reserved patients. Its dashboard forecasting is primarily
CGM based; displayed profile context should not be confused with proven
predictive benefit from clinical fusion.

Ridge validation MAE was 17.59 at 30 minutes and 28.89 at 60 minutes, versus
persistence 20.71/32.53. Its low-target MAE was 20.26/44.26 versus persistence
19.76/36.98. A boosting comparison was run, but lower typical errors did not
justify replacement because errors in important glucose slices deteriorated.
Detailed slice support and scores are retained in the RBG JSON reports.

## Completed: BrisT1D data audit and fixed CPU study v1

We changed inputs by auditing a separate open Type 1 cohort with linked
demographics, CGM, insulin, logged carbohydrates, heart rate, steps, distance
and calories. We did not blindly pool it with CGMacros/RBG.

Sources:

- [Original release](https://data.bris.ac.uk/data/dataset/33z5jc8fa6tob21ptrugzqog08)
- [Source schema](https://data.bris.ac.uk/datasets/33z5jc8fa6tob21ptrugzqog08/README.txt)
- [Processed release listing](https://data.bris.ac.uk/data/dataset/8dfdea4e24c4b90e6f044cadf612c477)

The downloaded open processed release has 20 sensor participants, 2,875,613
source rows and 847,956 reconciled glucose observations in the descriptive
audit. Five people have 15-minute CGM cadence; fifteen have five-minute cadence.
Devices occupy asynchronous rows. Insulin/HR overlap within the preceding five
minutes is 80.66%/59.00%; one participant has no insulin stream. Long outages,
conflicting duplicate values and incomplete meal logging matter.

The cohort is young (18–26 years). Demographics include age, self-reported
gender and diabetes duration; there are no invented lab results or genetic
fields. Unknown duration remains unknown. Missing carbohydrate entries are
unreported, not evidence of zero food intake. Source timestamps do not provide
meal-entry/upload availability. The processed source's upstream handling is
not independently established by our own no-interpolation label rule.

### Frozen evaluation contract

- Sixteen development patients in four patient-disjoint folds: twelve fit and
  four evaluate per fold; every development patient is evaluated once per arm.
- Four additional patients reserved. The initial descriptive source audit
  inspected all twenty before freezing roles; afterward reserved sensor files
  were not prepared or scored. They are not claimed to be wholly uninspected.
- Roles are cadence-stratified and fixed by seed 2026, not selected from outcomes.
- Assumed delays: CGM/insulin/wearables five minutes, logged carbs fifteen minutes.
  Profile availability is assumed at baseline. These are retrospective
  assumptions, not verified prospective ingestion times.
- Each reconciled glucose reading schedules an issue at its timestamp plus the
  CGM delay rounded up to native cadence: five or fifteen minutes. This is
  reading-triggered issuance, not continuous issuance during outages.
- Targets are exact measured glucose at **issue time + 30/60 minutes**. Missing
  targets stay missing; we do not interpolate labels.
- Two-hour warm-up, at least 80% past-hour CGM count, bounded past-hour gaps and
  a current-reading age admission rule apply before scoring.
- Five nested input arms share identical evaluation rows and clock/cadence
  features: CGM; CGM+profile; +insulin; +carbs; full wearable fusion.
- Training-only median imputation and missing indicators; actual logged zeros
  are preserved. Full fusion has 140 engineered features.
- Fixed Ridge alpha 10 and delta XGBoost with absolute loss, 300 trees, depth 3,
  learning rate 0.03, CPU histogram training, eight threads. No tuning sweep.
- At most 4,000 deterministic training rows per patient; equal total patient
  training weight. All eligible evaluation rows are scored.

### Results: all input arms, including failures

| Method / inputs | MAE30 | MAE60 | RMSE30 | RMSE60 |
|---|---:|---:|---:|---:|
| Persistence | 23.36 | 34.76 | 32.47 | 47.41 |
| Ridge / CGM | 20.70 | 30.72 | 28.47 | 41.22 |
| Ridge / CGM+profile | 20.76 | 30.85 | 28.51 | 41.29 |
| Ridge / +insulin | 20.86 | 31.16 | 28.57 | 41.52 |
| Ridge / +insulin+carbs | 38.88 | 62.44 | 85.66 | 143.11 |
| Ridge / full fusion | 37.47 | 60.99 | 80.51 | 137.94 |
| Delta XGBoost / CGM | 20.10 | 29.62 | 28.14 | 40.49 |
| Delta XGBoost / CGM+profile | 20.07 | 29.63 | 28.07 | 40.42 |
| Delta XGBoost / +insulin | 19.97 | 29.59 | 27.93 | 40.44 |
| Delta XGBoost / +insulin+carbs | 19.94 | 29.57 | 27.88 | 40.45 |
| Delta XGBoost / full fusion | 19.92 | 29.46 | 27.85 | 40.25 |

Row-pooled errors cover 625,755 exact 30-minute and 612,635 exact 60-minute
targets, from only sixteen independent development patients.

| Method | Patient-macro low MAE30 / MAE60 | High MAE30 / MAE60 | P95 error30 / error60 |
|---|---:|---:|---:|
| Persistence | 29.79 / 54.30 | 31.48 / 47.98 | 70.38 / 100.79 |
| Ridge / CGM+profile | 34.16 / 64.63 | 28.00 / 44.61 | 61.17 / 86.55 |
| Delta XGBoost / CGM+profile | 34.90 / 60.32 | 28.60 / 46.31 | 61.11 / 85.85 |
| Delta XGBoost / full fusion | 34.25 / 59.71 | 28.37 / 46.19 | 60.65 / 85.43 |

Full fusion versus CGM/profile XGBoost improved mean patient MAE by 0.186/0.229
at 30/60 minutes; exploratory paired bootstrap intervals were
[-0.251, -0.108] / [-0.402, -0.066]. These are small gains. High/low difference
intervals included zero at both horizons, and the 60-minute P95 interval also
included zero. All learned methods in this table were worse than persistence
on low-target MAE. No reliable advance event-warning improvement was shown.

### Confirmed failure mechanism and verification boundary

The worst saved full-input Ridge 60-minute prediction had 1019.8 absolute error.
Its `insulin_age_minutes` term alone contributed -819.1 to the prediction.
V1 permits unbounded last-observation ages; long outages can produce extreme
linear extrapolation. Adding inputs changes fitted coefficients; this diagnosis
does not establish that carbohydrate age alone caused the failure or explain
every bad prediction. Preserve this failed experiment rather than rewrite it.

Training/evaluation completed locally in 151.45 seconds, with sampled peak RSS
1027.07 MiB. Eighty fits were fixed model/input/fold/horizon combinations, not
eighty tuned configurations. GPU execution was unnecessary.

Fourteen BrisT1D synthetic tests passed. Real-source probes checked causal prefix
parity and exact targets at both native cadences. All eighty saved fold models
reproduced eight checked held-out probes each. Held-out arrays, aggregate
arithmetic and reserved-patient exclusion were checked. These are correctness
checks, not proof of generalization or prospective reliability.

## Related event prediction work already tried

Numerical endpoint MAE and episode-warning quality are different tasks.
CGMacros onset XGBoost v2 detected 229/336 development episodes: recall 68.2%,
precision 52.8%, 0.98 verified false alarms per eligible day, median lead ten
minutes. Support/operating requirements were not fully met.

A longer-history/method-selection v3 detected 173/336: recall 51.5%, precision
53.9%, 0.72 false alarms/day and the same median lead. Reduced false alarms
came with many missed events; v3 was rejected as an overall improvement.
Its CGM versus fused clock-feature mismatch prevents attribution solely to
clinical fusion. Fairer onset comparison machinery exists, but that comparison
has not been fitted or scored. Do not treat these as BrisT1D or active dashboard
event-model results.

## Original proposed experiments — current status updated above

### 1. Fix freshness handling in a new BrisT1D version

Bound recency features, represent long outages explicitly and mask stale last
values using declared channel-specific freshness rules. Fit transformations
on training data only where applicable. Separate a feature-repair comparison
from a change in row admission so improvements cannot be manufactured by
dropping difficult evaluation rows. Keep v1 as an immutable reference.

Compare repaired Ridge and XGBoost on the same folds, issue schedule, targets
and shared evaluation opportunities. Add tests around stale values, missing
actions, native cadences and future exclusion. Freshness limits are not yet
chosen; reviewer input is useful here.

### 2. Test causal patient adaptation

Compare a population model with a simple patient-specific residual correction
or calibration using only outcomes already available at each issue time.
For a prediction issued at t with horizon h, its outcome can enter adaptation
only after t+h plus the assumed target availability delay.

This is an online-adaptation research track: it uses past data from the new
patient, unlike a completely unadapted new-patient model. Report them separately,
declare warm-up/calibration requirements and never use a whole patient's future
record to estimate a personal correction. The subsequent fixed v3 adaptation
experiment is now complete and unsuccessful as a general replacement.

### 3. Test a compact neural sequence model

Start with a small TCN (Temporal Convolutional Network); a small GRU is an
alternative, not a commitment to a large architecture sweep. Proposed inputs
are several hours of past glucose, insulin, meal and wearable observations,
with missingness/freshness masks and a separate static-profile branch.

Hypothesis: an ordered sequence may retain rise/fall and delayed action-response
patterns lost in window summaries. This is a hypothesis, not an established
explanation for current errors. Sixteen development patients create substantial
overfitting risk despite many windows.

Sequence encoding, history length, loss and network size are not frozen yet.
Native five-/fifteen-minute cadence needs an explicit causal representation;
avoid interpolating through outages or generating labels. Match raw information
availability with tabular comparators. Use training-only scaling, small capacity,
regularization and early stopping on patient-disjoint inner development splits.
Outer evaluation patients must not choose epochs or architecture. Retain four
reserved patients and begin locally; move to a cloud GPU only if needed.

External evidence is mixed: [GlucoBench](https://arxiv.org/html/2410.05780v1)
found simple ARIMA/linear models best on three of five datasets and deep models
best on two. Its trajectory targets, splits and aggregation differ from ours;
its MAE table is not directly comparable with our endpoint scores.

### 4. Decide from matched error and event evidence

Evaluate row-pooled and patient-macro MAE/RMSE, high/low slices with support,
bias, patient error quantiles, error fractions above 40/60 and paired patient
differences. Preserve per-fold outcomes and failed candidates. Do not promote
solely on the best pooled MAE or a tiny statistically nonzero difference.

Once a forecast method earns a credible improvement, separately assess a frozen
event endpoint with episode recall, precision, false alarms per eligible day
and useful lead time. Do not enable alerts merely by thresholding a forecast
without episode evaluation. No numerical performance target is promised.

## Questions for an independent reviewer

1. What concrete data/label/availability errors can you identify in the linked
   implementation, beyond suggestions to tune parameters?
2. What bounded-age and stale-value rules would you use, and how would you
   compare them without selectively removing difficult rows?
3. Is a small TCN/GRU justified here? Specify a modest architecture, causal
   sequence encoding and patient-disjoint stopping/selection protocol.
4. What adaptation method can learn safely from only already matured outcomes?
5. Why might low-target errors remain worse than persistence, and what measured
   diagnostic would distinguish competing explanations?
6. What additional open dataset would address a specific weakness? Provide its
   direct source/license, linked inputs, patient count and availability caveats.
7. What is the smallest prioritized set of experiments likely to change the
   decision? Distinguish verified bugs, hypotheses and expected tradeoffs.

Please do not recommend random window train/test splits, label interpolation,
treating absent meals as zero, tuning on reserved patients, mixing cohorts to
claim lower MAE, or presenting already completed loss/history changes as new.

## Supporting code and aggregate evidence

Repository: [GlucoTwin](https://github.com/ArnavModi-MSIT/GlucoTwin).
The local work described here may be newer than the public repository; a public
checkout alone may not contain the latest experiment. Request the corresponding
source/report files when doing a code-level review. Raw data, patient-linked
outputs and model binaries are intentionally not embedded in this document.

- [Earlier method history](SCORE_IMPROVEMENT.md)
- [Independent review adjudication and v5 loss results](INDEPENDENT_REVIEW_ACTIONS.md)
- [CGMacros v3](../reports/regression_methods_v3.json),
  [v4](../reports/regression_methods_v4.json),
  [v4 paired diagnostics](../reports/regression_methods_v4_paired.json),
  [v5](../reports/regression_methods_v5.json),
  [v5 paired diagnostics](../reports/regression_methods_v5_paired.json)
- [CGMacros comparison runner](../scripts/compare_regression_methods.py)
- [RBG baseline](../reports/rbg_baseline_validation.json),
  [RBG boosting](../reports/rbg_boosting_validation.json)
- [BrisT1D source audit](BRIST1D_COHORT_AUDIT.md),
  [data contract](BRIST1D_DATA_CONTRACT.md),
  [fixed configuration](../configs/brist1d_contract_v1.json)
- [BrisT1D full study](BRIST1D_STUDY_V1.md),
  [aggregate results](../reports/brist1d_study_v1.json),
  [preparation counts](../reports/brist1d_preparation.json),
  [report-bound checks](../reports/brist1d_study_v1_checks.json)
- [BrisT1D feature implementation](../src/glucotwin/brist1d.py),
  [study runner](../scripts/run_brist1d_study.py),
  [verification runner](../scripts/verify_brist1d_study.py),
  [feature tests](../tests/test_brist1d_features.py)

Run commands from the `project` directory with the documented experiment
dependencies and local datasets. Reproduction of training requires private
local data/role manifests; the aggregate reports alone are not training inputs.
