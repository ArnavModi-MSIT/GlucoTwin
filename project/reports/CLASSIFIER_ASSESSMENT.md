# Future-high endpoint classifier assessment

Run: 8 October 2026. CPU logistic regression for **glucose exactly 60 minutes ahead >180 mg/dL**. This is not an onset-time prediction. Final test patients were not scored.

## Decision

**Keep probability display disabled.** The classifier has useful preliminary ranking performance, but separate sigmoid calibration worsens Brier score and fails the predeclared development gate in both all-endpoint and at-risk views. No probability or calibrated-risk percentage should be shown in the dashboard. Do not tune alternative calibration methods repeatedly until the same small development set yields a passing result.

Retain fused Ridge for numerical point forecasts. A derived >180 forecast flag must be labelled as a thresholded numerical forecast, not a probability. Its alert performance still requires assessment.

## Method and partition support

One fixed logistic model (C=1, max_iter=1000, natural class weights), training-only median imputation, missingness indicators and standardization. Features: reconstructed CGM, baseline clinical information and HR. Same 21 training patients as regression.

The six validation patients are split before fitting into three tuning and three calibration patients, one per HbA1c band in each. Lower ID within each band is tuning; higher is calibration. A second logistic model fits the base decision scores and labels on calibration patients only. Patient roles are stored locally and not published as record-level metadata.

| Role | Patients | Rows | High endpoints | Currently <=180 and future >180 |
|---|---:|---:|---:|---:|
| Training | 21 | 53,505 | 7,308 | 2,956 |
| Tuning assessment | 3 | 7,652 | 1,242 | 336 |
| Calibration fitting | 3 | 7,565 | 1,296 | 532 |

Calibration sample-count checks passed; this does not establish independent clinical support. Overlapping rows are not distinct adverse events, and episode counts for this particular operating point are not established. Both validation groups were previously inspected for regression, further limiting independence.

## Probability quality on tuning patients

Average precision (AP) is the scikit-learn ranking statistic, not trapezoidal PR-AUC. Report prevalence alongside it. Lower Brier score is better.

| Method | All-endpoint AP | All Brier | At-risk AP | At-risk Brier |
|---|---:|---:|---:|---:|
| Raw logistic | 0.860 | 0.0623 | 0.405 | 0.0484 |
| Sigmoid calibrated | 0.860 | 0.0785 | 0.405 | 0.0646 |
| Constant training prevalence | 0.162 | 0.1366 | 0.052 | 0.0567 |
| Current glucose >180 baseline | 0.576 | 0.0877 | 0.052 | 0.0524 |

All-endpoint positive prevalence is 16.23%; at-risk endpoint prevalence is 5.24%. The broad 0.860 AP includes already-high patients, so it must not be presented as new-high warning performance. Sigmoid calibration is monotonic and retains ranking AP here, while changing probability quality substantially.

The at-risk calibrated Brier is worse than both raw logistic and constant training prevalence. The probability gate therefore fails. Raw logistic's better Brier alone does not establish a calibrated clinical probability.

## Exploratory operating point

[Reliability figure](classifier_reliability.png) shows the raw and sigmoid-calibrated estimates in ten fixed bins. Bin counts are in the JSON report; small/empty bins and overlapping examples limit interpretation.

Threshold 0.61285 maximizes F1 on **at-risk tuning** endpoints, with the highest threshold breaking ties. It was not selected on final test. This score is optimized on the same tuning data and is optimistic:

- True positives 176, false positives 265, false negatives 160, true negatives 5,810.
- Precision **39.9%**, recall **52.4%**, F1 **0.453**.
- These are endpoint-window decisions, not distinct alerts, clinical episodes or warnings with measured lead time.

The operating point is stored for diagnosis, not approved as a production probability display. No false-alerts-per-day statistic is reported without a coverage/episode/cooldown definition.

## Verification and runtime

Training plus assessment took 1.30 seconds on CPU with a four-thread numeric-library cap. Peak memory was not instrumented for this run. Final test inference was never called.

Ten tests pass across the project, including classifier fit-role separation, training-only imputation statistics, saved classifier probability parity and explicit rejection of probability access after the failed gate. The upstream reconstructed-native uncertainty is unchanged.

Detailed reliability bins and numerical evidence: `reports/classifier_assessment.json`. Reproduce with `python scripts/train_classifier.py`, followed by `python -m unittest discover -s tests -v`. Saved model and record-level tuning predictions remain local and Git-ignored.

## Next step

Build a single-page replay dashboard around the provisional numerical forecaster, provenance, quality flags and immutable prediction/outcome history. Keep risk percentages absent. Resolve the raw-timing limitation and obtain stronger probability evidence before promoting this classifier or reporting final test results. No clinical or treatment recommendation is supported.
