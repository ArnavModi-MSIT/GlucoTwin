"""Summarize the completed fixed study without changing models or thresholds."""
from pathlib import Path
import sys,json,argparse
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from glucotwin.event_study import summarize

def run(study='v1'):
    name='event_study_'+study
    report=json.loads((ROOT/'reports'/f'{name}.json').read_text())
    rows=json.loads((ROOT/'data/processed'/f'cgmacros_event_patient_metrics_{study}.json').read_text())
    fused=rows['fused'];sensor=rows['cgm_only']
    assert [r['patient_id'] for r in fused]==[r['patient_id'] for r in sensor]
    rng=np.random.default_rng(2026);differences=[]
    for _ in range(2000):
        ids=rng.integers(0,len(fused),len(fused))
        a=summarize([fused[i] for i in ids]);b=summarize([sensor[i] for i in ids])
        if a['episode_recall'] is not None and b['episode_recall'] is not None:
            differences.append(a['episode_recall']-b['episode_recall'])
    paired={'description':'paired patient bootstrap; fused minus matched sensor-only episode recall',
            'difference':report['pooled']['fused']['episode_recall']-report['pooled']['cgm_only']['episode_recall'],
            'bootstrap95':np.quantile(differences,[.025,.975]).tolist()}
    # Separate supplementary result; retain the original runner report unchanged.
    (ROOT/'reports'/f'{name}_fusion_comparison.json').write_text(json.dumps(paired,indent=2),encoding='utf-8')
    candidate_count=len(report['folds'][0]['inner_selection'])
    lines=[f"# Future-onset prediction: {report['version']}",'',
        'Run 10 October 2026. Retrospective development data; no reserved-test sensor files or targets were opened.',
        '',f"Used {report['support']['patients']} patients, {report['support']['known_label_rows']:,} known training-label opportunities and {report['support']['unknown_label_rows']} unknown-label opportunities (excluded from training).",'',
        f'Three outer folds each held out nine patients. Model selection used inner patient-level CV on 15 fitting patients; thresholds used three additional patients. {candidate_count} fixed candidate configurations were compared. Predictions target sustained high-glucose onsets 5–30 minutes ahead. All feature preprocessing is fit only on fitting patients.','',
        '| Method | Detected / evaluable episodes | Recall | Conservative precision | False alarms / eligible day | Median lead | Pooled engineering gate |',
        '|---|---:|---:|---:|---:|---:|---|']
    for method,r in report['pooled'].items():
        lines.append(f"| {method} | {r['detected_episodes']} / {r['evaluable_episodes']} | {r['episode_recall']:.1%} | {r['precision_lower_bound']:.1%} | {r['false_per_eligible_day']:.2f} | {r['median_lead_minutes']:.0f} min | {report['pooled_engineering_gate_passed'][method]} |")
    lines.extend(['',f"Fused-minus-sensor-only recall difference: {paired['difference']:.1%}; paired patient bootstrap 95% interval [{paired['bootstrap95'][0]:.1%}, {paired['bootstrap95'][1]:.1%}]. Negative values favor sensor-only. This is a matched ablation, not a separately tuned best sensor model.",'',
        'Conservative precision counts all alarms, including unknown and redundant alarms, in the denominator. False-alarm days are eligible at-risk coverage, not calendar patient-days. Onsets are engineering labels, not adjudicated medical events. Patient bootstrap intervals for each method are in the JSON report.','',
        f"All fused threshold-setting folds passed: {report['all_threshold_folds_passed']}. This result does not enable alerts or percentages. Model ranking scores are uncalibrated. Repeated use of development patients, reconstructed source values, assumed historical-profile availability and small subject count remain limitations.",'',
        f"Runtime {report['runtime_seconds']:.1f} seconds; sampled peak RSS {report['sampled_peak_rss_mib']:.1f} MiB. Requested device: {report.get('device_requested','cpu')}. No training-row cap was used.",'',
        f'Reproduce with `python scripts/run_event_study.py --study {study}`, then `python scripts/summarize_event_study.py --study {study}`. Frozen roles and raw-input fingerprints remain local. The protocol hash is recorded in every fold artifact and aggregate report. Further experiments must use a new protocol version; do not lower gates after seeing these scores.'])
    if study=='gpu_v2':lines.extend(['','This study was specified after v1 results were inspected and reuses the same development patients. It is another exploratory comparison, not independent confirmation. CPU execution does not verify the cloud CUDA notebook.'])
    (ROOT/'reports'/f'{name.upper()}.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--study',choices=['v1','gpu_v2'],default='v1');args=parser.parse_args();run(args.study)
