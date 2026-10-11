"""Aggregate-only reliability figure from the saved development assessment."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
report=json.loads((ROOT/'reports/classifier_assessment.json').read_text())
fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
for ax,view,title in zip(axes,['all_endpoints','at_risk_endpoints'],['All endpoints','Current glucose <=180 mg/dL']):
    ax.plot([0,1],[0,1],color='gray',linestyle='--',label='Ideal calibration')
    for name,label,color in [('raw_logistic','Raw logistic','#2563eb'),('sigmoid_calibrated','Sigmoid calibrated','#d97706')]:
        bins=[b for b in report['scores'][name][view]['reliability_bins'] if b['rows']>0]
        ax.plot([b['mean_probability'] for b in bins],[b['observed_fraction'] for b in bins],marker='o',color=color,label=label)
    ax.set(xlim=(0,1),ylim=(0,1),xlabel='Mean predicted probability',ylabel='Observed positive fraction',title=title)
    ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.suptitle('Development reliability: 3 tuning patients; 10 fixed probability bins\nOverlapping endpoint windows; probability display disabled',fontsize=11)
fig.savefig(ROOT/'reports/classifier_reliability.png',dpi=160)
plt.close(fig)
