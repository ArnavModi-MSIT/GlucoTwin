# CGMacros data contract

The active CGMacros models use the Dexcom track from
[PhysioNet CGMacros v1.0.0](https://physionet.org/content/cgmacros/1.0.0/), linked
to the same patient's baseline row in `bio.csv`. The population includes healthy,
prediabetic and Type 2 participants. Do not fabricate attributes or pool this
cohort with the separate Type 1 RBG cohort.

## Source admission

Published glucose samples are interpolated. Source checks select a fixed
five-minute phase that reconstructs the finite published series and has integer
lattice values. This structural rule retains 33 of 45 participants; it is not
a model-score filter. The anchors are reconstructed samples, not verified native
device logs. Excluded patients and missing observations remain excluded or missing.

## Historical and dynamic inputs

- Historical: age, recorded sex, BMI, HbA1c interpreted as percent and fasting
  glucose interpreted in mg/dL. Baseline availability before replay is assumed.
- Dynamic: Dexcom glucose and heart rate, linked by patient ID.
- Features: 22 causal CGM features, five historical fields and nine heart-rate
  summaries. No patient ID, future glucose, target or split label enters the model.

At issue time, features use only observations through that time. The first
forecast follows a 24-hour warm-up. The preceding hour must span 60 minutes,
include the current CGM reading, contain at least 10 of 13 expected five-minute
readings and have no observation gap exceeding 15 minutes. Missing heart-rate
features use training-fitted imputation and reported coverage.

## Targets and roles

Numerical Ridge predicts the supplied glucose at issue time +60 minutes;
missing exact targets are not filled. The frozen patient split contains
21 training, six validation and six reserved-test patients. Source dates are
shifted; timezone is unspecified.

The event model uses all 27 development patients in separately frozen
patient-disjoint folds, with an onset window 5–30 minutes ahead. See the
[evaluation protocol](EVALUATION_PROTOCOL.md). Reserved patient series are not
replayed or scored by the current workflows.

Raw data, patient manifests and models stay local. Respect CC BY-NC-SA 4.0 and
dataset attribution. Reconstructed values, assumed historical availability,
limited patient coverage and absent clinical validation constrain all claims.
