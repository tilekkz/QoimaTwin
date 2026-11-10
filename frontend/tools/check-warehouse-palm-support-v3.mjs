/** Focused current native palm projection checks; no controller/foreign gate writes. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
import ts from 'typescript';
import * as T from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

const front=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.dirname(front),out=path.join(repo,'work/v3/palm-support-helper');
await mkdir(out,{recursive:true});
const input_hashes={},source=async p=>{const b=await readFile(path.join(repo,p));input_hashes[p]=createHash('sha256').update(b).digest('hex');return b;};
await source('frontend/tools/check-warehouse-palm-support-v3.mjs');
for(const name of ['warehousePalmSupport','warehouseCarryBreathing','workerRoles','workerRolesFixture']){
 const result=ts.transpileModule((await source('frontend/src/adaptive-v3/'+name+'.ts')).toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext},reportDiagnostics:true});
 assert.equal(result.diagnostics?.length??0,0,'Standalone TS syntax diagnostics');
 const code=result.outputText.replace(/from '(\.\/\w+)'/g,"from '$1.mjs'").replace(/from '(three(?:\/[^']+)?)'/g,(_,id)=>`from ${JSON.stringify(pathToFileURL(path.join(front,'node_modules',id==='three'?'three/build/three.module.js':id)).href)}`);
 await writeFile(path.join(out,name+'.mjs'),code);
}
const {createWarehousePalmSupport}=await import(pathToFileURL(path.join(out,'warehousePalmSupport.mjs')));
const {createWarehouseCarryBreathing}=await import(pathToFileURL(path.join(out,'warehouseCarryBreathing.mjs')));
const {createWorkerInstance,disposeWorkerInstance}=await import(pathToFileURL(path.join(out,'workerRoles.mjs')));
const pose=JSON.parse((await source('work/v3/close-hold/accepted-pose.json')).toString());
assert.equal(pose.worker_model_path,'frontend/public/models/v3/worker-base-close-hold.glb');
const b=await source(pose.worker_model_path),template=(await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene;
const unit=new T.Vector3(1,1,1),axisY=new T.Vector3(0,1,0),EPS=2e-6;
const close=(a,b,tol=1e-10)=>assert(Math.abs(a-b)<=tol,`${a} versus ${b}`);
const capture=root=>{const rows=[];root.traverse(n=>rows.push({name:n.name,position:n.position.toArray(),quaternion:n.quaternion.toArray(),scale:n.scale.toArray(),matrix:n.matrix.toArray(),matrixWorld:n.matrixWorld.toArray(),auto:n.matrixAutoUpdate,worldAuto:n.matrixWorldAutoUpdate,needsUpdate:n.matrixWorldNeedsUpdate}));return rows;};
const cargoLocal=z=>new T.Matrix4().compose(new T.Vector3(pose.cargo.position_m[0],pose.cargo.position_m[1],z),new T.Quaternion().setFromAxisAngle(axisY,pose.cargo.yaw_rad),unit);
const referenceRows=pose.contact_basis.map(row=>({side:row.side,lower:row.pads.lower,upper:row.pads.upper}));
let samples=0,maximum_gap=0,maximum_coverage_error=0,maximum_centroid_reference_error=0,baseline=null;
const negative_controls=[];
for(const scenario of [0,1,2]){
 const actor=createWorkerInstance(template,'P02','picker'),root=actor.root,parent=new T.Group();parent.add(root);
 if(scenario===1){parent.position.set(17.3,0,41.7);parent.rotation.set(.17,.31,-.09);root.position.set(-.3,.05,.23);root.rotation.y=-Math.PI/2;}
 if(scenario===2){parent.position.set(-8,.19,31);parent.rotation.set(-.11,-.87,.04);root.position.set(.41,0,-.13);root.rotation.y=2.41;}
 root.updateWorldMatrix(true,true);
 const untouched=capture(root),support=createWarehousePalmSupport(root),breathing=createWarehouseCarryBreathing(root),torso=root.getObjectByName('joint__torso');
 assert.deepEqual(capture(root),untouched,'Constructor must not mutate TRS or matrices');
 const apply=t=>{for(const[n,a]of Object.entries(pose.jointEulerXYZ))root.getObjectByName(n).quaternion.setFromEuler(new T.Euler(...a,'XYZ'));const breath=breathing.sample(t,true);torso.quaternion.copy(breath.torso_quaternion);root.updateWorldMatrix(true,true);return root.matrixWorld.clone().multiply(breath.cargo_delta_root);};
 const observe=frame=>{const before=capture(root),cargo=frame.clone().multiply(cargoLocal(pose.cargo.position_m[2])),cargoBefore=cargo.toArray(),rows=support.sample(cargo);assert.deepEqual(capture(root),before,'Sampler must not mutate actor state');assert.deepEqual(cargo.toArray(),cargoBefore,'Sampler must not mutate HU frame');samples++;return rows;};
 for(const time of [0,2.3,4.6,9.137,.023,28.47,1.337,0,1.337]){
  const frame=apply(time),rows=observe(frame);
  for(const row of rows){
   const expected=referenceRows.find(r=>r.side===row.side);
   for(const kind of ['lower','upper']){
    close(row[kind].area_m2,expected[kind].native_face_area_m2);
    maximum_coverage_error=Math.max(maximum_coverage_error,Math.abs(row[kind].coverage_ratio-1));
    close(row[kind].coverage_ratio,1);assert(row[kind].maximum_plane_gap_m<=EPS);maximum_gap=Math.max(maximum_gap,row[kind].maximum_plane_gap_m);
    assert(row[kind].centroid_hu_m);
    const want=expected[kind].centroid_worker_m.map((v,i)=>v-pose.cargo.position_m[i]);
    for(let i=0;i<3;i++){const error=Math.abs(row[kind].centroid_hu_m[i]-want[i]);maximum_centroid_reference_error=Math.max(maximum_centroid_reference_error,error);close(row[kind].centroid_hu_m[i],want[i]);}
   }
   assert(Math.abs(row.lower_centroid_z_offset_m)<=.025);
  }
  if(!baseline)baseline=structuredClone(rows);
  for(let i=0;i<2;i++)for(const kind of ['lower','upper']){close(rows[i][kind].area_m2,baseline[i][kind].area_m2);for(let k=0;k<3;k++)close(rows[i][kind].centroid_hu_m[k],baseline[i][kind].centroid_hu_m[k]);}
  const independent=structuredClone(rows);rows[0].lower.centroid_hu_m[0]=999;rows[0].upper.area_m2=999;
  assert.deepEqual(observe(frame),independent,'Returned row mutation must not affect next sample');
 }
 const frame=apply(0);
 for(const [label,z]of [['forward_by_80mm',.35],['historical_forward_centre',.3653497334951917]]){
  const rows=support.sample(frame.clone().multiply(cargoLocal(z)));
  for(const row of rows){close(row.lower.coverage_ratio,1);assert.equal(row.upper.area_m2,0);assert.equal(row.upper.coverage_ratio,0);assert.equal(row.upper.centroid_hu_m,null);assert(Math.abs(row.lower_centroid_z_offset_m)>.025);}
  negative_controls.push({scenario,label,cargo_centre_z_m:z,rows});
 }
 const partial=support.sample(frame.clone().multiply(cargoLocal(.31)));
 assert(partial.every(r=>r.lower.coverage_ratio>.999&&r.upper.coverage_ratio>0&&r.upper.coverage_ratio<.95));
 negative_controls.push({scenario,label:'partial_upper_pad_clip',cargo_centre_z_m:.31,rows:partial});
 const disjoint=support.sample(frame.clone().multiply(cargoLocal(2)));
 assert(disjoint.every(r=>r.lower.area_m2===0&&r.upper.area_m2===0&&r.lower.centroid_hu_m===null&&r.upper.centroid_hu_m===null&&r.lower_centroid_z_offset_m===null));
 negative_controls.push({scenario,label:'no_pad_overlap_null_centroids',cargo_centre_z_m:2,rows:disjoint});
 const shifted=frame.clone().multiply(cargoLocal(.27)).multiply(new T.Matrix4().makeTranslation(20e-6,0,0));
 const lost=support.sample(shifted);assert(lost.every(r=>r.lower.maximum_plane_gap_m>18e-6&&r.upper.maximum_plane_gap_m>18e-6));
 negative_controls.push({scenario,label:'20um_lateral_contact_loss',rows:lost});
 const state=capture(root);assert.throws(()=>support.sample(new T.Matrix4().makeScale(0,1,1)),/FINITE_INVERTIBLE/);
 const bad=new T.Matrix4();bad.elements[3]=NaN;assert.throws(()=>support.sample(bad),/FINITE_INVERTIBLE/);assert.deepEqual(capture(root),state);
 disposeWorkerInstance(actor);
}
const report={schema_id:'qoima.palm-support-helper-checks.v1',passed:true,input_hashes,samples,world_scenarios:3,maximum_plane_gap_m:maximum_gap,maximum_coverage_error,maximum_centroid_reference_error_m:maximum_centroid_reference_error,accepted_static_rows:baseline,negative_controls,scope:'Current cached native lower/upper pad faces projected and clipped to nominal whole-HU side rectangle; full actual cargo triangle/world clearance independent.',checks:['actual close-hold original native model and accepted static pose','both full pad areas/centroids match independently computed static native gate','common actor/HU rigid world transforms and actual shared breathing delta','absolute repeated/backwards time and pause-equivalent repeated frame','no constructor/sample actor TRS/matrix or cargo matrix mutation','returned observations share no mutable cached references','old forward HU keeps lower pad but loses upper and centroid criterion','partial upper clipping yields fractional coverage','20um contact loss exposes separate plane-gap failure','nonfinite/singular HU frames rejected'],limitations:['No controller integration/browser/foreign-body scan performed by this checker','Nominal side rectangle projection is not an actual cargo-triangle contact or force certificate']};
await writeFile(path.join(out,'checks.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:true,samples,world_scenarios:3,maximum_plane_gap_m:maximum_gap,maximum_coverage_error,maximum_centroid_reference_error_m:maximum_centroid_reference_error,accepted_static_rows:baseline,negative_controls:negative_controls.length},null,2));
