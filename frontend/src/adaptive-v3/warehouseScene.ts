import * as THREE from 'three';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls.js';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {RoomEnvironment} from 'three/examples/jsm/environments/RoomEnvironment.js';
import assetBindings from './warehouseAssetBindings.json';
import {createWorkerInstance,disposeWorkerInstance,type WorkerInstance} from './workerRoles';
import {bindSeatedDriver,validateSeatedDriverPose} from './seatedDriver';
import type {WarehouseBundle,V3Record,XYZ} from './warehouseTypes';
import type {RoutePose} from './warehouseRoutePose';
import {createWarehouseCargo} from './warehouseCargo';
import {createCargoGeometryInspector,type CargoMeshPart,type CargoSupportPart} from './warehouseCargoGeometry';
import {loadWarehouseSupportKit} from './warehouseSupportKit';
import {createWarehouseHolderScene} from './warehouseHolderScene';
import {cargoHolderKey} from './warehouseCargoHolders';
import type {CargoBinding} from './warehouseCargo';
import {registerWarehouseActionCatalogue,type WarehouseActionCatalogue} from './warehouseActionTimeline';
import type {RoutePolicy} from './warehouseRouting';
import {isWarehousePalletTransferPlan,type WarehousePalletTransferPlan} from './warehousePalletTransferPlan';
import {createWarehousePalletTransferScene} from './warehousePalletTransferScene';
import {createWarehouseCargoActionOverlay} from './warehouseCargoActionOverlay';
import {createWarehouseMagnifier,type WarehouseLensView} from '../ui/warehouseMagnifier';

