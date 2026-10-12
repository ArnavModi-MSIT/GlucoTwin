'use strict';
// User annotations only: never supplied to a forecasting model or treatment controller.
(function(root){
  const states=new Map();
  function shiftDate(value,days){const date=new Date(timestamp(value)+':00Z');date.setUTCDate(date.getUTCDate()+days);return timestamp(date.toISOString().slice(0,16));}
  function timestamp(value){
    if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value))throw Error('Enter a valid date and time.');
    const date=new Date(value+':00Z');
    if(!Number.isFinite(+date)||date.toISOString().slice(0,16)!==value)throw Error('Enter a valid date and time.');
    return value;
  }
  function add(key,input,now){
    const kind=input.kind;
    if(!['meal','medication','schedule','meal_plan'].includes(kind))throw Error('Choose an entry type.');
    const at=timestamp(input.at),issue=timestamp(now.slice(0,16));
    const note=String(input.note||'').trim();
    if(!note||note.length>300)throw Error('Enter a description of 1–300 characters.');
    if(['meal','medication'].includes(kind)&&at>issue)throw Error('An observed log cannot be later than replay time.');
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
  function remove(key,id){states.set(key,(states.get(key)||[]).filter(r=>r.id!==id));}
  function complete(key,id,now){const at=timestamp(now.slice(0,16));const r=(states.get(key)||[]).find(v=>v.id===id);if(!r||r.kind!=='schedule'||r.at>at)throw Error('Only a due reminder can be marked reviewed.');r.completed_at=at;}
  function status(row,now){const at=now.slice(0,16);if(row.kind==='meal_plan')return row.at>at?'Planned':'Planned time reached';if(row.kind!=='schedule')return row.at>at?'Later than replay time':'User-reported';if(row.completed_at&&row.completed_at<=at)return 'Reviewed';return row.at<=at?'Due in replay':'Upcoming';}
  function planningDays(key,now){const start=timestamp(now.slice(0,10)+'T00:00');return Array.from({length:3},(_,i)=>{const date=shiftDate(start,i).slice(0,10);return {date,entries:entries(key).filter(r=>['schedule','meal_plan'].includes(r.kind)&&r.at.slice(0,10)===date).sort((a,b)=>a.at.localeCompare(b.at)||a.id-b.id)};});}
  function validateImport(payload,identity){
    if(!payload||typeof payload!=='object'||Array.isArray(payload)||!['glucotwin-user-notes-v1','glucotwin-user-notes-v2'].includes(payload.schema))throw Error('Choose a GlucoTwin notes export (version 1 or 2).');
    if(typeof payload.patient_id!=='string'||payload.cohort!==identity.cohort||payload.patient_id!==String(identity.pid))throw Error('This file belongs to a different patient or dataset. Select that patient before importing.');
    if(typeof payload.replay_time!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00$/.test(payload.replay_time))throw Error('The export has an invalid replay time.');
    timestamp(payload.replay_time.slice(0,16));
    if(!Array.isArray(payload.entries)||payload.entries.length>200)throw Error('An export must contain at most 200 entries.');
    const ids=new Set();
    return payload.entries.map(r=>{
      if(!r||typeof r!=='object'||Array.isArray(r)||!Number.isSafeInteger(r.id)||r.id<1||ids.has(r.id))throw Error('The export has invalid or duplicate entry identifiers.');
      ids.add(r.id);
      if(!['meal','medication','schedule','meal_plan'].includes(r.kind)||typeof r.note!=='string'||!r.note.trim()||r.note.trim().length>300)throw Error('The export contains an invalid entry type or description.');
      const at=timestamp(r.at),created=timestamp(r.created_at_replay);
      if(['meal','medication'].includes(r.kind)&&at>created)throw Error('A recorded action is dated after its entry time.');
      const completed=r.completed_at===null?null:timestamp(r.completed_at);
      if(completed!==null&&(r.kind!=='schedule'||completed<at||completed<created))throw Error('The export has an invalid reminder review time.');
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
  const model={add,entries,remove,complete,status,timestamp,shiftDate,planningDays,validateImport,parseImport,restore};
  if(typeof module!=='undefined')module.exports=model;
  if(!root.document)return;
  const d=root.document,$=id=>d.getElementById(id);let context=null,pendingImport=null,patientEpoch=0,importEpoch=0;
  const section=d.createElement('section');section.className='card care-panel';section.id='care-panel';
  section.innerHTML=`<div class="card-heading"><div><div class="section-eyebrow">USER-ENTERED CONTEXT</div><h2>Meals & prescribed schedule</h2><p>Record meals or medication taken, and copy reminders from an existing prescription.</p></div><button id="care-export" type="button">Export notes</button></div>
  <p>Export notes to keep a file copy; use Restore notes after reloading. Files are read in this browser tab and are not uploaded. Entries are separate from dataset records, forecasts and the PDF report. Times follow the replay clock; no real-time notifications or dose recommendations.</p>
  <details class="care-import"><summary>Restore notes from a saved file</summary><label for="care-file">GlucoTwin JSON export · maximum 256 KB<input type="file" id="care-file" accept=".json,application/json"></label><p id="care-import-preview" role="status">Select a file to validate and preview before restoring.</p><label id="care-import-confirm-label" hidden><input type="checkbox" id="care-import-confirm">I checked these imported reminders against an existing prescribed schedule.</label><button id="care-import-apply" type="button" disabled>Restore validated entries</button><p>Restoring merges with this patient's current notes. Duplicates are skipped and existing review states are kept. Imported notes are user-reported, not verified clinical records.</p></details>
  <form id="care-form"><label for="care-kind">Entry type<select id="care-kind"><option value="meal">Meal log</option><option value="medication">Medication taken log</option><option value="meal_plan">Planned meal</option><option value="schedule">Prescribed-schedule reminder</option></select></label><label for="care-at">Study date and time<input id="care-at" type="datetime-local" required></label><label class="care-description" for="care-note">Description as recorded<input id="care-note" maxlength="300" required placeholder="Meal description, or medication details exactly as prescribed"></label><label for="care-repeat">Repeat plan<select id="care-repeat"><option value="1">Once</option><option value="3">Daily for three days</option></select></label><label class="care-confirm"><input id="care-confirm" type="checkbox">For a reminder, I am copying an existing prescribed schedule, including any daily repetition.</label><button type="submit">Add entry</button></form><p id="care-message" role="status"></p><div class="care-plan-heading"><h3>Three-day plan</h3><p>Today and the next two study dates. All meals and reminder times are entered by you. A planned time is not a prediction or proof that an action occurred.</p></div><div id="care-plan" class="care-plan"></div><details class="care-history"><summary>All entries for this patient</summary><p id="care-empty">No entries for this patient.</p><div class="table-wrap"><table><thead><tr><th>Time</th><th>Type</th><th>Description</th><th>Status</th><th>Actions</th></tr></thead><tbody id="care-rows"></tbody></table></div></details>`;
  d.querySelector('.ledger-card').before(section);
  const labels={meal:'Meal log',medication:'Medication taken',schedule:'Prescribed reminder',meal_plan:'Planned meal'};
  function syncRepeat(){const planned=['schedule','meal_plan'].includes($('care-kind').value);$('care-repeat').disabled=!planned;if(!planned)$('care-repeat').value='1';}
  function syncImport(){$('care-import-apply').disabled=!pendingImport||(pendingImport.rows.some(r=>r.kind==='schedule')&&!$('care-import-confirm').checked);}
  function refreshControls(){syncRepeat();syncImport();}
  $('care-kind').addEventListener('change',syncRepeat);syncRepeat();
  function draw(){
    if(!context)return;const rows=entries(context.key).sort((a,b)=>a.at.localeCompare(b.at)||a.id-b.id);$('care-empty').hidden=rows.length>0;$('care-rows').replaceChildren();
    syncRepeat();$('care-plan').replaceChildren();
    for(const day of planningDays(context.key,context.now)){const card=d.createElement('article'),title=d.createElement('h4');title.textContent=day.date;card.append(title);if(!day.entries.length){const empty=d.createElement('p');empty.textContent='No plan entered.';card.append(empty);}for(const r of day.entries){const item=d.createElement('div'),time=d.createElement('strong'),note=d.createElement('p'),state=d.createElement('small');time.textContent=`${r.at.slice(11)} · ${labels[r.kind]}`;note.textContent=r.note;state.textContent=status(r,context.now);item.append(time,note,state);if(r.kind==='schedule'&&status(r,context.now)==='Due in replay'){const b=d.createElement('button');b.type='button';b.textContent='Mark reviewed';b.onclick=()=>{complete(context.key,r.id,context.now);draw();};item.append(b);}card.append(item);}$('care-plan').append(card);}
    for(const r of rows){const tr=d.createElement('tr');for(const value of [r.at.replace('T',' '),labels[r.kind],r.note,status(r,context.now)]){const td=d.createElement('td');td.textContent=value;tr.append(td);}const td=d.createElement('td');
      if(r.kind==='schedule'&&status(r,context.now)==='Due in replay'){const b=d.createElement('button');b.type='button';b.textContent='Mark reviewed';b.onclick=()=>{complete(context.key,r.id,context.now);draw();};td.append(b);}
      const del=d.createElement('button');del.type='button';del.textContent='Remove';del.onclick=()=>{remove(context.key,r.id);draw();};td.append(del);tr.append(td);$('care-rows').append(tr);}
  }
  $('care-form').addEventListener('submit',e=>{e.preventDefault();if(!context)return;try{const repeats=Number($('care-repeat').value);add(context.key,{kind:$('care-kind').value,at:$('care-at').value,note:$('care-note').value,confirmed:$('care-confirm').checked,repeat_days:repeats},context.now);$('care-note').value='';$('care-confirm').checked=false;$('care-message').textContent=`${repeats} ${repeats===1?'entry':'entries'} added. Forecasts are unchanged.`;draw();}catch(err){$('care-message').textContent=err.message;}});
  $('care-export').onclick=()=>{if(!context)return;const payload={schema:'glucotwin-user-notes-v2',cohort:context.cohort,patient_id:context.pid,replay_time:context.now,source:'User-entered annotations and plans; not verified dataset events or model inputs',planning_days:planningDays(context.key,context.now),entries:entries(context.key)};const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const a=d.createElement('a');a.href=url;a.download='glucotwin-user-notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  $('care-import-confirm').addEventListener('change',syncImport);
  $('care-file').addEventListener('change',async()=>{
    const readEpoch=++importEpoch;pendingImport=null;$('care-import-confirm').checked=false;$('care-import-confirm-label').hidden=true;syncImport();
    const file=$('care-file').files[0];if(!file||!context){$('care-import-preview').textContent='Select a file to validate and preview before restoring.';return;}$('care-import-preview').textContent='Validating selected file…';
    const epoch=patientEpoch,key=context.key,identity={cohort:context.cohort,pid:context.pid};
    try{if(file.size>256*1024)throw Error('Choose a notes file no larger than 256 KB.');const text=await file.text();if(epoch!==patientEpoch||readEpoch!==importEpoch||key!==context?.key)return;const parsed=parseImport(text,identity);pendingImport={...parsed,key,epoch};const reminders=parsed.rows.filter(r=>r.kind==='schedule').length;$('care-import-preview').textContent=`Validated ${parsed.rows.length} entries for ${context.label}, including ${reminders} prescribed reminders. Original export replay time: ${parsed.payload.replay_time.replace('T',' ')}. Review, then restore.`;$('care-import-confirm-label').hidden=!reminders;syncImport();}catch(err){if(epoch!==patientEpoch||readEpoch!==importEpoch||key!==context?.key)return;$('care-import-preview').textContent=err.message;}
  });
  $('care-import-apply').onclick=()=>{if(!pendingImport||!context||pendingImport.key!==context.key||pendingImport.epoch!==patientEpoch)return;try{const result=restore(context.key,pendingImport.payload,{cohort:context.cohort,pid:context.pid},$('care-import-confirm').checked);$('care-import-preview').textContent=`Restored ${result.added} entries; skipped ${result.skipped} duplicates. Existing notes and forecasts are unchanged.`;pendingImport=null;$('care-file').value='';$('care-import-confirm').checked=false;$('care-import-confirm-label').hidden=true;syncImport();draw();}catch(err){$('care-import-preview').textContent=err.message;}};
  root.GlucoCare={refreshControls,update(s,pid){const key=JSON.stringify([s.cohort,String(pid)]),changed=context?.key!==key;context={key,cohort:s.cohort,pid:String(pid),label:s.patient_label,now:s.issue_time};if(changed){patientEpoch++;importEpoch++;pendingImport=null;$('care-file').value='';$('care-import-confirm').checked=false;$('care-import-confirm-label').hidden=true;$('care-import-preview').textContent='Select a file to validate and preview before restoring.';syncImport();$('care-note').value='';$('care-confirm').checked=false;$('care-repeat').value='1';$('care-kind').value='meal';$('care-message').textContent='';}if(changed||!$('care-at').value)$('care-at').value=s.issue_time.slice(0,16);draw();}};
})(typeof window!=='undefined'?window:globalThis);
