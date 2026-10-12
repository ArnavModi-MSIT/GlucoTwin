"""Exports accept a revealed snapshot only; they cannot read source records."""
import csv
import io
from html import escape


def csv_report(snapshot):
    output = io.StringIO(newline='')
    fields = ['record_type', 'cohort', 'synthetic', 'patient', 'model', 'replay_time',
              'issued_at', 'horizon', 'target_time', 'available_at', 'prediction',
              'persistence', 'status', 'outcome', 'actual', 'model_absolute_error',
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
    label = 'SYNTHETIC DEMONSTRATION — NOT MEASURED MODEL PERFORMANCE' if snapshot.get('synthetic') else 'RESEARCH REPLAY — NOT CLINICALLY VALIDATED'
    profile = ''.join('<li>'+escape(k)+': '+show(v)+'</li>' for k,v in snapshot['profile'].items())
    comparison = snapshot['comparison']
    forecasts = table(snapshot['ledger'], [('issued_at','Issued'),('horizon','Horizon (min)'),('target_time','Target'),
        ('prediction','Forecast mg/dL'),('persistence','Persistence'),('status','Status'),('outcome','Outcome'),('actual','Observed'),('ridge_error','Absolute error')])
    events = table((snapshot.get('event_research') or {}).get('ledger', []), [('issued_at','Issued'),('status','Decision'),
        ('window_start','Window start'),('window_end','Window end'),('available_at','Reveal after'),('outcome','Outcome'),('event_at','Onset')])
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>GlucoTwin session report</title><style>body{font:14px/1.5 system-ui;margin:32px;color:#182b39}h1{margin-bottom:0}table{border-collapse:collapse;width:100%;font-size:10px}th,td{border:1px solid #ddd;padding:6px;text-align:left;overflow-wrap:anywhere}thead{display:table-header-group}tr{break-inside:avoid}.notice{border:1px solid #8aaca5;padding:12px} @media print{body{margin:0;font-size:11px}.print-note{display:none}@page{size:landscape;margin:12mm}}</style><body><h1>GlucoTwin · Session report</h1><p class="notice">'+label+'</p><p class="print-note">Use your browser’s Print command to save this report as a PDF.</p><h2>'+show(snapshot['patient_label'])+'</h2><p>Replay time: '+show(snapshot['issue_time'])+' · Observations available through: '+show(snapshot['data_cutoff'])+'</p><p>Numerical model: '+show(snapshot['model_name'])+'<br>Event method: '+show(snapshot.get('event_model_name'))+'</p><ul>'+profile+'</ul><p>'+show(snapshot['profile_note'])+'</p><p>Latest glucose: '+show(snapshot['latest'])+' mg/dL · CGM coverage: '+show(snapshot['coverage'])+'/13 samples in the last hour.</p><p>Revealed pairs: '+show(comparison['evaluated'])+' · Session model MAE: '+show(comparison['ridge_mae'])+' mg/dL · Persistence MAE: '+show(comparison['persistence_mae'])+' mg/dL. Overlapping forecasts are not independent validation samples.</p><h2>Forecast ledger</h2>'+forecasts+'<h2>Event attempts</h2>'+events+'<p>Pending outcomes remain hidden. Missing readings are not filled. Event attempts may refer to the same episode; this session is not an episode-level performance evaluation. No diagnosis, treatment or insulin dosing.</p></body></html>'
