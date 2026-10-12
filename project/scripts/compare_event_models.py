"""Equal-budget independent tuning; keeps all active v2 artifacts immutable."""
from pathlib import Path
import json
import sys
import time
import threading

import run_event_study as base
import numpy as np
import pandas as pd
import joblib
import psutil

ROOT = Path(__file__).resolve().parents[1]
METRICS = ('episode_recall', 'precision_lower_bound', 'false_per_eligible_day',
           'recall_with_at_least_10_minutes_lead')


def describe(rows):
    result = base.summarize(rows)
    count = sum(sum(v >= 10 for v in row['lead_minutes']) for row in rows)
    result['recall_with_at_least_10_minutes_lead'] = (
        count / result['evaluable_episodes'] if result['evaluable_episodes'] else None)
    return result


def paired_intervals(rows, seed=2026, repeats=2000):
    """Resample whole patients with identical draws and explicit ID alignment."""
    indexed = {}
    for method, values in rows.items():
        indexed[method] = {row['patient_id']: row for row in values}
        if len(indexed[method]) != len(values):
            raise ValueError('Each evaluation patient must occur exactly once per arm')
    ids = sorted(indexed['fused'])
    if not ids or set(ids) != set(indexed['cgm_only']):
        raise ValueError('Both arms must evaluate identical patients')
    for pid in ids:
        for key in ('evaluable_episodes', 'eligible_monitoring_days'):
            if indexed['fused'][pid][key] != indexed['cgm_only'][pid][key]:
                raise ValueError('Both arms must use identical opportunities and events')
    rng = np.random.default_rng(seed)
    samples = {metric: [] for metric in METRICS}
    for _ in range(repeats):
        selected = [ids[i] for i in rng.integers(0, len(ids), len(ids))]
        a = describe([indexed['fused'][pid] for pid in selected])
        b = describe([indexed['cgm_only'][pid] for pid in selected])
        for metric in METRICS:
            if a[metric] is not None and b[metric] is not None:
                samples[metric].append(a[metric] - b[metric])
    return {metric: {'lower': float(np.quantile(values, .025)),
                     'upper': float(np.quantile(values, .975)),
                     'valid_resamples': len(values)}
            for metric, values in samples.items() if values}


def train_arm(records, role, bands, columns, protocol):
    """Selection cannot access cutoff/evaluation records; cutoff cannot access evaluation."""
    if any(set(role[a]) & set(role[b]) for a, b in
           [('fit', 'threshold'), ('fit', 'evaluation'), ('threshold', 'evaluation')]):
        raise ValueError('Patient roles overlap')
    fitting = {pid: records[pid] for pid in role['fit']}
    cutoff = {pid: records[pid] for pid in role['threshold']}
    chosen, selection = base.inner_select(
        fitting, role['fit'], {p: bands[p] for p in role['fit']}, columns,
        protocol['candidate_names'])
    model = base.fit(fitting, role['fit'], columns, chosen)
    scores = base.predict(model, cutoff, role['threshold'], columns)
    threshold, tuning, passed = base.choose_event_threshold(
        cutoff, scores, protocol['engineering_gate'], protocol['threshold_quantiles'])
    report = dict(selected_candidate=chosen, inner_selection=selection,
                  threshold=threshold, threshold_setting=tuning,
                  cutoff_operating_criteria_met_with_support_waived=passed,
                  cutoff_full_support_gate_met=base.gate(tuning, protocol['engineering_gate']),
                  cutoff_patients=len(cutoff))
    return model, report


