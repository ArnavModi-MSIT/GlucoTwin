"""Past-only summaries on the original five-minute phase; no interpolation."""
import numpy as np
import pandas as pd


def observed_excursions(readings):
    """Describe contiguous out-of-band runs on an available five-minute grid.

    Four consecutive readings span at least 15 observed minutes. Unknown
    boundary readings censor a run rather than proving its onset or recovery.
    This descriptive rule is independent of prediction/event evaluation labels.
    """
    values = readings.to_numpy(dtype=float)
    if not len(values):
        return []
    kinds = np.where(np.isfinite(values), np.where(values < 70, -1, np.where(values > 180, 1, 0)), 0)
    boundaries = np.flatnonzero(np.r_[True, kinds[1:] != kinds[:-1], True])
    rows = []
    for first, stop in zip(boundaries[:-1], boundaries[1:]):
        if kinds[first] == 0 or stop-first < 4:
            continue
        part = readings.iloc[first:stop]
        kind = 'low' if kinds[first] == -1 else 'high'
        before = first > 0 and np.isfinite(values[first-1])
        after = stop < len(values) and np.isfinite(values[stop])
        left = 'observed_crossing' if before else 'history_boundary' if first == 0 else 'gap'
        right = 'observed_exit' if after else 'cutoff' if stop == len(values) else 'gap'
        extreme_at = part.idxmin() if kind == 'low' else part.idxmax()
        context = readings.iloc[first-int(before):stop+int(after)]
        rows.append(dict(id=kind+'-'+part.index[0].isoformat(), kind=kind,
            first_observed=part.index[0].isoformat(), last_observed=part.index[-1].isoformat(),
            confirmed_at=part.index[3].isoformat(), samples=len(part),
            observed_span_minutes=int((part.index[-1]-part.index[0]).total_seconds()/60),
            minimum=float(part.min()), maximum=float(part.max()), mean=float(part.mean()),
            extreme_at=extreme_at.isoformat(), start_boundary=left, end_boundary=right,
            next_observed_at=readings.index[stop].isoformat() if after else None,
            points=[dict(time=t.isoformat(),glucose=float(v)) for t,v in context.items()]))
    return rows


