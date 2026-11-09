import * as THREE from 'three';
import {createWarehouseCargo} from '../warehouseCargo';
import type {WarehouseBundle,XYZ} from '../warehouseTypes';

export type LayoutRect={min:[number,number];max:[number,number]};
export type LayoutBox={min:XYZ;max:XYZ};
export type LayoutModule={module_id:string;source_module_id?:string;prototype_module_id:string;family?:string;storage_family?:string;world_pos?:XYZ;position_world:XYZ;yaw_rad:number;outer_bounds_world:LayoutBox;is_new:boolean};
export type LayoutHU={handling_unit_id:string;source_slot_id:string;target_module_id:string;target_slot_id:string;position_world:XYZ;yaw_rad:number};
export type LayoutActor={actor_id:string;world_pos?:XYZ;position_world?:XYZ;planned_world_pos?:XYZ;yaw_rad?:number};
export type LayoutZone={zone_id:string;family?:string;floor_bounds_xz_m:LayoutRect};
export type LayoutViewBounds={position:XYZ;yaw:number;min:XYZ;max:XYZ;bounds:LayoutBox;dimensions?:XYZ;module?:LayoutModule;HU?:LayoutHU};
/** A separately validated candidate. This renderer does not grant route/engine admission. */
export type TwinLayoutPlan={candidate_id:string;layout_version:string;source_kind:string;engine_operation?:boolean;plan_sha256:string;source_hashes:Record<string,string>;modules:readonly LayoutModule[];HUs:readonly LayoutHU[];actor_homes:readonly LayoutActor[];zones:readonly LayoutZone[]};
type MeshState={mesh:THREE.InstancedMesh;position:THREE.Vector3;attribute:THREE.InstancedBufferAttribute;count:number;visible:boolean;frustum:boolean;sphere:THREE.Sphere|null;box:THREE.Box3|null;bSphere:THREE.Sphere;bBox:THREE.Box3;bPosition:THREE.Vector3;bAttribute:THREE.InstancedBufferAttribute};
type ActorState={node:THREE.Object3D;position:THREE.Vector3;quaternion:THREE.Quaternion;bPosition:THREE.Vector3;bQuaternion:THREE.Quaternion;delta:THREE.Vector3};
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const triple=(v:unknown):v is XYZ=>Array.isArray(v)&&v.length===3&&v.every(finite);
function requireValue(v:unknown,message:string):asserts v{if(!v)throw Error(message);}
const pose=(p:XYZ,yaw:number)=>new THREE.Matrix4().compose(new THREE.Vector3(...p),new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),yaw),new THREE.Vector3(1,1,1));
const freeze=<T>(v:T):T=>{if(v&&typeof v==='object'){for(const x of Object.values(v))freeze(x);Object.freeze(v);}return v;};
const origin=(points:XYZ[])=>new THREE.Vector3(Math.round((Math.min(...points.map(p=>p[0]))+Math.max(...points.map(p=>p[0])))/2),0,Math.round((Math.min(...points.map(p=>p[2]))+Math.max(...points.map(p=>p[2])))/2));
const storageZone=(z:LayoutZone)=>/^(SMALL|STANDARD|HEAVY|LONG|FLEX|RESERVE)(_|$)/.test(z.zone_id)||['SMALL','STANDARD','HEAVY','LONG','FLEX'].includes(z.family??'');

/** Prepare every B buffer first, then install. A's original buffers, transforms,
 * parents, stock identities and resources are retained and restored after each pass. */
