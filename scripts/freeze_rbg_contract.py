"""Freeze RBG participant roles without model fitting or target-based selection."""
from pathlib import Path
import json,sys,hashlib
import pandas as pd
from sklearn.model_selection import train_test_split
ROOT=Path(__file__).resolve().parents[1]

def freeze():
    bio=pd.read_csv(ROOT/'dataset-verification/diadata-Demographics.csv')
    bio=bio[bio.Database.eq('RBG')].copy()
    audit=json.loads((ROOT/'dataset-verification/rbg-patient-audit.json').read_text())
    assert bio.PtID.is_unique and set(bio.PtID)==set(audit)
    bio['age']=pd.to_numeric(bio.AgeAtEnrollment,errors='raise')
    assert bio.age.between(18,100).all() and bio.Sex.isin(['M','F']).all()
    bio['stratum']=bio.Sex+'_'+bio.age.ge(45).map({False:'under45',True:'45plus'})
    trainval,test=train_test_split(bio,test_size=34,random_state=2026,stratify=bio.stratum)
    train,val=train_test_split(trainval,test_size=34,random_state=2026,stratify=trainval.stratum)
    assignments={pid:role for role,part in [('train',train),('validation',val),('test',test)] for pid in part.PtID}
    rows=[]
    for _,row in bio.sort_values('PtID').iterrows():
        first=pd.Timestamp(audit[row.PtID]['first_time'])
        minimum=max(first,pd.Timestamp('2024-01-01'))+pd.Timedelta(hours=24)
        rows.append({'patient_id':row.PtID,'split':assignments[row.PtID],
                     'age_at_enrollment':float(row.age),'sex_f':int(row.Sex=='F'),
                     'minimum_forecast_time':minimum.isoformat()})
    manifest={'version':'rbg-v0.1','seed':2026,'sensor_delay_minutes':5,'horizons_minutes':[30,60],
              'profile_availability':'enrollment age/sex assumed available at artificial enrollment origin; no labs',
              'participants':rows}
    (ROOT/'configs/rbg_splits.json').write_text(json.dumps(manifest,indent=2))
    summary={'version':'rbg-v0.1','seed':2026,'patients':len(rows),'split_counts':pd.Series(assignments).value_counts().to_dict(),
             'strata_counts':{role:part.stratum.value_counts().to_dict() for role,part in [('train',train),('validation',val),('test',test)]},
             'manifest_sha256':hashlib.sha256(json.dumps(manifest,indent=2).encode()).hexdigest(),
             'status':'roles frozen; no model fit, target support or test predictions evaluated'}
    (ROOT/'reports/rbg_contract_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
if __name__=='__main__':freeze()
