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
- Daily summaries and recurring time-of-day patterns from available history, with coverage checks.
- Patient-specific meal/medication logs and a three-day user-entered meal/reminder plan, with JSON export and validated restore.
- Synthetic scenarios that run without datasets or model downloads.
- Automatic five-minute replay, issued-flag and revealed-onset chart markers.
- CSV/JSON session exports and a printable report with PDF saving through the browser.

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
the same rounded MAEs. See [fusion details](project/docs/FUSION.md). Cohorts and
protocols differ, so these rows are not a controlled dataset comparison.

The separate CGMacros event study detected **229/336 episodes (68.2% recall)**,
with **52.8% conservative precision**, **0.98 false alarms per eligible day** and a
**10-minute median lead**. Recall requiring at least ten minutes warning was
**36.6%**. Cutoff-setting folds did not consistently pass; see the
[current results](project/docs/RESULTS.md).

**Research use only.** Low-glucose errors remain a weakness, and useful clinical
fusion gains are not established. Reserved-test performance remains unscored.
Operational alerts, calibrated risk probabilities and treatment advice are disabled.

## Setup

Requires Python 3.10+ and the dependencies below. The synthetic demonstration
runs immediately after installation, using fictional patients and an illustrative
trend rule. Its scores are **not** the development results reported above.
The research cohorts require locally prepared datasets and trusted model
artifacts; follow the [reproduction guide](project/docs/REPRODUCTION.md).

From the repository root:

```powershell
cd project
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/launch_dashboard.py
```

After installing dependencies, Windows users can double-click
[StartGlucoTwin.cmd](StartGlucoTwin.cmd) to open `http://127.0.0.1:8000`.
Press **Ctrl+C** in the server window to stop it. Optional event-model setup is
documented in [event replay](project/docs/EVENT_REPLAY.md).

Select **Synthetic demo** to explore a rising trajectory, stable readings or a
sensor interruption. **Play replay** advances every five minutes; larger jumps
also record each intermediate issue. Export buttons include only information
revealed by the current replay time.

Run tests from `project/`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Synthetic tests run without data. Set `GLUCOTWIN_INTEGRATION=1` to include
prepared local-data and artifact checks.

## Documentation

- [Architecture (PDF)](project/docs/delivery/GlucoTwin_Architecture.pdf)
- [Presentation (PPTX)](project/docs/delivery/GlucoTwin_Presentation.pptx) · [PDF](project/docs/delivery/GlucoTwin_Presentation.pdf)
- [API](project/docs/API.md) · [Data contract](project/DATA_CONTRACT.md) · [Evaluation protocol](project/EVALUATION_PROTOCOL.md)
- [Model results](project/docs/RESULTS.md) · [Model preparation](project/docs/REPRODUCTION.md)
- [Best-results checkpoint](project/docs/BEST_RESULTS.md)

Demonstration video preparation is deferred.

## Team

**arnavmodi23** — Maharaja Surajmal Institute of Technology (MSIT), Delhi.

| Member | Role |
|---|---|
| Arnav Modi | Team leader |
| Harjot Singh | Team member |
| Arnav Kumar | Team member |

## License and data

Original code is licensed under [MIT](project/LICENSE). Datasets and dependencies retain
their own terms: [CGMacros](https://physionet.org/content/cgmacros/1.0.0/) uses
CC BY-NC-SA 4.0; [DiaData v3](https://zenodo.org/records/17285631) uses CC BY-NC 4.0
with original-source attribution. Raw records and model binaries stay local.
