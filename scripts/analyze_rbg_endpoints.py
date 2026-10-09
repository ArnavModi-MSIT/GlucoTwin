"""Development PR diagnostics; no refitting, calibration changes or test access."""
from pathlib import Path
import os
os.environ.setdefault('OMP_NUM_THREADS','4')
import json
import joblib,numpy as np,pandas as pd
from sklearn.metrics import precision_recall_curve,average_precision_score
from threadpoolctl import threadpool_limits
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]

def run():
    roles=json.loads((ROOT/'configs/rbg_classifier_roles.json').read_text())
    prior=json.loads((ROOT/'reports/rbg_endpoint_assessment.json').read_text())
    base=ROOT/'data/processed/rbg';xs=[];ys=[];ids=[]
    for pid in roles['assessment']:
        with np.load(base/'30/validation'/f'{pid}.npz') as d:xs.append(d['X']);ys.append(d['y']);ids.extend([pid]*len(d['y']))
    X=np.concatenate(xs);target=np.concatenate(ys);ids=np.array(ids)
    fig,axes=plt.subplots(1,2,figsize=(11,4.6),constrained_layout=True)
    result={};private=[]
    for event,ax in zip(['high','low'],axes):
        artifact=joblib.load(ROOT/f'artifacts/rbg_{event}_endpoint.joblib')
        current=X[:,artifact['features'].index('cgm_current')]
        mask=current<=180 if event=='high' else current>=70
        actual=(target>180 if event=='high' else target<70)[mask].astype(int)
        people=ids[mask]
        with threadpool_limits(limits=4):
            if prior['events'][event]['operating_score']=='sigmoid':scores=artifact['calibrator'].predict_proba(artifact['model'].decision_function(X[mask]).reshape(-1,1))[:,1]
            else:scores=artifact['model'].predict_proba(X[mask])[:,1]
        precision,recall,thresholds=precision_recall_curve(actual,scores)
        table=[]
        for minimum in [.2,.3,.5,.7,.8]:
            candidates=np.flatnonzero(precision[:-1]>=minimum)
            if len(candidates):
                best=candidates[np.flatnonzero(recall[candidates]==recall[candidates].max())[-1]]
                t=thresholds[best];prediction=scores>=t;tp=int((prediction&actual.astype(bool)).sum());fp=int((prediction&~actual.astype(bool)).sum())
                table.append({'minimum_precision':minimum,'threshold':float(t),'precision':float(precision[best]),'recall':float(recall[best]),'tp':tp,'fp':fp})
            else:table.append({'minimum_precision':minimum,'unavailable':True})
        candidates=np.flatnonzero(recall[:-1]>=.6)
        best=candidates[np.argmax(precision[candidates])]
        recall60={'precision':float(precision[best]),'recall':float(recall[best]),'threshold':float(thresholds[best])}
        patient_stats=[];prediction=scores>=artifact['threshold']
        for pid in roles['assessment']:
            part=people==pid;y=actual[part];p=prediction[part]
            tp=int((p&y.astype(bool)).sum());fp=int((p&~y.astype(bool)).sum());n=int(y.sum())
            stat={'patient_id':pid,'rows':len(y),'positive_rows':n,'predicted_positive_rows':int(p.sum()),'tp':tp,'fp':fp,'recall':tp/n if n else None,'precision':tp/(tp+fp) if tp+fp else None,'ap':float(average_precision_score(y,scores[part])) if n else None}
            patient_stats.append(stat);private.append({'event':event,**stat})
        positives=[s for s in patient_stats if s['positive_rows']>0]
        result[event]={'precision_tradeoffs':table,'best_precision_at_recall_ge60pct':recall60,'patients_with_positives':len(positives),'patients_with_no_true_positive':sum(s['tp']==0 for s in positives),'patient_recall_quantiles':pd.Series([s['recall'] for s in positives]).quantile([0,.25,.5,.75,1]).to_dict(),'patient_macro_ap':float(np.mean([s['ap'] for s in positives])),'assessment_ap':float(average_precision_score(actual,scores)),'score_range':{'minimum':float(scores.min()),'maximum':float(scores.max())}}
        ax.plot(recall,precision,color='#277da1',label='Logistic endpoint score')
        ax.axhline(actual.mean(),color='#888888',linestyle=':',label=f'Prevalence {actual.mean():.1%}')
        operating=prior['events'][event]['at_risk_threshold_assessment']
        ax.scatter([operating['recall']],[operating['precision']],color='#e87518',zorder=3,label='Selected operating point')
        ax.axhline(.5,color='#aaaaaa',linestyle='--',linewidth=.8);ax.axvline(.6,color='#aaaaaa',linestyle='--',linewidth=.8)
        ax.set(xlabel='Recall (fraction of positive endpoints caught)',ylabel='Precision (fraction of flags correct)',title=f'{event.title()} endpoint at +30 min',xlim=(0,1),ylim=(0,1))
        ax.grid(alpha=.2);ax.legend(fontsize=8,loc='upper right')
    fig.suptitle('RBG development assessment: at-risk endpoints\nThresholds optimized on 17 assessment patients; no clinical/test validation',fontsize=11)
    fig.savefig(ROOT/'reports/rbg_endpoint_pr.png',dpi=170)
    pd.DataFrame(private).to_csv(base/'endpoint_patient_diagnostics.csv',index=False)
    report={'status':'descriptive development analysis; no model refit; threshold suggestions are not deployment approval','events':result}
    (ROOT/'reports/rbg_endpoint_diagnostics.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=='__main__':run()
