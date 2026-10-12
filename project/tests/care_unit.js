'use strict';
const assert=require('node:assert/strict');
const care=require('../web/care.js');
const exampleSnapshot={cohort:'demo',synthetic:true,demo_prefill:true,demo_seed_time:'2024-01-15T08:35:00',issue_time:'2024-01-15T08:35:00'};
assert.equal(care.seedDemo('example',exampleSnapshot,'showcase'),true);
assert.equal(care.entries('example').length,11);
assert.ok(care.entries('example').every(r=>r.note.startsWith('Fictional example:')));
assert.deepEqual(new Set(care.entries('example').map(r=>r.kind)),new Set(['meal','medication','review','question','follow_up','meal_plan','schedule']));
assert.ok(care.planningDays('example',exampleSnapshot.issue_time).every(r=>r.entries.length>=2));
assert.equal(care.seedDemo('example',exampleSnapshot,'showcase'),false);
care.remove('example',care.entries('example')[0].id);
care.seedDemo('example',exampleSnapshot,'showcase');assert.equal(care.entries('example').length,10);
const sampleStorage={removeItem(){}};care.clearLocal(sampleStorage,'example');
care.seedDemo('example',exampleSnapshot,'showcase');assert.equal(care.entries('example').length,0);
for(const [key,s,pid] of [
 ['real-example',{...exampleSnapshot,cohort:'rbg'},'showcase'],
 ['import-example',{...exampleSnapshot,cohort:'imported'},'showcase'],
 ['other-demo',exampleSnapshot,'rise'],
 ['early-demo',{...exampleSnapshot,issue_time:'2024-01-15T08:00:00'},'showcase']
]){assert.equal(care.seedDemo(key,s,pid),false);assert.equal(care.entries(key).length,0);}
care.add('existing-example',{kind:'review',at:'2024-01-15T08:00',note:'Keep my existing note'},exampleSnapshot.issue_time);
assert.equal(care.seedDemo('existing-example',exampleSnapshot,'showcase'),false);
assert.equal(care.entries('existing-example').length,1);
console.log('Worked example checks passed: explicit fictional identity, populated plans, no duplication, preserved edits and patient isolation.');
const editable=care.add('editable',{kind:'review',at:'2024-01-15T08:00',note:'Original'},exampleSnapshot.issue_time);
const revised=care.edit('editable',editable.id,{kind:'review',at:'2024-01-15T08:00',note:'Corrected'},'2024-01-15T09:00:00');
assert.equal(revised.id,editable.id);assert.equal(revised.note,'Corrected');
assert.equal(care.status(revised,exampleSnapshot.issue_time),'Entered after replay time');
assert.throws(()=>care.edit('editable',editable.id,{kind:'meal',at:'2024-01-15T09:30',note:'Future'},'2024-01-15T09:00:00'));
assert.throws(()=>care.edit('editable',editable.id,{kind:'schedule',at:'2024-01-15T10:00',note:'Unconfirmed'},'2024-01-15T09:00:00'));
assert.throws(()=>care.edit('editable',editable.id,{kind:'review',at:'2024-01-15T08:00',note:'Earlier edit'},exampleSnapshot.issue_time));
assert.equal(care.entries('editable')[0].note,'Corrected');
care.remove('editable',editable.id);assert.ok(care.canUndo('editable'));assert.equal(care.canUndo('other-editable'),false);
const reused=care.add('editable',{kind:'review',at:'2024-01-15T08:00',note:'New entry'},'2024-01-15T09:00:00');
const restoredEdit=care.undoRemove('editable');assert.notEqual(restoredEdit.id,reused.id);
assert.deepEqual(new Set(care.entries('editable').map(r=>r.note)),new Set(['New entry','Corrected']));
assert.equal(care.canUndo('editable'),false);
const completedEditable=care.add('edit-task',{kind:'follow_up',at:'2024-01-15T08:00',note:'Task'},exampleSnapshot.issue_time);
care.complete('edit-task',completedEditable.id,exampleSnapshot.issue_time);
care.edit('edit-task',completedEditable.id,{kind:'follow_up',at:'2024-01-15T10:00',note:'Revised task'},'2024-01-15T09:00:00');
assert.equal(care.entries('edit-task')[0].completed_at,null);
console.log('Entry editing and undo checks passed: chronology, prescription confirmation, atomic errors, identity collisions and reset completion.');
const reviewableMeal=care.add('undo-meal',{kind:'meal',at:'2024-01-15T06:00',note:'Original meal'},exampleSnapshot.issue_time);
const observedMeal={issue_time:exampleSnapshot.issue_time,data_cutoff:'2024-01-15T08:30:00',chart:Array.from({length:31},(_,i)=>({time:new Date(Date.UTC(2024,0,15,6,i*5)).toISOString().slice(0,19),glucose:100+i}))};
assert.equal(care.mealReview(observedMeal,'undo-meal')[0].difference,24);
care.remove('undo-meal',reviewableMeal.id);care.undoRemove('undo-meal');
const distantMeal={...observedMeal,issue_time:'2024-01-15T16:00:00',data_cutoff:'2024-01-15T15:55:00',chart:[{time:'2024-01-15T15:55:00',glucose:120}]};
assert.equal(care.mealReview(distantMeal,'undo-meal')[0].retained,true);
care.edit('undo-meal',reviewableMeal.id,{kind:'meal',at:'2024-01-15T06:00',note:'Corrected meal'},distantMeal.issue_time);
assert.equal(care.mealReview(distantMeal,'undo-meal')[0].difference,null);
for(let i=0;i<11;i++){const row=care.add('undo-limit',{kind:'review',at:'2024-01-15T08:00',note:String(i)},exampleSnapshot.issue_time);care.remove('undo-limit',row.id);}
for(let i=0;i<10;i++)care.undoRemove('undo-limit');
assert.equal(care.entries('undo-limit').length,10);assert.equal(care.canUndo('undo-limit'),false);
console.log('Meal cache correction and bounded undo checks passed.');
const now='2026-01-01T12:00:00';
const meal=care.add('a',{kind:'meal',at:'2026-01-01T11:00',note:'Lunch'},now);
assert.equal(care.entries('b').length,0);
assert.throws(()=>care.add('a',{kind:'meal',at:'2026-01-01T13:00',note:'Future lunch'},now));
assert.throws(()=>care.timestamp('2026-02-30T12:00'));
assert.throws(()=>care.add('a',{kind:'schedule',at:'2026-01-01T13:00',note:'Existing prescription'},now));
const reminder=care.add('a',{kind:'schedule',at:'2026-01-01T13:00',note:'Existing prescription',confirmed:true},now);
assert.equal(care.status(reminder,now),'Upcoming');
assert.throws(()=>care.complete('a',reminder.id,now));
care.complete('a',reminder.id,'2026-01-01T13:00:00');
assert.equal(care.status(care.entries('a')[1],'2026-01-01T13:00:00'),'Reviewed');
assert.equal(care.status(care.entries('a')[1],now),'Upcoming');
assert.equal(care.status(meal,'2026-01-01T10:00:00'),'Entered after replay time');
const copy=care.entries('a');copy[0].note='mutated';assert.equal(care.entries('a')[0].note,'Lunch');
care.remove('a',meal.id);assert.equal(care.entries('a').length,1);
assert.throws(()=>care.add('a',{kind:'dose_prediction',at:'2026-01-01T11:00',note:'x'},now));
console.log('Care log checks passed: isolation, validation, replay timing, immutable reads and removal');

