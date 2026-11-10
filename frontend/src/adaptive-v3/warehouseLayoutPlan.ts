import {adaptWarehouseV3,decodeV3Table,type WarehouseTexts} from './warehouseAdapter';
import {staffingHomeNodes} from './workerRoleAssignment';
import type {WarehouseBundle,WarehouseModule,XYZ,V3Bounds} from './warehouseTypes';

export type PlannedModule={module_id:string;source_module_id:string;prototype_module_id:string;family:string;storage_family:string;world_pos:XYZ;position_world:XYZ;yaw_rad:number;outer_bounds_world:V3Bounds;operating_bounds_world:V3Bounds;is_new:boolean;zone_id:string};
export type PlannedHU={handling_unit_id:string;source_slot_id:string;target_module_id:string;target_slot_id:string;position_world:XYZ;yaw_rad:number};
export type PlannedSlot={slot_id:string;source_slot_id:string;module_id:string;prototype_module_id:string;family:string;bin_anchor_world:XYZ;usable_bounds_world:V3Bounds;usable_dimensions_xyz_m:XYZ;max_payload_kg:number;max_handling_units:number;reserve_only:boolean;retrieval_blocked:boolean;is_new:boolean;new_route_required:boolean};
export type PlannedZone={zone_id:string;family:string;source_zone_id:string;floor_bounds_xz_m:{min:[number,number];max:[number,number]}};
export type LayoutObstacle={id:string;kind:string;bounds:V3Bounds};
export type WarehouseLayoutPlan={schema_id:string;candidate_id:string;layout_version:string;source_kind:'visual_fixture';engine_operation:false;operational_admission:false;source_hashes:Record<string,string>;source_layout_content_hash:string;modules:PlannedModule[];HUs:PlannedHU[];slots:PlannedSlot[];zones:PlannedZone[];actor_homes:{actor_id:string;node_id:string;world_pos:XYZ;position_world:XYZ;source_node_id:string;module_id:string|null}[];fixed_obstacles:LayoutObstacle[];floor_bounds:V3Bounds;invariants:{HU_count:530;worker_count:24;ports:6;source_modules:132;added_racks_empty:true;scale_factor:1;physical_relocation_executed:false};summary:{module_count:number;added_modules:number;moved_source_modules:number;slot_count:number;rack_footprint_m2:number;source_rack_footprint_m2:number};routing:{source_graph_reuse_for_moved_or_added_modules:false;new_B_access_validation_required:true;forklift_and_LONG_movement_admitted:false};plan_sha256:string};
const turn=(p:XYZ,y:number):XYZ=>[Math.cos(y)*p[0]+Math.sin(y)*p[2],p[1],-Math.sin(y)*p[0]+Math.cos(y)*p[2]];
const add=(a:XYZ,b:XYZ)=>a.map((x,i)=>x+b[i]) as XYZ;
const rigid=(p:XYZ,from:WarehouseModule,to:{world_pos:XYZ;yaw_rad:number})=>from.yaw_rad===to.yaw_rad?p.map((x,i)=>x+(to.world_pos[i]-from.world_pos[i])) as XYZ:add(to.world_pos,turn(turn(p.map((x,i)=>x-from.world_pos[i]) as XYZ,-from.yaw_rad),to.yaw_rad));
function bounds(b:V3Bounds,from:WarehouseModule,to:{world_pos:XYZ;yaw_rad:number}):V3Bounds{if(from.yaw_rad===to.yaw_rad)return{min:rigid(b.min,from,to),max:rigid(b.max,from,to)};const p:XYZ[]=[];for(const x of [b.min[0],b.max[0]])for(const y of [b.min[1],b.max[1]])for(const z of [b.min[2],b.max[2]])p.push(rigid([x,y,z],from,to));return{min:[0,1,2].map(i=>Math.min(...p.map(v=>v[i]))) as XYZ,max:[0,1,2].map(i=>Math.max(...p.map(v=>v[i]))) as XYZ};}
const area=(b:V3Bounds)=>(b.max[0]-b.min[0])*(b.max[2]-b.min[2]);
const textHash=async(v:string)=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(v)))].map(v=>v.toString(16).padStart(2,'0')).join('');
const hash=(v:unknown)=>textHash(JSON.stringify(v));

