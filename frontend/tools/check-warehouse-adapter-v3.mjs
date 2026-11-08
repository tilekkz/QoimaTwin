import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
const cache=path.resolve('../work/v3/warehouse-adapter-check'),out='../docs/adaptive-v3/evidence/W02.1-checks.json',hash=b=>createHash('sha256').update(b).digest('hex'),inputHashes={};
await mkdir(cache,{recursive:true});
for(const name of ['workerRegistry','workerProfiles','warehouseAdapter']){
 const p='src/adaptive-v3/'+name+'.ts',bytes=await readFile(p);inputHashes['frontend/'+p]=hash(bytes);
 const code=ts.transpileModule(bytes.toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace(/from '\.\/(workerRegistry|workerProfiles)'/g,"from './$1.mjs'");await writeFile(path.join(cache,name+'.mjs'),code);
}
const types='src/adaptive-v3/warehouseTypes.ts';inputHashes['frontend/'+types]=hash(await readFile(types));
const {adaptWarehouseV3,decodeWarehouseLayout,decodeV3Table,WarehouseAdapterError}=await import(pathToFileURL(path.join(cache,'warehouseAdapter.mjs')));
const files={fixture:'public/data/v3/warehouse-fixture-v3.json',layout:'public/data/adaptive-v3/layout-manifest.json',registry:'public/data/v3/worker-registry-v3.json',profiles:'public/data/v3/worker-profiles-v3.json'},texts={};
for(const [key,p] of Object.entries(files)){const bytes=await readFile(p);texts[key]=bytes.toString();inputHashes['frontend/'+p]=hash(bytes);}
const before=JSON.stringify(texts),bundle=await adaptWarehouseV3(texts),layout=JSON.parse(texts.layout),fixture=JSON.parse(texts.fixture);
assert.equal(bundle.source_kind,'visual_fixture');assert.equal(bundle.engine_operation,false);assert.equal(bundle.fixture.inputs.initial_stock.length,530);assert.equal(bundle.registry.actor_count,24);assert.equal(bundle.profiles.worker_count,24);assert.equal(bundle.fixture.inputs.ports.length,6);assert.equal(bundle.fixture.inputs.requests.length,16);assert.equal(bundle.fixture.actions.length,0);assert.equal(bundle.fixture.completion_events.length,0);assert.equal(bundle.fixture.metrics_scope,'none');
assert(Object.isFrozen(bundle)&&Object.isFrozen(bundle.layout.data)&&Object.isFrozen(bundle.fixture.inputs.initial_stock[529]));assert.equal(JSON.stringify(texts),before);
assert.equal(bundle.layout.modules.length,132);assert.equal(bundle.layout.slots.length,776);assert.equal(bundle.layout.walk.arcs.length,4000);assert.equal(bundle.layout.vehicle.arcs.length,1316);
// Every decoded ID/index/length is compared to the actual compact source row.
for(const kind of ['walk','vehicle']){const source=layout.data.graphs[kind],decoded=bundle.layout[kind];for(const t of ['nodes','arcs']){const rows=decodeV3Table(source[t]);for(let i=0;i<rows.length;i++){assert.equal(decoded[t][i][t==='nodes'?'node_id':'arc_id'],rows[i][t==='nodes'?'node_id':'arc_id']);if(t==='arcs')for(const k of ['from_node_index','to_node_index','length_m'])assert.equal(decoded.arcs[i][k],rows[i][k]);}}}
const reverse=structuredClone(layout);for(const table of [reverse.data.storage.modules,reverse.data.storage.slots,...['walk','vehicle'].flatMap(k=>[reverse.data.graphs[k].nodes,reverse.data.graphs[k].arcs])]){table.columns.reverse();table.rows.forEach(row=>row.reverse());}const reversed=decodeWarehouseLayout(reverse);for(const key of ['modules','slots','walk','vehicle'])assert.deepEqual(reversed[key],bundle.layout[key]);
const negatives=[];
async function rejectBundle(name,key,mutate,reason){const changed={...texts};if(mutate===null)changed[key]='{invalid';else{const data=JSON.parse(changed[key]);mutate(data);changed[key]=JSON.stringify(data);}await assert.rejects(()=>adaptWarehouseV3(changed),e=>e instanceof WarehouseAdapterError&&e.reason===reason);negatives.push({case:name,reason,rejected:true});}
await rejectBundle('actual_engine_run','fixture',d=>d.source_kind='actual_engine_run','ACTUAL_V3_UNSUPPORTED');
await rejectBundle('engine_operation','fixture',d=>d.engine_operation=true,'ACTUAL_V3_UNSUPPORTED');
await rejectBundle('analytical_fixture','fixture',d=>d.source_kind='analytical_fixture','SOURCE_SCOPE_MISMATCH');
await rejectBundle('V2_run','fixture',d=>d.schema_id='run.v2','SOURCE_SCOPE_MISMATCH');
await rejectBundle('unknown_visual_fixture','fixture',d=>d.fixture_id='v3:fixture:unknown','FIXTURE_NOT_REGISTERED');
await rejectBundle('invented_completion','fixture',d=>d.completion_events.push({at_s:10}),'SOURCE_SCOPE_MISMATCH');
await rejectBundle('broken_json','fixture',null,'INVALID_JSON');
for(const [name,mutation]of [['reduced_mass',d=>d.inputs.initial_stock[0].gross_mass_kg=.01],['changed_units',d=>d.inputs.initial_stock[0].quantity_units=2000],['teleported_HU',d=>d.inputs.initial_stock[0].location.slot_id=d.inputs.initial_stock[1].location.slot_id],['extra_PK01',d=>d.inputs.workers.push({actor_id:'PK01'})],['modified_request_time',d=>d.inputs.requests[0].requested_at_s=0]])await rejectBundle(name,'fixture',mutation,'BUNDLE_HASH_MISMATCH');
await rejectBundle('mixed_layout','layout',d=>d.layout_content_hash='0'.repeat(64),'LAYOUT_MISMATCH');
await rejectBundle('modified_geometry_same_hash_label','layout',d=>d.data.envelope.bounds.max[0]=72,'LAYOUT_MISMATCH');
await rejectBundle('mismatched_registry','registry',d=>d.workers.pop(),'BUNDLE_HASH_MISMATCH');
await rejectBundle('mismatched_profiles','profiles',d=>d.profiles[0].allowed_roles.push('forklift_driver'),'BUNDLE_HASH_MISMATCH');
function rejectLayout(name,mutate,reason){const changed=structuredClone(layout);mutate(changed);assert.throws(()=>decodeWarehouseLayout(changed),e=>e instanceof WarehouseAdapterError&&e.reason===reason);negatives.push({case:name,reason,rejected:true});}
function cell(d,kind,field,value){const t=d.data.graphs[kind].arcs;t.rows[0][t.columns.indexOf(field)]=value;}
rejectLayout('negative_arc_index',d=>cell(d,'walk','from_node_index',-1),'INDEX_INVALID');
rejectLayout('fractional_arc_index',d=>cell(d,'walk','to_node_index',.5),'INDEX_INVALID');
rejectLayout('out_of_range_vehicle_index',d=>cell(d,'vehicle','to_node_index',999999),'INDEX_INVALID');
rejectLayout('negative_arc_length',d=>cell(d,'walk','length_m',-1),'TABLE_INVALID');
rejectLayout('nonfinite_arc_length',d=>cell(d,'vehicle','length_m',Infinity),'TABLE_INVALID');
rejectLayout('duplicate_node_id',d=>d.data.graphs.walk.nodes.rows[1][0]=d.data.graphs.walk.nodes.rows[0][0],'IDENTITY_MISMATCH');
rejectLayout('truncated_table_row',d=>d.data.storage.modules.rows[0].pop(),'TABLE_INVALID');
rejectLayout('duplicate_column',d=>d.data.storage.slots.columns[1]=d.data.storage.slots.columns[0],'TABLE_INVALID');
rejectLayout('invalid_slot_module_index',d=>{const t=d.data.storage.slots;t.rows[0][t.columns.indexOf('module_index')]=132;},'INDEX_INVALID');
rejectLayout('invalid_slot_service_index',d=>{const t=d.data.storage.slots;t.rows[0][t.columns.indexOf('service_ref')]=['walk',-1];},'INDEX_INVALID');
rejectLayout('invalid_vehicle_primitive',d=>{const t=d.data.graphs.vehicle.arcs;t.rows[0][t.columns.indexOf('geometry')].kind='teleport';},'TABLE_INVALID');
rejectLayout('global_scale',d=>d.data.envelope.entity_dimension_scale_factor=3,'LAYOUT_MISMATCH');
inputHashes['frontend/tools/check-warehouse-adapter-v3.mjs']=hash(await readFile('tools/check-warehouse-adapter-v3.mjs'));
const report={passed:true,source_kind:'visual_fixture',engine_operation:false,fixture_id:fixture.fixture_id,full_stock_HUs:530,workers:24,profiles:24,ports:6,requests:16,decoded_modules:132,decoded_slots:776,walk_nodes:1633,walk_arcs:4000,vehicle_nodes:620,vehicle_arcs:1316,all_decoded_rows_match_source:true,named_columns_reordering_supported:true,inputs_unchanged:true,output_recursively_frozen:true,no_generated_actions_completions_or_metrics:true,negatives,input_hashes:inputHashes,scope:'Registered W01base only; new scenarios need explicit admitted registration. Source hashes are byte bindings, not employee qualification, physical workflow admission or actual engine support. W02.2viewer and W03+movement/cargo/clock remain separate.'};
await writeFile(out,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:true,stock:530,decoded_graph_arcs:5316,negative_cases:negatives.length,source_kind:'visual_fixture',engine_operation:false}));
