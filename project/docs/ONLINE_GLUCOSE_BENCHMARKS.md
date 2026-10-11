# Online glucose forecasting benchmarks

Checked 11 October 2026. External results are author-reported, not reproduced
locally. Code inspection verifies metric definitions, not numerical reproduction.

## Our current reference

BrisT1D v2 full-input delta XGBoost, mg/dL:

| Horizon | Row-pooled MAE | Row-pooled RMSE | Mean patient MAE |
|---|---:|---:|---:|
| 30 min | 19.92 | 27.84 | 20.74 |
| 60 min | 29.43 | 40.25 | 30.45 |

Source: [v2 study](BRIST1D_STUDY_V2.md). Sixteen development patients,
four patient-disjoint folds; four reserved patients remain unscored. Exact
endpoint targets, native 5/15-minute cadence, declared input availability
delays, identical evaluation rows across methods. These are offline research
results, not the dashboard's deployed models or proven event-warning quality.

## Comparable concepts, different protocols

| Source | Dataset/model | Reported 30-min MAE | Reported 60-min MAE | Meaning |
|---|---|---:|---:|---|
| [GlucoPulse saved results](https://github.com/srikarjy/GlucoPulse/blob/main/model/results/tft_eval.json) | AZT1D / TFT | 17.61 | 27.48 | Endpoint errors; four held-out patients |
| [Transformer study](https://arxiv.org/html/2505.08821v1) | OhioT1DM / Crossformer at 30, PatchTST at 60 | 9.67 | 16.38 | Average over the whole future trajectory; one-week input history |

All displayed MAEs are mg/dL. The Transformer rows use different architectures
at the two horizons. Its models train on DCLP3 and test externally on OhioT1DM.
Equations 4-6 and inspected [metrics.py](https://github.com/Center-for-Diabetes-Technology/TransformerBasedBGPrediction/blob/main/utils/metrics.py)
and [evaluation code](https://github.com/Center-for-Diabetes-Technology/TransformerBasedBGPrediction/blob/main/exp/exp_long_term_forecasting.py)
confirm averaging across future steps. This is not an exact +60-minute MAE.

GlucoPulse inspection covered `train.py`, `splits.py`, `evaluate.py`,
`baseline.py`, the two results JSON files and `spark/feature_job.py`.
Its saved endpoint RMSEs are 25.47/37.65. Cautions: baseline and TFT row
counts differ; training code constructs validation from train plus validation
patients; quality filtering excludes some weeks. Test patients are separate.
These details prevent treating its published gain as a controlled comparison
with our pipeline. [Training code](https://github.com/srikarjy/GlucoPulse/blob/main/model/train.py),
[baseline results](https://github.com/srikarjy/GlucoPulse/blob/main/model/results/baseline_metrics.json).

## Same source dataset: BrisT1D competition

The [winning write-up](https://www.kaggle.com/competitions/brist1d/writeups/sebastian-cuya-1st-place-solution-single-lgbm-mode)
reports a single LightGBM, private leaderboard RMSE 2.3615 mmol/L,
approximately **42.55 mg/dL at +60 minutes**. This is RMSE, not MAE.
The [official final leaderboard](https://www.kaggle.com/c/brist1d/leaderboard)
confirms the score. The author extracted training examples from earlier
readings within exposed test histories. This protocol differs from our fixed
patient-disjoint study; our RMSE 40.25 does not demonstrate beating that winner.
The write-up was read, but its linked implementation was not inspected.

## Exceptional claim requiring reproduction

A [2026 Physio-CDE/CRC/CVaR-PPO paper](https://portalcris.lsmuni.lt/server/api/core/bitstreams/f49e9a66-8f29-4cfd-9d9c-e4de40b01f5c/content)
reports BrisT1D MAE 3.4/3.9 in Table 3. However, it specifies a 24-person
16/4/4 device-data split, whereas the [original dataset paper](https://arxiv.org/pdf/2507.17757)
identifies four participants without sufficient device data. Normalization
and mean-versus-median wording also need clarification. No implementation
was found in the inspected paper. Treat this as an unverified published
claim, not a reproducible target.

## Implications

For a dataset change, see [other dataset candidates](DATASET_SWITCH_CANDIDATES.md)
with independently reproduced endpoint scores, access links and a proposed
DCLP3 pilot. The earlier BrisT1D comparisons do not exhaust the alternatives.

Lower published errors exist, but architecture alone does not explain the
differences. A fair experiment must match endpoint definition, patients,
cadence, availability delays, admitted rows and aggregation. Our next model
comparison should retain those controls. Low-target errors and episode-warning
recall, precision, false alarms and lead time still need separate improvement.
