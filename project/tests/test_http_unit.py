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
