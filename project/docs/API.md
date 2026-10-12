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
| `/api/export?format=json` | GET | Session cookie | Revealed snapshot download |
| `/api/export?format=html` | GET | Session cookie | Printable session report; browser Print can save PDF |

`demo` is always available in the catalog with scenarios `rise`, `stable`, and
`gap`. Create one using `{"cohort":"demo","patient_id":"rise"}`. This mode uses
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

Snapshots contain `issue_time`, `data_cutoff`, profile context, visible chart
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
are held in tab memory, cleared on reload/close, and exported separately as JSON.
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
CGMacros source samples retain their reconstruction limitations. The JSON and
print/PDF report include these summaries; the CSV remains a prediction ledger.

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
