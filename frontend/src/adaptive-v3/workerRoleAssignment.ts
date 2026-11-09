import type {WorkerRole} from './workerRoles';
import type {WarehouseBundle,XYZ} from './warehouseTypes';
import type {RoutePlan,RouteQuery} from './warehouseRouting';

/** Explicit synthetic staffing episode. It changes no stock, skills, jobs or scene objects. */
export const STAFFING_DURATION_S=600;
export const STAFFING_BREAK={from_s:30,to_s:600,actor_ids:['K05','K06']} as const;
export type RoleAssignmentRequest={event_id:string;actor_id:string;target_role:WorkerRole;station_id:string;at_s:number;until_s:number;handoff_s:number};
export type AssignmentReason='ASSIGNMENT_OK'|'INVALID_REQUEST'|'UNKNOWN_WORKER'|'ROLE_NOT_ELIGIBLE'|'EQUIPMENT_NOT_ALLOWED'|'VEHICLE_ASSIGNMENT_LOCKED'|'WORKER_ON_BREAK'|'STATION_UNAVAILABLE'|'ASSIGNMENT_CONFLICT'|'HANDOFF_REQUIRED'|'NO_PATH'|'UNSUPPORTED_ROUTE_GEOMETRY'|'ASSIGNMENT_TOO_SHORT'|'RETURN_OUTSIDE_EPISODE'|'BUSY'|'CANCELLED';
type Path={arc_ids:string[];points:XYZ[];length_m:number;duration_s:number};
export type RoleAssignmentPlan={request:RoleAssignmentRequest;from_node_id:string;to_node_id:string;departure_s:number;arrival_s:number;return_arrival_s:number;outbound:Path;return_path:Path;retained_task:{task_id:string;remaining_work_s:number}|null};
export type AssignmentResult={ok:boolean;reason:AssignmentReason;cost_evaluated:boolean;plan:RoleAssignmentPlan|null;source_kind:'visual_fixture';engine_operation:false};
export type StaffingWorker={actor_id:string;baseline_role:WorkerRole;effective_role:WorkerRole;phase:'baseline'|'break'|'handoff'|'walking'|'assigned'|'returning'|'restored';available:boolean;planned_position_m:XYZ;station_id:string|null;retained_task:{task_id:string;remaining_work_s:number;state:'retained'|'paused'}|null};
const digest=async(v:unknown)=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(v))))].map(x=>x.toString(16).padStart(2,'0')).join('');
const overlap=(a:number,b:number,c:number,d:number)=>a<d&&c<b;
function freeze<T>(v:T):T{if(v&&typeof v==='object'){for(const x of Object.values(v))freeze(x);Object.freeze(v);}return v;}

/** Same home-node construction used by the source warehouse scene. No nearest-node fallback. */
export function staffingHomeNodes(bundle:WarehouseBundle){
 const homes=new Map<string,string>(),modules=['SMALL_W','SMALL_E'].flatMap(zone=>bundle.layout.modules.filter(m=>m.module_id.includes(':'+zone+':')).filter((_,i)=>i%4===0).slice(0,6));let i=0;
 const service:Record<string,string>={R01:'IN_N_STANDARD',R02:'IN_E_PARCEL',S01:'OUT_W_RETAIL',S02:'OUT_S_EXPRESS',F01:'IN_W_BULK',F02:'OUT_E_B2B'};
 for(const w of bundle.registry.workers){let id='v3:service:'+service[w.actor_id];if(w.baseline_role==='packer')id='v3:service:PK'+w.actor_id.slice(1);if(w.baseline_role==='picker'){const m=modules[i++],slot=bundle.layout.slots.find(s=>bundle.layout.modules[s.module_index]===m);if(!slot)throw Error('STAFF_HOME_MISSING');id=bundle.layout.walk.nodes[slot.worker_node_index].node_id;}homes.set(w.actor_id,id);}
 return homes;
}

