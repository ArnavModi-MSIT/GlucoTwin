"""DCLP3 measured endpoints and causal features under an explicit contract."""
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, train_test_split

from .brist1d import last_observation, window_statistics


def assign_roles(roster, pump_ids, protocol):
    enrolled = roster.loc[roster.RandDt.ne('') & roster.trtGroup.isin(['CLC', 'SAP'])].copy()
    enrolled = enrolled.sort_values('PtID')
    if len(enrolled) != protocol['participants'] or enrolled.PtID.duplicated().any():
        raise ValueError('Unexpected randomized cohort')
    ids = enrolled.PtID.to_numpy()
    strata = (enrolled.trtGroup + enrolled.PtID.isin(pump_ids).map(
        {True: '_pump', False: '_no_pump'})).to_numpy()
    dev, reserve = train_test_split(np.arange(len(ids)), test_size=protocol['reserved_patients'],
        random_state=protocol['seed'], stratify=strata)
    dev = np.sort(dev)
    folds = []
    splitter = StratifiedKFold(n_splits=protocol['development_folds'], shuffle=True,
                              random_state=protocol['seed'])
    for i, (fit, evaluation) in enumerate(splitter.split(dev, strata[dev]), 1):
        folds.append({'fold': i, 'fit': sorted(ids[dev[fit]].tolist()),
                      'evaluation': sorted(ids[dev[evaluation]].tolist())})
    return {'development': sorted(ids[dev].tolist()), 'reserved': sorted(ids[reserve].tolist()),
            'folds': folds, 'strata': dict(zip(ids.tolist(), strata.tolist()))}


def canonical_cgm(times, values, protocol):
    frame = pd.DataFrame({'time': pd.to_datetime(times), 'value': np.asarray(values, dtype=float)})
    valid = frame.time.notna() & np.isfinite(frame.value)
    frame = frame.loc[valid]
    grouped = frame.groupby('time').value.agg(['first', 'nunique', 'size'])
    conflicts = grouped['nunique'].gt(1)
    stream = grouped['first'].copy()
    # Preserve unknown/conflict timestamps as barriers rather than falling back
    # silently to an older value after a contradictory new observation.
    stream.loc[conflicts] = np.nan
    lo, hi = protocol['cgm_exact_range']
    recognized = stream.between(lo, hi) | stream.isin([float(x) for x in protocol['boundary_codes']])
    stream.loc[~recognized] = np.nan
    return stream, {'source_rows': len(frame), 'extra_identical_rows': int(
        (grouped.loc[~conflicts, 'size'] - 1).sum()),
        'conflicting_timestamps': int(conflicts.sum()),
        'unknown_value_timestamps': int(stream.isna().sum())}


def issue_times(raw, protocol):
    delay = protocol['availability_delay_minutes']['cgm']
    if protocol.get('issue_schedule_kind') == 'native_observation':
        return raw.index + pd.Timedelta(minutes=delay)
    start = (raw.index[0]+pd.Timedelta(minutes=protocol['warmup_minutes']+delay)).ceil('5min')
    end = (raw.index[-1]+pd.Timedelta(minutes=delay)).floor('5min')
    return pd.date_range(start, end, freq=f'{protocol["issue_cadence_minutes"]}min')


def measured_targets(raw, issues, horizon, protocol):
    if horizon not in protocol['horizons_minutes']:
        raise ValueError('Unknown horizon')
    times = raw.index.asi8
    desired = (issues + pd.Timedelta(minutes=horizon)).asi8
    if not len(times):
        raise ValueError('Empty target stream')
    right = np.searchsorted(times, desired)
    left = np.clip(right - 1, 0, len(times)-1)
    right = np.clip(right, 0, len(times)-1)
    # <= deliberately resolves equidistant ties to the earlier measured reading.
    position = np.where(np.abs(times[left]-desired) <= np.abs(times[right]-desired), left, right)
    offset = (times[position]-desired) / 1e9
    matched = np.abs(offset) <= protocol['target_tolerance_seconds']
    value = raw.to_numpy()[position].astype(float)
    lo, hi = protocol['cgm_exact_range']
    exact_value = np.isfinite(value) & (value >= lo) & (value <= hi)
    boundary = matched & np.isin(value, [float(x) for x in protocol['boundary_codes']])
    outcome = np.where(matched & exact_value, value, np.nan)
    target_time = np.where(matched, times[position], np.iinfo(np.int64).min)
    offset = np.where(matched, offset, np.nan)
    return {'y': outcome, 'offset_seconds': offset, 'matched_time_ns': target_time,
            'boundary': boundary, 'strict': np.isfinite(outcome) & (offset == 0)}


def basal_integral(rate, cutoffs, minutes, freshness_minutes):
    """Integrate only past, finite, nonnegative rate state before expiry.

    A zero rate is an observed state. Unknown intervals produce zero known
    duration, not an assertion of no insulin. No future change may fill a gap.
    """
    if not len(rate):
        return np.full(len(cutoffs), np.nan), np.zeros(len(cutoffs))
    t = rate.index.asi8 / 1e9
    value = rate.to_numpy(dtype=float)
    end = np.minimum(np.r_[t[1:], np.inf], t + freshness_minutes*60)
    good = np.isfinite(value) & (value >= 0)
    durations = np.where(good, end-t, 0)
    amounts = durations * np.where(good, value, 0) / 3600
    cumulative_seconds = np.r_[0, np.cumsum(durations)]
    cumulative_units = np.r_[0, np.cumsum(amounts)]

    def prefix(query):
        q = query.asi8 / 1e9
        pos = np.searchsorted(t, q, side='right')-1
        clipped = np.maximum(pos, 0)
        elapsed = np.where((pos >= 0) & good[clipped],
                           np.maximum(0, np.minimum(q, end[clipped])-t[clipped]), 0)
        duration = np.where(pos >= 0, cumulative_seconds[clipped], 0) + elapsed
        units = np.where(pos >= 0, cumulative_units[clipped], 0) + elapsed*np.where(good[clipped], value[clipped], 0)/3600
        return units, duration

    current_units, current_seconds = prefix(cutoffs)
    previous_units, previous_seconds = prefix(cutoffs-pd.Timedelta(minutes=minutes))
    fraction = np.clip((current_seconds-previous_seconds)/(minutes*60), 0, 1)
    units = current_units-previous_units
    units[fraction == 0] = np.nan
    return units, fraction


