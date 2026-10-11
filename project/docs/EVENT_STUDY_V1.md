# Prospective specification for the next development experiment

Written 10 October 2026 before this experiment is fitted. Machine-readable
settings are in `configs/event_study_v1.json`; the runner records their SHA256,
raw-input hashes, package versions and frozen patient roles before fitting.
Existing development results motivated this design, so this is exploratory
nested development evaluation, not a pristine external holdout.

## Task and data

Use only the 21 training and six validation patients from the existing CGMacros
manifest. Do not open the six reserved patients' sensor files or targets.
Use the existing reconstructed five-minute grid and baseline clinical profile
plus past HR. No meal amounts or unverified action timestamps are added.
Use all eligible development rows; no per-patient subsampling cap.

The binary training target is a new onset above 180 mg/dL in [t+5,t+30], with
four consecutive high samples and seven preceding normal samples, matching
the existing engineering episode definition. Current glucose must be at most
180 and past quality/warm-up gates must pass. Training labels require all nine
future grid samples through t+45; unavailable labels are excluded, never made
negative. Evaluation warning opportunities depend only on available history,
including opportunities whose outcomes are unknown.

## Independence and model comparison

Three outer patient-disjoint folds are stratified by baseline HbA1c band.
Within each outer development set, one patient per band is reserved for
threshold setting. The remaining patients undergo three-fold stratified
patient-level inner CV to select one of six fixed configurations by mean AP.
Imputation, scaling and sample weights use training patients only. Fit the
chosen model on the fitting patients, choose its warning cutoff on the three
threshold patients, and evaluate once on that outer fold's held-out patients.
Never refit after threshold setting. No evaluation labels may select a model
or cutoff. Each patient contributes to outer evaluation once.

Candidates: logistic regression C=0.1/1; histogram boosting 200 trees/15 leaves
or 400 trees/31 leaves; balanced histogram boosting 400 trees/15 leaves; and
400 Extra Trees with minimum leaf size 20. The runner defines the remaining
fixed parameters. Training weights give equal total mass per patient; the
balanced candidate additionally weights classes using its training prevalence.
Eight numeric threads bound local computation. No GPU is needed for this stage.

Fit the same selected configuration on CGM-only columns as an ablation, with
its own threshold chosen on the same threshold-setting patients. Also assess
an untrained current-plus-trailing-slope warning rule with a threshold chosen
there. This is a matched ablation, not a separately optimized best sensor model.

## Warning assessment and gate

Use the existing 60-minute cooldown and one-to-one episode matching. Report
episode recall, conservative precision (unknown alarms count against its lower
bound), false alarms per eligible monitoring day, unknown/redundant alarms and
median lead time. Eligible days count at-risk five-minute coverage, not calendar
days. Threshold selection uses 101 score quantiles plus a no-alarm threshold.
If no threshold meets the tuning constraints, preserve a diagnostic cutoff
and explicitly report the failure. Support of 30 evaluable episodes in at
least five evaluation patients is required for the pooled engineering gate.
Bootstrap patients (2,000 draws) for uncertainty, not overlapping rows.

The engineering gate is recall >=0.6, conservative precision >=0.5, false
alarms <=1 per eligible day and median lead >=10 minutes. It is an experimental
acceptance criterion, not medical clearance. Displayed scores are uncalibrated
ranking scores, never patient risk percentages. Dashboard capabilities remain
disabled regardless of the result; promotion requires a separate review.

Do not change these settings in place after reading results. Further model
families, sequence/GPU experiments, calibration, synthetic demonstrations or
final evaluation require separate versioned protocols. Native sensor timing,
assumed baseline availability and limited cohort size remain unresolved.
