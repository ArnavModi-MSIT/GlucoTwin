"""Read-only source audit. Endpoint counts use supplied interpolated values."""
from pathlib import Path
import hashlib, json, time
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/raw/cgmacros/CGMacros'
OUT = ROOT / 'reports'
OUT.mkdir(exist_ok=True)
started = time.perf_counter()
bio = pd.read_csv(DATA / 'bio.csv')
bio.columns = bio.columns.str.strip()
bio['subject'] = pd.to_numeric(bio['subject'], errors='coerce')
rows, missing, sensor_stats = [], {}, {}
column_patients = {}
hashes = {}
for path in sorted(DATA.glob('CGMacros-*/CGMacros-*.csv')):
    pid = int(path.stem.split('-')[-1])
    hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    frame = pd.read_csv(path)
    frame.columns = frame.columns.str.strip()
    ts = pd.to_datetime(frame['Timestamp'], errors='coerce', format='mixed')
    delta = ts.diff().dt.total_seconds().div(60)
    item = {'patient_id': pid, 'rows': len(frame), 'invalid_timestamps': int(ts.isna().sum()),
            'duplicate_timestamps': int(ts.duplicated().sum()), 'out_of_order': int((delta < 0).sum()),
            'duration_days': (ts.max()-ts.min()).total_seconds()/86400,
            'one_minute_steps': int((delta == 1).sum()), 'gaps_over_one_minute': int((delta > 1).sum()),
            'max_gap_minutes': float(delta.max()), 'meal_rows': int(frame['Meal Type'].notna().sum()),
            'profile_matches': int((bio.subject == pid).sum())}
    for col in frame:
        column_patients.setdefault(col, []).append(pid)
        missing.setdefault(col, [0,0])
        missing[col][0] += int(frame[col].isna().sum())
        missing[col][1] += len(frame)
    valid = frame.assign(Timestamp=ts).dropna(subset=['Timestamp']).drop_duplicates('Timestamp').sort_values('Timestamp').set_index('Timestamp')
    for sensor in ['Dexcom GL', 'Libre GL']:
        glucose = pd.to_numeric(valid[sensor], errors='coerce')
        future = glucose.reindex(glucose.index + pd.Timedelta(minutes=60))
        future.index = glucose.index
        paired = glucose.notna() & future.notna()
        eligible = paired & (glucose <= 180)
        consecutive = glucose.index.to_series().diff().eq(pd.Timedelta(minutes=1))
        onset = consecutive & (glucose > 180) & (glucose.shift() <= 180)
        # Fractionality illustrates interpolation; it does not identify native samples.
        fractional = glucose.notna() & ((glucose-glucose.round()).abs() > 1e-6)
        second_difference = glucose.diff().diff()
        prefix = 'dexcom' if sensor == 'Dexcom GL' else 'libre'
        item.update({f'{prefix}_valid': int(glucose.notna().sum()), f'{prefix}_min': float(glucose.min()),
                     f'{prefix}_max': float(glucose.max()), f'{prefix}_paired_60m': int(paired.sum()),
                     f'{prefix}_high_60m': int((paired & (future > 180)).sum()),
                     f'{prefix}_eligible_60m': int(eligible.sum()),
                     f'{prefix}_low_to_high_endpoint_60m': int((eligible & (future > 180)).sum()),
                     f'{prefix}_observed_grid_upcrossings': int(onset.sum()),
                     f'{prefix}_fractional_values': int(fractional.sum()),
                     f'{prefix}_zero_second_difference': int((second_difference.notna() & (second_difference.abs()<1e-6)).sum()),
                     f'{prefix}_persistence_mae_60m': float((future[paired]-glucose[paired]).abs().mean())})
    both = valid[['Dexcom GL','Libre GL']].apply(pd.to_numeric, errors='coerce').dropna()
    item['paired_device_rows'] = len(both)
    item['device_mae'] = float((both['Dexcom GL']-both['Libre GL']).abs().mean())
    rows.append(item)