/** New counterfactual B configuration, never an in-place edit of canonical A or an executed rack move. */
export async function createDenseWarehouseLayoutPlan(bundle:WarehouseBundle,texts:WarehouseTexts):Promise<WarehouseLayoutPlan>{
 return createWarehouseLayoutPlan(bundle,texts,'dense');
}

/** Rebuild whole picking/storage blocks; vehicle-rated stock retains its proven service frames. */
export async function createBlockRebuildWarehouseLayoutPlan(bundle:WarehouseBundle,texts:WarehouseTexts):Promise<WarehouseLayoutPlan>{
 return createWarehouseLayoutPlan(bundle,texts,'blocks');
}

async function createWarehouseLayoutPlan(bundle:WarehouseBundle,texts:WarehouseTexts,variant:'dense'|'blocks'):Promise<WarehouseLayoutPlan>{
 const accepted=await adaptWarehouseV3(texts);if(JSON.stringify(bundle)!==JSON.stringify(accepted))throw Error('LAYOUT_BUNDLE_SOURCE_MISMATCH');bundle=accepted;
 if(bundle.source_kind!=='visual_fixture'||bundle.engine_operation!==false||bundle.layout.modules.length!==132||bundle.fixture.inputs.initial_stock.length!==530||bundle.registry.workers.length!==24)throw Error('ORIGINAL_WAREHOUSE_LAYOUT_REQUIRED');
 const sourceModules=bundle.layout.modules,sourceById=new Map(sourceModules.map(m=>[m.module_id,m])),sourceSlots=bundle.layout.slots,sourceZones=bundle.layout.data.zones as {zone_id:string;floor_bounds_xz_m:{min:[number,number];max:[number,number]};kind:string}[],modules:PlannedModule[]=[],newCounts:Record<string,number>={};
 const rawSlots=new Map(decodeV3Table((bundle.layout.data.storage as Record<string,unknown>).slots).map(s=>[s.slot_id as string,s]));
 const smallCols=[14.1,17.1,18.6,21.6,23.1,26.1,27.6,30.6],smallRows=[43.3,45.8,48.3,50.8,53.3];
 function append(source:WarehouseModule,pos:XYZ,yaw=source.yaw_rad,is_new=false,zoneId?:string){const family=source.family,id=is_new?`v3:planned:B:module:${family}:${String(newCounts[family]=(newCounts[family]??0)+1).padStart(3,'0')}`:source.module_id,outer=bounds(source.outer_bounds_world,source,{world_pos:pos,yaw_rad:yaw}),operating=structuredClone(outer);if(family==='HEAVY')operating.max[1]=1.8;
  modules.push({module_id:id,source_module_id:source.module_id,prototype_module_id:source.module_id,family,storage_family:family,world_pos:[...pos],position_world:[...pos],yaw_rad:yaw,outer_bounds_world:outer,operating_bounds_world:operating,is_new,zone_id:zoneId??sourceZones[source.zone_index].zone_id});}
 if(variant==='dense'){
 for(const m of sourceModules){const zone=sourceZones[m.zone_index].zone_id,bank=zone.endsWith('_E')?'E':'W',offset=bank==='E'?100:0;let p:XYZ=[...m.world_pos];
  if(m.family==='SMALL'){const peers=sourceModules.filter(n=>n.family==='SMALL'&&sourceZones[n.zone_index].zone_id===zone),xs=[...new Set(peers.map(n=>n.world_pos[0]))].sort((a,b)=>a-b),zs=[...new Set(peers.map(n=>n.world_pos[2]))].sort((a,b)=>a-b);p=[smallCols[xs.indexOf(m.world_pos[0])]+offset,0,smallRows[[0,1,3,4][zs.indexOf(m.world_pos[2])]]];}
  append(m,p);
 }
 for(const bank of ['W','E']){const small=sourceModules.filter(m=>sourceZones[m.zone_index].zone_id==='SMALL_'+bank),offset=bank==='E'?100:0;
  for(let col=0;col<8;col++)for(let row=0;row<5;row++)if(col>=6||row===2){const yaw=col%2===0?Math.PI/2:3*Math.PI/2,prototype=small.find(m=>Math.abs(m.yaw_rad-yaw)<1e-8)!;append(prototype,[smallCols[col]+offset,0,smallRows[row]],yaw,true,'SMALL_'+bank);}
 }
 }else{
  // Moving rated cargo would invalidate its source vehicle service graph. Keep those
  // seven STANDARD frames and all HEAVY/LONG frames; rebuild the other 89 modules.
  const ratedModules=new Set(bundle.fixture.inputs.initial_stock.filter(h=>h.gross_mass_kg>15).map(h=>h.location.module_id));
  for(const m of sourceModules)if(['HEAVY','LONG'].includes(m.family)||ratedModules.has(m.module_id))append(m,[...m.world_pos],m.yaw_rad,false,m.family==='STANDARD'?sourceZones[m.zone_index].zone_id+'_SERVICE':undefined);
  for(const bank of ['W','E']){
   const inZone=(id:string)=>sourceModules.filter(m=>sourceZones[m.zone_index].zone_id===id+'_'+bank);
   const standard=inZone('STANDARD').filter(m=>!ratedModules.has(m.module_id)),reserve=inZone('RESERVE'),small=inZone('SMALL'),flex=inZone('FLEX'),offset=bank==='W'?0:100;
   // Three five-bay STANDARD rows turn 90 degrees into the former SMALL banks.
   // 4.8m pitch - 1.4m depth = 3.4m clear forklift aisles, all facing east.
   for(let col=0;col<3;col++)for(let row=0;row<5;row++){const i=col*5+row;append(standard[i]??standard[0],[14+offset+col*4.8,0,42+row*3],Math.PI/2,i>=standard.length,'STANDARD_'+bank);}
   for(let row=0;row<5;row++)append(reserve[row]??reserve[0],[28.4+offset,0,42+row*3],Math.PI/2,row>=reserve.length,'RESERVE_'+bank);
   let pick=0;
   // Four short picking islands by packing. Vehicle spines at 52/72/92m stay open,
   // along with an 8.3m cross-aisle between HEAVY and the rebuilt STANDARD rows.
   for(const start of bank==='W'?[37,57]:[77,97])for(let col=0;col<5;col++)append(small[pick++],[start+col*2.5,0,14.3],Math.PI,false,'SMALL_'+bank);
   // Consolidated north picking blocks: 3.5m pitch - 1m depth = 2.5m cart aisles.
   // The wall-side row faces inward; no slot needs the narrow space behind it.
   for(const z of [64,67.5,71])for(let col=0;col<(z===71?6:14);col++){const i=pick++;append(small[i]??small[0],[(bank==='W'?35:79.1)+col*2.5,0,z],z===64?0:Math.PI,i>=small.length,'SMALL_'+bank+'_NORTH');}
   // Both FLEX banks now form one adjacent pair in the north-west, beyond staging.
   for(let col=0;col<10;col++)append(flex[col]??flex[0],[14+col*2,0,bank==='W'?64:67.5],bank==='W'?0:Math.PI,col>=flex.length,'FLEX_'+bank);
  }
  const prototype=sourceModules.find(m=>sourceZones[m.zone_index].zone_id==='STANDARD_E')!;
  for(let col=0;col<5;col++)append(prototype,[115+col*3.4,0,64],0,true,'STANDARD_E_BUFFER');
 }
 const plannedById=new Map(modules.map(m=>[m.module_id,m])),slots:PlannedSlot[]=[];
 for(const m of modules){const source=sourceById.get(m.prototype_module_id)!;for(const s of sourceSlots.filter(s=>s.module_index===sourceModules.indexOf(source))){const id=m.is_new?`${m.module_id}:slot:${s.slot_id.split(':').slice(-2).join(':')}`:s.slot_id;slots.push({slot_id:id,source_slot_id:s.slot_id,module_id:m.module_id,prototype_module_id:source.module_id,family:m.family,bin_anchor_world:rigid(s.bin_anchor,source,m),usable_bounds_world:bounds(s.usable_bounds_world,source,m),usable_dimensions_xyz_m:[...s.usable_dimensions_xyz_m],max_payload_kg:s.max_payload_kg,max_handling_units:s.max_handling_units,reserve_only:s.reserve_only,retrieval_blocked:s.retrieval_blocked,is_new:m.is_new,new_route_required:m.is_new||m.world_pos.some((v,i)=>v!==source.world_pos[i])||m.yaw_rad!==source.yaw_rad});}}
 const HUs:PlannedHU[]=bundle.fixture.inputs.initial_stock.map(h=>{const s=sourceSlots.find(s=>s.slot_id===h.location.slot_id)!,source=sourceModules[s.module_index],m=plannedById.get(source.module_id)!,shift=s.usable_dimensions_xyz_m[2]/2-(rawSlots.get(s.slot_id)!.clearance_each_side_m as number)-h.dimensions_xyz_m[2]/2,p:XYZ=[s.bin_anchor[0]+Math.sin(source.yaw_rad)*shift,s.bin_anchor[1],s.bin_anchor[2]+Math.cos(source.yaw_rad)*shift];return{handling_unit_id:h.handling_unit_id,source_slot_id:s.slot_id,target_module_id:m.module_id,target_slot_id:s.slot_id,position_world:rigid(p,source,m),yaw_rad:m.yaw_rad};});
 const homes=staffingHomeNodes(bundle),pickerModules=['SMALL_W','SMALL_E'].flatMap(zone=>sourceModules.filter(m=>m.module_id.includes(':'+zone+':')).filter((_,i)=>i%4===0).slice(0,6));let pi=0;
 const actor_homes=bundle.registry.workers.map(w=>{const id=homes.get(w.actor_id)!,n=bundle.layout.walk.nodes.find(n=>n.node_id===id)??bundle.layout.vehicle.nodes.find(n=>n.node_id===id)!;let pos:XYZ=[...n.world_pos],module_id:string|null=null;if(w.baseline_role==='picker'){const source=pickerModules[pi++],m=plannedById.get(source.module_id)!,local=turn(n.world_pos.map((v,i)=>v-source.world_pos[i]) as XYZ,-source.yaw_rad);local[2]=1.5;pos=add(m.world_pos,turn(local,m.yaw_rad));module_id=m.module_id;}return{actor_id:w.actor_id,node_id:w.baseline_role==='picker'?'v3:planned:B:home:'+w.actor_id:id,source_node_id:id,world_pos:pos,position_world:[...pos] as XYZ,module_id};});
 const zones:PlannedZone[]=variant==='blocks'?[...new Set(modules.map(m=>m.zone_id))].map(id=>{
  const rows=modules.filter(m=>m.zone_id===id),family=rows[0].family,sourceId=id.split('_').slice(0,2).join('_'),source=sourceZones.find(z=>z.zone_id===sourceId)!;
  const floor=['HEAVY','LONG'].includes(family)?structuredClone(source.floor_bounds_xz_m):{min:[Math.min(...rows.map(m=>m.outer_bounds_world.min[0]))-.4,Math.min(...rows.map(m=>m.outer_bounds_world.min[2]))-.9] as [number,number],max:[Math.max(...rows.map(m=>m.outer_bounds_world.max[0]))+.4,Math.min(72,Math.max(...rows.map(m=>m.outer_bounds_world.max[2]))+.9)] as [number,number]};
  return{zone_id:id,family,source_zone_id:sourceId,floor_bounds_xz_m:floor};
 }):sourceZones.filter(z=>['SMALL_W','SMALL_E','STANDARD_W','STANDARD_E','HEAVY_W','HEAVY_E','LONG_W','LONG_E','FLEX_W','FLEX_E','RESERVE_W','RESERVE_E'].includes(z.zone_id)).map(z=>{const bank=z.zone_id.endsWith('_E')?'E':'W',offset=bank==='E'?100:0;let b=structuredClone(z.floor_bounds_xz_m);if(z.zone_id.startsWith('SMALL_'))b={min:[13.1+offset,42],max:[31.6+offset,55.2]};return{zone_id:z.zone_id,family:z.zone_id.split('_')[0],source_zone_id:z.zone_id,floor_bounds_xz_m:b};});
 const fixed_obstacles:LayoutObstacle[]=[];const conveyor=bundle.layout.data.conveyor as {physical_modules:{module_id:string;floor_bounds_xz:{min:[number,number];max:[number,number]}}[];packing_stations:{pack_id:string;table_origin:XYZ;table_dimensions_m:XYZ}[]};
 for(const c of conveyor.physical_modules){const b=c.floor_bounds_xz;fixed_obstacles.push({id:c.module_id,kind:'source_conveyor',bounds:{min:[b.min[0],0,b.min[1]],max:[b.max[0],8,b.max[1]]}});}for(const p of conveyor.packing_stations)fixed_obstacles.push({id:p.pack_id,kind:'source_packing',bounds:{min:[p.table_origin[0]-p.table_dimensions_m[0]/2,0,p.table_origin[2]-p.table_dimensions_m[2]/2],max:[p.table_origin[0]+p.table_dimensions_m[0]/2,p.table_dimensions_m[1],p.table_origin[2]+p.table_dimensions_m[2]/2]}});
 for(const z of sourceZones.filter(z=>z.kind==='staging'))fixed_obstacles.push({id:z.zone_id,kind:'source_staging_reservation',bounds:{min:[z.floor_bounds_xz_m.min[0],0,z.floor_bounds_xz_m.min[1]],max:[z.floor_bounds_xz_m.max[0],8,z.floor_bounds_xz_m.max[1]]}});for(const[id,x]of [['FL01',6],['FL02',138]] as const)fixed_obstacles.push({id,kind:'source_parked_forklift_with_margin',bounds:{min:[x-1.75,0,17.15],max:[x+1.75,2.35,18.85]}});
 const partial:Omit<WarehouseLayoutPlan,'plan_sha256'>={schema_id:'qoima.planned-warehouse-layout.v1',candidate_id:variant==='blocks'?'v3:layout-plan:block-rebuild:001':'v3:layout-plan:dense-manual:001',layout_version:variant==='blocks'?'qoima-144x72-v3-planned-block-rebuild-1':'qoima-144x72-v3-planned-dense-manual-2',source_kind:'visual_fixture',engine_operation:false,operational_admission:false,source_hashes:{'frontend/public/data/v3/warehouse-fixture-v3.json':await textHash(texts.fixture),[bundle.fixture.layout_ref.path]:bundle.fixture.layout_ref.sha256,[bundle.fixture.registry_ref.path]:bundle.fixture.registry_ref.sha256,[bundle.fixture.profiles_ref.path]:bundle.fixture.profiles_ref.sha256},source_layout_content_hash:bundle.layout.layout_content_hash,modules,HUs,slots,zones,actor_homes,fixed_obstacles,floor_bounds:{min:[0,0,0],max:[144,8,72]},invariants:{HU_count:530,worker_count:24,ports:6,source_modules:132,added_racks_empty:true,scale_factor:1,physical_relocation_executed:false},summary:{module_count:modules.length,added_modules:modules.filter(m=>m.is_new).length,moved_source_modules:modules.filter(m=>!m.is_new&&m.world_pos.some((v,i)=>v!==sourceById.get(m.module_id)!.world_pos[i])).length,slot_count:slots.length,rack_footprint_m2:modules.reduce((s,m)=>s+area(m.outer_bounds_world),0),source_rack_footprint_m2:sourceModules.reduce((s,m)=>s+area(m.outer_bounds_world),0)},routing:{source_graph_reuse_for_moved_or_added_modules:false,new_B_access_validation_required:true,forklift_and_LONG_movement_admitted:false}};
 return{...partial,plan_sha256:await hash(partial)};
}
