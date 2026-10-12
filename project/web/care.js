'use strict';
// User annotations only: never supplied to a forecasting model or treatment controller.
(function(root){
  const states=new Map();
  function timestamp(value){
    if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value))throw Error('Enter a valid date and time.');
    const date=new Date(value+':00Z');
    if(!Number.isFinite(+date)||date.toISOString().slice(0,16)!==value)throw Error('Enter a valid date and time.');
    return value;
  }
  function add(key,input,now){
    const kind=input.kind;
    if(!['meal','medication','schedule'].includes(kind))throw Error('Choose an entry type.');
    const at=timestamp(input.at),issue=timestamp(now.slice(0,16));
    const note=String(input.note||'').trim();
    if(!note||note.length>300)throw Error('Enter a description of 1–300 characters.');
    if(kind!=='schedule'&&at>issue)throw Error('An observed log cannot be later than replay time.');
    if(kind==='schedule'&&!input.confirmed)throw Error('Confirm this reminder copies an existing prescribed schedule.');
    const rows=states.get(key)||[];
    if(rows.length>=200)throw Error('This patient has 200 entries. Export or remove entries first.');
    const entry={id:rows.reduce((m,r)=>Math.max(m,r.id),0)+1,kind,at,note,created_at_replay:issue,completed_at:null};
    states.set(key,[...rows,entry]);return entry;
  }
  function entries(key){return (states.get(key)||[]).map(r=>({...r}));}
  function remove(key,id){states.set(key,(states.get(key)||[]).filter(r=>r.id!==id));}
  function complete(key,id,now){const at=timestamp(now.slice(0,16));const r=(states.get(key)||[]).find(v=>v.id===id);if(!r||r.kind!=='schedule'||r.at>at)throw Error('Only a due reminder can be marked reviewed.');r.completed_at=at;}
  function status(row,now){const at=now.slice(0,16);if(row.kind!=='schedule')return row.at>at?'Later than replay time':'User-reported';if(row.completed_at&&row.completed_at<=at)return 'Reviewed';return row.at<=at?'Due in replay':'Upcoming';}
  const model={add,entries,remove,complete,status,timestamp};
  if(typeof module!=='undefined')module.exports=model;
  if(!root.document)return;
  const d=root.document,$=id=>d.getElementById(id);let context=null;
  const section=d.createElement('section');section.className='card care-panel';section.id='care-panel';
  section.innerHTML=`<div class="card-heading"><div><div class="section-eyebrow">USER-ENTERED CONTEXT</div><h2>Meals & prescribed schedule</h2><p>Record meals or medication taken, and copy reminders from an existing prescription.</p></div><button id="care-export" type="button">Export notes</button></div>
  <p>Entries stay in this tab until it closes or reloads. They are separate from dataset records, forecasts and the PDF report. Times follow the replay clock; no real-time notifications or dose recommendations.</p>
  <form id="care-form"><label>Entry type<select id="care-kind"><option value="meal">Meal log</option><option value="medication">Medication taken log</option><option value="schedule">Prescribed-schedule reminder</option></select></label><label>Study date and time<input id="care-at" type="datetime-local" required></label><label class="care-description">Description as recorded<input id="care-note" maxlength="300" required placeholder="Meal description, or medication details exactly as prescribed"></label><label class="care-confirm"><input id="care-confirm" type="checkbox">For a reminder, I am copying an existing prescribed schedule.</label><button type="submit">Add entry</button></form><p id="care-message" role="status"></p><p id="care-empty">No entries for this patient.</p><div class="table-wrap"><table><thead><tr><th>Time</th><th>Type</th><th>Description</th><th>Status</th><th>Actions</th></tr></thead><tbody id="care-rows"></tbody></table></div>`;
  d.querySelector('.ledger-card').before(section);
  const labels={meal:'Meal log',medication:'Medication taken',schedule:'Prescribed reminder'};
  function draw(){
    if(!context)return;const rows=entries(context.key).sort((a,b)=>a.at.localeCompare(b.at)||a.id-b.id);$('care-empty').hidden=rows.length>0;$('care-rows').replaceChildren();
    for(const r of rows){const tr=d.createElement('tr');for(const value of [r.at.replace('T',' '),labels[r.kind],r.note,status(r,context.now)]){const td=d.createElement('td');td.textContent=value;tr.append(td);}const td=d.createElement('td');
      if(r.kind==='schedule'&&status(r,context.now)==='Due in replay'){const b=d.createElement('button');b.type='button';b.textContent='Mark reviewed';b.onclick=()=>{complete(context.key,r.id,context.now);draw();};td.append(b);}
      const del=d.createElement('button');del.type='button';del.textContent='Remove';del.onclick=()=>{remove(context.key,r.id);draw();};td.append(del);tr.append(td);$('care-rows').append(tr);}
  }
  $('care-form').addEventListener('submit',e=>{e.preventDefault();if(!context)return;try{add(context.key,{kind:$('care-kind').value,at:$('care-at').value,note:$('care-note').value,confirmed:$('care-confirm').checked},context.now);$('care-note').value='';$('care-confirm').checked=false;$('care-message').textContent='Entry added. Forecasts are unchanged.';draw();}catch(err){$('care-message').textContent=err.message;}});
  $('care-export').onclick=()=>{if(!context)return;const payload={schema:'glucotwin-user-notes-v1',cohort:context.cohort,patient_id:context.pid,replay_time:context.now,source:'User-entered annotations; not verified dataset events or model inputs',entries:entries(context.key)};const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const a=d.createElement('a');a.href=url;a.download='glucotwin-user-notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  root.GlucoCare={update(s,pid){const key=JSON.stringify([s.cohort,String(pid)]),changed=context?.key!==key;context={key,cohort:s.cohort,pid:String(pid),now:s.issue_time};if(changed){$('care-note').value='';$('care-confirm').checked=false;$('care-message').textContent='';}if(changed||!$('care-at').value)$('care-at').value=s.issue_time.slice(0,16);draw();}};
})(typeof window!=='undefined'?window:globalThis);
