# RBG forecasting contract v0.1

Frozen 9 October 2026 before RBG model training. Separate Type 1 benchmark; do not pool with CGMacros.

## Inputs

Use RBG-only raw DiaData SDBIII and separate demographics. All226 IDs match one demographic row. Static inputs: enrollment age and recorded sex. Assume these available at enrollment; original enrollment dates are absent. Exclude changing time-series Age, HbA1c, height/weight, diagnosis age, race, treatments and other cohorts initially. No invented profile fields. Lab and screening timing remain unverified.

## Timing and feature eligibility

The source integration sets artificial enrollment origin2024-01-01 and rounds sensor timestamps to nearest5minutes. No real calendar or timezone inference. At issue time t use only records through s=t−5minutes, allowing a conservative five-minute availability delay. This covers potential2.5minute rounding advance, not verified upload latency. Label as delayed reconstructed-grid research; native timestamp truth is unavailable.

First prediction at max(first grid timestamp,artificial origin)+24hours. Require complete60minute history span ending s; an observed CGM at s; at least10/13 observed grid readings in that span; consecutive-observation gaps<=15minutes. No interpolation/backfill or complete-follow-up statistics. Missing exact lags remain missing. Original data is preserved; no glucose-based clipping initially. Source glucose units need verification before training claims.

Features: latest available CGM; trailing15/30/60minute mean/std/min/max/count and exact-lag change; causal30minute slope; missing fraction/maxgap; enrollment age/sex. No patient IDs as features. Imputation/scaling fitted on training only.

## Targets and evaluation

Predict exact supplied readings at t+30 and t+60minutes; the latest allowed feature observation is35/65minutes before these targets. Missing targets never filled. Labels inherit source timestamp rounding uncertainty. They are CGM values, not lab blood-glucose truth.

Engineering endpoint thresholds: >180 and <70mg/dL at target time, separately assess origins outside each state. Counts are overlapping endpoints, not independent adverse episodes or onset lead times. Freeze episode and calibration protocols separately before claiming onset prediction or showing probabilities.

Compare delayed persistence, delayed slope and Ridge CGM-only versus CGM+profile at both horizons. Small boosting comparison only after baseline verification. Report MAE,RMSE, patient-macro errors, error tails, high/low and rapid-change slices, patient-level bootstrap intervals; never bootstrap overlapping rows as independent samples. Evaluation-only future changes must not become predictors. Event classifiers need prevalence,PR-AUC,sensitivity,precision and defined false-alarm burden.

## Frozen roles and CPU constraints

Seed2026; stratify recorded sex and enrollment age under45/45plus:158training,34validation,34reservedtest. No target values involved in assignment. Local manifest configs/rbg_splits.json; public aggregate report reports/rbg_contract_summary.json includes hash. Full-file prior structural audit remains retrospective.

At most2,000 eligible training rows per patient per horizon, uniform seed2026 sampling without outcome balancing. Score all eligible validation rows with row/patient weighting disclosed. Process by patient in float32, fourCPUthreads; persist compact matrices, avoid materializing all18.1M rows as features. No test prediction outputs or test performance inspection until model/event choices frozen. Patient-level quality exclusions must be predeclared and reported; do not modify split based on model results.

## Sources and limits

- https://zenodo.org/records/17285631
- https://github.com/Beyza-Cinar/DiaData/blob/main/data_integration.py
- https://public.jaeb.org/dataset/546
- https://doi.org/10.2337/dc16-2482

Data CC BY-NC4.0; preserve original study attribution and non-endorsement text. Code license separate. More participants do not guarantee better forecasts. Missing meals/insulin, rounded timestamps, assumed profile availability and one-source population limit conclusions. No clinical validation and no RBG model trained yet.

## Fixed boosting assessment — declared before fitting

One configuration, no sweep: histogram gradient boosting with absolute-error loss,120iterations,learning rate0.05,15leaves,min leaf80,L2=10,seed2026,early stopping disabled. Train CGM-only and CGM+age/sex models at30/60minutes using identical frozen sampling. Native training-based missing handling; no validation fitting. Four CPU threads.

Assess average MAE/RMSE plus high/low slices. A candidate may replace CGM-only Ridge provisionally only if its validation all-row MAE and RMSE improve and neither high nor low target MAE worsens relative to Ridge at that horizon. If both candidates pass, prefer CGM-only unless profile version improves overall MAE by at least1%. This is a development selection rule, not a clinical safety certification. Keep the original persistence comparison, and report gate failures. No repeated configuration changes based on results; reserved test patients untouched.

## Endpoint classifier assessment — frozen before fitting

