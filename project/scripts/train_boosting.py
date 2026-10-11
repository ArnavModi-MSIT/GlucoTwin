"""One bounded CPU boosting configuration with development-only ablations."""
from pathlib import Path
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ.setdefault(name,'4')
import sys,json,time,threading
import numpy as np
import pandas as pd
import psutil,joblib,sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error,mean_squared_error
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from glucotwin.features import STATIC,HR

def score(actual,pred):
    return {'rows':len(actual),'mae_mg_dl':float(mean_absolute_error(actual,pred)),
            'rmse_mg_dl':float(np.sqrt(mean_squared_error(actual,pred)))}

def run():
    (ROOT/"artifacts").mkdir(exist_ok=True)
    started=time.perf_counter()
    stop=threading.Event(); rss=[psutil.Process().memory_info().rss]
    def monitor():
        while not stop.wait(.02):rss.append(psutil.Process().memory_info().rss)
    watcher=threading.Thread(target=monitor,daemon=True);watcher.start()
    data=pd.read_csv(ROOT/'data/processed/cgmacros_features.csv')
    train=data[data.split.eq('train')];val=data[data.split.eq('validation')]
    target='target_glucose_60m'
    cgm=[c for c in data if c.startswith('cgm_')]
    variants={'boost_cgm_only':cgm,'boost_cgm_clinical':cgm+STATIC,'boost_cgm_clinical_hr':cgm+STATIC+HR}
    params={'loss':'absolute_error','learning_rate':.05,'max_iter':120,'max_leaf_nodes':15,
            'min_samples_leaf':80,'l2_regularization':10.,'early_stopping':False,'random_state':2026}
    results={};patient_scores=[];predictions=val[['patient_id','prediction_time',target,'a1c_group']].copy()
    baseline=val.cgm_current.to_numpy()
    for name,columns in variants.items():
        began=time.perf_counter()
        model=HistGradientBoostingRegressor(**params)
        with threadpool_limits(limits=4):
            model.fit(train[columns],train[target]);pred=model.predict(val[columns])
        result=score(val[target],pred)
        result['fit_predict_seconds']=round(time.perf_counter()-began,3)
        result['mae_improvement_vs_persistence']=float(mean_absolute_error(val[target],baseline)-result['mae_mg_dl'])
        result['slices']={}
        for label,mask in {'type2_band':val.a1c_group.eq('above_6.4'),'target_high':val[target]>180,'target_low':val[target]<70}.items():
            result['slices'][label]=score(val.loc[mask,target],pred[mask]) if mask.any() else {'rows':0}
        deltas=[]
        for pid,part in val.assign(prediction=pred,baseline=baseline).groupby('patient_id'):
            metrics=score(part[target],part.prediction)
            delta=float((part.prediction-part[target]).abs().mean()-(part.baseline-part[target]).abs().mean())
            deltas.append(delta)
            patient_scores.append({'model':name,'patient_id':int(pid),**metrics,'mae_delta_vs_persistence':delta})
        result['patient_macro_mae_mg_dl']=float(np.mean([r['mae_mg_dl'] for r in patient_scores if r['model']==name]))
        result['patients_beating_persistence']=int((np.array(deltas)<0).sum())
        rng=np.random.default_rng(2026)
        draws=rng.choice(deltas,size=(2000,len(deltas)),replace=True).mean(axis=1)
        result['patient_macro_delta_bootstrap_95pct_interval']=np.quantile(draws,[.025,.975]).tolist()
        results[name]=result;predictions[name]=pred
        joblib.dump({'model':model,'features':columns,'target':target,'horizon_minutes':60,
                     'dataset':'CGMacros reconstructed grid','version':'boost-v0.1','sklearn_version':sklearn.__version__},ROOT/f'artifacts/{name}.joblib')
    stop.set();watcher.join()
    output={'status':'development validation only; final test NOT scored','parameters':params,
            'scores':results,'total_seconds':round(time.perf_counter()-started,3),
            'sampled_peak_rss_mib':round(max(rss)/2**20,2),'threads':4,
            'versions':{'python':sys.version.split()[0],'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__},
            'bootstrap_warning':'Only six validation patients; interval is exploratory and excludes model-selection uncertainty.'}
    (ROOT/'reports/boosting_validation.json').write_text(json.dumps(output,indent=2))
    pd.DataFrame(patient_scores).to_csv(ROOT/'reports/boosting_validation_patient_metrics.csv',index=False)
    predictions.to_csv(ROOT/'data/processed/boosting_validation_predictions.csv',index=False)
    print(json.dumps(output,indent=2))

if __name__=='__main__':run()
