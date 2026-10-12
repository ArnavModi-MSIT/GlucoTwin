"""Past-only summaries on the original five-minute phase; no interpolation."""
import numpy as np
import pandas as pd


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
        return dict(through=cutoff.isoformat(), daily=[], periods=[], observed_samples=0,
                    note='No available historical readings.')
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
    return dict(through=cutoff.isoformat(), daily=daily, periods=periods,
                observed_samples=int(g.notna().sum()),
                note='Last seven study dates through data cutoff. Five-minute samples; gaps stay missing. Reference bands: below 70, 70–180 and above 180 mg/dL. Descriptive history, not a future forecast or individualized target.')
