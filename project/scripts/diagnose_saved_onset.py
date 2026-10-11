"""Describe frozen onset predictions; do not fit or select new cutoffs."""
from pathlib import Path
import json,sys
import numpy as np
import pandas as pd
import joblib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from glucotwin.features import make_features,profile_features
from glucotwin.episodes import onsets,alarm_times,assess
from glucotwin.event_study import summarize,gate


def describe(rows):
    result=summarize(rows);leads=np.array([v for r in rows for v in r['lead_minutes']])
    result['lead_quantiles_minutes']={str(q):float(np.quantile(leads,q)) if len(leads) else None for q in [.25,.5,.75]}
    result['recall_by_minimum_lead']={str(m):int((leads>=m).sum())/result['evaluable_episodes'] if result['evaluable_episodes'] else None for m in [10,15,20,25]}
    unmatched=result['alarms']-result['detected_episodes']
    assert unmatched==result['false_alarms']+result['unknown_alarms']+result['redundant_alarms']
    result['unmatched_alarms']=unmatched
    days=result['eligible_monitoring_days'];result['unmatched_per_eligible_day']=unmatched/days if days else None
    return result


def run():
    output={'scope':'post-hoc descriptive diagnostics of frozen development predictions; no new fitting or cutoff selection',
            'day_denominator':'at-risk five-minute opportunity coverage, not calendar days','studies':{}}
    for study in ['v1','gpu_v2','methods_v3']:
        private=json.loads((ROOT/f'data/processed/cgmacros_event_patient_metrics_{study}.json').read_text())
        report=json.loads((ROOT/f'reports/event_study_{study}.json').read_text())
        settings=json.loads((ROOT/f'configs/event_study_{study}.json').read_text())['engineering_gate']
        output['studies'][study]={'methods':{k:describe(v) for k,v in private.items()},'cutoff_support':[
            {'fold':f['fold'],'cutoff':f['methods']['fused']['threshold'],
             'operating_criteria_met_with_support_waived':f['methods']['fused']['threshold_gate_passed'],
             'full_support_gate_met':gate(f['methods']['fused']['threshold_setting'],settings,True),
             'cutoff_patients':3,'patients_with_evaluable_episodes':f['methods']['fused']['threshold_setting']['patients_with_evaluable_episodes'],
             'evaluable_episodes':f['methods']['fused']['threshold_setting']['evaluable_episodes']} for f in report['folds']]}
        assert all(output['studies'][study]['methods'][k]['detected_episodes']==report['pooled'][k]['detected_episodes'] for k in private)
    # Inspect frozen v2 false-alarm contexts, retaining the original event definition.
    manifest=json.loads((ROOT/'configs/cgmacros_splits.json').read_text());patients={p['patient_id']:p for p in manifest['participants'] if p['split'] in ['train','validation']}
    source=ROOT/'data/raw/cgmacros/CGMacros';bio=pd.read_csv(source/'bio.csv');bio.columns=bio.columns.str.strip();bio=bio.set_index('subject')
    counts={'verified_false_alarms':0,'with_any_high_reading_next30':0,'with_sustained_high_start_next30_without_prior_normal_rule':0}
    for fold in range(1,4):
        artifact=joblib.load(ROOT/f'artifacts/cgmacros_onset_gpu_v2_fold{fold}_fused.joblib')
        for pid in artifact['roles']['evaluation']:
            if pid not in patients:raise RuntimeError('Reserved/unknown patient refused')
            patient=patients[pid];frame=pd.read_csv(source/f'CGMacros-{pid:03d}/CGMacros-{pid:03d}.csv')
            features=make_features(frame,profile_features(bio.loc[pid]),patient['phase_utc_minutes_mod_5'])
            g=features.cgm_current;eligible=features.history_eligible&(g<=180)&(features.index>=pd.Timestamp(patient['minimum_forecast_time']))
            X=features.loc[eligible,artifact['features']];scores=artifact['model'].predict_proba(X)[:,1]
            alarms=alarm_times(X.index,scores,artifact['threshold'],60);events=onsets(g,'high');matched=set()
            for t in alarms:
                candidates=events[(events>=t+pd.Timedelta(minutes=5))&(events<=t+pd.Timedelta(minutes=30))]
                available=[e for e in candidates if e not in matched]
                if available:matched.add(available[0]);continue
                if len(candidates):continue
                future=g.reindex(pd.date_range(t+pd.Timedelta(minutes=5),periods=9,freq='5min'))
                if future.isna().any():continue
                high=(future.to_numpy()>180);counts['verified_false_alarms']+=1
                counts['with_any_high_reading_next30']+=int(high[:6].any())
                counts['with_sustained_high_start_next30_without_prior_normal_rule']+=int(any(high[i:i+4].all() for i in range(6)))
    assert counts['verified_false_alarms']==output['studies']['gpu_v2']['methods']['fused']['false_alarms']
    output['frozen_v2_false_alarm_context']=counts
    output['interpretation']='Other high excursions are secondary descriptions, not true positives under the frozen endpoint and not proof of contaminated labels.'
    (ROOT/'reports/onset_review_diagnostics.json').write_text(json.dumps(output,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'v2':output['studies']['gpu_v2']['methods']['fused'],'false_alarm_context':counts},indent=2))


if __name__=='__main__':run()