patients = pd.DataFrame(rows)
a1c = pd.to_numeric(bio['A1c PDL (Lab)'], errors='coerce')
group = pd.Series(np.select([a1c < 5.7, a1c.between(5.7,6.4), a1c > 6.4], ['below_5.7','5.7_to_6.4','above_6.4'], default='missing'), index=bio.index)
patients['a1c_group'] = patients.patient_id.map(dict(zip(bio.subject, group)))
summary = {'patients':len(patients), 'profile_rows':len(bio), 'duplicate_profile_ids':int(bio.subject.duplicated().sum()),
           'profile_missing_id':int(bio.subject.isna().sum()), 'sensor_without_unique_profile':int((patients.profile_matches!=1).sum()),
           'profile_without_sensor':sorted(set(bio.subject.dropna().astype(int))-set(patients.patient_id)),
           'rows':int(patients.rows.sum()), 'duration_days_min':float(patients.duration_days.min()),
           'duration_days_median':float(patients.duration_days.median()), 'duration_days_max':float(patients.duration_days.max()),
           'invalid_timestamps':int(patients.invalid_timestamps.sum()), 'duplicate_timestamps':int(patients.duplicate_timestamps.sum()),
           'out_of_order_steps':int(patients.out_of_order.sum()), 'gaps_over_one_minute':int(patients.gaps_over_one_minute.sum()),
           'a1c_group_counts':group.value_counts().to_dict(), 'a1c_min':float(a1c.min()),'a1c_max':float(a1c.max()),
           'clinical_missing':{c:int(bio[c].isna().sum()) for c in bio.columns},
           'clinical_numeric_invalid':{c:int(pd.to_numeric(bio[c], errors='coerce').isna().sum()) for c in ['Age','BMI','Body weight','Height','A1c PDL (Lab)','Fasting GLU - PDL (Lab)','Insulin','Triglycerides','Cholesterol','HDL','Non HDL','LDL (Cal)','VLDL (Cal)','Cho/HDL Ratio']},
           'clinical_dictionary_error_counts':{'LDL_800':int((pd.to_numeric(bio['LDL (Cal)'],errors='coerce')==800).sum()),'VLDL_400':int((pd.to_numeric(bio['VLDL (Cal)'],errors='coerce')==400).sum()),'cholesterol_HDL_ratio_400':int((pd.to_numeric(bio['Cho/HDL Ratio'],errors='coerce')==400).sum())},
           'column_patient_counts':{c:len(ids) for c,ids in column_patients.items()},
           'sensor_missing':{c:{'missing_within_present_files':n,'rows_in_present_files':d,'absent_column_rows':int(patients.rows.sum())-d,'percent_unavailable_all_rows':round(100*(n+int(patients.rows.sum())-d)/int(patients.rows.sum()),3)} for c,(n,d) in missing.items()},
           'event_counts':{}, 'group_events':[], 'audit_seconds':round(time.perf_counter()-started,2),
           'rss_mib_at_end':None}
for prefix in ['dexcom','libre']:
    summary['event_counts'][prefix] = {key:int(patients[f'{prefix}_{key}'].sum()) for key in ['valid','paired_60m','high_60m','eligible_60m','low_to_high_endpoint_60m','observed_grid_upcrossings','fractional_values']}
    summary['event_counts'][prefix]['patients_with_low_to_high_endpoint'] = int((patients[f'{prefix}_low_to_high_endpoint_60m'] > 0).sum())
    summary['event_counts'][prefix]['persistence_mae_60m_mg_dl'] = float(np.average(patients[f'{prefix}_persistence_mae_60m'].fillna(0),weights=patients[f'{prefix}_paired_60m']))
    summary['event_counts'][prefix]['high_endpoint_percent'] = round(100*summary['event_counts'][prefix]['high_60m']/summary['event_counts'][prefix]['paired_60m'],3)
    summary['event_counts'][prefix]['low_to_high_percent_of_eligible'] = round(100*summary['event_counts'][prefix]['low_to_high_endpoint_60m']/summary['event_counts'][prefix]['eligible_60m'],3)
summary['device_mae_mg_dl'] = float(np.average(patients.device_mae.fillna(0),weights=patients.paired_device_rows))
summary['largest_timestamp_gap_minutes'] = float(patients.max_gap_minutes.max())
for name, sub in patients.groupby('a1c_group'):
    summary['group_events'].append({'a1c_group':name,'patients':len(sub),'dexcom_pairs':int(sub.dexcom_paired_60m.sum()),'dexcom_high_60m':int(sub.dexcom_high_60m.sum()),'dexcom_low_to_high':int(sub.dexcom_low_to_high_endpoint_60m.sum())})
patients.to_csv(OUT/'cgmacros_patient_audit.csv',index=False)
(OUT/'cgmacros_audit.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
hashes['data/raw/cgmacros/CGMacros/bio.csv'] = hashlib.sha256((DATA/'bio.csv').read_bytes()).hexdigest()
(OUT/'cgmacros_file_hashes.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
