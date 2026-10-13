# Current model results

The dashboard serves fused Ridge numerical forecasts and an optional fused
XGBoost high-glucose onset model. Results below are development evidence;
reserved-test performance has not been evaluated. The cohorts have different
timing and populations and are not directly comparable.

## Numerical forecasts

Mean absolute error (MAE), in mg/dL; lower is better.

| Cohort | Horizon | Persistence | Profile-fused Ridge |
|---|---|---:|---:|
| CGMacros | 60 minutes | 19.99 | 19.00 |
| RBG | 30 minutes | 20.71 | 17.59 |
| RBG | 60 minutes | 32.53 | 28.89 |

CGMacros uses 21 training, six validation and six reserved patients. The model
ingests age, recorded sex, BMI, HbA1c, fasting glucose, CGM history and heart rate.
RBG uses 158 training, 34 validation and 34 reserved patients; enrollment age/sex
and CGM history enter its model. RBG profile-fused values have the same rounded
MAEs as the original CGM-only reference, with essentially no age/sex gain.

These are overall errors, not clinical tolerances. Individual errors can be
larger, and low-target errors can exceed persistence. CGMacros samples are
reconstructed and historical profile availability is assumed. RBG has a
five-minute measurement-availability delay, making lookahead from the latest
reading approximately 35/65 minutes. See [fusion](FUSION.md) and the
[RBG contract](RBG_DATA_CONTRACT.md).

## Advance-event prediction

The active [protocol](../configs/event_study_gpu_v2.json) defines a new high
onset as four consecutive five-minute readings above 180 mg/dL, after seven
readings at or below 180. Features use past data only; the prediction window is
5–30 minutes ahead. This is an engineering label, not an adjudicated clinical event.

| Metric | Fused XGBoost |
|---|---:|
| Evaluable episodes detected | 229 / 336 |
| Episode recall | 68.2% |
| Conservative precision | 52.8% |
| False alarms per eligible monitoring day | 0.98 |
| Median detected-event lead | 10 minutes |
| Recall with at least ten minutes lead | 36.6% |

Twenty-seven development patients were separated into three outer folds. Each
fold used 15 fitting, three cutoff-setting and nine evaluation patients; six
reserved patients remain unscored. Replay uses the fold in which the selected
patient was excluded from fitting and cutoff selection.

Cutoff-setting folds did not consistently pass, and patient uncertainty intervals
cross operating limits. The fused-minus-CGM recall interval spans -6.7 to +11.6
percentage points, so a fusion advantage is not established. Conservative
precision includes unknown and redundant alarms in its denominator; eligible
monitoring days exclude unavailable or ineligible coverage.

The CGM-only comparison uses the configuration selected for the fused model,
with separate cutoff selection. It is a matched feature ablation, not an
independently tuned sensor-only benchmark. A fair model-selection comparison
is now available in a separately versioned
[equal-budget comparison](EVENT_COMPARISON.md). Independently tuned CGM-only
achieved 65.5% recall, 57.9% conservative precision, 0.770 false alarms per
eligible day and five-minute median lead. Fused reproduced v2 exactly. Its
paired recall advantage still includes zero (-7.8 to +11.5 percentage points);
earlier warnings trade off against lower precision and more false alarms.
This follow-up does not replace the active artifacts or improve numerical MAE.

The retained [aggregate model report](../reports/event_study_gpu_v2.json) also
supplies cutoffs and fingerprints needed to verify the saved runtime models.
Scores are uncalibrated ranking values. Clinical alerts, risk percentages and
treatment advice remain disabled. See [event replay behavior](EVENT_REPLAY.md).

The [cutoff-patient error audit](HIGH_EVENT_AUDIT.md) reproduces the saved cutoff
counts and diagnoses false alarms and misses without changing this model or its
reported validation results.
