# GlucoTwin

A CPU-based glucose forecasting research prototype with a local **HTML, CSS and JavaScript dashboard** and Python inference service. No frontend build tools, GPU or external chart CDN are required.

## Team

**Registered team:** arnavmodi23

**College:** Maharaja Surajmal Institute of Technology (MSIT), Delhi

| Member | Role |
|---|---|
| Arnav Modi | Team leader |
| Harjot Singh | Team member |
| Arnav Kumar | Team member |

## Problem and healthcare use case

GlucoTwin investigates whether a virtual patient combining historical clinical
context with recent CGM and heart-rate observations can forecast glucose and
identify an approaching sustained high-glucose episode. The intended user is a
clinician reviewing a patient's profile, sensor coverage, history and subsequently
observed outcomes. Numerical forecasting and event detection are evaluated
separately; neither establishes safe treatment or dosing decisions.

The current clinician dashboard serves fused numerical Ridge forecasts. A
separate XGBoost model predicts new high-glucose onsets 5-30 minutes ahead in
retrospective development studies. It now runs in a separate
[event research replay panel](docs/EVENT_REPLAY.md), using the saved fold in
which the patient was excluded from fitting and cutoff selection. Its scores
and fixed research flags remain exploratory, with operational alerts and risk
probabilities disabled. The larger DCLP3 study is offline. These paths must not
be presented as one validated clinical model.

## Technical stack and project materials

- Python 3.10+, NumPy, pandas, scikit-learn and joblib for preprocessing,
  regression, inference and evaluation; XGBoost for optional research studies.
- HTML, CSS and JavaScript with an SVG chart; Python HTTP service for local
  replay. No frontend build step or external chart service.
- [Architecture diagram (PDF)](docs/delivery/GlucoTwin_Architecture.pdf)
- [Project presentation (PPTX)](docs/delivery/GlucoTwin_Presentation.pptx) and
  [PDF presentation](docs/delivery/GlucoTwin_Presentation.pdf)
- [Delivery readiness](docs/DELIVERY_READINESS.md)

Demonstration video preparation is deferred. Original project code is licensed
under the [MIT License](LICENSE). Dataset and third-party dependency licenses
remain separate; MIT does not override their usage or redistribution terms.

## Run the dashboard

On this prepared Windows workspace, double-click **StartGlucoTwin.cmd** in the parent folder. It opens **http://127.0.0.1:8000** and keeps the server in the command window. Press **Ctrl+C** or close that window to stop it. Launching it again opens the existing dashboard. It checks dependencies, prepared data and saved models before starting; it does not download or train anything.

All project files are in this `project/` folder. For manual setup, use Python 3.10 or later and run commands from here:

```powershell
cd project
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/launch_dashboard.py
```

Local data, split manifests and trusted model artifacts must be prepared first; they are excluded from Git. For another local port, run `StartGlucoTwin.cmd --port 8001` from the parent folder, or `python scripts/launch_dashboard.py --port 8001` from this folder. Use `--no-browser` when opening the browser manually.

Select a cohort and development patient, advance by 5/30/60 minutes, or restart the replay. The interface includes historical profile context, visible glucose history, future forecast markers, persistence comparisons, data coverage and a forecast ledger. CGMacros additionally runs the optional saved XGBoost onset model, showing uncalibrated research scores and fixed decisions with outcomes withheld until issue time +45 minutes. Hover over history for readings; expand the chart for a larger view. Layout adapts to smaller screens.

The Python service retains session state and runs the saved models. The browser receives visible history and only outcomes that have become available; it never receives a full future patient series. Sessions are local, isolated and expire after one hour of inactivity. The service binds to loopback and is a local research tool, not an internet-facing deployment.

## Cohorts and models

- **CGMacros:** fused Ridge using glucose history, historical clinical profile and heart rate; 60-minute forecasts. Clinical availability is assumed and CGM samples are reconstructed. Six validation patients appear in replay; six test patients remain reserved.
- **RBG:** separate Type 1 diabetes benchmark with 158 training, 34 validation and 34 reserved test patients. Replay uses Ridge with enrollment age/sex **and CGM history** at 30/60 minutes. Both streams enter the model; age/sex added essentially no forecast gain. Enrollment-profile availability is assumed and unverified labs are excluded. The original CGM-only accuracy benchmark remains documented separately.

RBG inputs and outcome reveal follow a five-minute availability delay to account for source timestamp rounding. A forecast for 13:00 remains pending until 13:05. Issued forecasts remain fixed. Advancing skips intermediate issue times; it does not retroactively fill forecasts. Quality checks can withhold a forecast. Missing target observations remain missing.

