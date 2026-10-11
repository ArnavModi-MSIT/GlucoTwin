# DCLP3 local release audit

Audited 11 October 2026. Source: **DCLP3 Public Dataset - Release 3 -
2022-08-04**. This is a source audit, with no model trained or cohort split
selected. The existing dashboard and BrisT1D results are unchanged.

## What is actually available

The extracted release contains 87 files (approximately 1.59 GB), including
50 pipe-delimited data tables, a data dictionary, study protocol, forms and
questionnaires. Inspected all 50 table schemas and fully scanned the consolidated
CGM, basal-rate, bolus and meter streams used below. The remaining raw CGM
source tables were inventoried, not fully reconciled against the consolidated
stream.

| Component | Verified local coverage |
|---|---|
| Participant roster | 170 enrolled; 168 randomized/completed, 2 dropped |
| Treatment groups | 112 closed-loop control (CLC), 56 sensor-augmented pump (SAP) |
| Consolidated CGM | 9,032,235 rows from 168 participants |
| Baseline CGM | 602,103 rows; approximately two weeks per participant |
| Post-randomization CGM | 8,430,132 rows; median calendar span 182.6 days |
| Pump basal-rate changes | 2,610,772 rows from 125 participants |
| Delivered boluses | 221,292 rows from 125 participants |
| CGM + basal + bolus intersection | 125 participants: 112 CLC and 13 SAP |
| Age, recorded sex, diagnosis age and reported daily insulin | Screening fields populated for all 170 enrolled participants |
| Physical examination | Screening visits: weight for 170, height for 169 participants |
| Local HbA1c | Numeric results for 170; tests before randomization for all 168 randomized participants |
| Central lab HbA1c | 504 results from 168 participants, at randomization/13-week/26-week visits |
| Meter carbohydrates | **Zero numeric entries** in all 25,344 meter rows |

The 125-person insulin intersection describes availability, not a finalized
training cohort. Numeric pump events overlap the post-randomization CGM
calendar span for all 125. This does not establish uninterrupted insulin
logging or prospective event arrival.

**Clinical fusion is feasible:** demographics, diabetes history, local HbA1c,
unit-normalized physical measurements and insulin context can be joined to
CGM by participant and dated visit. The physical-exam heart rate is a clinic
measurement, not a continuous wearable stream. No continuous HR, activity or
sleep stream was identified in the table schemas.

**Meal information is unavailable in the inspected event streams.** The meter
schema lists `Carbs`, but every value is empty. Pump boluses provide delivered
insulin, without meal carbohydrate amounts. Pump-setting carbohydrate ratios
are therapy parameters, not recorded meals. Do not replace absent meals with
zero-carbohydrate events or claim complete meal coverage.

## Source handling that must precede modeling

- The source dictionary identifies `cgm.txt` as the aggregation used for the
  primary manuscript. Use it as the starting CGM source; appending Dexcom,
  pump and other CGM tables would risk repeated observations.
- Files mix UTF-16 and UTF-8 encodings. CGM timestamps use SAS-style
  `DDMONYY:HH:MM:SS`; clinical and pump tables use ISO-style timestamps.
- For pump events, use `DataDtTm_adjusted` when present and original
  `DataDtTm` otherwise. Adjusted timestamps differ in 38,382 basal records
  and 3,107 bolus records. Retain correction provenance during import.
- Dates are deidentified. The dictionary documents one participant's baseline
  dates as inconsistent with enrollment and explicitly says the correct
  relative dates are unknown. Do not invent a date shift to link that baseline
  to clinical/pump events. A post-randomization-only first study avoids using
  this anomalous baseline phase; verify post-randomization joins separately.
- Source values include **5,690 readings coded 39 and 33,309 coded 401**.
  These are outside the pump dictionary's nominal exact-valued 40-400 mg/dL
  range. Preserve them with flags and resolve censoring semantics before
  regression/event labeling. They must not be silently treated as ordinary
  exact glucose measurements or generic missingness.
- The audit's 40-400 screen is descriptive, not a frozen exclusion rule.
  Within that screen there are 8,993,236 readings, with no duplicate or
  conflicting patient/phase/timestamp keys. Endpoint inclusion and extreme
  glucose handling remain decisions for the contract.
- Native cadence is approximately five minutes, with timestamp jitter.
  Post-randomization data have 8,365,791 intervals within 270-330 seconds,
  out of 8,394,484 retained intervals. There are 14,218 gaps over 15 minutes.
  Exact timestamp matches at +30/+60 minutes exist for only 5,029,292 and
  4,577,523 anchors, respectively. These are descriptive matches from reading
  time, before any history screen or availability delay. Declare a measured
  target matching policy before window preparation; do not interpolate labels.
- Basal rates are units/hour; boluses are units. A commanded rate is not an
  independently measured delivered total. Integrate rates only across
  trustworthy intervals, and handle gaps and extended boluses explicitly.
- `RecID` is not a globally unique bolus key: the source dictionary states
  that the bolus table combines two tables with repeated record IDs.
- Screening `Weight`/`Height` columns are empty; actual measurements are in
  `DiabPhysExam_a.txt`. Convert pounds/inches using declared units; one
  missing height remains missing.
- Join screening/physical-exam forms through `ParentLoginVisitID` and participant
  ID to `VisitInfo_a.txt`. The audit verified unique visit keys and matched
  all 170 screening forms. Preserve unknown/approximate-date flags.
- Central lab HbA1c has **no analysis date before randomization**. Median
  collection-to-analysis delay is 18 days (range 1-120). Do not make central
  results available at collection time. Local HbA1c has usable pre-randomization
  test dates, but a test date still does not prove result-arrival time.
- Exclude `gluIndices.txt` and future follow-up labs, events and questionnaire
  responses from baseline features. They summarize or occur after monitoring.

## Next controlled experiment

1. Freeze a DCLP3 contract for measured 30/60-minute targets, timestamp
   tolerance, input freshness, result availability, censoring and patient
   splits. Preserve the original streams and existing experiments.
2. Start with post-randomization CGM and historical clinical features across
   the 168 randomized participants, subject to the frozen quality rules.
3. Compare persistence, CGM-only Ridge/tree and clinical + CGM models on the
   same patients and rows. Test insulin additions on the 125-person linked
   subset with a matched CGM-only comparator.
4. Keep treatment groups visible in splits and reports: the insulin subset
   is strongly dominated by closed-loop treatment. Lower errors may reflect
   smoother controlled glucose rather than a better forecasting method.
5. Report participant MAE/RMSE, paired differences and low/high-glucose errors
   before deciding whether a neural model is warranted. Evaluate event warnings
   separately; larger data alone does not establish alert reliability.

The [DCLP3 contract and preparation](DCLP3_CONTRACT.md) now freeze patient roles
and generate development-only matrices. The [fixed CPU study](DCLP3_STUDY_V2.md)
has now completed. Published trajectory-average scores are not endpoint goals
or a guarantee of improvement over BrisT1D.

## Reproduce and inspect

From the `project` directory:

```powershell
python scripts/audit_dclp3.py
```

The script reads the extracted release in `data/raw/` and writes aggregate
[audit results](../reports/dclp3_audit.json). Participant records, the original
release and the local README text conversion remain ignored by Git. The
source questionnaires carry copyright notices; the project's code license
does not relicense those forms or the participant dataset.

[Official source](https://public.jaeb.org/dataset/573).
For research comparisons, see [dataset candidates](DATASET_SWITCH_CANDIDATES.md).
