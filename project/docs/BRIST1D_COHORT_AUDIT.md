# BrisT1D full processed-cohort audit

Audited locally on 10 October 2026. The downloaded processed release is suitable
for designing a separate retrospective Type 1 benchmark. Recorded input
availability, substantial missing streams and mixed CGM cadence still require
explicit modeling rules. This audit provides no prediction score or evidence
that the dataset improves the existing models.

Source: [University of Bristol release](https://data.bris.ac.uk/data/dataset/33z5jc8fa6tob21ptrugzqog08)
and [source schema](https://data.bris.ac.uk/datasets/33z5jc8fa6tob21ptrugzqog08/README.txt).
Processed data are CC BY 4.0. The source README describes a study of 24 people;
the actual open processed release supplies 20 participant files. All 20 files
link uniquely to the 24-row demographics table. Four metadata entries have no
downloaded sensor file. Participant ages in the processed cohort range from
18 to 26; this population differs from the existing RBG cohort.

## Verified contents

The audit read all 2,875,613 source rows, preserving separate device rows and
native timestamps. It produced these reconciled observations:

| Channel | Retained unambiguous, numerically valid timestamps | Participants with observations |
|---|---:|---:|
| Glucose | 847,956 | 20 |
| Insulin | 931,284 | 19 |
| Recorded carbohydrates | 17,010 | 20 |
| Heart rate | 677,260 | 20 |
| Distance | 470,009 | 20 |
| Steps | 467,454 | 20 |
| Calories | 892,386 | 20 |

There are 1,066,990 repeated timestamp rows across devices. These do not imply
that the rows are duplicate glucose measurements: each channel must be joined
separately. Different values at the same participant/channel/time were excluded:
309 glucose timestamps, 107 insulin timestamps and two carbohydrate timestamps.
Identical duplicate observations were reconciled. Two negative insulin rows
were excluded. One source row lacks a device label and remains an explicit
source-quality issue to resolve during preparation; its values are not invented.

Fifteen participants have a modal CGM cadence of five minutes; five have a
15-minute cadence. Insulin streams have a five-minute modal cadence for all
19 participants who have them; HR has a five-minute modal cadence for all 20.
Glucose has 7,354 observed gaps longer than 15 minutes, including a longest
gap of about 37.2 days. Source spans and calendar days are not continuous
monitoring exposure. No gaps were interpolated or resampled during this audit.

## Input overlap and availability

Across the 847,956 retained glucose timestamps:

| Observation within the preceding five minutes, including the anchor | Count | Fraction of glucose timestamps |
|---|---:|---:|
| Insulin | 683,958 | 80.66% |
| Heart rate | 500,290 | 59.00% |
| Both insulin and HR | 411,466 | 48.52% |
| Steps | 347,653 | 41.00% |

The pilot participant had nearly complete insulin coverage and 96.1% HR
overlap, which does not describe the full cohort. One participant has no
recorded insulin stream; others have only partial overlap. Carb records are
intermittent user reports, not a continuous sensor stream. A missing record
must remain unreported, not become zero grams or proof that no meal occurred.
Recorded zero insulin doses, in contrast, are real observations.

The source timestamp is a measurement/event time and sometimes an interval-end
time. There is no entry/upload timestamp proving when a meal or dose became
available to a live application. As-of overlap is therefore descriptive, not
proof of prospective availability. The aggregate JSON also reports assumed
0/5/15/30-minute observation delays under a fixed 30-minute freshness limit.
Those scenarios measure coverage under stated assumptions, not actual ingestion
latency. At a delay equal to that freshness limit, only exact-age boundary
matches qualify; that result should not be interpreted as a measured outage.

## Potential measured targets

A descriptive history screen requires one hour of source warm-up, at least
80% of the expected inclusive past-hour observations at the participant's
native modal cadence, and no observed past-hour gap longer than two cadence
intervals. Future labels are exact observed samples, with no interpolation.

| Horizon from the glucose observation timestamp | Exact targets passing the history screen | Target below 70 mg/dL | Target above 180 mg/dL |
|---|---:|---:|---:|
| 30 minutes | 772,705 | 13,516 | 213,965 |
| 60 minutes | 755,029 | 13,075 | 207,406 |

All 20 participants have screened targets in both horizons and both target
slices. These counts include the whole downloaded cohort and precede any
frozen role assignment; no model was fitted or selected. They are overlapping
potential target rows, not independent adverse-event episodes, and source-time
anchors do not establish an operational issuance or ingestion timestamp.
The final preparation must reconcile its declared issue time, sensor/action
delay assumptions and target horizon rather than copy a different dataset's grid.

## Historical profile semantics

Age links successfully for every processed participant. Self-reported gender
includes non-binary responses and is not a recorded biological-sex variable;
those responses remain explicit categories. Diabetes duration is an exact
numeric year statement for 18 participants; two entries contain approximate or
fractional free text and are preserved without silently rounding them. The
baseline availability of questionnaire fields must be declared as an assumption
unless source collection times are verified. Ethnicity is not needed for the
initial proposed feature comparison.

## Next experiment

1. Freeze patient roles and a separate BrisT1D prediction/availability contract
   before selecting models. Preserve the existing CGMacros/RBG reserved patients.
2. Build past-only features at native observation anchors, with explicit
   missingness and channel freshness. Keep unreported food and absent insulin
   distinct from recorded zero; do not fill source glucose gaps with future values.
3. Compare CGM plus linked historical profile, then added insulin, then added
   recorded carbs/wearables on identical evaluation rows. Report full-cohort
   coverage and any restricted-input subset separately.
4. Evaluate patient adaptation using only matured past outcomes. Select on
   development patients; keep the final patient reserve for frozen evaluation.
5. Report patient-level MAE/RMSE, high/low errors and severe-error tails alongside
   aggregate MAE. Changing datasets alone is not evidence of improvement over RBG.

## Artifacts and checks

- [Aggregate results](../reports/brist1d_cohort_audit.json).
- [Audit implementation](../scripts/audit_brist1d_cohort.py).
- [Synthetic checks](../tests/test_brist1d_cohort_audit.py).
- Linked participant profiles, diagnostics and source hashes are in an ignored
  private data artifact. The earlier one-participant audit remains unchanged.

Run from `project/`:

```powershell
python scripts/audit_brist1d_cohort.py
python -m unittest discover -s tests -p "test_brist1d*" -v
```

The full audit completed on CPU in approximately eight seconds; sampled process
RSS after participant audits was about 128 MiB, not a continuously measured
peak. Synthetic checks cover conflicting readings, explicit zero actions,
missing meals, past-only delay alignment, exact native-cadence targets, metadata
semantics/linkage and omission of linked participant details from public output.
Public/private counts reconcile for all seven channels. Dashboard models and
predictions were unchanged; no model training or GitHub push was performed.

After this audit, a separate [fixed CPU study](BRIST1D_STUDY_V1.md) was completed
under the [frozen native-cadence contract](BRIST1D_DATA_CONTRACT.md). Its modest
input gains and failed linear-model results are recorded separately; they do
not change the descriptive audit counts above.
