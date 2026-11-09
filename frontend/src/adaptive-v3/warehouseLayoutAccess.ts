import type {WarehouseBundle,V3Bounds,XYZ} from './warehouseTypes';

type Module={module_id:string;source_module_id?:string;prototype_module_id:string;family:string;world_pos?:XYZ;position_world?:XYZ;yaw_rad:number;outer_bounds_world:V3Bounds;operating_bounds_world?:V3Bounds};
type Plan={candidate_id:string;layout_version:string;plan_sha256:string;source_kind:string;engine_operation:boolean;operational_admission:boolean;source_layout_content_hash:string;source_hashes:Record<string,string>;modules:Module[];fixed_obstacles:{id:string;kind:string;bounds:V3Bounds}[];actor_homes?:{actor_id?:string;position_world?:XYZ;world_pos?:XYZ}[]};
type Mode='pedestrian'|'manual_cart';
type Box={id:string;kind:string;bounds:V3Bounds};
type Endpoint={node_id:string;position_world:XYZ;kind:string;module_id?:string;source_node_id?:string};
export type WarehouseLayoutAccessResult={
 source_kind:'visual_fixture';engine_operation:false;operational_admission:false;candidate_id:string;layout_version:string;plan_sha256:string;
 ok:boolean;reasons:string[];geometry_basis:'B_obstacle_conservative_envelopes';manual:Record<Mode,{ok:boolean;radius_m:number;node_count:number;component_count:number;endpoints:Endpoint[];unreachable:Endpoint[]}>;
 unavailable_shared_service_frames:Endpoint[];
 vehicle:{ok:boolean;profiles:{profile_id:string;rechecked_source_arc_ids:string[];blocked_source_arc_ids:string[];unvalidated_source_arc_ids:string[]}[];required_service_access:{handling_unit_id:string;module_id:string;node_id:string|null;geometry_reachable:boolean;reason:string;inbound_reachable_port_ids:string[];outbound_reachable_port_ids:string[]}[];endpoint_source_frames_unchanged:boolean;actual_action_admission_required:true;dynamic_reservations_required:true};
 route(query:{mode:Mode;from_node_id:string;to_node_id:string;layout_version:string;plan_sha256:string}):{ok:boolean;reason:string;points_world:XYZ[];length_m:number|null};
};
const MARGIN=1e-4; // Additional conservative clearance, not a native contact tolerance.
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const vector=(v:unknown):v is XYZ=>Array.isArray(v)&&v.length===3&&v.every(finite);
function requireValue(value:unknown,reason:string):asserts value{if(!value)throw Error(reason);}
function bound(value:V3Bounds){requireValue(value&&vector(value.min)&&vector(value.max)&&value.min.every((n,i)=>n<=value.max[i]),'INVALID_B_OBSTACLE');return value;}
function world(p:XYZ,origin:XYZ,yaw:number):XYZ{const c=Math.cos(yaw),s=Math.sin(yaw);return[origin[0]+c*p[0]+s*p[2],origin[1]+p[1],origin[2]-s*p[0]+c*p[2]];}
function local(p:XYZ,origin:XYZ,yaw:number):XYZ{return world([p[0]-origin[0],p[1]-origin[1],p[2]-origin[2]],[0,0,0],-yaw);}
function movedBounds(b:V3Bounds,old:XYZ,oldYaw:number,now:XYZ,yaw:number):V3Bounds{
 const points:XYZ[]=[];for(const x of[b.min[0],b.max[0]])for(const y of[b.min[1],b.max[1]])for(const z of[b.min[2],b.max[2]])points.push(world(local([x,y,z],old,oldYaw),now,yaw));
 return{min:[0,1,2].map(i=>Math.min(...points.map(p=>p[i]))) as XYZ,max:[0,1,2].map(i=>Math.max(...points.map(p=>p[i]))) as XYZ};
}
const close=(a:number[],b:number[])=>a.length===b.length&&a.every((x,i)=>Math.abs(x-b[i])<1e-7);
function lower(a:number[],x:number){let l=0,h=a.length;while(l<h){const m=(l+h)>>>1;if(a[m]<x)l=m+1;else h=m;}return l;}
function upper(a:number[],x:number){let l=0,h=a.length;while(l<h){const m=(l+h)>>>1;if(a[m]<=x)l=m+1;else h=m;}return l;}
function unique(a:number[]){return [...new Set(a)].sort((x,y)=>x-y);}

