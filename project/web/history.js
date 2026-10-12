'use strict';
// Descriptive observed-hour inspection. No future reading, treatment or model input.
(function(root){
  const ms=t=>typeof t==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(t)?Date.parse(t+'Z'):NaN;
  const number=(v,d=1)=>Number.isFinite(v)?v.toFixed(d):'—';
  const percent=v=>Number.isFinite(v)?`${(100*v).toFixed(1)}%`:'—';
  function availableHours(snapshot){
    const history=snapshot.historical_patterns,cutoff=ms(snapshot.data_cutoff),issue=ms(snapshot.issue_time);
    if(!history||history.through!==snapshot.data_cutoff||!Number.isFinite(cutoff)||!Number.isFinite(issue)||cutoff>issue)return [];
    const start=Date.parse(snapshot.data_cutoff.slice(0,10)+'T00:00:00Z')-6*86400000,seen=new Set();
    return (history.hourly||[]).filter(r=>{
      const hourStart=Date.parse(r.date+'T00:00:00Z')+r.hour*3600000,key=r.date+':'+r.hour;
      const valid=/^\d{4}-\d{2}-\d{2}$/.test(r.date)&&Number.isInteger(r.hour)&&r.hour>=0&&r.hour<24&&hourStart>=start&&hourStart<=cutoff&&ms(r.first_checkpoint)>=hourStart&&ms(r.last_checkpoint)<hourStart+3600000&&ms(r.first_checkpoint)<=ms(r.last_checkpoint)&&ms(r.last_checkpoint)<=cutoff&&Number.isInteger(r.samples)&&Number.isInteger(r.expected)&&r.samples>=0&&r.samples<=r.expected&&r.expected>0&&r.expected<=12&&!seen.has(key);
      if(valid)seen.add(key);return valid;
    }).map(r=>({...r})).sort((a,b)=>a.date.localeCompare(b.date)||a.hour-b.hour);
  }
  function comparable(r,cutoff){return !!r&&r.complete_hour===true&&r.expected===12&&r.samples>=10&&Number.isFinite(r.mean)&&Date.parse(r.date+'T00:00:00Z')+(r.hour+1)*3600000<=ms(cutoff);}
  function cellKind(r,cutoff){if(!comparable(r,cutoff))return 'unavailable';return r.mean<70?'low':r.mean>180?'high':'reference';}
  function compareDays(rows,a,b,cutoff){
    if(!a||!b||a===b)return {pairs:[],a_mean:null,b_mean:null,difference:null};
    const left=new Map(rows.filter(r=>r.date===a&&comparable(r,cutoff)).map(r=>[r.hour,r])),right=new Map(rows.filter(r=>r.date===b&&comparable(r,cutoff)).map(r=>[r.hour,r]));
    const pairs=[...left].filter(([hour])=>right.has(hour)).map(([hour,r])=>({hour,a:r.mean,b:right.get(hour).mean})).sort((x,y)=>x.hour-y.hour);
    const mean=key=>pairs.length?pairs.reduce((n,r)=>n+r[key],0)/pairs.length:null,a_mean=mean('a'),b_mean=mean('b');
    return {pairs,a_mean,b_mean,difference:pairs.length?a_mean-b_mean:null};
  }
  function comparisonLines(rows,date,cutoff){
    const hours=rows.filter(r=>r.date===date&&comparable(r,cutoff));let runs=[],run=[];
    for(const r of hours){if(run.length&&r.hour!==run.at(-1).hour+1){runs.push(run);run=[];}run.push(r);}if(run.length)runs.push(run);return runs;
  }
  const model={availableHours,comparable,cellKind,compareDays,comparisonLines};
  if(typeof module!=='undefined')module.exports=model;
  if(!root.document)return;
  const d=root.document,$=id=>d.getElementById(id),NS='http://www.w3.org/2000/svg';
  let context=null;
  const section=d.createElement('section');section.className='hourly-explorer';section.id='hourly-explorer';
  section.innerHTML='<div class="card-heading"><div><h3>Hourly history explorer</h3><p>Choose a past hour to inspect readings and coverage. Cell colour describes the hourly mean; individual readings may cross other bands.</p></div><a data-export hidden href="/api/export?format=history">Download hourly CSV</a></div><div class="hourly-legend"><span>Below 70</span><span>70–180 mg/dL</span><span>Above 180</span><span>Unavailable / partial</span></div><div class="hourly-scroll"><table class="hourly-grid"><caption>Observed hourly means · last seven study dates</caption><thead id="hourly-head"></thead><tbody id="hourly-body"></tbody></table></div><p id="hourly-note"></p><div class="day-comparison"><h3>Compare two observed days</h3><div class="day-selectors"><label for="history-day-a">Day A<select id="history-day-a"></select></label><label for="history-day-b">Day B<select id="history-day-b"></select></label></div><p id="day-comparison-summary" role="status"></p><svg id="day-comparison-svg" role="img" aria-label="Observed hourly means on two study dates"></svg><p id="day-comparison-legend"></p><p>Comparison uses complete hours with at least 10/12 readings in both dates. Means give equal weight to matched hours. Lines describe each date’s observed history, not a forecast or a treatment effect; gaps remain gaps.</p></div>';
  $('patterns-provenance').after(section);
  const dialog=d.createElement('dialog');dialog.className='hour-detail';dialog.setAttribute('aria-labelledby','hour-detail-title');
  dialog.innerHTML='<div class="card-heading"><h2 id="hour-detail-title">Observed hour details</h2><button id="hour-detail-close" type="button">Close details</button></div><p id="hour-detail-date"></p><dl id="hour-detail-values"></dl><p id="hour-detail-note"></p>';
  d.body.append(dialog);$('hour-detail-close').onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>{$('hour-detail-values').replaceChildren();$('hour-detail-date').textContent='';$('hour-detail-note').textContent='';});
  function detail(r){
    if(!context)return;root.stopPlayback?.();$('hour-detail-date').textContent=`${r.date} · ${String(r.hour).padStart(2,'0')}:00–${String(r.hour+1).padStart(2,'0')}:00 · Available through ${context.snapshot.data_cutoff.replace('T',' ')}`;
    const dl=$('hour-detail-values');dl.replaceChildren();
    for(const [name,value] of [['Observed / expected checkpoints',`${r.samples}/${r.expected}`],['Coverage',percent(r.coverage)],['Mean',number(r.mean)+' mg/dL'],['Minimum / maximum',`${number(r.minimum)} / ${number(r.maximum)} mg/dL`],['Below 70',percent(r.low_fraction)],['70–180',percent(r.reference_fraction)],['Above 180',percent(r.high_fraction)],['Complete hour',r.complete_hour?'Yes':'No · partial supplied/current hour'],['Comparable coverage',comparable(r,context.snapshot.data_cutoff)?'Yes':'No'],['First / last available checkpoint',r.first_checkpoint.slice(11,16)+' / '+r.last_checkpoint.slice(11,16)]]){const row=d.createElement('div'),dt=d.createElement('dt'),dd=d.createElement('dd');dt.textContent=name;dd.textContent=value;row.append(dt,dd);dl.append(row);}
    $('hour-detail-note').textContent='Percentages and mean use observed readings only. No missing values are filled. These reference bands are not individual care targets; an hourly mean does not establish an adverse event.';
    dialog.showModal();
  }
  function node(tag,attrs,text){const el=d.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));if(text!==undefined)el.textContent=text;return el;}
  function drawComparison(){
    if(!context)return;const a=$('history-day-a').value,b=$('history-day-b').value,cutoff=context.snapshot.data_cutoff,rows=context.rows,comparison=compareDays(rows,a,b,cutoff),svg=$('day-comparison-svg');svg.replaceChildren();svg.setAttribute('viewBox','0 0 800 260');
    $('day-comparison-legend').textContent=`Blue: ${a||'Day A'} · Orange: ${b||'Day B'} · Study hours 00–23`;
    $('day-comparison-summary').textContent=!b?'Two observed study dates are required.':a===b?'Choose two different dates.':comparison.pairs.length?`${comparison.pairs.length} matched hours · A mean ${number(comparison.a_mean)} mg/dL · B mean ${number(comparison.b_mean)} mg/dL · A minus B ${number(comparison.difference)} mg/dL`:'No comparable complete hours in both dates.';
    const series=[{date:a,color:'#2587ba'},{date:b,color:'#dd7945'}].map(s=>({...s,runs:comparisonLines(rows,s.date,cutoff)})),values=series.flatMap(s=>s.runs.flatMap(run=>run.map(r=>r.mean)));
    if(!b||a===b||!values.length){svg.setAttribute('aria-label','No comparable day chart available');svg.append(node('text',{x:20,y:80,fill:'#6c7b87'},'Select two dates with complete covered hours.'));return;}
    svg.setAttribute('aria-label',`Observed hourly means for ${a} and ${b}. ${comparison.pairs.length} matched hours. Future hours and insufficient coverage are excluded.`);
    const low=Math.floor((Math.min(...values)-10)/10)*10,high=Math.ceil((Math.max(...values)+10)/10)*10,x=h=>80+h/23*670,y=v=>210-(v-low)/(high-low)*180;
    for(let i=0;i<=4;i++){const value=low+(high-low)*i/4,at=y(value);svg.append(node('line',{x1:80,x2:750,y1:at,y2:at,stroke:'#e2e9eb'}),node('text',{x:70,y:at+4,'text-anchor':'end',fill:'#6c7b87','font-size':11},number(value,0)));}
    svg.append(node('text',{x:80,y:16,fill:'#6c7b87','font-size':11},'Glucose · mg/dL'));
    for(const h of [0,6,12,18,23])svg.append(node('text',{x:x(h),y:235,'text-anchor':'middle',fill:'#6c7b87','font-size':11},String(h).padStart(2,'0')+':00'));
    for(const s of series)for(const run of s.runs){svg.append(node('polyline',{points:run.map(r=>`${x(r.hour)},${y(r.mean)}`).join(' '),fill:'none',stroke:s.color,'stroke-width':2}));for(const r of run){const dot=node('circle',{cx:x(r.hour),cy:y(r.mean),r:3,fill:s.color});dot.append(node('title',{},`${s.date} · ${r.hour}:00 · Mean ${number(r.mean)} mg/dL · ${r.samples}/${r.expected} readings`));svg.append(dot);}}
  }
  for(const id of ['history-day-a','history-day-b'])$(id).addEventListener('change',drawComparison);
  root.GlucoHistory={update(snapshot){
    const key=JSON.stringify([snapshot.cohort,String(snapshot.patient_id)]),changed=context?.key!==key,previousA=changed?'':$('history-day-a').value,previousB=changed?'':$('history-day-b').value;
    if(dialog.open)dialog.close();const rows=availableHours(snapshot);context={key,snapshot,rows};section.hidden=!rows.length;if(!rows.length)return;
    const dates=[...new Set(rows.map(r=>r.date))],covered=dates.filter(date=>rows.filter(r=>r.date===date&&comparable(r,snapshot.data_cutoff)).length===24),defaults=covered.length>=2?covered.slice(-2).reverse():dates.slice(-2).reverse();
    for(const [id,previous,index] of [['history-day-a',previousA,0],['history-day-b',previousB,1]]){const select=$(id);select.replaceChildren();if(index===1&&dates.length<2){const option=d.createElement('option');option.value='';option.textContent='No second date';select.append(option);}for(const date of [...dates].reverse()){const option=d.createElement('option');option.value=date;option.textContent=date;select.append(option);}select.value=dates.includes(previous)?previous:defaults[index]||'';}
    const head=$('hourly-head'),body=$('hourly-body');head.replaceChildren();body.replaceChildren();const header=d.createElement('tr');for(const label of ['Study date',...Array.from({length:24},(_,h)=>String(h).padStart(2,'0'))]){const th=d.createElement('th');th.textContent=label;th.scope='col';header.append(th);}head.append(header);
    for(const date of [...dates].reverse()){const tr=d.createElement('tr'),label=d.createElement('th');label.scope='row';label.textContent=date;tr.append(label);for(let hour=0;hour<24;hour++){const td=d.createElement('td'),button=d.createElement('button'),r=rows.find(r=>r.date===date&&r.hour===hour);button.type='button';button.className='hour-cell '+cellKind(r,snapshot.data_cutoff);button.textContent=comparable(r,snapshot.data_cutoff)?number(r.mean,0):'—';const future=Date.parse(date+'T00:00:00Z')+hour*3600000>ms(snapshot.data_cutoff),description=r?`${r.samples}/${r.expected} observed readings${r.complete_hour?'':' · partial hour'}`:future?'Future hour hidden':'No supplied history';button.title=`${date} · ${String(hour).padStart(2,'0')}:00 · ${description}`;button.setAttribute('aria-label',button.title+(comparable(r,snapshot.data_cutoff)?` · Mean ${number(r.mean)} mg/dL`:''));button.disabled=!r;if(r)button.onclick=()=>detail(r);td.append(button);tr.append(td);}body.append(tr);}
    $('hourly-note').textContent='Colour and displayed cell means require a complete hour and at least 10/12 readings. Click a supplied grey hour to inspect partial or missing coverage. Future hours contain no observations. No gaps are filled.';
    drawComparison();
  },refreshControls(){for(const button of section.querySelectorAll('.hour-cell'))if(!button.onclick)button.disabled=true;}};
})(typeof window!=='undefined'?window:globalThis);
