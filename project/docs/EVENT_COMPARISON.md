# Independent high-event model comparison

Recorded 12 October 2026. This versioned development study gives CGM-only and
clinical + CGM + heart-rate XGBoost models independent, equal tuning budgets.
The dashboard continues to use the saved v2 models. No numerical forecasting
model, reserved-test result or operational-alert setting is changed.

## Result and decision

| Outer development metric | Fused | Independently tuned CGM-only |
|---|---:|---:|
| Evaluable episodes detected | 229 / 336 | 220 / 336 |
| Episode recall | 68.2% | 65.5% |
| Conservative precision | 52.8% | 57.9% |
| False alarms per eligible monitoring day | 0.979 | 0.770 |
| Median detected-event lead | 10 min | 5 min |
| Recall requiring at least ten minutes' warning | 36.6% | 27.1% |

The fused arm reproduced v2 **exactly**, including all inner-selection scores,
chosen configurations, cutoffs and per-patient event metrics. Active v2 files
were unchanged. Both arms selected `xgb_600_d3` in folds 1 and 3. In fold 2,
CGM-only selected `xgb_1200_d3_balanced`; fused retained `xgb_600_d3`.

Independent tuning changed the previous CGM ablation from 219 to 220 detected
episodes, with precision falling from 59.3% to 57.9% and false alarms increasing
from 0.726 to 0.770 per eligible day. It did **not** establish a better model.
Inner average precision and final episode-warning utility are different criteria.

| Paired fused-minus-CGM difference | Point estimate | Patient bootstrap 95% interval |
|---|---:|---:|
| Episode recall | +2.7 percentage points | -7.8 to +11.5 points |
| Conservative precision | -5.1 percentage points | -9.5 to -0.5 points |
| False alarms / eligible day | +0.210 | +0.038 to +0.392 |
| Recall with at least ten minutes' warning | +9.5 percentage points | +0.9 to +18.8 points |

In this development sample, fusion trades earlier warnings for more false
alarms and lower precision. Overall recall superiority is not established.
The useful-lead interval favors fusion, but the repeatedly inspected cohort and
multiple metrics limit this evidence. It does not isolate which clinical or
heart-rate feature helps, nor establish clinical benefit.

Only fused passes the pooled engineering gate; CGM-only misses its median-lead
requirement. Cutoff operating criteria with support waived pass in one of three
fused folds and two of three CGM folds. Neither arm passes the full-support
cutoff gate in any fold. **Keep the current research model; enable no operational
alerts or risk percentages.** A further model study should address useful lead
and false-alarm trade-offs using fitting/inner-validation patients, not retune
against these outer results. These results do not change numerical MAE.

CPU runtime was 264.18 seconds, sampled peak process memory 232.98 MiB. The
[aggregate report](../reports/event_comparison_v3.json) retains full selections,
cutoff outcomes, paired intervals, versions and source fingerprints.

## Method

- Reuse the original 27 development patients and three outer patient splits:
  15 fitting, three cutoff-setting and nine evaluation patients per fold.
  The six reserved patients' sensor files are never opened. The shared profile
  table is loaded, but only development rows are selected for features.
- Keep source bytes, feature construction, five-minute opportunities, known
  labels, missing-outcome handling and event rules unchanged. Each arm uses
  exactly the same opportunities and evaluable episodes.
- Independently select each arm's configuration from the original four XGBoost
  candidates using the same three inner patient folds. Selection maximizes mean
  inner-fold average precision. Each inner score pools its validation patients'
  rows; it is not a patient-macro score.
- Use the original training weights, cutoff selection over 101 score quantiles,
  5–30 minute warning window and 60-minute cooldown. Three cutoff patients cannot
  satisfy the full gate's five-patient support requirement; report the cutoff
  operating criteria with support waived separately from the full gate.
- Freeze all six model configurations and cutoffs before outer evaluation.
  This costs 72 inner fits plus six final fits, using CPU and eight threads.
- Bootstrap whole evaluation patients 2,000 times with identical draws for the
  two arms, seed 2026. Report fused-minus-CGM intervals for episode recall,
  conservative precision, false alarms per eligible day and recall requiring
  at least ten minutes of warning.

This is a repeated analysis of previously inspected development patients,
**not a new independent test or medical validation**. Point estimates and
patient-bootstrap intervals do not account for all prior research choices.

## Reproduce and preserve

The [protocol](../configs/event_comparison_v3.json) pins the original protocol
by SHA-256. After preparing the original event study and installing
`requirements-event.txt`, run from `project/`:

```powershell
python scripts/compare_event_models.py
$env:GLUCOTWIN_INTEGRATION='1'
python -m unittest discover -s tests -p test_event_comparison.py -v
```

Use a separate reproduction checkout with the v3 aggregate output and private
v3 output directory absent. The script refuses to overwrite either. Never
remove the original v2 inputs or models: they are the required reference.
Private fitted models, frozen selections, patient roles and per-patient metrics
are retained under `data/processed/event_comparison_v3/`, outside Git tracking.

The workflow requires exact reproduction of the fused v2 candidate choices,
inner scores, cutoffs and per-patient event counts. It verifies that protected
active files are unchanged before publishing the aggregate report. Tests cover
independent selection, patient-role boundaries, reserved sensor exclusion and
paired resampling, and reproduce the saved aggregate evidence.
