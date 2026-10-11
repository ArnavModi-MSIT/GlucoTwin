"""Causal additional features for research; deployed feature contracts are unchanged."""
import numpy as np


def extend_history(features):
    result = features.copy()
    glucose = result['cgm_current']
    for minutes in (5, 10, 20, 45, 90, 120):
        result[f'cgm_lag_{minutes}m'] = glucose.shift(minutes // 5)
    for minutes in (120, 240, 1440):
        rolling = glucose.rolling(minutes // 5 + 1, min_periods=1)
        for stat in ('mean', 'std', 'min', 'max'):
            result[f'cgm_{stat}_{minutes}m'] = getattr(rolling, stat)()
        result[f'cgm_fraction_{minutes}m'] = rolling.count() / (minutes // 5 + 1)
    result['cgm_change_5m'] = glucose.diff()
    result['cgm_acceleration_5m'] = glucose.diff().diff()
    result['cgm_relative_daily_mean'] = glucose - result['cgm_mean_1440m']
    minute = result.index.hour * 60 + result.index.minute
    result['clock_sin'] = np.sin(2 * np.pi * minute / 1440)
    result['clock_cos'] = np.cos(2 * np.pi * minute / 1440)
    return result
