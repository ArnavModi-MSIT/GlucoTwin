# GlucoTwin

A CPU-based glucose forecasting research prototype with a local **HTML, CSS and JavaScript dashboard** and Python inference service. No frontend build tools, GPU or external chart CDN are required.

## Run the dashboard

Python 3.10 or later, from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/serve_dashboard.py
```

Open **http://127.0.0.1:8000**. Local data, split manifests and trusted model artifacts must be prepared first; they are excluded from Git. For another local port, use `--port 8001`.

Select a cohort and development patient, advance by 5/30/60 minutes, or restart the replay. The interface includes historical profile context, visible glucose history, future forecast markers, persistence comparisons, data coverage and a forecast ledger. Hover over history for readings; expand the chart for a larger view. Layout adapts to smaller screens.

The Python service retains session state and runs the saved models. The browser receives visible history and only outcomes that have become available; it never receives a full future patient series. Sessions are local, isolated and expire after one hour of inactivity. The service binds to loopback and is a local research tool, not an internet-facing deployment.

## Cohorts and models

- **CGMacros:** fused Ridge using glucose history, historical clinical profile and heart rate; 60-minute forecasts. Clinical availability is assumed and CGM samples are reconstructed. Six validation patients appear in replay; six test patients remain reserved.
- **RBG:** separate Type 1 diabetes benchmark with 158 training, 34 validation and 34 reserved test patients. CGM-only Ridge predicts 30/60 minutes ahead. Enrollment age/sex are shown as context because their inclusion gave essentially no forecast gain. Unverified labs are excluded.

RBG inputs and outcome reveal follow a five-minute availability delay to account for source timestamp rounding. A forecast for 13:00 remains pending until 13:05. Issued forecasts remain fixed. Advancing skips intermediate issue times; it does not retroactively fill forecasts. Quality checks can withhold a forecast. Missing target observations remain missing.

## Measured development results

| Cohort / horizon | Persistence MAE | Ridge MAE |
|---|---:|---:|
| CGMacros / 60 min | 19.99 | 19.00 mg/dL |
| RBG / 30 min | 20.71 | 17.59 mg/dL |
| RBG / 60 min | 32.53 | 28.89 mg/dL |

These are different populations and protocols, so they are not a controlled comparison. Individual errors can be much larger than average. RBG low-glucose errors worsened with Ridge. Fixed boosting improved overall error but failed the predeclared high/low slice requirements.

Endpoint classifiers failed the preset operating and calibration gates. A frozen engineering episode backtest on 17 development patients found 78.1% recall among evaluable high episodes, a 15-minute median lead, and 3.58 false alarms per eligible monitoring day. Low-event detection remained poor. This does not overturn the failed endpoint gates. **Operational alerts and risk probabilities remain disabled.** No reserved-test prediction results have been evaluated.

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

Research demonstration only. No diagnosis, treatment or insulin dosing. Missing intervention inputs, source interpolation/rounding, assumed clinical availability and limited population coverage remain material limitations. Indian clinical performance and medical reliability have not been established. Code license has not yet been selected; dataset licenses do not grant a license to this code.
