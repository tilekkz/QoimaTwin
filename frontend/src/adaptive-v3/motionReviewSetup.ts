import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {adaptWarehouseV3,type WarehouseTexts} from './warehouseAdapter';
import {createWarehouseCargo} from './warehouseCargo';
import {compileCargoHolders} from './warehouseCargoHolders';
import {registerWarehouseActionCatalogue} from './warehouseActionTimeline';
import {validateRoutePolicy} from './warehouseRouting';
import {createWarehouseLoadedWalkCalibration} from './warehouseLoadedWalkCalibration';
import {createWorkerInstance,disposeWorkerInstance,type WorkerInstance} from './workerRoles';
import type {CargoMeshPart} from './warehouseCargoGeometry';

export type MotionCarryPose='source'|'low_close'|'vertical_90'|'close_hold'|'original_hold';
export type MotionWorkerModelPath='frontend/public/models/v3/worker-base.glb'|'frontend/public/models/v3/worker-base-carry-natural.glb'|'frontend/public/models/v3/worker-base-vertical-carry.glb'|'frontend/public/models/v3/worker-base-close-hold-jointfit.glb';
export type MotionReviewManifest = {
 schema_id:'qoima.motion-review-sources.v1';source_kind:'visual_fixture';engine_operation:false;
 runtime_scene_joined:false;source_pickup_executed:false;motion_style:'grounded_carry';duration_s:number;
 carry_pose?:MotionCarryPose;breathing?:boolean;worker_model_path?:MotionWorkerModelPath;
 source_report_sha256:string;source_count:number;
 sources:Record<string,{repo_path:string;sha256:string;bytes:number;url:string}>;
};
export type MotionSourceReader = (path:string)=>Promise<Uint8Array>;
type Disposable = THREE.BufferGeometry|THREE.Material|THREE.Texture;

function workerModelPath(pose:MotionCarryPose='source',requested?:MotionWorkerModelPath):MotionWorkerModelPath{
 if(pose!=='source'&&pose!=='low_close'&&pose!=='vertical_90'&&pose!=='close_hold'&&pose!=='original_hold')throw Error('Invalid motion carry pose');
 const selected=requested??((pose==='source'||pose==='original_hold')?'frontend/public/models/v3/worker-base.glb':pose==='close_hold'?'frontend/public/models/v3/worker-base-close-hold-jointfit.glb':pose==='vertical_90'?'frontend/public/models/v3/worker-base-vertical-carry.glb':'frontend/public/models/v3/worker-base-carry-natural.glb');
 const valid=(pose==='source'||pose==='original_hold')?selected==='frontend/public/models/v3/worker-base.glb':pose==='low_close'?selected==='frontend/public/models/v3/worker-base-carry-natural.glb':pose==='close_hold'?selected==='frontend/public/models/v3/worker-base-close-hold-jointfit.glb':selected==='frontend/public/models/v3/worker-base-vertical-carry.glb';
 if(!valid)throw Error('Worker representation does not match the carry pose');
 return selected;
}

/** Resources belong exclusively to this review page. Shared native geometry is released once, at teardown. */
function releaseResources(roots:Iterable<THREE.Object3D>,controller:{dispose:()=>void}|undefined,actor:WorkerInstance|undefined){
 const resources=new Set<Disposable>(),instances=new Set<THREE.InstancedMesh>();
 for(const root of roots)root.traverse(node=>{
  if(node instanceof THREE.InstancedMesh)instances.add(node);
  if(!(node instanceof THREE.Mesh||node instanceof THREE.Line||node instanceof THREE.Points))return;
  resources.add(node.geometry);
  for(const material of Array.isArray(node.material)?node.material:[node.material]){
   resources.add(material);
   for(const value of Object.values(material))if(value instanceof THREE.Texture)resources.add(value);
  }
 });
 const released=new WeakSet<Disposable>();
 for(const resource of resources)resource.addEventListener('dispose',()=>released.add(resource));
 // The binding restores source slots and removes its private active instances first.
 try{controller?.dispose();}finally{
  try{if(actor&&!actor.disposed)disposeWorkerInstance(actor);}finally{
   for(const instance of instances)if(instance.parent)instance.dispose();
   for(const resource of resources)if(!released.has(resource))resource.dispose();
   for(const root of roots)root.clear();
  }
 }
}

