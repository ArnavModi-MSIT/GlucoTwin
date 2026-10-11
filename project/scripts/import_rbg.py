"""Import the versioned DiaData RBG cohort from local archives in bounded memory."""
from pathlib import Path
import argparse,hashlib,json,shutil,time,zipfile
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
SUBSET_SHA256='577f60ee31d77de367846c2a23e59e73d50985b6cd7c9c1c287fb7b4d5f6bc35'
DEMOGRAPHICS_MD5='bfdad21f65f60d79eb6bf3d293916954'
CSV_NAME='SDBIII_5min_sampling_raw.csv'

def digest(path,algorithm='sha256'):
    result=hashlib.new(algorithm)
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):result.update(block)
    return result.hexdigest()

def inner_archive(path,folder):
    with zipfile.ZipFile(path) as archive:
        if CSV_NAME in archive.namelist():return path
        member='raw/SDBIII_5min_sampling_raw.zip'
        info=archive.getinfo(member)
        target=folder/'SDBIII_5min_sampling_raw.zip'
        if target.resolve()==path.resolve():raise ValueError('Invalid archive layout')
        partial=target.with_suffix('.zip.partial')
        with archive.open(info) as source,partial.open('wb') as dest:
            shutil.copyfileobj(source,dest,1024*1024)
        partial.replace(target)
    return target

def extract_subset(archive_path,target):
    target=Path(target);partial=target.with_suffix('.csv.partial');rows=0
    with zipfile.ZipFile(archive_path) as archive,archive.open(CSV_NAME) as source,partial.open('wb') as dest:
        header=source.readline()
        if header.strip()!=b'ts,PtID,GlucoseCGM,Age,Sex,Hba1c,DiagAge,Race,HeightCm,WeightKg,Database':raise ValueError('Unexpected source CSV schema')
        dest.write(header)
        for line in source:
            if line.rstrip(b'\r\n').endswith(b',RBG'):dest.write(line);rows+=1
    # Reading the ZIP member to EOF verifies CRC; canonical subset hash is checked by run.
    return partial,rows

def audit_subset(path,chunksize=250000):
    patients={}
    with pd.read_csv(path,usecols=['ts','PtID','GlucoseCGM'],dtype={'PtID':'str'},chunksize=chunksize) as chunks:
        for chunk in chunks:
            chunk.ts=pd.to_datetime(chunk.ts,errors='raise')
            if chunk.ts.isna().any() or chunk.PtID.isna().any() or not chunk.PtID.str.endswith('_RBG').all():raise ValueError('Invalid RBG keys/timestamps')
            for pid,g in chunk.groupby('PtID',sort=False):
                a=patients.setdefault(pid,{'rows':0,'glucose_rows':0,'first_time':g.ts.iloc[0].isoformat(),'last_time':None})
                if not g.ts.diff().dropna().eq(pd.Timedelta(minutes=5)).all():raise ValueError('Non-5-minute grid or duplicate timestamp')
                if a['last_time'] is not None and g.ts.iloc[0]-pd.Timestamp(a['last_time'])!=pd.Timedelta(minutes=5):raise ValueError('Invalid chunk-boundary grid')
                a['rows']+=len(g);a['glucose_rows']+=int(g.GlucoseCGM.notna().sum());a['last_time']=g.ts.iloc[-1].isoformat()
    return patients

def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True,help='Local raw.zip or SDBIII_5min_sampling_raw.zip')
    parser.add_argument('--demographics',type=Path,required=True,help='Original DiaData v3 Demographics.csv')
    args=parser.parse_args();started=time.monotonic()
    if digest(args.demographics,'md5')!=DEMOGRAPHICS_MD5:raise ValueError('Demographics does not match the verified v3 release')
    folder=ROOT/'data/raw/diadata';folder.mkdir(parents=True,exist_ok=True)
    target=folder/'RBG_raw.csv'
    if target.exists():
        if digest(target)!=SUBSET_SHA256:raise ValueError('Existing RBG subset differs; preserve it and resolve the source mismatch before proceeding')
        print('Existing canonical subset verified; extraction skipped.',flush=True)
    else:
        archive=inner_archive(args.archive.resolve(),folder)
        partial,count=extract_subset(archive,target)
        if count!=18126280 or digest(partial)!=SUBSET_SHA256:raise ValueError('Subset does not match the frozen source; partial output retained for inspection')
        partial.replace(target)
    patients=audit_subset(target)
    bio=pd.read_csv(args.demographics);bio=bio[bio.Database.eq('RBG')]
    if not bio.PtID.is_unique or set(bio.PtID)!=set(patients) or len(patients)!=226:raise ValueError('Clinical and sensor IDs do not match the frozen cohort')
    metadata=folder/'Demographics.csv'
    if metadata.resolve()!=args.demographics.resolve():shutil.copyfile(args.demographics,metadata)
    (folder/'rbg_import_audit.json').write_text(json.dumps(patients,indent=2),encoding='utf-8')
    summary={'source':'DiaData v3 record 17285631, raw SDBIII RBG','patients':len(patients),'rows':sum(v['rows'] for v in patients.values()),'glucose_rows':sum(v['glucose_rows'] for v in patients.values()),'subset_sha256':SUBSET_SHA256,'demographics_md5':DEMOGRAPHICS_MD5,'grid_check':'unique strictly increasing five-minute grid, including chunk boundaries','seconds':round(time.monotonic()-started,1)}
    (ROOT/'reports/rbg_import.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':run()
