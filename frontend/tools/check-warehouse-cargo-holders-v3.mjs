import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import * as THREE from 'three';
import ts from 'typescript';

const cache=path.resolve('../work/v3/warehouse-cargo-holders-check'),input_hashes={};
const sha=b=>createHash('sha256').update(b).digest('hex');
await mkdir(cache,{recursive:true});
for(const name of ['workerRegistry','workerProfiles','warehouseAdapter','warehouseCargoHolders','warehouseCargo']){
 const p='src/adaptive-v3/'+name+'.ts',bytes=await readFile(p);input_hashes['frontend/'+p]=sha(bytes);
 const code=ts.transpileModule(bytes.toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace(/from '\.\/(workerRegistry|workerProfiles|warehouseAdapter|warehouseCargoHolders)'/g,"from './$1.mjs'");
 await writeFile(path.join(cache,name+'.mjs'),code);
}
for(const p of ['src/adaptive-v3/warehouseTypes.ts','tools/check-warehouse-cargo-holders-v3.mjs','package.json'])input_hashes['frontend/'+p]=sha(await readFile(p));
const texts={};
for(const [key,p]of Object.entries({fixture:'public/data/v3/warehouse-fixture-v3.json',layout:'public/data/adaptive-v3/layout-manifest.json',registry:'public/data/v3/worker-registry-v3.json',profiles:'public/data/v3/worker-profiles-v3.json'})){
 const bytes=await readFile(p);texts[key]=bytes.toString();input_hashes['frontend/'+p]=sha(bytes);
}
const sourcePaths=['frontend/public/models/v3/worker-manual.glb','frontend/public/models/v3/forklift.glb','frontend/public/models/v3/picking-cart-tote-fixture.glb','frontend/public/models/v3/conveyor-straight.glb','docs/v3/contract-proposals/vehicle-handling-v3.json'];
const source_refs={};for(const p of sourcePaths){source_refs[p]=sha(await readFile('../'+p));input_hashes[p]=source_refs[p];}
const c08=JSON.parse(await readFile('../docs/v3/contract-proposals/vehicle-handling-v3.json','utf8'));
const {adaptWarehouseV3}=await import(pathToFileURL(path.join(cache,'warehouseAdapter.mjs')));
const {createWarehouseCargo}=await import(pathToFileURL(path.join(cache,'warehouseCargo.mjs')));
const {compileCargoHolders,isCargoHolderCatalogue,cargoHolderKey,holderByDestination}=await import(pathToFileURL(path.join(cache,'warehouseCargoHolders.mjs')));
const bundle=await adaptWarehouseV3(texts),initial=bundle.fixture.inputs.initial_stock;
const byFamily=family=>initial.find(h=>h.archetype_id===family),small=initial.filter(h=>h.archetype_id==='SMALL_CARTON');
const actor={kind:'actor',actor_id:'P01',anchor_id:'two-hand-small'},vehicle={kind:'vehicle',vehicle_id:'FL01',anchor_id:'forks'},vehicle2={kind:'vehicle',vehicle_id:'FL02',anchor_id:'forks'},cart={kind:'cart',cart_id:'C01',anchor_id:'upper-tote'},belt={kind:'belt',cell_id:'V3-C-MAIN-000'};
const pose=(position_local,support_tare_kg)=>({position_local,yaw_local_rad:0,...(support_tare_kg===undefined?{}:{support_tare_kg})});
const vehiclePositions=Object.fromEntries(c08.loads.map(load=>[load.archetype_id,pose([(load.cargo_bounds_local_m.min[0]+load.cargo_bounds_local_m.max[0])/2,load.cargo_bounds_local_m.min[1]-.7,(load.cargo_bounds_local_m.min[2]+load.cargo_bounds_local_m.max[2])/2],load.attachment_mass_kg)]));
const definition=(destination,positions,max_payload_kg,support_tare_kg,max_total_gross_kg)=>({destination,positions,max_handling_units:1,max_payload_kg,support_tare_kg,max_total_gross_kg,source_refs:{...source_refs}});
const definitions=[definition(actor,{SMALL_CARTON:pose([0,.95,.4])},15,0,15),definition(vehicle,vehiclePositions,1000,0,1000),definition(vehicle2,vehiclePositions,1000,0,1000),definition(cart,{SMALL_CARTON:pose([0,.02,0])},12,3,15),definition(belt,{SMALL_CARTON:pose([0,0,0]),STANDARD_CARTON:pose([0,0,0])},15,0,15)];
const frames=new Map([[cargoHolderKey(actor),{position:[72,0,36],yaw_rad:0,scale:[1,1,1]}],[cargoHolderKey(vehicle),{position:[6,.7,18],yaw_rad:Math.PI/2,scale:[1,1,1]}],[cargoHolderKey(vehicle2),{position:[138,.7,18],yaw_rad:-Math.PI/2,scale:[1,1,1]}],[cargoHolderKey(cart),{position:[20,.62,48],yaw_rad:Math.PI/2,scale:[1,1,1]}],[cargoHolderKey(belt),{position:[128,.92,3],yaw_rad:-Math.PI/2,scale:[1,1,1]}]]);
const catalogue=compileCargoHolders(bundle,definitions),cargo=createWarehouseCargo(bundle);let frameCalls=0;
const resolve=destination=>{frameCalls++;return frames.get(cargoHolderKey(destination));};
cargo.registerHolders(catalogue,resolve);
const before=JSON.stringify(cargo.snapshot()),negative_cases=[],positives=[];
const bind=(hu,destination)=>({handling_unit_id:hu.handling_unit_id,destination});
const home=hu=>({kind:'storage_slot',slot_id:hu.location.slot_id});
function conserved(){const rows=cargo.snapshot();assert.equal(rows.length,530);assert.equal(new Set(rows.map(r=>r.handling_unit_id)).size,530);assert.equal(rows.reduce((s,r)=>s+r.cargo.quantity_units,0),12256);assert(Math.abs(rows.reduce((s,r)=>s+r.cargo.gross_mass_kg,0)-9403.85)<1e-7);for(const row of rows){assert.deepEqual(row.cargo,initial.find(h=>h.handling_unit_id===row.handling_unit_id));assert.equal(row.model_scale_factor,1);assert(Object.isFrozen(row)&&Object.isFrozen(row.position)&&Object.isFrozen(row.destination)&&Object.isFrozen(row.cargo));}assert.equal(cargo.completed_jobs,0);assert.equal(cargo.engine_operation,false);return rows;}
function reject(name,changes,reason){const previous=JSON.stringify(cargo.snapshot()),r=cargo.apply(changes);assert.equal(r.ok,false,name);assert.equal(r.reason,reason,name);assert.equal(r.cost_evaluated,false);assert.equal(JSON.stringify(cargo.snapshot()),previous,name);negative_cases.push({case:name,reason,rejected:true});}
function badDefinition(name,mutate,reason){const value=structuredClone(definitions);mutate(value);assert.throws(()=>compileCargoHolders(bundle,value),new RegExp(reason),name);negative_cases.push({case:name,reason,rejected:true});}
function expectedPose(hu,destination){const holder=holderByDestination(catalogue,destination),frame=frames.get(cargoHolderKey(destination)),local=holder.positions[hu.archetype_id].position_local;return new THREE.Vector3(...local).applyMatrix4(new THREE.Matrix4().compose(new THREE.Vector3(...frame.position),new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),frame.yaw_rad),new THREE.Vector3(1,1,1))).toArray();}
function positive(hu,destination,label){const previous=JSON.stringify(cargo.snapshot()),request=[bind(hu,destination)];assert(cargo.evaluate(request).ok);assert.equal(JSON.stringify(cargo.snapshot()),previous);assert(cargo.apply(request).ok);const bound=conserved().find(r=>r.handling_unit_id===hu.handling_unit_id);assert.deepEqual(bound.destination,destination);assert.equal(bound.yaw_rad,frames.get(cargoHolderKey(destination)).yaw_rad);assert(bound.position.every((x,i)=>Math.abs(x-expectedPose(hu,destination)[i])<1e-12));positives.push({case:label,handling_unit_id:hu.handling_unit_id,archetype_id:hu.archetype_id,destination,position:bound.position,yaw_rad:bound.yaw_rad});}

