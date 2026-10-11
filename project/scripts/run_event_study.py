"""Nested patient-disjoint future-onset study; never loads reserved sensor files."""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ.setdefault(key,'8')
import sys,json,hashlib,time,threading,argparse
import numpy as np,pandas as pd,joblib,sklearn,psutil
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from glucotwin.features import make_features,profile_features
from glucotwin.episodes import onsets
from glucotwin.event_study import onset_labels,summarize,gate,assess_scores,choose_event_threshold
DEVICE='cpu'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def freeze_roles(manifest,protocol):
    entries=sorted([p for p in manifest['participants'] if p['split'] in ('train','validation')],key=lambda p:p['patient_id'])
    reserved={p['patient_id'] for p in manifest['participants'] if p['split']=='test'}
    bands=np.array([p['a1c_group'] for p in entries]);roles=[]
    for fold,(development,evaluation) in enumerate(StratifiedKFold(3,shuffle=True,random_state=protocol['seed']).split(entries,bands)):
        rng=np.random.default_rng(protocol['seed']+fold)
        threshold=[]
        for band in sorted(set(bands)):
            pool=development[bands[development]==band]
            threshold.extend(rng.choice(pool,1,replace=False).tolist())
        fitting=sorted(set(development)-set(threshold))
        role={name:[entries[i]['patient_id'] for i in indices] for name,indices in [('fit',fitting),('threshold',sorted(threshold)),('evaluation',evaluation)]}
        assert all(reserved.isdisjoint(v) for v in role.values())
        assert not set(role['fit'])&set(role['threshold']) and not set(role['evaluation'])&(set(role['fit'])|set(role['threshold']))
        roles.append(role)
    return entries,roles

def model_for(name):
    from xgboost import XGBClassifier
    parts=name.split('_');trees=int(parts[1]);depth=int(parts[2][1:])
    classifier=XGBClassifier(n_estimators=trees,max_depth=depth,learning_rate=.03,
        min_child_weight=10,subsample=.8,colsample_bytree=.8,reg_lambda=10.,
        tree_method='hist',device=DEVICE,objective='binary:logistic',eval_metric='logloss',
        n_jobs=8,random_state=2026)
    return Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),
                     ('classifier',classifier)])

def matrix(records,ids,columns):
    parts=[];ys=[];groups=[]
    for pid in ids:
        r=records[pid];known=r['known'];parts.append(r['X'].loc[known,columns]);ys.append(r['y'][known]);groups.extend([pid]*int(known.sum()))
    return pd.concat(parts,ignore_index=True),np.concatenate(ys),np.array(groups)

def fit(records,ids,columns,name):
    X,y,groups=matrix(records,ids,columns)
    if len(np.unique(y))<2:raise RuntimeError('Insufficient training classes; no supported classifier')
    unique,counts=np.unique(groups,return_counts=True);count=dict(zip(unique,counts))
    weights=np.array([1./count[g] for g in groups]);weights*=len(weights)/weights.sum()
    if name.endswith('balanced'):
        fraction=np.average(y,weights=weights);weights*=np.where(y==1,.5/fraction,.5/(1-fraction))
    model=model_for(name)
    with threadpool_limits(limits=8):model.fit(X,y,classifier__sample_weight=weights)
    if DEVICE=='cuda':
        actual=json.loads(model.named_steps['classifier'].get_booster().save_config())['learner']['generic_param']['device']
        if not actual.startswith('cuda'):raise RuntimeError('CUDA requested but XGBoost fell back to CPU')
    return model

def predict(model,records,ids,columns):
    with threadpool_limits(limits=8):
        return {pid:model.predict_proba(records[pid]['X'][columns])[:,1] if len(records[pid]['X']) else np.empty(0) for pid in ids}

def inner_select(records,ids,bands,columns,names):
    splits=list(StratifiedKFold(3,shuffle=True,random_state=2026).split(ids,[bands[p] for p in ids]))
    results={}
    for name in names:
        aps=[]
        for training,validation in splits:
            fit_ids=[ids[i] for i in training];val_ids=[ids[i] for i in validation]
            model=fit(records,fit_ids,columns,name);scores=predict(model,records,val_ids,columns)
            labels=np.concatenate([records[p]['y'][records[p]['known']] for p in val_ids])
            values=np.concatenate([scores[p][records[p]['known']] for p in val_ids])
            aps.append(float(average_precision_score(labels,values)) if labels.sum() else 0.)
        results[name]={'mean_average_precision':float(np.mean(aps)),'fold_average_precision':aps}
        print('  inner',name,round(float(np.mean(aps)),4),flush=True)
    chosen=max(names,key=lambda name:results[name]['mean_average_precision'])
    return chosen,results

