/** Bounded CPU decode of changed fixed frame; prior tyre/rig interfaces stay frozen. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {createHash} from 'node:crypto';
import * as T from '../../../../../../frontend/node_modules/three/build/three.module.js';
import {GLTFLoader} from '../../../../../../frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js';
const ROOT=new URL('../../../../../../',import.meta.url),OUT=new URL('./',import.meta.url);
const read=p=>fs.readFile(new URL(p,ROOT));
const hash=b=>createHash('sha256').update(b).digest('hex');
const parse=async b=>(await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene;
const reports=[];
for(const [id,stage,parts,joints,anchors] of [['forklift-body-wheels','M14.2',30,6,0],['forklift-cab-stage','M14.3',45,7,8]]){
 const path=`frontend/public/models/v3/${id}.glb`,bytes=await read(path);
 const stats=JSON.parse(await read(`assets/v3/blender/${id}.stats.json`));
 const oldPath=`assets/v3/iterations/forklift/${stage}/front-axle-repair/before/${id}.glb`;
 const oldBytes=await read(oldPath),scene=await parse(bytes),oldScene=await parse(oldBytes);
 scene.updateMatrixWorld(true);oldScene.updateMatrixWorld(true);
 const root=scene.getObjectByName('forklift_root'),oldRoot=oldScene.getObjectByName('forklift_root');
 assert(root&&oldRoot);assert.equal(hash(bytes),stats.sha256);assert.equal(bytes.length,stats.glb_bytes);
 assert.deepEqual(root.matrix.elements,new T.Matrix4().elements);assert.equal(root.userData.complete_forklift,false);
 const nodes=[],meshes=[],interfaces=[],sourceParts=[],materials=new Set(),points=[];
 let triangles=0,vertices=0,maxNormalError=0,maxBatchBoundError=0;
 root.traverse(n=>{nodes.push(n);if(n.isMesh)meshes.push(n);if(n.userData.pivot_id||n.userData.anchor_id)interfaces.push(n);});
 for(const n of interfaces){const old=oldRoot.getObjectByName(n.name);assert(old);assert.equal(n.parent.name,old.parent.name);assert.deepEqual(n.matrix.elements,old.matrix.elements);assert.deepEqual(n.matrixWorld.elements,old.matrixWorld.elements);}
 assert.equal(interfaces.filter(n=>n.userData.pivot_id).length,joints);assert.equal(interfaces.filter(n=>n.userData.anchor_id).length,anchors);
 let unchangedWheelBatches=0;
 for(const mesh of meshes){
  const g=mesh.geometry,p=g.attributes.position,n=g.attributes.normal,ix=g.index;
  assert(p&&n&&ix&&p.count===n.count);const key=JSON.parse(mesh.userData.source_parts_json).sort();sourceParts.push(...key);materials.add(mesh.material.name);
  const ps=[];const nm=new T.Matrix3().getNormalMatrix(mesh.matrixWorld);
  for(let i=0;i<p.count;i++) {const v=new T.Vector3().fromBufferAttribute(p,i).applyMatrix4(mesh.matrixWorld),normal=new T.Vector3().fromBufferAttribute(n,i).applyMatrix3(nm);assert([...v.toArray(),...normal.toArray()].every(Number.isFinite));maxNormalError=Math.max(maxNormalError,Math.abs(normal.length()-1));ps.push(v);points.push(v);}
  for(let i=0;i<ix.count;i++)assert(ix.getX(i)>=0&&ix.getX(i)<p.count);
  const b=new T.Box3().setFromPoints(ps),e=stats.runtime_components.find(c=>c.name===mesh.name).bounds_runtime;
  maxBatchBoundError=Math.max(maxBatchBoundError,...b.min.toArray().map((v,i)=>Math.abs(v-e.min[i])),...b.max.toArray().map((v,i)=>Math.abs(v-e.max[i])));
  if(mesh.parent.name.startsWith('joint__wheel_')){
   let old;oldRoot.traverse(o=>{if(o.isMesh&&JSON.stringify(JSON.parse(o.userData.source_parts_json).sort())===JSON.stringify(key))old=o;});assert(old);
   assert.deepEqual(mesh.matrix.elements,old.matrix.elements);assert.equal(mesh.material.name,old.material.name);
   for(const attr of ['position','normal'])assert.deepEqual(g.attributes[attr].array,old.geometry.attributes[attr].array);
   assert.deepEqual(ix.array,old.geometry.index.array);unchangedWheelBatches++;
  }
  triangles+=ix.count/3;vertices+=p.count;
 }
 assert.equal(unchangedWheelBatches,12);assert.equal(new Set(sourceParts).size,parts);assert.equal(triangles,stats.triangles);assert.equal(meshes.length,stats.runtime_meshes);assert(maxNormalError<1e-5&&maxBatchBoundError<2e-5);
 const bounds=new T.Box3().setFromPoints(points);
 for(const key of ['min','max'])assert(bounds[key].toArray().every((v,i)=>Math.abs(v-stats.bounds_runtime[key][i])<2e-5));
 assert.equal(bounds.min.y,0);assert(bounds.min.x>=-.60002&&bounds.max.x<=.60002&&bounds.min.z>=-1.50002&&bounds.max.z<=1.50002&&bounds.max.y<=2.10002);
 reports.push({asset_id:id,sha256:hash(bytes),bytes:bytes.length,previous_sha256:hash(oldBytes),source_parts:parts,meshes:meshes.length,nodes:nodes.length,triangles,vertices,pivots:joints,anchors,unchanged_interface_matrices:interfaces.length,unchanged_wheel_batches:unchangedWheelBatches,maxNormalError,maxBatchBoundError,bounds:{min:bounds.min.toArray(),max:bounds.max.toArray()},materials:[...materials],completeForkliftAccepted:false});
}
await fs.writeFile(new URL('actual-repair-glb-checks.json',OUT),JSON.stringify({scope:'changed frame export only; no repeat route/action/worker pipeline',reports},null,2)+'\n');
console.log(JSON.stringify(reports,null,2));
