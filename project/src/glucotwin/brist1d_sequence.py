"""Causal masked history with explicit observation/freshness semantics."""
import numpy as np
import pandas as pd
from .brist1d import last_observation, MG_DL_PER_MMOL_L


def encode_sequence(streams,issues,native_minutes,protocol,config,caps):
    points=config['sequence_points']; step=config['step_minutes']
    if (points-1)*step!=config['history_minutes']: raise ValueError('History/grid mismatch')
    result=np.empty((len(issues),len(config['channels'])*5,points),dtype=np.float32)
    for c,channel in enumerate(config['channels']):
        stream=streams[channel]*(MG_DL_PER_MMOL_L if channel=='bg' else 1.)
        delay=protocol['availability_delay_minutes'][channel]
        cap=native_minutes+delay if channel=='bg' else caps[channel]
        for j,offset in enumerate(range(config['history_minutes'],-1,-step)):
            query=issues-pd.Timedelta(minutes=offset)
            cutoff=query-pd.Timedelta(minutes=delay)
            value,age=last_observation(stream,cutoff)
            unknown=~np.isfinite(age); source_age=age+delay
            fresh=~unknown & (source_age<=cap)
            value[~fresh]=np.nan
            # A carried event amount is context; it is not another administered
            # dose or consumed meal. New-observation flag uses (cutoff-5, cutoff].
            result[:,c*5,j]=value
            result[:,c*5+1,j]=fresh
            result[:,c*5+2,j]=~unknown & (age<step)
            result[:,c*5+3,j]=np.where(unknown,1.,np.minimum(source_age/cap,1.))
            result[:,c*5+4,j]=unknown
    return result


def inner_roles(role,manifest,seed):
    rng=np.random.default_rng(seed+role['fold'])
    chosen=[]
    for cadence,count in ((5,2),(15,1)):
        pool=sorted(p for p in role['fit'] if manifest['participants'][p]['native_minutes']==cadence)
        if len(pool)<count: raise ValueError('Inner cadence stratum lacks patients')
        chosen.extend(str(p) for p in rng.choice(pool,size=count,replace=False))
    fit=sorted(set(role['fit'])-set(chosen)); stop=sorted(chosen)
    if set(fit)&set(stop) or (set(fit)|set(stop))!=set(role['fit']): raise ValueError('Inner role overlap')
    if (set(fit)|set(stop))&set(role['evaluation']): raise ValueError('Outer evaluation used for stopping')
    return {'fit':fit,'stopping':stop}


def sample_positions(record,pid,cap,seed):
    positions=np.flatnonzero(np.isfinite(record['y30'])|np.isfinite(record['y60']))
    if cap is not None and len(positions)>cap:
        rng=np.random.default_rng(seed+int(pid[1:])*1000)
        positions=np.sort(rng.choice(positions,size=cap,replace=False))
    return positions


def head_weights(targets,groups):
    weights=np.zeros_like(targets,dtype=np.float32)
    patients=np.unique(groups)
    for pid in patients:
        for h in range(targets.shape[1]):
            available=(groups==pid)&np.isfinite(targets[:,h])
            if not available.any(): raise ValueError('Patient lacks head support')
            weights[available,h]=len(targets)/(len(patients)*available.sum())
    return weights


class SequenceScaler:
    def fit(self,sequence):
        # Only the measured/carried fresh-value channel is learned-scaled.
        values=sequence[:,::5,:].astype(np.float64)
        self.means=[]; self.stds=[]
        for c in range(values.shape[1]):
            observed=values[:,c,:][np.isfinite(values[:,c,:])]
            self.means.append(float(observed.mean()) if len(observed) else 0.)
            self.stds.append(max(float(observed.std()),1.) if len(observed) else 1.)
        self.means=np.array(self.means,dtype=np.float32)
        self.stds=np.array(self.stds,dtype=np.float32)
        return self

    def transform(self,sequence):
        output=sequence.astype(np.float32,copy=True)
        output[:,::5,:]=(output[:,::5,:]-self.means[None,:,None])/self.stds[None,:,None]
        output[:,::5,:]=np.nan_to_num(output[:,::5,:],nan=0.)
        if not np.isfinite(output).all(): raise ValueError('Nonfinite scaled sequence')
        return output
