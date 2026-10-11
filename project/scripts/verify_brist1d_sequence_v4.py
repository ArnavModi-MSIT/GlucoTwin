"""Check saved neural/comparator predictions, role isolation and causal histories."""
import json
import re
import subprocess
import sys
import joblib
import numpy as np
import pandas as pd
import torch
from run_brist1d_study import (ROOT,ROLES,digest,load_development_frame,write_json,patient_rows,summarize)
from run_brist1d_freshness_v2 import CONFIG as FRESHNESS_CONFIG,CACHE as V2_CACHE
from run_brist1d_sequence_v4 import (CONFIG,CACHE,REPORT,ARTIFACTS,load_inputs,gather,fit_scalers,predict_tcn)
from glucotwin.brist1d_sequence import encode_sequence,inner_roles,sample_positions
from glucotwin.brist1d_tcn import CompactTCN
from audit_brist1d_cohort import canonical_stream,CHANNELS


def verify():
    tests=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_brist1d*'],cwd=ROOT,
                         capture_output=True,text=True,check=True)
    if 'skipped=' in tests.stdout+tests.stderr: raise ValueError('Neural checks must execute, not skip')
    count=int(re.search(r'Ran (\d+) tests',tests.stdout+tests.stderr)[1])
    config,protocol,manifest,cache,records,sequences=load_inputs()
    torch.set_num_threads(config['training']['threads'])
    report=json.loads(REPORT.read_text())
    assert report['config_sha256']==digest(CONFIG) and set(report['horizons'])=={'30','60'}
    for path,value in report['reference_hashes'].items(): assert digest(ROOT/path)==value
    fresh=json.loads((V2_CACHE/'manifest.json').read_text()); assert fresh['features'][0]=='cgm_current'
    prepared={p.name.replace('_sequence.npy','') for p in CACHE.glob('*_sequence.npy')}
    assert prepared==set(manifest['development']) and not prepared&set(manifest['reserved'])
    caps=json.loads(FRESHNESS_CONFIG.read_text())['freshness_caps_minutes']
    native_probes=0
    for cadence in (5,15):
        pid=next(p for p in manifest['development'] if manifest['participants'][p]['native_minutes']==cadence)
        frame=load_development_frame(pid,manifest)
        frame=frame.loc[frame.device.fillna('').str.strip().ne('')].copy(); frame['timestamp']=pd.to_datetime(frame.timestamp)
        streams={c:canonical_stream(frame,c)[0] for c in CHANNELS}
        for position in [0,len(records[pid]['times'])//2,len(records[pid]['times'])-1]:
            issue=pd.Timestamp(records[pid]['times'][position]); issues=pd.DatetimeIndex([issue])
            prefix={c:s.loc[s.index<=issue-pd.Timedelta(minutes=protocol['availability_delay_minutes'][c])] for c,s in streams.items()}
            expected=encode_sequence(prefix,issues,cadence,protocol,config,caps)
            np.testing.assert_array_equal(expected[0],sequences[pid][position])
            np.testing.assert_allclose(expected[0,0,-1],records[pid]['X'][position,0],atol=2e-5,rtol=1e-6)
            native_probes+=1
    totals={h:{} for h in (30,60)}; neural_probes=0; xgb_probes=0; source_hashes={}
    private=joblib.load(CACHE/'study_private.joblib')
    for role in manifest['folds']:
        fold=role['fold']; expected=inner_roles(role,manifest,config['seed'])
        assert expected==cache['inner_roles'][str(fold)]
        detail=next(r for r in private['folds'] if r['fold']==fold)
        assert detail['inner_roles']==expected
        assert not (set(expected['fit'])|set(expected['stopping']))&set(role['evaluation'])
        assert not (set(role['fit'])|set(role['evaluation']))&set(manifest['reserved'])
        public=next(r for r in report['folds'] if r['fold']==fold)
        history=public['inner_selection_history']; best=float('inf'); best_epoch=1
        for row in history:
            if row['inner_patient_macro_mae']<best-config['training']['minimum_improvement_mg_dl']:
                best=row['inner_patient_macro_mae']; best_epoch=row['epoch']
        assert public['selected_epochs']==best_epoch
        assert len(public['refit_history'])==best_epoch
        # Recompute final preprocessing only from the twelve fit patients.
        fit=gather(records,sequences,role['fit'],config['fit_cap_per_patient'],config['seed'])
        bundle=joblib.load(ARTIFACTS/f'fold{fold}'/'preprocessing_and_xgb.joblib')
        assert bundle['config_sha256']==digest(CONFIG)
        scalers=fit_scalers(fit)
        np.testing.assert_array_equal(scalers[0].means,bundle['scalers'][0].means)
        np.testing.assert_array_equal(scalers[0].stds,bundle['scalers'][0].stds)
        for key in ('statistics_',):
            np.testing.assert_allclose(getattr(scalers[1][0],key),getattr(bundle['scalers'][1][0],key),equal_nan=True)
        for key in ('mean_','scale_'):
            np.testing.assert_allclose(getattr(scalers[1][1],key),getattr(bundle['scalers'][1][1],key),atol=1e-10,rtol=0)
        for pid in role['fit']:
            np.testing.assert_array_equal(fit['positions'][pid],detail['final_fit_positions'][pid])
        for head,horizon in enumerate((30,60)):
            assert int(np.isfinite(fit['targets'][:,head]).sum())==public['sampled_final_fit_rows_by_horizon'][str(horizon)]
        del fit
        model=CompactTCN(35,bundle['context_features'],config['architecture'])
        model.load_state_dict(torch.load(ARTIFACTS/f'fold{fold}'/'tcn.pt',map_location='cpu',weights_only=True)); model.eval()
        assert sum(p.numel() for p in model.parameters())==public['parameter_count']
        for horizon in (30,60):
            path=CACHE/'outer_predictions'/str(horizon)/f'fold{fold}.npz'
            source_hashes[str(path.relative_to(ROOT))]=digest(path)
            with np.load(path,allow_pickle=False) as archive: saved={k:archive[k] for k in archive.files}
            with np.load(V2_CACHE/'outer_predictions'/str(horizon)/f'fold{fold}.npz',allow_pickle=False) as reference:
                for key in ('actual','issued_at','groups','persistence'): np.testing.assert_array_equal(saved[key],reference[key])
                np.testing.assert_array_equal(saved['v2_xgb_fused'],reference['xgb_delta_fused'])
            groups=saved['groups']; y=saved['actual']; head=0 if horizon==30 else 1
            assert not set(groups)&set(manifest['reserved'])
            for name in ('tcn','matched_xgb','persistence','v2_xgb_fused'):
                totals[horizon].setdefault(name,[]).extend(patient_rows(y,saved[name],groups))
            for pid in role['evaluation']:
                in_saved=np.flatnonzero(groups==pid)
                selected=in_saved[np.linspace(0,len(in_saved)-1,8,dtype=int)]
                issue=saved['issued_at'][selected]
                positions=np.searchsorted(records[pid]['times'],issue)
                np.testing.assert_array_equal(records[pid]['times'][positions],issue)
                seq=bundle['scalers'][0].transform(np.asarray(sequences[pid][positions]))
                ctx=bundle['scalers'][1].transform(records[pid]['X'][positions]).astype(np.float32)
                current=records[pid]['X'][positions,0]
                neural=predict_tcn(model,seq,ctx,config)[:,head]+current
                flat=np.concatenate([seq.reshape(len(seq),-1),ctx],axis=1)
                boosted=bundle['xgb'][horizon].predict(flat)+current
                np.testing.assert_allclose(neural,saved['tcn'][selected],atol=.002,rtol=1e-6)
                np.testing.assert_allclose(boosted,saved['matched_xgb'][selected],atol=.002,rtol=1e-6)
                neural_probes+=len(selected); xgb_probes+=len(selected)
    for horizon,methods in totals.items():
        for name,rows in methods.items(): assert summarize(rows)==report['horizons'][str(horizon)]['scores'][name]
    assert not any('"'+p+'"' in REPORT.read_text() for p in manifest['participants'])
    checks={'status':'passed','report_sha256':digest(REPORT),'config_sha256':digest(CONFIG),
        'reference_hashes_unchanged':True,'synthetic_tests_passed':count,'real_native_prefix_sequence_probes':native_probes,
        'inner_patient_stopping_and_epoch_selection_verified':True,'final_train_only_scalers_recomputed_folds':4,
        'same_final_fit_sample_positions_verified_for_both_methods':True,
        'neural_prediction_probe_rows':neural_probes,'matched_xgb_prediction_probe_rows':xgb_probes,
        'prediction_absolute_tolerance_mg_dl':.002,'aggregate_methods_recomputed_per_horizon':4,
        'same_original_evaluation_arrays_verified':True,'reserved_sequence_matrices':0,'reserved_prediction_groups':0,
        'prediction_hashes':source_hashes}
    write_json(ROOT/'reports/brist1d_sequence_v4_checks.json',checks)
    print(json.dumps({k:v for k,v in checks.items() if k!='prediction_hashes'},indent=2))
    return checks


if __name__=='__main__': verify()