def prepare(root, reference):
    """Reconstruct exactly the v2 development opportunities; never open test sensor files."""
    manifest = json.loads((root / 'configs/cgmacros_splits.json').read_text())
    entries, roles = base.freeze_roles(manifest, reference)
    frozen = json.loads((root / 'configs/cgmacros_event_roles_gpu_v2.json').read_text())
    inputs = json.loads((root / 'data/processed/cgmacros_event_inputs_gpu_v2.json').read_text())
    expected = dict(protocol_sha256=base.sha(root / 'configs/event_study_gpu_v2.json'),
                    source_manifest_sha256=base.sha(root / 'configs/cgmacros_splits.json'), roles=roles)
    if frozen != expected or inputs['frozen'] != expected:
        raise RuntimeError('Reference input roles or protocol changed')
    source = root / 'data/raw/cgmacros/CGMacros'
    bio_path = source / 'bio.csv'
    if base.sha(bio_path) != inputs['source_sha256']['bio']:
        raise RuntimeError('Reference profile source changed')
    bio = pd.read_csv(bio_path)
    bio.columns = bio.columns.str.strip()
    bio = bio.set_index('subject')
    records = {}
    for patient in entries:
        pid = patient['patient_id']
        path = source / f'CGMacros-{pid:03d}/CGMacros-{pid:03d}.csv'
        if base.sha(path) != inputs['source_sha256'][str(pid)]:
            raise RuntimeError('Reference sensor source changed')
        features = base.make_features(pd.read_csv(path), base.profile_features(bio.loc[pid]),
                                      patient['phase_utc_minutes_mod_5'])
        glucose = features.cgm_current.copy()
        eligible = (features.history_eligible & (features.cgm_current <= 180) &
                    (features.index >= pd.Timestamp(patient['minimum_forecast_time'])))
        X = features.loc[eligible].drop(columns='history_eligible').copy()
        y, known = base.onset_labels(glucose, X.index)
        records[pid] = dict(X=X, y=y, known=known, times=X.index, glucose=glucose,
                            episodes=base.onsets(glucose, 'high'))
    columns = list(next(iter(records.values()))['X'])
    if columns != inputs['columns']:
        raise RuntimeError('Reference features changed')
    return records, roles, columns, {p['patient_id']: p['a1c_group'] for p in entries}


