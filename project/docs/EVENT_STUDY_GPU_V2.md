# XGBoost onset study and cloud execution

Specified 10 October 2026 after reading the v1 development result. This is
explicitly a further exploratory comparison on the same development patients,
not a fresh independent validation. The original v1 protocol/report is retained.

Keep the v1 labels, timing, patient roles, inner selection, separate threshold
patients, outer evaluation, eight-thread cap and engineering gates. Compare
four fixed XGBoost configurations: 600/depth3, 800/depth5, 1,200/depth3 balanced,
and 800/depth4 balanced. All use learning rate 0.03, minimum child weight 10,
subsample/column sample 0.8, L2 10 and seed 2026. Fit all development examples.
Patient and class weights use only fitting patients. Balanced candidates are
ranking models; outputs are not calibrated risk percentages.

Local CPU execution:

```powershell
python -m pip install -r requirements-experiments.txt
python scripts/run_event_study.py --study gpu_v2 --device cpu
```

The notebook `notebooks/event_study_gpu.ipynb` runs the same study with
`--device cuda` in a private Kaggle/Colab environment containing the current
project, legitimately obtained source data and prepared local manifests.
XGBoost enables its GPU histogram algorithm with `device=cuda` and
`tree_method=hist`: [official GPU documentation](https://xgboost.readthedocs.io/en/stable/gpu/).
The runner checks the fitted device and refuses silent CPU fallback. CUDA/build
compatibility must be verified in that runtime; a notebook file is not evidence
of successful cloud execution.

CPU and GPU runs write the same v2 report path within their own workspaces;
retain/export both separately when comparing devices. Do not overwrite v1 or
select a favorable backend result using reserved test patients. Cloud scores
and latency have not been measured locally. No accounts are created and no
data are uploaded automatically. Keep patient-level data, models and manifests
private; publish aggregate evidence only.