/** Safe RoleAssignment + absolute A/B replay. Route is the existing validated pedestrian router. */
export async function createStaffingComparison(bundle:WarehouseBundle,route:(q:RouteQuery)=>RoutePlan){
 if(bundle.source_kind!=='visual_fixture'||bundle.engine_operation!==false||bundle.registry.workers.length!==24||new Set(bundle.registry.workers.map(w=>w.actor_id)).size!==24)throw Error('EXACT_VISUAL_STAFF_REQUIRED');
 const homes=staffingHomeNodes(bundle),nodes=new Map(bundle.layout.walk.nodes.map(n=>[n.node_id,n])),arcs=new Map(bundle.layout.walk.arcs.map(a=>[a.arc_id,a]));
 const baselineAllocation=bundle.registry.workers.map(w=>({actor_id:w.actor_id,role:w.initial_role,home_node_id:homes.get(w.actor_id)}));
 const baselineHash=await digest(baselineAllocation),businessHash=await digest({inputs:bundle.fixture.inputs,profiles:bundle.profiles.profiles,common_break_calendar:STAFFING_BREAK,common_retained_tasks:[{actor_id:'P01',task_id:'fixture:retained-picker-work:P01',remaining_work_s:120},{actor_id:'P02',task_id:'fixture:retained-picker-work:P02',remaining_work_s:120}]});let allocationHash=baselineHash,plans:RoleAssignmentPlan[]=[],revision=0,pending=false;
 const pendingTask=(id:string)=>['P01','P02'].includes(id)?{task_id:'fixture:retained-picker-work:'+id,remaining_work_s:120}:null;
 const result=(ok:boolean,reason:AssignmentReason,plan:RoleAssignmentPlan|null=null):AssignmentResult=>freeze({ok,reason,cost_evaluated:ok,plan,source_kind:'visual_fixture',engine_operation:false});
 function pathFor(actor:string,from:string,to:string,speed:number):Path|null{
  const r=route({source_kind:'visual_fixture',engine_operation:false,mode:'pedestrian',actor_id:actor,vehicle_id:null,cargo_archetype_id:null,from_node_id:from,to_node_id:to,service_port_id:null,closed_arc_ids:[]});if(!r.ok||r.length_m===null)return null;
  let node=from;const points:XYZ[]=[[...nodes.get(node)!.world_pos]];let length=0;
  for(const id of r.arc_ids){const a=arcs.get(id);if(!a||bundle.layout.walk.nodes[a.from_node_index].node_id!==node)throw Error('INVALID_ROUTER_CHAIN');const next=bundle.layout.walk.nodes[a.to_node_index],last=points.at(-1)!;if(Math.abs(Math.hypot(...next.world_pos.map((v,i)=>v-last[i]))-a.length_m)>1e-6)throw Error('UNSUPPORTED_ROUTE_GEOMETRY');points.push([...next.world_pos]);node=next.node_id;length+=a.length_m;}
  if(node!==to||Math.abs(length-r.length_m)>1e-6)throw Error('INVALID_ROUTER_CHAIN');return{arc_ids:[...r.arc_ids],points,length_m:length,duration_s:length/speed};
 }
 async function assign(value:unknown):Promise<AssignmentResult>{
  if(pending)return result(false,'BUSY');const q=value as RoleAssignmentRequest;
  if(!q||typeof q!=='object'||Object.keys(q).sort().join('|')!==['event_id','actor_id','target_role','station_id','at_s','until_s','handoff_s'].sort().join('|')||![q.event_id,q.actor_id,q.station_id,q.target_role].every(v=>typeof v==='string'&&v.length>0&&v.length<=96)||![q.at_s,q.until_s,q.handoff_s].every(v=>typeof v==='number'&&Number.isFinite(v))||q.at_s<0||q.until_s<=q.at_s||q.until_s>STAFFING_DURATION_S||q.handoff_s<0)return result(false,'INVALID_REQUEST');
  const w=bundle.registry.workers.find(w=>w.actor_id===q.actor_id),p=bundle.profiles.profiles.find(p=>p.worker_id===q.actor_id);if(!w||!p)return result(false,'UNKNOWN_WORKER');
  if(!p.allowed_roles.includes(q.target_role))return result(false,'ROLE_NOT_ELIGIBLE');if(w.assigned_vehicle_id)return result(false,'VEHICLE_ASSIGNMENT_LOCKED');
  if(q.target_role!=='packer'||!p.allowed_equipment.includes('packing-station'))return result(false,'EQUIPMENT_NOT_ALLOWED');
  if(STAFFING_BREAK.actor_ids.includes(q.actor_id as 'K05'|'K06')&&overlap(q.at_s,q.until_s,STAFFING_BREAK.from_s,STAFFING_BREAK.to_s))return result(false,'WORKER_ON_BREAK');
  if(!['PK05','PK06'].includes(q.station_id)||q.at_s<STAFFING_BREAK.from_s||q.until_s>STAFFING_BREAK.to_s)return result(false,'STATION_UNAVAILABLE');
  if(q.handoff_s<=0)return result(false,'HANDOFF_REQUIRED');
  if(plans.some(p=>p.request.event_id===q.event_id||p.request.actor_id===q.actor_id||p.request.station_id===q.station_id&&overlap(q.at_s,q.until_s,p.request.at_s,p.request.until_s)))return result(false,'ASSIGNMENT_CONFLICT');
  const from=homes.get(q.actor_id)!,to='v3:service:'+q.station_id;let outbound:Path|null,back:Path|null;
  try{outbound=pathFor(q.actor_id,from,to,p.walk_speed_m_s);back=pathFor(q.actor_id,to,from,p.walk_speed_m_s);}catch{return result(false,'UNSUPPORTED_ROUTE_GEOMETRY');}if(!outbound||!back)return result(false,'NO_PATH');
  const departure=q.at_s+q.handoff_s,arrival=departure+outbound.duration_s,returnArrival=q.until_s+back.duration_s;if(arrival>=q.until_s)return result(false,'ASSIGNMENT_TOO_SHORT');if(returnArrival>STAFFING_DURATION_S)return result(false,'RETURN_OUTSIDE_EPISODE');
  const plan=freeze({request:structuredClone(q),from_node_id:from,to_node_id:to,departure_s:departure,arrival_s:arrival,return_arrival_s:returnArrival,outbound,return_path:back,retained_task:pendingTask(q.actor_id)}),token=revision;pending=true;
  try{const next=[...plans,plan].sort((a,b)=>a.request.actor_id.localeCompare(b.request.actor_id)),hash=await digest({baseline:baselineAllocation,events:next});if(revision!==token)return result(false,'CANCELLED');plans=next;allocationHash=hash;revision++;return result(true,'ASSIGNMENT_OK',plan);}finally{pending=false;}
 }
 function point(path:Path,elapsed:number):XYZ{let d=Math.max(0,Math.min(path.length_m,elapsed/path.duration_s*path.length_m));for(let i=1;i<path.points.length;i++){const a=path.points[i-1],b=path.points[i],length=Math.hypot(...b.map((x,j)=>x-a[j]));if(d<=length)return a.map((x,j)=>x+(b[j]-x)*d/length) as XYZ;d-=length;}return[...path.points.at(-1)!];}
 function sample(variant:'A'|'B',seconds:number){
  if(!['A','B'].includes(variant)||!Number.isFinite(seconds)||seconds<0||seconds>STAFFING_DURATION_S)throw Error('INVALID_STAFFING_TIME');
  const workers:StaffingWorker[]=bundle.registry.workers.map(w=>{const home=homes.get(w.actor_id)!,node=nodes.get(home)??bundle.layout.vehicle.nodes.find(n=>n.node_id===home)!,task=pendingTask(w.actor_id),out:StaffingWorker={actor_id:w.actor_id,baseline_role:w.baseline_role,effective_role:w.initial_role,phase:'baseline',available:true,planned_position_m:[...node.world_pos],station_id:w.baseline_role==='packer'?'PK'+w.actor_id.slice(1):null,retained_task:task?{...task,state:'retained'}:null};
   if(STAFFING_BREAK.actor_ids.includes(w.actor_id as 'K05'|'K06')&&seconds>=30&&seconds<600){out.phase='break';out.available=false;out.station_id=null;}
   const plan=variant==='B'?plans.find(p=>p.request.actor_id===w.actor_id):undefined;if(!plan||seconds<plan.request.at_s)return out;
   if(seconds<plan.return_arrival_s&&out.retained_task)out.retained_task.state='paused';
   if(seconds<plan.departure_s){out.phase='handoff';out.available=false;}
   else if(seconds<plan.arrival_s){out.phase='walking';out.available=false;out.planned_position_m=point(plan.outbound,seconds-plan.departure_s);}
   else if(seconds<plan.request.until_s){out.phase='assigned';out.effective_role=plan.request.target_role;out.station_id=plan.request.station_id;out.planned_position_m=[...plan.outbound.points.at(-1)!];}
   else if(seconds<plan.return_arrival_s){out.phase='returning';out.effective_role=plan.request.target_role;out.available=false;out.planned_position_m=point(plan.return_path,seconds-plan.request.until_s);}
   else out.phase='restored';return out;});
  return freeze({variant,time_s:seconds,source_kind:'visual_fixture' as const,engine_operation:false as const,operational_admission:false,fixture_id:'v3:staffing:role-assignment:demo:001',worker_count:24,workers,business_inputs_sha256:businessHash,allocation_sha256:variant==='A'?baselineHash:allocationHash,pending_tasks_executed:false,completed_jobs:0,calendar_kind:'synthetic_design_same_A_B',break_actor_positions_not_simulated:true,scene_binding:false,transition_costs:variant==='B'?plans.map(p=>({actor_id:p.request.actor_id,handoff_s:p.request.handoff_s,outbound_walk_s:p.outbound.duration_s,return_walk_s:p.return_path.duration_s,walk_distance_m:p.outbound.length_m+p.return_path.length_m})):[]});
 }
 function reset(){revision++;plans=[];allocationHash=baselineHash;}
 return Object.freeze({assign,sample,reset,plans:()=>structuredClone(plans),baseline_allocation_sha256:baselineHash,business_inputs_sha256:businessHash,source_kind:'visual_fixture' as const,engine_operation:false as const});
}
