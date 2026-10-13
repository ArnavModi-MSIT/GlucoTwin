# Importing a patient CSV

Open **Import a patient CSV** in the dashboard. Download the fictional template, or select an anonymized/synthetic UTF-8 file. Declare its units and provenance, validate it, review the quality summary, then start replay. File contents are sent only to the localhost server; the application does not write them to disk or train on them.

```text
timestamp,glucose
2024-01-01T00:00:00,100
2024-01-01T00:05:00,102
2024-01-01T00:10:00,
```

## Accepted contract

- Exact two-column header `timestamp,glucose`; no identifiers or extra columns.
- At most 1 MB, 10,000 rows and 31 days. At least one hour, 13 timestamped rows and ten numeric readings.
- Strictly increasing ISO study timestamps with optional zero seconds, without timezone suffixes. Every timestamp shares one five-minute phase. Duplicates, unsorted rows and off-phase samples are rejected; timestamps are not rounded or shifted.
- Empty physical lines are ignored. A blank glucose cell remains a missing measurement; malformed two-column records are rejected. Absent five-minute slots are explicitly inserted as missing. No interpolation, stale-value carrying or dropped difficult rows.
- Units are declared as mg/dL or mmol/L; mmol/L converts using a factor of 18. Positive values up to 1000 mg/dL are accepted after conversion as a parsing bound, not a clinical validity claim. Nonfinite and nonnumeric values are rejected.
- Optional anonymized age/recorded sex fields are context in history mode. Only adult ages 18–100 and F/M encodings are accepted by this prototype; other profiles are unsupported.

## Replay methods

**History + persistence baseline** works on a fresh checkout without saved models. It repeats the latest available reading at 30 and 60 minutes when the past hour is sufficiently covered (at least 10/13 readings and maximum observed gap 15 minutes). This is a transparent baseline, not a learned medical model. First issue follows one hour of history plus five-minute availability delay.

**Exploratory RBG Ridge transfer** is opt-in and needs trusted locally prepared RBG artifacts, age and recorded sex, at least 24 hours of history, and minute-00/05/10/etc. sampling. The saved profile-fused model is applied without fitting or adaptation. Its performance on user imports is unestablished; the original study's MAEs do not validate this use. First issue follows a 24-hour warm-up plus five-minute delay. No RBG/CGMacros event classifier or cohort-specific uncertainty range is transferred.

Both methods keep forecasts fixed at issue time and reveal exact-time outcomes only after target time plus five minutes. Missing outcomes remain missing. Every intermediate five-minute attempt is recorded when advancing by 30/60 minutes. Short records may end with pending forecasts; extending their outcomes is not simulated.

## Scope and retention

The imported cohort is separate from training, validation and reserved-test manifests. The parser accepts no file paths, executes no file code and loads no uploaded models. Preview reports whole-file quality, not performance. Historical summaries and replay outcomes use only the current available prefix.

Up to eight imports are kept in the browser tab's catalog. Server records stay in memory for replay sessions and are never included in public Git files; session access expires after inactivity. Reloading clears the browser import catalog. Reimporting identical readings with the same profile and method restores the same patient identity, so optionally saved local care notes can be reopened. Changing records/profile/method creates another identity. Synthetic/anonymized provenance is user-declared, not independently verified.

Exports clearly identify imported records and the applied method. Ordinary CSV/JSON/HTML exports contain replay data; review observations, questions and follow-up tasks enter the separate combined review summary. JSON care-note schema v3 supports these types, with v1/v2 imports still accepted for their original entry types.
