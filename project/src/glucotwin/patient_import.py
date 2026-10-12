"""Bounded CSV imports and local replay; no training or disk persistence."""
import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime
import numpy as np
import pandas as pd
from glucotwin.patterns import historical_patterns
from glucotwin.rbg_replay import issue_rbg_forecasts,reveal_rbg_outcomes

MAX_BYTES=1024*1024


def parse_patient(body):
    if set(body)-{'csv_text','unit','provenance','label','mode','profile'}:raise ValueError('Unsupported import fields.')
    text=body.get('csv_text')
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_BYTES:
        raise ValueError('Choose a UTF-8 CSV file no larger than 1 MB.')
    unit=body.get('unit')
    if unit not in ('mg/dL','mmol/L'):raise ValueError('Declare mg/dL or mmol/L; units are never inferred.')
    provenance=body.get('provenance')
    if provenance not in ('synthetic','anonymized'):raise ValueError('Declare synthetic or anonymized input data.')
    name=body.get('label','Anonymous import')
    if not isinstance(name,str) or not 1<=len(name.strip())<=60:
        raise ValueError('Use an anonymized label of 1–60 characters.')
    mode=body.get('mode','persistence')
    if mode not in ('persistence','rbg'):raise ValueError('Choose history baseline or exploratory RBG Ridge.')
    profile=body.get('profile',{})
    if not isinstance(profile,dict) or set(profile)-{'age','sex'}:raise ValueError('Only age and recorded sex are accepted in the import profile.')
    age=profile.get('age');sex=profile.get('sex')
    if age is not None and (type(age) not in (int,float) or not math.isfinite(age) or not 18<=age<=100):
        raise ValueError('Enrollment age must be 18–100 years, or omitted.')
    if sex is not None and sex not in ('F','M'):raise ValueError('Recorded sex must be F, M or omitted.')
    if mode=='rbg' and (age is None or sex is None):raise ValueError('Exploratory RBG Ridge requires age and recorded sex.')
    try:
        reader=csv.reader(io.StringIO(text.lstrip('\ufeff')),strict=True)
        if next(reader,None)!=['timestamp','glucose']:raise ValueError('CSV header must be exactly timestamp,glucose.')
        times=[];values=[]
        for row in reader:
            if len(row)!=2:raise ValueError('Each CSV row must contain exactly timestamp and glucose.')
            t,v=(c.strip() for c in row)
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:00)?',t):
                raise ValueError('Use ISO study timestamps with zero seconds and no timezone suffix.')
            try:parsed=datetime.fromisoformat(t)
            except ValueError:raise ValueError('Invalid calendar date in CSV.') from None
            if times and parsed<=times[-1]:raise ValueError('Timestamps must be strictly increasing; duplicate or unsorted rows are rejected.')
            if times and (parsed-times[0]).total_seconds()%300!=0:
                raise ValueError('Readings must share one five-minute sampling phase. Gaps remain missing.')
            if len(v)>16:raise ValueError('Invalid glucose value.')
            try:value=float(v)*(18.0 if unit=='mmol/L' else 1.) if v else np.nan
            except ValueError:raise ValueError('Glucose must be numeric or blank for a missing reading.') from None
            if v and (not math.isfinite(value) or not 0<value<=1000):
                raise ValueError('Glucose must be positive and at most 1000 mg/dL after conversion. Check the declared units.')
            times.append(parsed);values.append(value)
            if len(times)>10000:raise ValueError('Import supports at most 10,000 rows.')
    except csv.Error:raise ValueError('Malformed CSV; use the downloadable template.') from None
    if len(times)<13 or sum(math.isfinite(v) for v in values)<10:
        raise ValueError('Provide at least 13 timestamped rows and ten observed glucose readings.')
    span=(times[-1]-times[0]).total_seconds()/60
    if not 60<=span<=31*24*60:raise ValueError('Import duration must be between one hour and 31 days.')
    if mode=='rbg':
        if times[0].minute%5:raise ValueError('RBG transfer requires readings at minutes 00, 05, 10, etc.; timestamps are not shifted.')
        if span<24*60:raise ValueError('RBG transfer requires at least 24 hours of sensor history.')
    grid=pd.date_range(times[0],times[-1],freq='5min')
    source=pd.Series(values,index=pd.DatetimeIndex(times)).reindex(grid)
    observed=int(source.notna().sum())
    fingerprint=hashlib.sha256(json.dumps(dict(times=[t.isoformat() for t in times],values=[None if not math.isfinite(v) else v for v in values],profile=profile,mode=mode),sort_keys=True).encode()).hexdigest()[:20]
    return dict(id=fingerprint,label=name.strip(),mode=mode,provenance=provenance,
                profile=profile,frame=pd.DataFrame(dict(ts=grid,GlucoseCGM=source.to_numpy())),
                quality=dict(input_rows=len(times),expected_slots=len(grid),observed_samples=observed,
                    blank_rows=sum(not math.isfinite(v) for v in values),gap_slots=len(grid)-len(times),
                    coverage=observed/len(grid),input_unit=unit,output_unit='mg/dL',
                    start=times[0].isoformat(),end=times[-1].isoformat(),sampling_minutes=5,sensor_delay_minutes=5))