/** Exact rectilinear subdivision of conservative expanded obstacles. Obstacle boundaries
 * are grid axes, so two adjacent free vertices cannot skip a thin obstacle. No A arc is used. */
function manualGraph(boxes:Box[],endpoints:Endpoint[],radius:number){
 const min=radius+MARGIN,maxX=144-min,maxZ=72-min;
 const rects=boxes.map(b=>[b.bounds.min[0]-radius-MARGIN,b.bounds.max[0]+radius+MARGIN,b.bounds.min[2]-radius-MARGIN,b.bounds.max[2]+radius+MARGIN]);
 const xv=[min,maxX],zv=[min,maxZ];
 for(const r of rects){for(const x of[r[0]-MARGIN,r[0],r[1],r[1]+MARGIN])if(x>=min&&x<=maxX)xv.push(x);for(const z of[r[2]-MARGIN,r[2],r[3],r[3]+MARGIN])if(z>=min&&z<=maxZ)zv.push(z);}
 for(const e of endpoints){if(e.position_world[0]>=min&&e.position_world[0]<=maxX)xv.push(e.position_world[0]);if(e.position_world[2]>=min&&e.position_world[2]<=maxZ)zv.push(e.position_world[2]);}
 const xs=unique(xv),zs=unique(zv),nx=xs.length,nz=zs.length,size=nx*nz,stride=nx+1;
 requireValue(size<=2_000_000,'B_NAV_SUBDIVISION_LIMIT');
 const diff=new Int32Array((nx+1)*(nz+1));
 for(const r of rects){const a=lower(xs,r[0]),b=upper(xs,r[1]),c=lower(zs,r[2]),d=upper(zs,r[3]);if(a>=b||c>=d)continue;diff[c*stride+a]++;diff[c*stride+b]--;diff[d*stride+a]--;diff[d*stride+b]++;}
 const component=new Int32Array(size);component.fill(-1);
 for(let z=0;z<nz;z++)for(let x=0;x<nx;x++){const i=z*stride+x;diff[i]+=(x?diff[i-1]:0)+(z?diff[i-stride]:0)-(x&&z?diff[i-stride-1]:0);if(diff[i]>0)component[z*nx+x]=-2;}
 const q=new Int32Array(size);let count=0;
 for(let start=0;start<size;start++){if(component[start]!==-1)continue;let head=0,tail=1;q[0]=start;component[start]=count;while(head<tail){const i=q[head++],x=i%nx,z=(i/nx)|0;for(const n of[x?i-1:-1,x+1<nx?i+1:-1,z?i-nx:-1,z+1<nz?i+nx:-1])if(n>=0&&component[n]===-1){component[n]=count;q[tail++]=n;}}count++;}
 const indices=new Map(endpoints.map(e=>{const x=lower(xs,e.position_world[0]),z=lower(zs,e.position_world[2]);return[e.node_id,x<nx&&z<nz&&xs[x]===e.position_world[0]&&zs[z]===e.position_world[2]?z*nx+x:-1];}));
 const anchor=endpoints.find(e=>e.kind==='port'),anchorIndex=anchor?indices.get(anchor.node_id)!:-1,anchorComponent=anchorIndex>=0?component[anchorIndex]:-2;
 const unreachable=endpoints.filter(e=>{const i=indices.get(e.node_id)!;return i<0||anchorComponent<0||component[i]!==anchorComponent;});
 function route(from:string,to:string){
  const a=indices.get(from),b=indices.get(to);if(a===undefined||b===undefined)return{ok:false,reason:'UNKNOWN_B_NODE',points_world:[],length_m:null};
  if(a<0||b<0||component[a]<0||component[a]!==component[b])return{ok:false,reason:'NO_B_PATH',points_world:[],length_m:null};
  const previous=new Int32Array(size);previous.fill(-1);let head=0,tail=1;q[0]=a;previous[a]=a;
  while(head<tail&&previous[b]===-1){const i=q[head++],x=i%nx,z=(i/nx)|0;for(const n of[x?i-1:-1,x+1<nx?i+1:-1,z?i-nx:-1,z+1<nz?i+nx:-1])if(n>=0&&component[n]===component[a]&&previous[n]===-1){previous[n]=i;q[tail++]=n;}}
  const ids=[b];while(ids[ids.length-1]!==a)ids.push(previous[ids[ids.length-1]]);ids.reverse();
  const points:XYZ[]=[];for(const i of ids){const p:XYZ=[xs[i%nx],0,zs[(i/nx)|0]];if(points.length>=2){const v=points[points.length-2],w=points[points.length-1];if(v[0]===w[0]&&w[0]===p[0]||v[2]===w[2]&&w[2]===p[2]){points[points.length-1]=p;continue;}}points.push(p);}
  let length=0;for(let i=1;i<points.length;i++)length+=Math.hypot(points[i][0]-points[i-1][0],points[i][2]-points[i-1][2]);
  return{ok:true,reason:'B_GEOMETRY_PATH_ONLY',points_world:points,length_m:length};
 }
 return{ok:unreachable.length===0,radius_m:radius,node_count:size,component_count:count,endpoints,unreachable,route};
}

