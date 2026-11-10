/** Actual vehicle + unchanged worker GLTFLoader proof; CPU only. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {createHash} from 'node:crypto';
import * as T from '../../../../../frontend/node_modules/three/build/three.module.js';
import {GLTFLoader} from '../../../../../frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js';
const ROOT=new URL('../../../../../',import.meta.url);
const read=p=>fs.readFile(new URL(p,ROOT));
const json=async p=>JSON.parse(await read(p));
const hash=b=>createHash('sha256').update(b).digest('hex');
const stats=await json('assets/v3/blender/forklift-cab-stage.stats.json');
const plan=await json('assets/v3/specs/forklift.dimensions.json');
const frozen=await json('assets/v3/iterations/forklift/M14.1/actual-blueprint-checks.json');
const bytes=await read('frontend/public/models/v3/forklift-cab-stage.glb');
assert.equal(hash(bytes),stats.sha256);
assert.equal(hash(await read('frontend/public/models/v3/forklift-body-wheels.glb')),'a074423afa7624216f5508f9933d18083fd9479780e658c58ba476f0bb50faa9');
const parse=async b=>(await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene;
const scene=await parse(bytes),root=scene.getObjectByName('forklift_root');scene.updateMatrixWorld(true);
assert(root);assert.equal(root.userData.complete_forklift,false);assert.equal(root.userData.stage,'M14.3_body_and_cab_no_mast');
assert.deepEqual(root.matrix.elements,new T.Matrix4().elements);
const meshes=[],joints=[],anchors=[],materials=new Set(),parts=[],points=[];
let normals=0,vertices=0,triangles=0,nodeCount=0,maxNormalError=0,maxBatchBoundError=0;
root.traverse(n=>{nodeCount++;if(n.userData.pivot_id)joints.push(n);if(n.userData.anchor_id)anchors.push(n);if(n.isMesh)meshes.push(n);});
assert.equal(meshes.length,18);assert.equal(joints.length,7);assert.equal(anchors.length,8);assert.equal(nodeCount,34);
const worldPoints=new Map();
for(const mesh of meshes){
 const g=mesh.geometry,p=g.attributes.position,n=g.attributes.normal,ix=g.index;
 assert(p&&n&&ix&&p.count===n.count);materials.add(mesh.material.name);
 const ps=[],source=JSON.parse(mesh.userData.source_parts_json);parts.push(...source);
 const normalMatrix=new T.Matrix3().getNormalMatrix(mesh.matrixWorld);
 for(let i=0;i<p.count;i++){
  const point=new T.Vector3().fromBufferAttribute(p,i).applyMatrix4(mesh.matrixWorld);
  const normal=new T.Vector3().fromBufferAttribute(n,i).applyMatrix3(normalMatrix);
  assert([...point.toArray(),...normal.toArray()].every(Number.isFinite));
  maxNormalError=Math.max(maxNormalError,Math.abs(normal.length()-1));ps.push(point);points.push(point);normals++;
 }
 for(let i=0;i<ix.count;i++)assert(ix.getX(i)>=0&&ix.getX(i)<p.count);
 const bound=new T.Box3().setFromPoints(ps),expected=stats.runtime_components.find(c=>c.name===mesh.name).bounds_runtime;
 maxBatchBoundError=Math.max(maxBatchBoundError,...bound.min.toArray().map((v,i)=>Math.abs(v-expected.min[i])),...bound.max.toArray().map((v,i)=>Math.abs(v-expected.max[i])));
 worldPoints.set(mesh,ps);triangles+=ix.count/3;vertices+=p.count;
}
assert.equal(new Set(parts).size,40);assert.equal(materials.size,4);assert.equal(triangles,4810);assert(maxNormalError<1e-5&&maxBatchBoundError<2e-5);
const bounds=new T.Box3().setFromPoints(points);
for(const [actual,expected] of [[bounds.min.toArray(),[-.6,0,-1.5]],[bounds.max.toArray(),[.6,2.1,.7]]])assert(actual.every((v,i)=>Math.abs(v-expected[i])<2e-5));
const anchorResults={};
for(const a of anchors){const p=a.getWorldPosition(new T.Vector3()).toArray();anchorResults[a.name]=p;assert(p.every((v,i)=>Math.abs(v-plan.anchors[a.name][i])<2e-5));}
for(const side of ['L','R'])assert.equal(root.getObjectByName('joint__wheel_rear_'+side).parent.name,'joint__rear_steer_'+side);

const workerBytes=await read('frontend/public/models/v3/worker-base.glb');
assert.equal(hash(workerBytes),'c8546473c76f126844b427417db86e65be090fa04ad56c0deb9cb2bda92e73b7');
const workerScene=await parse(workerBytes),worker=workerScene.getObjectByName('worker_base_root');
worker.position.set(...plan.driver.worker_root_translation);
for(const [name,a] of Object.entries(plan.driver.jointEulerXYZ))worker.getObjectByName(name).quaternion.multiply(new T.Quaternion().setFromEuler(new T.Euler(...a,'XYZ')));
workerScene.updateMatrixWorld(true);
const workerMeshes=[],workerPoints=[],handTriangles={L:[],R:[]};
worker.traverse(n=>{if(n.isMesh)workerMeshes.push(n);});
for(const mesh of workerMeshes){
 const p=mesh.geometry.attributes.position,ix=mesh.geometry.index.array,ps=[];
 for(let i=0;i<p.count;i++){const v=new T.Vector3().fromBufferAttribute(p,i).applyMatrix4(mesh.matrixWorld);ps.push(v);workerPoints.push(v);}
 for(const side of ['L','R'])if(mesh.parent.name==='joint__hand_'+side)for(let i=0;i<ix.length;i+=3)handTriangles[side].push(new T.Triangle(ps[ix[i]],ps[ix[i+1]],ps[ix[i+2]]));
}
const workerBounds=new T.Box3().setFromPoints(workerPoints),contacts=[];
for(const [va,wa] of [['anchor_driver_seat','anchor_seat_contact'],['anchor_footrest_L','anchor_foot_floor_L'],['anchor_footrest_R','anchor_foot_floor_R'],['anchor_steering_grip_L','anchor_hand_grip_L'],['anchor_steering_grip_R','anchor_hand_grip_R']]){
 const target=new T.Vector3(...anchorResults[va]),point=worker.getObjectByName(wa).getWorldPosition(new T.Vector3());
 assert(target.distanceTo(point)<2e-5);contacts.push({vehicle:va,worker:wa,distance:target.distanceTo(point),world:point.toArray()});
}
const roofMin=Math.min(...points.filter(p=>p.y>=2.03999).map(p=>p.y));
assert(roofMin-workerBounds.max.y>=.045);
const gripResults=[];
for(const side of ['L','R']){
 const info=frozen.actualDriver.grips.find(g=>g.side===side),centre=new T.Vector3(...info.centre),axis=new T.Vector3(...info.axis);
 const gripMesh=meshes.find(m=>JSON.parse(m.userData.source_parts_json).includes('steering_grip_'+side));
 const ps=worldPoints.get(gripMesh).filter(p=>side==='L'?p.x<0:p.x>0);
 let minAir=Infinity,maxRadial=0,maxAxial=0;
 for(const p of ps){
  const d=p.clone().sub(centre),t=d.dot(axis);maxAxial=Math.max(maxAxial,Math.abs(t));
  maxRadial=Math.max(maxRadial,d.addScaledVector(axis,-t).length());
  for(const tri of handTriangles[side])minAir=Math.min(minAir,tri.closestPointToPoint(p,new T.Vector3()).distanceTo(p));
 }
 assert(maxAxial<=.04002&&maxRadial<=.01802&&minAir>=.0044);
 gripResults.push({side,maxAxial,maxRadial,actualVertexToHandTriangleMinAir:minAir});
}
const before=[];root.traverse(n=>before.push(...n.matrixWorld.elements));
const steering=root.getObjectByName('joint__steering_wheel'),q=steering.quaternion.clone();
steering.quaternion.multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(...steering.userData.mechanical_axis_runtime),.1));scene.updateMatrixWorld(true);
steering.quaternion.copy(q);scene.updateMatrixWorld(true);
const after=[];root.traverse(n=>after.push(...n.matrixWorld.elements));assert(before.every((v,i)=>v===after[i]));
const report={stage:'M14.3',sha256:hash(bytes),bytes:bytes.length,triangles,vertices,normals,nodeCount,
 meshes:meshes.length,joints:joints.map(n=>({name:n.name,parent:n.parent.name,local:n.position.toArray()})),
 anchors:anchorResults,materials:[...materials],maxNormalError,maxBatchBoundError,
 bounds:{min:bounds.min.toArray(),max:bounds.max.toArray()},workerBounds:{min:workerBounds.min.toArray(),max:workerBounds.max.toArray()},
 actualWorkerVehicleAnchorMatches:contacts,roofGap:roofMin-workerBounds.max.y,actualGrips:gripResults,exactReset:true,
 productionWorkerEmbedded:false,bodyGLBUnchanged:true,fullForkliftAccepted:false,browserKhronos:'pending root'};
await fs.writeFile(new URL('assets/v3/iterations/forklift/M14.3/actual-glb-checks.json',ROOT),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({sha256:report.sha256,bytes:bytes.length,triangles,vertices,nodes:nodeCount,joints:joints.length,anchors:anchors.length,
 maxNormalError,maxBatchBoundError,roofGap:report.roofGap,grips:gripResults,exactReset:true},null,2));