export type WarehouseView='overview'|'small-west'|'small-east'|'heavy-west'|'long-east'|'packing';
export type WarehouseSelection={kind:'HU'|'module'|'actor';id:string};
/** renderPass: optional page-owned frame drawing (e.g. A/B viewports); default is one full-canvas render. */
type Options={signal:AbortSignal;progress:(done:number,total:number)=>void;select:(selection:WarehouseSelection)=>void;renderPass?:(renderer:THREE.WebGLRenderer,scene:THREE.Scene,camera:THREE.OrthographicCamera)=>void;lensView?:(x:number,y:number)=>WarehouseLensView|null;setLensRender?:(draw:()=>void)=>void;requestLensRender?:()=>void};
type Placement={id:string;position:XYZ;yaw:number};
const presets:Record<WarehouseView,{target:XYZ;span:number}>={overview:{target:[72,1.5,36],span:184},'small-west':{target:[22,0,49],span:22},'small-east':{target:[122,0,49],span:22},'heavy-west':{target:[24,0,25],span:29},'long-east':{target:[92,.7,17.65],span:36},packing:{target:[91,0,5],span:32}};
const cargoModels:Record<string,string>={SMALL_CARTON:'small-carton',STANDARD_CARTON:'standard-carton',HEAVY_BOX:'heavy-box',PALLET_LOAD:'pallet-load',IBC:'ibc',LONG_BUNDLE:'long-bundle',DRUM:'drum',FRAGILE_CRATE:'fragile-crate'};
const storageModels:Record<string,string>={SMALL:'rack-small',STANDARD:'rack-standard',HEAVY:'heavy-bay',LONG:'long-rack',FLEX:'flex-bay'};
const object=(v:unknown)=>v as V3Record;
const sha256=async(b:ArrayBuffer)=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('');
function disposeObjects(objects:THREE.Object3D[]){const geometries=new Set<THREE.BufferGeometry>(),materials=new Set<THREE.Material>(),textures=new Set<THREE.Texture>();for(const root of objects)root.traverse(n=>{if(n instanceof THREE.Mesh){geometries.add(n.geometry);for(const m of Array.isArray(n.material)?n.material:[n.material]){materials.add(m);for(const v of Object.values(m))if(v instanceof THREE.Texture)textures.add(v);}}});for(const t of textures)t.dispose();for(const m of materials)m.dispose();for(const g of geometries)g.dispose();}
/** Shared mesh instances retain the original exported mesh transforms and 1:1 scale. */
export async function createWarehouseScene(host:HTMLElement,bundle:WarehouseBundle,options:Options){
 const base=import.meta.env.BASE_URL,loader=new GLTFLoader(),templates=new Map<string,THREE.Group>(),workers:WorkerInstance[]=[],seated:ReturnType<typeof bindSeatedDriver>[]=[],scene=new THREE.Scene();
 let renderer:THREE.WebGLRenderer|undefined,controls:OrbitControls|undefined,observer:ResizeObserver|undefined,frame=0,disposed=false,environment:THREE.WebGLRenderTarget|undefined;
 let magnifier:ReturnType<typeof createWarehouseMagnifier>|undefined;
 const actors=new Map<string,THREE.Object3D>(),vehicles=new Map<string,THREE.Object3D>(),pickables:THREE.Object3D[]=[],instances:THREE.InstancedMesh[]=[],stockPositions:Record<string,XYZ>={},actorHomes:Record<string,{node_id:string;world_pos:XYZ}>={};
 const vehicleHomes=new Map<string,{position:THREE.Vector3;quaternion:THREE.Quaternion;joints:Map<string,{node:THREE.Object3D;quaternion:THREE.Quaternion}>}>();
 const cargoState=createWarehouseCargo(bundle),cargoParts=new Map<string,CargoMeshPart[]>(),moduleParts=new Map<string,CargoSupportPart[]>(),cargoYaws:Record<string,number>={};
 const cargoGeometry=createCargoGeometryInspector(cargoParts,moduleParts);
 const cargoOverlay=createWarehouseCargoActionOverlay(bundle,cargoState.snapshot);
 let palletTransfer:ReturnType<typeof createWarehousePalletTransferScene>|undefined;
 let holderScene:ReturnType<typeof createWarehouseHolderScene>|undefined;
 const hasAttachedCargo=()=>cargoOverlay.busy()||cargoState.snapshot().some(b=>b.destination.kind!=='storage_slot');
 async function ensureCargoHolders(signal:AbortSignal){if(disposed)throw Error('SCENE_DISPOSED');if(palletTransfer)throw Error('CARGO_ACTION_BUSY');if(holderScene)return holderScene.snapshot();const kit=await loadWarehouseSupportKit(signal);if(disposed||signal.aborted){kit.dispose();throw new DOMException('Aborted','AbortError');}if(palletTransfer){kit.dispose();throw Error('CARGO_ACTION_BUSY');}try{holderScene=createWarehouseHolderScene(kit,{scene,bundle,workers,actors,vehicles,pickables,supports:moduleParts,cargoParts});cargoState.registerHolders(holderScene.catalogue,holderScene.frame);requestRender();return holderScene.snapshot();}catch(error){kit.dispose();throw error;}}
 async function prepareActionCatalogue(readSource:(path:string)=>Promise<Uint8Array>,signal:AbortSignal){await ensureCargoHolders(signal);if(disposed||signal.aborted)throw new DOMException('Aborted','AbortError');return registerWarehouseActionCatalogue(bundle,readSource,holderScene!.catalogue);}
 let routeTrace:THREE.Line|undefined,followedActor:string|null=null;
 let view:WarehouseView|'actor'|'cargo'='overview',activeSpan=184,highlight:THREE.Box3Helper|undefined,highlightId:string|null=null;
 function clearHighlight(){if(highlight){highlight.removeFromParent();highlight.geometry.dispose();(highlight.material as THREE.Material).dispose();highlight=undefined;}highlightId=null;}
 const camera=new THREE.OrthographicCamera(-100,100,70,-70,.05,1000),key=new THREE.DirectionalLight('#fff1d8',3),raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2();
 function render(){frame=0;if(disposed||!renderer)return;if(options.renderPass)options.renderPass(renderer,scene,camera);else renderer.render(scene,camera);if(!options.setLensRender)magnifier?.render();}
 function requestRender(){if(!frame&&!disposed)frame=requestAnimationFrame(render);}
 function flushRender(){if(frame)cancelAnimationFrame(frame);frame=0;render();}
 function clearRouteTrace(){if(routeTrace){routeTrace.removeFromParent();routeTrace.geometry.dispose();(routeTrace.material as THREE.Material).dispose();routeTrace=undefined;}}
 function setRouteTrace(points:XYZ[]|null){clearRouteTrace();if(points?.length&&!disposed){const geometry=new THREE.BufferGeometry().setFromPoints(points.map(p=>new THREE.Vector3(p[0],p[1]+.025,p[2])));routeTrace=new THREE.Line(geometry,new THREE.LineBasicMaterial({color:'#286f76',transparent:true,opacity:.8}));routeTrace.name='visual_route_trace_not_inventory';scene.add(routeTrace);}requestRender();}
 function resetRoutePreview(){if(disposed||palletTransfer)return;followedActor=null;clearRouteTrace();for(const [id,home]of vehicleHomes){const root=vehicles.get(id)!;root.position.copy(home.position);root.quaternion.copy(home.quaternion);for(const joint of home.joints.values())joint.node.quaternion.copy(joint.quaternion);}requestRender();}
 function setFollowActor(id:string|null){followedActor=id&&actors.has(id)?id:null;}
 function applyVehicleRoutePose(id:string,pose:RoutePose){
  if(hasAttachedCargo())throw Error('LOADED_ROUTE_NOT_ADMITTED');
  if(disposed)return;const root=vehicles.get(id),home=vehicleHomes.get(id);if(!root||!home)throw Error('UNKNOWN_VEHICLE');if(!pose.position.every(Number.isFinite)||!Number.isFinite(pose.yaw_rad)||Object.values(pose.wheel_angles_rad).some(v=>!Number.isFinite(v))||Math.max(Math.abs(pose.rear_steer_rad.L),Math.abs(pose.rear_steer_rad.R))>75*Math.PI/180+1e-8)throw Error('INVALID_VEHICLE_POSE');
  const following=followedActor?actors.get(followedActor):undefined,before=following?.getWorldPosition(new THREE.Vector3());root.position.fromArray(pose.position);root.rotation.set(0,pose.yaw_rad,0);const q=new THREE.Quaternion();for(const side of ['L','R'] as const){const steer=home.joints.get('joint__rear_steer_'+side)!;steer.node.quaternion.copy(steer.quaternion).multiply(q.setFromAxisAngle(new THREE.Vector3(0,1,0),pose.rear_steer_rad[side]));for(const axle of ['front','rear'] as const){const wheel=home.joints.get('joint__wheel_'+axle+'_'+side)!;wheel.node.quaternion.copy(wheel.quaternion).multiply(q.setFromAxisAngle(new THREE.Vector3(1,0,0),pose.wheel_angles_rad[`${axle}_${side}`]));}}
  if(following&&before){const delta=following.getWorldPosition(new THREE.Vector3()).sub(before);camera.position.add(delta);controls!.target.add(delta);key.position.add(delta);key.target.position.add(delta);controls!.update();}flushRender();
 }
 function inspectVehicleBounds(id:string){const root=vehicles.get(id);if(!root||disposed)throw Error('UNKNOWN_VEHICLE');root.updateWorldMatrix(true,true);const inverse=root.matrixWorld.clone().invert(),box=new THREE.Box3(),point=new THREE.Vector3();let vertices=0;root.traverse(n=>{if(n instanceof THREE.Mesh&&n.visible){const positions=n.geometry.getAttribute('position');for(let i=0;i<positions.count;i++){point.fromBufferAttribute(positions,i).applyMatrix4(n.matrixWorld).applyMatrix4(inverse);box.expandByPoint(point);vertices++;}}});return{vehicle_id:id,min:box.min.toArray(),max:box.max.toArray(),vertices,scale:root.scale.toArray()};}
 function resize(){if(!renderer||disposed)return;const w=Math.max(1,host.clientWidth),h=Math.max(1,host.clientHeight),aspect=w/h;renderer.setSize(w,h,false);camera.left=-activeSpan/2;camera.right=activeSpan/2;camera.top=activeSpan/aspect/2;camera.bottom=-activeSpan/aspect/2;camera.updateProjectionMatrix();requestRender();}
 function frameTarget(target:THREE.Vector3,span:number,yaw=0,side=1,dir?:THREE.Vector3){activeSpan=span;const direction=dir?dir.clone().normalize():new THREE.Vector3(.9*side,1.15,1).applyAxisAngle(new THREE.Vector3(0,1,0),yaw).normalize();camera.position.copy(target).addScaledVector(direction,180);camera.lookAt(target);controls!.target.copy(target);controls!.update();key.position.copy(target).add(new THREE.Vector3(-18,28,12));key.target.position.copy(target);key.shadow.camera.left=-span/1.5;key.shadow.camera.right=span/1.5;key.shadow.camera.top=span/1.5;key.shadow.camera.bottom=-span/1.5;key.shadow.camera.updateProjectionMatrix();renderer!.shadowMap.enabled=span<60;resize();}
 function setView(next:WarehouseView){if(disposed||!presets[next])return;followedActor=null;clearHighlight();view=next;const p=presets[next];frameTarget(new THREE.Vector3(...p.target),p.span);}
 /** Page-driven framing (e.g. animated fly-to); keeps the default viewing direction. */
 function frameAt(target:XYZ,span:number,dir?:XYZ){if(disposed||!target.every(Number.isFinite)||!(span>0))return;followedActor=null;view='cargo';camera.zoom=1;const d=dir&&dir.every(Number.isFinite)&&dir[1]>0?new THREE.Vector3(...dir):undefined;frameTarget(new THREE.Vector3(...target),span,0,1,d);}
 const frameState=()=>({target:(controls?.target.toArray()??[72,1.5,36]) as XYZ,span:activeSpan/camera.zoom,dir:(controls?camera.position.clone().sub(controls.target).normalize().toArray():[.9,1.15,1]) as XYZ});
 function focusActor(id:string){const actor=actors.get(id);if(!actor||disposed)return false;scene.updateMatrixWorld(true);clearHighlight();view='actor';const position=actor.getWorldPosition(new THREE.Vector3());position.y=.9;frameTarget(position,7);return true;}
 function selectionFromHit(hit:THREE.Intersection):WarehouseSelection|null{
  let node:THREE.Object3D|null=hit.object;while(node&&!node.userData.semanticKind)node=node.parent;if(!node)return null;
  const id=hit.instanceId===undefined?node.userData.semanticId:node.userData.semanticIds?.[hit.instanceId],kind=node.userData.semanticKind;
  return typeof id==='string'&&['HU','module','actor'].includes(kind)?{kind,id}:null;
 }
 function cargoCameraSide(id:string,position:XYZ,dimensions:XYZ,yaw:number){
  scene.updateMatrixWorld(true);const rotation=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),yaw),points=[[0,.5,.5],[-.25,.5,.5],[.25,.5,.5],[0,1,0]].map(p=>new THREE.Vector3(p[0]*dimensions[0],p[1]*dimensions[1],p[2]*dimensions[2]).applyQuaternion(rotation).add(new THREE.Vector3(...position)));
  let best=1,score=-1;const far=raycaster.far;
  try{raycaster.far=181;for(const side of [1,-1]){const direction=new THREE.Vector3(.9*side,1.15,1).applyQuaternion(rotation).normalize();let visible=0;for(const point of points){raycaster.set(point.clone().addScaledVector(direction,180),direction.clone().negate());const hit=raycaster.intersectObjects(pickables,true)[0],selected=hit&&selectionFromHit(hit);if(selected?.kind==='HU'&&selected.id===id)visible++;}if(visible>score){score=visible;best=side;}}}finally{raycaster.far=far;}
  return best;
 }
 function focusCargo(id:string){const position=stockPositions[id];if(!position||disposed)return false;clearHighlight();const hu=bundle.fixture.inputs.initial_stock.find(h=>h.handling_unit_id===id)!,c=Math.abs(Math.cos(cargoYaws[id])),s=Math.abs(Math.sin(cargoYaws[id])),d=hu.dimensions_xyz_m;highlight=new THREE.Box3Helper(new THREE.Box3().setFromCenterAndSize(new THREE.Vector3(position[0],position[1]+d[1]/2,position[2]),new THREE.Vector3(c*d[0]+s*d[2]+.01,d[1]+.01,s*d[0]+c*d[2]+.01)),0xb66523);(highlight.material as THREE.LineBasicMaterial).depthTest=false;highlight.renderOrder=10;highlightId=id;scene.add(highlight);view='cargo';frameTarget(new THREE.Vector3(position[0],position[1]+.4,position[2]),4.5,cargoYaws[id],cargoCameraSide(id,position,d,cargoYaws[id]));return true;}
 function addInstances(modelId:string,placements:Placement[],kind:'HU'|'module'|null,supportOnly=false){
  if(!placements.length)return;const source=templates.get(modelId)!;source.updateMatrixWorld(true);const origin=new THREE.Vector3(Math.round((Math.min(...placements.map(p=>p.position[0]))+Math.max(...placements.map(p=>p.position[0])))/2),0,Math.round((Math.min(...placements.map(p=>p.position[2]))+Math.max(...placements.map(p=>p.position[2])))/2)),relative=new THREE.Matrix4().makeTranslation(-origin.x,0,-origin.z);const transforms=placements.map(p=>new THREE.Matrix4().compose(new THREE.Vector3(...p.position),new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),p.yaw),new THREE.Vector3(1,1,1)));
  source.traverse(n=>{if(!(n instanceof THREE.Mesh)||!n.visible)return;const mesh=new THREE.InstancedMesh(n.geometry,n.material,placements.length);mesh.name='instances__'+modelId+'__'+n.name;mesh.position.copy(origin);mesh.castShadow=true;mesh.receiveShadow=true;mesh.userData.semanticIds=placements.map(p=>p.id);mesh.userData.semanticKind=kind;for(let i=0;i<placements.length;i++)mesh.setMatrixAt(i,new THREE.Matrix4().multiplyMatrices(transforms[i],n.matrixWorld).premultiply(relative));mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingBox();mesh.computeBoundingSphere();scene.add(mesh);instances.push(mesh);if(kind)pickables.push(mesh);if(kind||supportOnly){const table=kind==='HU'?cargoParts:moduleParts;for(let i=0;i<placements.length;i++){const parts=table.get(placements[i].id)??[];parts.push({mesh,index:i,sourceMatrix:n.matrixWorld.clone()});table.set(placements[i].id,parts);}}});
 }
 function updateCargoInstances(){
  const changed=new Set<THREE.InstancedMesh>(),rows=cargoState.snapshot(),ranges=new Map<string,THREE.Box3>();
  for(const bound of rows){const model=cargoModels[bound.cargo.archetype_id],box=ranges.get(model)??new THREE.Box3();box.expandByPoint(new THREE.Vector3(...bound.position));ranges.set(model,box);}
  for(const bound of rows){
   stockPositions[bound.handling_unit_id]=[...bound.position];cargoYaws[bound.handling_unit_id]=bound.yaw_rad;
   const matrix=new THREE.Matrix4().compose(new THREE.Vector3(...bound.position),new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),bound.yaw_rad),new THREE.Vector3(1,1,1));
   for(const part of cargoParts.get(bound.handling_unit_id)??[]){if(!changed.has(part.mesh)){const range=ranges.get(cargoModels[bound.cargo.archetype_id])!;part.mesh.position.set(Math.round((range.min.x+range.max.x)/2),0,Math.round((range.min.z+range.max.z)/2));}part.mesh.updateWorldMatrix(true,false);part.mesh.setMatrixAt(part.index,new THREE.Matrix4().multiplyMatrices(matrix,part.sourceMatrix).premultiply(part.mesh.matrixWorld.clone().invert()));changed.add(part.mesh);}
  }
  for(const mesh of changed){mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingBox();mesh.computeBoundingSphere();}
  if(highlight&&highlightId){const bound=cargoState.snapshot().find(b=>b.handling_unit_id===highlightId)!,d=bound.cargo.dimensions_xyz_m,c=Math.abs(Math.cos(bound.yaw_rad)),s=Math.abs(Math.sin(bound.yaw_rad));highlight.box.setFromCenterAndSize(new THREE.Vector3(bound.position[0],bound.position[1]+d[1]/2,bound.position[2]),new THREE.Vector3(c*d[0]+s*d[2]+.01,d[1]+.01,s*d[0]+c*d[2]+.01));}
  flushRender();
 }
 function applyCargoBindings(changes:unknown){
  if(disposed)throw Error('SCENE_DISPOSED');if(palletTransfer)throw Error('CARGO_ACTION_BUSY');const admission=cargoState.evaluate(changes);if(!admission.ok)return admission;
  const previous=cargoState.snapshot().map(b=>({handling_unit_id:b.handling_unit_id,destination:b.destination})),next=new Map(previous.map(b=>[b.handling_unit_id,b]));for(const b of changes as CargoBinding[])next.set(b.handling_unit_id,b);
  try{holderScene?.configure([...next.values()]);const result=cargoState.apply(changes);if(!result.ok){holderScene?.configure(previous);return result;}updateCargoInstances();
   for(const bound of cargoState.snapshot().filter(b=>b.destination.kind!=='storage_slot')){const proof=inspectCargo(bound.handling_unit_id);if('contacts'in proof){if(proof.contacts.some(c=>c.native_cargo_gap_m>2e-6||c.native_glove_gap_m>2e-6))throw Error('HOLDER_PHYSICAL_SUPPORT_UNAVAILABLE');}else if(!('native_contact_area_sum_m2'in proof)||proof.native_contact_area_sum_m2<=1e-8||!proof.geometric_centre_inside_support_hull||proof.maximum_contact_gap_m>2e-6)throw Error('HOLDER_PHYSICAL_SUPPORT_UNAVAILABLE');}
   return result;
  }catch(error){holderScene?.configure(previous);cargoState.apply(previous);updateCargoInstances();return {...admission,ok:false,reason:error instanceof Error&&error.message==='HOLDER_ATTACHMENT_UNAVAILABLE'?'HOLDER_ATTACHMENT_UNAVAILABLE' as const:'HOLDER_PHYSICAL_SUPPORT_UNAVAILABLE' as const};}
 }
 function resetCargoBindings(){if(disposed)throw Error('SCENE_DISPOSED');if(palletTransfer)throw Error('CARGO_ACTION_BUSY');cargoState.reset();holderScene?.configure([]);updateCargoInstances();}
 function inspectCargo(id:string){
  if(disposed)throw Error('SCENE_DISPOSED');const bound=cargoOverlay.values().find(b=>b.handling_unit_id===id);if(!bound)throw Error('UNKNOWN_CARGO_INSTANCE');
  if(palletTransfer&&cargoOverlay.frame()?.bound.handling_unit_id===id&&bound.destination.kind==='vehicle')return cargoGeometry.inspectSupported(bound,'pallet-transfer:FL02:forks');
  if(bound.destination.kind==='actor'){if(!holderScene)throw Error('PHYSICAL_HOLDER_NOT_REGISTERED');return {...cargoGeometry.inspectGeometry(bound),...holderScene.inspectActor(bound)};}
  if(bound.destination.kind!=='storage_slot')return cargoGeometry.inspectSupported(bound,cargoHolderKey(bound.destination));
  const slotId=bound.destination.slot_id,slot=bundle.layout.slots.find(s=>s.slot_id===slotId)!;
  return cargoGeometry.inspectSupported(bound,bundle.layout.modules[slot.module_index].module_id);
 }
 function publishCargoAction(id:string){
  const bound=cargoOverlay.values().find(row=>row.handling_unit_id===id)!;stockPositions[id]=[...bound.position];cargoYaws[id]=bound.yaw_rad;
  if(highlight&&highlightId===id){const d=bound.cargo.dimensions_xyz_m,c=Math.abs(Math.cos(bound.yaw_rad)),s=Math.abs(Math.sin(bound.yaw_rad));highlight.box.setFromCenterAndSize(new THREE.Vector3(bound.position[0],bound.position[1]+d[1]/2,bound.position[2]),new THREE.Vector3(c*d[0]+s*d[2]+.01,d[1]+.01,s*d[0]+c*d[2]+.01));}
 }
 /** Display-only capability: all native instances and the stock ledger remain the same objects. */
 function beginPalletTransfer(catalogue:WarehouseActionCatalogue,policy:RoutePolicy,plan:WarehousePalletTransferPlan){
  if(disposed)throw Error('SCENE_DISPOSED');if(hasAttachedCargo())throw Error('CARGO_ACTION_BUSY');
  if(!isWarehousePalletTransferPlan(plan,bundle,catalogue,policy))throw Error('INVALID_PALLET_TRANSFER_PLAN');
  for(const [id,home]of vehicleHomes){const root=vehicles.get(id)!;if(!root.position.equals(home.position)||1-Math.abs(root.quaternion.dot(home.quaternion))>1e-12||root.scale.toArray().some(v=>v!==1)||[...home.joints.values()].some(j=>!j.node.quaternion.equals(j.quaternion)))throw Error('ACTION_REQUIRES_PARKED_VEHICLES');}
  const actor=workers.find(w=>w.actorId==='F02')!,vehicle=vehicles.get('FL02')!,driver=seated.find(s=>s.actor===actor)!;
  const bound=cargoState.snapshot().find(h=>h.handling_unit_id===plan.request.handling_unit_id);if(!bound)throw Error('UNKNOWN_CARGO_INSTANCE');
  const native=createWarehousePalletTransferScene({bundle,catalogue,policy,plan,vehicle,actor,seated:driver,bound,parts:cargoParts.get(bound.handling_unit_id)!});
  try{cargoOverlay.bind(plan,native);}catch(error){native.dispose();throw error;}
  palletTransfer=native;moduleParts.set('pallet-transfer:FL02:forks',[...native.forkSupportParts]);let closed=false;
  const live=()=>{if(closed||disposed||palletTransfer!==native)throw Error('CARGO_ACTION_DISPOSED');};
  function apply(seconds:number){live();const following=followedActor==='F02',before=following?actor.root.getWorldPosition(new THREE.Vector3()):null;native.apply(seconds);const value=cargoOverlay.sync();publishCargoAction(bound!.handling_unit_id);if(before){const delta=actor.root.getWorldPosition(new THREE.Vector3()).sub(before);camera.position.add(delta);controls!.target.add(delta);key.position.add(delta);key.target.position.add(delta);controls!.update();}flushRender();return value;}
  function reset(){live();native.reset();cargoOverlay.sync();publishCargoAction(bound!.handling_unit_id);requestRender();}
  function close(){if(closed)return;closed=true;native.dispose();cargoOverlay.clear();palletTransfer=undefined;moduleParts.delete('pallet-transfer:FL02:forks');publishCargoAction(bound!.handling_unit_id);requestRender();}
  return Object.freeze({apply,reset,dispose:close,snapshot:()=>native.snapshot(),duration_s:plan.duration_s});
 }
 /** Read-only QA evidence from the actual scene objects and Float32 instance buffers. */
 function nativeIntegrity(){
  const local=(node:THREE.Object3D)=>({name:node.name,uuid:node.uuid,parent_uuid:node.parent?.uuid??null,position:node.position.toArray(),quaternion:node.quaternion.toArray(),scale:node.scale.toArray()});
  return {actors:workers.map(actor=>({actor_id:actor.actorId,...local(actor.root)})),vehicles:[...vehicles].map(([vehicle_id,root])=>{const nodes:ReturnType<typeof local>[]=[];root.traverse(node=>nodes.push(local(node)));return {vehicle_id,uuid:root.uuid,parent_uuid:root.parent?.uuid??null,nodes};}),cargo:[...cargoParts].map(([handling_unit_id,parts])=>({handling_unit_id,parts:parts.map(part=>{const matrix=new THREE.Matrix4();part.mesh.getMatrixAt(part.index,matrix);return {uuid:part.mesh.uuid,index:part.index,mesh_position:part.mesh.position.toArray(),mesh_quaternion:part.mesh.quaternion.toArray(),mesh_scale:part.mesh.scale.toArray(),instance_matrix:matrix.toArray()};})}))};
 }
 function dispose(){if(disposed)return;magnifier?.dispose();palletTransfer?.dispose();if(palletTransfer){cargoOverlay.clear();palletTransfer=undefined;}disposed=true;holderScene?.dispose();host.removeEventListener('pointerdown',down);host.removeEventListener('pointerup',up);cargoGeometry.dispose();cargoParts.clear();moduleParts.clear();if(frame)cancelAnimationFrame(frame);observer?.disconnect();controls?.dispose();clearHighlight();clearRouteTrace();for(const binding of seated)binding.release();for(const actor of workers)disposeWorkerInstance(actor);disposeObjects([scene,...templates.values()]);for(const mesh of instances)mesh.dispose();environment?.dispose();renderer?.dispose();renderer?.forceContextLoss();renderer?.domElement.remove();scene.clear();templates.clear();actors.clear();vehicles.clear();vehicleHomes.clear();pickables.length=0;}
 let downAt:[number,number]=[0,0];function down(e:PointerEvent){downAt=[e.clientX,e.clientY];}
 function up(e:PointerEvent){if(disposed||Math.hypot(e.clientX-downAt[0],e.clientY-downAt[1])>5)return;const rect=host.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);const hit=raycaster.intersectObjects(pickables,true)[0];if(!hit)return;const selected=selectionFromHit(hit);if(selected)options.select(selected);}
 try{
  const entries=Object.entries(assetBindings).filter(([id])=>id!=='seated-driver-pose'),total=entries.length+1;let completed=0;
  // Short bounded groups avoid opening many GPU/decoder jobs at once; no external assets.
  for(let i=0;i<entries.length;i+=4){const group=await Promise.allSettled(entries.slice(i,i+4).map(async([id,binding])=>{const response=await fetch(base+'models/v3/'+id+'.glb',{signal:options.signal});if(!response.ok)throw Error('Не загружена модель '+id+'.');const bytes=await response.arrayBuffer();if(await sha256(bytes)!==binding.sha256)throw Error('Модель '+id+' изменилась после проверки.');const gltf=await loader.parseAsync(bytes,base+'models/v3/');if(options.signal.aborted){disposeObjects([gltf.scene]);throw new DOMException('Aborted','AbortError');}let tagged=false;gltf.scene.traverse(n=>{if(n.userData.asset_id===id&&n.userData.namespace==='v3')tagged=true;});if(!tagged){disposeObjects([gltf.scene]);throw Error('Нет метаданных модели '+id+'.');}templates.set(id,gltf.scene);options.progress(++completed,total);}));const failed=group.find(r=>r.status==='rejected');if(failed?.status==='rejected')throw failed.reason;}
  const poseResponse=await fetch(base+assetBindings['seated-driver-pose'].path,{signal:options.signal});if(!poseResponse.ok)throw Error('Не загружена поза водителя.');const poseBytes=await poseResponse.arrayBuffer();if(await sha256(poseBytes)!==assetBindings['seated-driver-pose'].sha256)throw Error('Поза водителя изменилась после проверки.');const pose=validateSeatedDriverPose(JSON.parse(new TextDecoder().decode(poseBytes)));options.progress(++completed,total);
  if(options.signal.aborted)throw new DOMException('Aborted','AbortError');
  renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.domElement.setAttribute('aria-label','Склад V3. Вращение и приближение; виды и работники доступны кнопками.');host.append(renderer.domElement);
  magnifier=createWarehouseMagnifier(host,renderer,options.requestLensRender??requestRender,options.lensView??((x,y)=>{
   const rect=renderer!.domElement.getBoundingClientRect();camera.updateMatrixWorld();
   raycaster.setFromCamera(new THREE.Vector2(x/rect.width*2-1,1-y/rect.height*2),camera);
   const hit=raycaster.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0,1,0),0),new THREE.Vector3());
   const zone=hit&&(bundle.layout.data.zones as V3Record[]).find(z=>{const b=z.floor_bounds_xz_m as {min:[number,number];max:[number,number]};return b&&hit.x>=b.min[0]&&hit.x<=b.max[0]&&hit.z>=b.min[1]&&hit.z<=b.max[1];});
   const zoneName=String(zone?.zone_id??'Склад').replace(/_W$/,' запад').replace(/_E$/,' восток').replace('PACKING_LIGHT_LINE','Упаковка и линия');
   return {camera,viewport:{x:0,y:0,w:rect.width,h:rect.height},caption:zoneName,draw:c=>renderer!.render(scene,c)};
  }));
  options.setLensRender?.(magnifier.render);
  scene.background=new THREE.Color('#dce1db');scene.add(new THREE.HemisphereLight('#fff8e8','#82948b',1.8));key.castShadow=true;key.shadow.mapSize.set(2048,2048);key.shadow.camera.near=.1;key.shadow.camera.far=100;key.shadow.normalBias=.012;key.shadow.bias=-.0001;scene.add(key,key.target);const fill=new THREE.DirectionalLight('#d5e8ff',1);fill.position.set(130,40,-30);scene.add(fill);
  const room=new RoomEnvironment(),pmrem=new THREE.PMREMGenerator(renderer);environment=pmrem.fromScene(room,.04);scene.environment=environment.texture;scene.environmentIntensity=.2;room.dispose();pmrem.dispose();
  const shell=templates.get('environment-markings-fixture')!;scene.add(shell);shell.traverse(n=>{if(n instanceof THREE.Mesh){n.receiveShadow=true;n.castShadow=false;}});
  for(const [family,model]of Object.entries(storageModels))addInstances(model,bundle.layout.modules.filter(m=>m.family===family).map(m=>({id:m.module_id,position:m.world_pos,yaw:m.yaw_rad})),'module');
  const placements:Record<string,Placement[]>={};
  for(const bound of cargoState.snapshot()){stockPositions[bound.handling_unit_id]=[...bound.position];cargoYaws[bound.handling_unit_id]=bound.yaw_rad;(placements[cargoModels[bound.cargo.archetype_id]]??=[]).push({id:bound.handling_unit_id,position:bound.position,yaw:bound.yaw_rad});}
  for(const [id,items]of Object.entries(placements))addInstances(id,items,'HU');
  const conveyor=object(bundle.layout.data.conveyor),stationRows=conveyor.packing_stations as V3Record[],conveyorRows=conveyor.physical_modules as V3Record[];
  addInstances('packing-station',stationRows.map(p=>({id:p.pack_id as string,position:p.table_origin as XYZ,yaw:0})),null);
  for(const family of ['straight','diverter','turn'])addInstances('conveyor-'+family,conveyorRows.filter(p=>p.family===family).map(p=>({id:p.module_id as string,position:p.origin as XYZ,yaw:(p.rotation_y_rad as number|undefined)??0})),null,true);
  const nodeById=new Map(bundle.layout.walk.nodes.map(n=>[n.node_id,n]));const pickerModules=['SMALL_W','SMALL_E'].flatMap(zone=>bundle.layout.modules.filter(m=>m.module_id.includes(':'+zone+':')).filter((_,i)=>i%4===0).slice(0,6));
  const vehiclesStart:Record<string,string>={FL01:'v3:service:IN_W_BULK',FL02:'v3:service:OUT_E_B2B'};
  for(const v of bundle.registry.vehicles){const n=bundle.layout.vehicle.nodes.find(n=>n.node_id===vehiclesStart[v.vehicle_id])!,root=templates.get('forklift')!.clone(true);root.name='vehicle__'+v.vehicle_id;root.position.fromArray(n.world_pos);root.rotation.y=n.yaw_rad!;scene.add(root);vehicles.set(v.vehicle_id,root);const joints=new Map<string,{node:THREE.Object3D;quaternion:THREE.Quaternion}>();for(const name of ['joint__rear_steer_L','joint__rear_steer_R','joint__wheel_front_L','joint__wheel_front_R','joint__wheel_rear_L','joint__wheel_rear_R']){const node=root.getObjectByName(name);if(!node)throw Error('Нет узла машины '+name);joints.set(name,{node,quaternion:node.quaternion.clone()});}vehicleHomes.set(v.vehicle_id,{position:root.position.clone(),quaternion:root.quaternion.clone(),joints});}
  const serviceHome:Record<string,string>={R01:'v3:service:IN_N_STANDARD',R02:'v3:service:IN_E_PARCEL',S01:'v3:service:OUT_W_RETAIL',S02:'v3:service:OUT_S_EXPRESS'};let pickerIndex=0;
  for(const w of bundle.registry.workers){const actor=createWorkerInstance(templates.get('worker-base')!,w.actor_id,w.baseline_role);workers.push(actor);actor.root.userData.semanticKind='actor';actor.root.userData.semanticId=w.actor_id;actors.set(w.actor_id,actor.root);pickables.push(actor.root);
   if(w.assigned_vehicle_id){const vehicleId=w.assigned_vehicle_id,vehicle=vehicles.get(vehicleId)!;seated.push(bindSeatedDriver(vehicle,actor,pose));const n=bundle.layout.vehicle.nodes.find(n=>n.node_id===vehiclesStart[vehicleId])!;actorHomes[w.actor_id]={node_id:n.node_id,world_pos:[...n.world_pos]};continue;}
   let nodeId=serviceHome[w.actor_id],yaw=0;if(w.baseline_role==='packer'){nodeId='v3:service:PK'+w.actor_id.slice(1);yaw=Math.PI;}if(w.baseline_role==='picker'){const m=pickerModules[pickerIndex++],slot=bundle.layout.slots.find(s=>bundle.layout.modules[s.module_index]===m)!;nodeId=bundle.layout.walk.nodes[slot.worker_node_index].node_id;yaw=m.yaw_rad+Math.PI;}
   const node=nodeById.get(nodeId)!;actor.root.position.fromArray(node.world_pos);actor.root.rotation.y=yaw;scene.add(actor.root);actorHomes[w.actor_id]={node_id:node.node_id,world_pos:[...node.world_pos]};
  }
  controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=false;controls.enablePan=true;controls.minZoom=.4;controls.maxZoom=18;controls.maxPolarAngle=Math.PI*.49;controls.addEventListener('change',requestRender);observer=new ResizeObserver(resize);observer.observe(host);host.addEventListener('pointerdown',down);host.addEventListener('pointerup',up);setView('overview');scene.updateMatrixWorld(true);render();
  return {requestRender,frameAt,frameState,nativeIntegrity,beginPalletTransfer,prepareActionCatalogue,ensureCargoHolders,hasAttachedCargo,setView,focusActor,focusCargo,applyCargoBindings,resetCargoBindings,inspectCargo,getCargoBindings:cargoOverlay.values,setRouteTrace,resetRoutePreview,setFollowActor,applyVehicleRoutePose,inspectVehicleBounds,dispose,snapshot:()=>({magnifier:magnifier?.snapshot()??null,holders:holderScene?.snapshot()??null,pallet_transfer:palletTransfer?.snapshot()??null,disposed,view,highlight_HU:highlightId,followed_actor:followedActor,route_trace_points:routeTrace?.geometry.getAttribute('position').count??0,workers:workers.length,worker_ids:workers.map(w=>w.actorId),vehicle_ids:[...vehicles.keys()],vehicle_poses:[...vehicles].map(([id,root])=>({vehicle_id:id,position:root.position.toArray(),yaw_rad:root.rotation.y,scale:root.scale.toArray(),joints:[...vehicleHomes.get(id)!.joints].map(([name,joint])=>({name,quaternion:joint.node.quaternion.toArray()}))})),actor_homes:actorHomes,driver_contacts:seated.map(s=>s.snapshot()),modules:bundle.layout.modules.length,stock_HUs:bundle.fixture.inputs.initial_stock.length,cargo_binding_count:cargoParts.size,stock_positions:stockPositions,source_kind:'visual_fixture',engine_operation:false,actions_scheduled:0,completed_jobs:0,assets_loaded:templates.size,renderer:renderer?{calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,geometries:renderer.info.memory.geometries,textures:renderer.info.memory.textures}:null})};
 }catch(error){dispose();throw error;}
}
