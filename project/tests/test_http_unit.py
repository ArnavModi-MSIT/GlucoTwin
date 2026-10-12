"""HTTP boundary tests use no datasets, saved models or role manifests."""
import sys, unittest, threading, json, urllib.request, urllib.error, hashlib
import http.cookiejar
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import serve_dashboard as web

class HttpUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=web.ThreadingHTTPServer(('127.0.0.1',0),web.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start();cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def post(self,body,path='/api/session'):
        request=urllib.request.Request(self.url+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as response:return response.code,json.load(response)
    def test_non_object_and_invalid_cohort(self):
        for body in [[],None,42,'text',{'cohort':None},{'cohort':[]}]:
            status,value=self.post(body);self.assertEqual(status,400);self.assertIn('error',value)
    def test_feed_receipt_endpoint_is_session_specific_and_rejects_invalid_data(self):
        create=urllib.request.Request(self.url+'/api/session',data=b'{"cohort":"demo","patient_id":"feed"}',headers={'Content-Type':'application/json','X-GlucoTwin-Session':''})
        with urllib.request.urlopen(create) as response:
            token=response.headers['X-GlucoTwin-Session'];before=json.load(response)
        def receive(body):
            return urllib.request.urlopen(urllib.request.Request(self.url+'/api/feed/sample',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-GlucoTwin-Session':token}))
        with receive({'missing':True}) as response:
            after=json.load(response);self.assertEqual(after['sensor_feed']['received'],1)
            self.assertIsNone(after['latest']);self.assertEqual(after['sensor_feed']['missing'],1)
        with self.assertRaises(urllib.error.HTTPError) as error:receive({'missing':'false'})
        self.assertEqual(error.exception.code,400)
        request=urllib.request.Request(self.url+'/api/snapshot',headers={'X-GlucoTwin-Session':token})
        with urllib.request.urlopen(request) as response:self.assertEqual(json.load(response),after)
        self.assertNotEqual(before['issue_time'],after['issue_time'])

    def test_feed_endpoint_cannot_modify_research_or_replay_sessions(self):
        key,before=web.service.create('demo','rise')
        request=urllib.request.Request(self.url+'/api/feed/sample',data=b'{}',headers={'Content-Type':'application/json','X-GlucoTwin-Session':key})
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
        self.assertEqual(error.exception.code,400)
        self.assertEqual(web.clean(web.service.operate(key,'snapshot')),web.clean(before))

    def test_hourly_export_keeps_session_identity_and_returns_csv(self):
        key,snapshot=web.service.create('demo','showcase')
        request=urllib.request.Request(self.url+'/api/export?format=history',headers={'X-GlucoTwin-Session':key})
        with urllib.request.urlopen(request) as response:
            text=response.read().decode()
            self.assertEqual(response.headers['Content-Type'],'text/csv; charset=utf-8')
            self.assertIn('history.csv',response.headers['Content-Disposition'])
            self.assertIn('mean,minimum,maximum',text)
            self.assertIn(snapshot['patient_label'],text)
            self.assertNotIn('prediction',text)
    def test_failed_inference_is_controlled(self):
        with patch.object(web,'catalog',return_value={'P-012':{}}),patch.object(web.service,'create',side_effect=RuntimeError('private path')):
            with self.assertLogs(level='ERROR'):
                status,value=self.post({'cohort':'rbg','patient_id':'P-012'})
        self.assertEqual(status,500);self.assertNotIn('private path',value['error'])
    def test_catalog_missing_data_and_headers(self):
        with patch.object(web,'catalog',side_effect=FileNotFoundError):
            with urllib.request.urlopen(self.url+'/api/catalog') as response:
                value=json.load(response);self.assertEqual(len(value['errors']),2)
                self.assertEqual(response.headers['X-Frame-Options'],'DENY')
                self.assertIn("default-src 'self'",response.headers['Content-Security-Policy'])
    def test_missing_session_and_request_size(self):
        self.assertEqual(self.post({},'/api/advance')[0],400)
        self.assertEqual(self.post({'text':'x'*5000})[0],400)
    def test_health_identifies_workspace_without_loading_records(self):
        with patch.object(web,'catalog',side_effect=AssertionError('Health must not read patient manifests')):
            with urllib.request.urlopen(self.url+'/api/health') as response:
                value=json.load(response)
                self.assertEqual(value,{'app':'GlucoTwin','workspace_id':hashlib.sha256(str(web.ROOT.resolve()).encode()).hexdigest()})
                self.assertEqual(response.headers['Cache-Control'],'no-store')
        request=urllib.request.Request(self.url+'/api/health',headers={'Host':'example.com'})
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
        self.assertEqual(error.exception.code,403)
    def test_patient_labels(self):
        self.assertEqual(web.label('115.0_RBG'),'Patient 115')
        self.assertEqual(web.label('P-012'),'Patient P-012')

    def test_synthetic_session_and_export_boundaries(self):
        client=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        request=urllib.request.Request(self.url+'/api/session',data=b'{"cohort":"demo","patient_id":"rise"}',headers={'Content-Type':'application/json'})
        with client.open(request) as response:first=json.load(response)
        self.assertTrue(first['synthetic'])
        with client.open(self.url+'/api/export?format=json') as response:
            export=json.load(response);self.assertEqual(export,first)
            self.assertEqual(response.headers['Cache-Control'],'no-store')
        with client.open(self.url+'/api/export?format=html') as response:
            self.assertIn(b'SYNTHETIC DEMONSTRATION',response.read())
        with client.open(self.url+'/api/export?format=csv') as response:
            self.assertIn('attachment',response.headers['Content-Disposition'])
            self.assertIn(b'forecast,demo,True',response.read())
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(self.url+'/api/export?format=json')
        self.assertEqual(error.exception.code,400)
    def test_tab_headers_isolate_replay_and_export_despite_shared_cookie(self):
        client=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def create(pid):
            request=urllib.request.Request(self.url+'/api/session',data=json.dumps(dict(cohort='demo',patient_id=pid)).encode(),headers={'Content-Type':'application/json','X-GlucoTwin-Session':''})
            with client.open(request) as response:return response.headers['X-GlucoTwin-Session'],json.load(response)
        first,first_snapshot=create('rise');second,second_snapshot=create('stable')
        request=urllib.request.Request(self.url+'/api/advance',data=b'{"minutes":5}',headers={'Content-Type':'application/json','X-GlucoTwin-Session':first})
        with client.open(request) as response:changed=json.load(response)
        self.assertEqual(changed['patient_label'],first_snapshot['patient_label'])
        with client.open(urllib.request.Request(self.url+'/api/snapshot',headers={'X-GlucoTwin-Session':second})) as response:
            self.assertEqual(json.load(response)['issue_time'],second_snapshot['issue_time'])
        with client.open(urllib.request.Request(self.url+'/api/export?format=json',headers={'X-GlucoTwin-Session':first})) as response:
            self.assertEqual(json.load(response)['patient_label'],first_snapshot['patient_label'])

    def test_refresh_snapshot_restores_identity_and_fixed_ledger_without_cookie(self):
        request=urllib.request.Request(self.url+'/api/session',data=b'{"cohort":"demo","patient_id":"showcase"}',headers={'Content-Type':'application/json','X-GlucoTwin-Session':''})
        with urllib.request.urlopen(request) as response:token=response.headers['X-GlucoTwin-Session']
        advance=urllib.request.Request(self.url+'/api/advance',data=b'{"minutes":30}',headers={'Content-Type':'application/json','X-GlucoTwin-Session':token})
        with urllib.request.urlopen(advance) as response:expected=json.load(response)
        with patch.object(web,'DemoReplay',side_effect=AssertionError('Resume must not rebuild the replay')):
            snapshot=urllib.request.Request(self.url+'/api/snapshot',headers={'X-GlucoTwin-Session':token})
            with urllib.request.urlopen(snapshot) as response:self.assertEqual(json.load(response),expected)
        self.assertEqual(expected['patient_id'],'showcase')

    def test_import_preview_session_error_and_export_scope(self):
        import pandas as pd
        text='timestamp,glucose\n'+'\n'.join(f'{t.isoformat()},100' for t in pd.date_range('2024-01-01',periods=40,freq='5min'))
        body=dict(csv_text=text,unit='mg/dL',provenance='synthetic',mode='persistence',profile={},label='Synthetic upload')
        status,preview=self.post(body,'/api/import/preview');self.assertEqual(status,200);self.assertEqual(preview['quality']['gap_slots'],0)
        status,error=self.post({**body,'unit':'auto'},'/api/import/preview');self.assertEqual(status,400);self.assertIn('Declare',error['error'])
        request=urllib.request.Request(self.url+'/api/import/session',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-GlucoTwin-Session':''})
        with urllib.request.urlopen(request) as response:token=response.headers['X-GlucoTwin-Session'];snapshot=json.load(response)
        self.assertTrue(snapshot['imported']);self.assertIsNone(snapshot['event_research'])
        request=urllib.request.Request(self.url+'/api/export?format=json',headers={'X-GlucoTwin-Session':token})
        with urllib.request.urlopen(request) as response:self.assertTrue(json.load(response)['patient_label'].endswith('Synthetic upload'))
        hostile=urllib.request.Request(self.url+'/api/import/preview',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':'https://example.com'})
        with self.assertRaises(urllib.error.HTTPError) as exc:urllib.request.urlopen(hostile)
        self.assertEqual(exc.exception.code,403)

    def test_duplicate_listener_is_rejected(self):
        with self.assertRaises(OSError):
            web.ThreadingHTTPServer(('127.0.0.1',self.server.server_port),web.Handler)

class SessionUnitTests(unittest.TestCase):
    def test_repeated_switch_and_expiry(self):
        class Replay:
            def __init__(self,*args):pass
            def snapshot(self):return {}
        service=web.Service();key=None
        with patch.object(web,'Replay',Replay),patch.object(web.time,'monotonic',return_value=100.):
            for _ in range(40):key,_=service.create('rbg','synthetic',key)
        self.assertEqual(len(service.sessions),1)
        with patch.object(web.time,'monotonic',return_value=3701.):
            with self.assertRaisesRegex(ValueError,'expired'):service.operate(key,'snapshot')

    def test_exact_idle_expiry_boundary(self):
        class Replay:
            def snapshot(self):return {}
        for elapsed,expired in [(3599.,False),(3600.,True)]:
            service=web.Service();service.sessions['key']=(Replay(),100.)
            with patch.object(web.time,'monotonic',return_value=100.+elapsed):
                if expired:
                    with self.assertRaisesRegex(ValueError,'expired'):service.operate('key','snapshot')
                else:self.assertEqual(service.operate('key','snapshot'),{})
