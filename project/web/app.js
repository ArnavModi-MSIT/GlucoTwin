'use strict';
const $ = id => document.getElementById(id);
let catalog, cohort='demo', snapshot, busy=false, playing=false, playbackTimer=null;
const number=(v,d=0)=>Number.isFinite(v)?v.toFixed(d):'—';
const wall=t=>t?t.replace('T',' ').slice(0,16):'—';
const short=t=>t?`${t.slice(8,10)} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+t.slice(5,7)-1]}, ${t.slice(11,16)}`:'—';
const coord=t=>Date.parse(t+'Z'); // Use UTC solely as a plotting coordinate; retain supplied wall-time labels.
const text=(id,value)=>{$(id).textContent=value;};
function setBusy(value){busy=value;document.body.classList.toggle('busy',value);$('loading').hidden=!value;document.querySelectorAll('button,select').forEach(e=>e.disabled=value);if(playing)$('play').disabled=false;if(!value&&snapshot?.at_end){document.querySelectorAll('[data-step]').forEach(e=>e.disabled=true);$('play').disabled=true;}}
async function api(path,body){const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const value=await response.json();if(!response.ok)throw new Error(value.error||'Request failed');return value;}
async function action(path,body){if(busy)return;setBusy(true);$('error').hidden=true;try{snapshot=await api(path,body);render(snapshot);if(snapshot.at_end)stopPlayback();}catch(e){stopPlayback();$('error').textContent=e.message;$('error').hidden=false;}finally{setBusy(false);}}
function populate(){const select=$('patient');select.replaceChildren();for(const p of catalog.cohorts[cohort]||[]){const option=document.createElement('option');option.value=p.id;option.textContent=p.label;select.append(option);}document.querySelectorAll('[data-cohort]').forEach(b=>b.classList.toggle('active',b.dataset.cohort===cohort));}
async function selectPatient(){stopPlayback();if(!$('patient').options.length){text('error',catalog.errors?.[cohort]||'No prepared patients available for this cohort.');$('error').hidden=false;return;}await action('/api/session',{cohort,patient_id:$('patient').value});}
$('patient').addEventListener('change',selectPatient);
document.querySelectorAll('[data-cohort]').forEach(b=>b.addEventListener('click',async()=>{if(busy)return;stopPlayback();if(!catalog.cohorts[b.dataset.cohort]?.length){text('error',catalog.errors?.[b.dataset.cohort]||'Prepare this cohort first.');$('error').hidden=false;return;}cohort=b.dataset.cohort;populate();await selectPatient();}));
document.querySelectorAll('[data-step]').forEach(b=>b.addEventListener('click',()=>{stopPlayback();action('/api/advance',{minutes:+b.dataset.step});}));
$('reset').addEventListener('click',()=>{stopPlayback();action('/api/reset',{});});
function stopPlayback(){playing=false;clearTimeout(playbackTimer);playbackTimer=null;text('play','▶ Play replay');}
async function playbackTick(){if(!playing)return;if(!busy)await action('/api/advance',{minutes:5});if(playing)playbackTimer=setTimeout(playbackTick,Number($('speed').value)||1000);}
$('play').addEventListener('click',()=>{if(playing){stopPlayback();return;}if(!snapshot||snapshot.at_end||busy)return;playing=true;text('play','Ⅱ Pause replay');playbackTimer=setTimeout(playbackTick,Number($('speed').value)||1000);});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopPlayback();});
document.querySelectorAll('[data-export]').forEach(a=>a.addEventListener('click',stopPlayback));
$('fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $('chart-card').requestFullscreen();}catch(e){text('error','Fullscreen is unavailable in this browser.');$('error').hidden=false;}});
function render(s){
cohort=s.cohort;
const demo=cohort==='demo',modelLabel=demo?'Demo rule':'Ridge';
text('mode-label',demo?'Synthetic demonstration':'Research mode');
text('research-title',demo?'Fictional patient · illustrative rule · no trained model':'Research estimates. Alerts and risk probabilities are disabled.');
text('research-detail',demo?'Explore the workflow without downloading data. These trajectories and scores are not benchmark results.':'Development results do not establish medical reliability or support treatment decisions.');
text('profile-tag',demo?'Synthetic patient · no real patient data':'Validation patient · test patients excluded');
text('forecast30-note',demo?'Illustrative trend + fictional baseline':'Saved profile-fused Ridge');
text('forecast60-note',demo?'Illustrative trend + fictional baseline':'Saved profile-fused Ridge');
text('model-column',`${modelLabel} (mg/dL)`);text('error-column',`${modelLabel} absolute error (mg/dL)`);
text('review-title',demo?'Demo guide':'Session review');
text('review-note',demo?'Choose a scenario, play the five-minute replay, then compare each fixed forecast with its revealed outcome. Sensor interruption shows forecasts being withheld until history recovers.':`${s.model_name||'Saved model'} · Every five-minute issue is recorded. Session statistics describe this replay only.`);
text('review-quality',s.coverage===13?'Complete last-hour CGM window':`Incomplete CGM window: ${13-s.coverage} of 13 expected samples missing. Check forecast status.`);
document.querySelectorAll('[data-export]').forEach(a=>a.hidden=false);
text('patient-label',s.patient_label);
text('subtitle',demo?'Fictional scenarios · profile + past sensor trend · 30 / 60 minute illustrations':cohort==='rbg'?'Type 1 cohort · enrollment profile + CGM · 30 / 60 minute forecasts':'CGMacros cohort · clinical profile + CGM + heart rate · 60 minute forecast');
text('issue-date',s.issue_time.slice(0,10));text('issue-clock',s.issue_time.slice(11,16));text('cutoff',wall(s.data_cutoff));
text('latest',number(s.latest));
text('latest-note',`${Number.isFinite(s.latest)?'Reading at':'No CGM reading at'} ${s.data_cutoff.slice(11,16)}`);
$('forecast30-card').hidden=cohort==='cgmacros';
text('forecast30',number(s.forecasts.find(f=>f.horizon===30)?.prediction));
text('forecast60',number(s.forecasts.find(f=>f.horizon===60)?.prediction));
text('coverage',`${s.coverage}/13`);text('forecast-status',s.forecasts[0].status);text('profile-note',s.profile_note);
const inputs=s.forecasts[0].model_inputs||[],clinical=inputs.filter(c=>!c.startsWith('cgm_')&&!c.startsWith('hr_')),heart=inputs.filter(c=>c.startsWith('hr_'));
text('model-inputs',demo?'Illustrative rule: 90% of the past-trend projection + 10% of the fictional baseline. No learned coefficients.':`Model fusion: ${clinical.length} historical fields + ${inputs.filter(c=>c.startsWith('cgm_')).length} CGM features${heart.length?` + ${heart.length} heart-rate features`:''}. Both streams enter the same fitted Ridge model.`);
$('input-quality').hidden=cohort!=='cgmacros';
const hrFraction=s.forecasts[0].hr_fraction;
text('input-quality',`HR coverage, last hour: ${Number.isFinite(hrFraction)?`${number(hrFraction*100,1)}%`:'unavailable'}. Missing model inputs use the training-set median imputer.`);
const profile=$('profile');profile.replaceChildren();
for(const [label,value] of Object.entries(s.profile)){const row=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;row.append(dt,dd);profile.append(row);}
text('delay-note',s.sensor_delay_minutes?'Inputs and outcomes obey a five-minute availability delay. Target readings remain pending until target time +5 minutes.':'Only observations through replay time are visible. Reconstructed CGM samples and assumed profile availability limit real-time claims.');
const tbody=$('ledger');tbody.replaceChildren();
for(const row of s.ledger){
const tr=document.createElement('tr');
const values=[short(row.issued_at),`${row.horizon} min`,short(row.target_time),short(row.available_at),row.status,number(row.prediction,1),number(row.persistence,1),row.outcome,number(row.actual,1),number(row.ridge_error,1),number(row.persistence_error,1)];
values.forEach((value,i)=>{const td=document.createElement('td');if([5,6,8,9,10].includes(i))td.className='numeric';if(i===7){const tag=document.createElement('span');tag.className='outcome'+(row.outcome==='Observed'?' observed':'');tag.textContent=value;td.append(tag);}else td.textContent=value;tr.append(td);});tbody.append(tr);
}
const issued=s.ledger.filter(row=>Number.isFinite(row.prediction)).length;
text('ledger-count',`Issued forecasts: ${issued} · Withheld attempts: ${s.ledger.length-issued}`);
const summary=$('session-summary');summary.replaceChildren();
const horizonNote=cohort!=='cgmacros'?'30 / 60 min combined':'60 min';
for(const label of [`Forecast pairs evaluated: ${s.comparison.evaluated}`,`Session ${modelLabel} MAE (${horizonNote}): ${number(s.comparison.ridge_mae,1)} mg/dL`,`Session persistence MAE: ${number(s.comparison.persistence_mae,1)} mg/dL`]){const span=document.createElement('span');span.textContent=label;summary.append(span);}
const sessionNote=document.createElement('span');sessionNote.textContent='Replay session only; overlapping forecasts are not independent validation samples.';summary.append(sessionNote);
const evidence=$('evidence');evidence.replaceChildren();
const statements=demo?['All profiles and readings in this mode are generated locally from deterministic functions. They contain no real patient records.','Forecasts use only available past readings and a fictional baseline. Event flags use a simple projected-value cutoff, not XGBoost. Synthetic outcomes do not validate the research models.','Use the prepared CGMacros cohort to inspect the measured high-event research model. Research results in the README come from separate real-dataset development evaluations.']:cohort==='rbg'?[
'Active replay: profile-fused Ridge. Development split: 158 training patients, 34 validation, 34 reserved test. Row-weighted validation MAE: 17.59 mg/dL at 30 minutes and 28.89 at 60 minutes; persistence: 20.71 / 32.53. Reserved test patients have not been scored.',
'Low-target validation MAE worsened: Ridge 20.26 / 44.26 mg/dL at 30 / 60 minutes versus persistence 19.76 / 36.98. Enrollment age and recorded sex added essentially no accuracy gain. No meal or insulin-dose inputs.',
'RBG provides numerical forecasts only. Event research is available in the separate CGMacros panel. Operational alerts and risk percentages remain disabled.'
]:[
'Active replay: clinical-profile + CGM + heart-rate Ridge. Development split: 21 training patients, six validation, six reserved test. Row-weighted 60-minute validation MAE: 19.00 mg/dL; persistence: 19.99. Reserved test patients have not been scored. Individual errors can be much larger.',
'Low-target validation MAE worsened: Ridge 38.80 mg/dL versus persistence 20.26, based on only 39 target rows. Forecast targets overlap; these rows are not independent patient samples.',
'CGM samples are reconstructed from interpolated source data, and clinical-profile availability is assumed. Numerical forecasts use Ridge; the separate event panel uses saved fused XGBoost models. Event scores are uncalibrated. No diagnosis, treatment or insulin dosing.'
];
for(const statement of statements){const p=document.createElement('p');p.textContent=statement;evidence.append(p);}renderEvents(s);drawChart();
}
function renderEvents(s){
const event=s.event_research,demo=s.cohort==='demo';$('event-research').hidden=s.cohort==='rbg';
if(s.cohort==='rbg')return;
text('event-method',demo?'ILLUSTRATIVE TREND RULE':'SEPARATE XGBOOST MODEL');
text('event-score-label',demo?'Projected +30 min (mg/dL)':'Uncalibrated score');
text('event-score-note',demo?'Synthetic rule output; not a probability':'Ranking score; not a risk probability');
text('event-cutoff-note',demo?'Illustrative threshold in mg/dL':'Selected on separate cutoff patients');
text('event-timing',`Every five-minute step records an attempt, including time jumps. Flags have a 60-minute cooldown. Outcomes remain pending until issue time +${demo?50:45} minutes, including confirmation${demo?' and sensor delay':''}. Most recent attempts appear first.`);
$('event-evidence').hidden=demo;
const available=!!event?.available;$('event-content').hidden=!available;
text('event-availability',available?(demo?'Synthetic workflow example. No performance or clinical claims.':'Saved fused XGBoost uses the fold in which this patient was held out.'):event?.error||'Event research is unavailable; prepare the optional saved study.');
if(!available){$('event-ledger').replaceChildren();return;}
const row=event.current,meta=event.metadata;
text('event-score',number(row.score,demo?1:4));text('event-cutoff',number(row.cutoff,demo?1:4));text('event-decision',row.status);
text('event-window',`${short(row.window_start)} – ${short(row.window_end)}`);
text('event-fold',demo?'A flag illustrates a projected crossing; the outcome is revealed only after enough observations arrive. This rule has not been trained or evaluated on patients.':`Development fold ${meta.fold}: ${meta.fit_patients} fitting, ${meta.cutoff_patients} cutoff and ${meta.evaluation_patients} evaluation patients. This patient was excluded from fitting and cutoff selection. Cutoff operating criteria ${meta.cutoff_criteria_met?'met':'failed'} in that fold; medical reliability is unestablished.`);
const tbody=$('event-ledger');tbody.replaceChildren();
for(const issued of [...event.ledger].reverse()){const tr=document.createElement('tr');const values=[short(issued.issued_at),`${short(issued.window_start)} – ${short(issued.window_end)}`,short(issued.available_at),number(issued.score,demo?1:4),number(issued.cutoff,demo?1:4),issued.status,issued.outcome,issued.event_at?short(issued.event_at):'—'];
values.forEach((value,i)=>{const td=document.createElement('td');td.textContent=value;if(i===3||i===4)td.className='numeric';tr.append(td);});tbody.append(tr);}
}
const NS='http://www.w3.org/2000/svg';function svgNode(tag,attrs,textValue){const el=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);if(textValue!==undefined)el.textContent=textValue;return el;}
function drawChart(){if(!snapshot)return;const s=snapshot,container=$('chart'),svg=container.querySelector('svg');svg.replaceChildren();const w=Math.max(container.clientWidth,280),h=container.clientHeight;svg.setAttribute('aria-label',`${s.patient_label}. ${Number.isFinite(s.latest)?`Glucose at data cutoff ${number(s.latest)} mg/dL`:'No CGM reading at data cutoff'}. ${s.forecasts.map(f=>Number.isFinite(f.prediction)?`${f.horizon} minute forecast ${number(f.prediction)} mg/dL`:`${f.horizon} minute forecast withheld`).join('. ')}. Future observations hidden.`);svg.setAttribute('viewBox',`0 0 ${w} ${h}`);const left=42,right=w-12,top=18,bottom=h-34;const end=coord(s.issue_time)+65*60000,start=coord(s.data_cutoff)-360*60000;const markers=[];for(const f of s.forecasts){if(Number.isFinite(f.prediction))markers.push({time:f.target_time,glucose:f.prediction,color:f.horizon===30?'#dd7945':'#8867b2',name:`${s.synthetic?'Demo rule':'Ridge'} +${f.horizon} min`});if(Number.isFinite(f.persistence))markers.push({time:f.target_time,glucose:f.persistence,color:'#8c9ba6',name:'Persistence'});}const values=[...s.chart,...markers].map(p=>p.glucose).filter(Number.isFinite);let min=values.length?Math.floor((Math.min(...values)-10)/10)*10:60,max=values.length?Math.ceil((Math.max(...values)+10)/10)*10:200;if(max<=min)max=min+20;const x=t=>left+(coord(t)-start)/(end-start)*(right-left),y=v=>bottom-(v-min)/(max-min)*(bottom-top);
for(let i=0;i<=4;i++){const v=min+(max-min)*i/4,yy=y(v);svg.append(svgNode('line',{x1:left,x2:right,y1:yy,y2:yy,stroke:'#e7edf0'}),svgNode('text',{x:left-9,y:yy+4,'text-anchor':'end',fill:'#788996','font-size':10},Math.round(v)));}
for(let i=0;i<=6;i++){const time=start+(end-start)*i/6,d=new Date(time),label=`${String(d.getUTCHours()).padStart(2,'0')}:${String(d.getUTCMinutes()).padStart(2,'0')}`;svg.append(svgNode('text',{x:left+(right-left)*i/6,y:bottom+22,'text-anchor':'middle',fill:'#788996','font-size':10},label));}
const issueX=x(s.issue_time);svg.append(svgNode('line',{x1:issueX,x2:issueX,y1:top,y2:bottom,stroke:'#9eaeb7','stroke-dasharray':'4 4'}));let path='',previous=null;const cadence=s.sensor_delay_minutes?5:1;for(const p of s.chart){if(!Number.isFinite(p.glucose)){previous=null;continue;}const contiguous=previous&&coord(p.time)-coord(previous.time)<=cadence*60000;path+=`${contiguous?'L':'M'}${x(p.time).toFixed(2)},${y(p.glucose).toFixed(2)} `;previous=p;}svg.append(svgNode('path',{d:path,fill:'none',stroke:'#2587ba','stroke-width':2,'stroke-linejoin':'round'}));for(const p of markers){const px=x(p.time),py=y(p.glucose),dot=p.name==='Persistence'?svgNode('circle',{cx:px,cy:py,r:4.5,fill:p.color}):svgNode('path',{d:`M${px},${py-6} L${px+6},${py} L${px},${py+6} L${px-6},${py} Z`,fill:p.color});dot.append(svgNode('title',{},`${p.name}: ${number(p.glucose,1)} mg/dL · ${short(p.time)}`));svg.append(dot);}
drawEventMarkers(svg,s,x,top,bottom,start,end);const legend=$('legend');legend.replaceChildren();for(const [name,color] of [['Observed glucose','#2587ba'],...s.forecasts.map(f=>[`${s.synthetic?'Demo rule':'Ridge'} +${f.horizon} min`,f.horizon===30?'#dd7945':'#8867b2']),['Persistence','#8c9ba6']]){const span=document.createElement('span'),dot=document.createElement('i');dot.style.background=color;span.append(dot,document.createTextNode(name));legend.append(span);}if(s.event_research?.available){for(const [name,color] of [['Issued flag','#bd6435'],['Revealed onset','#963a63']]){const span=document.createElement('span'),dot=document.createElement('i');dot.style.background=color;span.append(dot,document.createTextNode(name));legend.append(span);}}const points=s.chart.filter(p=>Number.isFinite(p.glucose)),tip=container.querySelector('.chart-tooltip');svg.onpointermove=e=>{const rect=svg.getBoundingClientRect(),px=(e.clientX-rect.left)*w/rect.width;if(px<left||px>issueX||!points.length){tip.hidden=true;return;}let nearest=points[0];for(const p of points)if(Math.abs(x(p.time)-px)<Math.abs(x(nearest.time)-px))nearest=p;tip.textContent=`${short(nearest.time)} · ${number(nearest.glucose,1)} mg/dL`;tip.hidden=false;tip.style.left=`${Math.max(0,Math.min(container.clientWidth-170,px+10))}px`;tip.style.top=`${Math.max(0,y(nearest.glucose)-35)}px`;};svg.onpointerleave=()=>tip.hidden=true;}
new ResizeObserver(drawChart).observe($('chart'));
(async()=>{setBusy(true);try{catalog=await api('/api/catalog');populate();}catch(e){text('error',e.message);$('error').hidden=false;}finally{setBusy(false);}if($('patient').options.length)await selectPatient();})();

function drawEventMarkers(svg,s,x,top,bottom,start,end){
 const rows=s.event_research?.ledger||[],seen=new Set();
 for(const row of rows){
  if(row.research_flag&&coord(row.issued_at)>=start&&coord(row.issued_at)<=coord(s.issue_time)){
   const px=x(row.issued_at),marker=svgNode('path',{d:`M${px},${top+3} l9,0 l-9,10 Z`,fill:'#bd6435'});
   marker.append(svgNode('title',{},`${s.synthetic?'Illustrative':'Research'} flag issued ${short(row.issued_at)} · ${row.outcome}`));svg.append(marker);
  }
  if(row.event_at&&row.outcome==='Qualifying onset observed'&&!seen.has(row.event_at)&&coord(row.available_at)<=coord(s.issue_time)&&coord(row.event_at)>=start&&coord(row.event_at)<=end){
   seen.add(row.event_at);const px=x(row.event_at),line=svgNode('line',{x1:px,x2:px,y1:top+18,y2:bottom,stroke:'#963a63','stroke-dasharray':'2 4'});
   line.append(svgNode('title',{},`Revealed sustained onset ${short(row.event_at)}`));svg.append(line);
  }
 }
}
