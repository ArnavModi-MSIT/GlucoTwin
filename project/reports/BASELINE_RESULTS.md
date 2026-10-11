# CPU baseline results

Run: 8 October 2026. Development validation only; final test models have not been scored. Exploratory CGMacros reconstructed five-minute data, with upstream native-sample uncertainty as described in `DATA_CONTRACT.md`.

## Prepared data

33 admitted participants, 84,095 usable +60-minute examples:

| Partition | Patients | Rows | High endpoint rows | Current <=180 and future >180 |
|---|---:|---:|---:|---:|
| Training | 21 | 53,505 | 7,308 | 2,956 |
| Validation | 6 | 15,217 | 2,538 | 868 |
| Reserved test | 6 | 15,373 | 3,423 | 675 |

Test counts are preparation statistics, not prediction-quality scores. Overlapping examples are not independent events. Valid consecutive-five-minute upcrossing counts after warmup are 408/108/102 respectively; no clinical episode-duration or cooldown rule has been imposed.

## Validation comparison

Ridge alpha fixed at 10; train-only median imputation, missingness indicators and standardization. No parameter sweep. All models use identical admissible validation rows. Persistence repeats current glucose; slope extrapolates the causal trailing 30-minute slope for 60 minutes without clipping.

| Model | MAE (mg/dL) | RMSE (mg/dL) | Patient-macro MAE |
|---|---:|---:|---:|
| Persistence | 19.99 | 31.52 | 19.95 |
| Slope extrapolation | 32.10 | 48.98 | 32.07 |
| Ridge clinical only | 27.94 | 39.87 | 27.93 |
| Ridge CGM only | 19.69 | 29.32 | 19.67 |
| Ridge CGM + clinical | 19.21 | 28.41 | 19.20 |
| Ridge CGM + clinical + HR | 19.00 | 28.13 | 18.98 |

The fused Ridge reduces validation MAE by 0.99 mg/dL (~4.95%) versus persistence. Clinical features improve the CGM-only Ridge by 0.48 mg/dL in this split; HR adds 0.21 mg/dL. With only six validation patients and a structurally selected cohort, this is preliminary evidence, not proof of general clinical fusion benefit.

Important error slices:

- Type 2 HbA1c band (two validation patients, 5,092 rows): persistence MAE 28.25; fused Ridge 26.24. CGM-only Ridge 25.76 is better than fused Ridge in this slice.
- Future >180 (2,538 rows): persistence MAE 47.39; fused Ridge 44.85. Errors remain substantial.
- Future <70 (39 rows): persistence MAE 20.26; fused Ridge 38.80. All Ridge variants worsen this small low-glucose slice. Do not claim uniform improvement, reliable hypoglycemia warning or suitability for treatment.

The best average-MAE candidate is therefore not automatically the final selected model. Next compare a bounded nonlinear regressor and investigate errors using development data only. Calibration/classification and final test evaluation remain deferred.

## Verification and runtime

Five meaningful tests passed: future-edit invariance and prefix/batch parity under frozen metadata; missing-current rejection; internal-gap rejection; timestamp-based grid selection; exact-target and patient-split checks. These test our feature pipeline, not unobserved upstream sensor processing.

Feature preparation took 2.43 seconds. Baseline training plus validation inference took 1.37 seconds, using a four-thread numeric-library cap. Sampled peak process RSS was 282.55 MiB; a sampling monitor may miss very brief peaks and this excludes the dashboard. Each Ridge fit/predict took 0.11–0.60 seconds. No GPU was used.

Source hashes and prepared-data summaries are saved separately. Raw and processed patient records and locally saved model binaries are Git-ignored. No app has been built yet.

## Reproduce

Run from project root with pandas/NumPy for preparation and scikit-learn/joblib/psutil/threadpoolctl for training:

```powershell
python scripts/prepare_features.py
python -m unittest discover -s tests -v
python scripts/train_baselines.py
```

Tested preparation with bundled Python/pandas 3.0.1/NumPy 2.3.5. Training used Python 3.10.11, pandas 2.3.3, NumPy 2.2.6 and scikit-learn 1.7.2 because the bundled runtime lacks scikit-learn. A single pinned project environment is still to establish. Full numerical results: `reports/baseline_validation.json`; per-patient metrics: `reports/baseline_validation_patient_metrics.csv`.