## Measured development results

| Cohort / horizon | Persistence MAE | Ridge MAE |
|---|---:|---:|
| CGMacros / 60 min | 19.99 | 19.00 mg/dL |
| RBG / 30 min | 20.71 | 17.59 mg/dL |
| RBG / 60 min | 32.53 | 28.89 mg/dL |

These are different populations and protocols, so they are not a controlled comparison. Individual errors can be much larger than average. RBG low-glucose errors worsened with Ridge. Fixed boosting improved overall error but failed the predeclared high/low slice requirements.

The RBG table reports the original CGM-only benchmark. Its profile-fused replay models have the same MAEs at two-decimal precision, but slightly worse low-target errors. See [fusion implementation](docs/FUSION.md) for actual model inputs and limitations.

Endpoint classifiers failed the preset operating and calibration gates. A frozen engineering episode backtest on 17 development patients found 78.1% recall among evaluable high episodes, a 15-minute median lead, and 3.58 false alarms per eligible monitoring day. Low-event detection remained poor. This does not overturn the failed endpoint gates. **Operational alerts and risk probabilities remain disabled.** No reserved-test prediction results have been evaluated.

## Future-onset research

A separate algorithm now predicts **new sustained high-glucose onsets within 30 minutes**, using linked clinical profile, CGM and HR. Nested patient-level studies separate model selection, threshold setting and outer evaluation. All 27 development patients and eligible rows are used; the six reserved sensor files are not opened by these runners.

The first six-configuration study detected 193/336 evaluable episodes (57.4% recall), with 58.5% conservative precision, 0.65 false alarms per eligible monitoring day and a 10-minute median lead. It failed the predeclared recall gate; these are exploratory development results. See [protocol](docs/EVENT_STUDY_V1.md) and [results](reports/EVENT_STUDY_V1.md).

```powershell
python scripts/run_event_study.py
python scripts/summarize_event_study.py
```

A separately versioned four-configuration XGBoost study supports CPU and CUDA. Optional pinned dependencies and a Kaggle/Colab notebook template are provided in [GPU study instructions](docs/EVENT_STUDY_GPU_V2.md). A prepared notebook is not a verified cloud run. The dashboard uses Ridge for numerical forecasts and optionally loads saved XGBoost models in the separate event research panel; clinical warnings remain disabled.

The local **CPU** XGBoost study detected 229/336 episodes (68.2% recall), with 52.8% conservative precision, 0.98 false alarms per eligible monitoring day and 10-minute median lead. Its pooled engineering gate passed, but two threshold-setting folds failed and the patient-bootstrap intervals cross gate limits. Fusion's recall gain over sensor-only was 3.0 percentage points with an interval spanning zero. This remains exploratory evidence, with alerts and risk percentages disabled. The separate research panel now replays these saved models on their excluded evaluation patients; integration does not improve or independently validate the scores. See [XGBoost results](reports/EVENT_STUDY_GPU_V2.md), [comparison plot](reports/event_studies.png) and [event replay](docs/EVENT_REPLAY.md).

- [CGMacros data contract](DATA_CONTRACT.md) and [evaluation protocol](EVALUATION_PROTOCOL.md)
- [RBG contract](docs/RBG_DATA_CONTRACT.md)
- [RBG baseline results](reports/RBG_BASELINE_RESULTS.md) and [boosting comparison](reports/RBG_BOOSTING_RESULTS.md)
- [Endpoint assessment](reports/RBG_ENDPOINT_ASSESSMENT.md), [precision–recall diagnostics](reports/RBG_ENDPOINT_DIAGNOSTICS.md), [nonlinear comparison](reports/RBG_BOOST_ENDPOINT_ASSESSMENT.md), [episode backtest](reports/RBG_EPISODE_ASSESSMENT.md)

## Data and preparation

