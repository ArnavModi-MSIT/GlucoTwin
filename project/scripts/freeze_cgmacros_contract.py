"""Freeze exploratory patient splits without selecting on forecast scores."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
audit = pd.read_csv(ROOT/'reports/cgmacros_patient_audit.csv')
diag = pd.read_csv(ROOT/'reports/cgmacros_interpolation_diagnostics.csv')
dex = diag[diag.sensor.eq('Dexcom GL')].copy()
accepted = dex[dex.lattice_rebuild_mismatched_rows.eq(0) & dex.noninteger_lattice_values.eq(0)]
bio = pd.read_csv(ROOT/'data/raw/cgmacros/CGMacros/bio.csv')
bio.columns = bio.columns.str.strip()
rng = np.random.default_rng(2026)
entries, excluded = [], []
for group, subset in audit[audit.patient_id.isin(accepted.patient_id)].groupby('a1c_group',sort=True):
    ids = np.sort(subset.patient_id.to_numpy())
    rng.shuffle(ids)
    n_test = max(1,round(len(ids)*.2))
    n_validation = max(1,round(len(ids)*.2))
    for i,pid in enumerate(ids):
        split = 'test' if i<n_test else 'validation' if i<n_test+n_validation else 'train'
        frame = pd.read_csv(ROOT/f'data/raw/cgmacros/CGMacros/CGMacros-{pid:03d}/CGMacros-{pid:03d}.csv')
        times = pd.to_datetime(frame.Timestamp)
        cutoff = times.min()+pd.Timedelta(hours=24)
        warm = frame[times < cutoff]
        wt = times[times<cutoff].to_numpy(dtype='datetime64[ns]').astype('int64')/60e9
        wv = pd.to_numeric(warm['Dexcom GL'],errors='coerce').to_numpy()
        good = np.isfinite(wv)
        interior = good[:-2]&good[1:-1]&good[2:]&(np.diff(wt)[:-1]==1)&(np.diff(wt)[1:]==1)
        curved = interior&(np.abs(wv[2:]-2*wv[1:-1]+wv[:-2])>1e-6)
        phases = np.mod(wt[1:-1][curved].astype('int64'),5)
        phase = int(np.bincount(phases,minlength=5).argmax()) if len(phases) else None
        reference = int(accepted.loc[accepted.patient_id.eq(pid),'modal_phase'].iloc[0])
        if phase is None or phase!=reference:
            raise RuntimeError(f'Warmup phase not sufficient: {pid}')
        entries.append({'patient_id':int(pid),'split':split,'a1c_group':group,'phase_utc_minutes_mod_5':phase,
                        'warmup_hours':24,'minimum_forecast_time':cutoff.isoformat()})
for pid in sorted(set(audit.patient_id)-set(accepted.patient_id)):
    excluded.append({'patient_id':int(pid),'reason':'fixed-grid reconstruction not exact or noninteger anchor'})
manifest = {'seed':2026,'status':'exploratory reconstructed-grid benchmark; native flags not verified',
            'selection':'predeclared structural reconstruction checks, not model performance',
            'participants':sorted(entries,key=lambda r:r['patient_id']),'excluded':excluded}
out = ROOT/'configs'
out.mkdir(exist_ok=True)
(out/'cgmacros_splits.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
summary = pd.DataFrame(entries).groupby(['split','a1c_group']).size().unstack(fill_value=0)
print(summary.to_string())
print('Accepted',len(entries),'excluded',len(excluded))
assert len({r['patient_id'] for r in entries})==len(entries)
assert set(r['patient_id'] for r in entries).isdisjoint(r['patient_id'] for r in excluded)