const monthEnd='2024-02-28T08:00:00';
care.add('plan',{kind:'meal_plan',at:'2024-02-28T13:00',note:'User-selected lunch',repeat_days:3},monthEnd);
assert.deepEqual(care.planningDays('plan',monthEnd).map(r=>r.date),['2024-02-28','2024-02-29','2024-03-01']);
assert.deepEqual(care.entries('plan').map(r=>r.at),['2024-02-28T13:00','2024-02-29T13:00','2024-03-01T13:00']);
assert.equal(care.status(care.entries('plan')[0],monthEnd),'Planned');
assert.equal(care.status(care.entries('plan')[0],'2024-02-28T14:00:00'),'Planned time reached');
assert.throws(()=>care.complete('plan',1,'2024-02-28T14:00:00'));
care.add('plan',{kind:'schedule',at:'2024-02-28T15:00',note:'Copy of existing daily prescription',confirmed:true,repeat_days:3},monthEnd);
assert.equal(care.planningDays('plan',monthEnd)[0].entries.length,2);
assert.equal(care.planningDays('other',monthEnd)[0].entries.length,0);
assert.throws(()=>care.add('plan',{kind:'medication',at:'2024-02-28T07:00',note:'taken',repeat_days:3},monthEnd));
assert.throws(()=>care.add('plan',{kind:'schedule',at:'2024-02-28T15:00',note:'unconfirmed',repeat_days:3},monthEnd));
for(let i=0;i<199;i++)care.add('limit',{kind:'meal',at:'2024-02-28T07:00',note:'log'},monthEnd);
assert.throws(()=>care.add('limit',{kind:'meal_plan',at:'2024-02-28T13:00',note:'plan',repeat_days:3},monthEnd));
assert.equal(care.entries('limit').length,199);
assert.throws(()=>care.add('plan',{kind:'meal_plan',at:'9999-12-31T13:00',note:'invalid rollover',repeat_days:3},monthEnd));
assert.equal(care.entries('plan').length,6);
console.log('Three-day planning checks passed: leap dates, patient isolation, explicit repetition, planned status and atomic limits.');

