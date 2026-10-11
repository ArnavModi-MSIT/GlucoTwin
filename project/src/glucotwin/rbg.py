"""Delayed RBG features share the glucose calculations used by replay."""
import numpy as np
import pandas as pd
from glucotwin.features import make_features, STATIC


def rbg_features(frame, patient):
    source=pd.DataFrame({'Timestamp':pd.to_datetime(frame.ts),'Dexcom GL':pd.to_numeric(frame.GlucoseCGM,errors='coerce'),'HR':np.nan})
    profile={c:np.nan for c in STATIC}
    base=make_features(source,profile,0,include_hr=False)
    result=base[[c for c in base if c.startswith('cgm_')]+['history_eligible']].copy()
    # Feature time s is shifted to its availability/issue time t=s+5.
    complete=(base.index>=source.Timestamp.iloc[0]+pd.Timedelta(minutes=60))
    result['history_eligible'] &= complete
    result.index=result.index+pd.Timedelta(minutes=5)
    result.index.name='issue_time'
    result['age_at_enrollment']=patient['age_at_enrollment']
    result['sex_f']=patient['sex_f']
    return result


def supervised_rbg(frame,patient,horizon):
    features=rbg_features(frame,patient)
    glucose=pd.Series(pd.to_numeric(frame.GlucoseCGM,errors='coerce').to_numpy(),index=pd.to_datetime(frame.ts))
    labels=glucose.reindex(features.index+pd.Timedelta(minutes=horizon))
    labels.index=features.index
    eligible=features.history_eligible & labels.notna() & (features.index>=pd.Timestamp(patient['minimum_forecast_time']))
    chosen=features.loc[eligible].drop(columns='history_eligible').copy()
    chosen['target']=labels.loc[eligible]
    return chosen
