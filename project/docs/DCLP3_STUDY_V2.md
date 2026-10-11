# DCLP3 fixed CPU comparison

Completed 11 October 2026. Four patient-disjoint development folds; 134 participants for clinical fusion and a matched 100-person pump subset. The 34 reserved participants were not scored. Units mg/dL.

Every model uses the same evaluation rows within its cohort/horizon. Training uses at most 4,000 uniformly sampled rows per patient with equal patient total weight. Ridge predicts the endpoint directly; XGBoost predicts the change from the latest available glucose. Model settings were fixed before fitting; no parameter sweep or model promotion occurred.

Nominal +30/+60-minute targets are observed readings within ±30 seconds. There is no label interpolation. Five-minute input delay means approximately 35/65-minute lookahead from the latest measurement. Boundary-coded targets are counted separately and omitted from point-error scores.

## What the results establish

CGM-only XGBoost has the lowest overall participant MAE in the full cohort (17.53/27.47 at 30/60 minutes), versus persistence 20.92/32.32. Clinical-profile additions show no convincing overall gain: their paired intervals include zero. In the matched pump subset, adding insulin to clinical + CGM XGBoost reduces participant MAE by 0.105/0.222 mg/dL (95% intervals [-0.128,-0.084]/[-0.279,-0.171]). These are small point-forecast gains, conditional on this fixed configuration.

Low-target errors remain a major weakness. Full-cohort CGM-only XGBoost has low-target participant MAE 29.13/54.31 versus persistence 26.68/50.04. Ridge has lower 30-minute low/high-target errors and RMSE than XGBoost, despite slightly worse overall MAE. The numerical MAE winner does not dominate every error metric. This dataset switch has not established reliable adverse-event prediction.

## All development participants

| Horizon | Method | Pooled MAE | Participant MAE | Participant RMSE | Low-target MAE | High-target MAE | Strict-subset MAE |
|---|---|---:|---:|---:|---:|---:|---:|
| 30 min | persistence | 20.82 | 20.92 | 28.87 | 26.68 | 26.66 | 20.93 |
| 30 min | ridge_cgm_only | 17.63 | 17.71 | 24.40 | 26.12 | 21.84 | 17.68 |
| 30 min | ridge_cgm_profile | 17.61 | 17.70 | 24.33 | 26.47 | 21.99 | 17.67 |
| 30 min | xgb_delta_cgm_only | 17.44 | 17.53 | 24.71 | 29.13 | 22.97 | 17.52 |
| 30 min | xgb_delta_cgm_profile | 17.45 | 17.54 | 24.70 | 29.27 | 23.09 | 17.53 |
| 60 min | persistence | 32.16 | 32.32 | 43.60 | 50.04 | 42.88 | 32.32 |
| 60 min | ridge_cgm_only | 28.42 | 28.57 | 37.92 | 55.76 | 37.77 | 28.56 |
| 60 min | ridge_cgm_profile | 28.35 | 28.51 | 37.70 | 56.16 | 38.21 | 28.50 |
| 60 min | xgb_delta_cgm_only | 27.32 | 27.47 | 37.48 | 54.31 | 39.58 | 27.48 |
| 60 min | xgb_delta_cgm_profile | 27.32 | 27.48 | 37.39 | 54.93 | 39.86 | 27.48 |

## Pump-linked participants only

All three input arms below fit and evaluate within the same 100-person subset (89 CLC, 11 SAP). Do not interpret a difference between this table and the 134-person table as an insulin-input gain.