function trig(a:number,b:number,start:number,end:number){const lo=Math.min(start,end),hi=Math.max(start,end),points=[lo,hi],phase=Math.atan2(b,a);for(let k=Math.floor((lo-phase)/Math.PI)-1;k<=Math.ceil((hi-phase)/Math.PI)+1;k++){const t=phase+k*Math.PI;if(t>=lo&&t<=hi)points.push(t);}const values=points.map(t=>a*Math.cos(t)+b*Math.sin(t));return[Math.min(...values),Math.max(...values)];}
type Geometry={kind:string;start_yaw_rad:number;end_yaw_rad:number;icr_world_xz_m?:number[];icr_vehicle_local_x_m?:number};
function sweep(g:Geometry,a:XYZ,b:XYZ,component:V3Bounds,lo:number,hi:number,pad:number){
 const xs:number[]=[],zs:number[]=[];
 for(const x of[component.min[0],component.max[0]])for(const z of[component.min[2],component.max[2]]){
  if(g.kind==='line'){for(const u of[lo,hi]){const p=world([x,0,z],[a[0]+(b[0]-a[0])*u,0,a[2]+(b[2]-a[2])*u],g.start_yaw_rad);xs.push(p[0]);zs.push(p[2]);}}
  else{const [cx,cz]=g.icr_world_xz_m!,r=g.icr_vehicle_local_x_m!,dy=g.end_yaw_rad-g.start_yaw_rad,s=g.start_yaw_rad+dy*lo,e=g.start_yaw_rad+dy*hi;xs.push(...trig(x-r,z-.4,s,e).map(v=>cx+v));zs.push(...trig(z-.4,-(x-r),s,e).map(v=>cz+v));}
 }
 return[Math.min(...xs)-pad,Math.max(...xs)+pad,Math.min(...zs)-pad,Math.max(...zs)+pad];
}
function separated(a:number[],b:V3Bounds){return a[1]<b.min[0]||a[0]>b.max[0]||a[3]<b.min[2]||a[2]>b.max[2];}

/** Fresh B clearance guard. Success establishes static conservative geometry only;
 * it never grants handling, C08 eligibility, occupancy reservations or engine execution. */
