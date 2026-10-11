# BrisT1D input comparison v1

Frozen before fitting on 10 October 2026. This is a separate Type 1
development benchmark on the open processed release. It does not pool
participants or score scales with CGMacros or RBG.

## Patient roles

Twenty downloaded sensor participants are divided into five groups of four
using seed 2026 and audited native CGM cadence only. Each group contains three
five-minute and one 15-minute participant. The final group is reserved; the
remaining sixteen people form four development evaluation folds. Each fold
fits twelve people and evaluates the other four. Every development participant
is evaluated once by a model that was not fitted on that participant.

No prediction outcomes, low/high event prevalence, model scores or intervention
coverage select roles. The whole cohort was inspected for source quality before
these roles existed. Reserved sensors are not opened again by preparation or
training, and no reserved feature matrices or predictions are generated.
Linked assignments/profiles/source hashes remain private. Repeating the freeze
refuses a differing protocol or source manifest.

## Timing and measured targets

Declared retrospective availability assumptions are five minutes for CGM,
insulin and wearable observations, and fifteen minutes for recorded carbs.
The source does not contain upload/entry timestamps establishing those delays.
Clinical questionnaire fields are assumed available at baseline. These are
assumptions for the experiment, not verified real-time ingestion behavior.

For each reconciled glucose observation, schedule one forecast at its timestamp
plus `ceil(CGM delay / native cadence) * native cadence`: five minutes for a
five-minute CGM and fifteen minutes for a 15-minute CGM. This schedule is
causally anchored to a reading already assumed available when the forecast is
issued. It is a reading-triggered research schedule, not continuous monitoring
during outages.

At issue time `t`, a channel contributes only source timestamps at or before
`t - channel_delay`. A target is the exact published glucose observation at
`t + 30 minutes` or `t + 60 minutes`, converted from mmol/L using 18.0182.
It is **not** a target at the latest reading time plus the horizon. For example,
with 15-minute CGM, a 12:00 reading schedules an issue at 12:15; the 30-minute
target is 12:45. A 12:15 reading remains unavailable until 12:20 under the
five-minute delay assumption. Missing targets are not interpolated.

No source grid is resampled, and no gaps use future-valued interpolation. This
preserves the processed release as supplied; the audit does not establish the
original raw-device preprocessing history. Cadence is frozen from the audit,
not recalculated using future waveform values during replay.

## Features and admission

Shared CGM inputs include current value/age/cadence, past lags/changes, clock
features and 15/30/60/120-minute time-window summaries. Admission requires
two hours of source warm-up, at least 80% of expected inclusive past-hour
observations, no observed past-hour gap exceeding two cadence intervals and
current age no greater than native cadence plus CGM delay. All arms use the
same admission and measured-target rows at each horizon.

The arms progressively include:

1. CGM and shared source-clock/cadence inputs.
2. Add linked age, self-reported gender categories and exact-duration/missingness.
3. Add insulin observations, ages, past recorded dose sums and coverage.
4. Add recorded carbs, ages, logged sums/counts over 1/2/4/8 hours.
5. Add HR, steps, distance and calories with explicit observation coverage.

Dose sums are sums of recorded five-minute interval amounts, not inferred
insulin on board. Absent dose/food streams remain missing; real zero doses
remain zero. A zero logged-meal count means no source entries in that window,
not proof of no food consumption. Train-fitted median imputation with indicators
is model preprocessing, not reconstruction of the raw observations. Non-binary
gender is preserved; biological sex, genetics and unavailable labs are not
invented. Rows without a device label are excluded before feature/label
construction, resolving the single such row found during source audit.

## Fixed CPU comparison

Two fixed methods are evaluated for each arm/horizon/fold: median-imputed,
scaled Ridge alpha 10, and absolute-error XGBoost predicting future glucose
minus current glucose with 300 trees/depth 3. Parameters are in the
[frozen configuration](../configs/brist1d_contract_v1.json). No parameter sweep,
random-row validation, early-stop tuning on evaluation patients or post-hoc
winner deployment is performed.

Fitting uses at most 4,000 deterministically sampled rows per training person,
with equal total weight per person. Evaluation uses all admitted measured
targets for the four held-out development people, identically for every arm.
Preprocessing is fitted on training patients only. Source/cache hashes bind
the inputs. No patient ID is a model feature.

Report pooled MAE/RMSE, patient-macro MAE/RMSE and P95, high/low support and MAE,
error fractions above 40/60 mg/dL, and paired patient-bootstrap differences.
Patient-macro quantiles are averages of patient quantiles, not pooled quantiles.
The 2,000-repetition intervals are exploratory development uncertainty, not
clinical certification or selection-adjusted final-test evidence. Small patient
counts and overlapping forecast windows limit inference.

Lower MAE alone does not establish stronger adverse-event warnings. No new
event classifier, operational alerts, calibration result or medical reliability
claim follows from this regression study. Existing dashboard models are unchanged.

## Reproduce

From `project/`, after the full source audit and experimental dependencies:

```powershell
python scripts/run_brist1d_study.py --action freeze
python scripts/run_brist1d_study.py --action prepare
python scripts/run_brist1d_study.py --action train
python -m unittest discover -s tests -p "test_brist1d*" -v
```

Preparation opens only sixteen development sensors. Private caches, roles,
predictions and fold models remain excluded from Git. Public artifacts are
the configuration and aggregate role/preparation/score reports.
