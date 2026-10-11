# DCLP3 measured-endpoint preparation

Frozen before model fitting on 11 October 2026. This separate cohort does not
replace saved dashboard models or any earlier study.

## Patients and comparisons

The 168 randomized participants are split into **134 development** and
**34 reserved** participants. Splits use seed 2026 and treatment group crossed
with presence of both basal/bolus streams, never glucose outcomes. Four
development folds each hold out 33 or 34 participants and fit on the other
100 or 101. Every development participant is evaluated once.

The development cohort has 89 CLC pump participants, 11 SAP pump participants
and 34 SAP participants without the linked pump streams. The reserve contains
23 CLC pump, 2 SAP pump and 9 SAP participants without those streams.

Compare clinical profile + CGM against CGM-only on matched development rows.
The pump comparison uses the **100 development participants** with linked
pump streams, comparing CGM-only, clinical + CGM and clinical + CGM + insulin
within that same subset. Missing or stale pump features never decide whether
a row is evaluated. Report treatment groups separately.

Reserved participants appeared in the initial aggregate source audit.
Source files contain multiple participants, so file scans necessarily read
their tokens; reserved sensor rows are filtered before conversion and feature
construction. No reserved feature files or model scores are generated.

## Timing and measured targets

The active protocol is [v2](../configs/dclp3_contract_v2.json).
Forecasts are issued at each native post-randomization CGM observation timestamp
**plus five minutes**, under an explicitly assumed sensor delay. The latest
input observation is therefore five minutes old at issue. Pump events also have
a five-minute assumed delay. Neither assumption proves prospective upload
availability; deidentified local clocks are retained without asserting a timezone.

For nominal +30/+60-minute endpoints, choose the nearest **observed** CGM
reading within **±30 seconds** of issue + horizon. Equidistant ties choose the
earlier reading. Labels are never interpolated. Save the actual matched time
and offset, with a separate flag for exactly zero offset. Report strict
exact-timestamp subset metrics alongside nominal-endpoint metrics; do not
describe all tolerance-matched labels as exact-timestamp labels.

Outcome availability follows **actual matched time + five minutes**, which
can differ from nominal target time + five minutes. Relative to the latest
input reading, nominal predictions look 35/65 minutes ahead, plus any matching
offset. This differs from literature forecasting directly from the latest
measurement without an availability delay.

History requires a 120-minute warmup, at least 11 past-hour observations,
no past-hour gap over 630 seconds, and latest-reading age no more than
630 seconds. These history rules are independent of clinical/pump missingness
and unchanged between comparisons.

## Why the initial clock-grid version is retained but not used

[v1](../configs/dclp3_contract_v1.json) issued forecasts on wall-clock
five-minute bins. It produced 6,636,978 eligible histories but only 1,309,719
30-minute and 1,304,506 60-minute point labels: roughly **20% target support**.
Native sensor minute/second offsets made the ±30-second target match too
selective. Source timing checks passed, but cohort coverage was unsuitable.

Before any fit or error score, v2 changed the issue schedule to follow native
observation timestamps. It retains the same patient roles, target tolerance,
clinical availability and history rules. Original v1 configuration, caches
and [preparation counts](../reports/dclp3_preparation_v1.json) remain preserved.
This revision fixes label coverage, not an observed model score.

V2 preparation produced **6,630,200 eligible histories**, with **6,522,958
30-minute** and **6,477,018 60-minute** point targets (98.4% and 97.7% support).
Strict zero-offset subsets contain 3,925,456 and 3,595,915 rows. Boundary-coded
targets are counted separately: 24,155 and 23,783 rows. Eleven conflicting
basal timestamps became unknown; no complete source-identical bolus duplicates
were found. Preparation completed locally in 256 seconds.

## Features and exclusions

The feature matrix contains 77 columns: 37 CGM/clock features, nine additional
historical clinical features and 31 additional insulin features. Clinical fields
include age, recorded sex, diagnosis age/approximation flag, reported daily
insulin, screening BMI/blood pressure and screening local HbA1c.

Screening fields become available at their visit date + one day. Local HbA1c
uses the later of screening visit/test date + one day. Fields remain missing
until their own assumed availability. Unknown source flags and missing units
are preserved. Central and follow-up labs are excluded. Imputers and scalers
will be fitted only on each training fold; none is fitted during preparation.

Source codes 39/401 are preserved separately from exact-valued 40-400 readings.
For history features only, bounded 40/400 proxies are accompanied by code
flags/counts. Boundary-coded target rows are **not point-error labels** and
their counts are reported separately. This is a conservative engineering
policy for non-exact values, not a verified event/censoring model. Point-score
claims must disclose this omitted target domain. No event labels are created.

Pump clocks prefer adjusted event times where present. Basal rates are treated
as commanded units/hour. Known-rate integration expires a state after 30 minutes
without a new record and reports known-duration fractions. Unknown time is not
converted into zero insulin or a complete delivered total. Conflicting rates
become unknown. Bolus features preserve standard/extended types and summarize
observed delivered amounts, without interpreting an extended bolus as a known
instantaneous absorption curve. Recency is bounded at six hours, with stale
flags. Only complete source-identical bolus duplicates may be removed; repeated
`RecID` values alone are retained. Meal logs are absent.

The basal freshness limit is an engineering assumption, not proof that a
stable basal rate expires physiologically. It may hide genuine stable pump
settings, particularly in the SAP subgroup; report missingness/known-duration
coverage when interpreting an insulin ablation.

## Reproduction and validation

From the `project` directory:

```powershell
python -m unittest discover -s tests -p test_dclp3.py -v
python scripts/prepare_dclp3.py
python scripts/verify_dclp3_preparation.py
```

Preparation freezes hashed source files, patient roles and clinical provenance;
rerunning with changed sources or an edited frozen protocol refuses to replace
the existing manifest. Participant manifests and arrays are local ignored
artifacts. Aggregate outputs are public:

- [Contract summary](../reports/dclp3_contract_summary_v2.json)
- [Preparation support](../reports/dclp3_preparation_v2.json)
- [Validation checks](../reports/dclp3_preparation_checks_v2.json)

Checks cover patient-disjoint roles, source/cache hashes, clinical availability,
bounded recency, measured-label offsets, strict subset flags, support accounting,
36 real-source feature prefix probes and 72 brute-force target probes. Unit
tests cover future-input invariance, conflicting glucose, boundary proxies,
basal expiry/known-zero behavior and native sensor phase.

The [fixed CPU comparison](DCLP3_STUDY_V2.md) has now completed: 80 saved
models and training-only preprocessors were verified, with 1,280 inference
parity probes and full metric recomputation. Overall MAE improves over
persistence, clinical additions show no convincing gain, and insulin additions
produce small matched-subset gains. Poor low-target errors remain unresolved;
no warning or dashboard model was enabled from this study.
