# Advance-event research replay

The CGMacros dashboard now runs the saved **fused XGBoost v2 onset model** as a
separate research panel alongside the numerical Ridge forecast. It predicts
a new sustained high-glucose onset **5-30 minutes ahead**. A research score and
fixed cutoff are displayed; these are not calibrated risk probabilities or
operational medical alerts. The numerical forecast models and their results
are unchanged. DCLP3 remains a separate offline numerical study.

## Setup

Start the prepared dashboard with `StartGlucoTwin.cmd`, then select **CGMacros**.
The six existing validation patients are available. The event component is
optional: missing local study artifacts or XGBoost leave numerical replay
working and display an event setup message. Restart the server after updating
Python code; reload the browser after updating frontend files.

To reproduce the event study from prepared CGMacros development data, run from
`project/`:

```powershell
python -m pip install -r requirements-experiments.txt
python scripts/run_event_study.py --study gpu_v2 --device cpu
python scripts/summarize_event_study.py --study gpu_v2
```

The source release, frozen role manifest, input fingerprints and saved fold
models stay local. Never load models from an untrusted source. The launcher
does not download data, train missing models or install research dependencies.

## How model selection and timing work

- Replay selects the existing outer fold whose **evaluation** set includes the
  selected patient. The patient must be absent from fitting and cutoff sets.
  No model is refitted and no threshold is selected during replay.
- The loader checks protocol, patient-manifest and input fingerprints, source
  hashes, model roles, fused feature columns and the saved cutoff against the
  frozen study report. Failure leaves the research component unavailable.
- Prediction features use only records through the current issue time. Both
  five historical fields and 22 CGM/nine HR features enter the saved model.
- The original 24-hour warm-up and history-quality gates remain. A current
  glucose value above 180 mg/dL withholds a new-onset prediction; it is not a
  declaration that the patient's glucose is safe.
- Eligible scores above the fixed cutoff produce a **Research flag**, subject
  to the original 60-minute cooldown. Each button records a new attempt only
  at the selected issue time; skipped times are not retrospectively filled.
- Every eligible attempt's outcome stays pending until **issue time +45
  minutes**: the 30-minute onset window plus 15 minutes needed to observe the
  four qualifying five-minute readings. Source availability is assumed for
  this reconstructed dataset; it is not a verified device-arrival guarantee.
- Outcomes use only visible measurements. Incomplete future observations are
  labeled incomplete rather than interpolated. Score, cutoff and issued
  decision remain fixed. Restart clears only the current replay ledger.

The table shows the most recent attempts first. A qualifying onset can appear
in several overlapping attempt windows; those rows are not independent episodes.
The panel does not calculate an episode recall or precision from a short,
manually stepped session. Fold cutoff criteria and limitations are visible.

## Evidence and verification

The [original development report](../reports/EVENT_STUDY_GPU_V2.md) is unchanged:
229/336 evaluable episodes, 68.2% recall, 52.8% conservative precision, 0.98
false alarms per eligible monitoring day and ten-minute median detected-event
lead. Recall with at least ten minutes lead is 36.6%. Cutoff-setting folds did
not consistently pass; uncertainty intervals cross engineering gate limits.
Fusion's recall advantage has not been established. Later v3 was rejected as
an overall improvement. See [review diagnostics](INDEPENDENT_REVIEW_ACTIONS.md).

Tests cover future-input perturbation, delayed outcomes at the exact 45-minute
boundary, missing observations, cooldown, frozen roles/cutoffs, reservation
guards, HTTP reset/cohort switching and saved inference parity for all six
replay patients. Browser checks include a detected onset, below-cutoff attempts
whose later windows contain the same onset, and a flag without a qualifying
onset. These examples were selected after inspecting development outcomes;
they demonstrate behavior, not independent predictive validation.

On 11 October 2026, the full opt-in local suite ran 125 tests: 124 passed and
one optional CPU Torch test was skipped in the dashboard Python environment.
The event-specific saved-artifact checks verified three prediction times per
patient across all six replay patients, including future-input perturbations.
Browser console checks reported no errors during the verified interactions.

No new training, final-test evaluation, two-hour prediction, GPU execution or
clinical validation occurred. Risk probabilities and operational alerts remain
disabled.
