import json
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from glucotwin.brist1d_sequence import encode_sequence,SequenceScaler,inner_roles,head_weights,sample_positions


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/'configs/brist1d_sequence_v4.json').read_text())
        self.protocol=json.loads((ROOT/'configs/brist1d_contract_v1.json').read_text())
        self.caps=json.loads((ROOT/'configs/brist1d_freshness_v2.json').read_text())['freshness_caps_minutes']

    def streams(self,cadence):
        grid=pd.date_range('2024-01-01',periods=50,freq=f'{cadence}min')
        values={c:pd.Series(dtype=float,index=pd.DatetimeIndex([])) for c in self.config['channels']}
        values['bg']=pd.Series(np.arange(50.)+5,index=grid)
        return values

    def test_delays_native_cadence_future_insertion_and_prefix(self):
        for cadence in (5,15):
            streams=self.streams(cadence)
            issue=streams['bg'].index[30]+pd.Timedelta(minutes=cadence)
            issues=pd.DatetimeIndex([issue])
            expected=encode_sequence(streams,issues,cadence,self.protocol,self.config,self.caps)
            self.assertAlmostEqual(expected[0,0,-1],streams['bg'].iloc[30]*18.0182,places=3)
            prefix={c:s.loc[s.index<=issue-pd.Timedelta(minutes=self.protocol['availability_delay_minutes'][c])] for c,s in streams.items()}
            np.testing.assert_array_equal(expected,encode_sequence(prefix,issues,cadence,self.protocol,self.config,self.caps))
            future={c:s.copy() for c,s in streams.items()}
            for c,s in future.items(): s.loc[issue+pd.Timedelta(minutes=5)]=99999.
            np.testing.assert_array_equal(expected,encode_sequence(future,issues,cadence,self.protocol,self.config,self.caps))

    def test_meal_unknown_zero_carried_record_and_staleness(self):
        streams=self.streams(5); issue=streams['bg'].index[30]+pd.Timedelta(minutes=5)
        absent=encode_sequence(streams,pd.DatetimeIndex([issue]),5,self.protocol,self.config,self.caps)
        self.assertTrue(np.isnan(absent[0,10,-1])); self.assertEqual(absent[0,14,-1],1)
        streams['carbs']=pd.Series([0.],index=pd.DatetimeIndex([issue-pd.Timedelta(minutes=15)]))
        zero=encode_sequence(streams,pd.DatetimeIndex([issue]),5,self.protocol,self.config,self.caps)
        self.assertEqual(zero[0,10,-1],0); self.assertEqual(zero[0,11,-1],1); self.assertEqual(zero[0,12,-1],1)
        carried=encode_sequence(streams,pd.DatetimeIndex([issue+pd.Timedelta(minutes=5)]),5,self.protocol,self.config,self.caps)
        self.assertEqual(carried[0,10,-1],0); self.assertEqual(carried[0,12,-1],0)
        streams['insulin']=pd.Series([2.],index=pd.DatetimeIndex([issue-pd.Timedelta(minutes=35)]))
        stale=encode_sequence(streams,pd.DatetimeIndex([issue]),5,self.protocol,self.config,self.caps)
        self.assertTrue(np.isnan(stale[0,5,-1])); self.assertEqual(stale[0,6,-1],0); self.assertEqual(stale[0,8,-1],1)

    def test_scaler_training_only_and_constant_channel(self):
        train=np.zeros((2,35,25),dtype=np.float32); train[:,0,:]=10; train[:,5,:]=np.nan
        scaler=SequenceScaler().fit(train)
        before=scaler.means.copy()
        test=train.copy(); test[:,0,:]=20
        encoded=scaler.transform(test)
        np.testing.assert_array_equal(before,scaler.means)
        self.assertTrue(np.isfinite(encoded).all()); self.assertEqual(encoded[0,0,0],10)
        self.assertEqual(encoded[0,5,0],0)

    def test_head_masks_equal_patient_weights_and_reproducible_sampling(self):
        targets=np.array([[1.,2.],[3.,np.nan],[4.,5.],[6.,7.]])
        groups=np.array(['P01','P01','P02','P02'])
        weights=head_weights(targets,groups)
        self.assertEqual(weights[1,1],0)
        for h in (0,1): self.assertAlmostEqual(weights[:2,h].sum(),weights[2:,h].sum())
        record={'y30':np.arange(10.),'y60':np.arange(10.)}
        np.testing.assert_array_equal(sample_positions(record,'P01',4,2026),sample_positions(record,'P01',4,2026))

    def test_inner_stopping_roles_exclude_outer_and_reserved(self):
        ids=[f'P{i:02d}' for i in range(1,21)]
        manifest={'participants':{p:{'native_minutes':15 if i%4==0 else 5} for i,p in enumerate(ids)}}
        role={'fold':1,'fit':ids[:12],'evaluation':ids[12:16]}
        roles=inner_roles(role,manifest,2026)
        self.assertEqual(len(roles['fit']),9); self.assertEqual(len(roles['stopping']),3)
        self.assertFalse(set(roles['stopping'])&set(role['evaluation']))
        self.assertEqual(roles,inner_roles(role,manifest,2026))


class NeuralArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import torch
            cls.torch=torch
        except ImportError:
            raise unittest.SkipTest('Optional CPU torch environment not installed')

    def test_convolution_is_causal_and_receptive_field(self):
        from glucotwin.brist1d_tcn import CausalConv,CompactTCN
        torch=self.torch
        conv=CausalConv(1,2,3,4).eval(); x=torch.zeros(1,1,25)
        before=conv(x).detach(); x[:,:,20:]=999
        torch.testing.assert_close(before[:,:,:20],conv(x)[:,:,:20])
        config=json.loads((ROOT/'configs/brist1d_sequence_v4.json').read_text())
        a=config['architecture']
        self.assertEqual(1+2*(a['kernel_size']-1)*sum(a['dilations']),config['receptive_field_samples'])
        model=CompactTCN(35,10,a).eval()
        result=model(torch.zeros(2,35,25),torch.zeros(2,10))
        self.assertEqual(tuple(result.shape),(2,2)); self.assertEqual(result.abs().sum().item(),0.)


if __name__=='__main__': unittest.main()
