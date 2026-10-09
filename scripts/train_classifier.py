"""Fixed logistic endpoint model, separate sigmoid calibration, development assessment."""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ.setdefault(key,'4')
import json,sys,time
import joblib,numpy as np,pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score,brier_score_loss,precision_recall_curve,confusion_matrix
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from glucotwin.features import STATIC,HR

def reliability(y,p):
    bins=[]
    for i in range(10):
        mask=(p>=i/10)&(p<(i+1)/10) if i<9 else (p>=.9)&(p<=1)
        bins.append({'lower':i/10,'upper':(i+1)/10,'rows':int(mask.sum()),
                     'mean_probability':float(p[mask].mean()) if mask.any() else None,
                     'observed_fraction':float(y[mask].mean()) if mask.any() else None})
    return bins

def metrics(y,p,threshold=None):
    y=np.asarray(y,dtype=int);p=np.asarray(p,dtype=float)
    result={'rows':len(y),'positives':int(y.sum()),'prevalence':float(y.mean()),
            'average_precision':float(average_precision_score(y,p)),
            'brier':float(brier_score_loss(y,p)),'reliability_bins':reliability(y,p)}
    if threshold is not None:
        tn,fp,fn,tp=confusion_matrix(y,p>=threshold,labels=[0,1]).ravel()
        result.update({'threshold':float(threshold),'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp),
                       'precision':float(tp/(tp+fp)) if tp+fp else 0.,'recall':float(tp/(tp+fn)) if tp+fn else 0.,
                       'f1':float(2*tp/(2*tp+fp+fn)) if 2*tp+fp+fn else 0.})
    return result

def choose_threshold(y,p):
    precision,recall,threshold=precision_recall_curve(y,p)
    f1=np.divide(2*precision[:-1]*recall[:-1],precision[:-1]+recall[:-1],out=np.zeros(len(threshold)),where=(precision[:-1]+recall[:-1])>0)
    # Highest threshold wins a tied F1 to prefer fewer alerts.
    best=np.flatnonzero(np.isclose(f1,f1.max(),rtol=0,atol=1e-12))[-1]
    return float(threshold[best])