def make_features(raw, issues, profile, basal, bolus, protocol):
    if not issues.is_monotonic_increasing or issues.has_duplicates:
        raise ValueError('Issue times must be unique and sorted')
    glucose = raw.copy()
    for code, proxy in protocol['boundary_codes'].items():
        glucose.loc[raw.eq(float(code))] = float(proxy)
    cutoff = issues-pd.Timedelta(minutes=protocol['availability_delay_minutes']['cgm'])
    current, age = last_observation(glucose, cutoff)
    raw_current, _ = last_observation(raw, cutoff)
    result = {'cgm_current': current, 'cgm_age_minutes': age+protocol['availability_delay_minutes']['cgm'],
              'cgm_current_code_low': (raw_current == 39).astype(float),
              'cgm_current_code_high': (raw_current == 401).astype(float)}
    for minutes in (15, 30, 60, 120):
        lag, lag_age = last_observation(glucose, cutoff-pd.Timedelta(minutes=minutes))
        lag[lag_age*60 > protocol['lag_freshness_seconds']] = np.nan
        result[f'cgm_lag_{minutes}m'] = lag
        result[f'cgm_change_{minutes}m'] = current-lag
        stats = window_statistics(glucose, cutoff, minutes)
        for stat in ('mean', 'std', 'min', 'max', 'count'):
            result[f'cgm_{stat}_{minutes}m'] = stats[stat]
    gaps = raw.index.to_series().diff().dt.total_seconds()
    result['cgm_max_gap_60m'] = window_statistics(gaps, cutoff, 60)['max']
    for code, label in ((39, 'low'), (401, 'high')):
        result[f'cgm_code_{label}_count_60m'] = window_statistics(raw.eq(code).astype(float), cutoff, 60)['sum']
    minute = issues.hour*60 + issues.minute
    result['clock_sin'] = np.sin(2*np.pi*minute/1440)
    result['clock_cos'] = np.cos(2*np.pi*minute/1440)
    for name, item in profile.items():
        available = item['available_at']
        known = np.zeros(len(issues), dtype=bool) if available is None else issues >= pd.Timestamp(available)
        result['profile_'+name] = np.where(known, np.nan if item['value'] is None else item['value'], np.nan)
    pump_cutoff = issues-pd.Timedelta(minutes=protocol['availability_delay_minutes']['pump'])
    latest, basal_age = last_observation(basal, pump_cutoff)
    stale = ~np.isfinite(latest) | (basal_age > protocol['basal_state_freshness_minutes'])
    latest[stale] = np.nan
    result['insulin_basal_latest_known'] = latest
    result['insulin_basal_stale_or_missing'] = stale.astype(float)
    result['insulin_basal_recency_capped'] = np.minimum(basal_age, protocol['basal_state_freshness_minutes'])
    for minutes in (30, 60, 120):
        units, fraction = basal_integral(basal, pump_cutoff, minutes, protocol['basal_state_freshness_minutes'])
        result[f'insulin_basal_known_units_{minutes}m'] = units
        result[f'insulin_basal_known_fraction_{minutes}m'] = fraction
    all_bolus = bolus['amount'].groupby(level=0).sum() if len(bolus) else pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    latest, event_age = last_observation(all_bolus, pump_cutoff)
    cap = protocol['bolus_recency_cap_minutes']
    stale = ~np.isfinite(latest) | (event_age > cap)
    result['insulin_bolus_recency_capped'] = np.minimum(event_age, cap)
    result['insulin_bolus_stale_or_missing'] = stale.astype(float)
    for kind in ('Standard', 'Extended'):
        events = bolus.loc[bolus.kind.eq(kind), 'amount'].groupby(level=0).sum() if len(bolus) else all_bolus
        for minutes in (30, 60, 120, 240, 360):
            stats = window_statistics(events, pump_cutoff, minutes, closed='right')
            for stat in ('sum', 'count'):
                result[f'insulin_bolus_{kind.lower()}_{stat}_{minutes}m'] = stats[stat]
    eligible = (np.isfinite(current) & (result['cgm_age_minutes']*60 <= protocol['maximum_current_age_seconds'])
                & (result['cgm_count_60m'] >= protocol['minimum_past_hour_samples'])
                & (result['cgm_max_gap_60m'] <= protocol['maximum_past_hour_gap_seconds'])
                & (cutoff >= raw.index[0]+pd.Timedelta(minutes=protocol['warmup_minutes'])))
    result['history_eligible'] = eligible
    frame = pd.DataFrame(result, index=issues)
    frame.index.name = 'issued_at'
    return frame


def feature_arms(columns):
    base = [i for i, col in enumerate(columns) if col.startswith(('cgm_', 'clock_'))]
    profile = base + [i for i, col in enumerate(columns) if col.startswith('profile_')]
    return {'cgm_only': base, 'cgm_profile': profile,
            'cgm_profile_insulin': profile+[i for i, col in enumerate(columns) if col.startswith('insulin_')]}
