"""Build local validation-patient replay caches without targets or predictions."""
from pathlib import Path
import json,time
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1]

def run():
    start=time.monotonic();manifest=json.loads((ROOT/'configs/rbg_splits.json').read_text())
    chosen={p['patient_id'] for p in manifest['participants'] if p['split']=='validation'}
    out=ROOT/'data/processed/rbg/replay';out.mkdir(parents=True,exist_ok=True)
    prior=None;pending=[];seen=set()
    def save(pid,parts):
        frame=pd.concat(parts,ignore_index=True)
        np.savez(out/f'{pid}.npz',times=pd.to_datetime(frame.ts).to_numpy(dtype='datetime64[ns]').astype('int64'),glucose=frame.GlucoseCGM.to_numpy(dtype=np.float32))
        seen.add(pid)
    for chunk in pd.read_csv(ROOT/'data/raw/diadata/RBG_raw.csv',usecols=['ts','PtID','GlucoseCGM'],dtype={'PtID':'str'},chunksize=250000):
        for pid,g in chunk.groupby('PtID',sort=False):
            if prior is not None and prior!=pid:
                if prior in chosen:save(prior,pending)
                pending=[]
            prior=pid
            if pid in chosen:pending.append(g)
    if prior in chosen:save(prior,pending)
    assert seen==chosen
    print(f'Prepared {len(seen)} validation replay caches in {time.monotonic()-start:.1f}s. No test cache generated.')
if __name__=='__main__':run()
