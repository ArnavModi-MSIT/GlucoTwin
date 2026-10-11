# Local dashboard statistics and information audit

Checked 10 October 2026 against the running `http://127.0.0.1:8000/`, local
validation records, saved model artifacts and aggregate reports. This is a
dashboard consistency audit, not a new accuracy study or clinical validation.

## Active models and development results

Both deployed models use training-fitted median imputation, standard scaling
and Ridge regression with alpha 10. The numerical models currently served by
the dashboard are separate from the exploratory XGBoost onset studies.

| Replay / horizon | Model inputs | Train / validation / reserved patients | Ridge validation MAE | Persistence MAE |
|---|---|---|---:|---:|
| RBG / 30 minutes | 22 CGM features + enrollment age and recorded sex | 158 / 34 / 34 | 17.5862 mg/dL | 20.7123 mg/dL |
| RBG / 60 minutes | Same 24 inputs, separate horizon model | 158 / 34 / 34 | 28.8907 mg/dL | 32.5290 mg/dL |
| CGMacros / 60 minutes | 22 CGM + 5 historical clinical + 9 HR features | 21 / 6 / 6 | 18.9986 mg/dL | 19.9887 mg/dL |

The displayed two-decimal MAEs agree with the saved reports. RBG's replay
models include historical profile fields, although these fields gave essentially
no average improvement over the original CGM-only benchmark. The populations
and evaluation protocols differ across cohorts; these rows are not a controlled
comparison between datasets.

Sources: [RBG baseline validation](../reports/rbg_baseline_validation.json),
[CGMacros baseline validation](../reports/baseline_validation.json),
[actual fusion inputs](FUSION.md), and
[model selection](../configs/rbg_model_selection.json).

Overall error hides poor low-glucose performance. On low-target validation
rows, active RBG Ridge MAEs are approximately 20.26 / 44.26 mg/dL at 30 / 60
minutes, versus persistence 19.76 / 36.98. CGMacros fused Ridge low-target MAE
is 38.80 mg/dL on only 39 low-target rows, versus persistence 20.26. These are
development error slices, not estimates of clinical safety.

## Meaning of the historical event numbers

The RBG 78.1% recall, 15-minute median lead and 3.58 false alarms per eligible
monitoring day belong to a separate historical logistic classifier backtest on
17 development patients. They are not the active Ridge model's event results.

That classifier detected 4,752 of 6,081 evaluable high-glucose episodes; 630
other qualifying episodes lacked evaluable opportunities. Recall across all
6,711 qualifying episodes was 70.8%, and conservative alarm precision was
32.4%. Low-event recall was approximately 0.67%. The prior endpoint gates still
failed, and the dashboard does not issue operational event alerts or risk
probabilities. See the [episode assessment](../reports/rbg_episode_assessment.json).

The CGMacros failed probability-calibration result refers to a separate
logistic event classifier with sigmoid calibration. It does not describe
calibration of the active numerical Ridge forecast. See the
[classifier assessment](../reports/classifier_assessment.json).

## Live values and session statistics

- The glucose card represents the exact CGM grid sample at the visible data
  cutoff. A missing current sample remains missing even when an older reading
  is visible on the chart.
- CGM coverage is 13 possible five-minute grid points over an inclusive
  one-hour window. A 12/13 window can still fail the forecast quality check if
  the current reading is missing.
- CGMacros HR coverage comes from the current forecast's observed last-hour
  fraction. A checked validation window had only 1 of 61 HR samples while CGM
  was complete; missing HR features used training-fitted median imputation.
- An attempted forecast can be withheld. A ledger row with no prediction is
  not an issued numerical forecast.
- Absolute error is `abs(prediction - observed target glucose)`. Pending and
  missing observations do not contribute to the session MAE.
- Session MAE is based only on evaluable forecast/error pairs issued during
  that replay session. RBG pools its 30- and 60-minute forecasts, and different
  forecasts can share one observed target reading. This is not a count of
  independent patient outcomes or the aggregate validation MAE.
- RBG observations and outcomes have a five-minute availability delay.
  CGMacros follows its published reconstructed grid without that additional
  delay. Source dates are artificial or shifted; no real timezone is asserted.
- Larger replay steps skip intervening issue times. The dashboard does not
  retroactively create forecasts for those times.

## Verification scope

The live audit completed 242 API requests across all 34 RBG and six CGMacros
validation patients, with 30,014 checks and no numerical, timing or saved-model
mismatches. It checked chart cutoffs, profile fields, current readings,
coverage, forecast targets, delayed outcomes, immutable predictions, residual
arithmetic, session MAE, snapshot consistency, reset and saved inference parity.

Twenty-two additional direct replay cases covered middle, late, missing-data
and end-of-record windows. Advancing beyond the final record did not duplicate
ledger entries. Private patient-level audit evidence stays excluded from Git.

The browser check covered both cohorts, displayed forecast/error arithmetic,
delayed reveal and the expanded results panel. Missing observations stayed
unfilled. No models were retrained, no reserved sensor records were scored,
and no GitHub publication was performed during this audit.

All 75 Python tests passed with local integration checks enabled. The frontend
information checks and JavaScript syntax check also passed. Desktop and
390-pixel-wide browser checks confirmed the revised labels and responsive
header; no browser warnings or errors were observed during the checked flows.

## Information corrections applied

The frontend now identifies the active profile-fused Ridge models and the
separate historical event-classifier results. It shows issued and withheld
attempts separately, includes a forecast-status column, labels the mixed-horizon
session statistic, and states the absolute-error units. The glucose card names
its exact data cutoff, and CGMacros shows HR coverage plus the imputation note.
The longer forecast header wraps on narrow displays rather than squeezing the
description beside the count badge. Backend inference and saved models were
unchanged.

Synthetic frontend checks execute the real renderer on issued/withheld,
missing-current-CGM and missing/partial-HR cases without patient data:
`node tests/frontend_info_unit.js` from `project/`.
