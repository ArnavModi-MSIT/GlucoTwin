# Current build test report

Tested 10 October 2026 against the local working tree and the running dashboard
at `http://127.0.0.1:8000`. This is functional testing, not medical validation.

## Results

- All 43 existing regression tests passed. A new synthetic end-of-record/reset
  regression also passed separately (44 passing tests in total).
- 324 live API requests passed across all 34 RBG and six CGMacros validation
  patients. Every patient was created, advanced by 30/5/60 minutes and reset.
- Checked visible chart timestamps, pending outcomes, immutable issued
  predictions, error arithmetic and session MAE calculation.
- Invalid JSON shapes/cohorts/steps, Host/Origin violations and reserved-patient
  requests were rejected. Reserved patients were not replayed or scored.
- Four concurrent clients retained independent replay clocks; one session
  completed 100 consecutive five-minute advances without a failure.
- Request latency: median 113 ms, p95 250 ms, p99 515 ms, maximum 872 ms.
  These figures include local client/server overhead and the tested workflows;
  they are not a benchmark at every point of long patient histories.
- Browser checks passed for RBG delayed reveal (+30 minutes pending, +35
  minutes observed), CGMacros +60-minute reveal, patient/cohort changes, reset,
  measured-results panel and chart fullscreen entry/exit.
- At 390 x 844 viewport size, the chart remained visible, controls fit and the
  document had no horizontal overflow. Desktop viewport was restored.
- No browser console warnings/errors were recorded during the checked flows.

## Limits and remaining concerns

Model reliability remains the main limitation: Ridge can lose to persistence
in individual sessions, and existing low-glucose/calibration gates remain
failed. Functional correctness does not improve forecast performance.

The live sweep covers early replay windows and one 100-step trace, not every
timestamp, missing-data interval or terminal point of every real patient.
End-of-record idempotence was tested with synthetic data. Feature calculations
still recompute visible history, so long-history latency requires a separate
benchmark. This test did not exercise full keyboard accessibility or a
production/multi-user deployment.

Re-run `python scripts/check_dashboard.py` with the local server running to
regenerate aggregate diagnostics. The script creates its own browser-independent
cookie sessions and writes no patient-level report. Full local regression tests
require `GLUCOTWIN_INTEGRATION=1`; see the reproduction guide.

No model refits, new model selection, reserved-test performance evaluation or
GitHub publication were performed. The server remains running.
