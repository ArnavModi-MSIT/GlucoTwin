"""Prepare only development histories; retain all original cached issue rows."""
import json
import time
import numpy as np
import pandas as pd
from run_brist1d_study import (ROOT,CACHE as V1_CACHE,ROLES,PROTOCOL,load_cache,
    load_development_frame,digest,write_json)
from run_brist1d_freshness_v2 import CONFIG as FRESHNESS_CONFIG
from audit_brist1d_cohort import canonical_stream,CHANNELS
from glucotwin.brist1d_sequence import encode_sequence,inner_roles

CONFIG=ROOT/'configs/brist1d_sequence_v4.json'
CACHE=ROOT/'data/processed/brist1d_v4'


def prepare():
    if (CACHE/'manifest.json').exists(): raise ValueError('Sequence cache already frozen; refusing overwrite')
    config=json.loads(CONFIG.read_text()); protocol=json.loads(PROTOCOL.read_text())
    manifest=json.loads(ROLES.read_text()); caps=json.loads(FRESHNESS_CONFIG.read_text())['freshness_caps_minutes']
    stamp,records=load_cache(manifest)
    started=time.perf_counter(); counts=[]; hashes={}
    CACHE.mkdir(parents=True,exist_ok=True)
    for i,pid in enumerate(manifest['development'],1):
        frame=load_development_frame(pid,manifest)
        frame=frame.loc[frame.device.fillna('').str.strip().ne('')].copy()
        frame['timestamp']=pd.to_datetime(frame.timestamp)
        streams={c:canonical_stream(frame,c)[0] for c in CHANNELS}
        issues=pd.DatetimeIndex(records[pid]['times'].astype('datetime64[ns]'))
        sequence=encode_sequence(streams,issues,manifest['participants'][pid]['native_minutes'],protocol,config,caps)
        path=CACHE/(pid+'_sequence.npy')
        np.save(path,sequence,allow_pickle=False)
        hashes[pid]=digest(path); counts.append(len(sequence))
        print(f'Prepared causal sequence {i}/16: {len(sequence)} existing issue rows',flush=True)
    private={'version':config['version'],'config_sha256':digest(CONFIG),
        'roles_sha256':digest(ROLES),'v1_cache_manifest_sha256':digest(V1_CACHE/'manifest.json'),
        'development':manifest['development'],'sequence_sha256':hashes,
        'inner_roles':{str(role['fold']):inner_roles(role,manifest,config['seed']) for role in manifest['folds']}}
    write_json(CACHE/'manifest.json',private)
    public={'version':config['version'],'config_sha256':digest(CONFIG),'development_patients':16,
        'reserved_patients_prepared':0,'issue_rows':sum(counts),'sequence_shape_per_issue':[35,25],
        'sequence_storage_bytes':sum((CACHE/(pid+'_sequence.npy')).stat().st_size for pid in manifest['development']),
        'seconds':round(time.perf_counter()-started,2),
        'status':'original issue rows and exact targets preserved; no resampling of labels; only history queries placed on five-minute causal grid',
        'inner_roles':'three cadence-stratified stopping patients chosen from each outer fit group before model fitting'}
    write_json(ROOT/'reports/brist1d_sequence_preparation_v4.json',public)
    print(json.dumps(public),flush=True)
    return private


if __name__=='__main__': prepare()
