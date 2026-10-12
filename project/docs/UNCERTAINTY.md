# Exploratory forecast ranges

The point models and MAEs are unchanged. Optional frozen residual ranges describe uncertainty around each issued numerical forecast. They are not calibrated event probabilities or clinical confidence claims.

Run from `project/` after preparing the active Ridge models:

```powershell
python scripts/prepare_intervals.py
```

The script sorts validation patient IDs as strings and alternates them into calibration and assessment groups. CGMacros rows are rebuilt directly from validation sensor files; RBG uses only the validation feature directory. Patient membership is verified against the manifests. The final workflow never opens reserved sensor files or generates reserved predictions. The active model is not refitted. Calibration residuals and assessment predictions are generated separately for each horizon. The radius is the ceil((n+1)*0.90) order statistic of absolute calibration residuals.

| Cohort | Horizon | Calibration / assessment patients | Radius mg/dL | Full width mg/dL | Assessment coverage | Patient-macro coverage |
|---|---|---|---:|---:|---:|---:|
| CGMacros | 60 min | 3 / 3 | 35.29 | 70.58 | 83.4% | 83.4% |
| RBG | 30 min | 17 / 17 | 38.33 | 76.67 | 88.9% | 89.0% |
| RBG | 60 min | 17 / 17 | 62.19 | 124.37 | 89.3% | 89.4% |

CGMacros coverage was 51.4% on low targets and 47.8% on high targets. RBG low-target coverage was 87.3% at 30 minutes and 78.4% at 60 minutes. These results do not establish reliable uncertainty for adverse events. Full slice and patient coverage ranges are in [the aggregate report](../reports/forecast_intervals_v1.json).

Overlapping residuals are temporally dependent, patients differ, and these validation patients previously informed development/model selection. Consequently the nominal 90% calibration level does not guarantee 90% coverage on a new patient, within a clinical slice, or at a particular time. The large row counts are not independent sample sizes. No tuning was performed to repair coverage after seeing assessment results.

The local JSON calibration artifact contains patient assignments and model fingerprints and remains ignored. Only assessment patients receive ranges in replay; calibration patients explicitly show ranges as unavailable. Missing or mismatched artifacts fail closed. Bounds are attached at issue time and remain fixed when outcomes mature; no clipping, future readings or replay outcomes are used to adjust them. Synthetic forecasts have no calibrated ranges.

CSV/JSON session exports and HTML reports retain available bounds and measured coverage. These exploratory ranges support inspection of model limitations; they do not support dosing or treatment decisions.