export async function loadMotionReviewSources(manifestURL:URL,signal:AbortSignal){
 const response=await fetch(manifestURL,{signal,cache:'no-cache'});
 if(!response.ok)throw Error('Motion source manifest unavailable');
 const manifest=await response.json() as MotionReviewManifest;
 if(manifest.schema_id!=='qoima.motion-review-sources.v1'||manifest.source_kind!=='visual_fixture'||manifest.engine_operation!==false||manifest.runtime_scene_joined!==false||manifest.source_pickup_executed!==false||manifest.motion_style!=='grounded_carry'||Math.abs(manifest.duration_s-28.47)>1e-9||!Number.isFinite(manifest.duration_s)||!Number.isSafeInteger(manifest.source_count)||manifest.source_count<85||Object.keys(manifest.sources??{}).length!==manifest.source_count||!/^[a-f0-9]{64}$/.test(manifest.source_report_sha256)||(manifest.breathing!==undefined&&typeof manifest.breathing!=='boolean'))throw Error('Invalid motion source manifest');
 const bodyPath=workerModelPath(manifest.carry_pose,manifest.worker_model_path);
 if(manifest.sources[bodyPath]?.repo_path!==bodyPath)throw Error('Worker representation is not pinned');
 const cache=new Map<string,Promise<Uint8Array>>();
 const readSource:MotionSourceReader=path=>{
  const existing=cache.get(path);if(existing)return existing;
  const pending=(async()=>{
   const pin=manifest.sources[path];
   if(!pin||pin.repo_path!==path||!/^[a-f0-9]{64}$/.test(pin.sha256)||!Number.isSafeInteger(pin.bytes)||pin.bytes<=0||typeof pin.url!=='string'||pin.url.startsWith('/')||pin.url.includes('\\')||/^[a-zA-Z][a-zA-Z\d+.-]*:/.test(pin.url))throw Error('Unpinned motion source');
   const url=new URL(pin.url,manifestURL);
   if(url.origin!==manifestURL.origin)throw Error('Motion source must be local');
   const result=await fetch(url,{signal,cache:'no-cache'});if(!result.ok)throw Error('Motion source unavailable');
   const buffer=await result.arrayBuffer();
   const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',buffer))].map(value=>value.toString(16).padStart(2,'0')).join('');
   if(buffer.byteLength!==pin.bytes||digest!==pin.sha256)throw Error('Motion source fingerprint mismatch');
   return new Uint8Array(buffer);
  })();
  cache.set(path,pending);return pending;
 };
 return {manifest,readSource,clear:()=>cache.clear(),cachedSourceCount:()=>cache.size};
}

