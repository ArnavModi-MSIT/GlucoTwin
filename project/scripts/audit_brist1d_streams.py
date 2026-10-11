"""Audit downloaded processed streams without interpolation, training or invented entry times."""
from pathlib import Path
import argparse,json,hashlib
import pandas as pd
import numpy as np


def audit(frame):
    required={'timestamp','device','bg','insulin','carbs','hr'}
    if not required.issubset(frame):raise ValueError('Unexpected source schema')
    data=frame.copy();data['timestamp']=pd.to_datetime(data.timestamp,errors='raise')
    result={'rows':len(data),'repeated_timestamp_rows_across_devices':int(data.timestamp.duplicated().sum()),'channels':{}}
    streams={}
    for channel in ['bg','insulin','carbs','hr']:
        rows=data.loc[data[channel].notna(),['timestamp','device',channel]].copy()
        rows[channel]=pd.to_numeric(rows[channel],errors='raise')
        grouped=rows.groupby(['timestamp','device'])[channel]
        conflicts=grouped.nunique().gt(1)
        cross=rows.groupby('timestamp')[channel].nunique().gt(1)
        # Identical duplicate observations are reconciled; ambiguous values excluded.
        unique=rows.groupby('timestamp')[channel].agg(['first','nunique'])
        stream=unique.loc[unique['nunique']==1,'first'].sort_index()
        gaps=stream.index.to_series().diff().dt.total_seconds().div(60).dropna()
        result['channels'][channel]={'observed_rows':len(rows),'distinct_timestamps':len(unique),
            'same_device_conflicting_timestamp_keys':int(conflicts.sum()),
            'conflicting_timestamp_values':int(cross.sum()),'retained_unambiguous_timestamps':len(stream),
            'positive_rows':int((rows[channel]>0).sum()),'zero_rows':int((rows[channel]==0).sum()),
            'median_gap_minutes':float(gaps.median()) if len(gaps) else None,
            'most_common_gap_minutes':float(gaps.mode().iloc[0]) if len(gaps) else None,
            'gaps_over15_minutes':int((gaps>15).sum()),
            'device_sources':sorted(rows.device.unique().tolist())}
        streams[channel]=stream
    glucose=streams['bg']
    overlap={}
    for channel,tolerance in [('insulin',5),('hr',5)]:
        source=streams[channel];positions=source.index.searchsorted(glucose.index,side='right')-1
        valid=positions>=0
        if len(source):
            age=(glucose.index-source.index[np.maximum(positions,0)]).total_seconds()/60
            valid &= age<=tolerance
        else:valid[:]=False
        overlap[channel]={'glucose_timestamps':len(glucose),'with_past_observation_within_minutes':tolerance,
                          'matched':int(valid.sum()),'fraction':float(valid.mean()) if len(valid) else None}
    result['past_observation_overlap']=overlap
    result['interpretation']={'availability':'Entry/upload timestamps not in schema; retrospective event timestamps do not prove prospective availability.',
        'grid':'No interpolation or resampling; measured cadence reported per channel.',
        'food_missingness':'Missing carbohydrate entries remain unreported, not zero.',
        'glucose_units':'source mmol/L; conversion if needed is 18.0182 mg/dL per mmol/L',
        'conflict_policy':'Exclude conflicting timestamps from descriptive overlap; no prediction inputs created.'}
    return result


def run(folder,output):
    files=sorted(Path(folder).glob('P*.csv'))
    if not files:raise ValueError('No participant CSVs downloaded')
    private=[{'file':p.name,'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),**audit(pd.read_csv(p))} for p in files]
    private_path=Path('data/processed/brist1d_stream_audit_private.json');private_path.parent.mkdir(parents=True,exist_ok=True)
    private_path.write_text(json.dumps(private,indent=2),encoding='utf-8')
    summary={'scope':'downloaded participant pilot only' if len(files)==1 else 'downloaded processed participants only',
             'participants_audited':len(files),'no_models_fitted':True,'reports':[{k:v for k,v in r.items() if k not in ['file']} for r in private]}
    Path(output).write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',default='data/raw/brist1d_pilot');parser.add_argument('--output',default='reports/brist1d_stream_audit.json')
    args=parser.parse_args();run(args.folder,args.output)
