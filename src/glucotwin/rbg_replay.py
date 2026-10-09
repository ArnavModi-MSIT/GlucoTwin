"""RBG replay respects five-minute measurement availability for features and outcomes."""
import numpy as np
import pandas as pd
from glucotwin.rbg import rbg_features

def issue_rbg_forecasts(frame,patient,artifacts,now):
    if patient['split']=='test':raise ValueError('Reserved test patients cannot be replayed')
    now=pd.Timestamp(now);cutoff=now-pd.Timedelta(minutes=5)
    visible=frame.loc[pd.to_datetime(frame.ts)<=cutoff]
    features=rbg_features(visible,patient) if len(visible) else pd.DataFrame()
    row=features.loc[now] if now in features.index else None
    eligible=row is not None and bool(row.history_eligible) and now>=pd.Timestamp(patient['minimum_forecast_time'])
    output=[]
    for horizon,artifact in sorted(artifacts.items()):
        if artifact['sensor_delay_minutes']!=5 or artifact['horizon_minutes']!=horizon:raise ValueError('Artifact timing mismatch')
        result={'issued_at':now,'horizon':horizon,'target_time':now+pd.Timedelta(minutes=horizon),
                'available_at':now+pd.Timedelta(minutes=horizon+5),'prediction':None,'persistence':None,
                'latest_glucose':float(row.cgm_current) if row is not None else np.nan,
                'cgm_count':int(row.cgm_count_60m) if row is not None else 0,'status':'Insufficient history'}
        if now<pd.Timestamp(patient['minimum_forecast_time']):result['status']='24-hour warm-up'
        elif eligible:
            result['prediction']=float(artifact['model'].predict(features.loc[[now],artifact['features']].to_numpy(dtype=np.float32))[0])
            result['persistence']=float(row.cgm_current);result['status']='Forecast issued'
        output.append(result)
    return output

def reveal_rbg_outcomes(ledger,frame,now):
    now=pd.Timestamp(now)
    visible=frame.loc[pd.to_datetime(frame.ts)+pd.Timedelta(minutes=5)<=now].copy()
    source=pd.Series(visible.GlucoseCGM.to_numpy(),index=pd.to_datetime(visible.ts))
    rows=[]
    for issued in ledger:
        row=dict(issued);due=row['available_at']<=now
        actual=source.get(row['target_time'],np.nan) if due else np.nan
        row.update(actual=float(actual),outcome='Observed' if due and pd.notna(actual) else ('Missing observation' if due else 'Pending'),
                   ridge_error=abs(actual-row['prediction']) if pd.notna(actual) and row['prediction'] is not None else np.nan,
                   persistence_error=abs(actual-row['persistence']) if pd.notna(actual) and row['persistence'] is not None else np.nan)
        rows.append(row)
    return pd.DataFrame(rows)
