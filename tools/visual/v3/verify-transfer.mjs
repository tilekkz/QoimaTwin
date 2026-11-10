import {readFile,writeFile} from 'node:fs/promises';
import {GLTFLoader} from '../../../frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js';
import {Vector3} from '../../../frontend/node_modules/three/build/three.module.js';
globalThis.ProgressEvent??=class ProgressEvent{constructor(type,init={}){this.type=type;Object.assign(this,init);}};
const data=await readFile('frontend/public/models/v3/conveyor-diverter.glb');
const gltf=await new Promise((resolve,reject)=>new GLTFLoader().parse(data.buffer.slice(data.byteOffset,data.byteOffset+data.byteLength),'',resolve,reject));
const scene=gltf.scene;scene.updateMatrixWorld(true);
const pivot=scene.getObjectByName('joint__transfer');
if(!pivot)throw Error('Lost transfer joint');
const disk=pivot.children.find(x=>x.isMesh);
if(!disk)throw Error('No separate rotating mesh under transfer joint');
const anchor=scene.getObjectByName('anchor_payload_centre');
const vertices=object=>{const points=[];object.traverse(node=>{if(!node.isMesh)return;const p=node.geometry.attributes.position;for(let i=0;i<p.count;i++)points.push(new Vector3().fromBufferAttribute(p,i).applyMatrix4(node.matrixWorld));});return points;};
const boundary=new Map(),pointKey=p=>p.toArray().map(x=>x.toFixed(6)).join(',');
scene.getObjectByName('belt_surface').traverse(node=>{
 if(!node.isMesh)return;const p=node.geometry.attributes.position,idx=node.geometry.index;
 for(let i=0;i<(idx?.count??p.count);i+=3){
  const tri=[0,1,2].map(j=>new Vector3().fromBufferAttribute(p,idx?idx.getX(i+j):i+j).applyMatrix4(node.matrixWorld));
  if(!tri.every(v=>Math.abs(v.y-.92)<1e-5))continue;
  for(let j=0;j<3;j++){
   const a=tri[j],b=tri[(j+1)%3],key=[pointKey(a),pointKey(b)].sort().join('|');
   const e=boundary.get(key)||{a,b,count:0};e.count++;boundary.set(key,e);
  }
 }
});
const holeEdges=[...boundary.values()].filter(e=>e.count===1&&[e.a,e.b].every(v=>Math.hypot(v.x,v.z)>.406&&Math.hypot(v.x,v.z)<.423));
if(holeEdges.length!==16)throw Error('Actual exported hole edge loop mismatch: '+holeEdges.length);
let count=0,maxRadius=0,minHoleMargin=Infinity;
for(let degree=0;degree<=90;degree++){
 pivot.rotation.set(0,degree*Math.PI/180,0);scene.updateMatrixWorld(true);
 const centre=anchor.getWorldPosition(new Vector3());if(centre.distanceTo(new Vector3(0,.92,0))>1e-5)throw Error('Carrier support anchor drifts');
 for(const p of vertices(disk)){
   maxRadius=Math.max(maxRadius,Math.hypot(p.x,p.z));
   for(const {a,b} of holeEdges){
     let nx=b.z-a.z,nz=a.x-b.x;const len=Math.hypot(nx,nz);nx/=len;nz/=len;
     if(nx*a.x+nz*a.z<0){nx=-nx;nz=-nz;}
     const margin=nx*(a.x-p.x)+nz*(a.z-p.z);
     minHoleMargin=Math.min(minHoleMargin,margin);if(margin<.0019)throw Error('Rotating disk collides with surrounding deck');
   }
   count++;
 }
}
pivot.rotation.set(0,0,0);scene.updateMatrixWorld(true);
const all=vertices(scene),min=[0,1,2].map(i=>Math.min(...all.map(p=>p.getComponent(i)))),max=[0,1,2].map(i=>Math.max(...all.map(p=>p.getComponent(i))));
const expected={min:[-.5,0,-.45],max:[.5,1,.5]};for(const edge of ['min','max'])if((edge==='min'?min:max).some((x,i)=>Math.abs(x-expected[edge][i])>1e-5))throw Error('ActualGLB bounds mismatch');
const ports={anchor_port_east:[.5,.92,0],anchor_port_west:[-.5,.92,0],anchor_port_branch:[0,.92,.5]};
for(const [name,target]of Object.entries(ports))if(scene.getObjectByName(name).getWorldPosition(new Vector3()).distanceTo(new Vector3(...target))>1e-5)throw Error('Port mismatch '+name);
const result={status:'PASS',method:'Actual GLB decoded with pinned Three GLTFLoader; actual16-edge hole loop, world-space vertices and91 physical joint poses',actual_hole_edges:holeEdges.length,poses:91,tested_disk_vertices:count,max_actual_disk_radius_m:maxRadius,min_actual_hole_margin_m:minHoleMargin,bounds:{min,max},ports,carrier_anchor_world:[0,.92,0],reset_angle_rad:pivot.rotation.y,actual_source_events_tested:false};
await writeFile('docs/adaptive-v3/evidence/M13.3-transfer-numeric.json',JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