def descriptive_profile(times, values, cutoff):
    """Fourteen study dates, hourly distributions across covered past days."""
    cutoff=pd.Timestamp(cutoff);times=pd.DatetimeIndex(times)
    values=np.asarray(values,dtype=float)
    if len(times)!=len(values):raise ValueError('Times and readings must have the same length')
    start=cutoff.normalize()-pd.Timedelta(days=13)
    selected=(times>=start)&(times<=cutoff)
    source=pd.Series(values[selected],index=times[selected]).sort_index()
    if source.index.has_duplicates:raise ValueError('Duplicate historical timestamps')
    phase_start=cutoff-((cutoff-start)//pd.Timedelta(minutes=5))*pd.Timedelta(minutes=5)
    grid=pd.date_range(phase_start,cutoff,freq='5min')
    g=source.reindex(grid).replace([np.inf,-np.inf],np.nan)
    known=g.dropna();mean=float(known.mean()) if len(known) else None
    std=float(known.std(ddof=0)) if len(known) else None
    frame=pd.DataFrame(dict(value=g,date=grid.strftime('%Y-%m-%d'),hour=grid.hour))
    complete_days=sum(len(part)==288 and part.value.notna().mean()>=.7 for _,part in frame.groupby('date'))
    hours=[]
    for hour in range(24):
        covered=[part.value.dropna() for _,part in frame.loc[frame.hour==hour].groupby('date')
                 if len(part)==12 and part.value.notna().sum()>=10]
        enough=len(covered)>=3
        readings=pd.concat(covered) if enough else pd.Series(dtype=float)
        quantiles=np.quantile(readings,[.1,.25,.5,.75,.9]).tolist() if enough else [None]*5
        hours.append(dict(hour=hour,covered_days=len(covered),samples=len(readings),
                          **dict(zip(['p10','p25','median','p75','p90'],quantiles))))
    night=frame.loc[frame.hour<6].value.dropna()
    return dict(through=cutoff.isoformat(),start=phase_start.isoformat(),expected=len(grid),samples=len(known),
                coverage=len(known)/len(grid),observed_days=int(frame.loc[frame.value.notna(),'date'].nunique()),
                complete_covered_days=int(complete_days),mean=mean,std=std,
                coefficient_variation_pct=100*std/mean if mean and mean>0 else None,
                overnight=dict(samples=len(night),mean=float(night.mean()) if len(night) else None,
                    below70_fraction=float((night<70).mean()) if len(night) else None,
                    expected=int((frame.hour<6).sum())),hours=hours,
                note='Past-only fourteen-date profile. Five-minute readings, no gap interpolation. Each hourly distribution needs at least three days, each with 10/12 readings in a complete hour. Historical percentiles are not forecast intervals or personalized targets.')


def historical_patterns(times, values, cutoff):
    cutoff = pd.Timestamp(cutoff)
    times = pd.DatetimeIndex(times)
    values = np.asarray(values, dtype=float)
    if len(times) != len(values):
        raise ValueError('Times and readings must have the same length')
    start = cutoff.normalize() - pd.Timedelta(days=6)
    selected = (times >= start) & (times <= cutoff)
    source = pd.Series(values[selected], index=times[selected]).sort_index()
    if source.index.has_duplicates:
        raise ValueError('Duplicate historical timestamps')
    if source.empty:
        return dict(through=cutoff.isoformat(), daily=[], hourly=[], excursions=[], periods=[], observed_samples=0,
                    note='No available historical readings.',profile=descriptive_profile(times,values,cutoff))
    first = max(start, source.index.min())
    first = cutoff - ((cutoff-first)//pd.Timedelta(minutes=5))*pd.Timedelta(minutes=5)
    grid = pd.date_range(first, cutoff, freq='5min')
    g = source.reindex(grid).replace([np.inf, -np.inf], np.nan)
    frame = pd.DataFrame({'value': g, 'date': grid.strftime('%Y-%m-%d'), 'block': grid.hour//6})
    daily = []
    for date, part in frame.groupby('date', sort=True):
        known = part.value.dropna()
        count = len(known)
        daily.append(dict(date=date, samples=count, expected=len(part),
                          coverage=count/len(part), mean=float(known.mean()) if count else None,
                          low_fraction=float((known < 70).mean()) if count else None,
                          reference_fraction=float(known.between(70,180).mean()) if count else None,
                          high_fraction=float((known > 180).mean()) if count else None))
    hourly = []
    for (date, hour), part in frame.groupby(['date', frame.index.hour], sort=True):
        known = part.value.dropna()
        count = len(known)
        hour_end = pd.Timestamp(date) + pd.Timedelta(hours=int(hour)+1)
        complete = len(part) == 12 and hour_end <= cutoff
        hourly.append(dict(date=date, hour=int(hour), first_checkpoint=part.index[0].isoformat(),
            last_checkpoint=part.index[-1].isoformat(), samples=count, expected=len(part),
            coverage=count/len(part), complete_hour=bool(complete), comparable=bool(complete and count>=10),
            mean=float(known.mean()) if count else None,
            minimum=float(known.min()) if count else None, maximum=float(known.max()) if count else None,
            low_fraction=float((known < 70).mean()) if count else None,
            reference_fraction=float(known.between(70,180).mean()) if count else None,
            high_fraction=float((known > 180).mean()) if count else None))
    periods = []
    for block in range(4):
        eligible = []
        for _, part in frame.loc[frame.block == block].groupby('date'):
            known = part.value.dropna()
            if len(part) == 72 and len(known)/72 >= .8:
                eligible.append(known)
        n = len(eligible)
        high = sum(float((g > 180).mean()) >= .2 for g in eligible)
        low = sum(float((g < 70).mean()) >= .05 for g in eligible)
        recurring = []
        if high >= 2 and high/n >= .5:
            recurring.append('Repeated high readings')
        if low >= 2 and low/n >= .5:
            recurring.append('Repeated low readings')
        periods.append(dict(start_hour=block*6, end_hour=(block+1)*6,
                            eligible_days=n, high_days=high, low_days=low,
                            description='; '.join(recurring) if recurring else
                            'Insufficient comparable days' if n < 2 else 'No repeated pattern under this rule'))
    return dict(through=cutoff.isoformat(), daily=daily, hourly=hourly, excursions=observed_excursions(g), periods=periods,
                observed_samples=int(g.notna().sum()),
                profile=descriptive_profile(times,values,cutoff),
                note='Last seven study dates through data cutoff. Five-minute samples; gaps stay missing. Reference bands: below 70, 70–180 and above 180 mg/dL. Descriptive history, not a future forecast or individualized target.')
