/** Current production regression. Run from an isolated exported checkout: legacy validators write evidence. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
const frontend=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.dirname(frontend);
const names=[
 'check-warehouse-adapter-v3.mjs','check-warehouse-action-sources-v3.mjs','check-warehouse-action-timeline-v3.mjs',
 'check-warehouse-cargo-v3.mjs','check-warehouse-cargo-geometry-v3.mjs','check-warehouse-cargo-holders-v3.mjs',
 'check-warehouse-routing-v3.mjs','check-warehouse-route-pose-v3.mjs','check-warehouse-layout-plan-v3.mjs','check-warehouse-block-rebuild-v3.mjs',
 'check-warehouse-worker-walk-v3.mjs','check-warehouse-original-character-v3.mjs',
 'check-warehouse-heavy-inbound-binding-v3.mjs','check-warehouse-heavy-inbound-plan-v3.mjs','check-additional-heavy-cases-v3.mjs','check-additional-heavy-scene-v3.mjs',
 'check-warehouse-pallet-transfer-plan-v3.mjs','check-warehouse-pallet-transfer-scene-v3.mjs','check-warehouse-dynamic-cargo-binding-v3.mjs',
 'check-warehouse-receiving-route-v3.mjs','check-warehouse-scenario-execution-v3.mjs','check-warehouse-scenario-costs-v3.mjs',
 'check-warehouse-relocation-costs-v3.mjs','check-warehouse-scenario-effects-v3.mjs','check-warehouse-scenario-visual-cues-v3.mjs',
 'check-warehouse-scenario-comparison-render-v3.mjs','check-warehouse-scenario-comparison-integration-v3.mjs',
 'check-warehouse-staffing-pending-work-v3.mjs','check-warehouse-staffing-scene-v3.mjs','check-worker-role-assignment-v3.mjs',
 'check-warehouse-scenario-scene-lifecycle-v3.mjs','check-warehouse-scenario-n2-queue-v3.mjs','check-warehouse-scenario-small-v3.mjs','check-warehouse-small-clamp-workflow-v3.mjs','check-warehouse-source-long-concurrency-v3.mjs','check-warehouse-scenario-source-costs-v3.mjs',
 'check-twin-scenario-v3.mjs','check-twin-inventory-v3.mjs','check-twin-inventory-scene-v3.mjs',
 'check-twin-carrier-indicators-v3.mjs','check-twin-move-arcs-v3.mjs','check-twin-warehouse-motion-v3.mjs',
 'check-native-pair-v3.mjs','check-scenario-postend-native-v3.mjs','check-warehouse-west-pallet-v3.mjs'
];
const archived_checks=[{script:'frontend/tools/check-warehouse-palm-support-v3.mjs',checker_sha256:'e3102fe8970fd22789cdabb04d5de376a51f24d55c6e978f697c9114432c3d19',classification:'ARCHIVED_MODIFIED_BODY_EXPERIMENT',required_ignored_pose_path:'work/v3/close-hold/accepted-pose.json',required_nondefault_model_path:'frontend/public/models/v3/worker-base-close-hold.glb',reason:'This archived both-pad close-hold experiment depends on a modified body explicitly rejected for the current original542 production character. Its checker/assertions remain unchanged; it is not a production pass or a hidden missing-input skip.'}];
const onlyAt=process.argv.indexOf('--only'),filter=onlyAt<0?null:new Set(process.argv[onlyAt+1].split(','));
if(filter)for(const name of filter)if(!names.includes(name))throw Error('UNKNOWN_REGRESSION_SCRIPT:'+name);
const selected=filter?names.filter(n=>filter.has(n)):names;
const out=path.join(repo,'work/v3/full-tz-closeout-20261109/deep-current-regression',new Date().toISOString().replaceAll(/[:.]/g,'-'));
await fs.mkdir(out,{recursive:true});
const results=[];const started=Date.now();
for(const name of selected){
 const script=path.join(frontend,'tools',name),bytes=await fs.readFile(script),script_sha256=createHash('sha256').update(bytes).digest('hex');
 const begin=Date.now();let stdout='',stderr='';
 const result=await new Promise(resolve=>{
  const child=spawn(process.execPath,[script],{cwd:frontend,windowsHide:true,env:{...process.env}});
  child.stdout.on('data',b=>stdout+=b);child.stderr.on('data',b=>stderr+=b);
  child.on('error',error=>resolve({exit_code:null,error:String(error)}));
  child.on('close',(exit_code,signal)=>resolve({exit_code,signal}));
 });
 await fs.writeFile(path.join(out,name+'.stdout.txt'),stdout);await fs.writeFile(path.join(out,name+'.stderr.txt'),stderr);
 const row={script:'frontend/tools/'+name,script_sha256,...result,passed:result.exit_code===0,elapsed_s:(Date.now()-begin)/1000};results.push(row);
 await fs.writeFile(path.join(out,'progress.json'),JSON.stringify({results,elapsed_s:(Date.now()-started)/1000},null,2)+'\n');console.log(JSON.stringify(row));
}
const report={schema_id:'qoima.current-production-regression.v1',passed:results.every(r=>r.passed),executed:results.length,eligible_inventory_count:names.length,legacy_planned_inventory_count:names.length+archived_checks.length,archived_checks,passed_count:results.filter(r=>r.passed).length,failed_count:results.filter(r=>!r.passed).length,source_kind:'visual_fixture',engine_operation:false,results,elapsed_s:(Date.now()-started)/1000,limitations:['Current supported production checks only; experimental modified-character pose solvers are not promoted to release requirements.','Official frontend Playwright33 suite and actual final common-scene browser/performance are separate reports.','Execute in an isolated source export because historical validators write their own evidence paths.']};await fs.writeFile(path.join(out,'checks.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:report.passed,out,executed:results.length}));process.exitCode=report.passed?0:1;
