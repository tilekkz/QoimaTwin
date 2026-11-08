import * as THREE from 'three';
import {createWorkerInstance,disposeWorkerInstance,type WorkerInstance} from './workerRoles';
import {compileCargoHolders,cargoHolderKey,type CargoHolderDefinition,type CargoHolderDestination} from './warehouseCargoHolders';
import type {BoundCargo,CargoBinding} from './warehouseCargo';
import type {CargoMeshPart,CargoSupportPart} from './warehouseCargoGeometry';
import {applyCarryPose,type WarehouseSupportKit} from './warehouseSupportKit';
import type {WarehouseBundle,XYZ,V3Record} from './warehouseTypes';

type Options={scene:THREE.Scene;bundle:WarehouseBundle;workers:WorkerInstance[];actors:Map<string,THREE.Object3D>;vehicles:Map<string,THREE.Object3D>;pickables:THREE.Object3D[];supports:Map<string,CargoSupportPart[]>;cargoParts:Map<string,CargoMeshPart[]>};
const actorDestination={kind:'actor',actor_id:'P01',anchor_id:'two-hand-small'} as const;
const cartDestination={kind:'cart',cart_id:'C01',anchor_id:'upper-tote'} as const;
const beltDestination={kind:'belt',cell_id:'V3-C-MAIN-000'} as const;
const requireNode=(root:THREE.Object3D,name:string)=>{const n=root.getObjectByName(name);if(!n)throw Error('HOLDER_NODE_MISSING:'+name);return n;};
function parts(root:THREE.Object3D):CargoSupportPart[]{const out:CargoSupportPart[]=[];root.traverseVisible(n=>{if(n instanceof THREE.Mesh)out.push({mesh:n});});return out;}
function worldFrame(root:THREE.Object3D){root.updateWorldMatrix(true,false);const position=new THREE.Vector3(),q=new THREE.Quaternion(),scale=new THREE.Vector3();root.matrixWorld.decompose(position,q,scale);const up=new THREE.Vector3(0,1,0).applyQuaternion(q);if(up.distanceTo(new THREE.Vector3(0,1,0))>1e-8)throw Error('HOLDER_TILT_FORBIDDEN');return {position:position.toArray() as XYZ,yaw_rad:Math.atan2(2*(q.w*q.y+q.x*q.z),1-2*(q.y*q.y+q.z*q.z)),scale:scale.toArray() as XYZ};}
function nearest(point:THREE.Vector3,meshes:CargoSupportPart[]){let gap=Infinity;const triangle=new THREE.Triangle(),closest=new THREE.Vector3();for(const part of meshes){part.mesh.updateWorldMatrix(true,false);const matrix=part.mesh.matrixWorld.clone();if(part.mesh instanceof THREE.InstancedMesh&&part.index!==undefined){const m=new THREE.Matrix4();part.mesh.getMatrixAt(part.index,m);matrix.multiply(m);}const geometry=part.mesh.geometry,p=geometry.getAttribute('position'),ix=geometry.index;for(let i=0;i<(ix?.count??p.count);i+=3){[triangle.a,triangle.b,triangle.c].forEach((v,j)=>v.fromBufferAttribute(p,ix?ix.getX(i+j):i+j).applyMatrix4(matrix));gap=Math.min(gap,triangle.closestPointToPoint(point,closest).distanceTo(point));}}return gap;}

