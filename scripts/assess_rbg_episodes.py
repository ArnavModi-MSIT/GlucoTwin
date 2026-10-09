"""Frozen episode backtest on assessment patients; no refitting or test access."""
from pathlib import Path
import os
os.environ.setdefault('OMP_NUM_THREADS','4')
import sys,json,time
import joblib,numpy as np,pandas as pd
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from glucotwin.rbg import rbg_features
from glucotwin.episodes import onsets,alarm_times,assess

def run():
    started=time.monotonic()
    roles=json.loads((ROOT/'configs/rbg_classifier_roles.json').read_text())
    chosen=set(roles['assessment'])
    patients={p['patient_id']:p for p in json.loads((ROOT/'configs/rbg_splits.json').read_text())['participants']}
    assert all(patients[pid]['split']=='validation' for pid in chosen)
    models={};records=[]
    for family,file in [('logistic','rbg_endpoint_assessment.json'),('boost','rbg_boost_endpoint_assessment.json')]:
        report=json.loads((ROOT/'reports'/file).read_text())
        for event in ['high','low']:
            artifact=joblib.load(ROOT/f'artifacts/rbg_{event}_{"boost_" if family=="boost" else ""}endpoint.joblib')
            models[(family,event)]=(artifact,report['events'][event]['operating_score'])
    def evaluate(pid,frame):
        patient=patients[pid];frame.ts=pd.to_datetime(frame.ts)
        glucose=pd.Series(frame.GlucoseCGM.to_numpy(),index=frame.ts)
        features=rbg_features(frame,patient)
        visible=features.loc[features.history_eligible & (features.index>=pd.Timestamp(patient['minimum_forecast_time']))].drop(columns='history_eligible')
        for event in ['high','low']:
            episodes=onsets(glucose,event)
            outside=visible.cgm_current<=180 if event=='high' else visible.cgm_current>=70
            opportunities=visible.loc[outside]
            for family in ['logistic','boost']:
                artifact,kind=models[(family,event)]
                with threadpool_limits(limits=4):
                    X=opportunities[artifact['features']].to_numpy(dtype=np.float32)
                    prob=artifact['model'].predict_proba(X)[:,1]
                    if kind=='sigmoid':
                        if family=='logistic':score=artifact['model'].decision_function(X)
                        else:
                            p=np.clip(prob,1e-6,1-1e-6);score=np.log(p/(1-p))
                        prob=artifact['calibrator'].predict_proba(score.reshape(-1,1))[:,1]
                alarms=alarm_times(opportunities.index,prob,artifact['threshold'])
                record=assess(alarms,episodes,opportunities.index,glucose)
                records.append({'patient_id':pid,'family':family,'event':event,**record})
        print(f'{pid}: assessed with past-only opportunities',flush=True)
    prior=None;pending=[];seen=set()
    for chunk in pd.read_csv(ROOT/'data/raw/diadata/RBG_raw.csv',usecols=['ts','PtID','GlucoseCGM'],dtype={'PtID':'str'},chunksize=250000):
        for pid,g in chunk.groupby('PtID',sort=False):
            if prior is not None and pid!=prior:
                if prior in chosen:evaluate(prior,pd.concat(pending,ignore_index=True));seen.add(prior)
                pending=[]
            prior=pid
            if pid in chosen:pending.append(g)
    if prior in chosen:evaluate(prior,pd.concat(pending,ignore_index=True));seen.add(prior)
    assert seen==chosen
    summaries={}
    for event in ['high','low']:
        summaries[event]={}
        for family in ['logistic','boost']:
            rows=[r for r in records if r['event']==event and r['family']==family]
            count_keys=['qualifying_episodes','evaluable_episodes','detected_episodes','alarms','false_alarms','unknown_alarms','redundant_alarms','eligible_monitoring_days']
            total={k:sum(r[k] for r in rows) for k in count_keys}
            lead=[v for r in rows for v in r['lead_minutes']]
            n=total['alarms'];detected=total['detected_episodes']
            assert n==detected+total['false_alarms']+total['unknown_alarms']+total['redundant_alarms']
            total.update(episode_recall=detected/total['evaluable_episodes'] if total['evaluable_episodes'] else None,
                         all_episode_recall=detected/total['qualifying_episodes'] if total['qualifying_episodes'] else None,
                         false_per_eligible_day=total['false_alarms']/total['eligible_monitoring_days'],
                         precision_lower_bound=detected/n if n else None,precision_upper_bound=(detected+total['unknown_alarms'])/n if n else None,
                         median_lead_minutes=float(np.median(lead)) if lead else None,
                         lead_quartiles_minutes=np.quantile(lead,[.25,.5,.75]).tolist() if lead else [],
                         patient_macro_recall=float(np.mean([r['episode_recall'] for r in rows if r['episode_recall'] is not None])),
                         patient_macro_false_per_eligible_day=float(np.mean([r['false_per_eligible_day'] for r in rows if r['false_per_eligible_day'] is not None])))
            summaries[event][family]=total
    base=ROOT/'data/processed/rbg'
    (base/'episode_patient_details.json').write_text(json.dumps(records,indent=2))
    result={'status':'retrospective engineering episode backtest; prior endpoint gates still failed; no clinical/test validation','patients':17,'warning_window_minutes':[5,30],'cooldown_minutes':60,'sustained_samples':4,'prior_normal_samples':7,'sensor_delay_minutes':5,'seconds':round(time.monotonic()-started,1),'events':summaries}
    (ROOT/'reports/rbg_episode_assessment.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=='__main__':run()
