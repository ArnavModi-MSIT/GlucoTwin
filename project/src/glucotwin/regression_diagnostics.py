"""Error summaries and selection guardrails; no model training or future features."""
import numpy as np


def error_summary(actual, predicted):
    actual=np.asarray(actual,dtype=float);predicted=np.asarray(predicted,dtype=float)
    if actual.shape!=predicted.shape:raise ValueError('Mismatched prediction shape')
    if not (np.isfinite(actual).all() and np.isfinite(predicted).all()):
        raise ValueError('Nonfinite observed predictions')
    if not len(actual):return {'n':0,'mae':None,'rmse':None,'bias':None,'p90_absolute_error':None,
                               'p95_absolute_error':None,'p99_absolute_error':None,
                               'fraction_error_gt40':None,'fraction_error_gt60':None}
    signed=predicted-actual;error=np.abs(signed)
    return {'n':len(actual),'mae':float(error.mean()),'rmse':float(np.sqrt(np.mean(signed**2))),
            'bias':float(signed.mean()),'p90_absolute_error':float(np.quantile(error,.9)),
            'p95_absolute_error':float(np.quantile(error,.95)),'p99_absolute_error':float(np.quantile(error,.99)),
            'fraction_error_gt40':float((error>40).mean()),'fraction_error_gt60':float((error>60).mean())}


def sliced_errors(actual,predicted):
    actual=np.asarray(actual);predicted=np.asarray(predicted)
    return {name:error_summary(actual[mask],predicted[mask]) for name,mask in
            [('all',np.ones(len(actual),dtype=bool)),('high',actual>180),('low',actual<70)]}


def patient_macro(rows,slice_name='all'):
    metrics=[r['diagnostics'][slice_name] for r in rows if r['diagnostics'][slice_name]['n']]
    result={'patients_with_rows':len(metrics),'rows':sum(r['n'] for r in metrics)}
    if not metrics:return result
    for key in metrics[0]:
        if key!='n':result['mean_patient_'+key]=float(np.mean([r[key] for r in metrics]))
    return result


def select_guarded(tuning,settings):
    """Only tuning summaries enter selection; absent slice support fails closed."""
    baseline='ridge_original'; reference={s:patient_macro(tuning[baseline],s) for s in ['all','high','low']}
    accepted=[];decisions={}
    for name,rows in tuning.items():
        reasons=[]
        for slice_name,keys in [('all',['rmse','p90_absolute_error']),('high',['mae']),('low',['mae'])]:
            candidate=patient_macro(rows,slice_name);ref=reference[slice_name]
            if slice_name!='all' and ref['rows']<settings['minimum_slice_rows']:
                reasons.append(slice_name+' insufficient tuning support');continue
            for key in keys:
                if candidate.get('mean_patient_'+key,float('inf'))>ref.get('mean_patient_'+key,0.)*(1+settings['maximum_relative_worsening']):
                    reasons.append(slice_name+' '+key+' worsened')
        decisions[name]={'meets_guardrails':not reasons,'reasons':reasons}
        if not reasons:accepted.append(name)
    # Ridge remains the benchmark fallback; insufficient evidence never promotes a candidate.
    chosen=min(accepted,key=lambda n:patient_macro(tuning[n])['mean_patient_mae']) if accepted else baseline
    return chosen,decisions
