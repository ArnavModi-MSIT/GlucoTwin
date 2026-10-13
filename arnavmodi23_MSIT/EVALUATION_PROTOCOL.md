# Evaluation protocol

This document describes the active model workflows. Results are developmental,
not clinical validation. Patient identifiers link inputs and partitions; they
are not model features. Reserved-test predictions remain unscored.

## Numerical forecasting

CGMacros uses a frozen 21/6/6 training/validation/reserved split; RBG uses
158/34/34. Each source has its own timing and admission contract. Training-only
imputation and scaling feed fused Ridge models with alpha 10. Numerical targets
are observed CGM readings at the specified horizon; missing targets are not
interpolated. Persistence uses the latest available glucose.

Report MAE and RMSE in mg/dL, patient-level summaries and low/high-target errors
with denominators. Overlapping forecast windows are not independent patient
samples. A lower overall MAE does not establish better low-glucose performance.
See [CGMacros data](DATA_CONTRACT.md), [RBG data](docs/RBG_DATA_CONTRACT.md) and
[current results](docs/RESULTS.md).

## Advance-event prediction

Use the unchanged [frozen event configuration](configs/event_study_gpu_v2.json).
A new high onset requires four consecutive five-minute readings above 180 mg/dL
after seven at or below 180. The warning window is 5–30 minutes; label confirmation
extends through issue time +45 minutes. Future readings construct evaluation
labels only and never prediction features. Unknown labels are excluded from
training; gaps do not become fabricated negative outcomes.

The 27 CGMacros development patients form three outer folds. Each fold separates
15 fitting, three cutoff-setting and nine evaluation patients. Inner patient-level
validation selects among the fixed XGBoost configurations. Cutoffs are selected
on the separate cutoff patients and then frozen before outer evaluation. Feature
processing is fitted on fitting patients only. Research flags use a 60-minute cooldown.

Report episode recall, conservative precision, false alarms per eligible monitoring
day, useful lead-time recall and patient-bootstrap uncertainty. The selected
evaluation fold excludes a replay patient from fitting and cutoff selection.
Repeated development-data use and inconsistent cutoff performance restrict the
conclusion. Scores are uncalibrated; no operational alerts or treatment decisions
are approved. Make a written final model/cutoff decision before reserved evaluation.
