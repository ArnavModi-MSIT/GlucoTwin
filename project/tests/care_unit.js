'use strict';
const assert=require('node:assert/strict');
const care=require('../web/care.js');
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
assert.equal(care.status(meal,'2026-01-01T10:00:00'),'Later than replay time');
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
