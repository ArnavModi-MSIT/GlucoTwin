'use strict';
(function(root){
  const escape=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const time=t=>typeof t==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(t)?Date.parse(t+'Z'):NaN;
  const n=v=>v.toFixed(2);
  function plot(title,values,start,end,draw,ticks){
    const low=Math.floor((Math.min(...values)-10)/10)*10,high=Math.ceil((Math.max(...values)+10)/10)*10;
    const x=t=>56+(t-start)/(end-start)*864,y=v=>230-(v-low)/(high-low)*200;
    let axes='';
    for(let i=0;i<=4;i++){const value=low+(high-low)*i/4;axes+=`<line x1="56" x2="920" y1="${n(y(value))}" y2="${n(y(value))}" stroke="#e2e9eb"/><text x="46" y="${n(y(value)+4)}" text-anchor="end">${escape(value.toFixed(0))}</text>`;}
    for(const [at,label] of ticks)axes+=`<text x="${n(x(at))}" y="252" text-anchor="middle">${escape(label)}</text>`;
    return `<figure><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 275" role="img" aria-label="${escape(title)}"><title>${escape(title)}</title><g font-family="system-ui,sans-serif" font-size="11" fill="#6c7b87"><text x="56" y="15">Glucose · mg/dL</text>${axes}${draw(x,y)}</g></svg><figcaption>${escape(title)}</figcaption></figure>`;
  }
  function timeline(snapshot){
    const cutoff=time(snapshot.data_cutoff),issue=time(snapshot.issue_time);
    if(!Number.isFinite(cutoff)||!Number.isFinite(issue)||cutoff>issue)return '<p>Timeline unavailable.</p>';
    const start=cutoff-6*3600000;
    const points=(snapshot.chart||[]).filter(p=>time(p.time)>=start&&time(p.time)<=cutoff).sort((a,b)=>time(a.time)-time(b.time));
    const known=points.filter(p=>Number.isFinite(p.glucose));
    if(!known.length)return '<p>No observed readings in this timeline window.</p>';
    const forecasts=(snapshot.forecasts||[]).filter(p=>[30,60].includes(p.horizon)&&Number.isFinite(p.prediction)&&time(p.issued_at)<=issue&&time(p.target_time)>issue&&time(p.target_time)<=issue+3600000);
    const end=issue+3600000,values=known.map(p=>p.glucose).concat(forecasts.flatMap(p=>Number.isFinite(p.persistence)?[p.prediction,p.persistence]:[p.prediction]));
    const ticks=Array.from({length:7},(_,i)=>{const t=start+(end-start)*i/6;return [t,new Date(t).toISOString().slice(11,16)];});
    const svg=plot('Observed six-hour history and issued estimates',values,start,end,(x,y)=>{
      let path='',previous=null;
      for(const p of points){if(!Number.isFinite(p.glucose)){previous=null;continue;}const t=time(p.time);path+=`${previous===null||t-previous>300000?'M':'L'}${n(x(t))},${n(y(p.glucose))} `;previous=t;}
      let marks=`<path data-series="observed" d="${path}" fill="none" stroke="#2587ba" stroke-width="2"/><line x1="${n(x(issue))}" x2="${n(x(issue))}" y1="30" y2="230" stroke="#8c9ba6" stroke-dasharray="4 4"/>`;
      for(const p of forecasts){const at=x(time(p.target_time)),color=p.horizon===30?'#dd7945':'#8867b2';marks+=`<circle cx="${n(at)}" cy="${n(y(p.prediction))}" r="5" fill="${color}"><title>+${p.horizon} min estimate: ${n(p.prediction)} mg/dL</title></circle>`;if(Number.isFinite(p.persistence))marks+=`<circle cx="${n(at)}" cy="${n(y(p.persistence))}" r="3" fill="#8c9ba6"/>`;}
      return marks;
    },ticks);
    return svg+'<p class="muted">Blue: observed readings; orange/purple: +30/+60-minute estimates; grey: persistence. Dashed: issue time. Missing readings remain gaps. Future target observations are excluded.</p>';
  }
  function historyProfile(snapshot){
    const history=snapshot.historical_patterns;
    if(!history||history.through!==snapshot.data_cutoff)return '';
    const hours=(history.profile?.hours||[]).filter(p=>Number.isInteger(p.hour)&&p.hour>=0&&p.hour<24&&p.covered_days>=3&&[p.p10,p.median,p.p90].every(Number.isFinite)).sort((a,b)=>a.hour-b.hour);
    if(!hours.length)return '<p>Hourly profile unavailable: at least three sufficiently covered hours from different days are required.</p>';
    return plot('Past hourly median and 10th–90th percentiles',hours.flatMap(p=>[p.p10,p.p90,p.median]),0,24,(x,y)=>{
      let paths='',runs=[],run=[];
      for(const p of hours){if(run.length&&p.hour!==run.at(-1).hour+1){runs.push(run);run=[];}run.push(p);}if(run.length)runs.push(run);
      for(const rows of runs){const upper=rows.map(p=>`${n(x(p.hour+.5))},${n(y(p.p90))}`),lower=[...rows].reverse().map(p=>`${n(x(p.hour+.5))},${n(y(p.p10))}`);paths+=`<path d="M${upper.join(' L')} L${lower.join(' L')} Z" fill="#2587ba" opacity=".15"/><path d="M${rows.map(p=>`${n(x(p.hour+.5))},${n(y(p.median))}`).join(' L')}" fill="none" stroke="#2587ba" stroke-width="2"/>`;for(const p of rows)paths+=`<circle cx="${n(x(p.hour+.5))}" cy="${n(y(p.median))}" r="2.5" fill="#2587ba"/>`;}
      return paths;
    },[0,6,12,18,24].map(h=>[h,String(h).padStart(2,'0')+':00']))+'<p class="muted">Descriptive past distributions from available history, not forecast uncertainty or a prediction of tomorrow.</p>';
  }
  const api={timeline,historyProfile};
  if(typeof module!=='undefined')module.exports=api;
  root.GlucoReportCharts=api;
})(typeof window!=='undefined'?window:globalThis);
