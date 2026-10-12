"""Frozen half-validation calibration/assessment study; never opens reserved tests."""
from pathlib import Path
import json
import sys
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from glucotwin.uncertainty import fingerprint, residual_radius
from glucotwin.artifacts import validate_replay_artifact
from glucotwin.features import make_features,profile_features


def assess(parts, radius):
    summaries = []
    for prediction, actual in parts:
        error = np.abs(prediction-actual)
        summaries.append(dict(rows=len(actual), covered=int((error<=radius).sum()),
                              coverage=float((error<=radius).mean())))
    count = sum(p['rows'] for p in summaries)
    slices = {}
    for label, predicate in [('low', lambda y:y<70), ('reference', lambda y:(y>=70)&(y<=180)), ('high', lambda y:y>180)]:
        errors = [np.abs(p-y)[predicate(y)] for p,y in parts]
        errors = np.concatenate(errors)
        slices[label] = dict(rows=len(errors), coverage=float((errors<=radius).mean()) if len(errors) else None)
    return dict(patients=len(parts), rows=count, coverage=sum(p['covered'] for p in summaries)/count,
                patient_macro_coverage=float(np.mean([p['coverage'] for p in summaries])),
                patient_coverage_min=min(p['coverage'] for p in summaries),
                patient_coverage_max=max(p['coverage'] for p in summaries),
                width_mg_dl=2*radius, slices=slices)


def run():
    private = dict(version='residual-interval-v1', cohorts={})
    public = dict(version='residual-interval-v1', nominal=.90,
                  status='Exploratory previously examined development data; reserved tests untouched',
                  protocol='Sorted validation IDs alternate calibration/assessment; fixed before computing residuals. Row-pooled absolute residual order statistic. No clipping, refitting or adaptive selection.',
                  limitations=['Temporal overlap and patient shift invalidate an automatic nominal coverage guarantee.',
                               'Validation data previously informed model selection.',
                               'Ranges are descriptive research estimates, not clinical confidence or event probabilities.'], cohorts={})
    for cohort, horizons in [('cgmacros', [60]), ('rbg', [30,60])]:
        manifest = json.loads((ROOT/f'configs/{cohort}_splits.json').read_text())
        allowed = {str(p['patient_id']) for p in manifest['participants'] if p['split']=='validation'}
        private['cohorts'][cohort] = []
        public['cohorts'][cohort] = []
        for horizon in horizons:
            model_path = 'artifacts/ridge_cgm_clinical_hr.joblib' if cohort=='cgmacros' else f'artifacts/rbg_ridge_cgm_profile_{horizon}.joblib'
            artifact = validate_replay_artifact(joblib.load(ROOT/model_path),cohort,horizon,profile_fusion=cohort=='rbg')
            groups = {}
            if cohort=='cgmacros':
                # Build only named validation records, never load a combined table
                # that might contain reserved targets from another workflow.
                base = ROOT/'data/raw/cgmacros/CGMacros'
                bio = pd.read_csv(base/'bio.csv');bio.columns=bio.columns.str.strip()
                bio = bio.set_index('subject')
                for patient in manifest['participants']:
                    if patient['split']!='validation': continue
                    pid = patient['patient_id']
                    frame = pd.read_csv(base/f'CGMacros-{pid:03d}/CGMacros-{pid:03d}.csv')
                    part = make_features(frame,profile_features(bio.loc[pid]),patient['phase_utc_minutes_mod_5'])
                    target = part.cgm_current.reindex(part.index+pd.Timedelta(minutes=60))
                    target.index = part.index
                    part['target_glucose_60m'] = target
                    part = part.loc[part.history_eligible & target.notna() & (part.index>=pd.Timestamp(patient['minimum_forecast_time']))]
                    with threadpool_limits(limits=4): prediction = artifact['model'].predict(part[artifact['features']])
                    groups[str(pid)] = (prediction, part.target_glucose_60m.to_numpy())
            else:
                columns = json.loads((ROOT/'data/processed/rbg/features.json').read_text())
                indices = [columns.index(c) for c in artifact['features']]
                for path in sorted((ROOT/f'data/processed/rbg/{horizon}/validation').glob('*.npz')):
                    if path.stem not in allowed: raise ValueError('Patient outside validation manifest')
                    with np.load(path) as data:
                        if not len(data['y']): continue
                        with threadpool_limits(limits=4): prediction = artifact['model'].predict(data['X'][:,indices])
                        groups[path.stem] = (prediction, data['y'].copy())
            ids = sorted(groups)
            calibration, assessment = ids[::2], ids[1::2]
            if not calibration or not assessment: raise ValueError('Insufficient patients')
            residuals = np.concatenate([groups[pid][0]-groups[pid][1] for pid in calibration])
            radius = residual_radius(residuals)
            metrics = assess([groups[pid] for pid in assessment],radius)
            item = dict(horizon=horizon, nominal=.90, radius=radius, assessment=metrics,
                        calibration_patients=calibration, assessment_patients=assessment,
                        model_path=model_path, model_sha256=fingerprint(ROOT/model_path))
            private['cohorts'][cohort].append(item)
            public['cohorts'][cohort].append(dict(horizon=horizon, radius_mg_dl=radius,
                calibration_patients=len(calibration), calibration_rows=len(residuals), assessment=metrics))
    (ROOT/'artifacts/forecast_intervals.json').write_text(json.dumps(private,indent=2),encoding='utf-8')
    (ROOT/'reports/forecast_intervals_v1.json').write_text(json.dumps(public,indent=2),encoding='utf-8')
    print(json.dumps(public,indent=2))


if __name__ == '__main__': run()
