# Other datasets worth testing

Checked 11 October 2026. The goal is to test whether larger cohorts or more
usable clinical/action inputs improve forecasting. External scores are not
promises for our implementation. No new patient dataset was downloaded here.

## Stronger endpoint evidence

The [2026 reproducibility study](https://journals.plos.org/digitalhealth/article?id=10.1371/journal.pdig.0001633)
retrained models on DiaTrend and T1DEXI with five folds holding out participants.
Its [S5 table](https://journals.plos.org/digitalhealth/article/file?id=10.1371/journal.pdig.0001633.s007&type=supplementary)
reports mean participant errors at the exact 30-minute endpoint:

| Dataset / method | Evaluated people | MAE30 | RMSE30 |
|---|---:|---:|---:|
| T1DEXI / Martinsson LSTM | 63 | 13.91 | 19.40 |
| DiaTrend / Martinsson LSTM | 53 | 17.52 | 24.35 |
| DiaTrend / Karagoz PatchTST | 53 | 16.96 | 25.16 |

Units mg/dL. These are independent published replications, not runs performed
by us. Our BrisT1D v2 mean-participant MAE30 is 20.74; differing cohorts,
admission and availability rules prevent a controlled improvement claim.
The downloaded public S5 PDF was extracted and visually checked locally.

Inspected the replication repository's LSTM evaluation functions, T1DEXI
runner, DiaTrend loader and preprocessing README. Evaluation computes actual
glucose errors after undoing scaling. This was a focused inspection, not a
full repository audit or numerical reproduction.
[Code](https://github.com/Augmented-Health-Lab/ReproducibilityStudy_DL_BGPrediction).

## Candidate order

**DCLP3: practical next download.** A Transformer study used 112 participants
and reported MAE 10.13/16.78 at 30/60 minutes, but those are averages across
future trajectories. They are not endpoint targets. The larger cohort and
CGM/pump inputs justify a pilot. The inspected
[DIAX importer](https://github.com/Center-for-Diabetes-Technology/DIAX/blob/main/scripts/dclp3.py)
reads CGM, basal rates, delivered boluses, meter glucose and physical-exam
height/weight. Additional clinical and meal fields need release-level audit.
[Study](https://arxiv.org/html/2505.08821v1),
[official download form](https://public.jaeb.org/dataset/573).
Use **DCLP3 Public Dataset - Release 3 - 2022-08-04.zip**. The form requires
identity, intended use and agreement to terms; none was submitted by us.

**Local status:** the user supplied this release and its original files were
[audited](DCLP3_DATA_AUDIT.md). It has 168 CGM participants, 125 with pump
basal/bolus records and usable historical clinical fields. The meter carbohydrate
column is entirely empty. The [fixed CPU comparison](DCLP3_STUDY_V2.md) has
completed; overall errors improve over persistence, but clinical additions
show no convincing gain and low-target errors remain poor.

**T1DEXI: strongest longer-term candidate.** It combines CGM with insulin,
meal/exercise information and clinical context. The exact-endpoint replication
above is especially useful. Study size and usable training cohort are different;
do not assume every participant has every stream. Current official access
routes through [Vivli](https://doi.org/10.25934/PR00008428).

**HUPA-UCM: quick open multimodal pilot.** Twenty-five people, clinical
characterization including HbA1c/age/treatment and insulin, carbs, heart rate,
activity and sleep streams. [Original release](https://data.mendeley.com/datasets/3hbcscwz44/1)
is CC BY 4.0. GlucoHR-Net Table 5 reports MAE30/60 12.21/22.88 with CGM+HR;
its separate Table 9 reports 13.72/26.42. Both require clarification before
reproduction. It uses within-patient chronological splits. The source's
processed CGM interpolates native 15-minute observations onto a 5-minute grid.
Prefer raw observations for a causal evaluation.
[Model paper](https://onlinelibrary.wiley.com/doi/10.1155/acis/8171184),
[dataset methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC11214197/).

**DiaTrend: valuable diversity, access required.** Fifty-four participants,
longitudinal CGM, pump records and clinical data. Published endpoint scores
above support trying it, although it was harder than T1DEXI in that study.
Access requires Synapse registration, certification/validation, an intended
use statement and acceptance of conditions.
[Dataset paper](https://www.nature.com/articles/s41597-023-02469-5),
[access](https://doi.org/10.7303/syn38187184).

## Proposed first experiment

Audit DCLP3's original timestamps, units, availability of historical profile
fields and action logs before preparing windows. Start locally with matched
persistence/Ridge/tree models at exact 30/60-minute endpoints. Freeze a new
patient-disjoint protocol and keep a separate known-patient temporal protocol
if personalization is tested. Preserve BrisT1D results. Neural/GPU work is
conditional on evidence from this pilot, not necessary merely to switch data.
