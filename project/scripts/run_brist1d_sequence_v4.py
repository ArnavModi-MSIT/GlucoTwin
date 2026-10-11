"""One fixed CPU TCN with matched-information XGBoost and inner stopping."""
import json
import random
import threading
import time
import joblib
import numpy as np
import psutil
import torch
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from xgboost import XGBRegressor
from run_brist1d_study import (ROOT,ROLES,PROTOCOL,CACHE as V1_CACHE,load_cache,digest,
    patient_rows,summarize,paired_comparison,write_json)
from run_brist1d_freshness_v2 import CACHE as V2_CACHE,REPORT as V2_REPORT
from prepare_brist1d_sequence_v4 import CONFIG,CACHE
from glucotwin.brist1d_sequence import SequenceScaler,sample_positions,head_weights,inner_roles
from glucotwin.brist1d_tcn import CompactTCN

REPORT=ROOT/'reports/brist1d_sequence_v4.json'
ARTIFACTS=ROOT/'artifacts/brist1d_v4'


def seed_all(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)


def load_inputs():
    config=json.loads(CONFIG.read_text()); protocol=json.loads(PROTOCOL.read_text())
    manifest=json.loads(ROLES.read_text()); cache=json.loads((CACHE/'manifest.json').read_text())
    assert cache['config_sha256']==digest(CONFIG) and cache['roles_sha256']==digest(ROLES)
    assert cache['v1_cache_manifest_sha256']==digest(V1_CACHE/'manifest.json')
    _,original=load_cache(manifest)
    fresh=json.loads((V2_CACHE/'manifest.json').read_text())
    checks=json.loads((ROOT/'reports/brist1d_study_v2_checks.json').read_text())
    assert checks['status']=='passed' and checks['report_sha256']==digest(V2_REPORT)
    if set(cache['development'])!=set(manifest['development']) or set(cache['development'])&set(manifest['reserved']):
        raise ValueError('Sequence role mismatch')
    records={}; sequences={}
    for pid in manifest['development']:
        path=V2_CACHE/(pid+'.npz'); assert digest(path)==fresh['cache_sha256'][pid]
        with np.load(path,allow_pickle=False) as archive: records[pid]={k:archive[k] for k in archive.files}
        for key in ('times','y30','y60'): np.testing.assert_array_equal(records[pid][key],original[pid][key])
        path=CACHE/(pid+'_sequence.npy'); assert digest(path)==cache['sequence_sha256'][pid]
        sequences[pid]=np.load(path,mmap_mode='r',allow_pickle=False)
        assert len(sequences[pid])==len(records[pid]['times'])
    return config,protocol,manifest,cache,records,sequences


def gather(records,sequences,ids,cap,seed):
    sequences_out=[]; context=[]; targets=[]; current=[]; groups=[]; positions_private={}
    for pid in ids:
        r=records[pid]; pos=sample_positions(r,pid,cap,seed)
        if not len(pos): raise ValueError('No issue targets for patient')
        positions_private[pid]=pos
        sequences_out.append(np.asarray(sequences[pid][pos]))
        context.append(r['X'][pos]); targets.append(np.column_stack([r['y30'][pos],r['y60'][pos]]))
        current.append(r['X'][pos,0]); groups.extend([pid]*len(pos))
    return {'sequence':np.concatenate(sequences_out),'context':np.concatenate(context),
            'targets':np.concatenate(targets),'current':np.concatenate(current).astype(float),
            'groups':np.asarray(groups),'positions':positions_private}


def fit_scalers(data):
    sequence=SequenceScaler().fit(data['sequence'])
    context=make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler())
    context.fit(data['context'])
    return sequence,context


def encoded_training(data,scalers):
    sequence,context=scalers
    return sequence.transform(data['sequence']),context.transform(data['context']).astype(np.float32)


def predict_tcn(model,sequence,context,config):
    model.eval(); output=[]; batch=config['training']['prediction_batch_size']
    with torch.inference_mode():
        for start in range(0,len(sequence),batch):
            result=model(torch.from_numpy(sequence[start:start+batch]),torch.from_numpy(context[start:start+batch]))
            output.append(result.numpy().astype(float)*config['training']['target_scale_mg_dl'])
    return np.concatenate(output)


def patient_validation_mae(targets,predicted,groups):
    values=[]
    for pid in np.unique(groups):
        for head in (0,1):
            mask=(groups==pid)&np.isfinite(targets[:,head])
            if not mask.any(): raise ValueError('Inner stopping head unsupported')
            values.append(float(np.abs(predicted[mask,head]-targets[mask,head]).mean()))
    return float(np.mean(values))


