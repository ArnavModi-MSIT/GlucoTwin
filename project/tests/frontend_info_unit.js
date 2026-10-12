'use strict';
// Exercise the real renderer with controlled replay results; no private data or browser dependencies.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

class Element{
  constructor(tag='div'){
    this.tagName=tag;this.children=[];this._text='';this.hidden=false;
    this.classList={toggle(){}};
  }
  set textContent(value){this._text=String(value);this.children=[];}
  get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
  replaceChildren(...children){this.children=children;this._text='';}
  append(...children){this.children.push(...children);}
  addEventListener(){}
  setAttribute(key,value){this[key]=value;}
}
const elements=new Map();
const document={
  addEventListener(){},
  getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},
  createElement(tag){return new Element(tag);},
  createElementNS(ns,tag){return new Element(tag);},
  querySelectorAll(){return [];},
  body:new Element('body')
};
const context=vm.createContext({document,fetch:()=>new Promise(()=>{}),ResizeObserver:class{observe(){}},console,setTimeout,clearTimeout});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8'),context);
const element=id=>elements.get(id);
const cgmFeatures=Array.from({length:22},(_,i)=>`cgm_feature_${i}`);
const time='2024-01-02T12:30:00';
const forecast=(horizon,prediction,status='Forecast issued')=>({
  issued_at:time,horizon,target_time:'2024-01-02T13:00:00',available_at:'2024-01-02T13:05:00',
  prediction,persistence:Number.isFinite(prediction)?120:null,status,
  outcome:'Pending',actual:null,ridge_error:null,persistence_error:null,
  model_inputs:[...cgmFeatures,'age_at_enrollment','sex_f']
});
const issued30=forecast(30,110),issued60=forecast(60,115);
const completed={...issued30,outcome:'Observed',actual:100,ridge_error:10,persistence_error:20};
const withheld=forecast(30,null,'Insufficient history');
const rbg={
  cohort:'rbg',patient_label:'Patient example',issue_time:time,data_cutoff:'2024-01-02T12:25:00',
  latest:120,coverage:13,profile:{Age:'50 years'},profile_note:'Enrollment context',sensor_delay_minutes:5,
  forecasts:[issued30,issued60],ledger:[completed,issued60,withheld],
  comparison:{evaluated:1,ridge_mae:10,persistence_mae:20}
};
context.render(rbg);
assert.equal(element('ledger-count').textContent,'Issued forecasts: 2 · Withheld attempts: 1');
assert.equal(element('ledger').children.length,3);
assert.equal(element('ledger').children[2].children[4].textContent,'Insufficient history');
assert.equal(element('ledger').children[2].children[5].textContent,'—');
assert.equal(element('ledger').children[0].children[9].textContent,'10.0');
assert.equal(element('ledger').children[0].children[10].textContent,'20.0');
assert.match(element('session-summary').textContent,/Forecast pairs evaluated: 1/);
assert.match(element('session-summary').textContent,/30 \/ 60 min combined/);
assert.equal(element('latest-note').textContent,'Reading at 12:25');
assert.equal(element('input-quality').hidden,true);

// A missing current-grid CGM sample must remain missing despite earlier observations.
const clinical=['age','gender_f','bmi','hba1c_pct','fasting_glucose'];
const hrFeatures=Array.from({length:9},(_,i)=>`hr_feature_${i}`);
const noReading={...forecast(60,null,'Insufficient history'),model_inputs:[...cgmFeatures,...clinical,...hrFeatures]};
const cgmacros={
  ...rbg,cohort:'cgmacros',data_cutoff:time,latest:null,coverage:12,sensor_delay_minutes:0,
  forecasts:[noReading],ledger:[noReading],comparison:{evaluated:0,ridge_mae:null,persistence_mae:null}
};
context.render(cgmacros);
assert.equal(element('latest').textContent,'—');
assert.equal(element('latest-note').textContent,'No CGM reading at 12:30');
assert.equal(element('coverage').textContent,'12/13');
assert.equal(element('forecast60').textContent,'—');
assert.equal(element('forecast-status').textContent,'Insufficient history');
assert.equal(element('ledger-count').textContent,'Issued forecasts: 0 · Withheld attempts: 1');
assert.equal(element('forecast30-card').hidden,true);
assert.equal(element('input-quality').hidden,false);
assert.match(element('input-quality').textContent,/HR coverage, last hour: unavailable/);
assert.match(element('session-summary').textContent,/Forecast pairs evaluated: 0/);
assert.doesNotMatch(element('session-summary').textContent,/30 \/ 60/);

