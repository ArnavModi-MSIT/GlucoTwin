# High-event error audit

Recorded 12 October 2026. This audit diagnoses the saved fused XGBoost v2 model
on its existing cutoff-setting patients. It does not fit a model, tune a cutoff,
score outer-evaluation patients again, or load reserved sensor files.

## Scope and verification

- Three frozen models; three cutoff patients per fold, eight unique patients
  across nine patient-fold exposures. One patient appears in two cutoff folds.
- Every fold's aggregate counts and metrics reproduce its saved cutoff-setting
  report within numerical tolerance.
- Protocol, source, roles and model fingerprints are verified. Only cutoff
  sensor files are opened; the shared profile table is loaded, but only cutoff
  rows are selected for features.
- All scores, thresholds, five-minute opportunities, sustained-onset labels,
  missing-outcome handling and the 60-minute cooldown remain unchanged.
- Because these patients selected the cutoffs, these are **diagnostic counts,
  not validation results**. They do not replace the reported 68.2% development
  recall or 52.8% conservative precision.

## What failed

Across patient-fold exposures: 137 alarms, 89 matched events, 47 false alarms,
one unknown alarm and no redundant alarms. There were 143 evaluable episodes,
of which 54 were missed; another 15 episodes had no eligible warning opportunity.

| False-alarm category | Count | Share of 47 false alarms |
|---|---:|---:|
| No reading above 180 in the 5–30 minute warning window | 31 | 66.0% |
| High readings in the window, but no qualifying sustained onset | 13 | 27.7% |
| Qualifying onset occurred more than 30 and at most 60 minutes later | 3 | 6.4% |
| Qualifying onset had already occurred within the preceding 30 minutes | 0 | 0.0% |

The second category can include brief excursions or a failure of the prior-normal
requirement. It is not evidence that all 13 alarms predict clinically meaningful
events. Categories are mutually exclusive, with the priority documented in the
aggregate report. Future measurements describe errors retrospectively and must
never become model inputs or revised labels.

| Missed evaluable episode | Count | Share of 54 misses |
|---|---:|---:|
| No eligible score crossed its frozen cutoff | 52 | 96.3% |
| A score crossed the cutoff, but cooldown suppressed the alarm | 2 | 3.7% |

## Decision

Keep the working model and reported scores unchanged. Shortening cooldown has
limited scope to recover these misses and can increase repeated false alarms.
Extending the warning window solely to convert the three early alarms into hits
would change the endpoint rather than demonstrate a better model. Lowering a
cutoff trades precision for recall; this audit does not establish a better point.

The next bounded comparison should give CGM-only and fused models equal,
independent inner-selection budgets before claiming a fusion benefit. Retain
the current version as the reference. Any subsequent feature/model change needs
a separately versioned protocol with fixed patient roles and admission rules,
paired error/event reporting, and untouched reserved patients. Do not tune that
comparison against the error categories from outer-evaluation patients.

That follow-up is recorded in the separate
[independent tuning comparison](EVENT_COMPARISON.md); this diagnostic audit and
its original counts remain unchanged.

## Reproduce

After the existing event study has been prepared, run from `arnavmodi23_MSIT/`:

```powershell
python scripts/audit_high_events.py
python -m unittest discover -s tests -p test_event_audit.py -v
```

The audit refuses to overwrite an existing checkpoint. Use a separate checkout
with the output file absent to reproduce it. See the
[aggregate audit and fingerprints](../reports/high_event_audit_v1.json).
