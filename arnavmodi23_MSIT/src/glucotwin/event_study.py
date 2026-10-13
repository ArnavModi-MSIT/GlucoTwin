"""Labels and aggregate metrics for a future-onset development experiment."""
import numpy as np
import pandas as pd
from glucotwin.episodes import onsets,alarm_times,assess

def onset_labels(glucose,times):
    """Future labels only; never use this function to construct model inputs."""
    glucose=glucose.sort_index()
    if glucose.index.has_duplicates:raise ValueError('Duplicate glucose timestamps')
    times=pd.DatetimeIndex(times)
    events=onsets(glucose,'high')
    left=events.searchsorted(times+pd.Timedelta(minutes=5))
    right=events.searchsorted(times+pd.Timedelta(minutes=30),side='right')
    known=np.ones(len(times),dtype=bool)
    for offset in range(5,46,5):
        known &= np.isfinite(glucose.reindex(times+pd.Timedelta(minutes=offset)).to_numpy(dtype=float))
    return (right>left).astype(np.int8),known

def summarize(rows):
    keys=['qualifying_episodes','evaluable_episodes','detected_episodes','alarms',
          'false_alarms','unknown_alarms','redundant_alarms','eligible_monitoring_days']
    total={k:sum(r[k] for r in rows) for k in keys}
    leads=[v for r in rows for v in r['lead_minutes']]
    detected=total['detected_episodes'];alarms=total['alarms'];days=total['eligible_monitoring_days']
    total.update(episode_recall=detected/total['evaluable_episodes'] if total['evaluable_episodes'] else None,
                 precision_lower_bound=detected/alarms if alarms else 0.,
                 false_per_eligible_day=total['false_alarms']/days if days else None,
                 median_lead_minutes=float(np.median(leads)) if leads else None,
                 patients_with_evaluable_episodes=sum(r['evaluable_episodes']>0 for r in rows))
    return total

def gate(result,settings,require_support=True):
    return bool((not require_support or (
        result['evaluable_episodes']>=settings['minimum_evaluable_episodes'] and
        result['patients_with_evaluable_episodes']>=settings['minimum_patients_with_evaluable_episodes']))
        and (result['episode_recall'] or 0)>=settings['episode_recall']
        and result['precision_lower_bound']>=settings['precision_lower_bound']
        and result['false_per_eligible_day'] is not None
        and result['false_per_eligible_day']<=settings['maximum_false_alarms_per_eligible_day']
        and (result['median_lead_minutes'] or 0)>=settings['minimum_median_lead_minutes'])

def assess_scores(records,scores,threshold):
    rows=[]
    for pid,record in records.items():
        alarms=alarm_times(record['times'],scores[pid],threshold,60)
        rows.append({'patient_id':pid,**assess(alarms,record['episodes'],record['times'],record['glucose'])})
    return rows

def choose_event_threshold(records,scores,settings,quantiles=101):
    if not scores or not any(len(v) for v in scores.values()):
        raise ValueError('No threshold-setting opportunities; no supported cutoff')
    pooled=np.concatenate(list(scores.values()))
    candidates=np.unique(np.r_[np.quantile(pooled,np.linspace(0,1,quantiles)),np.nextafter(pooled.max(),np.inf)])
    options=[]
    for threshold in candidates:
        result=summarize(assess_scores(records,scores,float(threshold)))
        recall=result['episode_recall'] or 0.;precision=result['precision_lower_bound']
        f1=2*recall*precision/(recall+precision) if recall+precision else 0.
        cap=result['false_per_eligible_day'] is not None and result['false_per_eligible_day']<=settings['maximum_false_alarms_per_eligible_day']
        options.append((gate(result,settings,False),cap,f1,recall,precision,float(threshold),result))
    compliant=[v for v in options if v[0]]
    chosen=max(compliant,key=lambda v:(v[3],v[4],v[5])) if compliant else max(options,key=lambda v:(v[1],v[2],v[5]))
    return chosen[5],chosen[6],bool(chosen[0])

def choose_threshold_for_patients(records,scores,patient_ids,settings,quantiles=101):
    """Explicit boundary: evaluation records/labels are never accessed here."""
    return choose_event_threshold({p:records[p] for p in patient_ids},
                                  {p:scores[p] for p in patient_ids},settings,quantiles)
