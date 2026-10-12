# Local replay API

Double-click `StartGlucoTwin.cmd` in the repository's outer folder, or run `python scripts/launch_dashboard.py` from `project/`. The service uses `http://127.0.0.1:8000`.

`GET /api/health` returns the application name and an opaque workspace identifier so the launcher can safely reuse this dashboard when its port is already occupied.
The service binds to loopback. It is a local research interface.

| Route | Method | Request | Result |
|---|---|---|---|
| `/api/health` | GET | None | Application name and opaque workspace identifier; no patient/model reads |
| `/api/catalog` | GET | None | Validation-patient IDs/labels by cohort; `errors` explains unavailable local preparation |
| `/api/session` | POST | `{"cohort":"rbg","patient_id":"115.0_RBG"}` | New replay snapshot; replaces this browser's prior session |
| `/api/advance` | POST | `{"minutes":5}` (also 30 or 60) | Advance and issue immutable forecasts |
| `/api/reset` | POST | `{}` | Reset this session to its warm-up boundary |
| `/api/snapshot` | GET | None | Current snapshot without advancing |
| `/api/export?format=csv` | GET | Session cookie | Forecast and event ledger download |
| `/api/export?format=history` | GET | Session cookie or tab header | Available hourly history CSV; separate from the forecast ledger |
| `/api/export?format=json` | GET | Session cookie | Revealed snapshot download |
| `/api/export?format=html` | GET | Session cookie | Printable session report; browser Print can save PDF |
| `/api/feed/sample` | POST | Session cookie or tab header; optional `missing` boolean | Receive one fictional five-minute slot in the simulated feed only |

`demo` is always available in the catalog with scenarios `showcase`, `rise`, `stable`, and
`gap`. The default `showcase` includes fictional history and chronological replayed outcomes. Create one using `{"cohort":"demo","patient_id":"rise"}`. This mode uses
fictional profiles and generated sensor readings, with a deterministic past-only
trend rule. `synthetic: true` and model names distinguish it from trained models.
Synthetic event outcomes require a 50-minute delay (30-minute window, 15-minute
confirmation and 5-minute sensor delay); CGMacros uses its existing 45-minute rule.

All advances process **every five-minute issue**, including 30/60-minute jumps.
Automatic playback uses the same five-minute advance endpoint and pauses when
the browser page is hidden, on errors, on patient changes or at record end.
Exports use the current server snapshot and never query future source rows.
CSV contains `forecast` and `event` record types; JSON also includes visible chart
history and profile context. Reports carry synthetic/research labels and model
identity. Session MAE is not a validation benchmark.

POST bodies must be JSON objects with `Content-Type: application/json`, at
most 4,096 bytes. Session state uses an HttpOnly, SameSite=Strict cookie.
Invalid requests and expired sessions return HTTP 400 with an `error` field;
unexpected inference failures return HTTP 500 with a generic message and a
server log. Select a patient again after expiry. Host/Origin failures return
403. Unknown routes return 404.

Snapshots contain `patient_id`, `issue_time`, `data_cutoff`, profile context, visible chart
points, per-horizon forecasts, a fixed forecast ledger and session comparison
metrics. Null predictions mean abstention. Null outcomes remain pending or
have no exact observation. RBG inputs/outcomes have a five-minute availability
delay; hidden future observations are never included in snapshots. Neither
cohort exposes operational alerts or risk probabilities.

CGMacros snapshots additionally include `event_research`: optional availability,
setup error, fold metadata, the current fixed score/cutoff/decision and a separate
event ledger. The selected model's evaluation fold excludes this patient from
fitting and cutoff setting. Eligible outcomes remain pending until issue time
+45 minutes. Uncalibrated ranking scores are not risk probabilities; research
flags are not operational alerts. RBG returns `event_research: null`. See
[event research replay](EVENT_REPLAY.md).

