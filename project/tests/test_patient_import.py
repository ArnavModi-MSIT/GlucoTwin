"""Synthetic import contracts, prefix causality and explicit transfer mode."""
import copy
import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from glucotwin.patient_import import parse_patient,ImportedReplay


def payload(count=40,phase=0):
    times=pd.date_range(pd.Timestamp('2024-01-01')+pd.Timedelta(minutes=phase),periods=count,freq='5min')
    return dict(csv_text='timestamp,glucose\n'+'\n'.join(f'{t.isoformat()},100' for t in times),
                unit='mg/dL',provenance='synthetic',label='Synthetic import',mode='persistence',profile={})


class ImportTests(unittest.TestCase):
    def test_blank_lines_are_skipped_but_blank_measurements_and_bad_rows_are_not(self):
        original=payload()
        for newline in ['\n','\r\n']:
            text=(newline*2).join(original['csv_text'].splitlines())+newline*3
            parsed=parse_patient({**original,'csv_text':text})
            self.assertEqual(parsed['quality']['input_rows'],40)
            self.assertEqual(parsed['quality']['blank_rows'],0)
        blank={**original,'csv_text':original['csv_text'].replace(',100',',',1)+'\n\n'}
        self.assertEqual(parse_patient(blank)['quality']['blank_rows'],1)
        with self.assertRaises(ValueError):parse_patient({**original,'csv_text':original['csv_text']+'\n,'})

    def test_units_phase_and_missing_slots_preserved(self):
        body=payload(phase=3);lines=body['csv_text'].splitlines();lines.pop(6);lines[8]=lines[8].split(',')[0]+','
        body['csv_text']='\n'.join(lines)
        parsed=parse_patient(body);self.assertEqual(parsed['quality']['gap_slots'],1);self.assertEqual(parsed['quality']['blank_rows'],1)
        self.assertEqual(int(parsed['frame'].GlucoseCGM.isna().sum()),2)
        mmol=payload();mmol['unit']='mmol/L';mmol['csv_text']=mmol['csv_text'].replace(',100',',5.5')
        self.assertAlmostEqual(parse_patient(mmol)['frame'].GlucoseCGM.iloc[0],99.)

    def test_invalid_rows_units_profile_and_duration_rejected(self):
        cases=[]
        for key,value in [('unit','auto'),('provenance','identified'),('profile',{'age':True}),('profile',{'age':16}),('profile',{'sex':'unknown'}),('profile',{'name':'private'}),('csv_text','timestamp,glucose\n2024-02-30T00:00,100')]:
            cases.append({**payload(),key:value})
        duplicate=payload();duplicate['csv_text']+='\n2024-01-01T00:00:00,100';cases.append(duplicate)
        for value in ['nan','inf','-10','0','1001','text']:
            cases.append({**payload(),'csv_text':payload()['csv_text'].replace(',100',','+value,1)})
        cases.append({**payload(),'csv_text':payload()['csv_text'].replace('00:05:00','00:06:00')})
        cases.append(payload(12))
        cases.append({**payload(),'csv_text':'x'*(1024*1024+1)})
        for body in cases:
            with self.subTest(body_keys=list(body)),self.assertRaises(ValueError):parse_patient(body)

    def test_delayed_forecasts_future_edits_and_no_event_or_intervals(self):
        parsed=parse_patient(payload());a=ImportedReplay(parsed);first=a.snapshot()
        altered={**parsed,'frame':parsed['frame'].copy()}
        altered['frame'].loc[altered['frame'].ts>first['data_cutoff'],'GlucoseCGM']=500.
        b=ImportedReplay(altered)
        self.assertEqual(first['forecasts'],b.snapshot()['forecasts'])
        self.assertTrue(all(p['time']<=first['data_cutoff'] for p in first['chart']))
        self.assertEqual(first['forecasts'][0]['prediction'],100.)
        self.assertIsNone(first['event_research']);self.assertNotIn('interval_lower',first['forecasts'][0])
        a.advance(30);self.assertEqual(a.snapshot()['ledger'][0]['outcome'],'Pending')
        a.advance(5);self.assertEqual(a.snapshot()['ledger'][0]['outcome'],'Observed')
        self.assertEqual(a.snapshot()['ledger'][0]['prediction'],100.)
        a.reset();self.assertEqual(a.snapshot()['issue_time'],first['issue_time'])

    def test_missing_current_withholds_and_end_is_idempotent(self):
        body=payload();lines=body['csv_text'].splitlines();lines[13]=lines[13].split(',')[0]+',';body['csv_text']='\n'.join(lines)
        replay=ImportedReplay(parse_patient(body));self.assertIsNone(replay.snapshot()['forecasts'][0]['prediction'])
        for _ in range(10):replay.advance(60)
        count=len(replay.ledger);replay.advance(60);self.assertEqual(len(replay.ledger),count);self.assertTrue(replay.snapshot()['at_end'])

    def test_transfer_requires_profile_phase_warmup_and_trusted_models(self):
        body={**payload(),'mode':'rbg'}
        with self.assertRaises(ValueError):parse_patient(body)
        body['profile']={'age':40,'sex':'F'}
        with self.assertRaises(ValueError):parse_patient(body)
        body={**payload(313,3),'mode':'rbg','profile':{'age':40,'sex':'F'}}
        with self.assertRaises(ValueError):parse_patient(body)
        body={**payload(313),'mode':'rbg','profile':{'age':40,'sex':'F'}};parsed=parse_patient(body)
        with self.assertRaises(ValueError):ImportedReplay(parsed)
        class Model:
            def predict(self,X):return np.full(len(X),120.)
        artifacts={h:dict(model=Model(),features=['cgm_current','age_at_enrollment','sex_f'],sensor_delay_minutes=5,horizon_minutes=h) for h in (30,60)}
        replay=ImportedReplay(parsed,artifacts);first=replay.snapshot()
        self.assertEqual(first['issue_time'],pd.Timestamp('2024-01-02T00:05'))
        self.assertEqual(first['forecasts'][0]['prediction'],120.)
        self.assertTrue(first['imported']);self.assertIn('transfer',first['model_name'])

    def test_identity_tracks_records_profile_and_mode(self):
        body=payload();a=parse_patient(body)['id'];self.assertEqual(a,parse_patient(body)['id'])
        self.assertNotEqual(a,parse_patient({**body,'profile':{'age':45}})['id'])
        self.assertNotEqual(a,parse_patient({**body,'csv_text':body['csv_text'].replace(',100',',110',1)})['id'])
