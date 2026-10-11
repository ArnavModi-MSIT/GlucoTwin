# Project check — 10 October 2026

Scope: local reproduction and replay-session correctness. This is not a comprehensive clinical or security audit.

## Fixed

- RBG setup no longer depends on unpublished audit scripts/files. `scripts/import_rbg.py` imports supplied versioned archives, verifies hashes, streams patient-grid checks and creates local audit metadata.
- The RBG split generator reads canonical data-folder inputs and rejects attempts to overwrite a differing frozen manifest.
- Repeated patient switches replace the browser's previous replay session rather than accumulating sessions toward the service limit. Other browser sessions remain separate.
- README and reproduction instructions distinguish minimum dashboard setup from optional research artifacts required by the full test suite.

## Verified

- Existing real RBG subset: 226 linked IDs, 18,126,280 grid rows and 14,700,791 nonmissing glucose readings.
- Frozen split hash reproduced exactly; no patient roles or models changed.
- 34 tests passed, including synthetic import/filtering, chunk-boundary rejection, session replacement, isolation, delayed outcomes and model parity.
- New clinical metadata and patient-level audit files remain excluded from Git.

## Limits and remaining project work

A second full real-archive extraction and a new clean-machine end-to-end run were not performed. Existing canonical data plus synthetic import fixtures were used for this change. The full suite requires locally prepared datasets and assessment artifacts; those requirements are now explicit.

Model warning/calibration requirements remain failed. No reserved-test prediction results were generated, and the dashboard's operational alerts remain disabled. Better reproducibility does not improve measured medical performance.

Changes from this check remain local pending publication.
