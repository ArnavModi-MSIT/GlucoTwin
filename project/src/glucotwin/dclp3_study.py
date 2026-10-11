"""Matched development matrices and patient-level DCLP3 error summaries."""
import hashlib
import numpy as np

from .regression_diagnostics import error_summary, patient_macro, sliced_errors


def matrix(records, ids, horizon, cap, seed, development):
    if not ids or not set(ids) <= set(development):
        raise ValueError('Only development participants may enter a matrix')
    parts, targets, groups, times, strict = [], [], [], [], []
    for pid in sorted(ids):
        record = records[pid]
        y = record[f'y{horizon}']
        positions = np.flatnonzero(np.isfinite(y))
        if cap is not None and len(positions) > cap:
            rng = np.random.default_rng(seed+int(pid)*1000+horizon)
            positions = np.sort(rng.choice(positions, size=cap, replace=False))
        if not len(positions):
            raise ValueError('No measured point targets for a participant')
        parts.append(record['X'][positions])
        targets.append(y[positions])
        groups.extend([pid]*len(positions))
        times.append(record['times'][positions])
        strict.append(record[f'strict{horizon}'][positions])
    return {'X': np.concatenate(parts), 'y': np.concatenate(targets),
            'groups': np.asarray(groups), 'times': np.concatenate(times),
            'strict': np.concatenate(strict)}


def row_digest(data):
    digest = hashlib.sha256()
    for key in ('groups', 'times', 'y', 'strict'):
        value = np.ascontiguousarray(data[key])
        digest.update(str(value.dtype).encode())
        digest.update(str(value.shape).encode())
        digest.update(value.tobytes())
    return digest.hexdigest()


def equal_patient_weights(groups):
    _, inverse, count = np.unique(groups, return_inverse=True, return_counts=True)
    weights = 1/count[inverse]
    return weights * len(weights)/weights.sum()


def patient_rows(actual, predicted, current, groups, strict):
    result = []
    for pid in np.unique(groups):
        mask = groups == pid
        y, p, c, exact = actual[mask], predicted[mask], current[mask], strict[mask]
        diagnostics = sliced_errors(y, p)
        diagnostics['strict'] = error_summary(y[exact], p[exact])
        diagnostics['current_low'] = error_summary(y[c < 80], p[c < 80])
        diagnostics['current_high'] = error_summary(y[c > 180], p[c > 180])
        error = p-y
        result.append({'patient_id': str(pid), 'n': len(y),
            'absolute_error_sum': float(np.abs(error).sum()),
            'squared_error_sum': float((error**2).sum()), 'diagnostics': diagnostics})
    return result


SLICES = ('all', 'high', 'low', 'strict', 'current_low', 'current_high')


def summarize(rows):
    if not rows:
        return {'patients': 0, 'rows': 0}
    result = {'patients': len(rows), 'rows': sum(r['n'] for r in rows),
              'patient_macro_slices': {name: patient_macro(rows, name) for name in SLICES},
              'pooled_slices': {}, 'tail_interpretation': 'mean of participant quantiles, not pooled quantiles'}
    for name in SLICES:
        metrics = [r['diagnostics'][name] for r in rows if r['diagnostics'][name]['n']]
        n = sum(m['n'] for m in metrics)
        pool = {'rows': n, 'patients_with_rows': len(metrics)}
        if n:
            pool.update({'mae': sum(m['mae']*m['n'] for m in metrics)/n,
                'rmse': float(np.sqrt(sum(m['rmse']**2*m['n'] for m in metrics)/n)),
                'bias': sum(m['bias']*m['n'] for m in metrics)/n,
                'fraction_error_gt40': sum(m['fraction_error_gt40']*m['n'] for m in metrics)/n,
                'fraction_error_gt60': sum(m['fraction_error_gt60']*m['n'] for m in metrics)/n})
        result['pooled_slices'][name] = pool
    result.update({key: result['pooled_slices']['all'][key] for key in ('mae', 'rmse', 'bias')})
    return result


def paired_comparison(candidate, reference, repetitions=2000, seed=2026):
    left = {r['patient_id']: r for r in candidate}
    right = {r['patient_id']: r for r in reference}
    if set(left) != set(right) or any(left[p]['n'] != right[p]['n'] for p in left):
        raise ValueError('Paired comparisons require matched participants and row counts')
    rng = np.random.default_rng(seed)
    output = {}
    for name, metric in [('all', 'mae'), ('all', 'rmse'), ('all', 'p95_absolute_error'),
                         ('high', 'mae'), ('low', 'mae'), ('strict', 'mae'), ('current_low', 'mae')]:
        support = [p for p in sorted(left) if left[p]['diagnostics'][name]['n'] and right[p]['diagnostics'][name]['n']]
        if any(left[p]['diagnostics'][name]['n'] != right[p]['diagnostics'][name]['n'] for p in support):
            raise ValueError('Unmatched slice supports')
        difference = np.array([left[p]['diagnostics'][name][metric]-right[p]['diagnostics'][name][metric] for p in support])
        result = {'patients': len(support), 'mean_difference': None, 'patient_bootstrap95': None}
        if len(difference):
            bootstrap = rng.choice(difference, size=(repetitions, len(difference)), replace=True).mean(axis=1)
            result.update({'mean_difference': float(difference.mean()),
                           'patient_bootstrap95': np.quantile(bootstrap, [.025, .975]).tolist()})
        output[name+'_'+metric] = result
    return output
