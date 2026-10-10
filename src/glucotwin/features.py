"""Shared batch/replay feature builder; target construction is deliberately separate."""
import numpy as np
import pandas as pd

STATIC = ['age', 'gender_f', 'bmi', 'hba1c_pct', 'fasting_glucose']
HR = [f'hr_{stat}_{minutes}m' for minutes in (15, 30, 60) for stat in ('mean', 'std', 'fraction')]

def make_features(frame, profile, phase, include_hr=True):
    """For replay pass only the visible prefix. Returns features on the 5-minute grid."""
    data = frame.copy()
    data.columns = data.columns.str.strip()
    data['Timestamp'] = pd.to_datetime(data['Timestamp'])
    if data.Timestamp.duplicated().any() or not data.Timestamp.is_monotonic_increasing:
        raise ValueError('Timestamps must be unique and sorted')
    data = data.set_index('Timestamp')
    minutes = data.index.to_numpy(dtype='datetime64[ns]').astype('int64') // 60_000_000_000
    selected = data.index[minutes % 5 == phase]
    if len(selected) == 0:
        return pd.DataFrame()
    grid = pd.date_range(selected.min(), selected.max(), freq='5min')
    glucose = pd.to_numeric(data['Dexcom GL'], errors='coerce').reindex(grid)
    result = pd.DataFrame({'cgm_current': glucose}, index=grid)
    for length in (15, 30, 60):
        count = length // 5 + 1
        roll = glucose.rolling(count, min_periods=1)
        for stat in ('mean', 'std', 'min', 'max', 'count'):
            result[f'cgm_{stat}_{length}m'] = getattr(roll, stat)()
        result[f'cgm_change_{length}m'] = glucose - glucose.shift(length // 5)
    # Slope with missing observations ignored, using fixed grid offsets.
    x = pd.Series(np.arange(len(grid), dtype=float)*5, index=grid)
    mask = glucose.notna().astype(float)
    n = mask.rolling(7, min_periods=1).sum()
    sx = (x*mask).rolling(7, min_periods=1).sum()
    sy = glucose.fillna(0).rolling(7, min_periods=1).sum()
    sxx = (x*x*mask).rolling(7, min_periods=1).sum()
    sxy = (x*glucose.fillna(0)).rolling(7, min_periods=1).sum()
    denominator = n*sxx-sx*sx
    result['cgm_slope_30m'] = (n*sxy-sx*sy).div(denominator.where(denominator>0))
    result['cgm_missing_fraction_60m'] = 1-result.cgm_count_60m/13
    observed = np.isfinite(glucose.to_numpy())
    windows = np.lib.stride_tricks.sliding_window_view(np.pad(observed,(12,0)),13)
    positions = np.arange(13)
    previous = np.maximum.accumulate(np.where(windows,positions,-1),axis=1)
    previous = np.concatenate([np.full((len(grid),1),-1),previous[:,:-1]],axis=1)
    gaps = np.where(windows & (previous>=0), (positions-previous)*5, 0)
    result['cgm_max_gap_60m'] = gaps.max(axis=1)
    heart = pd.to_numeric(data['HR'], errors='coerce') if include_hr else None
    for length in (15, 30, 60) if include_hr else ():
        rolling = heart.rolling(f'{length}min',closed='both',min_periods=1)
        result[f'hr_mean_{length}m'] = rolling.mean().reindex(grid)
        result[f'hr_std_{length}m'] = rolling.std().reindex(grid)
        result[f'hr_fraction_{length}m'] = rolling.count().reindex(grid)/(length+1)
    for column in STATIC:
        result[column] = profile[column]
    result['history_eligible'] = glucose.notna() & (result.cgm_count_60m>=10) & (result.cgm_max_gap_60m<=15)
    result.index.name = 'prediction_time'
    return result

def profile_features(row):
    return {'age':float(row['Age']), 'gender_f':float(str(row['Gender']).strip()=='F'),
            'bmi':float(row['BMI']), 'hba1c_pct':float(row['A1c PDL (Lab)']),
            'fasting_glucose':float(row['Fasting GLU - PDL (Lab)'])}