def run(study='gpu_v2',device='cpu'):
    global DEVICE
    if study!='gpu_v2':raise ValueError('Only the active XGBoost protocol is supported')
    DEVICE=device
    if device=='cuda' and study!='gpu_v2':raise ValueError('CUDA is supported only for the XGBoost study')
    output_name='event_study_'+study
    start=time.perf_counter();protocol_path=ROOT/'configs'/f'{output_name}.json'
    protocol=json.loads(protocol_path.read_text());protocol_hash=sha(protocol_path)
    if device=='cuda' and not all(name.startswith('xgb_') for name in protocol['candidate_names']):
        raise ValueError('CUDA study requires XGBoost candidates')
    if study=='gpu_v2':
        import xgboost
        if xgboost.__version__!=protocol['xgboost_version']:raise RuntimeError('Install the pinned experiment requirements first')
    manifest_path=ROOT/'configs/cgmacros_splits.json';manifest=json.loads(manifest_path.read_text())
    entries,roles=freeze_roles(manifest,protocol)
    frozen={'protocol_sha256':protocol_hash,'source_manifest_sha256':sha(manifest_path),'roles':roles}
    role_path=ROOT/'configs'/f'cgmacros_event_roles_{study}.json'
    if role_path.exists() and json.loads(role_path.read_text())!=frozen:raise RuntimeError('Frozen roles changed; version the study')
    role_path.write_text(json.dumps(frozen,indent=2),encoding='utf-8')
    source=ROOT/'data/raw/cgmacros/CGMacros';bio_path=source/'bio.csv'
    bio=pd.read_csv(bio_path);bio.columns=bio.columns.str.strip();bio=bio.set_index('subject')
    records={};hashes={'bio':sha(bio_path)};bands={p['patient_id']:p['a1c_group'] for p in entries}
    for patient in entries:
        pid=patient['patient_id'];path=source/f'CGMacros-{pid:03d}/CGMacros-{pid:03d}.csv'
        hashes[str(pid)]=sha(path);frame=pd.read_csv(path)
        features=make_features(frame,profile_features(bio.loc[pid]),patient['phase_utc_minutes_mod_5'])
        glucose=features.cgm_current.copy()
        eligible=features.history_eligible & (features.cgm_current<=180) & (features.index>=pd.Timestamp(patient['minimum_forecast_time']))
        X=features.loc[eligible].drop(columns='history_eligible').copy()
        y,known=onset_labels(glucose,X.index)
        records[pid]={'X':X,'y':y,'known':known,'times':X.index,'glucose':glucose,'episodes':onsets(glucose,'high')}
    columns=list(next(iter(records.values()))['X']);cgm=[c for c in columns if c.startswith('cgm_')]
    input_path=ROOT/'data/processed'/f'cgmacros_event_inputs_{study}.json'
    input_path.write_text(json.dumps({'frozen':frozen,'source_sha256':hashes,'columns':columns},indent=2),encoding='utf-8')
    print('Prepared',len(records),'development patients;',sum(len(r['X']) for r in records.values()),'past-eligible rows;',sum(int(r['known'].sum()) for r in records.values()),'known labels',flush=True)
    support={'patients':len(records),'opportunities':sum(len(r['X']) for r in records.values()),'known_label_rows':sum(int(r['known'].sum()) for r in records.values()),'positive_label_rows':sum(int(r['y'][r['known']].sum()) for r in records.values()),'unknown_label_rows':sum(int((~r['known']).sum()) for r in records.values())}
    rss=[psutil.Process().memory_info().rss];stop=threading.Event()
    def monitor():
        while not stop.wait(.1):rss.append(psutil.Process().memory_info().rss)
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    arms={'fused':columns,'cgm_only':cgm}
    output_rows={name:[] for name in list(arms)+['slope_rule']};fold_reports=[]
    artifacts=ROOT/'artifacts';artifacts.mkdir(exist_ok=True)
    for fold,role in enumerate(roles):
        print('OUTER FOLD',fold+1,'fit',len(role['fit']),'threshold',len(role['threshold']),'evaluation',len(role['evaluation']),flush=True)
        chosen,selection=inner_select(records,role['fit'],bands,columns,protocol['candidate_names'])
        report={'fold':fold+1,'selected_candidate':chosen,'inner_selection':selection,'methods':{}}
        for method,used in list(arms.items())+[('slope_rule',cgm)]:
            if method=='slope_rule':
                model=None;scores={pid:(r['X'].cgm_current+30*r['X'].cgm_slope_30m.fillna(0)).to_numpy() for pid,r in records.items() if pid in role['threshold']+role['evaluation']}
            else:
                method_candidate=chosen
                model=fit(records,role['fit'],used,method_candidate);scores=predict(model,records,role['threshold']+role['evaluation'],used)
            threshold_records={p:records[p] for p in role['threshold']}
            threshold_scores={p:scores[p] for p in role['threshold']}
            threshold,tuning,tuning_pass=choose_event_threshold(threshold_records,threshold_scores,protocol['engineering_gate'],protocol['threshold_quantiles'])
            # Freeze cutoff before reading evaluation labels or onsets for scoring.
            artifact={'model':model,'features':used,'threshold':threshold,'method':method,'protocol_sha256':protocol_hash,'input_manifest_sha256':sha(input_path),'roles':role,'probability_display_approved':False,'operational_alerts_approved':False,'score_kind':'uncalibrated ranking score' if model is not None else 'trend extrapolation mg/dL','sklearn_version':sklearn.__version__}
            joblib.dump(artifact,artifacts/f'cgmacros_onset_{study}_fold{fold+1}_{method}.joblib')
            evaluation_rows=assess_scores({p:records[p] for p in role['evaluation']},{p:scores[p] for p in role['evaluation']},threshold)
            output_rows[method].extend(evaluation_rows)
            report['methods'][method]={'threshold':threshold,'threshold_gate_passed':tuning_pass,'threshold_setting':tuning,'outer_evaluation':summarize(evaluation_rows)}
            report['methods'][method].update(cutoff_operating_criteria_met_with_support_waived=tuning_pass,
                cutoff_full_support_gate_met=gate(tuning,protocol['engineering_gate'],True),
                cutoff_patients=len(role['threshold']))
            print(' ',method,'threshold',round(threshold,4),'recall',report['methods'][method]['outer_evaluation']['episode_recall'],'precision',report['methods'][method]['outer_evaluation']['precision_lower_bound'],flush=True)
        fold_reports.append(report)
    stop.set();thread.join()
    pooled={method:summarize(rows) for method,rows in output_rows.items()}
    intervals={};rng=np.random.default_rng(protocol['seed'])
    for method,rows in output_rows.items():
        boot=[summarize([rows[i] for i in rng.integers(0,len(rows),len(rows))]) for _ in range(2000)]
        intervals[method]={key:np.quantile([r[key] for r in boot if r[key] is not None],[.025,.975]).tolist() for key in ['episode_recall','precision_lower_bound','false_per_eligible_day']}
    checks={method:gate(result,protocol['engineering_gate']) for method,result in pooled.items()}
    study={'version':protocol['version'],'status':'exploratory nested patient-level development evaluation; no clinical or reserved-test evaluation',
        'protocol_sha256':protocol_hash,'source_manifest_sha256':sha(manifest_path),'input_manifest_sha256':sha(input_path),
        'support':support,'feature_groups':{'cgm':len(cgm),'clinical':5,'heart_rate':9,'clock':sum(c.startswith('clock_') for c in columns)},'folds':fold_reports,'pooled':pooled,'patient_bootstrap95':intervals,
        'pooled_engineering_gate_passed':checks,'all_threshold_folds_passed':all(f['methods']['fused']['threshold_gate_passed'] for f in fold_reports),
        'probability_display_approved':False,'operational_alerts_approved':False,
        'device_requested':device,'runtime_seconds':round(time.perf_counter()-start,2),'sampled_peak_rss_mib':round(max(rss)/2**20,2),
        'versions':{'python':sys.version.split()[0],'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__},
        'limitations':['Development patients previously inspected in earlier studies','Reconstructed sensor grid and assumed clinical availability','Patient count remains small','Unknown alarms lower precision bound','No calibration or medical validation']}
    if device=='cuda':study['gpu_execution_verified']=True
    if study['version'].endswith('gpu-v2'):
        import xgboost
        study['versions']['xgboost']=xgboost.__version__
    (ROOT/'reports'/f'{output_name}.json').write_text(json.dumps(study,indent=2,allow_nan=False),encoding='utf-8')
    suffix=output_name.removeprefix('event_study_')
    (ROOT/'data/processed'/f'cgmacros_event_patient_metrics_{suffix}.json').write_text(json.dumps(output_rows,indent=2,default=str),encoding='utf-8')
    print('COMPLETE',json.dumps({'pooled':pooled,'gates':checks,'seconds':study['runtime_seconds'],'peak_rss_mib':study['sampled_peak_rss_mib']},indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--study',choices=['gpu_v2'],default='gpu_v2');parser.add_argument('--device',choices=['cpu','cuda'],default='cpu');args=parser.parse_args()
    run(args.study,args.device)
