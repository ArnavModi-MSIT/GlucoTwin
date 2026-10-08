"""Build supervised rows using frozen metadata; never infer phases from test targets."""
from pathlib import Path
import json, sys, time
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from glucotwin.features import make_features, profile_features

def run():
    started = time.perf_counter()
    manifest = json.loads((ROOT/'configs/cgmacros_splits.json').read_text())
    data = ROOT/'data/raw/cgmacros/CGMacros'
    out = ROOT/'data/processed'
    out.mkdir(parents=True,exist_ok=True)
    bio = pd.read_csv(data/'bio.csv')
    bio.columns = bio.columns.str.strip()
    bio = bio.set_index('subject')
    all_rows, summaries = [], []
    for patient in manifest['participants']:
        pid = patient['patient_id']
        frame = pd.read_csv(data/f'CGMacros-{pid:03d}/CGMacros-{pid:03d}.csv')
        features = make_features(frame,profile_features(bio.loc[pid]),patient['phase_utc_minutes_mod_5'])
        labels = features.cgm_current.reindex(features.index+pd.Timedelta(minutes=60))
        labels.index = features.index
        features['target_glucose_60m'] = labels
        features['target_time'] = features.index+pd.Timedelta(minutes=60)
        eligible = features.history_eligible & labels.notna() & (features.index>=pd.Timestamp(patient['minimum_forecast_time']))
        selected = features.loc[eligible].drop(columns='history_eligible').copy()
        selected['patient_id'] = pid
        selected['split'] = patient['split']
        selected['a1c_group'] = patient['a1c_group']
        selected['high_endpoint'] = (selected.target_glucose_60m>180).astype(int)
        selected['new_high_endpoint'] = ((selected.cgm_current<=180)&(selected.target_glucose_60m>180)).astype(int)
        # Exploratory five-minute upcrossings, not clinically adjudicated episodes.
        upcross = (features.cgm_current>180)&(features.cgm_current.shift()<=180)
        summary = {'patient_id':pid,'split':patient['split'],'a1c_group':patient['a1c_group'],
                   'eligible_rows':len(selected),'high_endpoint_rows':int(selected.high_endpoint.sum()),
                   'new_high_endpoint_rows':int(selected.new_high_endpoint.sum()),
                   'valid_grid_upcrossings_after_warmup':int(upcross.loc[features.index>=pd.Timestamp(patient['minimum_forecast_time'])].sum())}
        summaries.append(summary)
        all_rows.append(selected.reset_index())
    combined = pd.concat(all_rows,ignore_index=True)
    combined.to_csv(out/'cgmacros_features.csv',index=False)
    counts = pd.DataFrame(summaries)
    counts.to_csv(ROOT/'reports/feature_patient_counts.csv',index=False)
    summary = {'feature_rows':len(combined),'patients':len(counts),'seconds':round(time.perf_counter()-started,2),
               'splits':counts.groupby('split')[['eligible_rows','high_endpoint_rows','new_high_endpoint_rows','valid_grid_upcrossings_after_warmup']].sum().to_dict('index')}
    (ROOT/'reports/feature_preparation.json').write_text(json.dumps(summary,indent=2))
    assert not combined.duplicated(['patient_id','prediction_time']).any()
    assert ((pd.to_datetime(combined.target_time)-pd.to_datetime(combined.prediction_time))==pd.Timedelta(minutes=60)).all()
    assert combined.groupby('patient_id').split.nunique().eq(1).all()
    print(json.dumps(summary,indent=2))

if __name__=='__main__': run()