The frontend shows request failures in its alert banner and restores controls
after requests. Chart labels summarize current values for screen readers;
the forecast ledger provides a tabular alternative to forecast markers.

## User-entered care notes

The dashboard provides patient-specific meal and medication-taken logs plus
planned meals and reminders copied from an existing prescribed schedule. These annotations
are held in tab memory, optionally saved locally, and exported separately as JSON.
They are not sent to the API or used as model inputs, dataset events, or PDF report
content. Reminder status follows replay time and supports manual review; no
real-world notification, medication scheduling algorithm or dosing advice runs.
Observed logs cannot be dated after replay time. Planned meals and reminders may
be dated in the future. The planner shows the current study date and the next two
dates. Explicit daily repetition creates three separate entries at the same
time, including across month/leap-day boundaries. Repetition of medication-taken
logs is rejected; reminders require confirmation that the entire schedule,
including repetition, was prescribed. A planned meal is never automatically
converted into a recorded meal. Notes export schema `glucotwin-user-notes-v2`
includes all entries plus the three displayed planning dates. Restarting a replay retains
notes for that patient and labels later entries accordingly.

## Historical patterns

Snapshots contain `historical_patterns`: last seven study dates ending at the
data cutoff, five-minute grid on the patient phase, no new interpolation. Daily
percentages use observed readings, with coverage and expected counts shown.
Comparable six-hour windows must have 72 expected slots and at least 80% coverage.
A high window has at least 20% readings above 180 mg/dL; a low window has at least
5% below 70. Recurrence requires at least two days and at least half of comparable
days. Partial windows and poor coverage are excluded from recurrence. These are
descriptive engineering rules, not future predictions or personalized targets.
CGMacros source samples retain their reconstruction limitations. JSON and
print/PDF reports include daily and recurring-period summaries; ordinary CSV
remains a prediction ledger.

`historical_patterns.hourly` contains one row per supplied five-minute-grid hour,
with `date`, `hour`, first/last checkpoint timestamps, observed `samples`,
`expected` slots, coverage, mean/minimum/maximum and observed band fractions.
A complete hour has 12 expected slots and its nominal end is no later than
`data_cutoff`; comparable hours additionally need at least 10 readings. The
first supplied hour and current hour may be partial. Missing readings remain
missing, and future hours are omitted. Means and fractions use observed readings
only; empty hours have null values.

The history CSV exports these fields with patient/cohort identity, replay time
and data cutoff. It requires matching summary/cutoff timestamps and omits rows
whose final checkpoint is after the cutoff. Text starting with spreadsheet
formula characters is escaped. No raw readings, predictions or browser care
notes are included. The interactive heatmap and two-day comparison are dashboard
views; they are not added to the existing printable reports.

## Restore care notes

The browser reads a selected local JSON file without uploading it. Exports with
`glucotwin-user-notes-v1` or `glucotwin-user-notes-v2` are supported; the cohort
and patient ID must match the selected patient exactly. Maximum file size is
256 KB and maximum merged patient entries is 200. Entry types, identifiers,
dates, descriptions, observed-action chronology and reminder review timestamps
are checked before changing any state. User-entered planned actions may be in
the future; imported review status remains hidden until that replay time.

Restore previews counts and requires confirmation for imported prescribed
reminders. It merges without overwriting existing entries or review states.
Duplicate identity uses type, action time, description and creation replay time;
import IDs are reassigned. Invalid files and capacity errors change no entries.
Changing patient cancels pending selection; a later file selection supersedes
an earlier asynchronous read. Unknown extra fields and exported planning-day
arrays are not restored: the calendar is recomputed from validated entries and
the current replay clock. Imported notes remain unverified user annotations and
never become model inputs or dataset records.

## Combined review summary

