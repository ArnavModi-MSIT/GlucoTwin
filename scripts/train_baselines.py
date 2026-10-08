"""CPU baselines and Ridge ablations. Deliberately does not score final test."""
from pathlib import Path
import os
os.environ.setdefault('OMP_NUM_THREADS','4')
os.environ.setdefault('OPENBLAS_NUM_THREADS','4')
os.environ.setdefault('MKL_NUM_THREADS','4')
import json, sys, time, threading
import numpy as np
import pandas as pd
import psutil, sklearn, joblib
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from glucotwin.features import STATIC, HR

def metrics(actual,prediction):
    return {'rows':len(actual),'mae_mg_dl':float(mean_absolute_error(actual,prediction)),
            'rmse_mg_dl':float(np.sqrt(mean_squared_error(actual,prediction)))}

def run():
    start=time.perf_counter()
    stop=threading.Event()
    memory=[psutil.Process().memory_info().rss]
    def monitor():
        while not stop.wait(.02): memory.append(psutil.Process().memory_info().rss)
    watcher=threading.Thread(target=monitor,daemon=True)
    watcher.start()
    data=pd.read_csv(ROOT/'data/processed/cgmacros_features.csv')
    train=data[data.split.eq('train')].copy()
    val=data[data.split.eq('validation')].copy()
    target='target_glucose_60m'
    cgm=[c for c in data if c.startswith('cgm_')]
    variants={'ridge_clinical_only':STATIC,'ridge_cgm_only':cgm,
              'ridge_cgm_clinical':cgm+STATIC,'ridge_cgm_clinical_hr':cgm+STATIC+HR}
    predictions={'persistence':val.cgm_current.to_numpy(),
                 'slope':(val.cgm_current+60*val.cgm_slope_30m.fillna(0)).to_numpy()}
    timings={}
    artifacts=ROOT/'artifacts'
    artifacts.mkdir(exist_ok=True)
    for name,columns in variants.items():
        begun=time.perf_counter()
        model=Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),
                        ('scale',StandardScaler()),('ridge',Ridge(alpha=10.0))])
        with threadpool_limits(limits=4):
            model.fit(train[columns],train[target])
            predictions[name]=model.predict(val[columns])
        timings[name]=round(time.perf_counter()-begun,4)
        # These files are locally generated trusted artifacts, not third-party pickles.
        joblib.dump({'model':model,'features':columns,'target':target,'horizon_minutes':60,
                     'dataset':'CGMacros reconstructed grid','version':'baseline-v0.1',
                     'sklearn_version':sklearn.__version__},artifacts/f'{name}.joblib')
    scores,patient_rows={},[]
    for name,pred in predictions.items():
        scores[name]=metrics(val[target],pred)
        scores[name]['mae_delta_vs_persistence']=scores[name]['mae_mg_dl']-mean_absolute_error(val[target],predictions['persistence'])
        groups=val.assign(prediction=pred).groupby('patient_id')
        patient_maes=[]
        for pid,part in groups:
            result=metrics(part[target],part.prediction)
            patient_maes.append(result['mae_mg_dl'])
            patient_rows.append({'model':name,'patient_id':int(pid),**result})
        scores[name]['patient_macro_mae_mg_dl']=float(np.mean(patient_maes))
        scores[name]['slices']={}
        for label,mask in {'type2_band':val.a1c_group.eq('above_6.4'),'target_high':val[target]>180,'target_low':val[target]<70}.items():
            scores[name]['slices'][label]=metrics(val.loc[mask,target],pred[mask]) if mask.any() else {'rows':0}
    stop.set();watcher.join()
    result={'status':'development validation only; final test NOT scored',
            'seed':2026,'ridge_alpha':10.0,'train_patients':int(train.patient_id.nunique()),
            'validation_patients':int(val.patient_id.nunique()),'train_rows':len(train),'validation_rows':len(val),
            'scores':scores,'fit_predict_seconds':timings,'total_seconds':round(time.perf_counter()-start,3),
            'sampled_peak_process_rss_mib':round(max(memory)/2**20,2),
            'versions':{'python':sys.version.split()[0],'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__},
            'limitations':['Exploratory reconstructed grid, not verified raw device samples','Only six validation patients','Clinical availability assumption','No clinical validation','Row-weighted metrics contain overlapping horizons']}
    (ROOT/'reports/baseline_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    pd.DataFrame(patient_rows).to_csv(ROOT/'reports/baseline_validation_patient_metrics.csv',index=False)
    print(json.dumps(result,indent=2))

if __name__=='__main__':run()