assert(isCargoHolderCatalogue(catalogue,bundle));assert(Object.isFrozen(catalogue)&&Object.isFrozen(catalogue.holders)&&Object.isFrozen(catalogue.holders[0].positions.SMALL_CARTON.position_local));
definitions[0].positions.SMALL_CARTON.position_local[1]=99;assert.equal(holderByDestination(catalogue,actor).positions.SMALL_CARTON.position_local[1],.95);definitions[0].positions.SMALL_CARTON.position_local[1]=.95;
assert.equal(JSON.stringify(conserved()),before);
for(const destination of [actor,cart,belt])positive(small[0],destination,'same_HU_storage_actor_cart_belt_'+destination.kind);
assert(cargo.apply([bind(small[0],home(small[0]))]).ok);assert.equal(JSON.stringify(cargo.snapshot()),before);
for(const load of c08.loads){positive(byFamily(load.archetype_id),vehicle,'vehicle_'+load.archetype_id);cargo.reset();}
positive(byFamily('PALLET_LOAD'),vehicle2,'canonical_FL02_F02');cargo.reset();positive(byFamily('STANDARD_CARTON'),belt,'belt_STANDARD_CARTON');cargo.reset();
positive(small[0],actor,'actor_dynamic_frame_start');const originalFrame=structuredClone(frames.get(cargoHolderKey(actor))),first=JSON.stringify(cargo.snapshot());
for(const at of [3,0,1,3,2,0]){frames.set(cargoHolderKey(actor),{position:[72+at,0,36-at],yaw_rad:at*Math.PI/4,scale:[1,1,1]});const row=conserved().find(r=>r.handling_unit_id===small[0].handling_unit_id);assert(row.position.every((x,i)=>Math.abs(x-expectedPose(small[0],actor)[i])<1e-12));}
frames.set(cargoHolderKey(actor),originalFrame);assert.equal(JSON.stringify(cargo.snapshot()),first);cargo.reset();
positive(small[0],actor,'atomic_swap_actor');positive(small[1],cart,'atomic_swap_cart');assert(cargo.apply([bind(small[0],cart),bind(small[1],actor)]).ok);conserved();assert.equal(cargo.snapshot().find(r=>r.handling_unit_id===small[0].handling_unit_id).destination.kind,'cart');
reject('occupied_actor',[bind(small[2],actor)],'HOLDER_OCCUPIED');reject('occupied_cart',[bind(small[2],cart)],'HOLDER_OCCUPIED');
assert.throws(()=>cargo.registerHolders(catalogue,resolve),/HOLDERS_IN_USE/);negative_cases.push({case:'replace_catalogue_while_held',reason:'HOLDERS_IN_USE',rejected:true});cargo.reset();
for(const destination of [actor,cart,belt])reject('unsupported_HEAVY_'+destination.kind,[bind(byFamily('HEAVY_BOX'),destination)],'HOLDER_CARGO_FORBIDDEN');
reject('unsupported_SMALL_vehicle',[bind(small[0],vehicle)],'HOLDER_CARGO_FORBIDDEN');
reject('unknown_actor',[bind(small[0],{...actor,actor_id:'P99'})],'PHYSICAL_HOLDER_NOT_REGISTERED');reject('unknown_vehicle',[bind(byFamily('IBC'),{...vehicle,vehicle_id:'FL99'})],'PHYSICAL_HOLDER_NOT_REGISTERED');reject('unknown_cart',[bind(small[0],{...cart,cart_id:'C99'})],'PHYSICAL_HOLDER_NOT_REGISTERED');reject('unknown_cell',[bind(small[0],{kind:'belt',cell_id:'unknown'})],'PHYSICAL_HOLDER_NOT_REGISTERED');
for(const field of ['position','scale','dimensions_xyz_m','gross_mass_kg','quantity_units','support_tare_kg'])reject('binding_override_'+field,[{...bind(small[0],actor),[field]:0}],'INVALID_REQUEST');
reject('destination_transform_override',[bind(small[0],{...actor,position:[0,0,0]})],'INVALID_REQUEST');
reject('two_destinations',[bind(small[0],[actor,cart])],'INVALID_REQUEST');reject('duplicate_binding',[bind(small[0],actor),bind(small[0],cart)],'DUPLICATE_HU');
assert(!isCargoHolderCatalogue(structuredClone(catalogue)));assert.throws(()=>cargo.registerHolders(structuredClone(catalogue),resolve),/INVALID_HOLDER_CATALOGUE/);negative_cases.push({case:'cloned_unissued_catalogue',reason:'INVALID_HOLDER_CATALOGUE',rejected:true});
const otherBundle=await adaptWarehouseV3(texts),stale=compileCargoHolders(otherBundle,definitions);assert.throws(()=>cargo.registerHolders(stale,resolve),/INVALID_HOLDER_CATALOGUE/);negative_cases.push({case:'catalogue_from_other_bundle_instance',reason:'INVALID_HOLDER_CATALOGUE',rejected:true});
badDefinition('unknown_definition_field',d=>d[0].dimension_scale=.9,'INVALID_HOLDER_DEFINITION');
badDefinition('second_anchor_same_actor',d=>d.push({...structuredClone(d[0]),destination:{...actor,anchor_id:'other'}}),'DUPLICATE_PHYSICAL_HOLDER');
badDefinition('second_anchor_same_vehicle',d=>d.push({...structuredClone(d[1]),destination:{...vehicle,anchor_id:'other'}}),'DUPLICATE_PHYSICAL_HOLDER');
badDefinition('second_anchor_same_cart',d=>d.push({...structuredClone(d[3]),destination:{...cart,anchor_id:'other'}}),'DUPLICATE_PHYSICAL_HOLDER');
badDefinition('driver_manual_holder',d=>d[0].destination.actor_id='F01','INELIGIBLE_ACTOR_HOLDER');badDefinition('unknown_actor_definition',d=>d[0].destination.actor_id='P99','INELIGIBLE_ACTOR_HOLDER');badDefinition('unknown_vehicle_definition',d=>d[1].destination.vehicle_id='FL99','INELIGIBLE_VEHICLE_HOLDER');badDefinition('unknown_belt_definition',d=>d[4].destination.cell_id='unknown','UNKNOWN_BELT_CELL');
badDefinition('unknown_cart_definition',d=>d[3].destination.cart_id='C02','UNKNOWN_CART_FIXTURE');badDefinition('bare_cart_without_tote_source',d=>delete d[3].source_refs['frontend/public/models/v3/picking-cart-tote-fixture.glb'],'UNKNOWN_CART_FIXTURE');
badDefinition('invented_actor_anchor',d=>d[0].destination.anchor_id='other','UNKNOWN_HOLDER_ANCHOR');badDefinition('two_HUs_per_holder',d=>d[0].max_handling_units=2,'INVALID_HOLDER_CAPACITY');badDefinition('negative_payload',d=>d[0].max_payload_kg=-1,'INVALID_HOLDER_CAPACITY');badDefinition('NaN_payload',d=>d[0].max_payload_kg=NaN,'INVALID_HOLDER_CAPACITY');badDefinition('infinite_tare',d=>d[0].support_tare_kg=Infinity,'INVALID_HOLDER_CAPACITY');
badDefinition('actor_over15kg',d=>d[0].max_payload_kg=16,'ACTOR_HOLDER_CAPACITY_FORBIDDEN');badDefinition('belt_over15kg',d=>d[4].max_payload_kg=16,'BELT_HOLDER_CAPACITY_FORBIDDEN');badDefinition('cart_over12kg_payload',d=>d[3].max_payload_kg=13,'CART_TOTE_CAPACITY_FORBIDDEN');badDefinition('cart_missing3kg_tote',d=>d[3].support_tare_kg=0,'CART_TOTE_CAPACITY_FORBIDDEN');badDefinition('vehicle_over1000kg',d=>d[1].max_payload_kg=1001,'VEHICLE_HOLDER_CAPACITY_FORBIDDEN');
badDefinition('actor_HEAVY_class',d=>d[0].positions={HEAVY_BOX:pose([0,0,0])},'HOLDER_CARGO_CLASS_FORBIDDEN');badDefinition('vehicle_SMALL_class',d=>d[1].positions={SMALL_CARTON:pose([0,0,0],0)},'HOLDER_CARGO_CLASS_FORBIDDEN');badDefinition('belt_LONG_class',d=>d[4].positions={LONG_BUNDLE:pose([0,0,0])},'HOLDER_CARGO_CLASS_FORBIDDEN');
badDefinition('rotated_local_orientation',d=>d[0].positions.SMALL_CARTON.yaw_local_rad=Math.PI/2,'INVALID_HOLDER_LOCAL_POSE');badDefinition('NaN_local_position',d=>d[0].positions.SMALL_CARTON.position_local[0]=NaN,'INVALID_HOLDER_LOCAL_POSE');badDefinition('local_scale_override',d=>d[0].positions.SMALL_CARTON.scale=[.9,.9,.9],'INVALID_HOLDER_LOCAL_POSE');badDefinition('manual_profile_tare_override',d=>d[0].positions.SMALL_CARTON.support_tare_kg=0,'HOLDER_PROFILE_TARE_OVERRIDE_FORBIDDEN');
badDefinition('LONG_missing40kg_cradle',d=>d[1].positions.LONG_BUNDLE.support_tare_kg=0,'VEHICLE_SUPPORT_TARE_MISMATCH');badDefinition('nonLONG_invented_cradle',d=>d[1].positions.HEAVY_BOX.support_tare_kg=40,'VEHICLE_SUPPORT_TARE_MISMATCH');badDefinition('empty_source_refs',d=>d[0].source_refs={},'INVALID_HOLDER_SOURCE_REFS');badDefinition('bad_source_SHA',d=>d[0].source_refs[sourcePaths[0]]='bad','INVALID_HOLDER_SOURCE_REFS');badDefinition('source_path_traversal',d=>d[0].source_refs['../outside.glb']='a'.repeat(64),'INVALID_HOLDER_SOURCE_REFS');
const low=structuredClone(definitions);low[0].max_payload_kg=.5;const lowCatalogue=compileCargoHolders(bundle,low);cargo.registerHolders(lowCatalogue,resolve);frameCalls=0;reject('whole_HU_payload_limit',[bind(small[0],actor)],'HOLDER_OVERWEIGHT');assert.equal(frameCalls,0);
const lowTotal=structuredClone(definitions);lowTotal[3].max_total_gross_kg=3.5;cargo.registerHolders(compileCargoHolders(bundle,lowTotal),resolve);frameCalls=0;reject('HU_plus_tote_tare',[bind(small[0],cart)],'HOLDER_TOTAL_OVERWEIGHT');assert.equal(frameCalls,0);
const limitedVehicle=structuredClone(definitions);limitedVehicle[1].max_total_gross_kg=230;cargo.registerHolders(compileCargoHolders(bundle,limitedVehicle),resolve);assert(cargo.apply([bind(byFamily('HEAVY_BOX'),vehicle)]).ok);cargo.reset();frameCalls=0;reject('LONG200_plus_cradle40',[bind(byFamily('LONG_BUNDLE'),vehicle)],'HOLDER_TOTAL_OVERWEIGHT');assert.equal(frameCalls,0);
cargo.registerHolders(catalogue,resolve);
const actorKey=cargoHolderKey(actor),good=structuredClone(frames.get(actorKey));
for(const [name,frame,reason]of [
 ['NaN_frame',{...good,position:[NaN,0,36]},'INVALID_HOLDER_FRAME'],['infinite_yaw',{...good,yaw_rad:Infinity},'INVALID_HOLDER_FRAME'],['scaled_frame',{...good,scale:[.9,1,1]},'INVALID_HOLDER_FRAME'],['extra_frame_transform',{...good,matrix:[]},'INVALID_HOLDER_FRAME'],['outside_frame',{...good,position:[145,0,36]},'HOLDER_OUTSIDE_WAREHOUSE'],['cargo_outside_frame',{...good,position:[.1,0,36]},'HOLDER_OUTSIDE_WAREHOUSE'],['cargo_above_roof',{...good,position:[72,7.5,36]},'HOLDER_OUTSIDE_WAREHOUSE']]){frames.set(actorKey,frame);const admission=cargo.apply([bind(small[0],actor)]);assert.equal(admission.ok,false,name);assert.equal(admission.reason,reason,name);frames.set(actorKey,good);assert.equal(JSON.stringify(cargo.snapshot()),before);negative_cases.push({case:name,reason,rejected:true});}
