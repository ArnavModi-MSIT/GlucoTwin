# Reproducing the local dashboard and research runs

Use Python 3.10 and the pinned requirements. Commands run from the `project/` folder inside the repository (`cd project` first). Keep records, generated manifests and model binaries local; the repository deliberately excludes them.

## CGMacros dashboard

```powershell
python download_cgmacros.py
python scripts/audit_cgmacros.py
python scripts/check_cgmacros_interpolation.py
python scripts/freeze_cgmacros_contract.py
python scripts/prepare_features.py
python scripts/train_baselines.py
```

The downloader needs network access. It retrieves selected CSV members from the original release and skips photographs. Follow the data license and original author attribution linked in the README.

## RBG dashboard from supplied DiaData files

Obtain the exact [DiaData v3 release](https://zenodo.org/records/17285631), including `Demographics.csv` and `5_min_sampling.zip`. Extract its `raw.zip` member into `data/5_min_sampling/raw.zip`; the importer can also accept the already extracted `SDBIII_5min_sampling_raw.zip`. The preprocessed data is not used.

Place the original demographic file at `data/raw/diadata/Demographics.csv`. Do not re-save it through a spreadsheet editor: the importer checks the original file hash.

```powershell
python scripts/import_rbg.py --archive data/5_min_sampling/raw.zip --demographics data/raw/diadata/Demographics.csv
python scripts/freeze_rbg_contract.py
python scripts/prepare_rbg.py
python scripts/train_rbg_baselines.py
python scripts/prepare_rbg_replay.py
```

The importer streams the source rather than expanding its 10.74 GB CSV. It creates the approximately 1.4 GB RBG subset, checks its frozen SHA-256, verifies the demographic file against the release MD5, audits all patient grids and creates local patient audit metadata. Output lives under `data/raw/diadata/`; only aggregate counts/hashes appear in `reports/rbg_import.json`. Allow sufficient disk space for downloaded archives, the subset and generated feature matrices.

If the canonical subset already exists, its hash is checked and extraction is skipped. A different existing subset is preserved and causes an error. The split generator refuses to overwrite a differing frozen manifest. Neither command fits a model or evaluates test predictions.

## Start the interface

On Windows, double-click `StartGlucoTwin.cmd` in the parent folder. For a manual start from `project/`:

```powershell
python scripts/launch_dashboard.py
```

The launcher checks the pinned runtime dependencies, prepared validation replay data and saved models, then opens http://127.0.0.1:8000. Keep the command window open; Ctrl+C stops the server. Use `--no-browser` to open it manually. The service provides local inference; no React build or external frontend dependency is required. Direct `python scripts/serve_dashboard.py` remains available for development.

## Optional research assessments

Numerical replay uses baseline Ridge artifacts. The optional CGMacros event research panel also loads the saved XGBoost v2 artifacts; see [event replay setup](EVENT_REPLAY.md). The full artifact verification suite additionally expects models/reports from these assessments:

```powershell
python scripts/train_boosting.py
python scripts/train_classifier.py
python scripts/train_rbg_boosting.py
python scripts/train_rbg_endpoints.py
python scripts/train_rbg_boost_endpoints.py
python scripts/analyze_rbg_endpoints.py
python scripts/assess_rbg_episodes.py
python -m pip install -r requirements-experiments.txt
python scripts/run_event_study.py
python scripts/run_event_study.py --study gpu_v2 --device cpu
$env:GLUCOTWIN_INTEGRATION='1'
python -m unittest discover -s tests -v
```

These are frozen development assessments, not instructions to search configurations until gates pass. Do not evaluate reserved test performance during reproduction. On bash, use `export GLUCOTWIN_INTEGRATION=1` for the local suite. The default suite runs synthetic checks and skips local-data tests; clear that variable to run it without data. Dataset-free checks can be run before data acquisition:

```powershell
python -m unittest discover -s tests -p test_rbg_import.py -v
python -m unittest discover -s tests -p test_episodes.py -v
```

## Verification scope

Future-onset studies have separate frozen protocols and artifacts. They use only
the 27 CGMacros development patients, nested patient-level model selection and
separate threshold-setting patients. They do not replace existing Ridge models
or open reserved sensor files. The CUDA notebook is prepared but has not been
executed in a cloud runtime. See the study protocols and reports for limitations.

On 10 October 2026, the importer verified the existing real subset, 226 linked patient IDs, 18,126,280 grid rows and 14,700,791 nonmissing glucose readings. It reproduced the existing split hash exactly. Extraction/filtering and invalid grid boundaries were tested with small synthetic ZIP/CSV fixtures. A second complete real-archive extraction was not rerun in this change; do not describe it as a newly executed clean-machine end-to-end reproduction.
