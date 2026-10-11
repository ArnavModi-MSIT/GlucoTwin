# GlucoTwin

A virtual patient research prototype that combines historical clinical profiles
with continuous glucose monitoring (CGM) and heart-rate data. It investigates
glucose forecasting and advance detection of sustained high-glucose episodes,
with a local dashboard for clinicians to review patient history and outcomes.

## Features

- Linked clinical and sensor inputs in the fitted models.
- Patient replay with glucose history, sensor coverage and future forecasts.
- Fixed prediction ledgers, delayed outcome reveal and persistence comparisons.
- A separate event research panel with uncalibrated scores and fixed cutoffs.

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
the same rounded MAEs. See [fusion details](docs/FUSION.md). Cohorts and
protocols differ, so these rows are not a controlled dataset comparison.

The separate CGMacros event study detected **229/336 episodes (68.2% recall)**,
with **52.8% conservative precision**, **0.98 false alarms per eligible day** and a
**10-minute median lead**. Recall requiring at least ten minutes warning was
**36.6%**. Cutoff-setting folds did not consistently pass; see the
[event results](reports/EVENT_STUDY_GPU_V2.md).

An [offline DCLP3 study](docs/DCLP3_STUDY_V2.md) achieved CGM-only XGBoost
participant MAE of **17.53/27.47 mg/dL** at 30/60 minutes across 134 development
participants. It is separate from the dashboard models.

**Research use only.** Low-glucose errors remain a weakness, and useful clinical
fusion gains are not established. Reserved-test performance remains unscored.
Operational alerts, calibrated risk probabilities and treatment advice are disabled.

## Setup

Requires Python 3.10+, locally prepared datasets and trusted model artifacts.
Data and models are excluded from Git; follow the
[reproduction guide](docs/REPRODUCTION.md) before launching.

From the repository root:

```powershell
cd project
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/launch_dashboard.py
```

After preparation, Windows users can double-click
[StartGlucoTwin.cmd](../StartGlucoTwin.cmd) to open `http://127.0.0.1:8000`.
Press **Ctrl+C** in the server window to stop it. Optional event-model setup is
documented in [event replay](docs/EVENT_REPLAY.md).

Run tests from `project/`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Synthetic tests run without data. Set `GLUCOTWIN_INTEGRATION=1` to include
prepared local-data and artifact checks.

## Documentation

- [Architecture (PDF)](docs/delivery/GlucoTwin_Architecture.pdf)
- [Presentation (PPTX)](docs/delivery/GlucoTwin_Presentation.pptx) · [PDF](docs/delivery/GlucoTwin_Presentation.pdf)
- [API](docs/API.md) · [Data contract](DATA_CONTRACT.md) · [Evaluation protocol](EVALUATION_PROTOCOL.md)
- [Experiment history](docs/SCORE_IMPROVEMENT.md) · [Verification](docs/BUILD_TEST_REPORT.md)

Demonstration video preparation is deferred; remaining deliverables are tracked
in [delivery readiness](docs/DELIVERY_READINESS.md).

## Team

**arnavmodi23** — Maharaja Surajmal Institute of Technology (MSIT), Delhi.

| Member | Role |
|---|---|
| Arnav Modi | Team leader |
| Harjot Singh | Team member |
| Arnav Kumar | Team member |

## License and data

Original code is licensed under [MIT](LICENSE). Datasets and dependencies retain
their own terms: [CGMacros](https://physionet.org/content/cgmacros/1.0.0/) uses
CC BY-NC-SA 4.0; [DiaData v3](https://zenodo.org/records/17285631) uses CC BY-NC 4.0
with original-source attribution. Raw records and model binaries stay local.
