import * as THREE from 'three';
import type {BoundCargo} from './warehouseCargo';

export type CargoMeshPart = {mesh:THREE.InstancedMesh; index:number; sourceMatrix:THREE.Matrix4};
export type CargoSupportPart = CargoMeshPart | {mesh:THREE.Mesh; index?:never};
type Point = [number,number];
type Triangle = {points:Point[]; y:number; normal_y:number; part:string};
type SupportState = {mesh:THREE.Mesh; index:number|undefined; matrix:THREE.Matrix4; visible:boolean; geometry:THREE.BufferGeometry; position:THREE.BufferAttribute|THREE.InterleavedBufferAttribute; positionVersion:number; indices:THREE.BufferAttribute|null; indexVersion:number};
const EPS=2e-6;
const cross=(a:Point,b:Point,c:Point)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
const area=(p:Point[])=>Math.abs(p.reduce((s,a,i)=>{const b=p[(i+1)%p.length];return s+a[0]*b[1]-a[1]*b[0];},0))/2;
function ccw(points:Point[]){return cross(points[0],points[1],points[2])<0?[...points].reverse():points;}
function clip(subject:Point[],boundary:Point[]){
 let output=subject;
 for(let i=0;i<boundary.length&&output.length;i++){
  const a=boundary[i],b=boundary[(i+1)%boundary.length],input=output;output=[];
  for(let j=0;j<input.length;j++){
   const p=input[j],q=input[(j+1)%input.length],dp=cross(a,b,p),dq=cross(a,b,q),insideP=dp>=-1e-12,insideQ=dq>=-1e-12;
   if(insideP)output.push(p);
   if(insideP!==insideQ){const u=dp/(dp-dq);output.push([p[0]+u*(q[0]-p[0]),p[1]+u*(q[1]-p[1])]);}
  }
 }
 return output;
}
function hull(points:Point[]){
 const unique=[...new Map(points.map(p=>[p.map(x=>x.toFixed(8)).join(','),p])).values()].sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
 if(unique.length<3)return unique;
 const half=(rows:Point[])=>{const out:Point[]=[];for(const p of rows){while(out.length>=2&&cross(out[out.length-2],out[out.length-1],p)<=1e-12)out.pop();out.push(p);}return out;};
 return [...half(unique).slice(0,-1),...half([...unique].reverse()).slice(0,-1)];
}
function worldMatrix(part:CargoSupportPart){
 part.mesh.updateWorldMatrix(true,false);const matrix=part.mesh.matrixWorld.clone();
 if(part.mesh instanceof THREE.InstancedMesh){const index=part.index;if(typeof index!=='number'||!Number.isInteger(index)||index<0||index>=part.mesh.count)throw Error('INVALID_SUPPORT_INSTANCE');const instance=new THREE.Matrix4();part.mesh.getMatrixAt(index,instance);matrix.multiply(instance);}
 return matrix;
}
function visible(part:CargoSupportPart){for(let node:THREE.Object3D|null=part.mesh;node;node=node.parent)if(!node.visible)return false;return true;}
function supportState(part:CargoSupportPart):SupportState{
 const geometry=part.mesh.geometry,position=geometry.getAttribute('position'),indices=geometry.index;
 return {mesh:part.mesh,index:part.index,matrix:worldMatrix(part),visible:visible(part),geometry,position,positionVersion:position instanceof THREE.InterleavedBufferAttribute?position.data.version:position.version,indices,indexVersion:indices?.version??0};
}
function sameState(a:SupportState,b:SupportState){return a.mesh===b.mesh&&a.index===b.index&&a.matrix.equals(b.matrix)&&a.visible===b.visible&&a.geometry===b.geometry&&a.position===b.position&&a.positionVersion===b.positionVersion&&a.indices===b.indices&&a.indexVersion===b.indexVersion;}
function vertices(part:CargoSupportPart,m=worldMatrix(part)){
 const positions=part.mesh.geometry.getAttribute('position'),points:THREE.Vector3[]=[];
 for(let i=0;i<positions.count;i++)points.push(new THREE.Vector3().fromBufferAttribute(positions,i).applyMatrix4(m));
 return points;
}
function horizontalTriangles(part:CargoSupportPart,points:THREE.Vector3[]){
 const index=part.mesh.geometry.index,count=index?.count??points.length,out:Triangle[]=[];
 for(let i=0;i<count;i+=3){const p=[0,1,2].map(j=>points[index?index.getX(i+j):i+j]);if(Math.max(...p.map(v=>v.y))-Math.min(...p.map(v=>v.y))>EPS)continue;
  const normal=new THREE.Vector3().subVectors(p[1],p[0]).cross(new THREE.Vector3().subVectors(p[2],p[0])).normalize(),xz=ccw(p.map(v=>[v.x,v.z] as Point));if(area(xz)>1e-12)out.push({points:xz,y:p.reduce((s,v)=>s+v.y,0)/3,normal_y:normal.y,part:part.mesh.name});
 }
 return out;
}