| Horizon | Method | Pooled MAE | Participant MAE | Participant RMSE | Low-target MAE | High-target MAE | Strict-subset MAE |
|---|---|---:|---:|---:|---:|---:|---:|
| 30 min | persistence | 20.59 | 20.67 | 28.50 | 28.37 | 27.02 | 20.67 |
| 30 min | ridge_cgm_only | 17.41 | 17.48 | 24.14 | 27.32 | 22.25 | 17.43 |
| 30 min | ridge_cgm_profile | 17.39 | 17.46 | 24.05 | 27.72 | 22.45 | 17.42 |
| 30 min | ridge_cgm_profile_insulin | 17.37 | 17.44 | 24.01 | 27.73 | 22.48 | 17.39 |
| 30 min | xgb_delta_cgm_only | 17.22 | 17.29 | 24.40 | 30.28 | 23.41 | 17.27 |
| 30 min | xgb_delta_cgm_profile | 17.23 | 17.30 | 24.39 | 30.46 | 23.57 | 17.28 |
| 30 min | xgb_delta_cgm_profile_insulin | 17.13 | 17.19 | 24.26 | 30.60 | 23.41 | 17.18 |
| 60 min | persistence | 31.78 | 31.91 | 43.01 | 53.51 | 43.53 | 31.91 |
| 60 min | ridge_cgm_only | 27.89 | 28.02 | 37.34 | 58.10 | 38.55 | 28.00 |
| 60 min | ridge_cgm_profile | 27.79 | 27.92 | 37.06 | 58.47 | 39.12 | 27.91 |
| 60 min | ridge_cgm_profile_insulin | 27.73 | 27.85 | 36.98 | 58.30 | 39.22 | 27.84 |
| 60 min | xgb_delta_cgm_only | 26.82 | 26.95 | 36.88 | 56.43 | 40.48 | 26.96 |
| 60 min | xgb_delta_cgm_profile | 26.82 | 26.95 | 36.77 | 57.00 | 40.84 | 26.95 |
| 60 min | xgb_delta_cgm_profile_insulin | 26.60 | 26.73 | 36.54 | 57.01 | 40.63 | 26.73 |

## Paired effects of additional inputs

Differences are candidate minus reference in participant MAE; negative means improvement. Intervals use 2,000 participant bootstrap samples, conditional on these fitted models. They do not capture all variability from refitting the training cohort.

| Horizon | Cohort | Comparison | Overall difference (95% interval) | Low-target difference | High-target difference |
|---|---|---|---:|---:|---:|
| 30 min | all_clinical | ridge_cgm_profile_versus_ridge_cgm_only | -0.008 [-0.068, +0.057] | +0.345 | +0.149 |
| 30 min | all_clinical | xgb_delta_cgm_profile_versus_xgb_delta_cgm_only | +0.011 [-0.006, +0.027] | +0.138 | +0.119 |
| 30 min | pump_linked | ridge_cgm_profile_versus_ridge_cgm_only | -0.018 [-0.094, +0.060] | +0.401 | +0.194 |
| 30 min | pump_linked | ridge_cgm_profile_insulin_versus_ridge_cgm_profile | -0.023 [-0.052, +0.007] | +0.012 | +0.036 |
| 30 min | pump_linked | xgb_delta_cgm_profile_versus_xgb_delta_cgm_only | +0.009 [-0.019, +0.042] | +0.184 | +0.154 |
| 30 min | pump_linked | xgb_delta_cgm_profile_insulin_versus_xgb_delta_cgm_profile | -0.105 [-0.128, -0.084] | +0.145 | -0.156 |
| 60 min | all_clinical | ridge_cgm_profile_versus_ridge_cgm_only | -0.062 [-0.208, +0.095] | +0.404 | +0.438 |
| 60 min | all_clinical | xgb_delta_cgm_profile_versus_xgb_delta_cgm_only | +0.002 [-0.048, +0.056] | +0.615 | +0.282 |
| 60 min | pump_linked | ridge_cgm_profile_versus_ridge_cgm_only | -0.097 [-0.285, +0.087] | +0.373 | +0.572 |
| 60 min | pump_linked | ridge_cgm_profile_insulin_versus_ridge_cgm_profile | -0.069 [-0.138, +0.001] | -0.172 | +0.095 |
| 60 min | pump_linked | xgb_delta_cgm_profile_versus_xgb_delta_cgm_only | -0.006 [-0.095, +0.098] | +0.575 | +0.360 |
| 60 min | pump_linked | xgb_delta_cgm_profile_insulin_versus_xgb_delta_cgm_profile | -0.222 [-0.279, -0.171] | +0.007 | -0.212 |

## Treatment-group context