/** Same original P02, whole HU and four source slots as the accepted isolated calibration. */
export async function createMotionReviewSetup(readSource:MotionSourceReader,options:{carry_pose?:MotionCarryPose;breathing?:boolean;worker_model_path?:MotionWorkerModelPath}={}){
 const bodyAssetPath=workerModelPath(options.carry_pose,options.worker_model_path);
 const scene=new THREE.Scene();scene.background=new THREE.Color('#e8ede7');
 const roots=new Set<THREE.Object3D>([scene]);
 let actor:WorkerInstance|undefined,controller:Awaited<ReturnType<typeof createWarehouseLoadedWalkCalibration>>|undefined,disposed=false;
 const dispose=()=>{if(disposed)return;disposed=true;releaseResources(roots,controller,actor);};
 try{
  const decoder=new TextDecoder('utf-8',{fatal:true}),text=async(path:string)=>decoder.decode(await readSource(path));
  const paths={fixture:'frontend/public/data/v3/warehouse-fixture-v3.json',layout:'frontend/public/data/adaptive-v3/layout-manifest.json',registry:'frontend/public/data/v3/worker-registry-v3.json',profiles:'frontend/public/data/v3/worker-profiles-v3.json'};
  const bundle=await adaptWarehouseV3(Object.fromEntries(await Promise.all(Object.entries(paths).map(async([key,path])=>[key,await text(path)]))) as WarehouseTexts);
  const policy=await validateRoutePolicy(await text('frontend/public/data/v3/route-policy-v3.json'),bundle);
  const stock=createWarehouseCargo(bundle).snapshot(),hu=stock.find(row=>row.handling_unit_id==='v3:HU:initial:DEMO_067:01');
  if(!hu)throw Error('Original whole HU missing');
  const loader=new GLTFLoader();
  const bodyBytes=await readSource(bodyAssetPath);
  const body=await loader.parseAsync(bodyBytes.slice().buffer as ArrayBuffer,'');roots.add(body.scene);
  const cargoBytes=await readSource('frontend/public/models/v3/small-carton.glb');
  const cargo=await loader.parseAsync(cargoBytes.slice().buffer as ArrayBuffer,'');roots.add(cargo.scene);
  actor=createWorkerInstance(body.scene,'P02','picker');scene.add(actor.root);
  actor.root.position.set(17.14,0,42.62);actor.root.rotation.y=5*Math.PI/2;
  // The controller owns this native root's TRS at every absolute time.
  actor.root.matrixAutoUpdate=true;
  const parts:CargoMeshPart[]=[],origin=new THREE.Vector3(72,0,49),offset=new THREE.Matrix4().makeTranslation(-72,0,-49);
  const huFrame=new THREE.Matrix4().compose(new THREE.Vector3(...hu.position),new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),hu.yaw_rad),new THREE.Vector3(1,1,1));
  cargo.scene.updateMatrixWorld(true);
  cargo.scene.traverseVisible(node=>{
   if(!(node instanceof THREE.Mesh))return;
   const mesh=new THREE.InstancedMesh(node.geometry,node.material,1);
   mesh.name='instances__small-carton__'+node.name;mesh.position.copy(origin);
   mesh.userData.semanticIds=[hu.handling_unit_id];mesh.userData.semanticKind='HU';
   mesh.setMatrixAt(0,new THREE.Matrix4().multiplyMatrices(huFrame,node.matrixWorld).premultiply(offset));
   mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingBox();mesh.computeBoundingSphere();scene.add(mesh);
   parts.push({mesh,index:0,sourceMatrix:node.matrixWorld.clone()});
  });
  const cargoParts=new Map<string,readonly CargoMeshPart[]>([[hu.handling_unit_id,parts]]);
  const bindings=JSON.parse(await text('frontend/src/adaptive-v3/warehouseSupportBindings.json'));
  const cartPath='frontend/public/'+bindings.cart.path;
  const holders=compileCargoHolders(bundle,[{destination:{kind:'cart',cart_id:'C01',anchor_id:'upper-tote'},positions:{SMALL_CARTON:{position_local:[0,0,0],yaw_local_rad:0}},max_handling_units:1,max_payload_kg:12,support_tare_kg:3,max_total_gross_kg:15,source_refs:{[cartPath]:bindings.cart.sha256}}]);
  const catalogue=await registerWarehouseActionCatalogue(bundle,readSource,holders);
  scene.add(new THREE.HemisphereLight('#ffffff','#66766d',2.2));
  for(const [position,intensity] of [[[12,8,52],2.2],[[2,7,44],1.3],[[7,6,32],1.8]] as const){const light=new THREE.DirectionalLight('#fff8ee',intensity);light.position.set(position[0],position[1],position[2]);scene.add(light);}
  const floor=new THREE.Mesh(new THREE.PlaneGeometry(144,72),new THREE.MeshStandardMaterial({color:'#d6ded5',roughness:1}));floor.rotation.x=-Math.PI/2;floor.position.set(72,-.0005,36);scene.add(floor);
  const grid=new THREE.GridHelper(32,64,'#a1b6a6','#c6d0c5');grid.position.set(8,-.0003,40);scene.add(grid);
  const route=new THREE.BufferGeometry().setFromPoints([[10.75,.001,49],[6,.001,49],[6,.001,38]].map(p=>new THREE.Vector3(...p)));
  scene.add(new THREE.Line(route,new THREE.LineBasicMaterial({color:'#a49268'})));
  scene.updateMatrixWorld(true);
  controller=await createWarehouseLoadedWalkCalibration({calibration_fixture:true,motion_style:'grounded_carry',carry_pose:options.carry_pose,breathing:options.breathing,bundle,catalogue,policy,actor,bound:hu,parts,cargoParts,readSource});
  if(controller.parts.length!==4)throw Error('Expected four original active cargo parts');
  return {scene,actor,controller,cargoParts:controller.parts.map(part=>part.mesh),dispose,bodyAssetPath,
   scope:{visible_actors:1,visible_HUs:1,source_logical_population:{actors:bundle.registry.workers.length,HUs:stock.length},source_kind:'visual_fixture',engine_operation:false,runtime_scene_joined:false,source_pickup_executed:false}};
 }catch(error){dispose();throw error;}
}
