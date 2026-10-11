"""Prepare bounded patient matrices; reserved test targets are never generated."""
from pathlib import Path
import json,sys,time
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from glucotwin.rbg import supervised_rbg

def run():
    started=time.monotonic()
    patients={p['patient_id']:p for p in json.loads((ROOT/'configs/rbg_splits.json').read_text())['participants']}
    output=ROOT/'data/processed/rbg';output.mkdir(parents=True,exist_ok=True)
    summaries=[];columns=None;done=set()
    def prepare(pid,frame):
        nonlocal columns
        if pid in done:raise ValueError('Input must have contiguous patient groups')
        done.add(pid);patient=patients[pid]
        if patient['split']=='test':return
        for horizon in [30,60]:
            selected=supervised_rbg(frame,patient,horizon)
            count=len(selected)
            if patient['split']=='train' and count>2000:
                selected=selected.sample(n=2000,random_state=2026).sort_index()
            feature_names=[c for c in selected if c!='target']
            if columns is None:columns=feature_names
            assert columns==feature_names
            folder=output/str(horizon)/patient['split'];folder.mkdir(parents=True,exist_ok=True)
            np.savez(folder/f'{pid}.npz',X=selected[columns].to_numpy(dtype=np.float32),y=selected.target.to_numpy(dtype=np.float32),
                     times=selected.index.to_numpy(dtype='datetime64[ns]').astype('int64'))
            summaries.append({'patient_id':pid,'split':patient['split'],'horizon':horizon,'eligible_rows':count,'saved_rows':len(selected)})
        if len(done)%20==0:print(f'{len(done)} patient groups processed',flush=True)
    prior=None;pending=[]
    for chunk in pd.read_csv(ROOT/'data/raw/diadata/RBG_raw.csv',usecols=['ts','PtID','GlucoseCGM'],dtype={'PtID':'str'},chunksize=250000):
        for pid,group in chunk.groupby('PtID',sort=False):
            if prior is not None and pid!=prior:
                prepare(prior,pd.concat(pending,ignore_index=True));pending=[]
            prior=pid;pending.append(group)
    if prior is not None:prepare(prior,pd.concat(pending,ignore_index=True))
    assert done==set(patients)
    (output/'features.json').write_text(json.dumps(columns,indent=2))
    pd.DataFrame(summaries).to_csv(output/'patient_counts.csv',index=False)
    counts=pd.DataFrame(summaries)
    summary={'status':'training/validation prepared; test target matrices absent','features':columns,'patients':counts.groupby('split').patient_id.nunique().to_dict(),
             'rows':counts.groupby(['horizon','split'])[['eligible_rows','saved_rows']].sum().reset_index().to_dict('records'),
             'seconds':round(time.monotonic()-started,1)}
    (ROOT/'reports/rbg_preparation.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
if __name__=='__main__':run()