| Horizon | Cohort | Treatment | Method | Participants | Participant MAE |
|---|---|---|---|---:|---:|
| 30 min | all_clinical | CLC | persistence | 89 | 20.73 |
| 30 min | all_clinical | CLC | xgb_delta_cgm_only | 89 | 17.31 |
| 30 min | all_clinical | CLC | xgb_delta_cgm_profile | 89 | 17.31 |
| 30 min | all_clinical | SAP | persistence | 45 | 21.30 |
| 30 min | all_clinical | SAP | xgb_delta_cgm_only | 45 | 17.96 |
| 30 min | all_clinical | SAP | xgb_delta_cgm_profile | 45 | 17.99 |
| 30 min | pump_linked | CLC | persistence | 89 | 20.73 |
| 30 min | pump_linked | CLC | xgb_delta_cgm_only | 89 | 17.30 |
| 30 min | pump_linked | CLC | xgb_delta_cgm_profile | 89 | 17.31 |
| 30 min | pump_linked | CLC | xgb_delta_cgm_profile_insulin | 89 | 17.22 |
| 30 min | pump_linked | SAP | persistence | 11 | 20.21 |
| 30 min | pump_linked | SAP | xgb_delta_cgm_only | 11 | 17.24 |
| 30 min | pump_linked | SAP | xgb_delta_cgm_profile | 11 | 17.25 |
| 30 min | pump_linked | SAP | xgb_delta_cgm_profile_insulin | 11 | 17.03 |
| 60 min | all_clinical | CLC | persistence | 89 | 31.97 |
| 60 min | all_clinical | CLC | xgb_delta_cgm_only | 89 | 26.88 |
| 60 min | all_clinical | CLC | xgb_delta_cgm_profile | 89 | 26.85 |
| 60 min | all_clinical | SAP | persistence | 45 | 33.01 |
| 60 min | all_clinical | SAP | xgb_delta_cgm_only | 45 | 28.65 |
| 60 min | all_clinical | SAP | xgb_delta_cgm_profile | 45 | 28.71 |
| 60 min | pump_linked | CLC | persistence | 89 | 31.97 |
| 60 min | pump_linked | CLC | xgb_delta_cgm_only | 89 | 26.83 |
| 60 min | pump_linked | CLC | xgb_delta_cgm_profile | 89 | 26.83 |
| 60 min | pump_linked | CLC | xgb_delta_cgm_profile_insulin | 89 | 26.65 |
| 60 min | pump_linked | SAP | persistence | 11 | 31.47 |
| 60 min | pump_linked | SAP | xgb_delta_cgm_only | 11 | 27.94 |
| 60 min | pump_linked | SAP | xgb_delta_cgm_profile | 11 | 27.89 |
| 60 min | pump_linked | SAP | xgb_delta_cgm_profile_insulin | 11 | 27.36 |

## Reproduce

From the `project` directory, after preparing v2:

```powershell
python scripts/run_dclp3_study.py
python scripts/verify_dclp3_study.py
python scripts/summarize_dclp3_study.py
```

The runner freezes its implementation, cache, role and configuration fingerprints before fitting. Matching saved local models can be reused on rerun; changed execution fingerprints are rejected. Source records, participant predictions and model files stay local and ignored by Git.

## Verification and limits

Training completed locally in 2206.1 seconds with 8 threads. Sampled peak resident memory was 4509.8 MiB. 80 saved models and 80 training-only preprocessors were checked, with 1280 inference parity probes. Overall, low/high-target, current-glucose, strict-timestamp and treatment-group scores and paired intervals were recomputed from matched predictions.

These are retrospective development results, not medical validation. Point MAE is distinct from episode recall, false alarms and useful warning lead time. No adverse-event classifier, calibrated probability or operational alert was enabled. No dashboard model was replaced.

The pump subset is dominated by closed-loop therapy; stable commanded basal states may be hidden by the conservative 30-minute freshness rule. Meal logs are absent. Clinical and sensor availability delays are assumptions. Lower errors on DCLP3 than on a different cohort do not establish that the model itself improved. The ±30-second subset and omitted boundary-coded targets must accompany point-error claims.

[Complete aggregate results](../reports/dclp3_study_v2.json), [verification](../reports/dclp3_study_v2_checks.json), [frozen preparation contract](DCLP3_CONTRACT.md).
