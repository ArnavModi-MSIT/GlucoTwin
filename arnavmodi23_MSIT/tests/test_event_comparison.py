"""Selection boundaries and paired-patient uncertainty for the independent study."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import compare_event_models as study
from local_only import local_only


def row(pid, detected, alarms, leads):
    return dict(patient_id=pid, qualifying_episodes=2, evaluable_episodes=2,
                detected_episodes=detected, alarms=alarms, false_alarms=alarms-detected,
                unknown_alarms=0, redundant_alarms=0, eligible_monitoring_days=1.,
                lead_minutes=leads)


class ComparisonTests(unittest.TestCase):
    def test_shared_patient_resampling_aligns_ids_not_row_order(self):
        rows = [row(1, 2, 3, [5, 15]), row(2, 1, 2, [10])]
        result = study.paired_intervals({'fused': rows, 'cgm_only': rows[::-1]}, repeats=50)
        self.assertTrue(all(v['lower'] == v['upper'] == 0 for v in result.values()))
        self.assertEqual(study.describe(rows)['recall_with_at_least_10_minutes_lead'], .5)

    def test_reject_mismatched_or_duplicate_patients(self):
        r = row(1, 1, 1, [5])
        for values in ([r, r], [row(2, 1, 1, [5])]):
            with self.assertRaises(ValueError):
                study.paired_intervals({'fused': [r], 'cgm_only': values})
        with self.assertRaises(ValueError):
            study.paired_intervals({'fused': [r], 'cgm_only': [{**r, 'eligible_monitoring_days': 2}]})

    def test_independent_selection_and_strict_record_boundaries(self):
        role = dict(fit=[1], threshold=[2], evaluation=[3])
        # An evaluation read is a hard failure, even if later discarded.
        class Guarded(dict):
            def __getitem__(self, key):
                if key == 3:
                    raise AssertionError('Evaluation accessed during selection')
                return super().__getitem__(key)
        records = Guarded({1: 'fit', 2: 'cutoff'})
        seen = []
        def select(values, ids, bands, columns, names):
            self.assertEqual(set(values), {1})
            seen.append(tuple(columns))
            return ('fused-choice' if len(columns) == 2 else 'cgm-choice'), {}
        def fit(values, ids, columns, name):
            self.assertEqual(set(values), {1})
            return name
        def predict(model, values, ids, columns):
            self.assertEqual(set(values), {2})
            return {2: [.5]}
        def cutoff(values, scores, settings, quantiles):
            self.assertEqual(set(values), {2})
            return .5, {}, False
        with patch.object(study.base, 'inner_select', side_effect=select), \
             patch.object(study.base, 'fit', side_effect=fit), \
             patch.object(study.base, 'predict', side_effect=predict), \
             patch.object(study.base, 'choose_event_threshold', side_effect=cutoff), \
             patch.object(study.base, 'gate', return_value=False):
            protocol = dict(candidate_names=['a', 'b'], engineering_gate={}, threshold_quantiles=101)
            a = study.train_arm(records, role, {1: 'band'}, ['cgm', 'profile'], protocol)
            b = study.train_arm(records, role, {1: 'band'}, ['cgm'], protocol)
        self.assertEqual(a[0], 'fused-choice')
        self.assertEqual(b[0], 'cgm-choice')
        self.assertEqual(len(seen), 2)

    def test_role_overlap_rejected_before_fitting(self):
        with self.assertRaises(ValueError):
            study.train_arm({}, dict(fit=[1], threshold=[1], evaluation=[2]), {}, [], {})


@local_only
class SavedComparisonTests(unittest.TestCase):
    def test_preparation_reads_only_development_sensor_files(self):
        manifest = json.loads((ROOT / 'configs/cgmacros_splits.json').read_text())
        ids = {p['patient_id'] for p in manifest['participants'] if p['split'] in ('train', 'validation')}
        source = ROOT / 'data/raw/cgmacros/CGMacros'
        allowed = {source / 'bio.csv'} | {source / f'CGMacros-{p:03d}/CGMacros-{p:03d}.csv' for p in ids}
        reader = study.pd.read_csv
        seen = set()
        def guarded(path, *args, **kwargs):
            self.assertIn(Path(path), allowed)
            seen.add(Path(path))
            return reader(path, *args, **kwargs)
        protocol = json.loads((ROOT / 'configs/event_study_gpu_v2.json').read_text())
        with patch.object(study.pd, 'read_csv', side_effect=guarded):
            records, roles, _, _ = study.prepare(ROOT, protocol)
        self.assertEqual(set(records), ids)
        self.assertEqual(seen, allowed)
        self.assertEqual(sorted(p for role in roles for p in role['evaluation']), sorted(ids))

    def test_saved_paired_evidence_and_unchanged_reference(self):
        result = json.loads((ROOT / 'reports/event_comparison_v3.json').read_text())
        rows = json.loads((ROOT / 'data/processed/event_comparison_v3/patient_metrics.json').read_text())
        original = json.loads((ROOT / 'data/processed/cgmacros_event_patient_metrics_gpu_v2.json').read_text())
        self.assertEqual(rows['fused'], original['fused'])
        self.assertEqual(result['pooled'], {m: study.describe(r) for m, r in rows.items()})
        self.assertEqual(result['paired_fused_minus_cgm_bootstrap95'], study.paired_intervals(rows))
        self.assertEqual(result['reference_report_sha256'], study.base.sha(ROOT / 'reports/event_study_gpu_v2.json'))
        self.assertFalse(result['operational_alerts_approved'])


if __name__ == '__main__':
    unittest.main()
