"""Past-only features on native asynchronous BrisT1D streams.

Input streams are conflict-reconciled numeric observations, indexed by recorded
time. Availability shifts are explicit assumptions, not inferred upload times.
"""
import math
import numpy as np
import pandas as pd


MG_DL_PER_MMOL_L = 18.0182


def issue_times(glucose, native_minutes, delay_minutes):
    if native_minutes <= 0 or delay_minutes < 0:
        raise ValueError('Invalid cadence or availability delay')
    offset = math.ceil(delay_minutes/native_minutes)*native_minutes
    return glucose.index + pd.Timedelta(minutes=offset)


def last_observation(stream, cutoffs):
    if not len(stream):
        return np.full(len(cutoffs), np.nan), np.full(len(cutoffs), np.nan)
    positions = stream.index.searchsorted(cutoffs, side='right')-1
    valid = positions >= 0
    values = stream.to_numpy()[np.maximum(positions, 0)].astype(float)
    ages = np.asarray((cutoffs-stream.index[np.maximum(positions, 0)]).total_seconds()/60, dtype=float)
    values[~valid] = np.nan
    ages[~valid] = np.nan
    return values, ages


def window_statistics(stream, cutoffs, minutes, closed='both'):
    if not len(stream):
        empty = np.full(len(cutoffs), np.nan)
        return {key: empty.copy() for key in ('mean', 'std', 'min', 'max', 'sum')} | {'count': np.zeros(len(cutoffs))}
    # Query timestamps have no invented observations. Rolling operations ignore
    # their NaNs while retaining the exact time boundary of each past window.
    augmented = stream.reindex(stream.index.union(cutoffs).sort_values())
    rolling = augmented.rolling(f'{minutes}min', closed=closed, min_periods=1)
    return {key: getattr(rolling, key)().reindex(cutoffs).to_numpy()
            for key in ('mean', 'std', 'min', 'max', 'sum', 'count')}


def make_brist_features(streams, profile, native_minutes, issues, protocol):
    if issues.has_duplicates or not issues.is_monotonic_increasing:
        raise ValueError('Issue times must be unique and ordered')
    delays = protocol['availability_delay_minutes']
    glucose = streams['bg']*MG_DL_PER_MMOL_L
    cutoffs = issues-pd.Timedelta(minutes=delays['bg'])
    current, source_age = last_observation(glucose, cutoffs)
    result = {'cgm_current': current, 'cgm_age_minutes': source_age+delays['bg'],
              'cgm_native_cadence_minutes': native_minutes}
    for minutes in (15, 30, 60, 120):
        values, lag_age = last_observation(glucose, cutoffs-pd.Timedelta(minutes=minutes))
        values[lag_age > native_minutes] = np.nan
        result[f'cgm_lag_{minutes}m'] = values
        result[f'cgm_change_{minutes}m'] = current-values
        stats = window_statistics(glucose, cutoffs, minutes)
        for name in ('mean', 'std', 'min', 'max', 'count'):
            result[f'cgm_{name}_{minutes}m'] = stats[name]
        result[f'cgm_fraction_{minutes}m'] = np.minimum(1, stats['count']/(minutes/native_minutes+1))
    result['cgm_slope_15m'] = result['cgm_change_15m']/15
    result['cgm_slope_30m'] = result['cgm_change_30m']/30
    result['cgm_acceleration_15m'] = result['cgm_slope_15m']-(result['cgm_lag_15m']-result['cgm_lag_30m'])/15
    gaps = glucose.index.to_series().diff().dt.total_seconds().div(60)
    result['cgm_max_gap_60m'] = window_statistics(gaps, cutoffs, 60)['max']
    minute = issues.hour*60+issues.minute
    result['clock_sin'] = np.sin(2*np.pi*minute/1440)
    result['clock_cos'] = np.cos(2*np.pi*minute/1440)
    result['profile_age'] = profile['age']
    duration = profile['diabetes_duration_exact_years']
    result['profile_duration_years'] = np.nan if duration is None else duration
    result['profile_duration_unreported_exact'] = float(duration is None)
    for category in ('female', 'male', 'non_binary', 'unmapped'):
        result[f'profile_gender_{category}'] = float(profile['gender_category'] == category)
    for channel in ('insulin', 'carbs', 'hr', 'steps', 'dist', 'cals'):
        cutoff = issues-pd.Timedelta(minutes=delays[channel])
        latest, age = last_observation(streams[channel], cutoff)
        result[f'{channel}_latest_observed'] = latest
        result[f'{channel}_age_minutes'] = age+delays[channel]
        windows = (60, 120, 240, 480) if channel == 'carbs' else (15, 30, 60, 120)
        for minutes in windows:
            # Dose/action amounts describe intervals ending at source time.
            # Right-closed windows avoid including an extra boundary interval.
            stats = window_statistics(streams[channel], cutoff, minutes,
                                      closed='both' if channel == 'hr' else 'right')
            names = ('mean', 'std', 'min', 'max', 'count') if channel == 'hr' else ('sum', 'count')
            for name in names:
                result[f'{channel}_{name}_{minutes}m'] = stats[name]
            if channel != 'carbs':
                expected = minutes/5+(1 if channel == 'hr' else 0)
                result[f'{channel}_fraction_{minutes}m'] = np.minimum(1, stats['count']/expected)
    eligible = (np.isfinite(result['cgm_current'])
                & (result['cgm_age_minutes'] <= native_minutes+delays['bg'])
                & (result['cgm_fraction_60m'] >= protocol['minimum_past_hour_fraction'])
                & (result['cgm_max_gap_60m'] <= protocol['maximum_past_hour_gap_cadence_multiple']*native_minutes))
    if len(glucose):
        eligible &= cutoffs >= glucose.index[0]+pd.Timedelta(minutes=protocol['warmup_minutes'])
    else:
        eligible[:] = False
    result['history_eligible'] = eligible
    result = pd.DataFrame(result, index=issues)
    result.index.name = 'issued_at'
    return result


