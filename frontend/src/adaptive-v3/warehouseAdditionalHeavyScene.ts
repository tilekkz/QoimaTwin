import * as THREE from 'three';
import {createWarehouseCargo} from './warehouseCargo';
import {captureAdditionalHeavyCase,sampleAdditionalHeavyCapture,isWarehouseAdditionalHeavyPlan,compileWarehouseAdditionalHeavyCase} from './warehouseAdditionalHeavyCases';
import type {WarehouseBundle} from './warehouseTypes';

type Plan=ReturnType<typeof compileWarehouseAdditionalHeavyCase>;
type Sample=ReturnType<Plan['sample']>;
type Wheels=Sample['wheel_angles_rad'];
export type AdditionalHeavyDisplayRow={case_id:string;local_s:number;active:boolean;wheel_offset_rad:Wheels;sample?:Sample;job_id?:string;start_s?:number;end_s?:number};
type Local={node:THREE.Object3D;parent:THREE.Object3D|null;p:THREE.Vector3;q:THREE.Quaternion;s:THREE.Vector3};
const Y=new THREE.Vector3(0,1,0),X=new THREE.Vector3(1,0,0),UNIT=new THREE.Vector3(1,1,1),owners=new WeakSet<THREE.Scene>();
const pose=(p:readonly number[],yaw:number)=>new THREE.Matrix4().compose(new THREE.Vector3(...p),new THREE.Quaternion().setFromAxisAngle(Y,yaw),UNIT);
const save=(node:THREE.Object3D):Local=>({node,parent:node.parent,p:node.position.clone(),q:node.quaternion.clone(),s:node.scale.clone()});
const restore=(rows:readonly Local[])=>{for(const r of rows){r.node.position.copy(r.p);r.node.quaternion.copy(r.q);r.node.scale.copy(r.s);}};
function need(v:unknown,reason:string):asserts v{if(!v)throw Error(reason);}
const angleError=(a:THREE.Quaternion,b:THREE.Quaternion)=>{const d=a.clone().multiply(b.clone().invert()).normalize();return 2*Math.atan2(Math.hypot(d.x,d.y,d.z),Math.abs(d.w));};

/** Borrow one original F01/FL01. Only the active case moves it; completed HUs
 * retain their actual source meshes at their terminal slots. No staging clones. */
