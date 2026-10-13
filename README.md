# GlucoTwin

A virtual patient research prototype that combines historical clinical profiles
with continuous glucose monitoring (CGM) and heart-rate data. It investigates
glucose forecasting and advance detection of sustained high-glucose episodes,
with a local dashboard for clinicians to review patient history and outcomes.

## Problem and healthcare use case

**Condition:** diabetes. **Target outcome:** a new sustained high-glucose episode.
The prototype links a patient's historical profile to recent sensor readings so
a clinician can review advance estimates, data coverage and observed outcomes.
The primary fusion and event study uses CGMacros, a mixed cohort including
people with prediabetes and type 2 diabetes. RBG is a separate type 1 diabetes
forecasting benchmark. Results do not establish type 2-specific performance.

## Features

- Linked clinical and sensor inputs in the fitted models.
- Validated local CSV import with explicit units, preserved gaps and optional exploratory RBG transfer.
- Patient overview with last-viewed snapshots, search and replay navigation.
- Sticky navigation between overview, timeline, history, care plan and results.
- Editable care entries with patient-specific undo for recent removals.
- Optional same-tab replay resume after refresh while the localhost session is active.
- Patient replay with glucose history, sensor coverage, future forecasts and user-log timeline markers.
- Ridge arithmetic explanations grouped into clinical, glucose, heart-rate and missingness contributions.
- Fixed prediction ledgers, delayed outcome reveal and persistence comparisons.
- Optional exploratory prediction ranges with measured assessment coverage and horizon-specific widths.
- A separate event research panel with uncalibrated scores and fixed cutoffs.
- Daily/hourly history, observed high/low runs, day comparisons and CSV exports.
- Fourteen-date historical percentile profile with coverage and variability summaries.
- Review observations, questions and replay-timed follow-up tasks, included in combined reports.
- Patient-specific meal/medication logs and a three-day user-entered plan, with optional local saving, JSON export and validated restore.
- Completed after-meal reviews retained beyond the visible timeline, with replay-time checks.
- Synthetic scenarios that run without datasets or model downloads.
- Automatic five-minute replay, issued-flag and revealed-onset chart markers.
- CSV/JSON session exports, a downloadable printable replay report, and a combined review summary with user logs and the three-day plan.

Dataset names: **RBG** identifies the REPLACE-BG type 1 diabetes study.
**CGMacros** is the nutrition and diet-monitoring dataset, combining glucose,
meal macronutrients and clinical information. **CGM** means continuous glucose
monitoring; **HR** means heart rate. The dashboard includes a dataset guide.

## Models and stack

| Dashboard path | Model inputs | Prediction horizon |
|---|---|---|
| CGMacros Ridge | Clinical profile, CGM and heart rate | 60 minutes |
| RBG Ridge | Enrollment age/sex and CGM | 30 and 60 minutes |
| CGMacros XGBoost | Clinical profile, CGM and heart rate | New high-glucose onset 5–30 minutes ahead |

**Backend:** Python, NumPy, pandas, scikit-learn, joblib and optional XGBoost.
**Frontend:** HTML, CSS and JavaScript with an SVG chart. The prepared dashboard
runs on CPU without a frontend build step or external chart service.

## Development results

Mean absolute error (MAE), in mg/dL; lower is better:

| Numerical benchmark | Horizon | Persistence | Ridge |
|---|---|---:|---:|
| CGMacros | 60 min | 19.99 | 19.00 |
| RBG | 30 min | 20.71 | 17.59 |
| RBG | 60 min | 32.53 | 28.89 |

RBG values describe the original CGM-only benchmark; profile-fused replay has
the same rounded MAEs. See [fusion details](arnavmodi23_MSIT/docs/FUSION.md). Cohorts and
protocols differ, so these rows are not a controlled dataset comparison.

The separate CGMacros event study detected **229/336 episodes (68.2% recall)**,
with **52.8% conservative precision**, **0.98 false alarms per eligible day** and a
**10-minute median lead**. Recall requiring at least ten minutes warning was
**36.6%**. Cutoff-setting folds did not consistently pass; see the
[current results](arnavmodi23_MSIT/docs/RESULTS.md).

**Research use only.** Low-glucose errors remain a weakness, and useful clinical
fusion gains are not established. Reserved-test performance remains unscored.
Operational alerts, calibrated risk probabilities and treatment advice are disabled.

