# Build verification history

## Release preparation: 11 October 2026

The current HTML dashboard includes numerical Ridge replay and the optional
saved CGMacros XGBoost event research panel. The event models and cutoffs remain
fixed; integration does not establish clinical reliability or improve scores.

- The full local suite ran 125 tests: 124 passed, one optional CPU Torch test
  skipped in the dashboard Python environment. Local HTTP checks used loopback
  access. The frontend information checks and JavaScript syntax check passed.
- An isolated snapshot of the staged public files, without private datasets or
  models, ran the same 125-test suite: 102 passed and 23 local-data or optional
  dependency tests skipped. This checks dataset-free publication behavior; it
  does not establish a new clean-machine training run.
- Public-file review covered 231 files, including the MIT license, original
  source, frozen protocols, aggregate reports and project materials. No scanned
  credentials, private paths, phone numbers, dataset/model files or unwanted
  discovery wording were found. All relative Markdown links resolve to public
  files. Reachable history was scanned separately, with no pattern findings.
- Duplicate ignore rules were consolidated without changing the admitted file
  set. Project files remain under `project/`, with the Windows launcher beside it;
  the CI workflow runs tests from that folder.
- The presentation's MIT license note was refreshed. Its 12-slide editable
  package passed structural, layout, font and first-party import checks; the
  revised slide and PDF page were visually inspected. Native PowerPoint
  execution was not verified.
- Browser checks for the event integration are documented in
  [event replay](EVENT_REPLAY.md). No model refits, reserved-test evaluation or
  new clinical performance result occurred during release preparation.

The earlier test history below describes its dated build, not the current
test count or server state. Video preparation remains deferred.

## Earlier verification: 10 October 2026

Tested 10 October 2026 after moving the working tree into `project/` and adding
the Windows launcher. The live dashboard used `http://127.0.0.1:8000`.
This is functional testing, not medical validation.

## Results

- All 75 unit and local integration tests passed with zero skips.
- The root `StartGlucoTwin.cmd --no-browser` started the prepared dashboard;
  a second launch reused the same workspace server. Browser opening is covered
  by synthetic launcher tests; this run did not repeat visual browser checks.
- Checked missing dependencies/data, unknown-server refusal, Windows exclusive
  port binding, safe duplicate launches, health identity and Ctrl+C cleanup.
- All previously tracked project files were retained under `project/`.
  Git metadata stays at the outer level and is hidden in Windows Explorer.
- Parsed 66 public Python files, 36 JSON files and the cloud notebook, verified
  35 local Markdown links, and scanned 142 public candidate files with no
  private-path, discovery-wording, credential or record/model/archive findings.
- 324 live API requests passed across all 34 RBG and six CGMacros validation
  patients. Every patient was created, advanced by 30/5/60 minutes and reset.
- Checked visible chart timestamps, pending outcomes, immutable issued
  predictions, error arithmetic and session MAE calculation.
- Invalid JSON shapes/cohorts/steps, Host/Origin violations and reserved-patient
  requests were rejected. Reserved patients were not replayed or scored.
- Four concurrent clients retained independent replay clocks; one session
  completed 100 consecutive five-minute advances without a failure.
- Request latency: median 148 ms, p95 281 ms, p99 547 ms, maximum 937 ms.
  These figures include local client/server overhead and the tested workflows;
  they are not a benchmark at every point of long patient histories.
- Earlier browser checks on the same frontend passed for RBG delayed reveal (+30 minutes pending, +35
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
GitHub publication were performed. The validation server was stopped; double-click
the outer `StartGlucoTwin.cmd` to start a fresh server and open the browser.