`Download review summary` generates a standalone HTML file in the browser from
the currently displayed snapshot and this patient’s validated in-tab notes. It
includes profile, sensor cutoff/coverage, current numerical estimates, available
daily summaries and recurring periods, user-reported actions, and the three-day
plan. Dataset history, algorithmic estimates and user annotations have separate
labels. Forecast target outcomes are not included. Actions dated or created
after replay time are omitted; review states appear only once their review time
has elapsed, and future-created plans are excluded. Plan times are copied user
inputs, not predicted treatments. All dynamic text is HTML-escaped.

This download makes no API upload, uses no external assets or scripts, and does
not alter model inference. Open the saved HTML file in a browser and choose
Print / Save as PDF. The existing backend print report remains the replay-only
report; care-note JSON remains the restore format. Local HTML preview may be
unavailable in embedded browsers that block file URLs. The summary is research
context for review and supplies no diagnosis or treatment recommendations.

The separate **Preview review report** button displays a frozen capture inside a
sandboxed in-app frame, without opening a file URL. Its download contains the same
captured HTML, including SVG timeline and past hourly percentile charts. It makes
no API upload, includes no scripts or external resources, and pauses playback.

## Fictional sensor feed

Create a demo session with `patient_id: "feed"`. It bootstraps 73 past fictional
samples. POST `/api/feed/sample` with `{}` or `{"missing": false}` generates one
new sample; `{"missing": true}` appends a missing slot. Other types are rejected
without changing the session. Research, imported and other demo sessions reject
this operation. `/api/advance` receives one slot per five-minute step for this
scenario; `/api/reset` discards received slots and restores the bootstrap state.

The clock is sample time plus five minutes. Forecast targets are revealed only
after their sample arrives, and previous issued estimates are unchanged.
`sensor_feed` snapshot metadata describes received/missing slots, bootstrap
count and the 288-slot limit. GET snapshot does not generate data. At the limit,
receipt is a no-op and `at_end` is true. This is accelerated fictional input,
not a connected sensor, research cohort or real-time medical monitoring service.

## User action markers

The timeline overlays in-tab meal and medication-taken logs for the visible
six-hour window. Both the action time and creation replay time must be no later
than the current replay time. Planned meals and prescribed reminders are never
treated as observed actions. Patient/dataset identity is checked against the
current care context before notes reach the renderer.

Meal circles and medication-log squares have distinct colors, text descriptions
and tooltips. A show/hide control changes marker visibility; the accessible list
remains available. Adding, restoring or removing notes redraws annotations
without changing sensor values, y-axis limits, forecast values or API inputs.
Timing is descriptive and does not establish a treatment response.

Patient review additions: issued numerical rows may include `explanation` with Ridge reference offset, grouped contributions, imputed fields and a reconstructed prediction. `historical_patterns.profile` contains the past-only fourteen-date descriptive summary and hourly quantiles. These fields enter JSON snapshots and HTML reports; they never reveal future target observations. The overview uses last-viewed browser snapshots, not a new live-data endpoint. Optional care-note persistence stays in browser local storage and is not sent to the API.

Browser requests use a tab-specific `X-GlucoTwin-Session` header. Creating a session with an explicit empty header leaves other tab sessions intact; the response returns the new token in that header. Tokens stay in memory unless same-tab refresh resume is enabled; then the bookmark is kept in session storage. Tokens are never placed in URLs. Cookie-only API clients remain supported. Browser exports fetch with the same header and download the resulting file, so the chosen patient is preserved even when another tab changes cohorts. Open the downloaded HTML report and print it to PDF if needed.

`POST /api/import/preview` accepts `csv_text`, declared `unit`, `provenance`, anonymized `label`, `mode` (`persistence` or `rbg`) and optional `profile` (`age`, `sex`). It validates without creating a replay and returns quality metadata. `POST /api/import/session` validates again, creates an imported replay and returns a tab session header. Import requests have a 4 MB JSON-body limit; CSV itself is limited to 1 MB. No file paths or model uploads are accepted. All normal local-host/origin guards remain in force. Imported snapshots have `imported: true`, `patient_id` and `import_quality`; they carry no cohort-specific event or uncertainty calibration.
