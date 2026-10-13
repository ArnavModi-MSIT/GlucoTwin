# Event research replay

The optional CGMacros panel runs saved fused XGBoost models alongside numerical
Ridge forecasts. It estimates a new sustained high-glucose onset 5–30 minutes
ahead. Scores are uncalibrated ranking values; research flags are not clinical alerts.

## Preparation

Follow [setup](REPRODUCTION.md), including `requirements-event.txt` and the active
CPU event-model command. Start the dashboard and select CGMacros. The six
existing validation patients are available. If optional dependencies or artifacts
are missing, numerical replay remains available with an event setup message.

## Timing and model verification

- Replay uses the saved fold whose evaluation set includes the selected patient,
  excluding them from fitting and cutoff selection. It fits no new model.
- The loader verifies protocol, input, source and role fingerprints, fused feature
  columns and saved cutoffs against the aggregate model report.
- Features contain only observations through issue time. A 24-hour warm-up and
  history-quality checks apply. Current glucose above 180 mg/dL withholds a
  new-onset score rather than declaring the patient safe.
- A score at or above the frozen cutoff produces a research flag, with a
  60-minute cooldown. Play and time-jump controls issue an attempt at every
  five-minute step, including intermediate times.
- Outcomes stay pending until issue time +45 minutes: the onset window plus
  the sustained-event confirmation readings. Missing measurements are not
  interpolated. Issued scores, cutoffs and decisions remain fixed.

Overlapping attempt windows can reveal the same onset; rows are not independent
episodes. The session table does not estimate aggregate clinical performance.
The numerical and event ledgers reset together when restarting replay.

Orange flags mark issue times on the glucose chart. A purple dotted onset line
appears only after an outcome has been revealed; overlapping windows share one
onset marker. CSV/JSON exports and printable reports preserve the same reveal
boundary. Synthetic-demo markers come from a separate illustrative trend rule,
not this saved XGBoost model.

See [current results and limitations](RESULTS.md). Reconstructed CGM samples,
assumed profile/source availability, limited patient coverage and inconsistent
cutoff performance restrict the interpretation. Operational alerts and risk
percentages remain disabled.
