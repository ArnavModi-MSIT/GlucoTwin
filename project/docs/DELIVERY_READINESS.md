# Prototype delivery readiness

Checked against the supplied requirements on 11 October 2026. This is a preparation record, not a declaration that the prototype is ready for final evaluation.

## Project and intended use

**GlucoTwin** is a virtual patient research workspace that links historical clinical context to an evolving sensor history. A clinician can inspect a patient profile, replay visible observations, compare fixed forecasts with a persistence baseline, and reveal outcomes as they become available.

The primary adverse-event research task is **a new sustained high-glucose onset 5-30 minutes ahead** in CGMacros. Numerical 30/60-minute endpoint forecasting is a separate task. A two-hour glucose spike is an example in the supplied requirements, not an explicit mandatory horizon. Do not claim that this build predicts two hours ahead.

## Technical requirement mapping

| Requirement | Current evidence | Readiness and remaining work |
|---|---|---|
| Historical clinical input | CGMacros age, recorded sex, BMI, baseline HbA1c and fasting glucose | Implemented in fitted replay and onset models. This is historical clinical context, not a complete hospital EHR. Availability is assumed. |
| Dynamic sensor input | CGMacros CGM and heart rate; separate RBG CGM replay | Implemented. Replay is retrospective; CGMacros samples are reconstructed. Do not describe it as a live device connection. |
| Both streams enter the algorithm | Linked IDs, combined feature vectors, training-fitted preprocessing; [fusion documentation](FUSION.md) | Implemented. Inclusion does not prove a useful accuracy gain. |
| Advance adverse-event prediction | [XGBoost onset study](../reports/EVENT_STUDY_GPU_V2.md), frozen [configuration](../configs/event_study_gpu_v2.json), [research replay](EVENT_REPLAY.md) | Algorithm, development evaluation and delayed-outcome patient replay implemented. Results remain exploratory; not all cutoff-setting folds passed. Reliable warning performance is not established. |
| Doctor interaction dashboard | HTML/CSS/JS profile, visible history, coverage, replay controls, immutable forecast/event ledgers and baseline comparison | Numerical Ridge and separate XGBoost event research are served. DCLP3 remains offline. |
| Permitted data | Published research datasets; raw records, patient metrics and model binaries excluded from Git | Preserve attribution and individual dataset terms. Public-source data is not necessarily unrestricted for redistribution or commercial use. |

## Evidence to present accurately

The CGMacros XGBoost v2 study used 27 development patients in three outer folds. Each fold separated 15 fitting patients, three threshold-setting patients and nine evaluation patients. Six reserved patients were not evaluated by this study.

- Target: four consecutive five-minute readings above 180 mg/dL, following seven consecutive readings at or below 180. This is an engineering event definition, not an adjudicated medical event.
- Advance window: 5-30 minutes. Future readings are used to construct evaluation labels, never prediction features.
- Detected 229 of 336 evaluable episodes: **68.2% recall**.
- Conservative precision: **52.8%**; verified false alarms: **0.98 per eligible monitoring day**; median detected-event lead: **10 minutes**.
- Recall requiring at least ten minutes lead: **36.6%**. The median lead alone does not mean most episodes receive ten minutes warning.
- Patient-bootstrap intervals cross operating gate limits. The fusion-minus-CGM recall interval is **-6.7 to +11.6 percentage points**, so a clinical-input advantage is not established.
- Later v3 detected 173/336 episodes (51.5% recall), with 53.9% precision and 0.72 false alarms/day; it was rejected as an overall improvement. V2 is a development reference chosen after comparing experiments, not a new independent validation result.

Separate DCLP3 numerical evidence: 134 development patients, four patient-disjoint folds, 34 reserved patients unscored. CGM-only XGBoost participant MAE is **17.53/27.47 mg/dL** at 30/60 minutes versus persistence **20.92/32.32**. Clinical fields show no convincing gain; adding insulin in the matched 100-person subset gives small gains. Low-target 60-minute MAE remains **54.31**, worse than persistence **50.04**. Do not combine this cohort's regression scores with CGMacros event scores as one model result.

## Materials

| Item | Location / status |
|---|---|
| Project title, problem, healthcare use case, stack and models | [README](../../README.md) |
| Architecture in PDF | [Architecture](delivery/GlucoTwin_Architecture.pdf) |
| Project presentation | [Editable deck](delivery/GlucoTwin_Presentation.pptx), [PDF deck](delivery/GlucoTwin_Presentation.pdf) |
| Demonstration video | Deferred at the team's request; remains a requirement for final delivery |
| Team and college information | arnavmodi23: Arnav Modi (leader), Harjot Singh, Arnav Kumar; MSIT, Delhi. Included in README and presentation. |
| Code license | [MIT](../LICENSE) for original project code; dataset and dependency licenses remain separate |
| Public accessibility | Requires a final Git push and logged-out link check; local paths alone do not establish public access |
| Requested team/college folder name | Suggested final delivery folder: `arnavmodi23_MSIT`; final packaging pending. Working source remains in `project/`. |
| Leader contact fields | Enter on the platform; do not publish phone/email by default |

## Completion order

1. Implemented: frozen onset-model replay with past-only features, uncalibrated research scores, fixed decisions and delayed outcomes. Browser verification covers an observed onset, below-cutoff attempts before that onset and a false flag; examples were selected after inspecting development outcomes. No new efficacy result is implied. Treatment advice, risk percentages and operational alerts remain disabled.
2. Make one final model/threshold decision with a written frozen protocol before using reserved data. Do not adjust thresholds on reserved outcomes or select patients to improve aggregate scores. Evaluate episode recall, conservative precision, false alarms per eligible day, lead-time distribution and patient intervals.
3. Rehearse the current numerical dashboard and the event demonstration separately; run appropriate timing, fusion, inference-parity and API checks. A single successful replay is not aggregate validation.
4. Team details and the approved MIT code license are included in the current materials. Refresh them if the build or scores change.
5. Video work is deferred. When resumed, record at least 20 minutes and link the actual unlisted video; the supplied requirements still include this deliverable. PDF/PPT assets are linked now.
6. Review the actual public Git tree and links, push the approved preparation changes, then verify public access. Submission itself is a separate user action.

## Claims that this build does not support

No clinically validated warning reliability, no safe insulin dosing, no guaranteed two-hour warning, no significant clinical-fusion gain, no new DCLP3 event results, no cloud GPU execution, no final held-out performance and no completed video recording. Operational alerts and risk probabilities remain disabled.
