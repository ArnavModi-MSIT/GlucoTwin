"""Fixed, outcome-independent repair of observation freshness features."""
import numpy as np
import pandas as pd


def repair_freshness(features, caps):
    """Retain rows/window features; change only ages/latest values and add flags.

    Insulin observation freshness is not time since a bolus or insulin activity.
    Missing meal logs remain unknown. No outcome or patient role is an input.
    """
    result = features.copy()
    flags = {}
    for channel, cap in caps.items():
        if not np.isfinite(cap) or cap <= 0:
            raise ValueError('Freshness cap must be positive and finite')
        age_name = channel+'_age_minutes'
        value_name = channel+'_latest_observed'
        ages = result[age_name].to_numpy(dtype=float)
        if np.isinf(ages).any() or (ages[np.isfinite(ages)] < 0).any():
            raise ValueError('Invalid observation age')
        unknown = np.isnan(ages)
        stale = np.isfinite(ages) & (ages > cap)
        result[age_name] = np.minimum(ages, cap)
        result.loc[stale | unknown, value_name] = np.nan
        flags[channel+'_unobserved'] = unknown.astype(float)
        flags[channel+'_stale'] = stale.astype(float)
    return pd.concat([result, pd.DataFrame(flags, index=result.index)], axis=1)


def diagnostic_masks(features, actual, predicted):
    """Outcome-conditioned masks are descriptive only, never model gates."""
    masks = {'all': np.ones(len(actual), dtype=bool), 'actual_low': actual < 70,
             'actual_high': actual > 180}
    for name, values in [('current', features.cgm_current.to_numpy()), ('predicted', predicted)]:
        edges = [-np.inf, 70, 80, 100, 140, 180, 250, np.inf]
        for low, high in zip(edges[:-1], edges[1:]):
            masks[f'{name}_{low:g}_to_{high:g}'] = (values >= low) & (values < high)
    cadence = features.cgm_native_cadence_minutes.to_numpy()
    for value in (5, 15):
        masks[f'cadence_{value}min'] = cadence == value
        masks[f'actual_low_cadence_{value}min'] = (actual < 70) & (cadence == value)
    slope = features.cgm_slope_15m.to_numpy()
    for name, mask in [('falling', slope < -.5), ('stable', np.abs(slope) <= .5),
                       ('rising', slope > .5), ('unknown', ~np.isfinite(slope))]:
        masks['slope_'+name] = mask
        masks['actual_low_slope_'+name] = (actual < 70) & mask
    for channel in ('insulin', 'carbs', 'hr'):
        ages = features[channel+'_age_minutes'].to_numpy()
        for low, high in [(-np.inf, 30), (30, 120), (120, 360), (360, np.inf)]:
            mask = (ages > low) & (ages <= high)
            masks[f'{channel}_age_{low:g}_to_{high:g}'] = mask
            masks[f'actual_low_{channel}_age_{low:g}_to_{high:g}'] = (actual < 70) & mask
        masks[channel+'_never_observed'] = ~np.isfinite(ages)
        masks['actual_low_'+channel+'_never_observed'] = (actual < 70) & ~np.isfinite(ages)
    return masks