def train_tcn(data,scalers,config,seed,epochs,validation=None,fold=0):
    seed_all(seed)
    sequence,context=encoded_training(data,scalers)
    model=CompactTCN(sequence.shape[1],context.shape[1],config['architecture'])
    optimizer=torch.optim.AdamW(model.parameters(),lr=config['training']['learning_rate'],weight_decay=config['training']['weight_decay'])
    weights=head_weights(data['targets'],data['groups'])
    deltas=(data['targets']-data['current'][:,None])/config['training']['target_scale_mg_dl']
    target=np.nan_to_num(deltas,nan=0.).astype(np.float32)
    seq_tensor=torch.from_numpy(sequence); ctx_tensor=torch.from_numpy(context)
    target_tensor=torch.from_numpy(target); weight_tensor=torch.from_numpy(weights)
    validation_encoded=encoded_training(validation,scalers) if validation is not None else None
    rng=np.random.default_rng(seed); best=float('inf'); best_epoch=1; bad=0; log=[]
    for epoch in range(1,epochs+1):
        model.train(); order=rng.permutation(len(target)); total=0.
        for start in range(0,len(order),config['training']['batch_size']):
            indices=torch.from_numpy(order[start:start+config['training']['batch_size']])
            optimizer.zero_grad(set_to_none=True)
            predicted=model(seq_tensor[indices],ctx_tensor[indices])
            loss=(torch.abs(predicted-target_tensor[indices])*weight_tensor[indices]).mean()
            if not torch.isfinite(loss): raise ValueError('Neural training diverged')
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),config['training']['gradient_clip'])
            optimizer.step(); total+=float(loss.detach())*len(indices)
        item={'epoch':epoch,'training_scaled_absolute_loss':total/len(target)}
        if validation is not None:
            pred=predict_tcn(model,*validation_encoded,config)+validation['current'][:,None]
            score=patient_validation_mae(validation['targets'],pred,validation['groups'])
            item['inner_patient_macro_mae']=score
            if score<best-config['training']['minimum_improvement_mg_dl']:
                best=score; best_epoch=epoch; bad=0
            else: bad+=1
        log.append(item)
        stage='inner' if validation is not None else 'refit'
        print(f'fold {fold}/4 {stage} epoch {epoch}/{epochs}: '+json.dumps(item),flush=True)
        if validation is not None and bad>=config['training']['patience']: break
    return model,{'selected_epochs':best_epoch if validation is not None else epochs,
                  'inner_best_patient_macro_mae':best if validation is not None else None,'history':log,
                  'parameter_count':sum(p.numel() for p in model.parameters()),'context_encoded_features':context.shape[1]}


