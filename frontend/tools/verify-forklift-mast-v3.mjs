import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import * as T from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

const bytes=await readFile('public/models/v3/forklift-mast-stage.glb');
const stats=JSON.parse(await readFile('../assets/v3/blender/forklift-mast-stage.stats.json','utf8'));
assert.equal(createHash('sha256').update(bytes).digest('hex'),stats.sha256);
const gltf=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
const root=gltf.scene.getObjectByName('forklift_root');assert(root);
gltf.scene.updateMatrixWorld(true);
const joints=[],anchors=[],points=[];let meshes=0,triangles=0,maxNormalError=0;
root.traverse(n=>{
 assert(n.scale.toArray().every(v=>Math.abs(v-1)<1e-7));
 if(n.userData.pivot_id)joints.push(n.name);
 if(n.userData.anchor_id)anchors.push(n.name);
 if(!n.isMesh)return;
 meshes++;const p=n.geometry.attributes.position,normal=n.geometry.attributes.normal,index=n.geometry.index;
 assert(p&&normal&&index&&normal.count===p.count);
 const local=[];
 for(let i=0;i<p.count;i++){
  const v=new T.Vector3().fromBufferAttribute(p,i).applyMatrix4(n.matrixWorld);
  assert(v.toArray().every(Number.isFinite));points.push(v);local.push(v);
  maxNormalError=Math.max(maxNormalError,Math.abs(new T.Vector3().fromBufferAttribute(normal,i).length()-1));
 }
 const bound=new T.Box3().setFromPoints(local),expected=stats.runtime_components.find(x=>x.name===n.name).bounds_runtime;
 assert([...bound.min.toArray().map((v,i)=>Math.abs(v-expected.min[i])),...bound.max.toArray().map((v,i)=>Math.abs(v-expected.max[i]))].every(v=>v<2e-6));
 for(let i=0;i<index.count;i++)assert(index.getX(i)<p.count);
 triangles+=index.count/3;
 for(const m of Array.isArray(n.material)?n.material:[n.material])assert(m.roughness===.8500000238418579||Math.abs(m.roughness-.85)<1e-6);
});
assert.equal(joints.length,11);assert.equal(anchors.length,12);assert.equal(triangles,stats.triangles);assert(maxNormalError<1e-5);
const bounds=new T.Box3().setFromPoints(points);assert(bounds.getSize(new T.Vector3()).toArray().every((v,i)=>Math.abs(v-[1.2,2.1,3][i])<2e-6));
const carriage=root.getObjectByName('joint__carriage'),reach=root.getObjectByName('joint__reach');
assert.equal(reach.parent,carriage);
for(const side of ['L','R'])assert.equal(root.getObjectByName('joint__fork_'+side).parent,reach);
const frames=[];
for(const [label,top,extension,spacing] of [['travel',.7,0,.4],['extended low',.18,.4,.24],['extended high',1.5,.4,.4]]){
 carriage.position.y=top;reach.position.z=.36+extension;
 for(const [side,sign] of [['L',-1],['R',1]])root.getObjectByName('joint__fork_'+side).position.x=sign*spacing;
 gltf.scene.updateMatrixWorld(true);
 const supports=['L','R'].map(side=>root.getObjectByName('anchor_fork_top_'+side).getWorldPosition(new T.Vector3()).toArray());
 assert(supports.every(p=>Math.abs(p[1]-top)<1e-6&&Math.abs(p[2]-(.95+extension))<1e-6));
 frames.push({label,forkTop:top,reach:extension,halfspacing:spacing,supports});
}
carriage.position.y=.7;reach.position.z=.36;
for(const [side,sign] of [['L',-1],['R',1]])root.getObjectByName('joint__fork_'+side).position.x=sign*.4;
gltf.scene.updateMatrixWorld(true);
const report={asset:'forklift-mast-stage',sha256:stats.sha256,meshes,triangles,joints,anchors,maxNormalError,
 dimensions_m:bounds.getSize(new T.Vector3()).toArray(),all_export_batch_bounds_match_source:true,unit_scale:true,
 motion_frames:frames,bind_restored:true,scope:'Final GLB geometry/axes/hierarchy/material and lift/reach transformation check. Complete cargo workflow is a later gate.'};
await writeFile('../assets/v3/iterations/forklift/M14.4/actual-glb-checks.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({asset:report.asset,triangles,joints:joints.length,anchors:anchors.length,motion_frames:frames.length,verified:true}));
