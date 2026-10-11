# Future-onset prediction: cgmacros-onset-gpu-v2

Run 10 October 2026. Retrospective development data; no reserved-test sensor files or targets were opened.

Used 27 patients, 58,880 known training-label opportunities and 225 unknown-label opportunities (excluded from training).

Three outer folds each held out nine patients. Model selection used inner patient-level CV on 15 fitting patients; thresholds used three additional patients. 4 fixed candidate configurations were compared. Predictions target sustained high-glucose onsets 5–30 minutes ahead. All feature preprocessing is fit only on fitting patients.

| Method | Detected / evaluable episodes | Recall | Conservative precision | False alarms / eligible day | Median lead | Pooled engineering gate |
|---|---:|---:|---:|---:|---:|---|
| fused | 229 / 336 | 68.2% | 52.8% | 0.98 | 10 min | True |
| cgm_only | 219 / 336 | 65.2% | 59.3% | 0.73 | 5 min | False |
| slope_rule | 144 / 336 | 42.9% | 50.5% | 0.67 | 5 min | False |

Fused-minus-sensor-only recall difference: 3.0%; paired patient bootstrap 95% interval [-6.7%, 11.6%]. Negative values favor sensor-only. This is a matched ablation, not a separately tuned best sensor model.

Conservative precision counts all alarms, including unknown and redundant alarms, in the denominator. False-alarm days are eligible at-risk coverage, not calendar patient-days. Onsets are engineering labels, not adjudicated medical events. Patient bootstrap intervals for each method are in the JSON report.

All fused threshold-setting folds passed: False. This result does not enable alerts or percentages. Model ranking scores are uncalibrated. Repeated use of development patients, reconstructed source values, assumed historical-profile availability and small subject count remain limitations.

Runtime 188.4 seconds; sampled peak RSS 242.8 MiB. Requested device: cpu. No training-row cap was used.

Reproduce with `python scripts/run_event_study.py --study gpu_v2`, then `python scripts/summarize_event_study.py --study gpu_v2`. Frozen roles and raw-input fingerprints remain local. The protocol hash is recorded in every fold artifact and aggregate report. Further experiments must use a new protocol version; do not lower gates after seeing these scores.

This study was specified after v1 results were inspected and reuses the same development patients. It is another exploratory comparison, not independent confirmation. CPU execution does not verify the cloud CUDA notebook.