/** Exact triangle intersections on native horizontal support faces; no AABB contact substitute. */
export function createCargoGeometryInspector(cargoParts:Map<string,CargoMeshPart[]>,moduleParts:Map<string,CargoSupportPart[]>){
 const storageFaces=new Map<string,{states:SupportState[];faces:Triangle[]}>();
 function inspect(bound:BoundCargo){
  const parts=cargoParts.get(bound.handling_unit_id);if(!parts?.length)throw Error('UNKNOWN_CARGO_INSTANCE');
  const worldBox=new THREE.Box3(),localBox=new THREE.Box3(),root=new THREE.Matrix4().compose(new THREE.Vector3(...bound.position),new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),bound.yaw_rad),new THREE.Vector3(1,1,1)),inverse=root.invert();
  let vertexCount=0;const bottom:Triangle[]=[];
  for(const part of parts){const points=vertices(part);for(const point of points){worldBox.expandByPoint(point);localBox.expandByPoint(point.clone().applyMatrix4(inverse));vertexCount++;}bottom.push(...horizontalTriangles(part,points));}
  const bottomFaces=bottom.filter(f=>f.normal_y<-.999999&&Math.abs(f.y-worldBox.min.y)<EPS),supportPoints:Point[]=[],supportNames=new Set<string>();let contactArea=0,maxContactGap=0;
  return {parts,worldBox,localBox,vertexCount,bottomFaces,supportPoints,supportNames,contactArea,maxContactGap};
 }
 function cargoObservation(bound:BoundCargo,data:ReturnType<typeof inspect>){return {handling_unit_id:bound.handling_unit_id,destination:bound.destination,position:bound.position,yaw_rad:bound.yaw_rad,dimensions_xyz_m:bound.cargo.dimensions_xyz_m,gross_mass_kg:bound.cargo.gross_mass_kg,quantity_units:bound.cargo.quantity_units,model_scale_factor:1,
  mesh_parts:data.parts.length,mesh_instances:data.parts.map(p=>({uuid:p.mesh.uuid,index:p.index})),vertices:data.vertexCount,
  bounds_world:{min:data.worldBox.min.toArray(),max:data.worldBox.max.toArray()},bounds_cargo_local:{min:data.localBox.min.toArray(),max:data.localBox.max.toArray()},actual_bottom_gap_m:data.worldBox.min.y-bound.position[1]};}
 // Side-clamped cargo needs independent hand-contact evidence; bounds do not imply a floor contact.
 function inspectGeometry(bound:BoundCargo){const data=inspect(bound);return {...cargoObservation(bound,data),support_scope:'Native cargo mesh bounds only; no support, hand-contact, strength or stability conclusion.',source_kind:'visual_fixture',engine_operation:false};}
 function inspectSupported(bound:BoundCargo,destinationModuleId:string){
  const data=inspect(bound),support=moduleParts.get(destinationModuleId);
  if(!support)throw Error('UNKNOWN_STORAGE_SUPPORT');
  // A moving carrier/joint or changed native geometry must never reuse old world-space faces.
  // Buffer writes follow Three.js needsUpdate/version semantics; invalidateSupport is also explicit.
  const states=support.map(supportState),cached=storageFaces.get(destinationModuleId);
  if(!cached||cached.states.length!==states.length||states.some((state,i)=>!sameState(state,cached.states[i])))storageFaces.set(destinationModuleId,{states,faces:support.flatMap((p,i)=>states[i].visible?horizontalTriangles(p,vertices(p,states[i].matrix)):[]).filter(f=>f.normal_y>.999999)});
  for(const a of data.bottomFaces)for(const b of storageFaces.get(destinationModuleId)!.faces){
   if(Math.abs(a.y-b.y)>EPS)continue;
   const contact=clip(a.points,b.points),size=area(contact);if(size<1e-10)continue;
   data.contactArea+=size;data.maxContactGap=Math.max(data.maxContactGap,Math.abs(a.y-b.y));data.supportPoints.push(...contact);data.supportNames.add(b.part);
  }
  const polygon=hull(data.supportPoints),centre:Point=[bound.position[0],bound.position[2]],centreSupported=polygon.length>=3&&polygon.every((p,i)=>cross(p,polygon[(i+1)%polygon.length],centre)>=-EPS*Math.hypot(polygon[(i+1)%polygon.length][0]-p[0],polygon[(i+1)%polygon.length][1]-p[1]));
  return {...cargoObservation(bound,data),native_contact_area_sum_m2:data.contactArea,maximum_contact_gap_m:data.maxContactGap,native_support_hull_xz:polygon,geometric_centre_inside_support_hull:centreSupported,support_parts:[...data.supportNames],
   support_scope:'Native horizontal triangle contact and footprint-centre support proxy only; no strength or stability certification.',source_kind:'visual_fixture',engine_operation:false};
 }
 function invalidateSupport(id?:string){if(id===undefined)storageFaces.clear();else storageFaces.delete(id);}
 return {inspectSupported,inspectGeometry,invalidateSupport,dispose:()=>storageFaces.clear()};
}
