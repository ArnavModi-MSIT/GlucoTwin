"""Aggregate research comparison; no patient-level output."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]

def run():
    reports=[json.loads((ROOT/'reports'/f'event_study_{study}.json').read_text()) for study in ('v1','gpu_v2')]
    labels=[f'{study}\n{method}' for study in ('v1','XGBoost') for method in ('Fused','CGM only','Trend')]
    colors=['#168477','#387ab9','#9ca5ad']*2
    fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    for ax,key,title,target,scale in zip(axes.ravel(),
        ['episode_recall','precision_lower_bound','false_per_eligible_day','median_lead_minutes'],
        ['Episode recall (%)','Conservative precision (%)','False alarms / eligible monitoring day','Median warning lead (minutes)'],
        [60,50,1,10],[100,100,1,1]):
        values=[];low=[];high=[]
        for report in reports:
            for method in ('fused','cgm_only','slope_rule'):
                value=report['pooled'][method][key]*scale;values.append(value)
                interval=report['patient_bootstrap95'][method].get(key,[value/scale,value/scale])
                low.append(max(0,value-interval[0]*scale));high.append(max(0,interval[1]*scale-value))
        ax.bar(np.arange(6),values,color=colors,width=.65)
        if key!='median_lead_minutes':ax.errorbar(np.arange(6),values,yerr=[low,high],fmt='none',color='#263544',capsize=3)
        ax.axhline(target,color='#b54a42',linestyle='--',linewidth=1,label='Engineering criterion')
        ax.set_xticks(np.arange(6),labels,fontsize=9);ax.set_title(title,fontsize=11);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
        for i,v in enumerate(values):ax.text(i,v+max(values)*.02,f'{v:.2f}' if key=='false_per_eligible_day' else f'{v:.1f}',ha='center',fontsize=9)
        ax.set_ylim(0,max(max(v+h for v,h in zip(values,high)),target)*1.25)
    fig.suptitle('Future-onset prediction: nested development evaluation, 27 patients\nPatient-bootstrap intervals; reconstructed data; no clinical validation\nRed dashed lines: engineering criteria',fontsize=12)
    fig.savefig(ROOT/'reports/event_studies.png',dpi=160);plt.close(fig)

if __name__=='__main__':run()