[CGMacros v1.0.0](https://physionet.org/content/cgmacros/1.0.0/) is governed by **CC BY-NC-SA 4.0**. The downloader retrieves CSV members while skipping photographs. Preserve dataset attribution and terms separately from code licensing.

```powershell
python download_cgmacros.py
python scripts/audit_cgmacros.py
python scripts/check_cgmacros_interpolation.py
python scripts/freeze_cgmacros_contract.py
python scripts/prepare_features.py
python scripts/train_baselines.py
```

For RBG, obtain the exact [DiaData v3 raw release](https://zenodo.org/records/17285631), extract `raw.zip` into `data/5_min_sampling/raw.zip`, and place the original `Demographics.csv` at `data/raw/diadata/Demographics.csv`. Data is under **CC BY-NC 4.0**, with applicable original-source attribution. No private audit files are required:

```powershell
python scripts/import_rbg.py --archive data/5_min_sampling/raw.zip --demographics data/raw/diadata/Demographics.csv
python scripts/freeze_rbg_contract.py
python scripts/prepare_rbg.py
python scripts/train_rbg_baselines.py
python scripts/prepare_rbg_replay.py
```

The importer checks the versioned files, streams the subset and creates local audit metadata. A differing existing subset or frozen split causes an error rather than silently changing the benchmark. See [complete reproduction instructions](docs/REPRODUCTION.md) for storage, optional research assessments and verification scope.

Raw records, clinical metadata, patient-level reports, replay caches and model binaries stay local. Never load an untrusted joblib/pickle artifact. The saved models here are generated by the project's training scripts.

## Verification

```powershell
python -m unittest discover -s tests -v
```

By default, synthetic tests run without datasets; local artifact tests skip with an explanation. To run all checks after preparing both cohorts and the optional assessment artifacts:

```powershell
$env:GLUCOTWIN_INTEGRATION='1'
python -m unittest discover -s tests -v
```

On bash, use `GLUCOTWIN_INTEGRATION=1 python -m unittest discover -s tests -v`. Install the package with `python -m pip install -e .`. See [reproduction instructions](docs/REPRODUCTION.md), [API reference](docs/API.md) and [review actions](docs/REVIEW_ACTIONS.md).

Checks cover causal feature timing, exact targets, patient-disjoint roles, train-only imputation, saved inference parity, delayed outcome reveal, session isolation and exclusion of reserved test patients. Local HTTP tests require loopback socket access.


## Scope

Current score-improvement experiments and intervention-data audits are
documented in [Score improvement](docs/SCORE_IMPROVEMENT.md). Modest MAE reductions
have not established an improvement in severe errors or reliable warnings.
The [independent review actions](docs/INDEPENDENT_REVIEW_ACTIONS.md) document
verified fixes, corrected review claims, and new loss/tail and warning-lead diagnostics.

The separate [BrisT1D CPU input study](docs/BRIST1D_STUDY_V1.md) evaluates sixteen
development patients with four additional patients reserved. Full-input XGBoost
achieved development MAE 19.92 / 29.46 mg/dL at 30 / 60 minutes, with only a
small gain from extra inputs and poor low-target errors. Its cohort/timing differ
from the dashboard benchmarks. This study did not replace the replay models or
enable warnings. See the [frozen contract](docs/BRIST1D_DATA_CONTRACT.md).

The matched [freshness repair study v2](docs/BRIST1D_STUDY_V2.md) recovered the
failed full-input Ridge experiment while barely changing XGBoost MAE
(19.92 / 29.43 mg/dL). Low-target errors remain worse than persistence.
The dashboard models are unchanged. The subsequent
[causal adaptation study](docs/BRIST1D_ADAPTATION_V3.md) slightly improved some
error slices but worsened overall XGBoost MAE, so its fixed rule was rejected.
The [matched compact neural comparison](docs/BRIST1D_SEQUENCE_V4.md) also ran:
TCN MAE was 20.44 / 29.70 versus matched XGBoost 19.98 / 29.54 mg/dL.
It did not establish an overall improvement or resolve poor low-target errors.

The separate [DCLP3 preparation](docs/DCLP3_CONTRACT.md) freezes 134 development
participants and 34 reserved participants, with four patient-disjoint folds.
It prepares historical clinical, CGM and pump inputs for measured 30/60-minute
endpoints under explicit availability delays. Meal logs are unavailable.
The [fixed CPU comparison](docs/DCLP3_STUDY_V2.md) now reports participant MAE
17.53/27.47 mg/dL for CGM-only XGBoost, versus persistence 20.92/32.32.
Clinical additions show no convincing gain. Insulin additions produce small
matched-subset gains, while low-target errors remain poor. These are separate
development results; no dashboard model or alert policy was replaced.

Research demonstration only. No diagnosis, treatment or insulin dosing. Missing intervention inputs, source interpolation/rounding, assumed clinical availability and limited population coverage remain material limitations. Indian clinical performance and medical reliability have not been established. Original code is MIT licensed; datasets and third-party dependencies retain their own licenses.
