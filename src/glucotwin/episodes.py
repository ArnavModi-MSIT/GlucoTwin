"""Frozen engineering episode rules and causal alarm cooldown."""
import numpy as np
import pandas as pd

def onsets(glucose,event):
    g=glucose.sort_index()
    if g.index.has_duplicates:raise ValueError('Duplicate times')
    g=g.reindex(pd.date_range(g.index.min(),g.index.max(),freq='5min'))
    inside=(g>180 if event=='high' else g<70)&g.notna()
    outside=(~inside)&g.notna()
    prior=outside.shift(1,fill_value=False).rolling(7,min_periods=7).sum().eq(7)
    sustained=inside.astype(int).rolling(4,min_periods=4).sum().shift(-3).eq(4)
    return g.index[prior&sustained]

def alarm_times(times,scores,threshold,cooldown_minutes=60):
    alarms=[];last=None
    for t in pd.DatetimeIndex(times)[np.asarray(scores)>=threshold]:
        if last is None or t-last>=pd.Timedelta(minutes=cooldown_minutes):
            alarms.append(t);last=t
    return pd.DatetimeIndex(alarms)

def assess(alarms,episodes,opportunities,glucose):
    episodes=pd.DatetimeIndex(episodes);opportunities=pd.DatetimeIndex(opportunities)
    # An opportunity exists in [onset-30,onset-5]. No target requirement.
    eligible=[]
    for onset in episodes:
        left=opportunities.searchsorted(onset-pd.Timedelta(minutes=30))
        right=opportunities.searchsorted(onset-pd.Timedelta(minutes=5),side='right')
        if right>left:eligible.append(onset)
    matched=set();lead=[];false=unknown=redundant=0
    for t in alarms:
        candidates=episodes[(episodes>=t+pd.Timedelta(minutes=5))&(episodes<=t+pd.Timedelta(minutes=30))]
        available=[e for e in candidates if e not in matched]
        if available:
            onset=available[0];matched.add(onset);lead.append((onset-t).total_seconds()/60)
        elif len(candidates):redundant+=1
        else:
            future=glucose.reindex(pd.date_range(t+pd.Timedelta(minutes=5),periods=9,freq='5min'))
            if future.notna().all():false+=1
            else:unknown+=1
    days=len(opportunities)*5/1440
    n=len(alarms);tp=len(matched)
    return {'qualifying_episodes':len(episodes),'evaluable_episodes':len(eligible),'detected_episodes':tp,
            'alarms':n,'false_alarms':false,'unknown_alarms':unknown,'redundant_alarms':redundant,
            'eligible_monitoring_days':days,'false_per_eligible_day':false/days if days else None,
            'episode_recall':tp/len(eligible) if eligible else None,'all_episode_recall':tp/len(episodes) if len(episodes) else None,
            'median_lead_minutes':float(np.median(lead)) if lead else None,'lead_minutes':lead,
            'precision_lower_bound':tp/n if n else None,'precision_upper_bound':(tp+unknown)/n if n else None}
