/** Focused native breathing algebra/contact check; no scene/action admission. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
import ts from 'typescript';
import * as T from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

const front=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),repo=path.dirname(front),out=path.join(repo,'work/v3/carry-breathing-helper');
await mkdir(out,{recursive:true});
const input_hashes={},source=async p=>{const b=await readFile(path.join(repo,p));input_hashes[p]=createHash('sha256').update(b).digest('hex');return b;};
await source('frontend/tools/check-warehouse-carry-breathing-v3.mjs');
for(const name of ['warehouseCarryBreathing','workerRoles','workerRolesFixture']){
 let code=ts.transpileModule((await source('frontend/src/adaptive-v3/'+name+'.ts')).toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
 code=code.replace(/from '(\.\/\w+)'/g,"from '$1.mjs'").replace(/from '(three(?:\/[^']+)?)'/g,(_,id)=>`from ${JSON.stringify(pathToFileURL(path.join(front,'node_modules',id==='three'?'three/build/three.module.js':id)).href)}`);
 await writeFile(path.join(out,name+'.mjs'),code);
}
const {createWarehouseCarryBreathing}=await import(pathToFileURL(path.join(out,'warehouseCarryBreathing.mjs')));
const {createWorkerInstance,disposeWorkerInstance}=await import(pathToFileURL(path.join(out,'workerRoles.mjs')));
const pose=JSON.parse((await source('frontend/public/data/v3/worker-base-carry-pose.json')).toString());
const loader=new GLTFLoader(),load=async id=>{const b=await source('frontend/public/models/v3/'+id+'.glb');return (await loader.parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene;};
const template=await load('worker-base'),cargo=await load('small-carton');
const identity=new T.Matrix4(),axisY=new T.Vector3(0,1,0),unit=new T.Vector3(1,1,1);
const cargoLocal=new T.Matrix4().compose(new T.Vector3(...pose.cargo.position_m),new T.Quaternion().setFromAxisAngle(axisY,pose.cargo.yaw_rad),unit);
cargo.updateWorldMatrix(true,true);
const cargoTriangles=[];
cargo.traverse(n=>{if(!n.isMesh)return;const p=n.geometry.attributes.position,ix=n.geometry.index;for(let i=0;i<(ix?.count??p.count);i+=3)cargoTriangles.push(new T.Triangle(...[0,1,2].map(j=>new T.Vector3().fromBufferAttribute(p,ix?ix.getX(i+j):i+j).applyMatrix4(n.matrixWorld))));});
const trs=n=>[...n.position.toArray(),...n.quaternion.toArray(),...n.scale.toArray(),n.matrixAutoUpdate,n.matrixWorldAutoUpdate];
const close=(a,b,tol=1e-12)=>assert(Math.max(...a.map((v,i)=>Math.abs(v-b[i])))<=tol);
const metrics={frames:0,contact_observations:0,upper_vertices:0,maximum_native_contact_gap_m:0,maximum_contact_gap_change_m:0,maximum_hand_travel_root_m:0,maximum_upper_vertex_travel_root_m:0,maximum_rigid_residual_m:0,maximum_lower_body_world_matrix_change:0};
let referenceSample=null;
for(const [scenario,worldPose] of [[0,[0,0,0,0,0]],[1,[10.75,0,49,-Math.PI/2,.37]],[2,[-7,.13,31,2.41,-.82]]]){
 const parent=new T.Group(),actor=createWorkerInstance(template,'P02','picker'),root=actor.root;
 parent.position.set(worldPose[0],worldPose[1],worldPose[2]);parent.rotation.y=worldPose[4];root.position.set(.31,0,-.24);root.rotation.y=worldPose[3];parent.add(root);
 for(const [name,a] of Object.entries(pose.jointEulerXYZ))root.getObjectByName(name).quaternion.setFromEuler(new T.Euler(...a,'XYZ'));
 root.updateWorldMatrix(true,true);
 const torso=root.getObjectByName('joint__torso'),q0=torso.quaternion.clone(),breath=createWarehouseCarryBreathing(root);
 assert.equal(root.matrixAutoUpdate,true);assert.equal(breath.period_s,4.6);assert.equal(breath.amplitude_rad,.0012);
 const before=[];root.traverse(n=>before.push([n,trs(n)]));
 const rootWorld=root.matrixWorld.clone(),rootInverse=rootWorld.clone().invert(),lower=[];
 root.traverse(n=>{let upper=false;for(let a=n;a;a=a.parent)if(a===torso)upper=true;if(!upper)lower.push([n,n.matrixWorld.toArray()]);});
 const vertices=[];torso.traverse(n=>{if(n.isMesh){const p=n.geometry.attributes.position;for(let i=0;i<p.count;i++)vertices.push({node:n,local:new T.Vector3().fromBufferAttribute(p,i),reference:new T.Vector3().fromBufferAttribute(p,i).applyMatrix4(n.matrixWorld).applyMatrix4(rootInverse)});}});
 metrics.upper_vertices+=vertices.length;
 const refs=pose.solved_reference_points.map(r=>({...r,hand:root.getObjectByName('joint__hand_'+r.side)}));
 for(const r of refs)r.reference=r.hand.localToWorld(new T.Vector3(...r.local_hand_m)).applyMatrix4(rootInverse);
 const baseGaps=[];
 const times=[...Array.from({length:185},(_,i)=>breath.period_s*i/184),9.137,.023,28.47,1.337,0,4.6,-1,2.3,1e6];
 for(const time of times){
  const sampled=breath.sample(time),expected=breath.sample(time);
  assert(sampled.angle_rad>=0&&sampled.angle_rad<=breath.amplitude_rad);
  if(time<=0||time===4.6){assert.equal(sampled.angle_rad,0);assert.deepEqual(sampled.cargo_delta_root.toArray(),identity.toArray());assert(sampled.torso_quaternion.equals(q0));}
  const disabled=breath.sample(time,false);assert.equal(disabled.angle_rad,0);assert.deepEqual(disabled.cargo_delta_root.toArray(),identity.toArray());assert(disabled.torso_quaternion.equals(q0));
  for(const [n,state] of before)assert.deepEqual(trs(n),state,'Sampler must not mutate source TRS');
  breath.sample(time+.781);assert.deepEqual(breath.sample(time).cargo_delta_root.toArray(),expected.cargo_delta_root.toArray());
  sampled.cargo_delta_root.elements[0]=999;sampled.torso_quaternion.x=999;
  assert.deepEqual(breath.sample(time).cargo_delta_root.toArray(),expected.cargo_delta_root.toArray());assert.deepEqual(breath.sample(time).torso_quaternion.toArray(),expected.torso_quaternion.toArray());
  if(time===1.337){if(referenceSample)assert.deepEqual(expected.cargo_delta_root.toArray(),referenceSample);else referenceSample=expected.cargo_delta_root.toArray();}
  torso.quaternion.copy(expected.torso_quaternion);root.updateWorldMatrix(true,true);
  for(const [n,m] of lower){const error=Math.max(...n.matrixWorld.toArray().map((x,i)=>Math.abs(x-m[i])));metrics.maximum_lower_body_world_matrix_change=Math.max(metrics.maximum_lower_body_world_matrix_change,error);assert.equal(error,0,'Root/pelvis/legs/feet matrices must be unchanged');}
  for(const v of vertices){const actual=v.local.clone().applyMatrix4(v.node.matrixWorld).applyMatrix4(rootInverse),rigid=v.reference.clone().applyMatrix4(expected.cargo_delta_root),residual=actual.distanceTo(rigid);metrics.maximum_rigid_residual_m=Math.max(metrics.maximum_rigid_residual_m,residual);metrics.maximum_upper_vertex_travel_root_m=Math.max(metrics.maximum_upper_vertex_travel_root_m,actual.distanceTo(v.reference));assert(residual<1e-12);}
  const cargoWorld=rootWorld.clone().multiply(expected.cargo_delta_root).multiply(cargoLocal);
  const triangles=cargoTriangles.map(t=>new T.Triangle(...[t.a,t.b,t.c].map(p=>p.clone().applyMatrix4(cargoWorld))));
  for(const [i,r] of refs.entries()){
   const point=r.hand.localToWorld(new T.Vector3(...r.local_hand_m));let gap=Infinity;
   for(const t of triangles)gap=Math.min(gap,point.distanceTo(t.closestPointToPoint(point,new T.Vector3())));
   if(time===0&&baseGaps[i]===undefined)baseGaps[i]=gap;
   metrics.maximum_native_contact_gap_m=Math.max(metrics.maximum_native_contact_gap_m,gap);
   if(baseGaps[i]!==undefined)metrics.maximum_contact_gap_change_m=Math.max(metrics.maximum_contact_gap_change_m,Math.abs(gap-baseGaps[i]));
   metrics.maximum_hand_travel_root_m=Math.max(metrics.maximum_hand_travel_root_m,point.clone().applyMatrix4(rootInverse).distanceTo(r.reference));
   assert(gap<=2e-6);if(baseGaps[i]!==undefined)assert(Math.abs(gap-baseGaps[i])<1e-12);metrics.contact_observations++;
  }
  torso.quaternion.copy(q0);root.updateWorldMatrix(true,true);metrics.frames++;
 }
 assert.throws(()=>breath.sample(NaN),/INVALID_CARRY_BREATHING_TIME/);assert.throws(()=>breath.sample(Infinity),/INVALID_CARRY_BREATHING_TIME/);assert.throws(()=>breath.sample(1,'yes'),/INVALID_CARRY_BREATHING_ENABLED/);
 // Cycle boundary has zero velocity and no frame-dependent phase accumulation.
 const dt=1e-5;assert(breath.sample(dt).angle_rad<1e-12);assert(breath.sample(4.6-dt).angle_rad<1e-12);
 root.matrixAutoUpdate=false;assert.throws(()=>createWarehouseCarryBreathing(root),/NATIVE_CARRY_BREATHING_RIG_REQUIRED/);root.matrixAutoUpdate=true;
 disposeWorkerInstance(actor);assert.equal(parent.children.length,0);
}
assert(metrics.maximum_hand_travel_root_m<.001);assert(metrics.maximum_upper_vertex_travel_root_m<.002);
const report={schema_id:'qoima.carry-breathing-helper-checks.v1',passed:true,period_s:4.6,amplitude_rad:.0012,reference_pose:'preserved f33 high carry; integration must recheck new low pose',world_scenarios:3,metrics,input_hashes,checks:['pure sampler no actor mutations','native torso hierarchy and original actor role badge','identity at start/cycle and disabled/reduced-motion input','deterministic arbitrary/backward seek and independent returned objects','actor/ancestor translation and yaw independent reference','whole original torso branch shares one rigid delta','root/pelvis/legs/feet world matrices bit-identical','actual native small-carton triangle contacts retained within 2um','sub-mm maximum reference hand travel; sub-2mm original upper vertex travel','smooth cycle boundary and nonfinite input rejection'],limitations:['No full body/foreign clearance certificate','No new low pose clearance or contact certification','No controller/browser/pause/visibility integration executed by this helper checker']};
await writeFile(path.join(out,'checks.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:true,period_s:report.period_s,amplitude_rad:report.amplitude_rad,...metrics},null,2));
