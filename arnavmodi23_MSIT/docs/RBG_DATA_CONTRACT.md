# RBG data contract

Use the RBG-only raw subset of [DiaData v3](https://zenodo.org/records/17285631)
and its original `Demographics.csv`. The importer checks source hashes and joins
226 patient IDs to enrollment demographics. Dataset terms are CC BY-NC 4.0
with applicable original-source attribution. Do not pool these Type 1 participants
with CGMacros.

## Inputs and timing

Static inputs are enrollment age and recorded sex, assumed available before
replay. Unverified labs and treatment fields are excluded. Dynamic inputs are
CGM readings; meals and insulin doses are unavailable in this replay model.

Source timestamps are rounded to five minutes and use an artificial enrollment
origin of 2024-01-01. No real calendar or timezone is inferred. At issue time t,
only readings through t minus five minutes are available. This conservative
availability delay accounts for rounding; it is not verified device-upload latency.

Forecasts begin after a 24-hour warm-up. Require a complete preceding-hour span,
an observation at the data cutoff, at least 10 of 13 expected grid readings and
no observation gap exceeding 15 minutes. Missing readings and exact lags are
not interpolated or backfilled.

## Features, targets and roles

Twenty-two causal CGM features and enrollment age/sex enter a training-fitted
imputer, scaler and Ridge model. Forecasts target exact supplied readings at
t +30 and t +60 minutes, approximately 35/65 minutes after the latest allowed
measurement. Outcomes become visible at target time plus five minutes. CGM
targets are not laboratory blood-glucose truth.

The frozen split contains 158 training, 34 validation and 34 reserved-test patients.
Training preparation samples at most 2,000 eligible rows per patient/horizon.
Validation uses admitted rows without this cap. Reserved target matrices are
not generated. Numerical accuracy and severe-error slices are assessed separately;
there is no RBG event model in the current dashboard.

The importer streams the source archive, preserves differing existing inputs
and refuses to overwrite a different frozen split. Records, generated patient
manifests, replay caches and trusted model binaries stay local. Follow the
[preparation guide](REPRODUCTION.md) and [evaluation protocol](../EVALUATION_PROTOCOL.md).
