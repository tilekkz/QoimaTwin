import * as THREE from 'three';
import {adaptWarehouseV3} from '../../../frontend/src/adaptive-v3/warehouseAdapter.ts';
import {createWarehouseCargo} from '../../../frontend/src/adaptive-v3/warehouseCargo.ts';
import {compileCargoHolders} from '../../../frontend/src/adaptive-v3/warehouseCargoHolders.ts';
import {registerWarehouseActionCatalogue} from '../../../frontend/src/adaptive-v3/warehouseActionTimeline.ts';
import {validateRoutePolicy} from '../../../frontend/src/adaptive-v3/warehouseRouting.ts';

/** One visible actor/HU, original source-bound owner. Other warehouse objects are not drawn. */
export async function attachLiveCalibration({scene,actor,cargoTemplate,source,manifest}){
 const decoder=new TextDecoder(),text=async path=>decoder.decode(await source(path));
 const bundle=await adaptWarehouseV3(Object.fromEntries(await Promise.all(Object.entries({fixture:'frontend/public/data/v3/warehouse-fixture-v3.json',layout:'frontend/public/data/adaptive-v3/layout-manifest.json',registry:'frontend/public/data/v3/worker-registry-v3.json',profiles:'frontend/public/data/v3/worker-profiles-v3.json'}).map(async([key,path])=>[key,await text(path)]))));
 const policy=await validateRoutePolicy(await text('frontend/public/data/v3/route-policy-v3.json'),bundle);
 const stock=createWarehouseCargo(bundle).snapshot(),hu=stock.find(row=>row.handling_unit_id==='v3:HU:initial:DEMO_067:01');
 if(!hu)throw Error('Original whole HU missing');
 actor.root.position.set(17.14,0,42.62);actor.root.rotation.y=5*Math.PI/2;
 const parts=[],origin=new THREE.Vector3(72,0,49),offset=new THREE.Matrix4().makeTranslation(-72,0,-49);
 const huFrame=new THREE.Matrix4().compose(new THREE.Vector3(...hu.position),new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),hu.yaw_rad),new THREE.Vector3(1,1,1));
 cargoTemplate.updateMatrixWorld(true);
 cargoTemplate.traverseVisible(node=>{if(!(node instanceof THREE.Mesh))return;const mesh=new THREE.InstancedMesh(node.geometry,node.material,1);mesh.name='instances__small-carton__'+node.name;mesh.position.copy(origin);mesh.userData.semanticIds=[hu.handling_unit_id];mesh.userData.semanticKind='HU';mesh.setMatrixAt(0,new THREE.Matrix4().multiplyMatrices(huFrame,node.matrixWorld).premultiply(offset));mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingBox();mesh.computeBoundingSphere();scene.add(mesh);parts.push({mesh,index:0,sourceMatrix:node.matrixWorld.clone()});});
 const cargoParts=new Map([[hu.handling_unit_id,parts]]),bindings=JSON.parse(await text('frontend/src/adaptive-v3/warehouseSupportBindings.json'));
 const cartPath='frontend/public/'+bindings.cart.path;
 const holders=compileCargoHolders(bundle,[{destination:{kind:'cart',cart_id:'C01',anchor_id:'upper-tote'},positions:{SMALL_CARTON:{position_local:[0,0,0],yaw_local_rad:0}},max_handling_units:1,max_payload_kg:12,support_tare_kg:3,max_total_gross_kg:15,source_refs:{[cartPath]:bindings.cart.sha256}}]);
 const catalogue=await registerWarehouseActionCatalogue(bundle,source,holders);
 scene.updateMatrixWorld(true);
 const {createWarehouseLoadedWalkCalibration}=await import(/* @vite-ignore */manifest.source_module_url);
 const controller=await createWarehouseLoadedWalkCalibration({calibration_fixture:true,motion_style:manifest.motion_style??'source',bundle,catalogue,policy,actor,bound:hu,parts,cargoParts,readSource:source});
 return {controller,cargoParts:controller.parts.map(part=>part.mesh),scope:{visible_actors:1,visible_HUs:1,source_logical_population:{actors:bundle.registry.workers.length,HUs:stock.length},source_pickup_executed:false,runtime_scene_joined:false,engine_operation:false}};
}
