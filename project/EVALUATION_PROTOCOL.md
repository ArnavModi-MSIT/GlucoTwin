# GlucoTwin initial evaluation protocol

Date: 8 October 2026. Scope: exploratory CGMacros reconstructed-grid benchmark as defined in `DATA_CONTRACT.md`. No achieved scores or clinical success thresholds are specified here.

1. Load fixed patient-disjoint manifest (21 train, 6 validation, 6 test). All compared models use identical admissible rows, target definition and partitions.
2. Fit imputation, encoding, feature scaling and any feature selection on training patients only. Do not select hyperparameters or imputation behavior using final test scores.
3. Compare persistence (latest glucose), causal slope extrapolation, Ridge and optionally one bounded histogram/LightGBM model. Select regression by validation MAE in mg/dL; prefer the simpler model for practically indistinguishable results. No large tuning sweep.
4. Report MAE, RMSE, delta from persistence, patient-macro MAE and per-patient errors. Report high/low target slices with their denominators and a separate Type 2 slice. Full-data audit persistence is not the final baseline score.
5. Compare recent-CGM-only, clinical-only, CGM-plus-clinical and CGM/clinical/HR variants. This distinguishes EHR contribution from added wearable contribution. The clinical-only model is a baseline, not the production forecast. Report null/negative gains honestly.
6. Event classification is conditional on adequate distinct episodes and both classes across development partitions. Do not decide adequacy from inflated overlapping-row counts alone. First recount episodes and eligible endpoint examples after contract filtering.
7. If classifier proceeds, use logistic regression first. Partition the six validation patients deterministically into three tuning and three calibration patients, one per HbA1c band in each; persist assignments before model fitting. Calibrate only if sample support is adequate; otherwise omit probabilities. Select an operating threshold using a documented development-only criterion. Do not optimize on test.
8. Classification evidence: PR-AUC with prevalence, confusion matrix, precision/recall at frozen threshold, Brier score and calibration plot where applicable. No probability derived arbitrarily from regression values.
9. Endpoint forecasting alone does not support event onset lead time. Report alert/day burden only if a continuous observed-time denominator and explicit episode/cooldown policy are established. Otherwise mark unavailable.
10. Measure actual train time, inference latency, peak memory and artifact size on CPU. Restrict threads/tuning; no GPU dependency. Record library versions, configuration and seed.
11. Required correctness checks: exact +60 alignment; disjoint patient partitions; no future rows passed to feature builder; modifying future observations cannot change features at t under frozen reconstruction metadata; offline/replay parity; missing-history abstention.
12. Final report must distinguish data-derived descriptive audit, development scores, final holdout scores and uncertainty about reconstructed native samples. Do not claim clinical validation or pristine untouched test data after the exploratory audit.

Run final holdout once after the pipeline and validation choices are frozen. If a correctness defect requires rerunning, record the defect, repair and rerun rather than concealing test reuse.

## Endpoint classifier assessment protocol (before fitting)

Use one fixed logistic model (C=1, max_iter=1000, no class weights), train-only median imputation and standardization, CGM/clinical/HR features. For each HbA1c band, the lower validation patient ID is tuning and the higher ID is calibration. Sigmoid calibration fits a second logistic model to base-model decision scores on calibration patients only. Require at least 100 positives and negatives overall in calibration, with at least two patients each providing ten positive endpoint examples. These are engineering support checks, not sufficient evidence of clinical reliability.

Assess reliability on tuning patients, separately for all endpoints and current glucose <=180. Probability display remains disabled unless calibrated Brier score is no worse than raw logistic and better than the constant training-prevalence baseline in both views. Reliability bins must also be reported. The three-patient assessment is preliminary; independent final-test reliability is still required.

Choose the highest threshold tied for maximum F1 on at-risk tuning endpoints; report this operating point as tuning-optimized, not unbiased held-out alert performance. Do not fit or choose anything on final test patients. Both development groups were previously inspected for regression, which limits independence and must be disclosed. Future-classifier probabilities must not be presented as first-onset timing or intervention advice.
