"""Local HTML dashboard service. Model inference remains entirely in Python."""
from pathlib import Path
from http.server import ThreadingHTTPServer as _ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from functools import lru_cache
import argparse,json,sys,uuid,time,threading,math,logging,hashlib,socket,importlib.metadata
import numpy as np,pandas as pd,joblib
from urllib.parse import urlsplit,parse_qs
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from glucotwin.features import profile_features
from glucotwin.replay import issue_forecast,reveal_outcomes
from glucotwin.rbg_replay import issue_rbg_forecasts,reveal_rbg_outcomes
from glucotwin.artifacts import validate_replay_artifact
from glucotwin.event_replay import load_event_artifact,issue_event,reveal_events
from glucotwin.demo import DemoReplay,SCENARIOS
from glucotwin.reporting import csv_report,html_report
from glucotwin.patterns import historical_patterns
from glucotwin.uncertainty import load_intervals,attach_interval

class ThreadingHTTPServer(_ThreadingHTTPServer):
    # Windows SO_REUSEADDR permits overlapping listeners. Exclusive binding
    # makes near-simultaneous launcher clicks reuse one server safely.
    allow_reuse_address=not hasattr(socket,'SO_EXCLUSIVEADDRUSE')
    def server_bind(self):
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()

@lru_cache(maxsize=2)
def catalog(cohort):
    if cohort not in ['rbg','cgmacros']:raise ValueError('Unknown cohort')
    path='rbg_splits.json' if cohort=='rbg' else 'cgmacros_splits.json'
    return {p['patient_id']:p for p in json.loads((ROOT/'configs'/path).read_text())['participants'] if p['split']=='validation'}

@lru_cache(maxsize=2)
def models(cohort):
    if cohort=='rbg':
        selection=json.loads((ROOT/'configs/rbg_model_selection.json').read_text())
        if any(selection['horizons'][str(h)].get('replay_selected',selection['horizons'][str(h)]['selected'])!='ridge_cgm_profile' for h in (30,60)):
            raise ValueError('Unsupported replay model selection')
        return {h:validate_replay_artifact(joblib.load(ROOT/f'artifacts/rbg_ridge_cgm_profile_{h}.joblib'),cohort,h,profile_fusion=True) for h in (30,60)}
    if cohort!='cgmacros':raise ValueError('Unknown cohort')
    selection=json.loads((ROOT/'configs/model_selection.json').read_text())
    if selection.get('artifact')!='artifacts/ridge_cgm_clinical_hr.joblib' or selection.get('horizon_minutes')!=60:
        raise ValueError('Unsupported replay model selection')
    return {60:validate_replay_artifact(joblib.load(ROOT/'artifacts/ridge_cgm_clinical_hr.joblib'),cohort,60)}

@lru_cache(maxsize=4)
def records(cohort,pid):
    patient=catalog(cohort)[pid]
    if cohort=='rbg':
        with np.load(ROOT/f'data/processed/rbg/replay/{pid}.npz') as d:frame=pd.DataFrame({'ts':pd.to_datetime(d['times']),'GlucoseCGM':d['glucose']})
        return frame,{'age':patient['age_at_enrollment'],'sex':'F' if patient['sex_f'] else 'M'}
    base=ROOT/'data/raw/cgmacros/CGMacros'
    frame=pd.read_csv(base/f'CGMacros-{pid:03d}/CGMacros-{pid:03d}.csv');frame.columns=frame.columns.str.strip();frame.Timestamp=pd.to_datetime(frame.Timestamp)
    bio=pd.read_csv(base/'bio.csv');bio.columns=bio.columns.str.strip()
    return frame,profile_features(bio.set_index('subject').loc[pid])

