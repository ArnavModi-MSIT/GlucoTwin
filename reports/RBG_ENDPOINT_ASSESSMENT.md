# RBG 30-minute endpoint classifier assessment

Measured 9 October 2026. Two fixed logistic models using delayed CGM history plus enrollment age/sex. Train: 158 patients; calibration: 17; assessment: 17; reserved test: 34, unused. Assessment patients were used in prior numerical model comparisons; this is development analysis.

## At-risk endpoint results

High: target >180 with latest allowed glucose <=180. Low: target <70 with latest allowed glucose >=70. Target is the exact supplied reading 30 minutes after issue time, with a five-minute feature availability delay. These are overlapping endpoint labels, not independent episodes.

| Endpoint | At-risk rows | Positive fraction | Average precision | Precision at selected threshold | Recall |
|---|---:|---:|---:|---:|---:|
| high | 666,194 | 7.84% | 0.473 | 50.0% | 49.69% |
| low | 941,815 | 2.11% | 0.271 | 50.0% | 0.22% |

Thresholds maximize assessment recall subject to precision >=50%. Predeclared operating gate additionally requires recall >=60%; both endpoints fail. Threshold selection on assessment makes these results optimistic. The low classifier catches only44 of19,907 positive at-risk rows at its selected threshold. High catches25,957 of52,242, with25,957 false-positive rows. Row counts cannot be interpreted as separate patient alarms or independent episodes.

## Probability assessment

Calibration support passed for both endpoints. Sigmoid calibration slightly worsened Brier scores overall and at-risk, failing the strict predeclared no-worsening rule. This is a development gate failure, not proof that every raw score is unreliable. No probability display is approved.

| Endpoint / subset | Raw Brier | Sigmoid Brier | Training-prevalence Brier |
|---|---:|---:|---:|
| high / all | 0.066828 | 0.067129 | 0.215861 |
| high / at_risk | 0.053368 | 0.053613 | 0.130941 |
| low / all | 0.024815 | 0.024874 | 0.032032 |
| low / at_risk | 0.017309 | 0.017313 | 0.020994 |

All-row average precision is much higher for high glucose because it includes readings already high at issue time. It must not be advertised as early-onset warning performance. At-risk ranking is stronger than constant prevalence but does not meet the chosen precision/recall operating requirement. Lower thresholds could improve recall at a false-positive cost; that tradeoff has not been clinically validated.

## Outcome and limits

Both probability display and flag deployment remain disabled in saved artifacts. The CGMacros dashboard is unchanged. No medical clearance, independent episode lead-time, false alarms per real-world day or reserved-test performance claimed. Age/sex inclusion alone does not establish a meaningful clinical-profile contribution. Missing meals/insulin and unverified lab timing still limit forecasts.

Runtime 28.4 seconds; sampled peak RSS 814.3 MiB. [Aggregate metrics](rbg_endpoint_assessment.json); [frozen protocol](../docs/RBG_DATA_CONTRACT.md).

Next: inspect precision/recall curves and per-patient failures, then consider one predeclared nonlinear endpoint comparison rather than deploying these flags. Freeze an independent episode evaluation protocol before claiming adverse-event onset prediction. Keep the reserved test patients unused during development.