/** Optional native holder assembly. It creates neither a transfer nor an additional worker/HU. */
export function createWarehouseHolderScene(kit:WarehouseSupportKit,o:Options){
 const {scene,bundle,workers,actors,vehicles,pickables,supports,cargoParts}=o;
 const original=workers.find(w=>w.actorId==='P01');if(!original||original.disposed)throw Error('HOLDER_ORIGINAL_WORKER_MISSING');
 const index=workers.indexOf(original),oldRoot=original.root,pickableIndex=pickables.indexOf(oldRoot),oldParent=oldRoot.parent;
 if(actors.get('P01')!==oldRoot||pickableIndex<0||!oldParent||workers.filter(w=>w.actorId==='P01').length!==1)throw Error('HOLDER_ORIGINAL_WORKER_OWNERSHIP');
 const vehicleRest=new Map<string,{node:THREE.Object3D;position:THREE.Vector3;quaternion:THREE.Quaternion}[]>();
 const supportKeys=[actorDestination,cartDestination,beltDestination,...[...vehicles.keys()].map(id=>({kind:'vehicle' as const,vehicle_id:id,anchor_id:'forks'}))].map(cargoHolderKey);
 const supportBefore=new Map(supportKeys.map(key=>[key,supports.get(key)]));
 const cart=kit.cart,beltFrame=new THREE.Object3D(),manual=createWorkerInstance(kit.manual,'P01',original.role);
 function restoreVehicles(){for(const rows of vehicleRest.values())for(const home of rows){home.node.position.copy(home.position);home.node.quaternion.copy(home.quaternion);}}
 function restoreSupports(){for(const [key,value]of supportBefore){if(value)supports.set(key,value);else supports.delete(key);}}
 try{
 manual.root.position.copy(oldRoot.position);manual.root.quaternion.copy(oldRoot.quaternion);manual.root.userData.semanticKind='actor';manual.root.userData.semanticId='P01';
 const carry=applyCarryPose(manual.root,kit.carryPose);carry.restore();
 cart.name='equipment__C01';cart.position.set(16,0,44.38);cart.rotation.y=Math.PI/2;
 const belt=(bundle.layout.data.conveyor as V3Record).cells as V3Record[],cell=belt.find(c=>c.cell_id===beltDestination.cell_id);if(!cell)throw Error('NATIVE_BELT_CELL_MISSING');
 beltFrame.position.fromArray(cell.position as XYZ);const flow=cell.flow as XYZ;beltFrame.rotation.y=Math.atan2(flow[0],flow[2]);
 const cartAnchor=requireNode(cart,'anchor_contents_support'),mounts=new Map<string,THREE.Vector3>(),positions=new Map<string,CargoHolderDefinition['positions']>();
 for(const [id,vehicle]of vehicles){
  const nodes=['joint__carriage','joint__reach','joint__fork_L','joint__fork_R'].map(name=>requireNode(vehicle,name));vehicleRest.set(id,nodes.map(node=>({node,position:node.position.clone(),quaternion:node.quaternion.clone()})));
  const reach=requireNode(vehicle,'joint__reach'),anchor=requireNode(vehicle,'anchor_LONG_cradle');vehicle.updateWorldMatrix(true,true);const mount=reach.worldToLocal(anchor.getWorldPosition(new THREE.Vector3()));
  mounts.set(id,mount);
  // Offsets are relative to the exported moving reach bind, including its Float32 source translation.
  const relative=vehicle.worldToLocal(reach.getWorldPosition(new THREE.Vector3()));positions.set(id,Object.fromEntries(kit.travelProfiles.map(profile=>{const b=profile.cargo_bounds_local_m;return [profile.archetype_id,{position_local:[(b.min[0]+b.max[0])/2,b.min[1]-profile.fork_top_travel_y_m,(b.min[2]+b.max[2])/2-relative.z],yaw_local_rad:0,support_tare_kg:profile.attachment_mass_kg}];})));
 }
 const refs=kit.sourceRefs,definition=(destination:CargoHolderDestination,p:CargoHolderDefinition['positions'],max:number,tare=0,total:number|null=max):CargoHolderDefinition=>({destination,positions:p,max_handling_units:1,max_payload_kg:max,support_tare_kg:tare,max_total_gross_kg:total,source_refs:refs});
 const catalogue=compileCargoHolders(bundle,[definition(actorDestination,{SMALL_CARTON:{position_local:[0,0,0],yaw_local_rad:0}},15),definition(cartDestination,{SMALL_CARTON:{position_local:[0,0,0],yaw_local_rad:0}},12,3,15),definition(beltDestination,{SMALL_CARTON:{position_local:[0,0,0],yaw_local_rad:0},STANDARD_CARTON:{position_local:[0,0,0],yaw_local_rad:0}},15),...[...vehicles.keys()].map(id=>definition({kind:'vehicle',vehicle_id:id,anchor_id:'forks'},positions.get(id)!,1000))]);
 const beltSupport=supports.get('V3_MAIN_000');if(!beltSupport?.length)throw Error('NATIVE_BELT_SUPPORT_MISSING');supports.set(cargoHolderKey(beltDestination),beltSupport);
 let carryActive=false,disposed=false,profiles:Record<string,string|null>={};
 function handPoints(){manual.root.updateWorldMatrix(true,true);return kit.carryPose.contacts.map(c=>requireNode(manual.root,'joint__hand_'+c.side).localToWorld(new THREE.Vector3(...c.local_hand_m)));}
 function frame(destination:CargoHolderDestination){
  if(disposed)throw Error('HOLDERS_DISPOSED');if(destination.kind==='actor'){const points=handPoints(),centre=points[0].clone().add(points[1]).multiplyScalar(.5);centre.y-=kit.carryPose.cargo.dimensions_xyz_m[1]/2;return {...worldFrame(manual.root),position:centre.toArray() as XYZ};}
  return worldFrame(destination.kind==='vehicle'?requireNode(vehicles.get(destination.vehicle_id)!,'joint__reach'):destination.kind==='cart'?cartAnchor:beltFrame);
 }
 function configure(bindings:CargoBinding[]){
  if(disposed)throw Error('HOLDERS_DISPOSED');
  const long=bindings.filter(b=>b.destination.kind==='vehicle'&&bundle.fixture.inputs.initial_stock.find(h=>h.handling_unit_id===b.handling_unit_id)?.archetype_id==='LONG_BUNDLE');if(long.length>1)throw Error('HOLDER_ATTACHMENT_UNAVAILABLE');
  const held=bindings.some(b=>b.destination.kind==='actor'&&b.destination.actor_id==='P01');carry.restore();if(held)applyCarryPose(manual.root,kit.carryPose);carryActive=held;
  kit.cradle.removeFromParent();kit.restraint.removeFromParent();
  for(const [id,vehicle]of vehicles){
   for(const home of vehicleRest.get(id)!){home.node.position.copy(home.position);home.node.quaternion.copy(home.quaternion);}
   const binding=bindings.find(b=>b.destination.kind==='vehicle'&&b.destination.vehicle_id===id),hu=binding&&bundle.fixture.inputs.initial_stock.find(h=>h.handling_unit_id===binding.handling_unit_id),profile=hu&&kit.travelProfiles.find(p=>p.archetype_id===hu.archetype_id);profiles[id]=profile?.archetype_id??null;
   if(profile){requireNode(vehicle,'joint__carriage').position.y=profile.fork_top_travel_y_m;for(const [i,side]of ['L','R'].entries())requireNode(vehicle,'joint__fork_'+side).position.x=profile.fork_centres_x_m[i];if(profile.archetype_id==='LONG_BUNDLE'){for(const attachment of [kit.cradle,kit.restraint]){attachment.position.copy(mounts.get(id)!);requireNode(vehicle,'joint__reach').add(attachment);}}}
   vehicle.updateWorldMatrix(true,true);
  }
  for(const [id,vehicle]of vehicles)supports.set(cargoHolderKey({kind:'vehicle',vehicle_id:id,anchor_id:'forks'}),parts(vehicle).filter(p=>!p.mesh.name.startsWith('role_badge__')));
  supports.set(cargoHolderKey(cartDestination),parts(cart));scene.updateMatrixWorld(true);
 }
 function inspectActor(bound:BoundCargo){const points=handPoints(),nativeCargo=cargoParts.get(bound.handling_unit_id)!;return {contact_kind:'static_two_hand_side_clamp',contacts:points.map((p,i)=>({side:kit.carryPose.contacts[i].side,world_contact_m:p.toArray(),native_cargo_gap_m:nearest(p,nativeCargo),native_glove_gap_m:nearest(p,parts(requireNode(manual.root,'joint__hand_'+kit.carryPose.contacts[i].side)))})),joints:Object.fromEntries(Object.keys(kit.carryPose.jointEulerXYZ).map(name=>[name,requireNode(manual.root,name).quaternion.toArray()])),thumb_positions:Object.fromEntries(Object.keys(kit.carryPose.jointTranslations).map(name=>[name,requireNode(manual.root,name).position.toArray()])),friction_assumption:'Synthetic opposed fingertip/edge clamp; no force, stability, ergonomics or motion certification.',horizontal_support_claimed:false};}
 function dispose(){if(disposed)return;disposed=true;carry.restore();restoreVehicles();restoreSupports();cart.removeFromParent();beltFrame.removeFromParent();kit.cradle.removeFromParent();kit.restraint.removeFromParent();disposeWorkerInstance(manual);kit.dispose();}
 configure([]);
 // A replacement in the existing registry, never transplanting children through workerRoles' private ownership.
 oldRoot.removeFromParent();scene.add(manual.root,cart,beltFrame);workers[index]=manual;actors.set('P01',manual.root);pickables[pickableIndex]=manual.root;disposeWorkerInstance(original);
 return {catalogue,frame,configure,inspectActor,dispose,snapshot:()=>({ready:!disposed,carry_active:carryActive,worker_id:'P01',worker_replacement_count:1,equipment:{cart_ids:['C01'],cart_totes:1,long_cradle_count:1,source_kind:'visual_fixture'},vehicle_profiles:{...profiles},source_refs:refs,source_kind:'visual_fixture',engine_operation:false,operational_admission:false})};
 }catch(error){
  restoreVehicles();restoreSupports();cart.removeFromParent();beltFrame.removeFromParent();kit.cradle.removeFromParent();kit.restraint.removeFromParent();disposeWorkerInstance(manual);
  if(!original.disposed){workers[index]=original;actors.set('P01',oldRoot);pickables[pickableIndex]=oldRoot;if(oldRoot.parent!==oldParent)oldParent.add(oldRoot);}
  throw error;
 }
}
