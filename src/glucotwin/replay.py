"""Replay inference consumes only visible records; outcomes are a separate read."""
import pandas as pd
from glucotwin.features import make_features


def issue_forecast(frame, profile, patient, artifact, now):
    now = pd.Timestamp(now)
    if patient['split'] == 'test':
        raise ValueError('Reserved test patients cannot be replayed')
    visible = frame.loc[pd.to_datetime(frame.Timestamp) <= now]
    features = make_features(visible, profile, patient['phase_utc_minutes_mod_5'])
    result = {'issued_at': now, 'target_time': now + pd.Timedelta(minutes=60),
              'prediction': None, 'status': 'Insufficient history'}
    if now not in features.index:
        return result
    row = features.loc[now]
    result.update(current=row.cgm_current, cgm_count=int(row.cgm_count_60m),
                  hr_fraction=float(row.hr_fraction_60m))
    if now < pd.Timestamp(patient['minimum_forecast_time']):
        result['status'] = '24-hour warm-up'
    elif row.history_eligible:
        result['prediction'] = float(artifact['model'].predict(features.loc[[now], artifact['features']])[0])
        result['status'] = 'Forecast issued'
    return result


def reveal_outcomes(ledger, frame, now):
    """Return a display copy, never alter issued predictions or expose future targets."""
    visible = frame.loc[pd.to_datetime(frame.Timestamp) <= pd.Timestamp(now)].copy()
    visible.Timestamp = pd.to_datetime(visible.Timestamp)
    source = visible.set_index('Timestamp')['Dexcom GL']
    rows = []
    for issued in ledger:
        row = dict(issued)
        due = row['target_time'] <= pd.Timestamp(now)
        actual = source.get(row['target_time'], float('nan')) if due else float('nan')
        row['actual'] = float(actual)
        row['outcome'] = 'Pending' if not due else ('Observed' if pd.notna(actual) else 'Missing observation')
        row['absolute_error'] = abs(actual-row['prediction']) if pd.notna(actual) and row['prediction'] is not None else float('nan')
        rows.append(row)
    return pd.DataFrame(rows)
