import unittest,sys,json,threading,urllib.request,urllib.error,http.cookiejar
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import serve_dashboard as web

class WebReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=web.ThreadingHTTPServer(('127.0.0.1',0),web.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def client(self):return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(self,client,path,data=None):
        req=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'} if data is not None else {})
        with client.open(req) as response:return json.load(response)
    def test_rbg_delay_reset_and_session_isolation(self):
        a,b=self.client(),self.client();pid=next(iter(web.catalog('rbg')))
        first=self.request(a,'/api/session',{'cohort':'rbg','patient_id':pid})
        separate=self.request(b,'/api/session',{'cohort':'rbg','patient_id':pid})
        self.assertEqual(len(first['ledger']),2);self.assertEqual(first['ledger'][0]['actual'],None)
        self.assertTrue(all(p['time']<=first['data_cutoff'] for p in first['chart']))
        at_target=self.request(a,'/api/advance',{'minutes':30})
        self.assertEqual(at_target['ledger'][0]['outcome'],'Pending')
        after=self.request(a,'/api/advance',{'minutes':5})
        self.assertIn(after['ledger'][0]['outcome'],['Observed','Missing observation'])
        self.assertEqual(self.request(b,'/api/snapshot')['issue_time'],separate['issue_time'])
        reset=self.request(a,'/api/reset',{})
        self.assertEqual(reset['issue_time'],first['issue_time']);self.assertEqual(len(reset['ledger']),2)
    def test_cgmacros_and_reserved_patient_rejection(self):
        client=self.client();pid=next(iter(web.catalog('cgmacros')))
        first=self.request(client,'/api/session',{'cohort':'cgmacros','patient_id':pid})
        self.assertEqual(first['sensor_delay_minutes'],0);self.assertIn('HbA1c',first['profile']);self.assertEqual(len(first['forecasts']),1)
        manifest=json.loads((ROOT/'configs/rbg_splits.json').read_text())
        test=next(p['patient_id'] for p in manifest['participants'] if p['split']=='test')
        with self.assertRaises(urllib.error.HTTPError) as context:self.request(client,'/api/session',{'cohort':'rbg','patient_id':test})
        self.assertEqual(context.exception.code,400)
    def test_static_routes_and_cross_origin_guard(self):
        client=self.client()
        with client.open(self.url+'/') as response:self.assertIn(b'Patient trajectory',response.read())
        with self.assertRaises(urllib.error.HTTPError) as context:client.open(self.url+'/../../configs/rbg_splits.json')
        self.assertEqual(context.exception.code,404)
        req=urllib.request.Request(self.url+'/api/reset',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://example.com'})
        with self.assertRaises(urllib.error.HTTPError) as context:client.open(req)
        self.assertEqual(context.exception.code,403)

if __name__=='__main__':unittest.main()
