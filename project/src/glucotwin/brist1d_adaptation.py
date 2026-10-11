"""Matured-outcome calibration of fixed forecasts, with independent patient state."""
from collections import deque
import math
import numpy as np

MINUTE_NS = 60_000_000_000


def scheduled_updates(all_eligible_times, interval_minutes):
    """Schedule independently of future target presence or values."""
    times = np.asarray(all_eligible_times, dtype=np.int64)
    if interval_minutes <= 0 or not np.isfinite(interval_minutes):
        raise ValueError('Invalid update interval')
    if times.ndim != 1 or (len(times)>1 and (np.diff(times)<=0).any()):
        raise ValueError('Eligible issue times must be unique and ordered')
    chosen = np.zeros(len(times), dtype=bool)
    last = None
    interval = interval_minutes*MINUTE_NS
    for i,time in enumerate(times):
        if last is None or time-last>=interval:
            chosen[i] = True; last = time
    return times[chosen]


def adapt_forecasts(issued_at, actual, baseline, all_eligible_times, horizon_minutes, config):
    """Only matured scheduled targets influence correction at each issue time.

    Baseline predictions are fixed population forecasts, not earlier corrected
    forecasts. Sparse exact-target availability does not alter scheduling.
    Each invocation is one patient/method/horizon and starts from zero state.
    """
    times = np.asarray(issued_at,dtype=np.int64)
    actual = np.asarray(actual,dtype=float); baseline = np.asarray(baseline,dtype=float)
    full_times = np.asarray(all_eligible_times,dtype=np.int64)
    if times.ndim!=1 or actual.shape!=times.shape or baseline.shape!=times.shape:
        raise ValueError('Mismatched forecast arrays')
    if (len(times)>1 and (np.diff(times)<=0).any()) or not np.isfinite(actual).all() or not np.isfinite(baseline).all():
        raise ValueError('Forecast times must be ordered; scored values must be finite')
    if horizon_minutes<=0 or config['target_availability_delay_minutes']<0:
        raise ValueError('Invalid horizon or delay')
    for key in ('history_minutes','half_life_minutes','minimum_matured_updates','prior_weight_zero_residual',
                'residual_clip_mg_dl','correction_clip_mg_dl','maximum_latest_update_age_minutes'):
        if not np.isfinite(config[key]) or config[key]<=0: raise ValueError('Invalid adaptation rule: '+key)
    if config['minimum_matured_updates']!=int(config['minimum_matured_updates']):
        raise ValueError('Update minimum must be an integer')
    schedule = scheduled_updates(full_times,config['update_interval_minutes'])
    if not np.isin(times,full_times).all(): raise ValueError('Scored issue not in eligible schedule')
    positions = np.flatnonzero(np.isin(times,schedule))
    available = times[positions]+int((horizon_minutes+config['target_availability_delay_minutes'])*MINUTE_NS)
    history = int(config['history_minutes']*MINUTE_NS)
    expiry = int(config['maximum_latest_update_age_minutes']*MINUTE_NS)
    rate = math.log(2)/(config['half_life_minutes']*MINUTE_NS)
    corrections = np.zeros(len(times)); active = np.zeros(len(times),dtype=bool)
    counts = np.zeros(len(times),dtype=np.int32)
    queue = deque(); pointer = 0; weight = weighted_residual = 0.; last_time = None
    for i,time in enumerate(times):
        if last_time is not None:
            decay = math.exp(-rate*int(time-last_time))
            weight *= decay; weighted_residual *= decay
        last_time = time
        while pointer<len(positions) and available[pointer]<=time:
            position = positions[pointer]
            # Read actual only after its availability time; never look ahead.
            residual = float(np.clip(actual[position]-baseline[position],
                                     -config['residual_clip_mg_dl'],config['residual_clip_mg_dl']))
            arrival = int(available[pointer])
            if arrival>=time-history:
                w = math.exp(-rate*int(time-arrival))
                queue.append((arrival,residual)); weight += w; weighted_residual += w*residual
            pointer += 1
        while queue and queue[0][0]<time-history:
            arrival,residual = queue.popleft()
            w = math.exp(-rate*int(time-arrival))
            weight -= w; weighted_residual -= w*residual
        if not queue: weight = weighted_residual = 0.
        weight = max(0.,weight)
        counts[i] = len(queue)
        active[i] = len(queue)>=config['minimum_matured_updates'] and time-queue[-1][0]<=expiry
        if active[i]:
            corrections[i] = np.clip(weighted_residual/(weight+config['prior_weight_zero_residual']),
                                     -config['correction_clip_mg_dl'],config['correction_clip_mg_dl'])
    return {'predicted':baseline+corrections,'correction':corrections,'active':active,
            'matured_count':counts,'scheduled_updates_with_exact_targets':len(positions),
            'all_scheduled_updates':len(schedule),'matured_updates_by_last_issue':pointer}
