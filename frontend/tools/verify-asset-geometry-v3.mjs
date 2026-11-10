import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import * as T from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

const assets=process.argv.slice(2);assert(assets.length);
for(const asset of assets){
 assert(/^[a-z0-9][a-z0-9-]*$/.test(asset));
 const bytes=await readFile(`public/models/v3/${asset}.glb`);
 const stats=JSON.parse(await readFile(`../assets/v3/blender/${asset}.stats.json`,'utf8'));
 // Two float32 world-coordinate roundings at144m need a larger absolute
 // budget than millimetre-sized parts. Small assets retain the3um floor.
 const tolerance=stats.bounds_runtime.min.map((v,i)=>Math.max(3e-6,2*2**(Math.floor(Math.log2(Math.max(1,Math.abs(v),Math.abs(stats.bounds_runtime.max[i]))))-23)));
 assert.equal(createHash('sha256').update(bytes).digest('hex'),stats.sha256);
 const {scene}=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
 scene.updateMatrixWorld(true);let triangles=0,maxNormalError=0,meshes=0;const anchors={},pivots={};const doubleSided=new Set();
 const bound=new T.Box3();const point=new T.Vector3();const batchBounds=new Map();
 const safe=T.PropertyBinding.sanitizeNodeName;
 const expectedBatches=new Map(stats.runtime_components.map(x=>[safe(x.name),x]));
 scene.traverse(n=>{
  assert(n.scale.toArray().every(v=>Math.abs(v-1)<1e-6));
  if(n.userData.anchor_id)anchors[n.name]=n.getWorldPosition(new T.Vector3()).toArray();
  if(n.userData.pivot_id)pivots[n.name]={parent:n.parent.name,local_runtime:n.position.toArray()};
  if(!n.isMesh)return;meshes++;
  const p=n.geometry.getAttribute('position'),norm=n.geometry.getAttribute('normal'),index=n.geometry.index;
  assert(p&&norm&&index&&p.count===norm.count);const batch=new T.Box3();
  for(let i=0;i<p.count;i++){
   point.fromBufferAttribute(p,i).applyMatrix4(n.matrixWorld);assert(point.toArray().every(Number.isFinite));batch.expandByPoint(point);bound.expandByPoint(point);
   maxNormalError=Math.max(maxNormalError,Math.abs(new T.Vector3().fromBufferAttribute(norm,i).length()-1));
  }
  // GLTFLoader splits a multi-material mesh into primitive children. Match
  // its actual original batch parent and union all primitive bounds first.
  let owner=n;while(owner&&!expectedBatches.has(owner.name))owner=owner.parent;assert(owner,`Unexpected mesh ${n.name}`);
  if(!batchBounds.has(owner.name))batchBounds.set(owner.name,new T.Box3());batchBounds.get(owner.name).union(batch);
  for(let i=0;i<index.count;i++)assert(index.getX(i)<p.count);triangles+=index.count/3;
  for(const mat of Array.isArray(n.material)?n.material:[n.material]){assert([T.FrontSide,T.DoubleSide].includes(mat.side)&&mat.roughness>=.5&&mat.opacity===1);if(mat.side===T.DoubleSide)doubleSided.add(mat.name);}
 });
 assert.equal(batchBounds.size,stats.runtime_meshes);assert.equal(triangles,stats.triangles);assert(maxNormalError<1e-5);
 let maxBoundError=0;
 for(const [name,batch] of batchBounds){const expected=expectedBatches.get(name).bounds_runtime;for(let i=0;i<3;i++)for(const side of ['min','max']){const error=Math.abs(batch[side].getComponent(i)-expected[side][i]);maxBoundError=Math.max(maxBoundError,error);assert(error<tolerance[i],`${asset}/${name}/${side}/${i}: ${error} > ${tolerance[i]}`);}}
 for(const [name,expected] of Object.entries(stats.anchors))assert(anchors[safe(name)]?.every((v,i)=>Math.abs(v-expected[i])<tolerance[i]));
 for(const [name,expected] of Object.entries(stats.pivots)){assert.equal(pivots[safe(name)]?.parent,safe(expected.parent));assert(pivots[safe(name)].local_runtime.every((v,i)=>Math.abs(v-expected.local_runtime[i])<3e-6));}
 assert(bound.getSize(new T.Vector3()).toArray().every((v,i)=>Math.abs(v-stats.dimensions_m[i])<2*tolerance[i]));
 const report={asset,sha256:stats.sha256,triangles,meshes,maxNormalError,maximum_native_batch_bound_error_m:maxBoundError,coordinate_tolerance_xyz_m:tolerance,tolerance_basis:'max(3um, two float32 ULPs at the native world-coordinate magnitude); dimensions use both endpoint budgets',dimensions_m:bound.getSize(new T.Vector3()).toArray(),anchors:Object.keys(anchors).length,pivots:Object.keys(pivots).length,all_exported_batches_match_native_source:true,unit_scale:true,double_sided_materials:[...doubleSided],scope:'GLB vertices/normals/indices/batches/hierarchy/material factors. Real shell thickness and outward closed native meshes are proven by the corresponding Blender source check.',verified:true};
 await mkdir(`../assets/v3/qa-browser/${asset}`,{recursive:true});await writeFile(`../assets/v3/qa-browser/${asset}/actual-glb-geometry.json`,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}