cargo.registerHolders(catalogue,()=>{throw Error('Unavailable physical frame');});reject('frame_provider_throws',[bind(small[0],actor)],'INVALID_HOLDER_FRAME');cargo.registerHolders(catalogue,resolve);
positive(small[0],actor,'held_frame_snapshot');const held=JSON.stringify(cargo.snapshot());frames.set(actorKey,{...good,scale:[1,0,1]});assert.throws(()=>cargo.snapshot(),/INVALID_HOLDER_FRAME/);assert.equal(cargo.apply([]).reason,'INVALID_HOLDER_FRAME');frames.set(actorKey,good);assert.equal(JSON.stringify(cargo.snapshot()),held);negative_cases.push({case:'invalid_current_frame_does_not_commit',reason:'INVALID_HOLDER_FRAME',rejected:true});
frames.set(actorKey,{...good,position:[NaN,0,0]});cargo.reset();assert.equal(JSON.stringify(cargo.snapshot()),before);frames.set(actorKey,good);cargo.reset();assert.equal(JSON.stringify(conserved()),before);
// Batch validation is performed before consulting physical frames.
frameCalls=0;reject('occupied_before_pose_query',[bind(small[0],actor),bind(small[1],actor)],'HOLDER_OCCUPIED');assert.equal(frameCalls,0);
assert.throws(()=>cargo.registerHolders(catalogue,null),/INVALID_HOLDER_CATALOGUE/);negative_cases.push({case:'missing_frame_provider',reason:'INVALID_HOLDER_CATALOGUE',rejected:true});
const report={passed:true,source_kind:'visual_fixture',engine_operation:false,operational_admission:false,initial_HUs:530,quantity_units:12256,gross_mass_kg:9403.85,holder_definitions:catalogue.holders.length,vehicle_families_checked:c08.loads.length,positive_cases:positives,negative_cases,all_requests_before_cost:true,issued_catalogue_bundle_binding:true,one_holder_per_physical_entity:true,LONG_cradle_tare_kg:40,cart_tote_tare_payload_total_kg:[3,12,15],absolute_current_frame_poses:true,atomic_batch_swap:true,absolute_reset:true,input_hashes,scope:'Pure immutable single-owner declared holder state and synthetic capacity/capability checks only. Test poses are not native contact admission. Root must independently verify source GLBs/physical support, actions and resources before scene use; no warehouse operation, engine run or parent PASS.'};
await writeFile('../docs/adaptive-v3/evidence/W04.3-holder-state-checks.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,positive_cases:positives.length,negative_cases:negative_cases.length,input_hashes:undefined}));