def run(root=ROOT):
    import xgboost
    start = time.perf_counter()
    config_path = root / 'configs/event_comparison_v3.json'
    protocol = json.loads(config_path.read_text())
    reference_path = root / 'configs/event_study_gpu_v2.json'
    reference = json.loads(reference_path.read_text())
    if base.sha(reference_path) != protocol['reference_protocol_sha256']:
        raise RuntimeError('Reference protocol fingerprint changed')
    if xgboost.__version__ != reference['xgboost_version']:
        raise RuntimeError('Use pinned XGBoost experiment requirements')
    report_path = root / 'reports/event_comparison_v3.json'
    destination = root / 'data/processed/event_comparison_v3'
    if report_path.exists() or destination.exists():
        raise FileExistsError('Versioned study already exists; refusing to overwrite')
    # Protect active source, frozen inputs, results, and every saved v2 model.
    protected = [reference_path, root / 'reports/event_study_gpu_v2.json',
                 root / 'configs/cgmacros_event_roles_gpu_v2.json',
                 root / 'data/processed/cgmacros_event_inputs_gpu_v2.json',
                 root / 'data/processed/cgmacros_event_patient_metrics_gpu_v2.json']
    protected += sorted((root / 'artifacts').glob('cgmacros_onset_gpu_v2_*.joblib'))
    before = {p: base.sha(p) for p in protected}
    old = json.loads((root / 'reports/event_study_gpu_v2.json').read_text())
    records, roles, columns, bands = prepare(root, reference)
    support = dict(patients=len(records), opportunities=sum(len(r['X']) for r in records.values()),
                   known_label_rows=sum(int(r['known'].sum()) for r in records.values()),
                   positive_label_rows=sum(int(r['y'][r['known']].sum()) for r in records.values()),
                   unknown_label_rows=sum(int((~r['known']).sum()) for r in records.values()))
    if support != old['support']:
        raise RuntimeError('Reference row support changed')
    destination.mkdir()
    (destination / 'protocol.json').write_bytes(config_path.read_bytes())
    (destination / 'roles.json').write_text(json.dumps(roles, indent=2), encoding='utf-8')
    used = {'fused': columns, 'cgm_only': [c for c in columns if c.startswith('cgm_')]}
    folds = []
    rss = [psutil.Process().memory_info().rss]
    stop = threading.Event()
    def monitor():
        while not stop.wait(.2):
            rss.append(psutil.Process().memory_info().rss)
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        # Freeze all six selections/models/cutoffs before any outer scoring.
        for number, role in enumerate(roles, 1):
            fold = {'fold': number, 'methods': {}}
            for method, features in used.items():
                print(f'FOLD {number} independent {method} selection', flush=True)
                model, detail = train_arm(records, role, bands, features, reference)
                artifact = dict(model=model, features=features, threshold=detail['threshold'],
                                method=method, roles=role, protocol_sha256=base.sha(config_path),
                                operational_alerts_approved=False, probability_display_approved=False)
                joblib.dump(artifact, destination / f'fold{number}_{method}.joblib')
                fold['methods'][method] = detail
            folds.append(fold)
        (destination / 'frozen_selection.json').write_text(json.dumps(folds, indent=2), encoding='utf-8')
        print('All selections and cutoffs frozen. Starting outer evaluation.', flush=True)
        rows = {method: [] for method in used}
        for number, role in enumerate(roles, 1):
            evaluation = {p: records[p] for p in role['evaluation']}
            for method, features in used.items():
                artifact = joblib.load(destination / f'fold{number}_{method}.joblib')
                scores = base.predict(artifact['model'], evaluation, role['evaluation'], features)
                assessed = base.assess_scores(evaluation, scores, artifact['threshold'])
                rows[method].extend(assessed)
                folds[number-1]['methods'][method]['outer_evaluation'] = describe(assessed)
        old_rows = json.loads((root / 'data/processed/cgmacros_event_patient_metrics_gpu_v2.json').read_text())
        # Exact equality, not just matching rounded aggregate scores.
        reproduction = rows['fused'] == old_rows['fused']
        for new, previous in zip(folds, old['folds']):
            detail = new['methods']['fused']
            reproduction &= (detail['selected_candidate'] == previous['selected_candidate'] and
                             detail['inner_selection'] == previous['inner_selection'] and
                             detail['threshold'] == previous['methods']['fused']['threshold'])
        unchanged = all(base.sha(p) == checksum for p, checksum in before.items())
        if not reproduction or not unchanged:
            raise RuntimeError('Fused reference reproduction or active-file integrity failed')
        pooled = {method: describe(values) for method, values in rows.items()}
        result = dict(version=protocol['version'],
                      status='exploratory development comparison; reserved patients unscored; no promotion',
                      protocol_sha256=base.sha(config_path),
                      reference_report_sha256=base.sha(root / 'reports/event_study_gpu_v2.json'),
                      reference_input_manifest_sha256=base.sha(root / 'data/processed/cgmacros_event_inputs_gpu_v2.json'),
                      source_sha256={str(p.relative_to(root)): base.sha(p) for p in
                                     [Path(__file__), root / 'scripts/run_event_study.py',
                                      root / 'src/glucotwin/features.py', root / 'src/glucotwin/episodes.py',
                                      root / 'src/glucotwin/event_study.py']},
                      support=support, folds=folds, pooled=pooled,
                      paired_fused_minus_cgm_bootstrap95=paired_intervals(rows),
                      bootstrap_unit='patient; identical 2000 resamples for both arms, seed 2026',
                      pooled_engineering_gate_passed={m: base.gate(v, reference['engineering_gate']) for m, v in pooled.items()},
                      fused_v2_exact_reproduction=bool(reproduction), active_files_unchanged=unchanged,
                      operational_alerts_approved=False, probability_display_approved=False,
                      runtime_seconds=round(time.perf_counter()-start, 2),
                      sampled_peak_rss_mib=round(max(rss)/2**20, 2), device='cpu',
                      versions={**old['versions'], 'xgboost': xgboost.__version__,
                                'numpy': np.__version__, 'pandas': pd.__version__,
                                'sklearn': base.sklearn.__version__, 'python': sys.version.split()[0]},
                      limitations=['Repeatedly inspected development cohort; not a fresh test',
                                   'Only 27 development patients and three cutoff patients per fold',
                                   'Reconstructed sensor grid and assumed clinical availability',
                                   'Uncalibrated scores; no medical validation',
                                   'Pooled episode metrics are not patient-macro metrics'])
        (destination / 'patient_metrics.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
        report_path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
        print(json.dumps({k: result[k] for k in ['pooled', 'paired_fused_minus_cgm_bootstrap95',
                          'runtime_seconds', 'sampled_peak_rss_mib']}, indent=2), flush=True)
        return result
    finally:
        stop.set()
        thread.join()


if __name__ == '__main__':
    run()
