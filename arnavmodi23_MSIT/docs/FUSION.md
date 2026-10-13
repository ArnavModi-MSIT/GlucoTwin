# Historical and sensor fusion

Both replay paths now ingest linked historical and dynamic data in the fitted
model, rather than merely displaying a profile beside a sensor-only forecast.

| Path | Historical stream | Dynamic stream | Forecast |
|---|---|---|---|
| CGMacros | Age, recorded sex, BMI, baseline HbA1c, fasting glucose | 22 CGM features and nine heart-rate features | +60 minutes |
| RBG | Enrollment age and recorded sex | 22 causal CGM features | +30/+60 minutes |

Patient IDs link each profile to its own time series. Static values are
broadcast into each eligible feature row. The same training-fitted imputer,
scaler and Ridge model consume the combined feature vector at inference.
RBG receives only sensor measurements through issue time minus five minutes.
Each issued forecast reports its exact `model_inputs` in the API.

The RBG replay loads existing `ridge_cgm_profile` models trained on the original
158 training patients. The selection configuration identifies this active
profile-fused model. No new fitting or reserved-test scoring is performed
during replay.

Fusion is an implementation fact, not evidence of useful clinical gain.
RBG age/sex produced essentially no average improvement and slightly worsened
low-target error. CGMacros showed a small development gain from profile/HR
features, with only six validation patients and worse low-target errors.

Neither dataset is a complete hospital EHR. Historical availability is assumed;
unverified RBG labs are excluded. No arbitrary synthetic labs are attached to
real patients. Adverse-event success, calibration and independent validation
remain separate unresolved requirements; alerts stay disabled.
