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
