# Event-prediction progress

Completed 10 October 2026. Two fixed, separately versioned development studies
ran locally on CPU. Across the studies, 102 classifiers were fitted: 90 inner
model-selection fits and 12 outer fused/sensor-only fits. No sampling cap was
used. The 27 development patients provided 58,880 known-label opportunities;
225 opportunities with incomplete future observations were excluded from
training, while past-eligible evaluation opportunities remained eligible.

The v1 pooled fused result failed the recall gate. XGBoost v2's pooled fused
result met the engineering criteria: 229/336 episodes detected, 68.2% recall,
52.8% conservative precision, 0.98 false alarms per eligible day, median lead
10 minutes. The four-configuration inner selection chose 600-tree/depth3
XGBoost in each outer fold; increasing depth/trees did not win inner AP.

This is not permission to deploy. Two threshold-setting folds failed. For the
XGBoost fused result, patient-bootstrap 95% intervals were recall 59.2–75.4%,
precision 44.5–60.3%, and false alarms 0.75–1.22 per eligible day. The matched
fusion-minus-sensor-only recall interval was -6.7 to +11.6 percentage points.
More consistent gain from historical fields has not been established.

Next work should establish a larger cohort with trustworthy historical and
meal/insulin availability, or separately evaluate fixed sequence models using
the same patient boundaries. Preserve every current result and the six reserved
patients. Additional model searches on these same patients remain exploratory;
neither GPU speed nor favorable pooled point estimates provide independent
medical validation. Final held-out evaluation must follow a single frozen
selection and threshold protocol, not another tuning loop.

The Kaggle/Colab notebook and CUDA backend are prepared; only CPU execution has
been performed. No cloud accounts were accessed and no data were uploaded.
The existing Ridge dashboard and disabled warning capabilities are retained.

Verification: the 51-test local suite passed before two additional saved-artifact
checks were added; both new checks passed separately (53 passing checks total).
Saved XGBoost inference reproduced the reported first outer fold episode counts.
Notebook code syntax and cleared outputs were checked. Cloud execution and
external clinical validation remain unverified. Changes are local, not pushed.