// Known HR coverage is shown separately from CGM coverage without becoming an invented prediction.
context.render({...cgmacros,forecasts:[{...noReading,hr_fraction:0.5}]});
assert.match(element('input-quality').textContent,/HR coverage, last hour: 50\.0%/);
assert.equal(element('forecast60').textContent,'—');
assert.equal(element('ledger-count').textContent,'Issued forecasts: 0 · Withheld attempts: 1');
console.log('Frontend information checks passed: issued/withheld rows, paired session stats, missing CGM and HR coverage.');

// Synthetic mode must never inherit the measured study's model or evidence labels.
context.render({...rbg,cohort:'demo',synthetic:true,event_research:{available:true,current:{score:190,cutoff:180,status:'Illustrative flag',window_start:time,window_end:time},metadata:{},ledger:[]}});
assert.match(element('research-title').textContent,/Fictional patient/);
assert.match(element('forecast60-note').textContent,/Illustrative trend/);
assert.match(element('evidence').textContent,/not XGBoost/);
assert.equal(element('event-evidence').hidden,true);
assert.equal(element('forecast30-card').hidden,false);

// Issued flags are visible immediately; onset markers require matured outcomes and deduplicate episodes.
const chart=new Element('svg'),eventAt='2024-01-02T12:10:00';
const eventRow={issued_at:'2024-01-02T12:00:00',available_at:'2024-01-02T12:45:00',research_flag:true,event_at:eventAt,outcome:'Qualifying onset observed'};
const chartSnapshot={issue_time:time,event_research:{ledger:[eventRow]}};
context.drawEventMarkers(chart,chartSnapshot,()=>100,0,200,Date.parse('2024-01-02T11:00:00Z'),Date.parse('2024-01-02T13:00:00Z'));
assert.equal(chart.children.filter(e=>e.tagName==='line').length,0);
chart.replaceChildren();
context.drawEventMarkers(chart,{...chartSnapshot,issue_time:'2024-01-02T12:50:00',event_research:{ledger:[eventRow,eventRow]}},()=>100,0,200,Date.parse('2024-01-02T11:00:00Z'),Date.parse('2024-01-02T13:00:00Z'));
assert.equal(chart.children.filter(e=>e.tagName==='line').length,1);
console.log('Synthetic labels and causal event marker checks passed.');

(async()=>{
 const calls=[],scheduled=[];
 context.api=async(path,body)=>{calls.push({path,body});return rbg;};
 context.setTimeout=(fn)=>{scheduled.push(fn);return 1;};
 context.clearTimeout=()=>{};
 vm.runInContext('snapshot=null;playing=true;busy=false;drawChart=()=>{};',context);
 await context.playbackTick();
 assert.equal(calls.length,1);assert.equal(calls[0].body.minutes,5);
 assert.equal(scheduled.length,1);
 context.stopPlayback();await scheduled[0]();
 assert.equal(calls.length,1);
 context.api=async()=>{throw new Error('test failure');};
 vm.runInContext('playing=true;',context);await context.playbackTick();
 assert.equal(element('play').textContent,'▶ Play replay');
 assert.equal(scheduled.length,1);
 console.log('Playback advances once per completed request and stops on pause/error.');
})().catch(error=>{console.error(error);process.exitCode=1;});