## Setup

Requires Python 3.10+ and the dependencies below. The synthetic demonstration
runs immediately after installation, using fictional patients and an illustrative
trend rule. Its scores are **not** the development results reported above.
The default worked example opens with two weeks of fictional history, replayed
forecast outcomes, and labeled sample notes and a three-day plan. Sample entries
can be edited or removed; they are never added to research or imported patients.
Patient summaries show observed trends and coverage; a task inbox tracks entered
reminders and follow-up. Sensor gaps and forecast errors can be inspected, with
separate results by horizon. A simulated feed generates fictional readings on
arrival. Review reports can be previewed with charts and downloaded for printing.
The research cohorts require locally prepared datasets and trusted model
artifacts; follow the [reproduction guide](arnavmodi23_MSIT/docs/REPRODUCTION.md).

From the repository root:

```powershell
cd arnavmodi23_MSIT
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/launch_dashboard.py
```

After installing dependencies, Windows users can double-click
[StartGlucoTwin.cmd](StartGlucoTwin.cmd) to open `http://127.0.0.1:8000`.
Press **Ctrl+C** in the server window to stop it. Optional event-model setup is
documented in [event replay](arnavmodi23_MSIT/docs/EVENT_REPLAY.md).

Select **Synthetic demo** to explore a rising trajectory, stable readings or a
sensor interruption. **Play replay** advances every five minutes; larger jumps
also record each intermediate issue. Export buttons include only information
revealed by the current replay time.

Run Python and JavaScript checks from `arnavmodi23_MSIT/` (Node.js 22+ required):

```powershell
.\.venv\Scripts\python.exe scripts/run_tests.py
```

Synthetic tests run without data. Add `--integration` for prepared local-data
and artifact checks, or `--node PATH` when Node is not on PATH.

All application code, preparation scripts and project materials are inside
`arnavmodi23_MSIT/` (registered team name plus college abbreviation). The README
and Windows launcher remain at the repository root for direct access.

## Documentation

- [Architecture and workflow diagrams (PDF)](arnavmodi23_MSIT/docs/delivery/GlucoTwin_Architecture.pdf)
- [Presentation (PPTX)](arnavmodi23_MSIT/docs/delivery/GlucoTwin_Presentation.pptx) · [PDF](arnavmodi23_MSIT/docs/delivery/GlucoTwin_Presentation.pdf)
- [Diagram source (Figma)](https://www.figma.com/design/hrTQZOj6fL2W2cu9ghWN7Y)
- [API](arnavmodi23_MSIT/docs/API.md) · [Data contract](arnavmodi23_MSIT/DATA_CONTRACT.md) · [Evaluation protocol](arnavmodi23_MSIT/EVALUATION_PROTOCOL.md)
- [Model results](arnavmodi23_MSIT/docs/RESULTS.md) · [Model preparation](arnavmodi23_MSIT/docs/REPRODUCTION.md)
- [CSV import](arnavmodi23_MSIT/docs/CSV_IMPORT.md)
- [Patient review features](arnavmodi23_MSIT/docs/PATIENT_REVIEW.md)
- [Forecast uncertainty](arnavmodi23_MSIT/docs/UNCERTAINTY.md)
- [Best-results checkpoint](arnavmodi23_MSIT/docs/BEST_RESULTS.md)

Demonstration video preparation is deferred.

## Team

**arnavmodi23** — Maharaja Surajmal Institute of Technology (MSIT), Delhi.

| Member | Role |
|---|---|
| Arnav Modi | Team leader |
| Harjot Singh | Team member |
| Arnav Kumar | Team member |

## License and data

Original code is licensed under [MIT](arnavmodi23_MSIT/LICENSE). Datasets and dependencies retain
their own terms: [CGMacros](https://physionet.org/content/cgmacros/1.0.0/) uses
CC BY-NC-SA 4.0; [DiaData v3](https://zenodo.org/records/17285631) uses CC BY-NC 4.0
with original-source attribution. Raw records and model binaries stay local.

After-meal review pairs user-reported meal times with available sensor history. It shows the baseline, highest available two-hour reading and coverage; incomplete or poorly covered windows withhold the difference. These observations do not establish a food effect or recommend treatment.
