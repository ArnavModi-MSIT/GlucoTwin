# Review findings and actions

Checked 10 October 2026 against the current working tree. All four supplied
reviews were considered: two downloaded Markdown reports and two pasted
reviews. Their recommendations are review evidence, not commands. The reviews
primarily inspect the published revision; existing local fixes were retained.

## Implemented

- Non-object JSON, invalid cohorts and oversized bodies now receive controlled
  errors. Short bodies are checked and sockets have a five-second timeout.
  Unexpected replay failures are logged internally with a generic API error.
- Patient switching replaces the browser's prior session (already fixed before
  this review). Synthetic checks exercise forty switches and expiry.
- Missing catalog data is explained in the UI; nonnumeric patient labels work.
- Local HTTP responses add CSP, frame, referrer and content-type protections.
- Two CGMacros training scripts create their artifact directory.
- RBG CGM-only feature selection uses names, not the last-two-column assumption.
- HR conversion occurs once; RBG skips dummy HR rolling computations.
- Calibration score handling supports decision scores and clipped log odds.
  Unapproved probability access still fails before calling a model.
- Both RBG endpoint scripts check calibration support before fitting a
  calibrator. Unsupported cohorts stop explicitly rather than fitting first.
- Episode assessment avoids inference on empty opportunities and zero-day
  division. Original episode definitions and thresholds are preserved.
- Replay loading checks selected model, feature order, input dimension,
  horizon, delay and artifact version; CGMacros also checks its saved sklearn
  version. Legacy RBG artifacts lack library/source-hash metadata; this check
  does not manufacture those missing provenance records.
- Editable Python packaging and Python 3.10/3.12 synthetic CI are configured.
  Local dataset/artifact tests require `GLUCOTWIN_INTEGRATION=1`; synthetic
  causality, import, endpoint, contract and HTTP checks run by default.
- API documentation, reproduction commands and dynamic chart descriptions
  were added. The earlier canonical RBG importer already removes dependence
  on private audit scripts and checks the source subset checksum.

## Findings corrected or already covered

Dependencies were already pinned; do not replace the minimal requirements
with an entire workstation `pip freeze`. Chart lines already break at missing
observations. Source-timing limitations, repeated validation use, disabled
alerts, dataset restrictions and poor low-glucose results were already
disclosed. A SHA256 file beside a joblib artifact cannot establish that an
untrusted pickle is safe; only locally generated trusted artifacts may load.

## Research and larger changes retained for a separate protocol

Delta-target prediction, larger/block samples, grouped cross-validation,
patient residual adaptation, additional latency assumptions, conditional
calibration baselines and episode sensitivity studies are plausible new
experiments. They have not been run and cannot be described as improvements
in performance. Preserve the existing reports and reserved test patients.
Further assessment requires independent threshold-setting/evaluation roles.

Full-prefix replay optimization needs feature-parity and latency measurements;
it remains open. So do independently anchored artifact/source manifests,
CGMacros test-target partition isolation, richer error diagnostics, live
evidence generation, complete keyboard chart navigation and ledger paging.
Avoid a wholesale architecture rewrite or new workflow framework for this
small local project. Code licensing remains the owner's decision; no license
was selected by a review recommendation.

## Verification

The local suite passed 43 tests, including saved prediction parity and HTTP
regressions. A temporary copy without datasets, artifacts or private manifests
passed 26 synthetic tests and explicitly skipped 17 integration tests. Python
compilation, JavaScript syntax and package metadata parsing also passed.
No models were retrained and no reserved-test performance was
scored. CI is configured, not yet executed on GitHub. Changes remain local.