export async function validateWarehouseLayoutPlanAccess(bundle:WarehouseBundle,input:Plan):Promise<WarehouseLayoutAccessResult>{
 requireValue(input&&typeof input.candidate_id==='string'&&typeof input.layout_version==='string'&&typeof input.plan_sha256==='string'&&input.plan_sha256.length===64,'INVALID_B_LAYOUT_ID');
 const plan=structuredClone(input),{plan_sha256:claimed,...payload}=plan;
 const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(payload))))].map(v=>v.toString(16).padStart(2,'0')).join('');
 requireValue(digest===claimed,'B_PLAN_HASH_MISMATCH');
 requireValue(plan.source_kind==='visual_fixture'&&plan.engine_operation===false&&plan.operational_admission===false&&plan.source_layout_content_hash===bundle.layout.layout_content_hash,'B_SOURCE_LAYOUT_MISMATCH');
 for(const [p,h]of Object.entries({'frontend/public/data/adaptive-v3/layout-manifest.json':bundle.fixture.layout_ref.sha256,'frontend/public/data/v3/worker-registry-v3.json':bundle.fixture.registry_ref.sha256,'frontend/public/data/v3/worker-profiles-v3.json':bundle.fixture.profiles_ref.sha256}))requireValue(plan.source_hashes[p]===h,'B_SOURCE_PIN_MISMATCH:'+p);
 const sources=new Map(bundle.layout.modules.map(m=>[m.module_id,m])),boxes:Box[]=[],reasons:string[]=[];
 const moduleIds=new Set<string>();let heavyUnchanged=true;
 for(const m of plan.modules){
  const source=sources.get(m.prototype_module_id||m.source_module_id||m.module_id),p=m.position_world||m.world_pos;
  requireValue(source&&vector(p)&&finite(m.yaw_rad)&&!moduleIds.has(m.module_id)&&source.family===m.family,'INVALID_B_MODULE');moduleIds.add(m.module_id);
  requireValue(Math.abs(Math.sin(m.yaw_rad*2))<1e-8,'NON_CARDINAL_B_MODULE');
  const expected=movedBounds(source.outer_bounds_world,source.world_pos,source.yaw_rad,p,m.yaw_rad),actual=bound(m.outer_bounds_world);
  requireValue(close(expected.min,actual.min)&&close(expected.max,actual.max),'B_MODULE_BOUNDS_MISMATCH:'+m.module_id);
  const outer=bound(m.operating_bounds_world||actual);requireValue(outer.min.every((n,i)=>n<=actual.min[i]+1e-7)&&outer.max.every((n,i)=>n>=actual.max[i]-1e-7),'B_OPERATING_BOUNDS_SHRUNK');
  requireValue(outer.min[0]>=0&&outer.max[0]<=144&&outer.min[2]>=0&&outer.max[2]<=72,'B_MODULE_OUTSIDE_FLOOR');boxes.push({id:m.module_id,kind:'storage',bounds:outer});
  if(['HEAVY','LONG'].includes(m.family)&&(!sources.has(m.module_id)||!close(p,sources.get(m.module_id)!.world_pos)||Math.abs(Math.sin((m.yaw_rad-sources.get(m.module_id)!.yaw_rad)/2))>1e-8))heavyUnchanged=false;
 }
 requireValue(bundle.layout.modules.every(m=>moduleIds.has(m.module_id)),'SOURCE_B_MODULE_OMITTED');
 for(const o of plan.fixed_obstacles){requireValue(typeof o.id==='string'&&typeof o.kind==='string','INVALID_FIXED_OBSTACLE');boxes.push({id:o.id,kind:o.kind,bounds:bound(o.bounds)});}
 // Fixed conveyor/table coverage comes from the original source bundle, not a caller flag.
 const conveyor=bundle.layout.data.conveyor as {physical_modules?:{module_id:string;floor_bounds_xz:{min:number[];max:number[]}}[];packing_stations?:{pack_id:string;table_origin:XYZ;table_dimensions_m:XYZ}[]};
 for(const o of conveyor.physical_modules||[]){const b=o.floor_bounds_xz;boxes.push({id:'source:'+o.module_id,kind:'conveyor',bounds:{min:[b.min[0],0,b.min[1]],max:[b.max[0],8,b.max[1]]}});}
 for(const o of conveyor.packing_stations||[]){const p=o.table_origin,d=o.table_dimensions_m;boxes.push({id:'source:'+o.pack_id,kind:'packing',bounds:{min:[p[0]-d[0]/2,0,p[2]-d[2]/2],max:[p[0]+d[0]/2,d[1],p[2]+d[2]/2]}});}
 const endpoints:Record<Mode,Endpoint[]>={pedestrian:[],manual_cart:[]},unavailable:Endpoint[]=[];
 const manualCargo=new Set(bundle.fixture.inputs.archetypes.filter(a=>(a.handling_unit as {gross_mass_kg:number}).gross_mass_kg<=15).map(a=>a.archetype_id));
 const manualPorts=new Set((bundle.layout.data.ports as {port_id:string;allowed_cargo_archetype_ids:string[]}[]).filter(p=>p.allowed_cargo_archetype_ids.some(id=>manualCargo.has(id))).map(p=>p.port_id));
 for(const mode of['pedestrian','manual_cart'] as Mode[]){
  for(const n of bundle.layout.walk.nodes){const type=n.attributes.node_type,allowed=n.attributes.allowed_modes as string[]|undefined;if((type==='port_service'||type===(mode==='manual_cart'?'packing_cart_stop':'packing_pedestrian_service'))&&(!allowed||allowed.includes(mode))){const e={node_id:`${plan.layout_version}:${mode}:${n.node_id}`,position_world:[...n.world_pos] as XYZ,kind:type==='port_service'?'port':'packing',source_node_id:n.node_id};if(type==='port_service'&&!manualPorts.has(n.attributes.port_id as string)){unavailable.push(e);continue;}endpoints[mode].push(e);}}
  for(const m of plan.modules){if(!['SMALL','STANDARD','FLEX'].includes(m.family))continue;const source=sources.get(m.prototype_module_id||m.source_module_id||m.module_id)!,index=bundle.layout.modules.indexOf(source),seen=new Set<number>();
   for(const slot of bundle.layout.slots){if(slot.module_index!==index||slot.retrieval_blocked||slot.reserve_only)continue;const ni=mode==='pedestrian'?slot.worker_node_index:slot.cart_stop_node_index;if(seen.has(ni))continue;seen.add(ni);const n=bundle.layout.walk.nodes[ni],p=local(n.world_pos,source.world_pos,source.yaw_rad);
    // B's 2m opposing aisles require a new centre stop, not A's deeper cart offset.
    const bb=movedBounds(source.outer_bounds_world,source.world_pos,source.yaw_rad,[0,0,0],0);
    p[2]=bb.max[2]+(mode==='manual_cart'?1:.45);
    const pos=world(p,m.position_world||m.world_pos!,m.yaw_rad);endpoints[mode].push({node_id:`${plan.layout_version}:${mode}:${m.module_id}:${ni}`,position_world:pos,kind:'storage_service',module_id:m.module_id,source_node_id:n.node_id});
   }
  }
 }
 const drivers=new Set(bundle.registry.workers.filter(w=>w.assigned_vehicle_id!==null).map(w=>w.actor_id));
 for(const home of plan.actor_homes||[]){const p=home.position_world||home.world_pos;if(p&&vector(p)){const e={node_id:`${plan.layout_version}:home:${home.actor_id}`,position_world:p,kind:'actor_home'};if(drivers.has(home.actor_id!))unavailable.push(e);else endpoints.pedestrian.push(e);}}
 const profiles=bundle.layout.data.storage as {access_profiles:{pedestrian:{radius_m:number};manual_cart:{radius_m:number};[key:string]:unknown}};
 requireValue(profiles.access_profiles.pedestrian.radius_m===.35&&profiles.access_profiles.manual_cart.radius_m===.95,'SOURCE_MANUAL_ENVELOPE_CHANGED');
 // The native original resting worker is wider than the old .35m policy capsule:
 // bbox X±.373024, Z[-.16,.22] fits a .434m circle. .44m encloses that rest shape
 // for arbitrary root yaw. Loaded carrying / joint animation need their own action proof.
 const graphs={pedestrian:manualGraph(boxes,endpoints.pedestrian,.44),manual_cart:manualGraph(boxes,endpoints.manual_cart,.95)};
 for(const mode of['pedestrian','manual_cart'] as Mode[])if(!graphs[mode].ok)reasons.push(`B_${mode.toUpperCase()}_ACCESS_BLOCKED`);
 const definitions={...profiles.access_profiles,unloaded_bare:{component_bounds_local_m:[(bundle.layout.data.vehicle_geometry as {blueprint:{bounds_local_m:V3Bounds}}).blueprint.bounds_local_m],padding_m:.25}} as Record<string,{component_bounds_local_m?:V3Bounds[];padding_m?:number}>;
 const vehicleProfiles=[];
 const movedModuleIds=new Set(plan.modules.filter(m=>{const s=sources.get(m.module_id);return s&&(!close(m.position_world||m.world_pos!,s.world_pos)||Math.abs(Math.sin((m.yaw_rad-s.yaw_rad)/2))>1e-8);}).map(m=>m.module_id));
 for(const profileId of['unloaded_bare','nonlong_forklift','long_loaded']){
  const verified:string[]=[],blocked:string[]=[],unvalidated:string[]=[],definition=definitions[profileId],components=definition?.component_bounds_local_m;
  for(const arc of bundle.layout.vehicle.arcs){
   const sourceRef=arc.fields.source_ref as {source_id?:string}|undefined;
   if(sourceRef?.source_id&&[...movedModuleIds].some(id=>sourceRef.source_id!.startsWith(id+':'))){unvalidated.push(arc.arc_id);continue;}
   const allowed=arc.fields.allowed_geometry_profile_ids as string[],wanted=profileId==='long_loaded'?['long_loaded','loaded_max']:profileId==='unloaded_bare'?['unloaded_bare','nonlong_forklift','long_loaded','loaded_max']:[profileId,'loaded_max'];
   if(!components||!Array.isArray(allowed)||!allowed.some(v=>wanted.includes(v))){unvalidated.push(arc.arc_id);continue;}
   const g=arc.fields.geometry as unknown as Geometry,a=bundle.layout.vehicle.nodes[arc.from_node_index].world_pos,b=bundle.layout.vehicle.nodes[arc.to_node_index].world_pos;
   if(!g||!['line','rear_steer_arc'].includes(g.kind)||![g.start_yaw_rad,g.end_yaw_rad].every(finite)||g.kind==='line'&&Math.abs(g.start_yaw_rad-g.end_yaw_rad)>1e-9||g.kind==='rear_steer_arc'&&(!g.icr_world_xz_m?.every(finite)||!finite(g.icr_vehicle_local_x_m))){unvalidated.push(arc.arc_id);continue;}
   // Other moving/parked actors need resource reservations, not a static map edit.
   const obstacles=boxes.filter(o=>!/(parked|vehicle|forklift)/i.test(o.kind));
   const clear=(lo:number,hi:number,depth:number):boolean=>components.every(c=>{const s=sweep(g,a,b,c,lo,hi,.25+MARGIN),nearby=obstacles.filter(o=>!separated(s,o.bounds));if(s[0]<0||s[1]>144||s[2]<0||s[3]>72)return false;if(!nearby.length)return true;if(depth>=7)return false;const mid=(lo+hi)/2;return clearComponent(c,lo,mid,depth+1,nearby)&&clearComponent(c,mid,hi,depth+1,nearby);});
   const clearComponent=(c:V3Bounds,lo:number,hi:number,depth:number,obs:Box[]):boolean=>{const s=sweep(g,a,b,c,lo,hi,.25+MARGIN),nearby=obs.filter(o=>!separated(s,o.bounds));if(!nearby.length)return true;if(depth>=7)return false;const mid=(lo+hi)/2;return clearComponent(c,lo,mid,depth+1,nearby)&&clearComponent(c,mid,hi,depth+1,nearby);};
   (clear(0,1,0)?verified:blocked).push(arc.arc_id);
  }
  vehicleProfiles.push({profile_id:profileId,rechecked_source_arc_ids:verified,blocked_source_arc_ids:blocked,unvalidated_source_arc_ids:unvalidated});
 }
 if(!heavyUnchanged)reasons.push('B_HEAVY_LONG_SERVICE_FRAMES_CHANGED');
 const required=[];
 for(const hu of bundle.fixture.inputs.initial_stock.filter(h=>h.gross_mass_kg>15)){
  const slot=bundle.layout.slots.find(s=>s.slot_id===hu.location.slot_id),ni=slot?.vehicle_node_index??null,nodeId=ni===null?null:bundle.layout.vehicle.nodes[ni].node_id;
  let reachable=false,reason='SOURCE_SERVICE_FRAME_MOVED';const inbound:string[]=[],outbound:string[]=[];
  if(!movedModuleIds.has(hu.location.module_id)&&ni!==null){
   const profileId=hu.archetype_id==='LONG_BUNDLE'?'long_loaded':'nonlong_forklift',ids=new Set(vehicleProfiles.find(p=>p.profile_id===profileId)!.rechecked_source_arc_ids),graph=bundle.layout.vehicle;
   const ports=(bundle.layout.data.ports as {port_id:string;direction:string;allowed_cargo_archetype_ids:string[];service_node_id:string}[]).filter(p=>p.allowed_cargo_archetype_ids.includes(hu.archetype_id));
   const adjacency=graph.nodes.map(()=>[] as number[]),reverse=graph.nodes.map(()=>[] as number[]);
   for(const a of graph.arcs)if(ids.has(a.arc_id)&&(a.fields.allowed_cargo_archetype_ids as string[]||[]).includes(hu.archetype_id)){adjacency[a.from_node_index].push(a.to_node_index);reverse[a.to_node_index].push(a.from_node_index);}
   const visit=(start:number,edges:number[][])=>{const seen=new Set([start]),queue=[start];for(let i=0;i<queue.length;i++)for(const n of edges[queue[i]])if(!seen.has(n)){seen.add(n);queue.push(n);}return seen;};
   const forward=visit(ni,adjacency),back=visit(ni,reverse);
   for(const p of ports){const i=graph.nodes.findIndex(n=>n.node_id===p.service_node_id);if(i<0)continue;if(p.direction==='inbound'&&back.has(i))inbound.push(p.port_id);if(p.direction==='outbound'&&forward.has(i))outbound.push(p.port_id);}
   reachable=inbound.length>0&&outbound.length>0;reason=reachable?'PRESERVED_SERVICE_GEOMETRY_RECHECKED':'B_VEHICLE_SERVICE_PATH_BLOCKED';
  }
  required.push({handling_unit_id:hu.handling_unit_id,module_id:hu.location.module_id,node_id:nodeId,geometry_reachable:reachable,reason,inbound_reachable_port_ids:inbound,outbound_reachable_port_ids:outbound});
 }
 if(required.some(r=>!r.geometry_reachable))reasons.push('B_REQUIRED_HEAVY_CARGO_ACCESS_UNPROVEN');
 const base={source_kind:'visual_fixture' as const,engine_operation:false as const,operational_admission:false as const,candidate_id:plan.candidate_id,layout_version:plan.layout_version,plan_sha256:plan.plan_sha256};
 return{...base,ok:reasons.length===0,reasons,geometry_basis:'B_obstacle_conservative_envelopes',manual:graphs,unavailable_shared_service_frames:unavailable,vehicle:{ok:heavyUnchanged&&required.every(r=>r.geometry_reachable),profiles:vehicleProfiles,required_service_access:required,endpoint_source_frames_unchanged:heavyUnchanged,actual_action_admission_required:true,dynamic_reservations_required:true},route(query){if(query.layout_version!==plan.layout_version||query.plan_sha256!==plan.plan_sha256)return{ok:false,reason:'B_LAYOUT_VERSION_MISMATCH',points_world:[],length_m:null};if(query.mode!=='pedestrian'&&query.mode!=='manual_cart')return{ok:false,reason:'UNADMITTED_B_MODE',points_world:[],length_m:null};return graphs[query.mode].route(query.from_node_id,query.to_node_id);}};
}