const importIdentity={cohort:'demo',pid:'restore'};
const importedRow={id:9,kind:'schedule',at:'2024-02-28T07:00',note:'Synthetic prescribed reminder',created_at_replay:'2024-02-28T06:00',completed_at:'2024-02-28T07:00'};
const importPayload={schema:'glucotwin-user-notes-v2',cohort:'demo',patient_id:'restore',replay_time:monthEnd,entries:[importedRow]};
assert.throws(()=>care.restore('restored',importPayload,importIdentity));
assert.equal(care.entries('restored').length,0);
assert.deepEqual(care.restore('restored',importPayload,importIdentity,true),{added:1,skipped:0});
assert.equal(care.status(care.entries('restored')[0],monthEnd),'Reviewed');
assert.equal(care.status(care.entries('restored')[0],'2024-02-28T06:00:00'),'Upcoming');
assert.deepEqual(care.restore('restored',importPayload,importIdentity,true),{added:0,skipped:1});
const stale={...importPayload,entries:[{...importedRow,completed_at:null}]};
care.restore('restored',stale,importIdentity,true);assert.equal(care.entries('restored')[0].completed_at,'2024-02-28T07:00');
for(const invalid of [
 {...importPayload,cohort:'rbg'}, {...importPayload,patient_id:'other'},
 {...importPayload,schema:'other'}, {...importPayload,entries:[importedRow,importedRow]},
 {...importPayload,entries:[{...importedRow,id:-1}]},
 {...importPayload,entries:[{...importedRow,at:'2024-02-30T07:00'}]},
 {...importPayload,entries:[{...importedRow,kind:'meal',completed_at:null,at:'2024-02-28T09:00'}]},
 {...importPayload,entries:[{...importedRow,completed_at:'2024-02-28T05:00'}]},
 {...importPayload,entries:[{...importedRow,note:'x'.repeat(301)}]},
]){assert.throws(()=>care.restore('restored',invalid,importIdentity,true));assert.equal(care.entries('restored').length,1);}
assert.throws(()=>care.parseImport('broken JSON',importIdentity));
assert.throws(()=>care.parseImport('x'.repeat(256*1024+1),importIdentity));
const legacy={...importPayload,schema:'glucotwin-user-notes-v1'};
assert.equal(care.parseImport(JSON.stringify(legacy),importIdentity).rows.length,1);
const overflow={...importPayload,entries:[{...importedRow,id:1},{...importedRow,id:2,note:'Second distinct note'}]};
assert.throws(()=>care.restore('limit',overflow,importIdentity,true));assert.equal(care.entries('limit').length,199);
const sanitized=care.validateImport({...importPayload,entries:[{...importedRow,model_prediction:500}]},importIdentity);
assert.equal(sanitized[0].model_prediction,undefined);
console.log('Restore checks passed: identity, legacy files, malformed data, duplicate handling, review preservation and atomic merge.');