export function createWarehouseAdditionalHeavyScene(scene:THREE.Scene,bundle:WarehouseBundle,plans:readonly Plan[]){
 need(scene?.isScene&&!owners.has(scene),'ADDITIONAL_HEAVY_SCENE_BUSY');
 need(plans.length>0&&plans.every(isWarehouseAdditionalHeavyPlan)&&new Set(plans.map(p=>p.case.case_id)).size===plans.length&&new Set(plans.map(p=>p.case.receipt.handling_unit_id)).size===plans.length,'UNIQUE_ISSUED_ADDITIONAL_PLANS_REQUIRED');
 const actorIDs=new Map<string,THREE.Object3D>(),vehicles=new Map<string,THREE.Object3D>();scene.traverse(n=>{if(n.userData.semanticKind==='actor'){need(!actorIDs.has(n.userData.semanticId),'DUPLICATE_VISIBLE_SOURCE_ACTOR');actorIDs.set(n.userData.semanticId,n);}if(n.name.startsWith('vehicle__'))vehicles.set(n.name.slice(9),n);});
 need(actorIDs.size===24&&vehicles.size===2&&bundle.registry.workers.length===24&&bundle.registry.vehicles.length===2,'ORIGINAL_24_WORKERS_2_VEHICLES_REQUIRED');
 const vehicle=vehicles.get('FL01'),driver=actorIDs.get('F01');need(vehicle&&driver,'ORIGINAL_FL01_F01_REQUIRED');let parent:THREE.Object3D|null=driver;while(parent&&parent!==vehicle)parent=parent.parent;need(parent===vehicle,'F01_MUST_REMAIN_SEATED_IN_FL01');
 const original:Local[]=[];vehicle.traverse(n=>original.push(save(n)));const bases=new Map(original.map(r=>[r.node,r])),joint=(name:string)=>{const n=vehicle.getObjectByName(name);need(n,'ADDITIONAL_NATIVE_JOINT_MISSING:'+name);return n;},carriage=joint('joint__carriage'),reach=joint('joint__reach');
 for(const s of ['L','R'])for(const n of ['joint__fork_'+s,'joint__rear_steer_'+s,'joint__wheel_front_'+s,'joint__wheel_rear_'+s])joint(n);
 const sourceCargo=createWarehouseCargo(bundle).snapshot(),stockIDs=new Set(sourceCargo.map(h=>h.handling_unit_id)),owned=new THREE.Group();owned.name='additional_heavy_display_fixture';
 const entries=new Map<string,{plan:Plan;root:THREE.Group;capture:readonly number[];parts:number;current:Sample|null;positionError:number;orientationError:number}>();let disposed=false,currentRows:readonly AdditionalHeavyDisplayRow[]=[];
 function body(s:Sample,offset:Wheels){restore(original);const matrix=pose(s.body.position,s.body.yaw_rad);if(vehicle!.parent)matrix.premultiply(vehicle!.parent.matrixWorld.clone().invert());matrix.decompose(vehicle!.position,vehicle!.quaternion,vehicle!.scale);carriage.position.y=s.joints.fork_top_m;reach.position.z=bases.get(reach)!.p.z+s.joints.extension_m;for(const[side,sign]of[['L',-1],['R',1]] as const){joint('joint__fork_'+side).position.x=sign*s.joints.fork_halfspacing_m;const steer=joint('joint__rear_steer_'+side);steer.quaternion.copy(bases.get(steer)!.q).multiply(new THREE.Quaternion().setFromAxisAngle(Y,s.joints.rear_steer_rad[side]));for(const axle of['front','rear'] as const){const wheel=joint('joint__wheel_'+axle+'_'+side),key=`${axle}_${side}` as keyof Wheels;wheel.quaternion.copy(bases.get(wheel)!.q).multiply(new THREE.Quaternion().setFromAxisAngle(X,s.wheel_angles_rad[key]+offset[key]));}}vehicle!.updateWorldMatrix(true,true);}
 const zero:Wheels={front_L:0,front_R:0,rear_L:0,rear_R:0};
 try{scene.updateMatrixWorld(true);for(const plan of plans){
   const c=plan.case;need(!stockIDs.has(c.receipt.handling_unit_id),'ADDITIONAL_HU_MUST_NOT_REPLACE_STOCK');
   const support=scene.getObjectByName(c.stage.support_id);need(support&&support.userData.semanticKind==='staging_support','EXISTING_PROVED_STAGE_SUPPORT_REQUIRED');
   need(support.getWorldPosition(new THREE.Vector3()).distanceTo(new THREE.Vector3(...c.stage.support_position))<=2e-6&&angleError(support.getWorldQuaternion(new THREE.Quaternion()),new THREE.Quaternion().setFromAxisAngle(Y,c.stage.support_yaw_rad))<=1e-8&&support.getWorldScale(new THREE.Vector3()).distanceTo(UNIT)<1e-9,'EXACT_STAGE_SUPPORT_FRAME_REQUIRED');
   const prototype=sourceCargo.find(h=>h.cargo.archetype_id===c.receipt.archetype_id);need(prototype,'ORIGINAL_CARGO_PROTOTYPE_REQUIRED');
   const root=new THREE.Group();root.name='incoming__'+c.receipt.handling_unit_id;root.userData={semanticKind:'HU',semanticId:c.receipt.handling_unit_id,incoming:true,additional_heavy:true};root.visible=false;let parts=0;
   const inverse=pose(prototype.position,prototype.yaw_rad).invert();scene.traverse(n=>{if(!(n instanceof THREE.InstancedMesh)||n.userData.semanticKind!=='HU')return;const i=(n.userData.semanticIds as string[]).indexOf(prototype.handling_unit_id);if(i<0)return;const matrix=new THREE.Matrix4();n.getMatrixAt(i,matrix);const mesh=new THREE.Mesh(n.geometry,n.material);mesh.name='additional_borrowed__'+n.name;mesh.matrixAutoUpdate=false;mesh.matrix.copy(inverse.clone().multiply(n.matrixWorld).multiply(matrix));mesh.castShadow=mesh.receiveShadow=true;root.add(mesh);parts++;});need(parts>0,'ORIGINAL_CARGO_NATIVE_PARTS_REQUIRED');owned.add(root);
   const atAttach=plan.sample(plan.attach_at_s);body(atAttach,zero);const capture=captureAdditionalHeavyCase(c,reach.matrixWorld,pose(atAttach.cargo.position,atAttach.cargo.yaw_rad));
   body(plan.sample(plan.release_at_s),zero);const release=sampleAdditionalHeavyCapture(capture,reach.matrixWorld),expected=pose(c.target.HU_position,c.target.HU_yaw_rad);need(new THREE.Vector3().setFromMatrixPosition(release).distanceTo(new THREE.Vector3().setFromMatrixPosition(expected))<=2e-6,'ADDITIONAL_NATIVE_RELEASE_MISMATCH');
   entries.set(c.case_id,{plan,root,capture,parts,current:null,positionError:0,orientationError:0});
  }}finally{restore(original);vehicle.updateWorldMatrix(true,true);}
 scene.add(owned);owners.add(scene);
 function alive(){need(!disposed,'ADDITIONAL_HEAVY_SCENE_DISPOSED');}
 function clearIncoming(){for(const e of entries.values()){const s=e.plan.sample(0);e.root.position.fromArray(s.cargo.position);e.root.quaternion.fromArray(s.cargo.quaternion);e.root.scale.copy(UNIT);e.root.visible=false;e.current=null;e.positionError=e.orientationError=0;}}
 function apply(rows:readonly AdditionalHeavyDisplayRow[]){alive();need(new Set(rows.map(r=>r.case_id)).size===rows.length&&rows.filter(r=>r.active).length<=1,'SINGLE_ACTIVE_ADDITIONAL_CASE_REQUIRED');
  const previous=original.map(r=>save(r.node)),saved=[...entries.values()].map(e=>({e,local:save(e.root),visible:e.root.visible,current:e.current,p:e.positionError,q:e.orientationError}));
  try{clearIncoming();
   const active=rows.find(r=>r.active);if(active){const e=entries.get(active.case_id);need(e,'UNKNOWN_ADDITIONAL_CASE');need(active.local_s>=0&&active.local_s<e.plan.duration_s,'ACTIVE_ADDITIONAL_TIME_OUTSIDE_EPISODE');need(Object.values(active.wheel_offset_rad).every(Number.isFinite),'FINITE_ADDITIONAL_WHEEL_OFFSET_REQUIRED');body(e.plan.sample(active.local_s),active.wheel_offset_rad);}
   for(const row of rows){const e=entries.get(row.case_id);need(e&&Number.isFinite(row.local_s)&&row.local_s>=0&&row.local_s<=e.plan.duration_s,'INVALID_ADDITIONAL_CASE_TIME');need(row.active||row.local_s===e.plan.duration_s,'INACTIVE_ADDITIONAL_CASE_MUST_BE_TERMINAL');const s=e.plan.sample(row.local_s);if(row.sample)need(JSON.stringify(row.sample)===JSON.stringify(s),'ADDITIONAL_SAMPLE_IDENTITY_MISMATCH');
    const matrix=row.active&&s.cargo.attached?sampleAdditionalHeavyCapture(e.capture,reach.matrixWorld):pose(s.cargo.position,s.cargo.yaw_rad),p=new THREE.Vector3(),q=new THREE.Quaternion(),scale=new THREE.Vector3();matrix.decompose(p,q,scale);e.positionError=p.distanceTo(new THREE.Vector3(...s.cargo.position));e.orientationError=angleError(q,new THREE.Quaternion(...s.cargo.quaternion));need(e.positionError<=2e-6&&e.orientationError<=2e-6&&scale.distanceTo(UNIT)<1e-9,'ADDITIONAL_NATIVE_CARGO_FRAME_MISMATCH');e.root.position.copy(p);e.root.quaternion.copy(q);e.root.scale.copy(UNIT);e.root.visible=s.cargo.visible;e.root.updateWorldMatrix(true,true);e.current=s;
   }currentRows=rows.map(r=>({...r}));return snapshot();
  }catch(error){restore(previous);for(const r of saved){restore([r.local]);r.e.root.visible=r.visible;r.e.current=r.current;r.e.positionError=r.p;r.e.orientationError=r.q;}scene.updateMatrixWorld(true);throw error;}
 }
 function snapshot(){const driverRows=original.filter(r=>{for(let n:THREE.Object3D|null=r.node;n;n=n.parent)if(n===driver)return true;return false;});return {source_kind:'visual_fixture',engine_operation:false,operational_admission:false,disposed,source_stock_HUs:530,workers:24,vehicles:2,vehicle_uuid:vehicle!.uuid,driver_uuid:driver!.uuid,driver_parent_uuid:driver!.parent?.uuid,same_existing_driver:driverRows.every(r=>r.node.parent===r.parent&&r.node.position.equals(r.p)&&r.node.quaternion.equals(r.q)&&r.node.scale.equals(r.s)),active_case_id:currentRows.find(r=>r.active)?.case_id??null,staging_supports_added:0,source_geometry_materials_borrowed:true,incoming:[...entries].map(([case_id,e])=>({case_id,handling_unit_id:e.plan.case.receipt.handling_unit_id,archetype_id:e.plan.case.receipt.archetype_id,visible:e.root.visible,native_parts:e.parts,position:e.root.getWorldPosition(new THREE.Vector3()).toArray(),quaternion:e.root.getWorldQuaternion(new THREE.Quaternion()).toArray(),scale:e.root.getWorldScale(new THREE.Vector3()).toArray(),location:e.current?.cargo.location??null,attached:e.current?.cargo.attached??false,maximum_frame_position_error_m:e.positionError,orientation_error_rad:e.orientationError,at_s:e.current?.at_s??null}))};}
 function reset(){alive();restore(original);clearIncoming();currentRows=[];scene.updateMatrixWorld(true);return snapshot();}
 function dispose(){if(disposed)return;restore(original);owned.removeFromParent();vehicle!.updateWorldMatrix(true,true);owners.delete(scene);disposed=true;}
 return {apply,snapshot,reset,dispose};
}
