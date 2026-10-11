# MAE review findings and actions

Reviewed 10 October 2026: all three supplied review texts and the additional
review pasted in the message. They are external recommendations, not verified
facts or instructions to execute every proposed experiment.

## Accepted and implemented for the fixed v2 study

| Finding | Evidence and action |
|---|---|
| Unbounded action/wearable recency causes linear extrapolation | Confirmed v1 diagnostic. Cap six observation ages, mask stale latest values and add separate stale/unobserved flags. Preserve v1 files. |
| Feature repair must not remove difficult rows | V2 repairs existing v1 cached matrices. Exact timestamps, targets, patient roles, fit samples and evaluation rows are retained and checked. No admission arm is run. |
| Diagnose cadence effects | Report five-/fifteen-minute strata and low-target support. These groups contain different patients; differences do not isolate cadence as a causal effect. |
| Diagnose low-target bias using inputs known at issuance | Report signed bias and error by current-glucose bins and past slope, alongside future-target and predicted-value bins. No future bin is a gating feature. |
| Diagnose logging gaps | Use original uncapped observation-age buckets, not repaired/capped values, when reporting errors. Missing logs stay distinct from logged zeros. |
| Patient average can hide heterogeneity | Report the distribution of per-patient low-target MAE and support, without publishing linked patient records. |

The fixed engineering caps are thirty minutes for the regularly sampled insulin,
HR, steps, distance and calories streams, and 480 minutes for event-style
carbohydrate logs. They were written before the v2 fit. They express observation
freshness assumptions, not insulin/meal action duration or optimized thresholds.
They are not claimed uniquely correct. No cap sweep is performed.

CGM features remain unchanged: v1 admission already bounds current age by native
cadence plus assumed delay and bounds past-hour gaps. Historical window amounts,
counts and fractions remain unchanged. Masking a stale latest insulin record
does not set insulin activity to zero or discard a still-in-window recorded dose.
An age equal to a cap is fresh; no prior observation remains NaN with an
unobserved flag and a false stale flag.

CGM-only/profile arms reuse v1 predictions exactly. Forty-eight new fixed fits
cover the other three input arms, two model kinds, four folds and two horizons.
Adding missing/stale flags changes the feature space and XGBoost subsampling;
this experiment tests the combined repair, not a unique attribution to clipping.

## Corrected or unsupported claims in the reviews

- Ridge already has training-fitted `StandardScaler` after median imputation.
  Unequal raw-feature scaling was not a verified missing implementation step.
- The -819.1 number is a signed feature contribution to one prediction, not
  an absolute residual error. The corresponding absolute error was 1019.8.
- The source schema says timestamps are reading times or aggregation-interval
  ends; it does not establish that all meals use upload timestamps. Meal timing
  and prospective availability remain uncertain. The fifteen-minute delay is
  an assumption, not an inferred source fact.
- `insulin_age_minutes` measures age since a recorded pump interval, including
  logged zero intervals. It is not time since a positive bolus. Insulin totals
  cover the preceding five minutes; right-closed sum windows avoid including
  an extra boundary interval. Identical duplicates are reconciled and conflicts
  are excluded before v1 features and targets are prepared.
- Worse target-conditioned low MAE is a real descriptive weakness. Regression
  to the mean, missing treatment information and timing can all contribute;
  calibration bins or a low delta-variance ratio cannot prove one cause.
- Selecting a lower quantile after seeing the actual target is not a deployable
  rule. A quantile forecast may be useful for a separately defined task but is
  not automatically a fix for ordinary point MAE or calibrated warning risk.
- Sixteen patients are the independent development count, not a formally
  estimated effective sample size of all correlated windows. Repeated folds
  also share training patients; exploratory patient bootstrap intervals are
  not selection-adjusted final-test evidence.
- Neural receptive field depends on convolution count, kernel and dilation.
  Review suggestions mix numbers of blocks/dilations and cadences; a future
  model must calculate its actual time coverage explicitly.

These conclusions are based on the actual local v1 source and downloaded
official schema, which are newer than the public checkout inspected by one
reviewer. No claim of an additional label leak was substantiated by these texts.

## Deferred experiments and why

1. **Insulin/carbohydrate decay features:** do not call generic decayed pump
   totals clinical insulin-on-board. The source lacks a verified basal/bolus
   split, insulin type and patient-specific pharmacokinetics. A future separate
   arm may test clearly named recorded-action decay proxies with fixed assumptions,
   coverage indicators and matched opportunities; it has not been run.
2. **Causal residual adaptation:** next inexpensive research arm. Use only
   outcomes whose target timestamp plus assumed availability delay has matured.
   Declare update cadence, shrinkage, clipping, warm-up and adaptation-active
   fraction before testing. Overlapping residuals are highly correlated. Report
   adapted and unadapted new-patient protocols separately. Not implemented here.
3. **Damped-trend or regime blend:** plausible fixed comparator, but its damping
   or gate must be chosen without outer-patient outcomes. Not fitted here.
4. **Compact TCN/GRU:** one matched sequence experiment after the repair and
   diagnostic results; retain masks, causal timing and inner patient-disjoint
   early stopping. Architecture remains unfrozen; no neural training occurred.
5. **Event endpoint:** a separate contract is needed. "Any measured low" and
   "sustained low onset" are different tasks. Define onset/recovery, prior-normal
   rules, monitoring support, gaps, episodes and threshold selection before
   fitting. A missing future interval cannot be labeled confidently negative.
   Keep warnings disabled pending episode/lead/false-alarm evaluation.
6. **Additional datasets:** OhioT1DM, DiaTrend, HUPA-UCM and D1NAMO were proposed
   by reviewers. Their links, access, licensing and numbers have not been
   independently verified in this round. No download or cross-cohort pooling
   was performed; do not repeat their claims as confirmed dataset facts.

## Results and evidence

See [the completed v2 study](BRIST1D_STUDY_V2.md) for measured results and
limitations. The historical [handoff](MAE_REVIEW_HANDOFF.md) and
[v1 study](BRIST1D_STUDY_V1.md) retain the original failures.

Follow-up on 11 October: [causal adaptation v3](BRIST1D_ADAPTATION_V3.md) completed
the deferred residual-adaptation test. A fixed rule slightly improved some
slices but worsened overall XGBoost MAE. It was not promoted. Neural models,
new event endpoints and decay-proxy features remain unrun.

Further follow-up: [matched neural sequence v4](BRIST1D_SEQUENCE_V4.md) also
completed locally with inner patient stopping and a matched-input XGBoost
comparator. TCN did not give a convincing overall improvement and its low-target
errors remain worse than persistence. The fixed architecture was not promoted.
Event definitions, damped-trend comparison and action-decay proxies remain unrun.

Implementation: [repair and diagnostic masks](../src/glucotwin/brist1d_freshness.py),
[fixed config](../configs/brist1d_freshness_v2.json),
[runner](../scripts/run_brist1d_freshness_v2.py),
[diagnostics](../scripts/diagnose_brist1d_freshness.py),
[verification](../scripts/verify_brist1d_freshness_v2.py).
