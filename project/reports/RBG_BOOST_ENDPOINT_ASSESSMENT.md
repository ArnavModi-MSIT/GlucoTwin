# RBG nonlinear endpoint comparison

Measured 9 October 2026. Fixed histogram boosting classifiers for high/low endpoints at +30 minutes. Same training, calibration and assessment patients as logistic; reserved test patients unused. No parameter sweep.

## At-risk operating results

| Endpoint | Model | Average precision | Precision | Recall | Calibration gate | Operating gate |
|---|---|---:|---:|---:|---|---|
| high | Logistic | 0.473 | 50.0% | 49.69% | Fail | Fail |
| high | Boosting | 0.473 | 50.0% | 47.54% | Fail | Fail |
| low | Logistic | 0.271 | 50.0% | 0.22% | Fail | Fail |
| low | Boosting | 0.276 | 50.0% | 0.66% | Fail | Fail |

Threshold score values differ between model families, but selection rule and requirements are unchanged: maximum recall at precision >=50%, operating gate additionally requires recall >=60%. Thresholds optimized on assessment remain optimistic; they are not deployment approval. Events mean exact-time target >180/<70 from latest available glucose outside that state. They are not independent clinical episodes.

## Calibration

Sigmoid calibration used clipped log-odds from raw boosting probability and calibration patients only. Support requirements passed, but the combined Brier gate failed for both endpoints. Differences can be small; failure is under the preset engineering rule, not a universal clinical calibration standard.

| Endpoint / subset | Raw Brier | Sigmoid Brier | Brier gate |
|---|---:|---:|---|
| high / all | 0.065951 | 0.065960 | Fail |
| high / at_risk | 0.053014 | 0.053046 | Fail |
| low / all | 0.023654 | 0.023872 | Fail |
| low / at_risk | 0.017058 | 0.017166 | Fail |

## Patient-level support

- High: 17 assessment patients with positive at-risk endpoint rows; 0 have no correct flags. Median patient recall 48.90%.
- Low: 17 assessment patients with positive at-risk endpoint rows; 5 have no correct flags. Median patient recall 0.35%.

Runtime 19.5 seconds; sampled peak RSS 715.6 MiB. Fixed 120 iterations, 15 leaves, learning rate 0.05, minimum leaf size 80, L2=10, seed 2026; early stopping disabled, four CPU threads. Ten RBG tests passed, including saved-model flag parity and disabled deployment.

## Decision

No meaningful improvement sufficient for the preset warning requirements. Keep probabilities and deployed flags disabled. Do not silently switch dashboard models. Stop this fixed model comparison without a configuration search. More flexible modelling alone has not solved the observed endpoint warning limitations.

Next: freeze independent episode definitions and alarm cooldown rules, then assess episode recall, lead time and false alarms per observed monitoring day on development patients. This will answer a different question from overlapping endpoint precision/recall and must report the existing failed endpoint gates alongside results. Do not relax those gates retroactively or claim new clinical validation. Missing intervention data and historical-lab availability deserve further work; no guarantee of improvement. Keep test patients reserved until final scope/model choices are frozen.

[Aggregate metrics](rbg_boost_endpoint_assessment.json); [endpoint protocol](../docs/RBG_DATA_CONTRACT.md).
