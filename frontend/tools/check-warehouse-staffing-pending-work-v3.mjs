import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import crypto from 'node:crypto';
import ts from 'typescript';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const own=path.join(root,'work/v3/full-tz-closeout-20261109/staffing-pending-work');
fs.mkdirSync(own,{recursive:true});
const runtime=path.join(own,'runtime'),pins={},compiled=new Map();
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const read=p=>{const b=fs.readFileSync(path.join(root,p));pins[p]=hash(b);return b;};
function compile(p){
 if(compiled.has(p))return compiled.get(p);const out=path.join(runtime,p+'.mjs');compiled.set(p,out);
 let code=ts.transpileModule(read(p).toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
 code=code.replace(/import\s+(\w+)\s+from\s+['"]([^'"]+\.json)['"];?/g,(_,name,spec)=>'const '+name+'='+read(path.posix.normalize(path.posix.dirname(p)+'/'+spec)).toString()+';');
 code=code.replace(/from ['"](\.[^'"]+)['"]/g,(_,spec)=>`from '${pathToFileURL(compile(path.posix.normalize(path.posix.dirname(p)+'/'+spec+'.ts'))).href}'`).replace(/from ['"](three(?:\/[^'"]+)?)['"]/g,(_,id)=>`from '${pathToFileURL(path.join(root,'frontend/node_modules',id==='three'?'three/build/three.module.js':id)).href}'`);
 fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,code);return out;
}
const load=async name=>import(pathToFileURL(compile('frontend/src/adaptive-v3/'+name+'.ts')));
const [{adaptWarehouseV3},{validateRoutePolicy,createWarehouseRouter},{compileWarehouseScenarioExecution},{createStaffingComparison,STAFFING_BREAK},pendingApi]=await Promise.all(['warehouseAdapter','warehouseRouting','warehouseScenarioExecution','workerRoleAssignment','warehouseStaffingPendingWork'].map(load));
const texts=Object.fromEntries(Object.entries({fixture:'frontend/public/data/v3/warehouse-fixture-v3.json',layout:'frontend/public/data/adaptive-v3/layout-manifest.json',registry:'frontend/public/data/v3/worker-registry-v3.json',profiles:'frontend/public/data/v3/worker-profiles-v3.json'}).map(([k,p])=>[k,read(p).toString()]));
const bundle=await adaptWarehouseV3(texts),policy=await validateRoutePolicy(read('frontend/public/data/v3/route-policy-v3.json').toString(),bundle),router=createWarehouseRouter(bundle,policy);
const sourcePath='docs/adaptive-v3/fixtures/scenarios/W09-normal-input-v3.json',input=JSON.parse(read(sourcePath)),beforeInput=JSON.stringify(input),beforeBundle=JSON.stringify(bundle);
const plan=await compileWarehouseScenarioExecution(bundle,policy,input,{scenario_id:'N0',allow_semantic_rebase:true});
const {createWarehouseStaffingPendingWork:bind,isWarehouseStaffingPendingWork:issued,sampleWarehouseStaffingPendingWork:sample}=pendingApi;
const binding=await bind(bundle,plan);
const request=(actor,station)=>({event_id:'pending-work:'+actor,actor_id:actor,target_role:'packer',station_id:station,at_s:40,until_s:360,handoff_s:8});
const configure=async model=>{for(const [id,post]of[['P01','PK05'],['P02','PK06']])assert((await model.assign(request(id,post))).ok);return model;};
const times=[0,39.999,40,47.999,48,119.999,120,239.999,240,359.999,360,599.999,600];
const legacy=await configure(await createStaffingComparison(bundle,router.route));
for(const p of legacy.plans())times.push(p.arrival_s-1e-7,p.arrival_s,p.return_arrival_s-1e-7,p.return_arrival_s);
times.sort((a,b)=>a-b);
const frames=times.flatMap(t=>['A','B'].map(v=>legacy.sample(v,t)));
const baseline=path.join(root,'frontend/tools/fixtures/staffing-legacy-8156-before.json');
if(process.argv.includes('--capture-legacy')){
 assert(!fs.existsSync(baseline),'preserve existing baseline');
 fs.writeFileSync(baseline,JSON.stringify({source_sha256:pins['frontend/src/adaptive-v3/workerRoleAssignment.ts'],times,frames,plans:legacy.plans()},null,2)+'\n');
 fs.writeFileSync(path.join(own,'workerRoleAssignment-before.ts'),read('frontend/src/adaptive-v3/workerRoleAssignment.ts'));
 fs.writeFileSync(path.join(own,'pending-source-probe.json'),JSON.stringify({passed:true,materialized_input_sha256:plan.materialized_input_sha256,pending_jobs:binding.pending_jobs,source_hashes:pins},null,2)+'\n');
 console.log(JSON.stringify({captured:true,legacy_source_sha256:pins['frontend/src/adaptive-v3/workerRoleAssignment.ts'],input_sha256:plan.materialized_input_sha256,jobs:binding.pending_jobs.map(j=>({actor:j.assigned_actor_id,request:j.request_id,HU:j.handling_unit_id,units:j.quantity_units,kg:j.gross_mass_kg,owner:j.owner}))}));process.exit(0);
}
const checks=[];
assert(Object.isFrozen(STAFFING_BREAK)&&Object.isFrozen(STAFFING_BREAK.actor_ids));
const beforeMutation=JSON.stringify(legacy.sample('B',50)),businessHash=legacy.business_inputs_sha256;
assert.throws(()=>{STAFFING_BREAK.from_s=100;},TypeError);
assert.throws(()=>{STAFFING_BREAK.actor_ids.push('P01');},TypeError);
assert.throws(()=>{STAFFING_BREAK.actor_ids[0]='P01';},TypeError);
assert.equal(JSON.stringify(legacy.sample('B',50)),beforeMutation);
assert.equal(legacy.business_inputs_sha256,businessHash);
checks.push('break_calendar_and_nested_actor_ids_reject_runtime_mutation_without_replay_hash_drift');
assert(issued(binding,bundle));assert(Object.isFrozen(binding)&&binding.pending_jobs.every(Object.isFrozen));
assert.equal(binding.pending_jobs.length,2);assert.equal(binding.pending_jobs[1].gross_mass_kg,6.35);
for(const j of binding.pending_jobs){assert.equal(j.remaining_work_s,null);assert.equal(j.source_snapshot_at_s,0);assert.equal(j.owner.kind,'storage_slot');assert.deepEqual(j.source_job,plan.jobs.find(p=>p.job_id===j.job_id));assert.deepEqual(j.source_request,input.inputs.requests.find(q=>q.request_id===j.request_id));}
checks.push('issued_exact_N0_source530HU24actors2vehicles_and_two_real_pending_picker_jobs');
const actual=await configure(await createStaffingComparison(bundle,router.route,{pending_work:binding}));
const admittedPlans=actual.plans();assert.deepEqual(admittedPlans.map(({retained_task,...plan})=>plan),legacy.plans().map(({retained_task,...plan})=>plan),'assignment paths and timing unchanged');
for(const t of times)for(const v of ['A','B']){
 const f=actual.sample(v,t),old=legacy.sample(v,t);assert.equal(f.worker_count,24);assert.equal(f.completed_jobs,0);assert.equal(f.pending_tasks_executed,false);assert.equal(f.pending_work_basis,'issued_scenario_plan');assert.equal(f.pending_work_source_materialized_input_sha256,plan.materialized_input_sha256);
 const withoutWork=x=>x.workers.map(({retained_task,...rest})=>rest);assert.deepEqual(withoutWork(f),withoutWork(old),'native role/route/positions/timing unchanged');
 assert.equal(f.business_inputs_sha256,actual.sample(v==='A'?'B':'A',t).business_inputs_sha256);
 for(const worker of f.workers.filter(w=>['P01','P02'].includes(w.actor_id))){const task=worker.retained_task,j=binding.pending_jobs.find(j=>j.assigned_actor_id===worker.actor_id),p=actual.plans().find(p=>p.request.actor_id===worker.actor_id),paused=v==='B'&&t>=p.request.at_s&&t<p.return_arrival_s;assert(task);assert.equal(task.remaining_work_s,null);assert.equal(task.task_id,j.job_id);assert.equal(task.handling_unit_id,j.handling_unit_id);assert.equal(task.quantity_units,j.quantity_units);assert.equal(task.gross_mass_kg,j.gross_mass_kg);assert.deepEqual(task.owner,j.owner);assert.equal(task.state,paused?'paused':'retained');assert.equal(task.release_state,t<j.requested_at_s?'not_released':'queued');assert.equal(task.completed,false);assert.equal(task.work_executed,false);}
}
checks.push('same_exact_jobs_HU_owner_units_mass_and_unknown_remaining_time_retained_in_both_AB');
checks.push('handoff_assigned_return_restored_states_preserve_actual_outstanding_work_without_execution');
const priorBytes=read('frontend/tools/fixtures/staffing-legacy-8156-before.json');assert.equal(hash(priorBytes),'a361bae488ac63704d1dd1fb10c4f522e0b38c2b38c491414e32afbba3b134a3','Exact frozen pre-change legacy fixture');const prior=JSON.parse(priorBytes);assert.deepEqual(times,prior.times);for(let i=0;i<frames.length;i++){const {pending_work_basis,...frame}=frames[i];assert.equal(pending_work_basis,'synthetic_design_reference');assert.deepEqual(frame,prior.frames[i]);}assert.deepEqual(legacy.plans(),prior.plans);
checks.push('legacy_default_frames_and_plans_exactly_preserved_except_explicit_synthetic_basis_label');
for(const t of[500,0,200,600,40,120,240,350,500])assert.deepEqual(actual.sample('B',t),actual.sample('B',t));actual.reset();const reset=actual.sample('B',0);assert.deepEqual(reset.workers,actual.sample('A',0).workers);assert.equal(reset.allocation_sha256,actual.baseline_allocation_sha256);assert.equal(actual.pending_work,binding);
checks.push('reverse_repeat_reset_preserves_same_binding_and_returns_jobs_to_original_actor_owners');
await assert.rejects(()=>bind(bundle,{...plan}),/ISSUED_PENDING_SCENARIO_PLAN_REQUIRED/);
await assert.rejects(()=>createStaffingComparison(bundle,router.route,{pending_work:{...binding}}),/ISSUED_STAFFING_PENDING_WORK_REQUIRED/);
await assert.rejects(()=>createStaffingComparison(bundle,router.route,{pending_work:null}),/ISSUED_STAFFING_PENDING_WORK_REQUIRED/);
const secondBundle=await adaptWarehouseV3(texts);await assert.rejects(()=>createStaffingComparison(secondBundle,router.route,{pending_work:binding}),/ISSUED_STAFFING_PENDING_WORK_REQUIRED/);
const n1=JSON.parse(read('docs/adaptive-v3/fixtures/scenarios/W10-port-mix-input-v3.json')),n1Plan=await compileWarehouseScenarioExecution(bundle,policy,n1,{allow_semantic_rebase:true});await assert.rejects(()=>bind(bundle,n1Plan),/EXACT_N0_PENDING_INPUT_REQUIRED/);
const extra=structuredClone(input);extra.inputs.requests.push({...extra.inputs.requests[0],request_id:'targeted:modified-source'});await assert.rejects(async()=>bind(bundle,await compileWarehouseScenarioExecution(bundle,policy,extra,{allow_semantic_rebase:true})),/EXACT_N0_PENDING_INPUT_REQUIRED/);
assert.throws(()=>sample({...binding},'P01',0,false),/ISSUED_STAFFING_PENDING_WORK_REQUIRED/);for(const t of[NaN,Infinity,-1,601])assert.throws(()=>sample(binding,'P01',t,false),/INVALID_PENDING_WORK_TIME/);assert.throws(()=>sample(binding,'P99',0,false),/UNKNOWN_PENDING_WORK_ACTOR/);assert.equal(sample(binding,'K01',100,false),null);
checks.push('forged_plan_binding_wrong_bundle_changed_N0_N1_nonfinite_controls_are_inert');
assert.equal(JSON.stringify(bundle),beforeBundle);assert.equal(JSON.stringify(input),beforeInput);assert.deepEqual(plan.sample(0),plan.sample(0));for(const[p,h]of Object.entries(pins))assert.equal(hash(fs.readFileSync(path.join(root,p))),h,'source drift '+p);
checks.push('source_bundle_input_stock_and_plan_unchanged_no_fake_completion_or_stock_move');
const report={passed:true,source_kind:'visual_fixture',engine_operation:false,checks,source_hashes:pins,binding,assignment_plans:admittedPlans,sample_count:times.length*2,scope:'Real issued pending-job capture and same N4 role-clock retention only. No warehouse work execution, native gait/contact reproof, browser or throughput gain.'};
fs.writeFileSync(path.join(own,'checks.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:true,checks:checks.length,samples:report.sample_count,report:path.join(own,'checks.json')}));
