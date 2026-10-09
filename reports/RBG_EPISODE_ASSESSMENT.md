# RBG engineering episode backtest

Measured 9 October 2026 on the same 17 development assessment patients. Models and endpoint thresholds unchanged. No training, threshold sweep, reserved-test access or deployment change. Prior endpoint operating/calibration gates remain failed.

## Frozen rules

Qualifying high/low onset: first >180/<70 reading after seven consecutive observed readings outside that state, followed by four consecutive observed readings inside it. The preceding outside-state samples span30minutes; the four abnormal samples span15minutes. Missing observations break qualification. Short excursions, gaps and previously abnormal states are excluded. These are engineering episodes, not medically adjudicated events.

Generate opportunities from past-only features with five-minute sensor delay, warm-up and quality abstention. No future target is required. At-risk alarms use the saved thresholds and a60minute cooldown after every issued alarm. An alarm matches at most one qualifying onset5–30minutes later, and one onset receives at most one match.

Primary recall counts onsets with at least one eligible at-risk forecast opportunity in that warning window. Report all qualifying onsets separately, including those outside warm-up/quality availability. Unmatched alarms are false only with complete observed future data through45minutes; other alarms are unknown. Unknown is not silently negative. Native timing may differ by up to2.5minutes from the published rounded grid.

## Results

| Endpoint | Model | Evaluable episodes | Detected | Episode recall | Median lead | False alarms / eligible day | Unknown alarms |
|---|---|---:|---:|---:|---:|---:|---:|
| high | logistic | 6,081 | 4,752 | 78.1% | 15 min | 3.58 | 1,443 |
| high | boost | 6,081 | 4,626 | 76.1% | 15 min | 3.32 | 1,351 |
| low | logistic | 2,392 | 16 | 0.7% | 10 min | 0.01 | 16 |
| low | boost | 2,392 | 46 | 1.9% | 5 min | 0.04 | 23 |

Eligible monitoring days = at-risk eligible opportunities ×5minutes/1440. This is observed forecast coverage, not real-world calendar days; it differs between high/low tasks. Alarm rows include unknown cases. All qualifying high onsets:6,711; primary evaluable:6,081. All qualifying low onsets:2,557; primary evaluable:2,392.

## Uncertainty and alarm precision

Exploratory95% intervals resample patients (2,000 resamples), not overlapping rows. These do not remove development model/threshold selection bias or episode-definition limitations.

- high/logistic: recall interval 75.9%–80.3%; false alarms/eligible day 3.21–4.00. Alarm precision bounds 32.4%–42.2% depending on unknown outcomes.
- high/boost: recall interval 73.8%–78.2%; false alarms/eligible day 3.01–3.67. Alarm precision bounds 33.4%–43.2% depending on unknown outcomes.
- low/logistic: recall interval 0.2%–1.1%; false alarms/eligible day 0.01–0.03. Alarm precision bounds 20.8%–41.6% depending on unknown outcomes.
- low/boost: recall interval 0.7%–3.3%; false alarms/eligible day 0.02–0.06. Alarm precision bounds 22.9%–34.3% depending on unknown outcomes.

High logistic all-qualifying-onset recall is70.8%, lower than78.1% among evaluable episodes. Most high warnings arrive10–20minutes before the rounded-grid onset. Neither measure proves reliable30minute advance warning for every event. Low logistic detects16/2,392evaluable episodes; boosting detects46/2,392. Low false-alarm burden partly reflects issuing almost no useful warnings, not superior safety.

## Decision

High-event ranking supports an exploratory research demonstration, but repeated false alarms remain substantial and independent clinical validation is absent. Low-event warning is not supported. Keep operational flags and probabilities disabled. Do not relax failed endpoint gates or replace their metrics with this more favorable episode recall.

Stop adding model configurations to the current input set. Missing meal/insulin context and verified historical lab availability need investigation for further modelling. A useful next implementation is a dashboard that presents30/60minute RBG numerical forecasts beside persistence, data quality and measured limitations; the existing CGMacros replay must be identified separately. Retain the reserved test until final choices are frozen.

Runtime26.9seconds; four episode-rule tests passed (sustained onset/gap break, causal cooldown, one-to-one matching/unknown handling and missing-future negative exclusion). Alarm-count reconciliation passed for every event/model summary.

[Aggregate metrics](rbg_episode_assessment.json); [frozen protocol](../docs/RBG_DATA_CONTRACT.md).
