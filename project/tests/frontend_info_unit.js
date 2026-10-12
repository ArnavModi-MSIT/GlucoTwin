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
const replayBookmark={schema:'glucotwin-tab-replay-v1',cohort:'demo',pid:'showcase',token:'a'.repeat(32),issue_time:'2024-01-15T08:35:00'};
assert.equal(context.readSavedReplay({getItem:()=>null}),null);
assert.equal(context.readSavedReplay({getItem:()=>JSON.stringify(replayBookmark)}).pid,'showcase');
for(const invalid of [{...replayBookmark,token:'not-a-session'}, {...replayBookmark,cohort:'unknown'}, {...replayBookmark,pid:''}, {...replayBookmark,issue_time:null}])assert.throws(()=>context.readSavedReplay({getItem:()=>JSON.stringify(invalid)}));
assert.throws(()=>context.readSavedReplay({getItem:()=>'x'.repeat(2049)}));
console.log('Replay bookmark validation checks passed.');
(async()=>{
 const held=new Set(),locks={async request(name,options,callback){if(held.has(name))return callback(null);held.add(name);try{return await callback({name});}finally{held.delete(name);}}};
 context.navigator={locks};
 const other=vm.createContext({document,navigator:{locks},fetch:()=>new Promise(()=>{}),ResizeObserver:class{observe(){}},console,setTimeout,clearTimeout});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8'),other);
 assert.equal(await context.ownReplay('test-owned-replay'),true);
 assert.equal(await other.ownReplay('test-owned-replay'),false);
 assert.equal(await context.ownReplay('test-new-replay'),true);
 assert.equal(await other.ownReplay('test-owned-replay'),true);
 console.log('Replay ownership checks passed: active-tab isolation and released locks.');
})().catch(error=>{console.error(error);process.exitCode=1;});
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

context.render({...rbg,historical_patterns:{through:time,note:'Past-only history',observed_samples:58,periods:[{start_hour:0,end_hour:6,eligible_days:2,high_days:2,low_days:0,description:'Repeated high readings'}],daily:[{date:'2024-01-02',samples:58,expected:72,coverage:58/72,mean:190,low_fraction:0,reference_fraction:.2,high_fraction:.8}]}});
assert.equal(element('patterns-panel').hidden,false);
assert.match(element('patterns-periods').textContent,/Repeated high readings/);
assert.match(element('patterns-days').textContent,/58\/7280.6%190.0 mg\/dL/);
context.render(rbg);assert.equal(element('patterns-panel').hidden,true);
console.log('Historical pattern renderer checks passed: coverage, descriptive periods and missing-payload handling.');

const actionSvg=new Element('svg');
const actionRows=[
 {id:1,kind:'meal',at:'2024-01-02T12:00',created_at_replay:'2024-01-02T12:05',note:'Recorded lunch'},
 {id:2,kind:'medication',at:'2024-01-02T12:10',created_at_replay:'2024-01-02T12:15',note:'Recorded medication'},
 {id:3,kind:'meal_plan',at:'2024-01-02T12:00',created_at_replay:'2024-01-02T12:05',note:'Planned only'},
 {id:4,kind:'meal',at:'2024-01-02T13:00',created_at_replay:'2024-01-02T13:00',note:'Future action'},
 {id:5,kind:'meal',at:'2024-01-02T12:00',created_at_replay:'2024-01-02T13:00',note:'Future-created note'},
 {id:6,kind:'meal',at:'2024-01-02T05:00',created_at_replay:'2024-01-02T05:05',note:'Outside visible history'}
];
context.GlucoCare={timelineEntries:()=>actionRows};
element('show-care-markers').checked=true;
const selectedActions=context.drawCareMarkers(actionSvg,{issue_time:time},()=>100,0,200,Date.parse('2024-01-02T06:25:00Z'));
assert.equal(selectedActions.length,2);assert.equal(actionSvg.children.length,2);
assert.match(actionSvg.children[0]['aria-label'],/User-reported meal log/);
assert.match(actionSvg.children[1]['aria-label'],/medication taken log/);
assert.doesNotMatch(element('care-chart-notes').textContent,/Future|Planned|Outside/);
element('show-care-markers').checked=false;actionSvg.replaceChildren();
assert.equal(context.drawCareMarkers(actionSvg,{issue_time:time},()=>100,0,200,Date.parse('2024-01-02T06:25:00Z')).length,0);
assert.equal(actionSvg.children.length,0);assert.match(element('care-marker-count').textContent,/2 logged actions/);
delete context.GlucoCare;
console.log('Timeline annotation renderer checks passed: shapes, labels, future exclusion and toggle.');

context.renderUncertainty({synthetic:false,uncertainty_note:'Exploratory',forecasts:[{horizon:30,interval_lower:80,interval_upper:140,interval_assessment_coverage:.89,interval_assessment_patients:17}]});
assert.ok(elements.get('uncertainty-ranges').children[0].textContent.includes('89.0%'));
context.renderUncertainty({synthetic:true,forecasts:[]});
assert.ok(elements.get('uncertainty-note').textContent.includes('fictional'));
console.log('Uncertainty renderer checks passed.');

context.renderExplanations({...rbg,forecasts:[{horizon:30,explanation:{persistence:100,reference_offset:10,groups:{glucose:5,clinical:2,heart_rate:-1,missingness:0},reconstructed_prediction:116,imputed:['age'],note:'Arithmetic only'}}]});
assert.ok(element('forecast-explanations').textContent.includes('116.0'));
context.renderHistoryProfile({observed_days:3,complete_covered_days:3,samples:800,expected:1000,coverage:.8,mean:100,std:10,coefficient_variation_pct:10,overnight:{samples:50,expected:60,mean:90,below70_fraction:null},note:'History only',hours:[]});
assert.ok(!element('profile-night').textContent.includes('below 70: 0.0%'));
vm.runInContext("catalog={cohorts:{demo:[{id:'rise',label:'Rising glucose'}]}};",context);
context.renderOverview();assert.equal(element('overview-rows').children.length,1);
console.log('Overview, explanation and historical profile render checks passed.');

context.render({...rbg,cohort:'imported',synthetic:true,imported:true,model_name:'Persistence baseline · no trained model',import_quality:{input_rows:40,gap_slots:1,blank_rows:1,input_unit:'mg/dL'},profile_note:'User-supplied readings',event_research:null});
assert.ok(element('research-title').textContent.includes('Imported patient'));assert.ok(element('model-column').textContent.includes('Persistence'));
assert.equal(element('event-research').hidden,true);assert.ok(!element('evidence').textContent.includes('158 training'));
console.log('Imported-record labels and benchmark separation checks passed.');
