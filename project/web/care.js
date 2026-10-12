'use strict';
// User annotations only: never supplied to a forecasting model or treatment controller.
(function(root){
  const states=new Map(),mealCache=new Map();
  const storagePrefix='glucotwin-care-local-v1:';
  function shiftDate(value,days){const date=new Date(timestamp(value)+':00Z');date.setUTCDate(date.getUTCDate()+days);return timestamp(date.toISOString().slice(0,16));}
  function timestamp(value){
    if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value))throw Error('Enter a valid date and time.');
    const date=new Date(value+':00Z');
    if(!Number.isFinite(+date)||date.toISOString().slice(0,16)!==value)throw Error('Enter a valid date and time.');
    return value;
  }
  function add(key,input,now){
    const kind=input.kind;
    if(!['meal','medication','schedule','meal_plan','review','question','follow_up'].includes(kind))throw Error('Choose an entry type.');
    const at=timestamp(input.at),issue=timestamp(now.slice(0,16));
    const note=String(input.note||'').trim();
    if(!note||note.length>300)throw Error('Enter a description of 1–300 characters.');
    if(['meal','medication','review','question'].includes(kind)&&at>issue)throw Error('An observed log cannot be later than replay time.');
    if(kind==='schedule'&&!input.confirmed)throw Error('Confirm this reminder copies an existing prescribed schedule.');
    const repeats=input.repeat_days??1;
    if(![1,3].includes(repeats)||repeats===3&&!['schedule','meal_plan'].includes(kind))throw Error('Daily repetition is only available for plans and prescribed reminders.');
    const rows=states.get(key)||[];
    if(rows.length+repeats>200)throw Error('This patient has reached the 200-entry limit. Export or remove entries first.');
    const firstId=rows.reduce((m,r)=>Math.max(m,r.id),0)+1;
    const added=Array.from({length:repeats},(_,i)=>({id:firstId+i,kind,at:shiftDate(at,i),note,created_at_replay:issue,completed_at:null}));
    states.set(key,[...rows,...added]);return {...added[0]};
  }
  function entries(key){return (states.get(key)||[]).map(r=>({...r}));}
  function remove(key,id){states.set(key,(states.get(key)||[]).filter(r=>r.id!==id));const cache=mealCache.get(key);if(cache)for(const [tag,r] of cache)if(r.id===id)cache.delete(tag);}
  function complete(key,id,now){const at=timestamp(now.slice(0,16));const r=(states.get(key)||[]).find(v=>v.id===id);if(!r||!['schedule','follow_up'].includes(r.kind)||r.at>at||r.created_at_replay>at)throw Error('Only a due reminder or follow-up can be marked complete.');r.completed_at=at;}
  function status(row,now){const at=now.slice(0,16);if(row.created_at_replay>at)return 'Entered after replay time';if(row.kind==='meal_plan')return row.at>at?'Planned':'Planned time reached';if(['review','question'].includes(row.kind))return row.at>at||row.created_at_replay>at?'Later than replay time':'User-entered review';if(row.kind==='follow_up'){if(row.completed_at&&row.completed_at<=at)return 'Completed';return row.at<=at?'Follow-up due':'Upcoming';}if(row.kind!=='schedule')return row.at>at?'Later than replay time':'User-reported';if(row.completed_at&&row.completed_at<=at)return 'Reviewed';return row.at<=at?'Due in replay':'Upcoming';}
  function planningDays(key,now){const start=timestamp(now.slice(0,10)+'T00:00');return Array.from({length:3},(_,i)=>{const date=shiftDate(start,i).slice(0,10);return {date,entries:entries(key).filter(r=>['schedule','meal_plan','follow_up'].includes(r.kind)&&r.created_at_replay<=now.slice(0,16)&&r.at.slice(0,10)===date).sort((a,b)=>a.at.localeCompare(b.at)||a.id-b.id)};});}
  function timelineEntries(key,now){const issue=timestamp(now.slice(0,16));return entries(key).filter(r=>['meal','medication'].includes(r.kind)&&r.at<=issue&&r.created_at_replay<=issue).sort((a,b)=>a.at.localeCompare(b.at)||a.id-b.id);}
  function mealReview(snapshot,key){
    const ms=value=>Date.parse(value.length===16?value+':00Z':value+'Z');
    const cutoff=Math.min(ms(snapshot.data_cutoff),ms(snapshot.issue_time)),step=300000;
    if(!Number.isFinite(cutoff))return [];
    const readings=new Map();
    for(const r of snapshot.chart||[]){const t=ms(r.time);if(Number.isFinite(t)&&t<=cutoff&&Number.isFinite(r.glucose)&&Math.abs((cutoff-t)%step)<1)readings.set(t,r.glucose);}
    return timelineEntries(key,snapshot.issue_time).filter(r=>r.kind==='meal').map(r=>{
      const at=ms(r.at),end=at+120*60000;
      const baseline=[...readings].filter(([t])=>t<=at&&t>=at-15*60000).sort((a,b)=>b[0]-a[0])[0];
      const observed=[...readings].filter(([t])=>t>at&&t<=end);
      const maximum=observed.length?Math.max(...observed.map(([,v])=>v)):null;
      const finished=cutoff>=end,covered=observed.length>=20;
      const computed={at:r.at,note:r.note,baseline:baseline?.[1]??null,maximum,samples:observed.length,expected:24,
        difference:finished&&covered&&baseline?maximum-baseline[1]:null,
        status:!finished?'Collecting two-hour window':!covered?'Insufficient visible coverage':!baseline?'Baseline unavailable':'Window available',retained:false};
      const cache=mealCache.get(key)||new Map(),tag=JSON.stringify([r.id,r.at,r.note,r.created_at_replay]),saved=cache.get(tag);
      if(saved&&ms(saved.through)<=cutoff&&(snapshot.chart||[]).length&&ms(snapshot.chart[0].time)>end)return {...saved,retained:true};
      if(finished&&computed.samples>0&&(!saved||computed.samples>=saved.samples)){cache.set(tag,{...computed,id:r.id,through:new Date(cutoff).toISOString().slice(0,19)});mealCache.set(key,cache);}
      return computed;
    });
  }
  function validateImport(payload,identity){
    if(!payload||typeof payload!=='object'||Array.isArray(payload)||!['glucotwin-user-notes-v1','glucotwin-user-notes-v2','glucotwin-user-notes-v3'].includes(payload.schema))throw Error('Choose a GlucoTwin notes export (version 1, 2 or 3).');
    if(typeof payload.patient_id!=='string'||payload.cohort!==identity.cohort||payload.patient_id!==String(identity.pid))throw Error('This file belongs to a different patient or dataset. Select that patient before importing.');
    if(typeof payload.replay_time!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00$/.test(payload.replay_time))throw Error('The export has an invalid replay time.');
    timestamp(payload.replay_time.slice(0,16));
    if(!Array.isArray(payload.entries)||payload.entries.length>200)throw Error('An export must contain at most 200 entries.');
    const ids=new Set();
    return payload.entries.map(r=>{
      if(!r||typeof r!=='object'||Array.isArray(r)||!Number.isSafeInteger(r.id)||r.id<1||ids.has(r.id))throw Error('The export has invalid or duplicate entry identifiers.');
      ids.add(r.id);
      if(!(payload.schema==='glucotwin-user-notes-v3'?['meal','medication','schedule','meal_plan','review','question','follow_up']:['meal','medication','schedule','meal_plan']).includes(r.kind)||typeof r.note!=='string'||!r.note.trim()||r.note.trim().length>300)throw Error('The export contains an invalid entry type or description.');
      const at=timestamp(r.at),created=timestamp(r.created_at_replay);
      if(['meal','medication','review','question'].includes(r.kind)&&at>created)throw Error('A recorded action is dated after its entry time.');
      const completed=r.completed_at===null?null:timestamp(r.completed_at);
      if(completed!==null&&(!['schedule','follow_up'].includes(r.kind)||completed<at||completed<created))throw Error('The export has an invalid reminder review time.');
      return {id:r.id,kind:r.kind,at,note:r.note.trim(),created_at_replay:created,completed_at:completed};
    });
  }
  function parseImport(text,identity){
    if(typeof text!=='string'||new TextEncoder().encode(text).byteLength>256*1024)throw Error('Choose a notes file no larger than 256 KB.');
    let payload;try{payload=JSON.parse(text);}catch{throw Error('This file is not valid JSON.');}
    const rows=validateImport(payload,identity);return {payload,rows};
  }
  function restore(key,payload,identity,confirmed=false){
    const imported=validateImport(payload,identity);
    if(imported.some(r=>r.kind==='schedule')&&!confirmed)throw Error('Check the imported reminders against an existing prescription before restoring them.');
    const fingerprint=r=>JSON.stringify([r.kind,r.at,r.note,r.created_at_replay]);
    const current=entries(key),seen=new Set(current.map(fingerprint));
    let id=current.reduce((m,r)=>Math.max(m,r.id),0),skipped=0;
    const added=[];
    for(const r of imported){const identity=fingerprint(r);if(seen.has(identity)){skipped++;continue;}seen.add(identity);added.push({...r,id:++id});}
    if(current.length+added.length>200)throw Error('Restoring this file would exceed the 200-entry limit. No entries were changed.');
    states.set(key,[...current,...added]);return {added:added.length,skipped};
  }
  function reviewEntries(key,now){const issue=timestamp(now.slice(0,16));return entries(key).filter(r=>['review','question','follow_up'].includes(r.kind)&&r.created_at_replay<=issue&&(r.kind==='follow_up'||r.at<=issue)).sort((a,b)=>a.at.localeCompare(b.at)||a.id-b.id);}
  function saveLocal(storage,key,identity,now,expected=undefined){
    if(expected!==undefined&&storage.getItem(storagePrefix+key)!==expected)throw Error('Local notes changed in another tab. Export this tab, then reload before saving.');
    const payload={schema:'glucotwin-user-notes-v3',cohort:identity.cohort,patient_id:String(identity.pid),replay_time:now,entries:entries(key)};
    const encoded=JSON.stringify({payload,review_cache:[...(mealCache.get(key)||new Map())]});storage.setItem(storagePrefix+key,encoded);return encoded;
  }
  function loadLocal(storage,key,identity){
    const text=storage.getItem(storagePrefix+key);if(!text)return false;
    if(new TextEncoder().encode(text).byteLength>512*1024)throw Error('Saved notes exceed the local limit; restore a file instead.');
    const saved=JSON.parse(text),rows=validateImport(saved.payload,identity),cache=new Map();
    if(!Array.isArray(saved.review_cache)||saved.review_cache.length>200)throw Error('Invalid saved meal reviews.');
    for(const pair of saved.review_cache){
      if(!Array.isArray(pair)||pair.length!==2)throw Error('Invalid saved meal review.');
      const [tag,r]=pair,note=rows.find(v=>v.kind==='meal'&&tag===JSON.stringify([v.id,v.at,v.note,v.created_at_replay]));
      if(!note||!r||r.id!==note.id||r.at!==note.at||r.note!==note.note||r.expected!==24||!Number.isInteger(r.samples)||r.samples<1||r.samples>24)throw Error('Invalid saved meal review.');
      if(typeof r.through!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00$/.test(r.through))throw Error('Invalid saved review cutoff.');
      timestamp(r.through.slice(0,16));
      if(Date.parse(r.through+'Z')<Date.parse(note.at+':00Z')+120*60000)throw Error('Incomplete saved meal review.');
      for(const name of ['baseline','maximum','difference'])if(r[name]!==null&&!Number.isFinite(r[name]))throw Error('Invalid saved meal reading.');
      const difference=r.samples>=20&&r.baseline!==null?r.maximum-r.baseline:null;
      if(r.difference!==difference||r.maximum===null)throw Error('Invalid saved meal difference.');
      const status=r.samples<20?'Insufficient visible coverage':r.baseline===null?'Baseline unavailable':'Window available';
      cache.set(tag,{id:r.id,at:note.at,note:note.note,baseline:r.baseline,maximum:r.maximum,difference,samples:r.samples,expected:24,status,retained:false,through:r.through});
    }
    states.set(key,rows);mealCache.set(key,cache);return true;
  }
  function clearLocal(storage,key){storage.removeItem(storagePrefix+key);storage.removeItem(storagePrefix+'enabled:'+key);states.delete(key);mealCache.delete(key);}
  function reviewHtml(snapshot,key){
    const now=timestamp(snapshot.issue_time.slice(0,16));
    const escape=value=>String(value??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const number=value=>Number.isFinite(value)?value.toFixed(1):'—';
    const percent=value=>Number.isFinite(value)?`${(value*100).toFixed(1)}%`:'—';
    const table=(headers,rows)=>`<table><thead><tr>${headers.map(h=>`<th>${escape(h)}</th>`).join('')}</tr></thead><tbody>${rows.length?rows.map(row=>`<tr>${row.map(v=>`<td>${escape(v)}</td>`).join('')}</tr>`).join(''):`<tr><td colspan="${headers.length}">None available.</td></tr>`}</tbody></table>`;
    const labels={meal:'Meal log',medication:'Medication taken log',meal_plan:'Planned meal',schedule:'Prescribed reminder',review:'Review observation',question:'Review question',follow_up:'Follow-up task'};
    const notes=entries(key),logs=notes.filter(r=>['meal','medication'].includes(r.kind)&&r.at<=now&&r.created_at_replay<=now).sort((a,b)=>a.at.localeCompare(b.at));
    const omitted=notes.filter(r=>['meal','medication'].includes(r.kind)&&!logs.some(v=>v.id===r.id)).length;
    const reviews=reviewEntries(key,snapshot.issue_time);
    const plan=planningDays(key,snapshot.issue_time).flatMap(day=>day.entries.filter(r=>r.created_at_replay<=now));
    const history=snapshot.historical_patterns;
    if(history&&history.through!==snapshot.data_cutoff)throw Error('Historical summary does not match the current data cutoff. Refresh the patient replay.');
    const daily=(history?.daily||[]).map(r=>[r.date,`${r.samples}/${r.expected}`,percent(r.coverage),number(r.mean),percent(r.low_fraction),percent(r.reference_fraction),percent(r.high_fraction)]);
    const periods=(history?.periods||[]).map(r=>[`${String(r.start_hour).padStart(2,'0')}:00–${String(r.end_hour).padStart(2,'0')}:00`,r.eligible_days,r.description]);
    const extended=history?.profile;
    const extendedHtml=extended?`<h2>Fourteen-date descriptive profile</h2><p>${escape(extended.note)}</p>${table(['Dates with readings','Complete covered dates','Samples / expected','Coverage','Mean mg/dL','Standard deviation mg/dL','Coefficient of variation %'],[[extended.observed_days,extended.complete_covered_days,`${extended.samples}/${extended.expected}`,percent(extended.coverage),number(extended.mean),number(extended.std),number(extended.coefficient_variation_pct)]])}${table(['Study hour','Covered days','10th percentile','25th percentile','Median','75th percentile','90th percentile'],extended.hours.map(r=>[r.hour,r.covered_days,...['p10','p25','median','p75','p90'].map(k=>number(r[k]))]))}`:'';
    const explanationsHtml=(snapshot.forecasts||[]).filter(r=>r.explanation).map(r=>{const e=r.explanation;return `<h3>+${r.horizon} minute model arithmetic</h3><p>${escape(e.note)}</p>${table(['Term','mg/dL'],[['Latest available reading',number(e.persistence)],['Model reference offset',number(e.reference_offset)],...Object.entries(e.groups).map(([k,v])=>[k,number(v)]),['Reconstructed forecast',number(e.reconstructed_prediction)]])}`;}).join('');
    const notice=snapshot.imported?'USER IMPORT · Transfer performance is unestablished':snapshot.synthetic?'SYNTHETIC DEMONSTRATION · Fictional readings and illustrative forecasts':'RESEARCH REPLAY · Model results are not clinically validated';
    const source={demo:'Synthetic demonstration',rbg:'REPLACE-BG study (RBG)',cgmacros:'CGMacros nutrition dataset',imported:'User-supplied CSV'}[snapshot.cohort]||snapshot.cohort;
    const profile=Object.entries(snapshot.profile||{}).map(([label,value])=>[label,value]);
    const forecasts=(snapshot.forecasts||[]).map(r=>[`${r.horizon} minutes`,r.target_time,number(r.prediction),Number.isFinite(r.interval_lower)?`${number(r.interval_lower)}–${number(r.interval_upper)}`:'Unavailable',Number.isFinite(r.interval_assessment_coverage)?percent(r.interval_assessment_coverage):'—',r.status]);
    const event=snapshot.event_research;
    const research=event?.available?`<p>Current advance-event research decision: ${escape(event.current?.status)}. This is a research flag, not a clinical alert or calibrated probability.</p>`:'';
    return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GlucoTwin · Review summary</title><style>body{font:14px/1.6 system-ui;color:#182b39;max-width:1100px;margin:32px auto;padding:0 20px}h1{margin-bottom:0}h2{margin-top:28px;font-size:20px}.notice{background:#edf7f4;border:1px solid #80b7ae;padding:12px}table{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0}th,td{text-align:left;vertical-align:top;border:1px solid #dce5e8;padding:8px;overflow-wrap:anywhere}th{background:#f3f6f7}thead{display:table-header-group}tr{break-inside:avoid}.muted{color:#6c7b87;font-size:12px}@media print{body{max-width:none;margin:0;padding:0;font-size:11px}table{font-size:10px}.print-note{display:none}@page{size:A4 landscape;margin:12mm}}</style></head><body><h1>GlucoTwin · Review summary</h1><p class="notice">${escape(notice)}</p><p class="print-note">Open this saved HTML file, then use Print → Save as PDF to share the summary.</p><h2>${escape(snapshot.patient_label)}</h2><p>Source: ${escape(source)}<br>Replay time: ${escape(snapshot.issue_time)}<br>Dataset readings available through: ${escape(snapshot.data_cutoff)}. Study dates are shifted or artificial; no timezone is assumed.</p><h2>Clinical profile and current sensor reading</h2>${table(['Profile field','Dataset value'],profile)}<p>${escape(snapshot.profile_note)}</p><p>Glucose at the data cutoff: <strong>${number(snapshot.latest)} mg/dL</strong>. Last-hour sensor coverage: ${escape(snapshot.coverage)}/13 samples.</p><h2>Short-term algorithmic estimates</h2><p>Method: ${escape(snapshot.model_name)}. Estimates remain subject to model error; they do not determine treatment timing. Ranges use separate calibration patients; measured development coverage is not a patient-level guarantee.</p>${table(['Horizon','Target study time','Estimate (mg/dL)','Exploratory range (mg/dL)','Development range coverage','Forecast status'],forecasts)}${research}${explanationsHtml}<h2>Available glucose history</h2><p>${escape(history?.note||'No historical summary is available.')}</p>${table(['Study date','Observed / expected','Coverage','Mean mg/dL','Below 70','70–180','Above 180'],daily)}${table(['Six-hour period','Comparable days','Descriptive observation'],periods)}<p class="muted">Recurring patterns require at least two comparable days and half of covered days. Each complete six-hour window needs at least 80% coverage; high windows have at least 20% readings above 180, and low windows at least 5% below 70. This describes history and does not forecast the next three days.</p>${extendedHtml}<h2>User-reported meals and medication taken</h2><p>These entries were entered or imported by the user. They are not verified dataset records and are not used by the forecasting models.</p>${table(['Study time','Entry type','User description'],logs.map(r=>[r.at,labels[r.kind],r.note]))}<p class="muted">${omitted} user-reported action entries dated or entered after replay time were excluded.</p><h2>After-meal observed glucose</h2><p>Available five-minute readings, not a causal food effect. Differences require a finished two-hour window, at least 20/24 readings and a baseline within 15 minutes. Older meals may be outside visible history.</p>${table(['Meal time','Description','Baseline mg/dL','Highest available mg/dL','Coverage','Maximum minus baseline mg/dL','Status'],mealReview(snapshot,key).map(r=>[r.at,r.note,number(r.baseline),number(r.maximum),`${r.samples}/24`,number(r.difference),r.status+(r.retained?` · Retained through ${r.through.replace('T',' ')}`:'')]))}<h2>User-entered review observations, questions and follow-up</h2><p>These are user notes and tasks; the application does not verify clinician identity, findings or advice.</p>${table(['Study time','Review type','Note or task','Replay status'],reviews.map(r=>[r.at,labels[r.kind],r.note,status(r,snapshot.issue_time)]))}<h2>Three-day user-entered plan</h2><p>Current study date and next two dates. Meal plans and reminder times are copied or entered by the user. A reviewed reminder does not establish that medication was taken. Planned actions are not predicted interventions.</p>${table(['Study time','Plan type','User description','Replay status'],plan.map(r=>[r.at,labels[r.kind],r.note,status(r,snapshot.issue_time)]))}<p class="muted">Only notes created by replay time are included. Reminder review states are shown only after their recorded review time. This summary supplies research context for review; it does not provide diagnosis, dietary treatment, medicine changes or insulin doses.</p></body></html>`;
  }
  const model={add,entries,remove,complete,status,timestamp,shiftDate,planningDays,validateImport,parseImport,restore,reviewHtml,timelineEntries,mealReview,saveLocal,loadLocal,clearLocal,reviewEntries};
  if(typeof module!=='undefined')module.exports=model;
  if(!root.document)return;
  const d=root.document,$=id=>d.getElementById(id),storageVersions=new Map();let context=null,pendingImport=null,patientEpoch=0,importEpoch=0;
  const section=d.createElement('section');section.className='card care-panel';section.id='care-panel';
  section.innerHTML=`<div class="card-heading"><div><div class="section-eyebrow">USER-ENTERED CONTEXT</div><h2>Care notes & prescribed schedule</h2><p>Record meals, review observations, questions and follow-up tasks. Copy medication reminders only from an existing prescription.</p></div><div class="care-actions"><button id="care-export" type="button">Export notes</button><button id="care-review" type="button">Download review summary</button></div></div>
  <p class="care-storage"><label><input type="checkbox" id="care-persist">Keep this patient’s notes and completed meal reviews in this browser</label> <button type="button" id="care-clear-local">Clear this patient’s notes</button><span id="care-storage-status" role="status"></span></p><p>Local saving is optional, unencrypted and specific to this browser and localhost address. Clearing removes this patient’s notes from memory and local storage; export first if you need a copy.</p><p>Export notes to keep a file copy; use Restore notes after reloading. Files are read in this browser tab and are not uploaded. Entries are separate from dataset records, forecasts and the PDF report. Times follow the replay clock; no real-time notifications or dose recommendations.</p>
  <details class="care-import"><summary>Restore notes from a saved file</summary><label for="care-file">GlucoTwin JSON export · maximum 256 KB<input type="file" id="care-file" accept=".json,application/json"></label><p id="care-import-preview" role="status">Select a file to validate and preview before restoring.</p><label id="care-import-confirm-label" hidden><input type="checkbox" id="care-import-confirm">I checked these imported reminders against an existing prescribed schedule.</label><button id="care-import-apply" type="button" disabled>Restore validated entries</button><p>Restoring merges with this patient's current notes. Duplicates are skipped and existing review states are kept. Imported notes are user-reported, not verified clinical records.</p></details>
  <form id="care-form"><label for="care-kind">Entry type<select id="care-kind"><option value="meal">Meal log</option><option value="medication">Medication taken log</option><option value="review">Review observation</option><option value="question">Review question</option><option value="follow_up">Follow-up task</option><option value="meal_plan">Planned meal</option><option value="schedule">Prescribed-schedule reminder</option></select></label><label for="care-at">Study date and time<input id="care-at" type="datetime-local" required></label><label class="care-description" for="care-note">Description as recorded<input id="care-note" maxlength="300" required placeholder="Observation, question, task, meal or existing prescription details"></label><label for="care-repeat">Repeat plan<select id="care-repeat"><option value="1">Once</option><option value="3">Daily for three days</option></select></label><label class="care-confirm"><input id="care-confirm" type="checkbox">For a reminder, I am copying an existing prescribed schedule, including any daily repetition.</label><button type="submit">Add entry</button></form><p id="care-message" role="status"></p><div class="care-plan-heading"><h3>Review observations & follow-up</h3><p>User-entered notes and tasks, not verified clinician findings or model-generated recommendations. Tasks can be dated ahead; completion follows the replay clock.</p></div><div class="table-wrap"><table><thead><tr><th>Study time</th><th>Type</th><th>Note or task</th><th>Status</th><th>Action</th></tr></thead><tbody id="care-review-rows"></tbody></table></div><div class="care-plan-heading"><h3>After-meal observed glucose</h3><p>Available five-minute readings in the two hours after a user-reported meal. Maximum minus baseline is shown only for finished windows with at least 20 of 24 readings and a baseline within 15 minutes. Completed observed windows are retained while this tab is open, and across reloads when local saving is enabled. Older meals without a captured window may be outside visible history. Other meals, activity and medication can affect readings; this does not establish a food effect.</p></div><div class="table-wrap"><table><thead><tr><th>Meal time</th><th>Description</th><th>Baseline mg/dL</th><th>Highest available mg/dL</th><th>Coverage</th><th>Maximum minus baseline mg/dL</th><th>Status</th></tr></thead><tbody id="care-meal-review"></tbody></table></div><div class="care-plan-heading"><h3>Three-day plan</h3><p>Today and the next two study dates. All meals and reminder times are entered by you. A planned time is not a prediction or proof that an action occurred.</p></div><div id="care-plan" class="care-plan"></div><details class="care-history"><summary>All entries for this patient</summary><p id="care-empty">No entries for this patient.</p><div class="table-wrap"><table><thead><tr><th>Time</th><th>Type</th><th>Description</th><th>Status</th><th>Actions</th></tr></thead><tbody id="care-rows"></tbody></table></div></details>`;
  d.querySelector('.ledger-card').before(section);
  const labels={meal:'Meal log',medication:'Medication taken',schedule:'Prescribed reminder',meal_plan:'Planned meal',review:'Review observation',question:'Review question',follow_up:'Follow-up task'};
  function syncRepeat(){const planned=['schedule','meal_plan'].includes($('care-kind').value);$('care-repeat').disabled=!planned;if(!planned)$('care-repeat').value='1';}
  function syncImport(){$('care-import-apply').disabled=!pendingImport||(pendingImport.rows.some(r=>r.kind==='schedule')&&!$('care-import-confirm').checked);}
  function refreshControls(){syncRepeat();syncImport();}
  $('care-kind').addEventListener('change',syncRepeat);syncRepeat();
  function draw(redrawTimeline=true){
    if(!context)return;const rows=entries(context.key).sort((a,b)=>a.at.localeCompare(b.at)||a.id-b.id);$('care-empty').hidden=rows.length>0;$('care-rows').replaceChildren();
    $('care-review-rows').replaceChildren();
    const reviews=reviewEntries(context.key,context.now);
    for(const r of reviews){const tr=d.createElement('tr');for(const v of [r.at.replace('T',' '),labels[r.kind],r.note,status(r,context.now)]){const td=d.createElement('td');td.textContent=v;tr.append(td);}const td=d.createElement('td');if(r.kind==='follow_up'&&status(r,context.now)==='Follow-up due'){const b=d.createElement('button');b.type='button';b.textContent='Mark completed';b.onclick=()=>{complete(context.key,r.id,context.now);draw();};td.append(b);}const removeButton=d.createElement('button');removeButton.type='button';removeButton.textContent='Remove';removeButton.onclick=()=>{remove(context.key,r.id);draw();};td.append(removeButton);tr.append(td);$('care-review-rows').append(tr);}
    if(!reviews.length){const tr=d.createElement('tr'),td=d.createElement('td');td.colSpan=5;td.textContent='No review notes or follow-up tasks entered.';tr.append(td);$('care-review-rows').append(tr);}
    $('care-meal-review').replaceChildren();
    const mealRows=mealReview(context.snapshot,context.key);
    for(const r of mealRows){const tr=d.createElement('tr');for(const value of [r.at.replace('T',' '),r.note,r.baseline??'—',r.maximum??'—',`${r.samples}/${r.expected}`,r.difference===null?'—':r.difference.toFixed(1),r.status+(r.retained?` · Retained through ${r.through.replace('T',' ')}`:'')]){const td=d.createElement('td');td.textContent=value;tr.append(td);}$('care-meal-review').append(tr);}
    if(!mealRows.length){const tr=d.createElement('tr'),td=d.createElement('td');td.colSpan=7;td.textContent='Add a meal log to review available readings.';tr.append(td);$('care-meal-review').append(tr);}
    syncRepeat();$('care-plan').replaceChildren();
    for(const day of planningDays(context.key,context.now)){const card=d.createElement('article'),title=d.createElement('h4');title.textContent=day.date;card.append(title);if(!day.entries.length){const empty=d.createElement('p');empty.textContent='No plan entered.';card.append(empty);}for(const r of day.entries){const item=d.createElement('div'),time=d.createElement('strong'),note=d.createElement('p'),state=d.createElement('small');time.textContent=`${r.at.slice(11)} · ${labels[r.kind]}`;note.textContent=r.note;state.textContent=status(r,context.now);item.append(time,note,state);if(['schedule','follow_up'].includes(r.kind)&&['Due in replay','Follow-up due'].includes(status(r,context.now))){const b=d.createElement('button');b.type='button';b.textContent=r.kind==='follow_up'?'Mark completed':'Mark reviewed';b.onclick=()=>{complete(context.key,r.id,context.now);draw();};item.append(b);}card.append(item);}$('care-plan').append(card);}
    for(const r of rows){const tr=d.createElement('tr');for(const value of [r.at.replace('T',' '),labels[r.kind],r.note,status(r,context.now)]){const td=d.createElement('td');td.textContent=value;tr.append(td);}const td=d.createElement('td');
      if(['schedule','follow_up'].includes(r.kind)&&['Due in replay','Follow-up due'].includes(status(r,context.now))){const b=d.createElement('button');b.type='button';b.textContent=r.kind==='follow_up'?'Mark completed':'Mark reviewed';b.onclick=()=>{complete(context.key,r.id,context.now);draw();};td.append(b);}
      const del=d.createElement('button');del.type='button';del.textContent='Remove';del.onclick=()=>{remove(context.key,r.id);draw();};td.append(del);tr.append(td);$('care-rows').append(tr);}
    if($('care-persist').checked){try{storageVersions.set(context.key,saveLocal(root.localStorage,context.key,{cohort:context.cohort,pid:context.pid},context.now,storageVersions.get(context.key)));$('care-storage-status').textContent='Saved in this browser.';}catch(err){ $('care-storage-status').textContent=err.message||'Saving failed. Export notes to keep a copy.';}}
    if(redrawTimeline)root.drawChart?.();
  }
  $('care-persist').addEventListener('change',()=>{if(!context)return;try{root.localStorage.setItem(storagePrefix+'enabled:'+context.key,$('care-persist').checked?'1':'0');if(!$('care-persist').checked){root.localStorage.removeItem(storagePrefix+context.key);storageVersions.set(context.key,null);$('care-storage-status').textContent='Local saving off. Notes stay in this tab until reload.';}else draw(false);}catch{$('care-storage-status').textContent='Local storage is unavailable. Export notes instead.';}});
  $('care-clear-local').onclick=()=>{if(!context)return;try{clearLocal(root.localStorage,context.key);storageVersions.set(context.key,null);$('care-persist').checked=false;$('care-storage-status').textContent='This patient’s notes and retained reviews were cleared.';draw();}catch{$('care-storage-status').textContent='Could not clear local storage.';}};
  $('care-form').addEventListener('submit',e=>{e.preventDefault();if(!context)return;try{const repeats=Number($('care-repeat').value);add(context.key,{kind:$('care-kind').value,at:$('care-at').value,note:$('care-note').value,confirmed:$('care-confirm').checked,repeat_days:repeats},context.now);$('care-note').value='';$('care-confirm').checked=false;$('care-message').textContent=`${repeats} ${repeats===1?'entry':'entries'} added. Forecasts are unchanged.`;draw();}catch(err){$('care-message').textContent=err.message;}});
  $('care-export').onclick=()=>{if(!context)return;const payload={schema:'glucotwin-user-notes-v3',cohort:context.cohort,patient_id:context.pid,replay_time:context.now,source:'User-entered annotations and plans; not verified dataset events or model inputs',planning_days:planningDays(context.key,context.now),entries:entries(context.key)};const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const a=d.createElement('a');a.href=url;a.download='glucotwin-user-notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  $('care-review').onclick=()=>{if(!context)return;try{const html=reviewHtml(context.snapshot,context.key);const url=URL.createObjectURL(new Blob([html],{type:'text/html;charset=utf-8'}));const a=d.createElement('a');a.href=url;a.download='glucotwin-review-summary.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('care-message').textContent='Summary downloaded. Open the HTML file and choose Print → Save as PDF.';}catch(err){$('care-message').textContent=err.message;}};
  $('care-import-confirm').addEventListener('change',syncImport);
  $('care-file').addEventListener('change',async()=>{
    const readEpoch=++importEpoch;pendingImport=null;$('care-import-confirm').checked=false;$('care-import-confirm-label').hidden=true;syncImport();
    const file=$('care-file').files[0];if(!file||!context){$('care-import-preview').textContent='Select a file to validate and preview before restoring.';return;}$('care-import-preview').textContent='Validating selected file…';
    const epoch=patientEpoch,key=context.key,identity={cohort:context.cohort,pid:context.pid};
    try{if(file.size>256*1024)throw Error('Choose a notes file no larger than 256 KB.');const text=await file.text();if(epoch!==patientEpoch||readEpoch!==importEpoch||key!==context?.key)return;const parsed=parseImport(text,identity);pendingImport={...parsed,key,epoch};const reminders=parsed.rows.filter(r=>r.kind==='schedule').length;$('care-import-preview').textContent=`Validated ${parsed.rows.length} entries for ${context.label}, including ${reminders} prescribed reminders. Original export replay time: ${parsed.payload.replay_time.replace('T',' ')}. Review, then restore.`;$('care-import-confirm-label').hidden=!reminders;syncImport();}catch(err){if(epoch!==patientEpoch||readEpoch!==importEpoch||key!==context?.key)return;$('care-import-preview').textContent=err.message;}
  });
  $('care-import-apply').onclick=()=>{if(!pendingImport||!context||pendingImport.key!==context.key||pendingImport.epoch!==patientEpoch)return;try{const result=restore(context.key,pendingImport.payload,{cohort:context.cohort,pid:context.pid},$('care-import-confirm').checked);$('care-import-preview').textContent=`Restored ${result.added} entries; skipped ${result.skipped} duplicates. Existing notes and forecasts are unchanged.`;pendingImport=null;$('care-file').value='';$('care-import-confirm').checked=false;$('care-import-confirm-label').hidden=true;syncImport();draw();}catch(err){$('care-import-preview').textContent=err.message;}};
  root.GlucoCare={refreshControls,timelineEntries(s,pid){return context?.key===JSON.stringify([s.cohort,String(pid)])?timelineEntries(context.key,s.issue_time):[];},update(s,pid){const key=JSON.stringify([s.cohort,String(pid)]),changed=context?.key!==key;context={key,cohort:s.cohort,pid:String(pid),label:s.patient_label,now:s.issue_time,snapshot:s};if(changed){$('care-persist').checked=false;$('care-storage-status').textContent='Local saving off.';try{if(!storageVersions.has(key))storageVersions.set(key,root.localStorage.getItem(storagePrefix+key));if(root.localStorage.getItem(storagePrefix+'enabled:'+key)==='1'){if(!states.has(key))loadLocal(root.localStorage,key,{cohort:s.cohort,pid:String(pid)});$('care-persist').checked=true;$('care-storage-status').textContent='Restored this patient’s saved notes.';}}catch{$('care-storage-status').textContent='Saved notes could not be validated. Restore an exported file instead.';}patientEpoch++;importEpoch++;pendingImport=null;$('care-file').value='';$('care-import-confirm').checked=false;$('care-import-confirm-label').hidden=true;$('care-import-preview').textContent='Select a file to validate and preview before restoring.';syncImport();$('care-note').value='';$('care-confirm').checked=false;$('care-repeat').value='1';$('care-kind').value='meal';$('care-message').textContent='';}if(changed||!$('care-at').value)$('care-at').value=s.issue_time.slice(0,16);draw(false);}};
})(typeof window!=='undefined'?window:globalThis);