export function createTwinLayoutVariant(scene:THREE.Scene,bundle:WarehouseBundle,input:TwinLayoutPlan){
 requireValue(input?.source_kind==='visual_fixture'&&input.engine_operation!==true&&typeof input.candidate_id==='string'&&/^[a-f0-9]{64}$/.test(input.plan_sha256),'INVALID_LAYOUT_CANDIDATE');
 const plan=freeze(structuredClone(input)),modules=new Map(plan.modules.map(m=>[m.module_id,m])),HUs=new Map(plan.HUs.map(h=>[h.handling_unit_id,h]));
 const sourceModules=new Map(bundle.layout.modules.map(m=>[m.module_id,m])),sourceHUs=new Map(createWarehouseCargo(bundle).snapshot().map(h=>[h.handling_unit_id,h]));
 requireValue(modules.size===plan.modules.length&&HUs.size===plan.HUs.length&&HUs.size===sourceHUs.size,'LAYOUT_IDENTITY_COUNT_MISMATCH');
 for(const id of sourceModules.keys())requireValue(modules.has(id)&&!modules.get(id)!.is_new,'LAYOUT_REMOVES_SOURCE_MODULE');
 for(const m of plan.modules){requireValue(triple(m.position_world)&&finite(m.yaw_rad)&&sourceModules.has(m.prototype_module_id),'INVALID_LAYOUT_MODULE');requireValue(m.is_new?!sourceModules.has(m.module_id):sourceModules.has(m.module_id),'INVALID_LAYOUT_MODULE_ID');requireValue((m.storage_family??m.family)===sourceModules.get(m.prototype_module_id)!.family,'LAYOUT_PROTOTYPE_FAMILY_MISMATCH');}
 const sourceSlots=new Map(bundle.layout.slots.map(s=>[s.slot_id,s]));
 for(const h of plan.HUs){
  requireValue(sourceHUs.has(h.handling_unit_id)&&modules.has(h.target_module_id)&&triple(h.position_world)&&finite(h.yaw_rad),'INVALID_LAYOUT_HU');
  const source=sourceHUs.get(h.handling_unit_id)!;requireValue(source.destination.kind==='storage_slot'&&source.destination.slot_id===h.source_slot_id&&h.target_slot_id===h.source_slot_id,'LAYOUT_SOURCE_SLOT_IDENTITY_CHANGED');
  const slot=sourceSlots.get(h.source_slot_id)!;const from=bundle.layout.modules[slot.module_index],to=modules.get(h.target_module_id)!;requireValue(to.module_id===from.module_id&&!to.is_new,'LAYOUT_HU_MUST_RETAIN_ORIGINAL_MODULE_SLOT');
  const expected=new THREE.Vector3(...source.position).applyMatrix4(pose(to.position_world,to.yaw_rad).multiply(pose(from.world_pos,from.yaw_rad).invert()));
  requireValue(expected.distanceTo(new THREE.Vector3(...h.position_world))<1e-7&&Math.abs(Math.atan2(Math.sin(h.yaw_rad-source.yaw_rad-to.yaw_rad+from.yaw_rad),Math.cos(h.yaw_rad-source.yaw_rad-to.yaw_rad+from.yaw_rad)))<1e-8,'LAYOUT_HU_NOT_RIGID_WITH_MODULE');
 }
 const rows:MeshState[]=[],actors:ActorState[]=[],extra=new THREE.Group(),paint=new THREE.Group(),owned:(THREE.BufferGeometry|THREE.Material|THREE.Texture)[]=[],created:THREE.InstancedMesh[]=[],hidden:{node:THREE.Object3D;visible:boolean}[]=[];
 extra.name='candidate_B_extra_empty_modules';paint.name='candidate_B_section_markings';extra.visible=paint.visible=false;extra.userData.candidateLayoutVisual=true;
 let applied:'A'|'B'='A',disposed=false;
 const own=<T extends THREE.BufferGeometry|THREE.Material|THREE.Texture>(r:T)=>{owned.push(r);return r;};
 const worldParts=new Map<string,{mesh:THREE.InstancedMesh;index:number;world:THREE.Matrix4;intrinsic:THREE.Matrix4}[]>();
 const zoneById=new Map(plan.zones.filter(storageZone).map(z=>[z.zone_id,z]));
 const sourceZones=new Map((bundle.layout.data.zones as {zone_id:string;floor_bounds_xz_m:LayoutRect}[]).map(z=>[z.zone_id,z]));
 const changedZones=new Set([...zoneById].filter(([id,z])=>JSON.stringify(z.floor_bounds_xz_m)!==JSON.stringify(sourceZones.get(id)?.floor_bounds_xz_m)).map(([id])=>id));
 const sourceActors=new Map<string,THREE.Object3D>(),actorBoxes=new Map<string,THREE.Box3>();
 try{
  scene.updateMatrixWorld(true);
  const sourceMeshes:THREE.InstancedMesh[]=[];
  scene.traverse(n=>{
   for(let p:THREE.Object3D|null=n;p;p=p.parent)if(p.userData.candidateLayoutVisual)return;
   if(n instanceof THREE.InstancedMesh&&['module','HU'].includes(n.userData.semanticKind))sourceMeshes.push(n);
   if(n.userData.semanticKind==='actor'&&typeof n.userData.semanticId==='string')sourceActors.set(n.userData.semanticId,n);
   // Native zone leaves have their own parent; columns, fixed gates and road markings are untouched.
   const parent=n.userData.batch_parent as string|undefined;
   if(n instanceof THREE.Mesh&&parent?.startsWith('zone__')&&changedZones.has(parent.slice(6)))hidden.push({node:n,visible:n.visible});
  });
  for(const[id,node]of sourceActors)actorBoxes.set(id,new THREE.Box3().setFromObject(node));
  for(const mesh of sourceMeshes){
   const ids=mesh.userData.semanticIds as string[];requireValue(Array.isArray(ids)&&ids.length===mesh.count,'LAYOUT_INSTANCE_IDS_REQUIRED');
   const isModule=mesh.userData.semanticKind==='module',dest=ids.map(id=>isModule?modules.get(id)?.position_world:HUs.get(id)?.position_world);requireValue(dest.every(triple),'LAYOUT_MISSING_INSTANCE_POSE');
   const bPosition=origin(dest as XYZ[]),bWorld=new THREE.Matrix4().compose(bPosition,mesh.quaternion,mesh.scale),inverse=bWorld.clone().invert(),array=new Float32Array(mesh.instanceMatrix.array.length);
   for(let i=0;i<ids.length;i++){
    const id=ids[i],instance=new THREE.Matrix4();mesh.getMatrixAt(i,instance);const world=mesh.matrixWorld.clone().multiply(instance);
    if(isModule){const source=sourceModules.get(id)!;requireValue(source,'UNKNOWN_SOURCE_MODULE_INSTANCE');const intrinsic=pose(source.world_pos,source.yaw_rad).invert().multiply(world);const parts=worldParts.get(id)??[];parts.push({mesh,index:i,world,intrinsic});worldParts.set(id,parts);const next=modules.get(id)!;inverse.clone().multiply(pose(next.position_world,next.yaw_rad)).multiply(intrinsic).toArray(array,i*16);}
    else{const source=sourceHUs.get(id)!,next=HUs.get(id)!;requireValue(source,'UNKNOWN_SOURCE_HU_INSTANCE');const delta=pose(next.position_world,next.yaw_rad).multiply(pose(source.position,source.yaw_rad).invert());inverse.clone().multiply(delta).multiply(world).toArray(array,i*16);}
   }
   if(!mesh.geometry.boundingSphere)mesh.geometry.computeBoundingSphere();if(!mesh.geometry.boundingBox)mesh.geometry.computeBoundingBox();const bSphere=new THREE.Sphere().makeEmpty(),bBox=new THREE.Box3();
   for(let i=0;i<ids.length;i++){const m=new THREE.Matrix4().fromArray(array,i*16);bSphere.union(mesh.geometry.boundingSphere!.clone().applyMatrix4(m));bBox.union(mesh.geometry.boundingBox!.clone().applyMatrix4(m));}
   rows.push({mesh,position:mesh.position.clone(),attribute:mesh.instanceMatrix,count:mesh.count,visible:mesh.visible,frustum:mesh.frustumCulled,sphere:mesh.boundingSphere,box:mesh.boundingBox,bSphere,bBox,bPosition,bAttribute:new THREE.InstancedBufferAttribute(array,16)});
  }
  // Group extra empty modules by each native prototype part; geometry/materials are borrowed unchanged.
  const groups=new Map<THREE.InstancedMesh,{module:LayoutModule;intrinsic:THREE.Matrix4}[]>();
  for(const m of plan.modules.filter(m=>m.is_new))for(const p of worldParts.get(m.prototype_module_id)??[]){const list=groups.get(p.mesh)??[];list.push({module:m,intrinsic:p.intrinsic});groups.set(p.mesh,list);}
  requireValue(plan.modules.filter(m=>m.is_new).every(m=>worldParts.has(m.prototype_module_id)),'LAYOUT_NATIVE_PROTOTYPE_MISSING');
  for(const [source,list]of groups){const mesh=new THREE.InstancedMesh(source.geometry,source.material,list.length),base=origin(list.map(r=>r.module.position_world)),inverse=new THREE.Matrix4().makeTranslation(-base.x,0,-base.z);mesh.position.copy(base);mesh.name='candidate_B__'+source.name;mesh.castShadow=source.castShadow;mesh.receiveShadow=source.receiveShadow;mesh.frustumCulled=false;mesh.userData.semanticKind='module';mesh.userData.semanticIds=list.map(r=>r.module.module_id);for(let i=0;i<list.length;i++)mesh.setMatrixAt(i,inverse.clone().multiply(pose(list[i].module.position_world,list[i].module.yaw_rad)).multiply(list[i].intrinsic));mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingBox();mesh.computeBoundingSphere();created.push(mesh);extra.add(mesh);}
  const role=new Map(bundle.registry.workers.map(w=>[w.actor_id,w.baseline_role]));
  for(const h of plan.actor_homes){const node=sourceActors.get(h.actor_id);requireValue(node,'LAYOUT_ACTOR_MISSING');if(role.get(h.actor_id)!=='picker')continue;const target=h.position_world??h.world_pos??h.planned_world_pos;requireValue(triple(target),'LAYOUT_ACTOR_HOME_REQUIRED');const previous=node.getWorldPosition(new THREE.Vector3()),q=finite(h.yaw_rad)?new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),h.yaw_rad):node.getWorldQuaternion(new THREE.Quaternion()),world=pose(target,0);world.makeRotationFromQuaternion(q);world.setPosition(new THREE.Vector3(...target));const local=(node.parent?.matrixWorld.clone().invert()??new THREE.Matrix4()).multiply(world),bp=new THREE.Vector3(),bq=new THREE.Quaternion(),bs=new THREE.Vector3();local.decompose(bp,bq,bs);requireValue(bs.distanceTo(node.scale)<1e-8,'LAYOUT_ACTOR_SCALE_CHANGED');actors.push({node,position:node.position.clone(),quaternion:node.quaternion.clone(),bPosition:bp,bQuaternion:bq,delta:new THREE.Vector3(...target).sub(previous)});}
  for(const z of [...zoneById.values()].filter(z=>changedZones.has(z.zone_id))){
   const {min,max}=z.floor_bounds_xz_m;requireValue(min?.every(finite)&&max?.every(finite)&&max[0]>min[0]&&max[1]>min[1],'INVALID_LAYOUT_ZONE');const w=max[0]-min[0],d=max[1]-min[1],cx=(min[0]+max[0])/2,cz=(min[1]+max[1])/2;
   const fill=new THREE.Mesh(own(new THREE.PlaneGeometry(w,d)),own(new THREE.MeshBasicMaterial({color:'#c8ded1',transparent:true,opacity:.12,depthWrite:false})));fill.rotation.x=-Math.PI/2;fill.position.set(cx,.025,cz);paint.add(fill);
   const edge=new THREE.LineLoop(own(new THREE.BufferGeometry().setFromPoints([[min[0],.035,min[1]],[max[0],.035,min[1]],[max[0],.035,max[1]],[min[0],.035,max[1]]].map(p=>new THREE.Vector3(...p)))),own(new THREE.LineBasicMaterial({color:'#78b294',transparent:true,opacity:.7})));paint.add(edge);
   if(typeof document!=='undefined'){
    const canvas=document.createElement('canvas');canvas.width=768;canvas.height=96;const g=canvas.getContext('2d')!;g.fillStyle='#33594c';g.font='600 48px system-ui,sans-serif';g.textAlign='center';g.textBaseline='middle';g.fillText(z.zone_id,384,48);
    const texture=own(new THREE.CanvasTexture(canvas));texture.colorSpace=THREE.SRGBColorSpace;
    const label=new THREE.Mesh(own(new THREE.PlaneGeometry(5,.625)),own(new THREE.MeshBasicMaterial({map:texture,transparent:true,depthWrite:false})));label.rotation.x=-Math.PI/2;label.position.set(cx,.045,min[1]+.5);paint.add(label);
   }
  }
  scene.add(extra);extra.updateWorldMatrix(true,true);
 }catch(e){for(const mesh of created)mesh.dispose();for(const r of owned)r.dispose();throw e;}
 function apply(v:'A'|'B'){
  if(disposed)throw Error('LAYOUT_VARIANT_DISPOSED');
  for(const r of rows){r.mesh.position.copy(v==='B'?r.bPosition:r.position);r.mesh.instanceMatrix=v==='B'?r.bAttribute:r.attribute;r.mesh.boundingSphere=v==='B'?r.bSphere:r.sphere;r.mesh.boundingBox=v==='B'?r.bBox:r.box;r.mesh.count=r.count;r.mesh.visible=r.visible;r.mesh.frustumCulled=v==='B'?false:r.frustum;r.mesh.updateWorldMatrix(true,false);}
  for(const r of actors){r.node.position.copy(v==='B'?r.bPosition:r.position);r.node.quaternion.copy(v==='B'?r.bQuaternion:r.quaternion);r.node.updateWorldMatrix(true,true);}
  for(const r of hidden)r.node.visible=v==='B'?false:r.visible;
  extra.visible=paint.visible=v==='B';applied=v;
 }
 const actorDelta=(id:string)=>actors.find(a=>a.node.userData.semanticId===id)?.delta.clone()??new THREE.Vector3();
 function bounds(kind:'HU'|'module'|'actor',id:string):LayoutViewBounds|null{
  if(kind==='module'){const m=modules.get(id);return m?{position:[...m.position_world] as XYZ,yaw:m.yaw_rad,...structuredClone(m.outer_bounds_world),bounds:structuredClone(m.outer_bounds_world),module:m}:null;}
  if(kind==='HU'){const h=HUs.get(id),source=sourceHUs.get(id);if(!h||!source)return null;const d=source.cargo.dimensions_xyz_m,c=Math.abs(Math.cos(h.yaw_rad)),s=Math.abs(Math.sin(h.yaw_rad)),x=(c*d[0]+s*d[2])/2,z=(s*d[0]+c*d[2])/2,bounds={min:[h.position_world[0]-x,h.position_world[1],h.position_world[2]-z] as XYZ,max:[h.position_world[0]+x,h.position_world[1]+d[1],h.position_world[2]+z] as XYZ};return {position:[...h.position_world] as XYZ,yaw:h.yaw_rad,dimensions:[...d] as XYZ,...bounds,bounds,HU:h};}
  const node=sourceActors.get(id);if(!node)return null;const row=actors.find(a=>a.node===node),p=row?row.bPosition.clone().applyMatrix4(node.parent?.matrixWorld??new THREE.Matrix4()):node.getWorldPosition(new THREE.Vector3()),box=actorBoxes.get(id)!.clone().translate(actorDelta(id)),bounds={min:box.min.toArray() as XYZ,max:box.max.toArray() as XYZ};return {position:p.toArray() as XYZ,yaw:0,...bounds,bounds};
 }
 function snapshot(){return {candidate_id:plan.candidate_id,layout_version:plan.layout_version,plan_sha256:plan.plan_sha256,module_count:plan.modules.length,source_module_count:sourceModules.size,added_empty_modules:plan.modules.filter(m=>m.is_new).length,HU_count:HUs.size,source_HU_count:sourceHUs.size,relocated_picker_homes:actors.length,hidden_old_zone_leaves:hidden.length,applied,A_restored:applied==='A'&&rows.every(r=>r.mesh.instanceMatrix===r.attribute&&r.mesh.position.equals(r.position))&&actors.every(r=>r.node.position.equals(r.position)&&r.node.quaternion.equals(r.quaternion)),source_kind:'visual_fixture',engine_operation:false,stock_created:0,geometry_or_materials_scaled:false,route_admission:'separate candidate route validation required'};}
 function dispose(){if(disposed)return;apply('A');disposed=true;extra.removeFromParent();paint.removeFromParent();for(const m of created)m.dispose();for(const r of owned)r.dispose();}
 return {apply,bounds,actorDelta,snapshot,dispose,paint,plan,zones:zoneById};
}