class ImportedReplay:
    def __init__(self, parsed, artifacts=None):
        self.parsed=parsed;self.frame=parsed['frame'];self.artifacts=artifacts
        if parsed['mode']=='rbg' and not artifacts:raise ValueError('Prepare the trusted local RBG models before choosing transfer mode.')
        self.clock=pd.date_range(self.frame.ts.min()+pd.Timedelta(minutes=5),self.frame.ts.max()+pd.Timedelta(minutes=5),freq='5min')
        warmup=24*60 if artifacts else 60
        minimum=self.frame.ts.min()+pd.Timedelta(minutes=warmup+5)
        self.patient=dict(patient_id=parsed['id'],split='imported',minimum_forecast_time=minimum,
                          age_at_enrollment=parsed['profile'].get('age'),sex_f=float(parsed['profile'].get('sex')=='F'))
        self.start=min(int(self.clock.searchsorted(minimum)),len(self.clock)-1)
        self.reset()

    def issue(self):
        now=self.clock[self.position];cutoff=now-pd.Timedelta(minutes=5)
        if self.ledger and self.ledger[-1]['issued_at']==now:return
        if self.artifacts:
            rows=issue_rbg_forecasts(self.frame,self.patient,self.artifacts,now)
        else:
            source=self.frame.set_index('ts').GlucoseCGM
            window=source.reindex(pd.date_range(cutoff-pd.Timedelta(minutes=60),cutoff,freq='5min'))
            current=window.iloc[-1];known=np.flatnonzero(window.notna().to_numpy())
            max_gap=int(np.diff(known).max()*5) if len(known)>1 else 60
            eligible=pd.notna(current) and len(known)>=10 and max_gap<=15
            rows=[dict(issued_at=now,horizon=h,target_time=now+pd.Timedelta(minutes=h),available_at=now+pd.Timedelta(minutes=h+5),
                prediction=float(current) if eligible else None,persistence=float(current) if eligible else None,
                latest_glucose=float(current),cgm_count=len(known),model_inputs=[],
                status='Baseline issued' if eligible else 'Insufficient history') for h in (30,60)]
        self.ledger.extend(rows)

    def advance(self,minutes):
        if type(minutes) is not int or minutes not in (5,30,60):raise ValueError('Step must be 5, 30 or 60 minutes')
        end=min(self.position+minutes//5,len(self.clock)-1)
        while self.position<end:self.position+=1;self.issue()

    def reset(self):self.position=self.start;self.ledger=[];self.issue()

    def snapshot(self):
        now=self.clock[self.position];cutoff=now-pd.Timedelta(minutes=5)
        shown=reveal_rbg_outcomes(self.ledger,self.frame,now)
        completed=shown.loc[shown.ridge_error.notna()]
        visible=self.frame.loc[self.frame.ts.between(cutoff-pd.Timedelta(hours=6),cutoff)]
        profile={'Source':self.parsed['provenance'],'Declared age':self.parsed['profile'].get('age','Not supplied'),
                 'Recorded sex':self.parsed['profile'].get('sex','Not supplied')}
        learned=bool(self.artifacts)
        return dict(cohort='imported',synthetic=self.parsed['provenance']=='synthetic',imported=True,patient_id=self.parsed['id'],
            patient_label='Imported · '+self.parsed['label'],issue_time=now,data_cutoff=cutoff,sensor_delay_minutes=5,
            profile=profile,profile_note='User-supplied profile and sensor records. Imported patients are outside all research splits. '+
                ('Age/sex and CGM enter the saved RBG Ridge model; transfer performance is unestablished.' if learned else 'Clinical fields are context only. Persistence repeats the latest available reading; no learned model is applied.'),
            latest=self.ledger[-1]['latest_glucose'],coverage=self.ledger[-1]['cgm_count'],forecasts=self.ledger[-2:],ledger=shown.to_dict('records'),
            chart=[dict(time=t,glucose=v) for t,v in zip(visible.ts,visible.GlucoseCGM)],
            historical_patterns=historical_patterns(self.frame.ts,self.frame.GlucoseCGM,cutoff),
            comparison=dict(evaluated=len(completed),ridge_mae=float(completed.ridge_error.mean()) if len(completed) else None,
                            persistence_mae=float(completed.persistence_error.mean()) if len(completed) else None),
            event_research=None,model_name='Exploratory RBG Ridge transfer' if learned else 'Persistence baseline · no trained model',
            event_model_name=None,uncertainty_note='No validated uncertainty ranges or event scores for imported patients.',
            import_quality=self.parsed['quality'],at_end=self.position==len(self.clock)-1)