Assess the 30-minute horizon only, selected after the numerical comparisons; this remains development analysis. Define high as target>180 and low as target<70. At-risk subsets have latest allowed glucose<=180 for high and>=70 for low. These definitions describe delayed-grid endpoints, not episode onset.

Split the 34 validation patients into17calibration and17assessment, seed2026 stratified by sex/age band. These patients were used for earlier forecast comparisons and are not a new untouched holdout. Keep the34reservedtestpatients unused. Train two fixed logistic models (C=1,maxiter1000,no class weights), using CGM plus enrollment age/sex and training-only imputation/scaling. Fit one sigmoid calibrator per endpoint on calibration patients only; no calibration-method search.

Calibration support: at least100positive and100negative rows and at least5patients with10positives in the calibration group. Reliability gate: calibratedBrier no worse than raw and below constant training prevalence, both overall and at-risk on assessment patients. Failure disables probability display. Even passing this development gate does not establish medical reliability or authorize clinical use.

Choose threshold on assessment at-risk rows for maximum recall subject to precision>=0.50; if no candidate satisfies, use maximumF1 as a diagnostic. Operating gate requires precision>=0.50 and recall>=0.60. Threshold-optimized results are optimistic and require later frozen test evaluation. No repeated alarm/day or independent episode claims from row-level endpoint metrics. Include latest-glucose threshold and constant-prevalence baselines. Probability/flag deployment remains disabled pending independent validation and the frozen final evaluation; save all gate results openly.

## Fixed nonlinear endpoint comparison — declared before fitting

Use one histogram gradient boosting classifier per high/low30-minute endpoint: log-loss,120iterations,learning rate0.05,15leaves,min leaf80,L2=10,seed2026,early stopping disabled,no class weighting,fourCPUthreads. Reuse existing training sample and17calibration/17assessment roles. Native missing handling; no validation-based fitting or parameter search.

Sigmoid calibration uses clipped log-odds of raw model probability (clip1e-6), fitted only on calibration patients. Apply the same support/Brier and precision>=50%,recall>=60% gates. Diagnostic thresholds are selected on assessment with the same rule; changing their numerical score value between model families is required for a fair operating comparison, not changing the precision/recall requirement. Probabilities and deployed flags remain disabled even if development gates pass until independent evaluation. Compare ranking and per-patient outcomes to logistic; do not repeat configurations based on these results.

## Episode backtest protocol — frozen before episode scoring

Use only the17existing assessment patients. This is a retrospective engineering episode definition, not clinically adjudicated events or an untouched holdout. Keep endpoint thresholds and saved classifiers fixed; no parameter/threshold optimization from episode results.

High/low qualifying onset: first >180/<70 sample after seven consecutive observed outside-state readings on the exact five-minute grid (preceding readings span30minutes), followed by four consecutive observed inside-state readings (onset to onset+15minutes). Missing readings break qualification. Shorter excursions and onsets without the prior stable observed window are excluded by definition. Define episodes by these qualifying starts, not by every abnormal row. Report exclusions/limitations and all positive episode counts; do not claim coverage of every clinical event.

Rebuild issue opportunities using past-only RBG features, five-minute delay, warm-up and quality abstention. Do not require a future target reading to generate an alarm. At-risk issue opportunities use latest allowed glucose outside the endpoint state. Alarm when fixed score meets its saved threshold; apply60minute cooldown separately per patient,event,model. Cooldown also follows a false alarm; no future-informed suppression.

An alarm matches at most one qualifying onset5–30minutes after issue; one onset matches at most one alarm. Greedy chronological matching uses first unmatched onset in that window. Primary episode denominator: qualifying onsets with at least one at-risk eligible issue opportunity in the pre-onset5–30minute window; report all qualifying onsets and evaluable subset. Compare all qualifying onset recall as a conservative secondary denominator. Report published-grid lead time and rounding uncertainty; native lead time may differ by up to2.5minutes.

For unmatched alarms, classify as false only when all nine exact future readings at+5 through+45minutes are observed and no qualifying onset lies5–30minutes ahead. The additional15minutes allows qualification of a candidate at the end of the warning window. Unmatched alarms near data gaps/endpoints are unknown, not silently negative. If an onset was already matched, additional alarms linked to it count as redundant, not new true positives. Report unknown/redundant counts and precision bounds using unknown as either true or false.

Normalize false alarms by at-risk eligible forecast time (number of opportunities*5minutes/1440), labelled eligible monitoring days rather than real-world wall-clock days. Also report per-patient macro burden, episode recall and median lead time. A persistence-state alert emits no at-risk warning by construction; do not claim that zero-warning baseline establishes usefulness. Compare logistic vsfixedboosting; probabilities/deployed flags stay disabled regardless of retrospective episode metrics. No gate relaxation or medical safety claims.