def run():
    if REPORT.exists(): raise ValueError('Completed sequence study exists; refusing overwrite')
    config,protocol,manifest,cache,records,sequences=load_inputs()
    torch.set_num_threads(config['training']['threads']); torch.set_num_interop_threads(1)
    reference_paths=[CONFIG,PROTOCOL,ROLES,CACHE/'manifest.json',V2_REPORT]
    references={str(p.relative_to(ROOT)):digest(p) for p in reference_paths}
    started=time.perf_counter(); stop=threading.Event(); peak=[psutil.Process().memory_info().rss]
    def sampler():
        while not stop.wait(.25): peak[0]=max(peak[0],psutil.Process().memory_info().rss)
    thread=threading.Thread(target=sampler,daemon=True); thread.start()
    public={'version':config['version'],'units':'mg/dL','config_sha256':digest(CONFIG),'reference_hashes':references,
        'development_patients':16,'reserved_patients_scored':0,'torch_version':torch.__version__,
        'status':'one fixed CPU architecture; inner patient stopping; matched-information comparator; no deployment',
        'horizons':{},'folds':[]}
    totals={h:{} for h in (30,60)}; private={'folds':[]}
    try:
        for role in manifest['folds']:
            fold=role['fold']; chosen=inner_roles(role,manifest,config['seed'])
            assert chosen==cache['inner_roles'][str(fold)]
            fit=gather(records,sequences,chosen['fit'],config['fit_cap_per_patient'],config['seed'])
            validation=gather(records,sequences,chosen['stopping'],config['inner_cap_per_patient'],config['seed'])
            scalers=fit_scalers(fit)
            _,selection=train_tcn(fit,scalers,config,config['seed']+fold,config['training']['maximum_epochs'],validation,fold)
            epochs=selection['selected_epochs']; del fit,validation,scalers
            fit=gather(records,sequences,role['fit'],config['fit_cap_per_patient'],config['seed'])
            scalers=fit_scalers(fit)
            model,refit=train_tcn(fit,scalers,config,config['seed']+fold,epochs,None,fold)
            encoded_seq,encoded_ctx=encoded_training(fit,scalers)
            flattened=np.concatenate([encoded_seq.reshape(len(encoded_seq),-1),encoded_ctx],axis=1)
            xgb_models={}
            weights=head_weights(fit['targets'],fit['groups'])
            for head,horizon in enumerate((30,60)):
                valid=np.isfinite(fit['targets'][:,head])
                xgb=XGBRegressor(**protocol['models']['xgb_delta'],n_jobs=protocol['threads'],random_state=config['seed'])
                with threadpool_limits(limits=protocol['threads']):
                    xgb.fit(flattened[valid],fit['targets'][valid,head]-fit['current'][valid],sample_weight=weights[valid,head])
                xgb_models[horizon]=xgb
                print(f'fold {fold}/4 matched XGBoost +{horizon}: fitted',flush=True)
            artifact=ARTIFACTS/f'fold{fold}'; artifact.mkdir(parents=True,exist_ok=True)
            torch.save(model.state_dict(),artifact/'tcn.pt')
            joblib.dump({'scalers':scalers,'context_features':refit['context_encoded_features'],
                'config_sha256':digest(CONFIG),'xgb':xgb_models},artifact/'preprocessing_and_xgb.joblib')
            private['folds'].append({'fold':fold,'inner_roles':chosen,'final_fit_positions':fit['positions'],
                'inner_selection':selection,'refit':refit})
            fit_counts={str(h):int(np.isfinite(fit['targets'][:,i]).sum()) for i,h in enumerate((30,60))}
            del fit,encoded_seq,encoded_ctx,flattened,weights
            patient_predictions={h:[] for h in (30,60)}
            for pid in role['evaluation']:
                record=records[pid]; positions=sample_positions(record,pid,None,config['seed'])
                tcn=[]; boosted=[]; batch=config['training']['prediction_batch_size']
                for start in range(0,len(positions),batch):
                    pos=positions[start:start+batch]
                    seq=scalers[0].transform(np.asarray(sequences[pid][pos]))
                    ctx=scalers[1].transform(record['X'][pos]).astype(np.float32)
                    tcn.append(predict_tcn(model,seq,ctx,config)+record['X'][pos,0,None])
                    flat=np.concatenate([seq.reshape(len(seq),-1),ctx],axis=1)
                    with threadpool_limits(limits=protocol['threads']):
                        boosted.append(np.column_stack([xgb_models[h].predict(flat) for h in (30,60)])+record['X'][pos,0,None])
                tcn=np.concatenate(tcn); boosted=np.concatenate(boosted)
                for head,horizon in enumerate((30,60)):
                    valid=np.isfinite(record['y'+str(horizon)][positions]); selected=positions[valid]
                    patient_predictions[horizon].append({'pid':pid,'actual':record['y'+str(horizon)][selected],
                        'issued_at':record['times'][selected],'tcn':tcn[valid,head],
                        'matched_xgb':boosted[valid,head],'persistence':record['X'][selected,0]})
                print(f'fold {fold}/4 evaluated development patient',flush=True)
            for horizon in (30,60):
                parts=patient_predictions[horizon]
                prediction={key:np.concatenate([p[key] for p in parts]) for key in ('actual','issued_at','tcn','matched_xgb','persistence')}
                groups=np.concatenate([np.repeat(p['pid'],len(p['actual'])) for p in parts]); prediction['groups']=groups
                with np.load(V2_CACHE/'outer_predictions'/str(horizon)/f'fold{fold}.npz',allow_pickle=False) as reference:
                    for key in ('actual','issued_at','groups'): np.testing.assert_array_equal(prediction[key],reference[key])
                    prediction['v2_xgb_fused']=reference['xgb_delta_fused'].copy()
                    np.testing.assert_array_equal(prediction['persistence'],reference['persistence'])
                for name in ('tcn','matched_xgb','persistence','v2_xgb_fused'):
                    totals[horizon].setdefault(name,[]).extend(patient_rows(prediction['actual'],prediction[name],groups))
                folder=CACHE/'outer_predictions'/str(horizon); folder.mkdir(parents=True,exist_ok=True)
                np.savez_compressed(folder/f'fold{fold}.npz',**prediction)
            public['folds'].append({'fold':fold,'inner_fit_patients':9,'inner_stopping_patients':3,
                'final_fit_patients':12,'outer_patients':4,'selected_epochs':epochs,
                'inner_selection_history':selection['history'],'refit_history':refit['history'],
                'parameter_count':refit['parameter_count'],'context_encoded_features':refit['context_encoded_features'],
                'sampled_final_fit_rows_by_horizon':fit_counts})
            print('Completed fold '+str(fold),flush=True)
        for horizon in (30,60):
            scores=totals[horizon]
            public['horizons'][str(horizon)]={'scores':{n:summarize(rows) for n,rows in scores.items()},
                'paired_tcn_minus_matched_xgb':paired_comparison(scores['tcn'],scores['matched_xgb'],protocol['bootstrap_repetitions'],protocol['seed']),
                'paired_tcn_minus_v2_reference':paired_comparison(scores['tcn'],scores['v2_xgb_fused'],protocol['bootstrap_repetitions'],protocol['seed'])}
        for path in reference_paths: assert digest(path)==references[str(path.relative_to(ROOT))], 'Reference changed'
        public['runtime']={'seconds':round(time.perf_counter()-started,2),
            'sampled_peak_rss_mib':round(peak[0]/1048576,2),'threads':config['training']['threads'],'device':'cpu'}
        private['patient_errors']=totals
        # Keep arrays in sampling manifests private, serialized via joblib.
        joblib.dump(private,CACHE/'study_private.joblib')
        write_json(REPORT,public)
        print(json.dumps({h:{n:round(s['mae'],3) for n,s in v['scores'].items()} for h,v in public['horizons'].items()}),flush=True)
        print(json.dumps(public['runtime']),flush=True)
        return public
    finally:
        stop.set(); thread.join(timeout=2)


if __name__=='__main__': run()