def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,(pd.Timestamp,np.datetime64)):return pd.Timestamp(value).isoformat()
    if isinstance(value,np.generic):return clean(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value

class Replay:
    def __init__(self,cohort,pid):
        self.cohort=cohort;self.patient=catalog(cohort)[pid];self.frame,self.profile=records(cohort,pid);self.models=models(cohort)
        self.intervals,self.interval_note=load_intervals(ROOT,cohort,self.patient['patient_id'])
        if cohort=='rbg':self.clock=pd.date_range(self.frame.ts.min()+pd.Timedelta(minutes=5),self.frame.ts.max()+pd.Timedelta(minutes=5),freq='5min')
        else:
            minutes=self.frame.Timestamp.to_numpy(dtype='datetime64[ns]').astype('int64')//60_000_000_000
            start=self.frame.Timestamp.loc[minutes%5==self.patient['phase_utc_minutes_mod_5']].min()
            self.clock=pd.date_range(start,self.frame.Timestamp.max(),freq='5min')
        self.start=min(int(self.clock.searchsorted(pd.Timestamp(self.patient['minimum_forecast_time']))),len(self.clock)-1)
        self.event_artifact=None;self.event_metadata=None;self.event_ledger=[];self.event_error=None
        if cohort=='cgmacros':
            try:self.event_artifact,self.event_metadata=load_event_artifact(ROOT,self.patient)
            except (FileNotFoundError,ImportError,importlib.metadata.PackageNotFoundError):
                self.event_error='Optional event study preparation or pinned XGBoost dependency is missing. See event replay setup.'
            except ValueError:
                self.event_error='Event study verification failed; this research model is unavailable.'
        self.position=self.start;self.ledger=[];self.issue()
    def issue(self):
        now=self.clock[self.position]
        if self.ledger and self.ledger[-1]['issued_at']==now:return
        if self.cohort=='rbg':rows=issue_rbg_forecasts(self.frame,self.patient,self.models,now)
        else:
            row=issue_forecast(self.frame,self.profile,self.patient,self.models[60],now)
            row.update(horizon=60,available_at=row['target_time'],persistence=row.get('current') if row['prediction'] is not None else None)
            rows=[row]
        for row in rows:attach_interval(row,self.intervals.get(row['horizon']))
        self.ledger.extend(rows)
        if self.event_artifact is not None:
            self.event_ledger.append(issue_event(self.frame,self.profile,self.patient,self.event_artifact,now,self.event_ledger))
    def advance(self,minutes):
        if type(minutes) is not int or minutes not in [5,30,60]:raise ValueError('Step must be 5, 30 or 60 minutes')
        end=min(self.position+minutes//5,len(self.clock)-1)
        while self.position<end:
            self.position+=1;self.issue()
    def reset(self):self.position=self.start;self.ledger=[];self.event_ledger=[];self.issue()
    def snapshot(self):
        now=self.clock[self.position];rbg=self.cohort=='rbg';cutoff=now-pd.Timedelta(minutes=5) if rbg else now
        count=len(self.models);current=self.ledger[-count:]
        if rbg:
            shown=reveal_rbg_outcomes(self.ledger,self.frame,now)
            visible=self.frame.loc[self.frame.ts.between(cutoff-pd.Timedelta(hours=6),cutoff)]
            chart=[{'time':t,'glucose':v} for t,v in zip(visible.ts,visible.GlucoseCGM)]
            profile={'Age':f"{self.profile['age']:.0f} years",'Recorded sex':self.profile['sex']}
            latest=current[0]['latest_glucose'];coverage=current[0]['cgm_count']
            note='Enrollment age and recorded sex feed the model together with CGM history. Availability is assumed. Their inclusion added essentially no accuracy gain; unverified labs are excluded.'
        else:
            shown=reveal_outcomes(self.ledger,self.frame,now).rename(columns={'absolute_error':'ridge_error'})
            shown['persistence_error']=[abs(a-p) if pd.notna(a) and p is not None else np.nan for a,p in zip(shown.actual,shown.persistence)]
            visible=self.frame.loc[self.frame.Timestamp.between(cutoff-pd.Timedelta(hours=6),cutoff)]
            chart=[{'time':t,'glucose':v} for t,v in zip(visible.Timestamp,visible['Dexcom GL'])]
            p=self.profile;profile={'Age':f"{p['age']:.0f} years",'Recorded sex':'F' if p['gender_f'] else 'M','BMI':f"{p['bmi']:.1f}",'HbA1c':f"{p['hba1c_pct']:.1f}%",'Fasting glucose':f"{p['fasting_glucose']:.0f} mg/dL"}
            latest=current[0].get('current');coverage=current[0].get('cgm_count',0)
            note='Historical profile and heart rate feed the fused Ridge model. Baseline availability is assumed; samples are reconstructed.'
        completed=shown.loc[shown.ridge_error.notna()]
        patterns=historical_patterns(self.frame.ts if rbg else self.frame.Timestamp,
                                     self.frame.GlucoseCGM if rbg else self.frame['Dexcom GL'],cutoff)
        comparison={'evaluated':len(completed),'ridge_mae':float(completed.ridge_error.mean()) if len(completed) else None,'persistence_mae':float(completed.persistence_error.mean()) if len(completed) else None}
        event=None
        if not rbg:
            event={'available':self.event_artifact is not None,'error':self.event_error,'metadata':self.event_metadata,
                   'current':self.event_ledger[-1] if self.event_ledger else None,
                   'ledger':reveal_events(self.event_ledger,self.frame,self.patient,now) if self.event_artifact is not None else [],
                   'probability_display_approved':False,'operational_alerts_approved':False}
        return clean({'cohort':self.cohort,'synthetic':False,'model_name':'Profile-fused Ridge · RBG' if rbg else 'Clinical + CGM + HR Ridge · CGMacros','event_model_name':None if rbg else 'Fused XGBoost · cgmacros-onset-gpu-v2','patient_label':label(self.patient['patient_id']),'issue_time':now,'data_cutoff':cutoff,'sensor_delay_minutes':5 if rbg else 0,'profile':profile,'profile_note':note,'latest':latest,'coverage':coverage,'forecasts':current,'chart':chart,'historical_patterns':patterns,'ledger':shown.to_dict('records'),'comparison':comparison,'event_research':event,'uncertainty_note':self.interval_note,'at_end':self.position==len(self.clock)-1})

def label(pid):
    value=str(pid).removesuffix('_RBG')
    try:value=str(int(float(value)))
    except (ValueError,OverflowError):pass
    return 'Patient '+value

class Service:
    def __init__(self):self.sessions={};self.lock=threading.RLock()
    def create(self,cohort,pid,previous_key=None):
        replay=DemoReplay(cohort,pid) if cohort=='demo' else Replay(cohort,pid);key=uuid.uuid4().hex
        with self.lock:
            now=time.monotonic();self.sessions={k:v for k,v in self.sessions.items() if now-v[1]<3600}
            self.sessions.pop(previous_key,None)
            if len(self.sessions)>=32:raise ValueError('Too many active replay sessions')
            self.sessions[key]=(replay,now)
        return key,replay.snapshot()
    def operate(self,key,action,minutes=None):
        with self.lock:
            if key not in self.sessions or time.monotonic()-self.sessions[key][1]>=3600:raise ValueError('Session expired; select a patient again')
            replay,_=self.sessions[key]
            if action=='advance':replay.advance(minutes)
            elif action=='reset':replay.reset()
            self.sessions[key]=(replay,time.monotonic());return replay.snapshot()

service=Service()
class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)
    def log_message(self,*args):pass
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        super().end_headers()
    def local_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
    def respond(self,status,value,cookie=None):
        data=json.dumps(clean(value),allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store')
        if cookie:
            self.send_header('Set-Cookie',f'glucotwin_session={cookie}; HttpOnly; SameSite=Strict; Path=/')
            self.send_header('X-GlucoTwin-Session',cookie)
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def session_key(self):
        # An explicit empty header creates a fresh tab session. Cookie-only
        # clients retain the original API behavior for compatibility.
        if 'X-GlucoTwin-Session' in self.headers:return self.headers['X-GlucoTwin-Session']
        cookie=SimpleCookie(self.headers.get('Cookie',''))
        return cookie['glucotwin_session'].value if 'glucotwin_session' in cookie else ''
    def do_GET(self):
        if not self.local_host():return self.respond(403,{'error':'Local host required'})
        if self.path=='/api/health':
            return self.respond(200,{'app':'GlucoTwin','workspace_id':hashlib.sha256(str(ROOT.resolve()).encode()).hexdigest()})
        if self.path=='/api/catalog':
            cohorts={'demo':[{'id':pid,'label':name} for pid,name in SCENARIOS.items()]};errors={}
            for cohort in ['rbg','cgmacros']:
                try:
                    models(cohort)
                    cohorts[cohort]=[{'id':pid,'label':label(pid)} for pid in catalog(cohort)]
                except (FileNotFoundError,ValueError,ImportError,KeyError):errors[cohort]='Local dataset/model preparation required. Synthetic demo is available.'
            return self.respond(200,{'cohorts':cohorts,'errors':errors})
        if self.path=='/api/snapshot':return self.action('snapshot',{})
        if urlsplit(self.path).path=='/api/export':
            format_=parse_qs(urlsplit(self.path).query).get('format',['json'])[0]
            if format_ not in ('json','csv','html'):return self.respond(400,{'error':'Use json, csv or html'})
            try:
                key=self.session_key()
                snapshot=clean(service.operate(key,'snapshot'))
                data=(json.dumps(snapshot,indent=2,allow_nan=False) if format_=='json' else csv_report(snapshot) if format_=='csv' else html_report(snapshot)).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type',{'json':'application/json','csv':'text/csv; charset=utf-8','html':'text/html; charset=utf-8'}[format_])
                self.send_header('Content-Disposition',f'{"inline" if format_=="html" else "attachment"}; filename="glucotwin-{snapshot["cohort"]}-session.{format_}"')
                self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)))
                self.end_headers();self.wfile.write(data)
            except (ValueError,KeyError):return self.respond(400,{'error':'Session expired; select a patient again'})
            return
        files={'/':'index.html','/style.css':'style.css','/app.js':'app.js','/care.js':'care.js'}
        if self.path not in files:return self.respond(404,{'error':'Not found'})
        path=ROOT/'web'/files[self.path];data=path.read_bytes();self.send_response(200)
        self.send_header('Content-Type',{'html':'text/html; charset=utf-8','css':'text/css','js':'text/javascript'}[path.suffix[1:]])
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_POST(self):
        if not self.local_host():return self.respond(403,{'error':'Local host required'})
        origin=self.headers.get('Origin')
        if origin and origin!=f'http://{self.headers.get("Host")}':return self.respond(403,{'error':'Cross-origin request denied'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.respond(400,{'error':'Expected JSON'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=4096:
                # Drain small rejected bodies so closing the socket does not
                # discard the JSON error response on Windows. Never parse them.
                if 0<length<=65536:self.rfile.read(length)
                raise ValueError('Invalid request size')
            raw=self.rfile.read(length)
            if len(raw)!=length:raise ValueError('Incomplete request')
            body=json.loads(raw)
            if not isinstance(body,dict):raise ValueError('Expected JSON object')
            action={'/api/session':'create','/api/advance':'advance','/api/reset':'reset'}.get(self.path)
            if not action:return self.respond(404,{'error':'Not found'})
            self.action(action,body)
        except (ValueError,TypeError,TimeoutError):self.respond(400,{'error':'Invalid request'})
    def action(self,action,body):
        try:
            if action=='create':
                cohort=body.get('cohort');pid=body.get('patient_id')
                if cohort not in ('rbg','cgmacros','demo'):raise ValueError('Unknown cohort')
                if cohort=='cgmacros':pid=int(pid)
                if pid not in (SCENARIOS if cohort=='demo' else catalog(cohort)):raise ValueError('Patient unavailable for replay')
                previous=self.session_key() or None
                key,snapshot=service.create(cohort,pid,previous);return self.respond(200,snapshot,key)
            key=self.session_key()
            self.respond(200,service.operate(key,action,body.get('minutes')))
        except FileNotFoundError:self.respond(400,{'error':'Prepare local data and saved models first. See README.'})
        except (ValueError,KeyError,TypeError) as exc:self.respond(400,{'error':str(exc)})
        except Exception:
            logging.exception('Replay request failed')
            self.respond(500,{'error':'Replay failed; check the local server log'})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8000);args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'GlucoTwin: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
