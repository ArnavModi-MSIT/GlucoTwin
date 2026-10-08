# GlucoTwin data contract v0.1

Frozen for the first exploratory benchmark: 8 October 2026. This is an engineering protocol, not a statement of clinical validation. Original inputs remain unchanged.

## Dataset and population

CGMacros PhysioNet v1.0.0, Dexcom track only. Use the actual linked baseline profile from `bio.csv`; do not fabricate attributes. The study includes healthy, prediabetic and Type 2 participants, not Type 1. Model all admitted groups and report Type 2 results separately. Any benefit to Indian patients is unvalidated.

## Interpolation investigation and admission rule

The published series is interpolated, and neither its CSV schema nor the inspected author analysis notebook supplies raw measurement flags. The author notebook analyzes already-published meal windows rather than rebuilding the raw sensor export. [Author notebook](https://github.com/PSI-TAMU/CGMacros/blob/main/parse_data.ipynb).

Our independent diagnostic found that all observed interior slope-change values are integer-valued. This is compatible with piecewise linear interpolation of integer native CGM readings. Collinear original readings cannot be uniquely recovered from turning points. An independent implementation also uses slope-change recovery, but its claims do not substitute for raw-source verification. [Reference implementation](https://github.com/sfourdrinier/opencgm/blob/main/src/opencgm_stateevent/data/readers.py).

One fixed five-minute phase exactly reproduces the published finite Dexcom series in 35/45 files when linearly reinterpolated between lattice anchors. Ten fail reconstruction. Two of the 35 also contain noninteger lattice values, so the stricter initial admission rule retains **33 participants**. This is a structural data-quality filter, not a model-score filter. Record exclusions in every reported result; the subset may be biased.

**Admission:** zero reconstruction errors above 1e-5 mg/dL and all candidate lattice values integer within 1e-5. Phase is determined from the first 24 hours, and must agree with the diagnostic phase. No prediction samples are generated during that warmup. This inference assumes the publication's five-minute native cadence and linear interpolation accurately describe each admitted file. It does **not** prove individual anchors are original device records. Call them **reconstructed five-minute samples**, never verified raw observations.

The reconstruction gate inspects full-file signal geometry as a retrospective audit. It cannot be described as prospective deployment validation. If original logs contradict it, invalidate the benchmark and rebuild. Do not silently use delayed interpolation as a supposed fix across long gaps.

## Records and timing

- Identifier: integer `subject` matched to `CGMacros-NNN` file; no patient ID as a model feature.
- Sample key: `(patient_id, timestamp)`; preserve date-shifted timestamps as supplied, without inventing timezone or true calendar dates.
- Glucose: mg/dL; use admitted patient-specific five-minute phase, not every fifth CSV row.
- Target: same patient's reconstructed glucose exactly **60 minutes after prediction time**. No target interpolation, nearest-date substitution or fill. Missing target means exclude that supervised example.
- Endpoint flag: `target_glucose > 180`. New-high endpoint view: current glucose `<=180` and target `>180`. Neither definition establishes first onset or an event anywhere in the hour.
- History: trailing 60 minutes, all timestamps `<=t`; require at least 10/13 possible five-minute samples and current sample present. Maximum allowed gap between observed history samples: 15 minutes. No extra interpolation or backward fill.
- First-day exclusion: phase warmup and baseline availability buffer, at least 24 hours from file start. Clinical lab result turnaround is not available in the source; historical profile availability is a documented replay assumption, not verified clinical delivery timing.
- HR: optional trailing past-only aggregates of the supplied one-minute summaries; flag missing values. Its device-minute aggregation is described in the dictionary; full upstream processing remains unaudited.
- METs/Intensity, other CGM, steps, microbiome, photographs, fingerstick measurements, meal final consumed amounts and insulin-dose features: excluded initially. Fasting insulin is a lab, not a dosing record.
- Meals/macros: excluded from initial benchmark until event/entry availability is defensible. Missing meal records do not mean no food was eaten.

## Initial feature definition

| Group | Features | Availability |
|---|---|---|
| CGM | Current value; mean/std/min/max and valid count over trailing 15/30/60 min; change at 15/30/60 min where exact prior value exists; causal slope over 30 min | Reconstructed grid at/before t; missingness retained |
| Sensor quality | Missing fraction, maximum observed-history gap | Past history only |
| Wearable | HR mean/std and observed fraction over trailing 15/30/60 min | Supplied rows at/before t; optional ablation |
| Clinical | Age, gender, BMI, HbA1c, fasting glucose | Baseline profile under stated availability assumption |

HbA1c interpreted in percent based on the publication and 4.6–8.5 data range; document the conflicting dictionary unit. Do not reuse erroneous LDL/VLDL/ratio sentinels. Do not use cohort labels derived from HbA1c as extra features. No day-of-week feature because dates were shifted.

## Shared inference and replay

Use one feature builder for offline evaluation and replay. Pass a prefix/history filtered to timestamp <=t, clinical profile and frozen metadata only. Ground-truth targets belong to the evaluator, never the inference input. Forecasts are logged when made and actuals appear only after target time. This enforces causality **within the reconstructed dataset contract**; it does not resolve the upstream raw-data uncertainty.

Abstain for absent current glucose, insufficient history, excessive gaps, unknown profile or incompatible artifact. A probability appears only if a separately trained classifier passes calibration checks. No insulin or treatment advice.

## Fixed partitions

Manifest: `configs/cgmacros_splits.json`, seed 2026, patient-disjoint stratification by recorded HbA1c bands. **21 training / 6 validation / 6 test patients**, with two patients from each HbA1c band in validation and test. No participant appears in multiple partitions. Patient-history warmup is unsupervised phase determination; no test-period outcomes are used to tune model parameters.

The audit already explored full-data event counts and descriptive persistence values; the test cannot honestly be called completely unseen. Freeze the manifest now, avoid further test-target exploration and reserve final test model scores for one final evaluation. Within-patient splits are not part of the initial protocol; any later temporal experiment needs interval-based purging.

## Evidence and next stage

Diagnostics: `reports/cgmacros_interpolation_diagnostics.csv`; admission/splits generated by `scripts/freeze_cgmacros_contract.py`. These are generated locally and excluded from public Git. Feature preparation and development-only Ridge/boosting runs are now implemented; see `reports/BASELINE_RESULTS.md` and `reports/BOOSTING_RESULTS.md`.

Next: assess endpoint classification and calibration using development patients. If reconstruction uncertainty is unacceptable for a real-time claim, obtain original native logs or move the causal real-data benchmark to raw DiaData. A reconstructed CGMacros proof of concept must disclose this limitation prominently.
