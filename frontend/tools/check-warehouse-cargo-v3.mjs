import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';

const cache=path.resolve('../work/v3/warehouse-cargo-check'),input_hashes={};
const sha=b=>createHash('sha256').update(b).digest('hex');
await mkdir(cache,{recursive:true});
for(const name of ['workerRegistry','workerProfiles','warehouseAdapter','warehouseCargoHolders','warehouseCargo']){
 const p='src/adaptive-v3/'+name+'.ts',bytes=await readFile(p);input_hashes['frontend/'+p]=sha(bytes);
 const code=ts.transpileModule(bytes.toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace(/from '\.\/(workerRegistry|workerProfiles|warehouseAdapter|warehouseCargoHolders)'/g,"from './$1.mjs'");
 await writeFile(path.join(cache,name+'.mjs'),code);
}
for(const p of ['src/adaptive-v3/warehouseTypes.ts','tools/check-warehouse-cargo-v3.mjs'])input_hashes['frontend/'+p]=sha(await readFile(p));
const texts={};
for(const [key,p]of Object.entries({fixture:'public/data/v3/warehouse-fixture-v3.json',layout:'public/data/adaptive-v3/layout-manifest.json',registry:'public/data/v3/worker-registry-v3.json',profiles:'public/data/v3/worker-profiles-v3.json'})){
 const bytes=await readFile(p);texts[key]=bytes.toString();input_hashes['frontend/'+p]=sha(bytes);
}
const {adaptWarehouseV3}=await import(pathToFileURL(path.join(cache,'warehouseAdapter.mjs')));
const {createWarehouseCargo}=await import(pathToFileURL(path.join(cache,'warehouseCargo.mjs')));
const bundle=await adaptWarehouseV3(texts),cargo=createWarehouseCargo(bundle),before=JSON.stringify(cargo.snapshot());
const initial=cargo.snapshot(),modules=new Map(bundle.layout.modules.map(m=>[m.module_id,m]));
assert.equal(initial.length,530);assert.equal(new Set(initial.map(h=>h.handling_unit_id)).size,530);
let maximum_initial_position_error_m=0,world_corner_checks=0;
for(const bound of initial){
 const h=bound.cargo,m=modules.get(h.location.module_id),p=h.location.placement,c=Math.cos(m.yaw_rad),s=Math.sin(m.yaw_rad);
 const expected=[m.world_pos[0]+c*p.centre_local_xyz_m[0]+s*p.centre_local_xyz_m[2],m.world_pos[1]+p.bottom_y_m,m.world_pos[2]-s*p.centre_local_xyz_m[0]+c*p.centre_local_xyz_m[2]];
 maximum_initial_position_error_m=Math.max(maximum_initial_position_error_m,...bound.position.map((v,i)=>Math.abs(v-expected[i])));
 const slot=bundle.layout.slots.find(s=>s.slot_id===bound.destination.slot_id);
 assert.equal(bound.yaw_rad,m.yaw_rad);assert.equal(bound.model_scale_factor,1);assert.equal(bound.position[1],slot.usable_bounds_world.min[1]);
 for(const x of [-.5,.5])for(const y of [0,1])for(const z of [-.5,.5]){
  const local=[x*h.dimensions_xyz_m[0],y*h.dimensions_xyz_m[1],z*h.dimensions_xyz_m[2]],world=[bound.position[0]+c*local[0]+s*local[2],bound.position[1]+local[1],bound.position[2]-s*local[0]+c*local[2]];
  world.forEach((v,i)=>assert(v>=slot.usable_bounds_world.min[i]-1e-8&&v<=slot.usable_bounds_world.max[i]+1e-8));world_corner_checks++;
 }
 assert(Object.isFrozen(bound)&&Object.isFrozen(bound.position)&&Object.isFrozen(bound.destination)&&Object.isFrozen(bound.cargo));
}
assert(maximum_initial_position_error_m<1e-8);
const totals=()=>cargo.snapshot().reduce((a,b)=>[a[0]+b.cargo.quantity_units,a[1]+b.cargo.gross_mass_kg],[0,0]);
assert.equal(totals()[0],12256);assert(Math.abs(totals()[1]-9403.85)<1e-7);
const negatives=[];
function reject(name,changes,reason){const saved=JSON.stringify(cargo.snapshot());const r=cargo.apply(changes);assert.equal(r.ok,false,name);assert.equal(r.reason,reason,name);assert.equal(r.cost_evaluated,false);assert.equal(JSON.stringify(cargo.snapshot()),saved,name);negatives.push({case:name,reason,rejected:true});}
const h=initial[0],other=initial.find(i=>i.cargo.archetype_id==='SMALL_CARTON'&&i.handling_unit_id!==h.handling_unit_id);
const at=(id,slot)=>({handling_unit_id:id,destination:{kind:'storage_slot',slot_id:slot}});
reject('missing_changes',null,'INVALID_REQUEST');
reject('unknown_HU',[at('invented',h.destination.slot_id)],'UNKNOWN_HU');
reject('duplicate_HU',[at(h.handling_unit_id,h.destination.slot_id),at(h.handling_unit_id,h.destination.slot_id)],'DUPLICATE_HU');
reject('unknown_slot',[at(h.handling_unit_id,'invented')],'UNKNOWN_SLOT');
reject('occupied_slot',[at(h.handling_unit_id,other.destination.slot_id)],'SLOT_OCCUPIED');
const reserve=bundle.layout.slots.find(s=>s.reserve_only),heavy=bundle.layout.slots.find(s=>bundle.layout.modules[s.module_index].family==='HEAVY');
reject('reserved_slot',[at(h.handling_unit_id,reserve.slot_id)],'RESERVE_SLOT');
reject('forbidden_family',[at(h.handling_unit_id,heavy.slot_id)],'CARGO_CLASS_FORBIDDEN');
for(const key of ['dimensions_xyz_m','gross_mass_kg','quantity_units','orientation_id','model_scale_factor'])reject('HU_override_'+key,[{...at(h.handling_unit_id,h.destination.slot_id),[key]:key==='model_scale_factor'?.9:'override'}],'INVALID_REQUEST');
for(const key of ['position','yaw_rad','scale','support_gap_m'])reject('destination_override_'+key,[{handling_unit_id:h.handling_unit_id,destination:{...h.destination,[key]:0}}],'INVALID_REQUEST');
for(const destination of [{kind:'actor',actor_id:'P01',anchor_id:'hands'},{kind:'vehicle',vehicle_id:'FL01',anchor_id:'forks'},{kind:'cart',cart_id:'C01',anchor_id:'deck'},{kind:'belt',cell_id:'V3-C-MAIN-000'}])reject('unreviewed_'+destination.kind,[{handling_unit_id:h.handling_unit_id,destination}],'PHYSICAL_HOLDER_NOT_REGISTERED');
for(const kind of ['constructor','hasOwnProperty'])reject('inherited_destination_kind_'+kind,[{handling_unit_id:h.handling_unit_id,destination:{kind}}],'INVALID_REQUEST');
reject('two_simultaneous_parents',[{...at(h.handling_unit_id,h.destination.slot_id),destination:[h.destination,h.destination]}],'INVALID_REQUEST');
reject('invalid_request_object',{},'INVALID_REQUEST');
assert.throws(()=>createWarehouseCargo(structuredClone(bundle)),/VALIDATED_VISUAL_BUNDLE_REQUIRED/);
// A batch swap is atomic: both source slots are released before occupancy is evaluated.
const swap=[at(h.handling_unit_id,other.destination.slot_id),at(other.handling_unit_id,h.destination.slot_id)];
assert(cargo.evaluate(swap).ok);assert.equal(JSON.stringify(cargo.snapshot()),before);assert(cargo.apply(swap).ok);
swap[0].destination.slot_id='invented';assert.notEqual(cargo.snapshot()[0].destination.slot_id,'invented');
assert.deepEqual(totals().map((v,i)=>i?Math.round(v*100):v),[12256,940385]);
const swapped=JSON.stringify(cargo.snapshot());assert(cargo.apply([]).ok);assert.equal(JSON.stringify(cargo.snapshot()),swapped);
assert.equal(JSON.stringify(cargo.reset()),before);assert.equal(JSON.stringify(cargo.reset()),before);
// Exercise compatible free slots for every original family with an independent active-source candidate list.
const raw=JSON.parse(texts.layout).data.storage.slots,rows=raw.rows.map(r=>Object.fromEntries(raw.columns.map((c,i)=>[c,r[i]]))),used=new Set(initial.map(h=>h.destination.slot_id)),relocations=[];
for(const archetype of bundle.fixture.inputs.archetypes){
 const item=initial.find(i=>i.cargo.archetype_id===archetype.archetype_id),candidate=rows.find(s=>!used.has(s.slot_id)&&!s.reserve_only&&!s.retrieval_blocked&&s.allowed_cargo_archetype_ids.includes(archetype.archetype_id)&&item.cargo.dimensions_xyz_m.every((d,i)=>d+2*s.clearance_each_side_m<=s.usable_dimensions_xyz_m[i]+1e-9)&&item.cargo.gross_mass_kg<=s.max_payload_kg);
 if(!candidate)continue;
 const change=at(item.handling_unit_id,candidate.slot_id);assert(cargo.apply([change]).ok);const relocated=cargo.snapshot().find(i=>i.handling_unit_id===item.handling_unit_id);assert.equal(relocated.destination.slot_id,candidate.slot_id);relocations.push({archetype_id:archetype.archetype_id,handling_unit_id:item.handling_unit_id,slot_id:candidate.slot_id,position:relocated.position,yaw_rad:relocated.yaw_rad});cargo.reset();
}
assert(relocations.length>=7);
assert.equal(JSON.stringify(cargo.snapshot()),before);assert.equal(cargo.completed_jobs,0);assert.equal(cargo.engine_operation,false);
const report={passed:true,source_kind:'visual_fixture',engine_operation:false,initial_HUs:530,quantity_units:12256,gross_mass_kg:9403.85,maximum_initial_position_error_m,world_corner_checks,negative_cases:negatives,compatible_free_relocations:relocations,initial_placements:initial.map(i=>({handling_unit_id:i.handling_unit_id,slot_id:i.destination.slot_id,position:i.position,yaw_rad:i.yaw_rad})),atomic_swap:true,absolute_reset:true,input_hashes,scope:'Immutable identities/single-parent storage binding and placement admission only. Actual shared mesh/support and physical actor/vehicle/cart/belt holders remain W04.2/W04.3; no transfer/action/resource or engine completion.'};
await writeFile('../docs/adaptive-v3/evidence/W04.1-checks.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,input_hashes:undefined,initial_placements:undefined,negative_cases:negatives.length,compatible_free_relocations:relocations.length}));
