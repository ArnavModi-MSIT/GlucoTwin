# GlucoTwin

CPU-based glucose forecasting research prototype combining historical clinical profiles with continuous glucose monitor and heart-rate data.

The current implementation predicts glucose **60 minutes ahead**. It includes dataset audits, a shared feature builder, patient-disjoint development partitions, persistence/Ridge/gradient-boosting comparisons and correctness checks. The dashboard and calibrated event classifier are not implemented yet.

## Current results

Exploratory CGMacros reconstructed-grid benchmark: 33 admitted participants, with 21 training, 6 validation and 6 reserved test patients.

| Model | Validation MAE (mg/dL) | Validation RMSE (mg/dL) |
|---|---:|---:|
| Persistence | 19.99 | 31.52 |
| Ridge: glucose + clinical profile + HR | 19.00 | 28.13 |
| Boosting: glucose only | 18.45 | 29.72 |
| Boosting: glucose + clinical profile + HR | 18.96 | 30.81 |

Fused Ridge is the provisional point forecaster because fused boosting's small average-MAE gain accompanies worse high-glucose errors and RMSE. Neither model improves every error slice. Final test prediction scores have not been evaluated.

These are development results on reconstructed samples, not clinical validation. The source interpolates CGM onto a one-minute grid. The inferred five-minute samples lack verified native measurement flags, and historical clinical-profile availability is assumed. See the [data contract](DATA_CONTRACT.md), [evaluation protocol](EVALUATION_PROTOCOL.md) and [boosting report](reports/BOOSTING_RESULTS.md).

## Local setup

Python 3.10 or later. From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Dependencies are pinned to the tested training environment. No GPU is required.

## Data and reproduction

Obtain [CGMacros v1.0.0 from PhysioNet](https://physionet.org/content/cgmacros/1.0.0/). It is governed by **CC BY-NC-SA 4.0**, including attribution, noncommercial and share-alike conditions. Data licensing is separate from this repository's code. Cite the original dataset authors and follow the [data license](https://creativecommons.org/licenses/by-nc-sa/4.0/).

Raw records, clinical metadata, participant-level derived reports and model binaries are excluded from Git. The downloader fetches CSV members from the official public archive while skipping photographs. Reproduction requires network access for data acquisition:

```powershell
python download_cgmacros.py
python scripts/audit_cgmacros.py
python scripts/check_cgmacros_interpolation.py
python scripts/freeze_cgmacros_contract.py
python scripts/prepare_features.py
python scripts/train_baselines.py
python scripts/train_boosting.py
python -m unittest discover -s tests -v
```

Local preparation generates the split manifest, processed records and saved models. Reports contain measured results from actual runs. Avoid further final-test evaluation until model choices and inference behavior are frozen.

## Scope

Research demonstration only. Not for diagnosis, treatment or insulin dosing. The study includes healthy, prediabetic and Type 2 participants; it does not establish performance in Type 1 diabetes or an Indian clinical population. Forecast threshold flags are not calibrated probabilities or verified onset warnings.