const reviewSnapshot={cohort:'demo',synthetic:true,patient_label:'Fictional <patient>',issue_time:monthEnd,data_cutoff:'2024-02-28T07:55:00',profile:{Age:'48 <fictional>'},profile_note:'Synthetic profile',latest:123,coverage:13,model_name:'Illustrative rule',forecasts:[{horizon:30,target_time:'2024-02-28T08:30:00',prediction:130,status:'Forecast issued',actual:'FUTURE_ACTUAL_SENTINEL'}],historical_patterns:{through:'2024-02-28T07:55:00',note:'Past-only samples',daily:[{date:'2024-02-28',samples:10,expected:13,coverage:10/13,mean:123,low_fraction:0,reference_fraction:1,high_fraction:0}],periods:[]}};
care.add('review',{kind:'meal',at:'2024-02-28T07:00',note:'<script>unsafe</script>'},monthEnd);
care.add('review',{kind:'meal',at:'2024-02-29T07:00',note:'FUTURE_NOTE_SENTINEL'},'2024-02-29T08:00:00');
care.add('review',{kind:'meal_plan',at:'2024-02-29T13:00',note:'User planned lunch'},monthEnd);
const futureReviewed={...importPayload,entries:[{...importedRow,completed_at:'2024-02-28T09:00'}]};
care.restore('review',futureReviewed,importIdentity,true);
const review=care.reviewHtml(reviewSnapshot,'review');
assert.match(review,/SYNTHETIC DEMONSTRATION/);
assert.match(review,/Fictional &lt;patient&gt;/);
assert.match(review,/&lt;script&gt;unsafe&lt;\/script&gt;/);
assert.doesNotMatch(review,/<script>|FUTURE_ACTUAL_SENTINEL|FUTURE_NOTE_SENTINEL/);
assert.match(review,/User planned lunch/);
assert.match(review,/Due in replay/);
assert.doesNotMatch(review,/<td>Reviewed<\/td>/);
assert.match(review,/1 user-reported action entries/);
assert.throws(()=>care.reviewHtml({...reviewSnapshot,historical_patterns:{...reviewSnapshot.historical_patterns,through:'2024-02-29T08:00:00'}},'review'));
assert.match(care.reviewHtml({...reviewSnapshot,synthetic:false},'empty-patient'),/None available/);
console.log('Review report checks passed: provenance, escaping, future-note exclusion, hidden target outcomes and causal review state.');

care.add('timeline',{kind:'meal',at:'2024-02-28T07:00',note:'Known meal'},monthEnd);
care.add('timeline',{kind:'medication',at:'2024-02-28T07:30',note:'Known medication log'},monthEnd);
care.add('timeline',{kind:'meal',at:'2024-02-28T06:30',note:'Backdated later entry'},'2024-02-28T09:00:00');
care.add('timeline',{kind:'meal_plan',at:'2024-02-28T07:00',note:'Plan only'},monthEnd);
care.add('timeline',{kind:'schedule',at:'2024-02-28T07:00',note:'Reminder only',confirmed:true},monthEnd);
assert.deepEqual(care.timelineEntries('timeline',monthEnd).map(r=>r.note),['Known meal','Known medication log']);
assert.equal(care.timelineEntries('other-timeline',monthEnd).length,0);
assert.equal(care.timelineEntries('timeline','2024-02-28T09:00:00').length,3);
const timelineCopy=care.timelineEntries('timeline',monthEnd);timelineCopy[0].note='changed';assert.equal(care.timelineEntries('timeline',monthEnd)[0].note,'Known meal');
console.log('Timeline action filtering checks passed: actual logs, creation time, patient scope and immutable reads.');

care.add('meal-review',{kind:'meal',at:'2024-01-01T08:00',note:'Breakfast'},'2024-01-01T08:00:00');
const mealSnapshot={issue_time:'2024-01-01T10:05:00',data_cutoff:'2024-01-01T10:00:00',chart:Array.from({length:25},(_,i)=>({time:new Date(Date.UTC(2024,0,1,8,i*5)).toISOString().slice(0,19),glucose:100+i}))};
let mealResult=care.mealReview(mealSnapshot,'meal-review')[0];
assert.equal(mealResult.samples,24);assert.equal(mealResult.baseline,100);assert.equal(mealResult.maximum,124);assert.equal(mealResult.difference,24);
assert.equal(care.mealReview({...mealSnapshot,data_cutoff:'2024-01-01T09:55:00'},'meal-review')[0].difference,null);
assert.equal(care.mealReview({...mealSnapshot,chart:mealSnapshot.chart.slice(8)},'meal-review')[0].difference,null);
assert.equal(care.mealReview({...mealSnapshot,chart:mealSnapshot.chart.slice(1)},'meal-review')[0].status,'Baseline unavailable');
assert.deepEqual(care.mealReview({...mealSnapshot,chart:[...mealSnapshot.chart,{time:'2024-01-01T10:10:00',glucose:999}]},'meal-review'),care.mealReview(mealSnapshot,'meal-review'));
assert.equal(care.mealReview(mealSnapshot,'other-patient').length,0);
console.log('After-meal review checks passed: sensor delay, coverage, baseline, future exclusion and patient isolation.');

