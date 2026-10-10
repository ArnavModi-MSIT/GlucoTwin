"""Exercise a running local dashboard using validation patients only.

Writes aggregate diagnostics, never patient-level records. Does not train or
score reserved-test patients. Run after starting serve_dashboard.py.
"""
import argparse,json,time,urllib.request,urllib.error,http.cookiejar
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

def run(url):
    latencies=[];requests=0
    def client():return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(c,path,body=None,expected=200,headers=None):
        nonlocal requests
        h={'Content-Type':'application/json'} if body is not None else {}
        h.update(headers or {})
        req=urllib.request.Request(url+path,data=json.dumps(body).encode() if body is not None else None,headers=h)
        start=time.perf_counter()
        try:response=c.open(req,timeout=30)
        except urllib.error.HTTPError as error:response=error
        with response:
            assert response.status==expected,(path,response.status,expected)
            value=json.load(response)
        latencies.append((time.perf_counter()-start)*1000);requests+=1
        return value
    def verify(s):
        now=datetime.fromisoformat(s['issue_time']);cutoff=datetime.fromisoformat(s['data_cutoff'])
        assert all(datetime.fromisoformat(p['time'])<=cutoff for p in s['chart'])
        for row in s['ledger']:
            if datetime.fromisoformat(row['available_at'])>now:
                assert row['outcome']=='Pending' and row['actual'] is None
            if row['actual'] is not None and row['prediction'] is not None:
                assert abs(row['ridge_error']-abs(row['actual']-row['prediction']))<1e-8
        completed=[r for r in s['ledger'] if r['ridge_error'] is not None]
        assert len(completed)==s['comparison']['evaluated']
        if completed:
            assert abs(np.mean([r['ridge_error'] for r in completed])-s['comparison']['ridge_mae'])<1e-8
        assert not {'risk_probability','alert','alerts'} & s.keys()
    catalog=call(client(),'/api/catalog');counts={}
    c=client()
    for cohort,patients in catalog['cohorts'].items():
        counts[cohort]=len(patients)
        for patient in patients:
            initial=call(c,'/api/session',{'cohort':cohort,'patient_id':patient['id']});verify(initial)
            s=initial
            for minutes in (30,5,60):
                old=[r['prediction'] for r in s['ledger']]
                s=call(c,'/api/advance',{'minutes':minutes});verify(s)
                assert [r['prediction'] for r in s['ledger'][:len(old)]]==old
            reset=call(c,'/api/reset',{});verify(reset)
            assert reset['issue_time']==initial['issue_time'] and len(reset['ledger'])==len(initial['ledger'])
    for body in ([],{}, {'cohort':'unknown'}, {'cohort':None}, {'cohort':[]}):call(c,'/api/session',body,400)
    call(c,'/api/advance',{'minutes':7},400)
    call(c,'/api/reset',{},403,{'Origin':'https://example.com'})
    call(c,'/api/reset',{},403,{'Host':'example.com'})
    for cohort in counts:
        manifest=json.loads((ROOT/'configs'/f'{cohort}_splits.json').read_text())
        reserved=next(p['patient_id'] for p in manifest['participants'] if p['split']=='test')
        call(c,'/api/session',{'cohort':cohort,'patient_id':reserved},400)
    def parallel_worker(minutes):
        c=client();patient=catalog['cohorts']['rbg'][0]
        initial=call(c,'/api/session',{'cohort':'rbg','patient_id':patient['id']})
        s=call(c,'/api/advance',{'minutes':minutes});verify(s)
        assert (datetime.fromisoformat(s['issue_time'])-datetime.fromisoformat(initial['issue_time'])).total_seconds()==minutes*60
        assert call(c,'/api/snapshot')['issue_time']==s['issue_time']
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(parallel_worker,[5,30,60,5]))
    c=client();p=catalog['cohorts']['rbg'][0]
    call(c,'/api/session',{'cohort':'rbg','patient_id':p['id']})
    for _ in range(100):verify(call(c,'/api/advance',{'minutes':5}))
    report={'scope':'local validation replay; no model refit or reserved-test scoring',
            'patient_counts':counts,'requests':requests,'checks':'chart cutoff, delayed reveal, immutable forecasts, error arithmetic, reset, invalid inputs, origin/host guards, test rejection, four concurrent clients, 100-step replay',
            'request_latency_ms':dict(zip(['p50','p95','p99','max'],[round(v,2) for v in [*np.quantile(latencies,[.5,.95,.99]),max(latencies)]]))}
    (ROOT/'reports/dashboard_checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8000');args=parser.parse_args()
    if args.url not in ('http://127.0.0.1:8000','http://localhost:8000'):parser.error('Only the local dashboard is supported')
    run(args.url)
