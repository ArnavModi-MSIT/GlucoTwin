"""Frozen exploratory residual intervals; no replay outcomes used for calibration."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def residual_radius(residuals, nominal=.90):
    values = np.asarray(residuals, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError('Calibration residuals must be finite and nonempty')
    if not 0 < nominal < 1:
        raise ValueError('Invalid nominal coverage')
    # Finite-sample order statistic. Temporal dependence means this is not a
    # patient-level guarantee; coverage must be assessed on separate patients.
    rank = math.ceil((len(values)+1)*nominal)
    if rank > len(values):
        raise ValueError('Insufficient calibration residuals')
    return float(np.sort(np.abs(values))[rank-1])


def load_intervals(root, cohort, patient_id):
    path = Path(root)/'artifacts/forecast_intervals.json'
    if not path.exists():
        return {}, 'Intervals not prepared; run scripts/prepare_intervals.py.'
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        if payload['version'] != 'residual-interval-v1':
            raise ValueError('Unsupported interval version')
        result = {}
        for item in payload['cohorts'][cohort]:
            if str(patient_id) not in item['assessment_patients']:
                return {}, 'Intervals withheld: this patient belongs to calibration, not assessment.'
            if set(item['assessment_patients']) & set(item['calibration_patients']):
                raise ValueError('Calibration and assessment overlap')
            artifact = Path(root)/item['model_path']
            if fingerprint(artifact) != item['model_sha256']:
                raise ValueError('Interval model fingerprint mismatch')
            if not math.isfinite(item['radius']) or item['radius'] < 0:
                raise ValueError('Invalid interval radius')
            if item['horizon'] not in ([30,60] if cohort=='rbg' else [60]) or item['nominal']!=.90:
                raise ValueError('Interval protocol mismatch')
            if not 0<=item['assessment']['coverage']<=1 or item['assessment']['patients']<1:
                raise ValueError('Invalid assessment metrics')
            result[item['horizon']] = item
        return result, 'Exploratory residual ranges; assessment coverage is measured, not guaranteed.'
    except (ValueError, KeyError, TypeError, OSError):
        return {}, 'Interval verification failed; ranges are unavailable.'


def attach_interval(row, interval):
    """Attach once at issue time. Do not clip bounds or change the prediction."""
    prediction = row.get('prediction')
    if interval is not None and prediction is not None and math.isfinite(prediction):
        row.update(interval_lower=prediction-interval['radius'],
                   interval_upper=prediction+interval['radius'],
                   interval_nominal=interval['nominal'],
                   interval_assessment_coverage=interval['assessment']['coverage'],
                   interval_assessment_patients=interval['assessment']['patients'],
                   interval_low_coverage=interval['assessment'].get('slices',{}).get('low',{}).get('coverage'),
                   interval_high_coverage=interval['assessment'].get('slices',{}).get('high',{}).get('coverage'))
    return row
