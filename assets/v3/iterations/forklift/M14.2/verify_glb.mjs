/** Independent actual GLTFLoader decode of partial body/wheels, CPU only. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {createHash} from 'node:crypto';
import * as T from '../../../../../frontend/node_modules/three/build/three.module.js';
import {GLTFLoader} from '../../../../../frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js';
const ROOT=new URL('../../../../../',import.meta.url);
const read=p=>fs.readFile(new URL(p,ROOT));
const bytes=await read('frontend/public/models/v3/forklift-body-wheels.glb');
const stats=JSON.parse(await read('assets/v3/blender/forklift-body-wheels.stats.json'));
const hash=createHash('sha256').update(bytes).digest('hex');assert.equal(hash,stats.sha256);
assert.equal(bytes.toString('ascii',0,4),'glTF');assert.equal(bytes.readUInt32LE(4),2);assert.equal(bytes.readUInt32LE(8),bytes.length);
const {scene}=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
scene.updateMatrixWorld(true);
const root=scene.getObjectByName('forklift_root');assert(root);
assert.equal(root.userData.complete_forklift,false);assert.equal(root.userData.stage,'M14.2_body_wheels_only');
assert.deepEqual(root.matrix.elements,new T.Matrix4().elements);
const meshes=[],joints=[],materials=new Set(),parts=[];
let vertexCount=0,triangles=0,normalError=0,nodeCount=0;
root.traverse(n=>{nodeCount++;if(n.userData.pivot_id)joints.push(n);if(n.isMesh)meshes.push(n);});
assert.equal(meshes.length,15);assert.equal(joints.length,6);assert.equal(nodeCount,22);
const pts=[],saddleNormals=[];
for(const mesh of meshes){
 const g=mesh.geometry,p=g.attributes.position,n=g.attributes.normal,ix=g.index;
 assert(p&&n&&ix&&p.count===n.count);materials.add(mesh.material.name);
 const source=JSON.parse(mesh.userData.source_parts_json);parts.push(...source);
 const normalMatrix=new T.Matrix3().getNormalMatrix(mesh.matrixWorld);
 for(let i=0;i<p.count;i++){
  const v=new T.Vector3().fromBufferAttribute(p,i).applyMatrix4(mesh.matrixWorld);
  const norm=new T.Vector3().fromBufferAttribute(n,i).applyMatrix3(normalMatrix);
  assert([...v.toArray(),...norm.toArray()].every(Number.isFinite));
  normalError=Math.max(normalError,Math.abs(norm.length()-1));pts.push(v);
  if(source.includes('front_axle_saddle')&&Math.abs(v.z-.48)<2e-5&&Math.abs(v.x)<.145&&v.y>.085&&v.y<.355)saddleNormals.push(norm.toArray());
 }
 for(let i=0;i<ix.count;i++)assert(Number.isInteger(ix.getX(i))&&ix.getX(i)>=0&&ix.getX(i)<p.count);
 triangles+=ix.count/3;vertexCount+=p.count;
}
assert.equal(new Set(parts).size,25);assert.equal(materials.size,4);assert.equal(triangles,3148);assert(normalError<1e-5);
const bounds=new T.Box3().setFromPoints(pts);
for(const [a,b] of [[bounds.min.toArray(),[-.6,0,-1.5]],[bounds.max.toArray(),[.6,.92,.7]]])assert(a.every((v,i)=>Math.abs(v-b[i])<2e-5));
for(const side of ['L','R']){
 const p=root.getObjectByName('joint__wheel_rear_'+side);assert.equal(p.parent.name,'joint__rear_steer_'+side);assert(p.position.length()<1e-7);
 assert.equal(p.userData.rotation_axis_runtime,'X');assert.equal(p.parent.userData.rotation_axis_runtime,'Y');
}
const before=[];root.traverse(n=>before.push(...n.matrixWorld.elements));
const steer=[];
for(const side of ['L','R']){
 const joint=root.getObjectByName('joint__rear_steer_'+side),wheel=[];
 joint.traverse(n=>{if(n.isMesh)wheel.push(n);});
 let maxx=0,miny=Infinity;
 for(let step=-150;step<=150;step++){
  joint.rotation.y=T.MathUtils.degToRad(step*.5);scene.updateMatrixWorld(true);
  for(const mesh of wheel){
   const p=mesh.geometry.attributes.position;
   for(let i=0;i<p.count;i++){const v=new T.Vector3().fromBufferAttribute(p,i).applyMatrix4(mesh.matrixWorld);maxx=Math.max(maxx,Math.abs(v.x));miny=Math.min(miny,v.y);}
  }
 }
 assert(maxx<.60&&Math.abs(miny)<2e-5);
 steer.push({side,states:301,maxAbsX:maxx,minY:miny});joint.rotation.y=0;scene.updateMatrixWorld(true);
}
const after=[];root.traverse(n=>after.push(...n.matrixWorld.elements));
assert(before.every((v,i)=>v===after[i]));
const report={stage:'M14.2_body_wheels_only',sha256:hash,bytes:bytes.length,triangles,vertexCount,
 nodeCount,meshes:meshes.length,pivots:joints.map(n=>({name:n.name,parent:n.parent.name,local:n.position.toArray()})),
 sourceParts:parts,materials:[...materials],maxUnitNormalError:normalError,
 actualBounds:{min:bounds.min.toArray(),max:bounds.max.toArray()},steer,exactReset:true,
 frontSaddleMaxZVertexNormalsIncludingBevelTransitions:saddleNormals,
 sourceVsRuntimeBoundMaxError:Math.max(...bounds.min.toArray().map((v,i)=>Math.abs(v-stats.bounds_runtime.min[i])),...bounds.max.toArray().map((v,i)=>Math.abs(v-stats.bounds_runtime.max[i]))),
 browserAndKhronosAcceptance:'pending root, not executed by this checker',completeForkliftAccepted:false};
await fs.writeFile(new URL('assets/v3/iterations/forklift/M14.2/actual-glb-checks.json',ROOT),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({sha256:hash,triangles,vertexCount,nodeCount,normalError,steer,exactReset:true,saddleNormals},null,2));