const shiftedMeal={...mealSnapshot,issue_time:'2024-01-01T10:08:00',data_cutoff:'2024-01-01T10:03:00',chart:mealSnapshot.chart.map(r=>({...r,time:new Date(Date.parse(r.time+'Z')+180000).toISOString().slice(0,19)}))};
assert.equal(care.mealReview(shiftedMeal,'meal-review')[0].samples,24);
assert.equal(care.mealReview(shiftedMeal,'meal-review')[0].baseline,null);
care.add('meal-review',{kind:'meal_plan',at:'2024-01-01T08:00',note:'Planned only'},'2024-01-01T08:00:00');
assert.equal(care.mealReview(mealSnapshot,'meal-review').length,1);
const reviewWithMeal=care.reviewHtml({...mealSnapshot,cohort:'demo',synthetic:true,patient_label:'Test',coverage:13,forecasts:[],profile:{}},'meal-review');
assert.ok(reviewWithMeal.includes('After-meal observed glucose'));assert.ok(reviewWithMeal.includes('24/24'));

const memoryStorage=new Map(),adapter={getItem:k=>memoryStorage.get(k)||null,setItem:(k,v)=>memoryStorage.set(k,v),removeItem:k=>memoryStorage.delete(k)};
care.saveLocal(adapter,'meal-review',{cohort:'demo',pid:'rise'},mealSnapshot.issue_time);
care.remove('meal-review',1);
assert.ok(care.loadLocal(adapter,'meal-review',{cohort:'demo',pid:'rise'}));
assert.throws(()=>care.loadLocal(adapter,'meal-review',{cohort:'demo',pid:'wrong'}));
const lateMeal={...mealSnapshot,issue_time:'2024-01-01T18:05:00',data_cutoff:'2024-01-01T18:00:00',chart:[{time:'2024-01-01T12:00:00',glucose:100}]};
assert.equal(care.mealReview(lateMeal,'meal-review')[0].retained,true);
assert.equal(care.mealReview({...mealSnapshot,data_cutoff:'2024-01-01T09:55:00'},'meal-review')[0].difference,null);
care.clearLocal(adapter,'meal-review');assert.equal(care.entries('meal-review').length,0);assert.equal(memoryStorage.size,0);
console.log('Local persistence checks passed: validated restore, retained windows, rewind withholding, scope and clearing.');

care.add('conflict',{kind:'meal',at:'2024-01-01T03:30',note:'Synthetic tab A'},mealSnapshot.issue_time);
const storedVersion=care.saveLocal(adapter,'conflict',{cohort:'demo',pid:'rise'},mealSnapshot.issue_time,null);
assert.throws(()=>care.saveLocal(adapter,'conflict',{cohort:'demo',pid:'rise'},mealSnapshot.issue_time,'stale version'));
assert.ok(care.saveLocal(adapter,'conflict',{cohort:'demo',pid:'rise'},mealSnapshot.issue_time,storedVersion));
console.log('Concurrent local-save conflict check passed.');

const reviewClock='2024-01-01T12:00:00';
care.add('review-notes',{kind:'review',at:'2024-01-01T11:00',note:'Observed repeated gaps'},reviewClock);
care.add('review-notes',{kind:'question',at:'2024-01-01T11:30',note:'Confirm logging times?'},reviewClock);
const task=care.add('review-notes',{kind:'follow_up',at:'2024-01-01T13:00',note:'Discuss record quality'},reviewClock);
assert.throws(()=>care.complete('review-notes',task.id,reviewClock));
care.complete('review-notes',task.id,'2024-01-01T13:00:00');
assert.equal(care.status(care.entries('review-notes')[2],reviewClock),'Upcoming');
assert.equal(care.status(care.entries('review-notes')[2],'2024-01-01T13:00:00'),'Completed');
assert.equal(care.timelineEntries('review-notes',reviewClock).length,0);
assert.equal(care.reviewEntries('review-notes',reviewClock).length,3);
assert.equal(care.reviewEntries('review-notes','2024-01-01T11:59:00').length,0);
const journal={schema:'glucotwin-user-notes-v3',cohort:'demo',patient_id:'rise',replay_time:reviewClock,entries:care.entries('review-notes')};
assert.equal(care.validateImport(journal,{cohort:'demo',pid:'rise'}).length,3);
assert.throws(()=>care.validateImport({...journal,schema:'glucotwin-user-notes-v2'},{cohort:'demo',pid:'rise'}));
const journalHtml=care.reviewHtml({...mealSnapshot,issue_time:reviewClock,cohort:'demo',synthetic:true,patient_label:'Test',coverage:13,forecasts:[],profile:{}},'review-notes');
assert.ok(journalHtml.includes('Confirm logging times?'));assert.ok(journalHtml.includes('Upcoming'));assert.ok(!journalHtml.includes('<td>Completed</td>'));
console.log('Review notes checks passed: schema compatibility, future completion withholding, scope and timeline separation.');
