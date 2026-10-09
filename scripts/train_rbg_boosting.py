"""RBG fixed CPU boosting assessment; validation only."""
from pathlib import Path
import os
os.environ.setdefault('OMP_NUM_THREADS','4')
import json,time,threading
import numpy as np,pandas as pd,joblib,psutil
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1]

def run():
    start=time.monotonic();stop=threading.Event();rss=[]
    def sample():
        while not stop.wait(.05):rss.append(psutil.Process().memory_info().rss)
    monitor=threading.Thread(target=sample,daemon=True);monitor.start()
    base=ROOT/'data/processed/rbg';columns=json.loads((base/'features.json').read_text())
    all_results={};patient_rows=[]
    for horizon in [30,60]:
        files=sorted((base/str(horizon)/'train').glob('*.npz'))
        Xs=[];ys=[]
        for file in files:
            with np.load(file) as data:Xs.append(data['X']);ys.append(data['y'])
        X=np.concatenate(Xs);y=np.concatenate(ys);del Xs,ys
        fitted={}
        for name,indices in {'boost_cgm':list(range(len(columns)-2)),'boost_cgm_profile':list(range(len(columns)))}.items():
            model=HistGradientBoostingRegressor(loss='absolute_error',learning_rate=.05,max_iter=120,max_leaf_nodes=15,min_samples_leaf=80,l2_regularization=10.,early_stopping=False,random_state=2026)
            with threadpool_limits(limits=4):model.fit(X[:,indices],y)
            fitted[name]=(model,indices)
            (ROOT/'artifacts').mkdir(exist_ok=True)
            joblib.dump({'model':model,'features':[columns[i] for i in indices],'horizon_minutes':horizon,'sensor_delay_minutes':5,'version':'rbg-boost-v0.1'},ROOT/f'artifacts/rbg_{name}_{horizon}.joblib')
        accum={name:{} for name in ['persistence','slope',*fitted]}
        for file in sorted((base/str(horizon)/'validation').glob('*.npz')):
            with np.load(file) as data:V=data['X'];actual=data['y']
            if len(actual)==0:continue
            current=V[:,columns.index('cgm_current')]
            predictions={'persistence':current,'slope':current+(horizon+5)*np.nan_to_num(V[:,columns.index('cgm_slope_30m')])}
            with threadpool_limits(limits=4):
                for name,(model,indices) in fitted.items():predictions[name]=model.predict(V[:,indices])
            masks={'all':np.ones(len(actual),dtype=bool),'high':actual>180,'low':actual<70,'rapid_change':np.abs(actual-current)>=30}
            for name,pred in predictions.items():
                for slice_name,mask in masks.items():
                    errors=pred[mask]-actual[mask]
                    a=accum[name].setdefault(slice_name,{'n':0,'abs':0.,'sq':0.,'signed':0.,'over30':0,'patient_maes':[]})
                    a['n']+=len(errors);a['abs']+=float(np.abs(errors).sum(dtype=np.float64));a['sq']+=float(np.square(errors.astype(np.float64)).sum());a['signed']+=float(errors.sum(dtype=np.float64));a['over30']+=int((np.abs(errors)>30).sum())
                    if len(errors):a['patient_maes'].append(float(np.mean(np.abs(errors))))
                patient_rows.append({'horizon':horizon,'model':name,'patient_id':file.stem,'rows':len(actual),'mae':float(np.abs(pred-actual).mean())})
        scores={}
        for name,slices in accum.items():
            scores[name]={}
            for label,a in slices.items():
                n=a['n'];maes=np.array(a['patient_maes']);rng=np.random.default_rng(2026)
                bootstrap=maes[rng.integers(0,len(maes),size=(2000,len(maes)))].mean(axis=1) if len(maes) else np.array([np.nan])
                scores[name][label]={'rows':n,'mae':a['abs']/n if n else None,'rmse':float(np.sqrt(a['sq']/n)) if n else None,'bias':a['signed']/n if n else None,'fraction_error_over30':a['over30']/n if n else None,'patient_macro_mae':float(maes.mean()) if len(maes) else None,'patient_macro_mae_bootstrap95':np.quantile(bootstrap,[.025,.975]).tolist()}
        all_results[str(horizon)]={'training_rows':len(y),'training_patients':len(files),'scores':scores}
        print(f'{horizon} min: '+json.dumps({name:round(score['all']['mae'],3) for name,score in scores.items()}),flush=True)
        del X,y
    stop.set();monitor.join()
    result={'status':'development validation only; no reserved test predictions generated','parameters':{'loss':'absolute_error','learning_rate':.05,'max_iter':120,'max_leaf_nodes':15,'min_samples_leaf':80,'l2_regularization':10.,'early_stopping':False,'random_state':2026},'sensor_delay_minutes':5,'horizons':all_results,'seconds':round(time.monotonic()-start,1),'sampled_peak_rss_mib':round(max(rss)/2**20,1)}
    (ROOT/'reports/rbg_boosting_validation.json').write_text(json.dumps(result,indent=2))
    pd.DataFrame(patient_rows).to_csv(base/'boosting_validation_patient_metrics.csv',index=False)
    print('COMPLETE',result['seconds'],'seconds;',result['sampled_peak_rss_mib'],'MiB',flush=True)
if __name__=='__main__':run()
