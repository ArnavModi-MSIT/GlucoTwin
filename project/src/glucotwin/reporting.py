"""Exports accept a revealed snapshot only; they cannot read source records."""
import csv
import io
from datetime import datetime
from html import escape


def history_csv_report(snapshot):
    """Export the available hourly summaries; no raw records or user notes."""
    history = snapshot.get('historical_patterns') or {}
    cutoff = datetime.fromisoformat(snapshot['data_cutoff'])
    if history.get('through') != snapshot['data_cutoff'] or cutoff > datetime.fromisoformat(snapshot['issue_time']):
        raise ValueError('Historical summary does not match the current data cutoff')
    output = io.StringIO(newline='')
    fields = ['cohort','synthetic','patient','replay_time','data_cutoff','date','hour',
              'first_checkpoint','last_checkpoint','samples','expected','coverage',
              'complete_hour','comparable','mean','minimum','maximum',
              'low_fraction','reference_fraction','high_fraction']
    writer = csv.DictWriter(output,fieldnames=fields,extrasaction='ignore')
    writer.writeheader()
    base = dict(cohort=snapshot['cohort'],synthetic=bool(snapshot.get('synthetic')),
                patient=snapshot['patient_label'],replay_time=snapshot['issue_time'],data_cutoff=snapshot['data_cutoff'])
    for row in history.get('hourly',[]):
        if datetime.fromisoformat(row['last_checkpoint']) > cutoff:
            continue
        values = dict(row,**base)
        writer.writerow({k:"'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for k,v in values.items()})
    return output.getvalue()


def csv_report(snapshot):
    output = io.StringIO(newline='')
    fields = ['record_type', 'cohort', 'synthetic', 'patient', 'model', 'replay_time',
              'issued_at', 'horizon', 'target_time', 'available_at', 'prediction',
              'interval_lower', 'interval_upper', 'interval_nominal', 'interval_assessment_coverage', 'interval_assessment_patients', 'interval_low_coverage', 'interval_high_coverage', 'persistence', 'status', 'outcome', 'actual', 'model_absolute_error',
              'baseline_absolute_error', 'window_start', 'window_end', 'score',
              'cutoff', 'research_flag', 'event_at', 'lead_minutes']
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    base = dict(cohort=snapshot['cohort'], synthetic=bool(snapshot.get('synthetic')),
                patient=snapshot['patient_label'], model=snapshot['model_name'], replay_time=snapshot['issue_time'])
    def safe(row):
        # Prevent spreadsheet formula execution in exported text cells.
        return {k: "'"+v if isinstance(v, str) and v.startswith(('=', '+', '-', '@')) else v for k,v in row.items()}
    for row in snapshot['ledger']:
        writer.writerow(safe(dict(base, **row, record_type='forecast', model_absolute_error=row['ridge_error'],
                                  baseline_absolute_error=row['persistence_error'])))
    for row in (snapshot.get('event_research') or {}).get('ledger', []):
        writer.writerow(safe(dict(base, **row, record_type='event', model=snapshot.get('event_model_name', 'Event research'))))
    return output.getvalue()


def html_report(snapshot):
    def show(value):
        return escape('—' if value is None else f'{value:.2f}' if isinstance(value, float) else str(value))
    def table(rows, columns):
        return '<table><thead><tr>'+''.join('<th>'+escape(label)+'</th>' for key,label in columns)+'</tr></thead><tbody>'+''.join(
            '<tr>'+''.join('<td>'+show(row.get(key))+'</td>' for key,label in columns)+'</tr>' for row in rows)+'</tbody></table>'
    label = 'USER IMPORT — TRANSFER PERFORMANCE UNESTABLISHED' if snapshot.get('imported') else 'SYNTHETIC DEMONSTRATION — NOT MEASURED MODEL PERFORMANCE' if snapshot.get('synthetic') else 'RESEARCH REPLAY — NOT CLINICALLY VALIDATED'
    profile = ''.join('<li>'+escape(k)+': '+show(v)+'</li>' for k,v in snapshot['profile'].items())
    comparison = snapshot['comparison']
    forecasts = table(snapshot['ledger'], [('issued_at','Issued'),('horizon','Horizon (min)'),('target_time','Target'),
        ('prediction','Forecast mg/dL'),('interval_lower','Exploratory lower'),('interval_upper','Exploratory upper'),('interval_assessment_coverage','Development range coverage'),('persistence','Persistence'),('status','Status'),('outcome','Outcome'),('actual','Observed'),('ridge_error','Absolute error')])
    events = table((snapshot.get('event_research') or {}).get('ledger', []), [('issued_at','Issued'),('status','Decision'),
        ('window_start','Window start'),('window_end','Window end'),('available_at','Reveal after'),('outcome','Outcome'),('event_at','Onset')])
    history = snapshot.get('historical_patterns')
    patterns = ''
    if history:
        days = [{**r, **{k: None if r[k] is None else f'{100*r[k]:.1f}%'
                          for k in ('coverage','low_fraction','reference_fraction','high_fraction')}}
                for r in history['daily']]
        patterns = '<h2>Available historical patterns</h2><p>'+show(history['note'])+'</p>'+table(days,
            [('date','Study date'),('samples','Observed samples'),('expected','Expected'),
             ('coverage','Coverage'),('mean','Mean mg/dL'),('low_fraction','Below 70'),
             ('reference_fraction','70–180'),('high_fraction','Above 180')])
        patterns += '<p>Recurring periods use complete six-hour windows with at least 80% coverage. A high window has at least 20% readings above 180; a low window has at least 5% below 70. Recurrence requires at least two days and half of comparable days. No future forecast or personalized target.</p>'+table(
            history['periods'], [('start_hour','Start hour'),('end_hour','End hour'),
                ('eligible_days','Comparable days'),('high_days','High periods'),('low_days','Low periods'),('description','Observation')])
    extended = (history or {}).get('profile')
    if extended:
        patterns += '<h2>Fourteen-date descriptive profile</h2><p>'+show(extended['note'])+'</p>'+table([extended],
            [('observed_days','Dates with readings'),('complete_covered_days','Complete dates at least 70% covered'),('samples','Samples'),('expected','Expected'),('coverage','Coverage fraction'),('mean','Mean mg/dL'),('std','Standard deviation mg/dL'),('coefficient_variation_pct','Coefficient of variation %')])
        patterns += table(extended['hours'],[('hour','Study hour'),('covered_days','Covered days'),('p10','10th percentile'),('p25','25th percentile'),('median','Median'),('p75','75th percentile'),('p90','90th percentile')])
    explanations = '<h2>Current forecast arithmetic</h2><p>Model contributions do not establish physiological or treatment effects.</p>'
    for forecast in snapshot.get('forecasts',[]):
        e=forecast.get('explanation')
        if not e:continue
        rows=[dict(term='Latest available reading',value=e['persistence']),dict(term='Model reference offset',value=e['reference_offset'])]
        rows += [dict(term=k,value=v) for k,v in e['groups'].items()]
        rows += [dict(term='Reconstructed forecast',value=e['reconstructed_prediction'])]
        explanations += '<h3>'+show(forecast['horizon'])+' minutes</h3>'+table(rows,[('term','Term'),('value','mg/dL')])+'<p>'+show(e['note'])+'</p>'
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>GlucoTwin session report</title><style>body{font:14px/1.5 system-ui;margin:32px;color:#182b39}h1{margin-bottom:0}table{border-collapse:collapse;width:100%;font-size:10px}th,td{border:1px solid #ddd;padding:6px;text-align:left;overflow-wrap:anywhere}thead{display:table-header-group}tr{break-inside:avoid}.notice{border:1px solid #8aaca5;padding:12px} @media print{body{margin:0;font-size:11px}.print-note{display:none}@page{size:landscape;margin:12mm}}</style><body><h1>GlucoTwin · Session report</h1><p class="notice">'+label+'</p><p class="print-note">Use your browser’s Print command to save this report as a PDF.</p><h2>'+show(snapshot['patient_label'])+'</h2><p>Replay time: '+show(snapshot['issue_time'])+' · Observations available through: '+show(snapshot['data_cutoff'])+'</p><p>Numerical model: '+show(snapshot['model_name'])+'<br>Event method: '+show(snapshot.get('event_model_name'))+'</p><ul>'+profile+'</ul><p>'+show(snapshot['profile_note'])+'</p><p>Latest glucose: '+show(snapshot['latest'])+' mg/dL · CGM coverage: '+show(snapshot['coverage'])+'/13 samples in the last hour.</p><p>Revealed pairs: '+show(comparison['evaluated'])+' · Session model MAE: '+show(comparison['ridge_mae'])+' mg/dL · Persistence MAE: '+show(comparison['persistence_mae'])+' mg/dL. Overlapping forecasts are not independent validation samples.</p>'+patterns+explanations+'<h2>Forecast ledger</h2><p>Exploratory ranges use separate calibration patients; assessment coverage is not a patient-level guarantee. '+show(snapshot.get('uncertainty_note'))+'</p>'+forecasts+'<h2>Event attempts</h2>'+events+'<p>Pending outcomes remain hidden. Missing readings are not filled. Event attempts may refer to the same episode; this session is not an episode-level performance evaluation. No diagnosis, treatment or insulin dosing.</p></body></html>'
