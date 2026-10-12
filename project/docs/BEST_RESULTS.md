# Best-results checkpoint

Recorded 12 October 2026. This register preserves the working selection and
notable experimental results without replacing the application with a model
chosen on one attractive metric. All results are development evaluations;
reserved-test performance remains unscored. Synthetic-demo scores are excluded.

The [high-event diagnostic audit](HIGH_EVENT_AUDIT.md) leaves this selection and
all scores unchanged; its cutoff-patient counts are not a new best result.

## Working application

| Path | Model | Reported result | Status |
|---|---|---|---|
| CGMacros numerical | Clinical + CGM + HR Ridge | Row-weighted MAE60: 19.00 mg/dL; persistence 19.99 | Active |
| RBG numerical | Enrollment profile + CGM Ridge | Row-weighted MAE30/60: 17.59 / 28.89; persistence 20.71 / 32.53 | Active |
| CGMacros high onset | Fused XGBoost, frozen v2 | 229/336 episodes detected; recall 68.2%, conservative precision 52.8%, false alarms 0.98/eligible day, median lead 10 min | Active research panel |

The high-event model is the current adverse-event demonstration. Recall requiring
at least ten minutes' warning is 36.6%. Cutoff folds did not consistently meet
operating criteria; useful fusion gain remains uncertain. Low-target numerical
errors remain a weakness. See [full active results](RESULTS.md).

## Retained experimental candidates

| Experiment | Result retained | Why it is not the active model |
|---|---|---|
| CGMacros absolute-loss delta XGBoost | Row-pooled MAE30/60: 11.73 / 17.46 mg/dL; matched Ridge 12.13 / 17.97 | Higher RMSE than matched Ridge; paired patient MAE intervals include zero; some high/low slices worsen |
| DCLP3 v2 CGM-only XGBoost | Patient-macro MAE30/60: 17.53 / 27.47; persistence 20.92 / 32.32 | Low-target errors worse than persistence; no demonstrated warning endpoint; separate cohort |
| RBG low-onset GRU v2, CGM-only | Recall 69.8%, conservative precision 34.5%, false alarms 0.862/eligible day, median lead 10 min | Highest recall among the listed low-onset comparisons, but full warning gate fails |
| RBG low-onset GRU v2, profile-fused | Recall 61.6%, conservative precision 37.0%, false alarms 0.676/eligible day, median lead 10 min | Better precision trade-off than the listed CGM-only arm, but full warning gate fails |

CGMacros regression experiments used 27 development patients with patient-disjoint
selection/evaluation; the active numerical benchmark uses 21 training and six
validation patients. DCLP3 used 134 development patients across four outer folds.
Low-onset GRU used 120 fitting, 19 selection, 19 cutoff and 34 assessment patients,
with 5,149 evaluable assessment episodes. The assessment cohort was previously
examined. GRU epochs were selected on separate selection patients (epoch 24 for
both arms), not on assessment performance.

**These rows are not a shared leaderboard.** Cohorts, horizons, availability
delays, weighting and endpoints differ. Lowest pooled MAE does not establish the
best patient-level performance or reliable event warnings.

## Preservation and promotion

- GitHub preserves application code, active training workflows, the active
  aggregate event report, and this compact results register. Named Git tags mark
  tested working checkpoints; later work must not move those tags.
- [Source fingerprints](../reports/best_results_sources.json) identify the local
  reports used for this register. Fingerprints are integrity records, not copies
  of those reports or fitted models.
- Historical experiment workflows, private reports, raw data and fitted model
  binaries remain local and ignored. This public checkpoint is not an off-device
  backup of those files.
- Promote a candidate only after matched cohort/row comparisons, error-slice and
  event checks, causal replay parity, and updated documentation. Preserve the
  earlier version instead of overwriting its evidence.
- Commit and push tested working milestones and verified result updates. Do not
  publish raw patient records, credentials or unverified performance claims.
