"""RBG fixed endpoint classifiers with disjoint development calibration roles."""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ.setdefault(key,'4')
import json,time,threading
import numpy as np,pandas as pd,joblib,psutil
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score,brier_score_loss,precision_recall_curve,confusion_matrix
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1]

def score(y,p,threshold=None):
    result={'rows':len(y),'positives':int(y.sum()),'prevalence':float(y.mean()),'average_precision':float(average_precision_score(y,p)),'brier':float(brier_score_loss(y,p))}
    if threshold is not None:
        tn,fp,fn,tp=confusion_matrix(y,p>=threshold,labels=[0,1]).ravel()
        result.update(threshold=float(threshold),tn=int(tn),fp=int(fp),fn=int(fn),tp=int(tp),precision=float(tp/(tp+fp)) if tp+fp else 0.,recall=float(tp/(tp+fn)) if tp+fn else 0.)
    return result

def threshold_for(y,p):
    precision,recall,thresholds=precision_recall_curve(y,p)
    precision=precision[:-1];recall=recall[:-1]
    eligible=np.flatnonzero(precision>=.5)
    if len(eligible):
        best=eligible[np.flatnonzero(recall[eligible]==recall[eligible].max())[-1]]
    else:
        f1=np.divide(2*precision*recall,precision+recall,out=np.zeros_like(precision),where=precision+recall>0)
        best=np.flatnonzero(f1==f1.max())[-1]
    return float(thresholds[best])

def run():
    start=time.monotonic();rss=[];stop=threading.Event()
    def sample():
        while not stop.wait(.05):rss.append(psutil.Process().memory_info().rss)
    monitor=threading.Thread(target=sample,daemon=True);monitor.start()
    manifest=json.loads((ROOT/'configs/rbg_splits.json').read_text())
    validation=pd.DataFrame([p for p in manifest['participants'] if p['split']=='validation'])
    strata=validation.sex_f.astype(str)+'_'+validation.age_at_enrollment.ge(45).astype(str)
    cal,assessment=train_test_split(validation,test_size=17,random_state=2026,stratify=strata)
    roles={'calibration':sorted(cal.patient_id),'assessment':sorted(assessment.patient_id)}
    (ROOT/'configs/rbg_classifier_roles.json').write_text(json.dumps(roles,indent=2))
    train_ids=sorted(p['patient_id'] for p in manifest['participants'] if p['split']=='train')
    test_ids={p['patient_id'] for p in manifest['participants'] if p['split']=='test'}
    assert set(roles['calibration']).isdisjoint(roles['assessment']) and test_ids.isdisjoint(set(train_ids)|set(roles['calibration'])|set(roles['assessment']))
    base=ROOT/'data/processed/rbg/30';columns=json.loads((base.parent/'features.json').read_text())
    def load(ids,split):
        xs=[];ys=[];patients=[]
        for pid in ids:
            with np.load(base/split/f'{pid}.npz') as d:xs.append(d['X']);ys.append(d['y']);patients.extend([pid]*len(d['y']))
        return np.concatenate(xs),np.concatenate(ys),np.array(patients)
    X,target,_=load(train_ids,'train')
    C,ct,cpid=load(roles['calibration'],'validation')
    A,at,apid=load(roles['assessment'],'validation')
    current_idx=columns.index('cgm_current');results={}
    for event in ['high','low']:
        y=(target>180 if event=='high' else target<70).astype(int)
        cy=(ct>180 if event=='high' else ct<70).astype(int)
        ay=(at>180 if event=='high' else at<70).astype(int)
        at_risk=A[:,current_idx]<=180 if event=='high' else A[:,current_idx]>=70
        positive_patients=sum(int(cy[cpid==pid].sum())>=10 for pid in roles['calibration'])
        support=int(cy.sum())>=100 and int((1-cy).sum())>=100 and positive_patients>=5
        if not support:
            raise RuntimeError(f'{event}: insufficient calibration support; no calibrator fitted')
        model=Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),('scale',StandardScaler()),('classifier',LogisticRegression(C=1,max_iter=1000))])
        with threadpool_limits(limits=4):
            model.fit(X,y);raw=model.predict_proba(A)[:,1]
            calibrator=LogisticRegression(C=1,max_iter=1000).fit(model.decision_function(C).reshape(-1,1),cy)
            calibrated=calibrator.predict_proba(model.decision_function(A).reshape(-1,1))[:,1]
        constant=np.full(len(ay),y.mean())
        baseline=(A[:,current_idx]>180 if event=='high' else A[:,current_idx]<70).astype(float)
        metrics={};gate={}
        for label,mask in [('all',np.ones(len(ay),dtype=bool)),('at_risk',at_risk)]:
            metrics[label]={name:score(ay[mask],prob[mask]) for name,prob in [('raw',raw),('sigmoid',calibrated),('train_prevalence',constant),('latest_glucose_threshold',baseline)]}
            gate[label]=metrics[label]['sigmoid']['brier']<=metrics[label]['raw']['brier'] and metrics[label]['sigmoid']['brier']<metrics[label]['train_prevalence']['brier']
        calibration_pass=support and all(gate.values())
        chosen=calibrated if calibration_pass else raw
        threshold=threshold_for(ay[at_risk],chosen[at_risk])
        operating=score(ay[at_risk],chosen[at_risk],threshold)
        operation_pass=operating['precision']>=.5 and operating['recall']>=.6
        result={'training_prevalence':float(y.mean()),'calibration_rows':len(cy),'calibration_positives':int(cy.sum()),'calibration_positive_patients_ge10':positive_patients,'calibration_support_pass':support,'calibration_brier_gate':gate,'calibration_pass':calibration_pass,'metrics':metrics,'operating_score':'sigmoid' if calibration_pass else 'raw','at_risk_threshold_assessment':operating,'operating_gate_pass':operation_pass,'probability_display_approved':False,'flag_deployment_approved':False}
        # Per-patient metrics are local. Gate combines development assessments only.
        per_patient=[]
        for pid in roles['assessment']:
            mask=(apid==pid)&at_risk
            if mask.any():per_patient.append({'patient_id':pid,**score(ay[mask],chosen[mask],threshold)})
        pd.DataFrame(per_patient).to_csv(base.parent/f'{event}_classifier_patient_metrics.csv',index=False)
        joblib.dump({'model':model,'calibrator':calibrator,'features':columns,'horizon_minutes':30,'sensor_delay_minutes':5,'event':event,'threshold':threshold,'probability_display_approved':False,'flag_deployment_approved':False,'version':'rbg-endpoint-assessment-v0.1'},ROOT/f'artifacts/rbg_{event}_endpoint.joblib')
        results[event]=result
        print(event,'AP',round(operating['average_precision'],3),'precision',round(operating['precision'],3),'recall',round(operating['recall'],3),'calibration',calibration_pass,'operating gate',operation_pass,flush=True)
    stop.set();monitor.join()
    report={'status':'development endpoint assessment only; thresholds optimized on assessment; no clinical/test validation','role_patients':{'train':158,'calibration':17,'assessment':17,'reserved_test':34},'training_rows':len(target),'assessment_rows':len(at),'horizon_minutes':30,'sensor_delay_minutes':5,'events':results,'seconds':round(time.monotonic()-start,1),'sampled_peak_rss_mib':round(max(rss)/2**20,1)}
    (ROOT/'reports/rbg_endpoint_assessment.json').write_text(json.dumps(report,indent=2))
    print('COMPLETE',report['seconds'],'seconds;',report['sampled_peak_rss_mib'],'MiB',flush=True)
if __name__=='__main__':run()
