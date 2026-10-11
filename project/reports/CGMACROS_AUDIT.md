# CGMacros downloaded-file audit

Run: 8 October 2026. Source: downloaded CSV members of the official PhysioNet v1.0.0 archive. Raw files were not modified. Script: `scripts/audit_cgmacros.py`; numerical results: `reports/cgmacros_audit.json`; patient summary: `reports/cgmacros_patient_audit.csv`; source SHA256 hashes: `reports/cgmacros_file_hashes.json`.

## Verdict

**Clinical-to-sensor linkage passes. Forecast development is plausible, but causal availability of interpolated values remains unresolved.** Do not start claiming real-time validation or use the supplied one-minute series blindly as live observations.

## Actual coverage

| Check | Result |
|---|---:|
| Participant sensor files | 45 |
| Clinical profile rows | 45 |
| Sensor participants with exactly one profile | 45/45 |
| Missing or duplicate profile IDs | 0 |
| Total sensor rows | 687,580 |
| Timestamp parse failures / duplicate timestamps / reverse steps | 0 / 0 / 0 |
| Per-participant elapsed span | 7.23–19.15 days; median 10.63 |
| Timestamp jumps greater than one minute | 1,155 |
| Largest timestamp jump | 901 minutes |
| Logged meal rows | 1,706 |

Elapsed span includes gaps; it is not equivalent to continuous observed duration. The published approximately ten-day design does not describe every file's exact span. HbA1c bands reproduce the reported 15 below 5.7, 16 between 5.7 and 6.4 inclusive, and 14 above 6.4. These are dataset bands, not diagnoses newly assigned by this audit.

## Missingness and different schemas

| Field | Participant files containing column | Unavailable across all rows |
|---|---:|---:|
| Dexcom glucose | 45 | 8.40% |
| Libre glucose | 45 | 0.032% |
| Heart rate | 45 | 11.25% |
| Activity calories | 44 | 5.16% |
| METs | 34 | 27.12% |
| Intensity | 11 | 77.21% |
| Steps | 1 | 99.18% |

Unavailable includes missing cells and rows from files lacking the column. **Correction to the initial dictionary-based description: one file does contain Steps.** It is not a usable cohort-wide step stream. METs and Intensity are not automatically interchangeable; their definition and conversion need verification.

Meal fields are populated at meal events; their roughly 99.75% empty-row rate does not indicate 99.75% lost meal records. Do not fill blank meal macros with zero unless distinguishing no logged event from unknown intake. Final Amount Consumed and photo-derived information may be retrospective.

Clinical columns have no pandas-detected nulls; selected numerical columns parse successfully. This does not prove validity. The dictionary's LDL=800 and VLDL=400 error markers each occur once; cholesterol/HDL ratio=400 also occurs once and needs review. Exclude these optional lipid features initially or flag invalid values separately without overwriting source. HbA1c actual range is 4.6–8.5, consistent with publication percent framing despite dictionary mmol/mol wording. Weight/height require pounds/inches conversion.

## Endpoint feasibility check

Engineering threshold for audit: glucose **>180 mg/dL**, target exactly **60 minutes later**. Each participant is sorted by timestamp and joined to its own t+60 row. Current and target glucose must both exist. No extra filling or interpolation was performed.

| Supplied CGM series | Valid current/+60 pairs | +60 above 180 | Current <=180 and +60 >180 |
|---|---:|---:|---:|
| Dexcom | 624,213 | 89,684 (14.37%) | 32,666 / 534,569 eligible (6.11%) |
| Libre | 681,947 | 42,720 (6.26%) | 18,530 / 639,030 eligible (2.90%) |

Dexcom has qualifying low-to-high endpoint examples in 43 participants; Libre in 29. These are heavily overlapping one-minute examples, **not independent adverse events**. They do not establish the first crossing time or an event anywhere within the horizon.

Consecutive-minute upcrossing counts on the supplied grid are 944 for Dexcom and 406 for Libre. These are exploratory threshold crossings, not adjudicated clinical episodes: no persistence-duration/cooldown rule is applied, gap-start crossings are excluded, and interpolation affects counts.

Dexcom low-to-high endpoint counts by HbA1c band: 4,514 below 5.7; 11,045 in 5.7–6.4; 17,107 above 6.4. Recount after causal sampling, usable-history filtering and patient splits before deciding classifier/calibration feasibility.

The two CGMs differ materially: paired-row mean absolute disagreement is **34.74 mg/dL**. Do not mix devices as interchangeable targets. Using contemporaneous alternate-device measurements is not inherently future leakage, but would change the intended single-CGM task; omit the second device from initial predictors and report it separately.

Exploratory full-data persistence MAE at +60 is 19.38 mg/dL (Dexcom) and 16.86 mg/dL (Libre). These are descriptive reference values on interpolated full data, **not held-out validation results or achieved model performance**.

## Remaining blocker and next step

The publication describes one-minute interpolation using bracketing native readings. Fractional glucose values are common, but integer values alone do not prove native sampling. Native sample flags/raw source timestamps were not found in the observed CSV schema. A simple every-fifth-row filter does not establish causality, especially across gaps. No leakage-safe model input or patient split has been frozen yet.

Next work is a data contract and temporal-availability investigation:

1. Establish native CGM timestamps or a defensible delayed-availability rule from the original data-generation code/source. Handle interpolation gaps explicitly; a fixed delay alone may be insufficient.
2. Use genuinely available baseline fields (age, gender, BMI, HbA1c, fasting glucose) and confirm first-day measurement availability. Exclude fingersticks with ambiguous timing and optional problematic lipids initially.
3. Start with one CGM plus HR/activity, without meal final amounts or photos; add meal timing/macros only after availability is justified.
4. Freeze patient-held-out splits and causal feature/target construction, then recount events and train persistence plus Ridge/compact boosting.

No data were cleaned, no model trained and no final dataset choice was made by this audit. Small cohort and non-Indian study population limit transfer claims. Data license and attribution requirements remain separate from code licensing.