def feature_arms(columns):
    base = [i for i, name in enumerate(columns) if name.startswith(('cgm_', 'clock_'))]
    profile = base+[i for i, name in enumerate(columns) if name.startswith('profile_')]
    insulin = profile+[i for i, name in enumerate(columns) if name.startswith('insulin_')]
    carbs = insulin+[i for i, name in enumerate(columns) if name.startswith('carbs_')]
    return {'cgm_only': base, 'cgm_profile': profile, 'cgm_profile_insulin': insulin,
            'cgm_profile_insulin_carbs': carbs, 'fused': list(range(len(columns)))}


def measured_targets(glucose, issues, horizon_minutes):
    if horizon_minutes <= 0:
        raise ValueError('Forecast horizon must be positive')
    return glucose.reindex(issues+pd.Timedelta(minutes=horizon_minutes)).to_numpy()*MG_DL_PER_MMOL_L


def assign_roles(entries, seed):
    """Patient roles depend on IDs/cadence, never outcomes or model scores."""
    if len(entries) != 20 or len({r['participant_id'] for r in entries}) != 20:
        raise ValueError('Expected twenty unique processed participants')
    rng = np.random.default_rng(seed)
    groups = [[] for _ in range(5)]
    for cadence, expected in ((5, 15), (15, 5)):
        ids = sorted(r['participant_id'] for r in entries if r['channels']['bg']['modal_gap_minutes'] == cadence)
        if len(ids) != expected:
            raise ValueError('Unexpected native cadence stratum')
        shuffled = rng.permutation(ids)
        for i, part in enumerate(np.array_split(shuffled, 5)):
            groups[i].extend(str(value) for value in part)
    groups = [sorted(group) for group in groups]
    folds = [{'fold': i+1, 'evaluation': group,
              'fit': sorted(pid for j, other in enumerate(groups[:4]) if j != i for pid in other)}
             for i, group in enumerate(groups[:4])]
    return {'reserved': groups[4], 'development': sorted(pid for group in groups[:4] for pid in group),
            'folds': folds}