def run():
    started=time.perf_counter()
    data=pd.read_csv(ROOT/'data/processed/cgmacros_features.csv')
    manifest=json.loads((ROOT/'configs/cgmacros_splits.json').read_text())
    validation=pd.DataFrame([r for r in manifest['participants'] if r['split']=='validation'])
    roles={'tuning':[],'calibration':[]}
    for _,part in validation.groupby('a1c_group',sort=True):
        ids=sorted(part.patient_id.tolist())
        if len(ids)!=2:raise ValueError('Expected two validation patients per band')
        roles['tuning'].append(ids[0]);roles['calibration'].append(ids[1])
    # Write patient roles before fitting. Local-only because they contain study identifiers.
    (ROOT/'configs/classifier_roles.json').write_text(json.dumps(roles,indent=2))
    train=data[data.split.eq('train')];tune=data[data.patient_id.isin(roles['tuning'])];cal=data[data.patient_id.isin(roles['calibration'])]
    test_ids=set(data.loc[data.split.eq('test'),'patient_id'])
    assert set(train.patient_id).isdisjoint(tune.patient_id) and set(train.patient_id).isdisjoint(cal.patient_id)
    assert set(tune.patient_id).isdisjoint(cal.patient_id)
    assert test_ids.isdisjoint(set(train.patient_id)|set(tune.patient_id)|set(cal.patient_id))
    columns=[c for c in data if c.startswith('cgm_')]+STATIC+HR
    target='high_endpoint'
    model=Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),
                    ('scale',StandardScaler()),('classifier',LogisticRegression(C=1.,max_iter=1000,random_state=2026))])
    with threadpool_limits(limits=4):model.fit(train[columns],train[target])
    support={name:{'patients':int(part.patient_id.nunique()),'rows':len(part),'positives':int(part[target].sum()),
                   'negative':int((part[target]==0).sum()),'at_risk_rows':int((part.cgm_current<=180).sum()),
                   'at_risk_positives':int(part.new_high_endpoint.sum())} for name,part in [('train',train),('tuning',tune),('calibration',cal)]}
    enough=(support['calibration']['positives']>=100 and support['calibration']['negative']>=100
            and int(cal.groupby('patient_id')[target].sum().ge(10).sum())>=2)
    if not enough:raise RuntimeError('Insufficient calibration support; omit probability output')
    calibrator=LogisticRegression(C=1.,max_iter=1000,random_state=2026)
    with threadpool_limits(limits=4):
        cal_score=model.decision_function(cal[columns]).reshape(-1,1)
        calibrator.fit(cal_score,cal[target])
    raw=model.predict_proba(tune[columns])[:,1]
    calibrated=calibrator.predict_proba(model.decision_function(tune[columns]).reshape(-1,1))[:,1]
    at_risk=(tune.cgm_current<=180).to_numpy();y=tune[target].to_numpy()
    train_prevalence=float(train[target].mean())
    scores={}
    for name,p in [('raw_logistic',raw),('sigmoid_calibrated',calibrated),('train_prevalence',np.full(len(y),train_prevalence)),('current_glucose_threshold',(tune.cgm_current>180).to_numpy(dtype=float))]:
        scores[name]={'all_endpoints':metrics(y,p),'at_risk_endpoints':metrics(y[at_risk],p[at_risk])}
    # Gate declared before training in EVALUATION_PROTOCOL: reliability on tuning only.
    all_ok=scores['sigmoid_calibrated']['all_endpoints']['brier']<=scores['raw_logistic']['all_endpoints']['brier'] and scores['sigmoid_calibrated']['all_endpoints']['brier']<scores['train_prevalence']['all_endpoints']['brier']
    risk_ok=scores['sigmoid_calibrated']['at_risk_endpoints']['brier']<=scores['raw_logistic']['at_risk_endpoints']['brier'] and scores['sigmoid_calibrated']['at_risk_endpoints']['brier']<scores['train_prevalence']['at_risk_endpoints']['brier']
    gate=bool(all_ok and risk_ok)
    threshold=choose_threshold(y[at_risk],calibrated[at_risk])
    scores['sigmoid_calibrated']['at_risk_operating_point']=metrics(y[at_risk],calibrated[at_risk],threshold)
    scores['sigmoid_calibrated']['all_operating_point']=metrics(y,calibrated,threshold)
    artifact={'model':model,'calibrator':calibrator,'features':columns,'horizon_minutes':60,
              'event':'glucose at t+60 >180 mg/dL','threshold':threshold,'probability_display_approved':gate,
              'version':'logistic-assessment-v0.1','roles':roles,
              'threshold_scope':'current glucose <=180; tuning-maximized F1, optimistic operating-point estimate'}
    joblib.dump(artifact,ROOT/'artifacts/endpoint_classifier.joblib')
    # Local patient-level files; not public. No final test inference is performed.
    tune[['patient_id','prediction_time','high_endpoint','new_high_endpoint','cgm_current']].assign(raw_probability=raw,calibrated_probability=calibrated).to_csv(ROOT/'data/processed/classifier_tuning_predictions.csv',index=False)
    output={'status':'development assessment only; final test NOT scored','target':'glucose exactly +60 min >180 mg/dL',
            'support':support,'scores':scores,'calibration_gate_passed':gate,'gate_checks':{'all_endpoints':bool(all_ok),'at_risk_endpoints':bool(risk_ok)},
            'calibration_gate':'Calibration Brier no worse than raw and better than training-prevalence baseline, both all/at-risk tuning views',
            'operating_threshold':threshold,'threshold_rule':'maximize at-risk tuning F1; highest threshold breaks ties',
            'seconds':round(time.perf_counter()-started,3),'limitations':['Only three tuning and three calibration patients','Both validation groups previously inspected for regression','Threshold F1 optimized on reported tuning data','Overlapping endpoints are not independent episodes','Reconstructed CGM and assumed clinical availability','No final test probability reliability or clinical validation']}
    (ROOT/'reports/classifier_assessment.json').write_text(json.dumps(output,indent=2))
    print(json.dumps({k:v for k,v in output.items() if k!='scores'},indent=2))
    for name,value in scores.items():
        print(name,json.dumps({view:{k:v for k,v in result.items() if k!='reliability_bins'} for view,result in value.items()}))

if __name__=='__main__':run()
