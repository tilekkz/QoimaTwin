import type {WarehouseBundle,XYZ} from '../warehouseTypes';
import type {WarehouseLayoutPlan} from '../warehouseLayoutPlan';
import type {WarehouseLayoutAccessResult} from '../warehouseLayoutAccess';
import type {RoutePolicy} from '../warehouseRouting';
import type {WorkerRole} from '../workerRoles';
import type {Variant,WorkerSpot} from './twinScenario';
import {createShiftAisles,createShiftPickRoutes,sampleShiftPath,shiftPath,type ShiftPath,type ShiftPose} from './twinShiftRoutes';
import {SHIFT_DURATION_S,SHIFT_PROBLEMS,shiftProblemActive} from './twinShiftProblems';

export const SHIFT_SEED=0x514f494d;
export const SHIFT_LABEL='Насыщенная смена · демонстрация';
export function normalizeShiftTime(t:number){if(typeof t!=='number'||!Number.isFinite(t))throw new RangeError('SHIFT_INVALID_TIME');return Math.max(0,Math.min(SHIFT_DURATION_S,t));}
export type ShiftActor={id:string;role:WorkerRole;extra:boolean;zone:string;cart:boolean;vehicle:number|null;paths:Record<Variant,ShiftPath>;jobs:Record<Variant,ShiftJob[]>;period:number;offset:number};
type ShiftJob={release:number;start:number;outEnd:number;serviceEnd:number;backEnd:number;end:number;due:number;index:number};
export type ShiftWorkerFrame=ShiftPose&{id:string;role:WorkerRole;extra:boolean;cart:boolean;vehicle:number|null;zone:string};
export type ShiftCargoFrame=ShiftPose&{visible:boolean;kind:'tote'|'parcel'|'pallet'|'oversize';id:string};
type Port={port_id:string;world_pos:XYZ;direction:string;service_node_world_pos:XYZ;outward_normal:XYZ;finite_buffer_capacity:{allocations:{zone_id:string}[]}};
type Zone={zone_id:string;floor_bounds_xz_m:{min:[number,number];max:[number,number]}};
type BeltEdge={edge_id:string;from_node_id:string;to_node_id:string;length_m:number;path_kind:string;centre?:XYZ;radius_m?:number;theta_start_rad?:number;theta_end_rad?:number};
type Conveyor={edges:BeltEdge[];nodes:{node_id:string;world_pos:XYZ}[];packing_stations:{pack_id:string;work_node_id:string;worker_service:XYZ;table_origin:XYZ}[];source_assumptions:{speed_m_s:number}};
type BeltJob={id:string;release:number;path:ShiftPath;packAt:number;duration:number};
const freshPose=():ShiftPose=>({x:0,y:0,z:0,yaw:0,moving:false,working:false,waiting:false,loaded:false,phase:'idle',step:0});
const distance=(a:XYZ,b:XYZ)=>Math.hypot(a[0]-b[0],a[2]-b[2]);
function seeded(seed:number){let n=seed>>>0;return()=>{n^=n<<13;n^=n>>>17;n^=n<<5;return(n>>>0)/4294967296;};}

function beltRoute(source:Conveyor,from:string,to:string){
 const queue=[from],parents=new Map<string,BeltEdge>(),seen=new Set(queue);
 for(let i=0;i<queue.length&&!seen.has(to);i++)for(const e of source.edges)if(e.from_node_id===queue[i]&&!seen.has(e.to_node_id)){seen.add(e.to_node_id);parents.set(e.to_node_id,e);queue.push(e.to_node_id);}
 if(!seen.has(to))throw Error('SHIFT_CONVEYOR_DISCONNECTED');const edges:BeltEdge[]=[];for(let n=to;n!==from;){const e=parents.get(n)!;edges.unshift(e);n=e.from_node_id;}
 const nodes=new Map(source.nodes.map(n=>[n.node_id,n.world_pos])),points:XYZ[]=[[...nodes.get(from)!]];
 for(const e of edges){if(e.path_kind==='arc'){for(let k=1;k<=16;k++){const a=e.theta_start_rad!+(e.theta_end_rad!-e.theta_start_rad!)*k/16;points.push([e.centre![0]+e.radius_m!*Math.cos(a),e.centre![1],e.centre![2]+e.radius_m!*Math.sin(a)]);}}else points.push([...nodes.get(e.to_node_id)!]);}
 return shiftPath(points,'source_conveyor_edges');
}

/** Pure absolute-time schedules. Seed, orders, assignments and geometry are fixed at
 * construction. Playback never integrates positions, random values or counters. */
export function createTwinShiftGenerator(bundle:WarehouseBundle,policy:RoutePolicy,plan:WarehouseLayoutPlan|null,access:WarehouseLayoutAccessResult|null){
 const random=seeded(SHIFT_SEED),conveyor=bundle.layout.data.conveyor as Conveyor,ports=bundle.layout.data.ports as Port[],sourceZones=bundle.layout.data.zones as Zone[];
 const zones=new Map(sourceZones.map(z=>[z.zone_id,z]));for(const z of plan?.zones??[])zones.set(z.zone_id,z);
 const pickRoutes=createShiftPickRoutes(bundle,policy,plan,access);
 const aisles={A:createShiftAisles(bundle,null,.55),B:createShiftAisles(bundle,plan,.55)},vehicleAisles={A:createShiftAisles(bundle,null,1.7),B:createShiftAisles(bundle,plan,1.7)};
 const actors:ShiftActor[]=[],fleet:{id:string;extra:boolean;zone:string;paths:Record<Variant,ShiftPath>;actor:string}[]=[];
 const definitions:{id:string;role:WorkerRole;extra:boolean}[]=bundle.registry.workers.map(w=>({id:w.actor_id,role:w.baseline_role,extra:false}));
 const extras:{role:WorkerRole;count:number}[]=[{role:'picker',count:24},{role:'packer',count:6},{role:'receiver',count:7},{role:'shipper',count:7},{role:'forklift_driver',count:4}];
 for(const e of extras)for(let i=0;i<e.count;i++)definitions.push({id:`DEMO-${e.role}-${i+1}`,role:e.role,extra:true});
 const roleIndex:Partial<Record<WorkerRole,number>>={},pickModules=bundle.layout.modules.filter((m,i)=>['SMALL','STANDARD','FLEX'].includes(m.family)&&bundle.layout.slots.some(s=>s.module_index===i&&!s.reserve_only&&!s.retrieval_blocked));
 // Spread the same orders across the whole source warehouse, using a stable shuffled deck.
 for(let i=pickModules.length-1;i>0;i--){const k=Math.floor(random()*(i+1));[pickModules[i],pickModules[k]]=[pickModules[k],pickModules[i]];}
 const centre=(zone:string):XYZ=>{const r=zones.get(zone)?.floor_bounds_xz_m;if(!r)throw Error('SHIFT_ZONE_MISSING:'+zone);return[(r.min[0]+r.max[0])/2,0,(r.min[1]+r.max[1])/2];};
 for(const d of definitions){
  const index=roleIndex[d.role]??0;roleIndex[d.role]=index+1;let paths:Record<Variant,ShiftPath>,zone:string,vehicle:number|null=null;
  if(d.role==='picker'){
   const m=pickModules[index%pickModules.length],pack=conveyor.packing_stations.reduce((a,b)=>distance(a.worker_service,m.world_pos)<distance(b.worker_service,m.world_pos)?a:b);
   paths={A:pickRoutes.route(m.module_id,pack.pack_id,'A'),B:pickRoutes.route(m.module_id,pack.pack_id,'B')};zone=sourceZones[m.zone_index].zone_id;
  }else if(d.role==='packer'){
   const station=conveyor.packing_stations[index%conveyor.packing_stations.length],p:XYZ=[station.worker_service[0]+(index<6?-.48:.48),0,station.worker_service[2]];
   paths={A:shiftPath([p,p],'source_packing_station'),B:shiftPath([p,p],'source_packing_station')};zone='PACKING_LIGHT_LINE';
  }else if(d.role==='forklift_driver'){
   vehicle=fleet.length;const direction=vehicle%2===0?'inbound':'outbound',port=ports.filter(p=>p.direction===direction)[Math.floor(vehicle/2)%3];
   const family=vehicle%3===2?'LONG':'HEAVY',source=bundle.layout.modules.filter(m=>m.family===family).sort((a,b)=>distance(a.world_pos,port.service_node_world_pos)-distance(b.world_pos,port.service_node_world_pos)||a.module_id.localeCompare(b.module_id)),m=source[vehicle%Math.min(4,source.length)];zone=sourceZones[m.zone_index].zone_id;
   const route=(v:Variant)=>{const target=v==='B'&&plan?plan.modules.find(n=>n.module_id===m.module_id)!:m,b=target.outer_bounds_world,p:XYZ=[(b.min[0]+b.max[0])/2,0,b.min[2]-2.4];return vehicleAisles[v].route(port.service_node_world_pos,p);};
   paths={A:route('A'),B:route('B')};fleet.push({id:vehicle<2?'FL0'+(vehicle+1):'DEMO-FL'+(vehicle+1),extra:d.extra,zone,paths,actor:d.id});
  }else{
   const eligible=ports.filter(p=>p.direction===(d.role==='receiver'?'inbound':'outbound')),port=eligible[index%eligible.length],stage=port.finite_buffer_capacity.allocations[0].zone_id;
   const r=zones.get(stage)!.floor_bounds_xz_m,p=centre(stage),lane=Math.floor(index/eligible.length);p[0]=r.min[0]+(r.max[0]-r.min[0])*(.25+lane*.22);p[2]=r.min[1]+(r.max[1]-r.min[1])*.7;
   const end:XYZ=[port.service_node_world_pos[0]+port.outward_normal[2]*(lane-1)*1.3,0,port.service_node_world_pos[2]-port.outward_normal[0]*(lane-1)*1.3];
   paths={A:aisles.A.route(p,end),B:aisles.B.route(p,end)};zone=stage;
  }
  const speedB=vehicle!==null?1.65:d.role==='picker'?1.08:1.0,serviceB=d.role==='packer'?9:vehicle!==null?12:8;
  // Demand is materialized from source A, independently of a selected B layout.
  const referenceDuration=paths.A.length*2/speedB+serviceB+6,period=Math.max(d.role==='packer'?18:45,referenceDuration+18),offset=-period*(.2+random()*.8);
  const a:ShiftActor={...d,zone,cart:d.role==='picker',vehicle,paths,jobs:{A:[],B:[]},period,offset};
  for(const v of ['A','B'] as Variant[]){let available=-Infinity;const speed=v==='A'?(vehicle!==null?2.1:d.role==='picker'?1.75:1.4):speedB;
   for(let j=0,release=offset;release<=SHIFT_DURATION_S+period;release=offset+(++j)*period){
    const travel=paths[v].length/speed,delay=v==='A'?Math.max(38,referenceDuration-travel*2+48):serviceB,waitEnd=v==='A'?26:6,start=Math.max(release,available),outEnd=start+travel,serviceEnd=outEnd+delay,backEnd=serviceEnd+travel,end=backEnd+waitEnd;
    a.jobs[v].push({release,start,outEnd,serviceEnd,backEnd,end,due:release+referenceDuration+20,index:j});available=end;
   }
  }actors.push(a);
 }
 const beltPlans=conveyor.packing_stations.map(station=>{const out=beltRoute(conveyor,'v3:conv:intake',station.work_node_id??`v3:conv:${station.pack_id}:WORK`),back=beltRoute(conveyor,station.work_node_id??`v3:conv:${station.pack_id}:WORK`,'v3:conv:output');return {path:shiftPath([...out.points,...back.points.slice(1)],'source_conveyor_edges'),packAt:out.length};});
 const beltSpeed=conveyor.source_assumptions.speed_m_s,beltJobs:BeltJob[]=[];
 for(let i=0,release=-240;release<=SHIFT_DURATION_S;release=-240+(++i)*4.8){const p=beltPlans[i%beltPlans.length];beltJobs.push({id:'DEMO-BELT-'+i,release,path:p.path,packAt:p.packAt,duration:p.path.length/beltSpeed+10});}
 const jam=SHIFT_PROBLEMS.find(p=>p.kind==='jam')!;
 const staging:{id:string;zone:string;point:XYZ;ordinal:number}[]=[];
 // Actual staging rectangles determine every cargo cell; keep clear approaches empty.
 for(const z of sourceZones.filter(z=>z.zone_id.startsWith('STAGE_'))){const r=zones.get(z.zone_id)!.floor_bounds_xz_m;let n=0;for(let x=r.min[0]+1.2;x<r.max[0]-1;x+=2.2)for(let zz=r.min[1]+1.2;zz<r.max[1]-1;zz+=2.2){if(staging.filter(s=>s.zone===z.zone_id).length>=16)break;staging.push({id:`DEMO-STAGE-${z.zone_id}-${n}`,zone:z.zone_id,point:[x,0,zz],ordinal:n++});}}
 const rejectedModule=bundle.layout.modules.find(m=>m.family==='LONG'&&sourceZones[m.zone_index].zone_id==='LONG_E')!,rejectedBounds=rejectedModule.outer_bounds_world;
 const rejectedRoute=vehicleAisles.A.route(ports.find(p=>p.direction==='outbound')!.service_node_world_pos,[(rejectedBounds.min[0]+rejectedBounds.max[0])/2,0,rejectedBounds.min[2]-2.4]);
 const rejectedPoint=rejectedRoute.points.at(-1)!,rejectedPallet={...freshPose(),x:rejectedPoint[0],z:rejectedPoint[2]};
 const frames={} as Record<Variant,ReturnType<typeof makeFrame>>;
 function makeFrame(){return {at:-Infinity,workers:actors.map(a=>({...freshPose(),id:a.id,role:a.role,extra:a.extra,cart:a.cart,vehicle:a.vehicle,zone:a.zone})),vehicles:fleet.map(f=>({...freshPose(),id:f.id,extra:f.extra})),belt:Array.from({length:80},(_,i)=>({...freshPose(),visible:false,kind:'tote' as ShiftCargoFrame['kind'],id:'DEMO-BELT-'+i})),staging:staging.map(s=>({...freshPose(),x:s.point[0],z:s.point[2],visible:false,kind:'pallet' as ShiftCargoFrame['kind'],id:s.id})),trucks:ports.map(p=>({...freshPose(),id:'DEMO-TRUCK-'+p.port_id,visible:true,port:p.port_id})),summary:{people:actors.length,registered:actors.filter(a=>!a.extra).length,extra_crew:actors.filter(a=>a.extra).length,vehicles:fleet.length,trucks:0,movements_done:0,tasks_waiting:0,workers_waiting:0,late_orders:0,belt_visible:0,staging_cargo:0,incoming_orders:0},activeProblems:[] as string[]};}
 frames.A=makeFrame();frames.B=makeFrame();
 function sample(v:Variant,t:number){
  if(v!=='A'&&v!=='B')throw new RangeError('SHIFT_INVALID_VARIANT');t=normalizeShiftTime(t);
  const f=frames[v];if(f.at===t)return f;f.at=t;let done=0,queued=0,waiting=0,late=0,incoming=0;
  for(let i=0;i<actors.length;i++){
   const a=actors[i],p=f.workers[i],jobs=a.jobs[v];let actorTime=t,incidentPhase:string|null=null;
   // Pause the worker's task clock at the incident boundary, preserving the exact
   // position on the path. Arrival of new orders continues on the shared clock.
   if(v==='A')for(const problem of SHIFT_PROBLEMS){
    const pausesPicker=a.role==='picker'&&a.zone===problem.zone&&problem.kind==='replenishment'&&(problem.id==='replenishment'||i%2===0),pausesVehicle=a.vehicle===0&&problem.kind==='blocked',pausesPacker=a.role==='packer'&&(a.id==='K03'||a.id==='K05')&&problem.kind==='packing',pausesReceiver=a.role==='receiver'&&a.zone===problem.zone&&problem.kind==='late-truck';
    if(pausesPicker||pausesVehicle||pausesPacker||pausesReceiver){actorTime-=Math.max(0,Math.min(t,problem.end)-problem.start);if(t>=problem.start&&t<problem.end)incidentPhase=pausesVehicle?'blocked':pausesPacker?'needs-help':pausesReceiver?'late-truck':'wait-replenishment';}
   }
   let job=jobs[0];for(const j of jobs){if(j.start<=actorTime)job=j;if(j.release>=0&&j.release<=t){incoming++;if(j.start>actorTime)queued++;}if(j.end>=0&&j.end<=actorTime)done++;if(j.release>=0&&j.due<=t&&j.end>actorTime)late++;}
   p.waiting=false;p.working=false;p.moving=false;p.loaded=false;p.phase='ready';p.step=t*(v==='A'?2.8:1.65)+i*.79;
   let d=0,returning=false;
   if(actorTime<job.start){p.phase='ready';}else if(actorTime<job.outEnd){d=(actorTime-job.start)/(job.outEnd-job.start)*a.paths[v].length;p.moving=true;p.phase='to-slot';}
   else if(actorTime<job.serviceEnd){d=a.paths[v].length;p.waiting=v==='A';p.working=!p.waiting;p.loaded=true;p.phase=p.waiting?'waiting':'handling';}
   else if(actorTime<job.backEnd){d=a.paths[v].length*(1-(actorTime-job.serviceEnd)/(job.backEnd-job.serviceEnd));returning=true;p.moving=true;p.loaded=true;p.phase='to-handoff';}
   else if(actorTime<job.end){d=0;p.waiting=v==='A';p.working=!p.waiting;p.loaded=true;p.phase=p.waiting?'handoff-queue':'handoff';}
   sampleShiftPath(a.paths[v],d,p,v==='B');if(returning)p.yaw+=Math.PI;
   if(a.role==='packer'){p.yaw=Math.PI;p.moving=false;p.waiting=v==='A'&&shiftProblemActive('packing',v,t)&&(a.id==='K03'||a.id==='K05');p.working=!p.waiting;p.phase=p.waiting?'needs-help':'packing';}
   if(incidentPhase){p.waiting=true;p.moving=false;p.working=false;p.phase=incidentPhase;}
   if(a.vehicle!==null){if(a.vehicle%2===0)p.loaded=actorTime>=job.start&&actorTime<job.serviceEnd;const fleetPose=f.vehicles[a.vehicle];Object.assign(fleetPose,p);fleetPose.id=fleet[a.vehicle].id;fleetPose.extra=fleet[a.vehicle].extra;}
   if(p.waiting)waiting++;
  }
  const beltClock=v==='A'?t-Math.max(0,Math.min(t,jam.end)-jam.start):t;let bi=0;
  for(const b of beltJobs){if(b.release>=0&&b.release<=t){incoming++;if(b.release>beltClock)queued++;}const elapsed=beltClock-b.release;if(elapsed>=b.duration){if(b.release>=0)done++;continue;}if(elapsed<0)continue;if(bi>=f.belt.length)break;
   const p=f.belt[bi++],atPack=b.packAt/beltSpeed,travel=elapsed>atPack?Math.max(atPack,elapsed-10):elapsed;sampleShiftPath(b.path,Math.min(b.path.length,travel*beltSpeed),p,true);p.y=b.path.points[0][1];p.id=b.id;p.visible=true;p.loaded=true;p.kind=elapsed>atPack+10?'parcel':'tote';p.waiting=elapsed>=atPack&&elapsed<atPack+10||shiftProblemActive('jam',v,t);p.phase=p.waiting?'belt-wait':'belt-travel';}
  for(let i=bi;i<f.belt.length;i++)f.belt[i].visible=false;
  let pallets=0;for(let i=0;i<staging.length;i++){const s=staging[i],p=f.staging[i];let incident=false;if(v==='A')for(const pr of SHIFT_PROBLEMS)if(pr.zone===s.zone&&t>=pr.start&&(t<pr.end||t===SHIFT_DURATION_S&&pr.end===SHIFT_DURATION_S)){incident=true;break;}p.visible=incident||s.ordinal<2&&((Math.floor(t/18)+s.ordinal+i)%4<2);if(p.visible)pallets++;}
  let trucks=0;for(let i=0;i<ports.length;i++){
   const port=ports[i],p=f.trucks[i],cycle=(t+i*37)%240,lateTruck=port.port_id==='IN_N_STANDARD'&&shiftProblemActive('late-truck',v,t),progress=cycle<25?1-cycle/25:cycle>205?(cycle-205)/35:0;
   // Approach/leave along the exterior apron, rather than into the neighbouring
   // copy in the shared A/B scene. Both poses derive from the fixed gate frame.
   const tx=Math.abs(port.outward_normal[2])>0?1:0,tz=tx?0:port.outward_normal[0]>0?1:-1,heading=Math.atan2(-port.outward_normal[0],-port.outward_normal[2]),turn=Math.atan2(Math.sin(Math.atan2(tx,tz)-heading),Math.cos(Math.atan2(tx,tz)-heading));
   p.x=port.world_pos[0]+port.outward_normal[0]*5.2+tx*progress*14;p.z=port.world_pos[2]+port.outward_normal[2]*5.2+tz*progress*14;p.yaw=heading+turn*Math.min(1,progress*3);p.waiting=lateTruck;p.moving=progress>0;p.visible=!lateTruck&&progress<.95;if(p.visible)trucks++;
  }
  f.activeProblems.length=0;if(v==='A')for(const p of SHIFT_PROBLEMS)if(t>=p.start&&(t<p.end||t===SHIFT_DURATION_S&&p.end===SHIFT_DURATION_S))f.activeProblems.push(p.id);
  const s=f.summary;s.trucks=trucks;s.movements_done=done;s.tasks_waiting=queued;s.workers_waiting=waiting;s.late_orders=late;s.belt_visible=bi;s.staging_cargo=pallets;s.incoming_orders=incoming;return f;
 }
 const workerSpots:WorkerSpot[]=actors.map(a=>({actor_id:a.id,zone_id:a.zone}));
 function workers(_v:Variant,_t:number):readonly WorkerSpot[]{return workerSpots;}
 function snapshot(t:number){
  t=normalizeShiftTime(t);
  const describe=(v:Variant)=>{const f=sample(v,t);return {summary:{...f.summary},active_problems:[...f.activeProblems],workers:f.workers.map(w=>({id:w.id,extra:w.extra,role:w.role,position:[w.x,w.y,w.z],yaw:w.yaw,phase:w.phase,loaded:w.loaded,waiting:w.waiting,moving:w.moving})),vehicles:f.vehicles.map(w=>({id:w.id,position:[w.x,w.y,w.z],yaw:w.yaw,phase:w.phase,loaded:w.loaded,waiting:w.waiting})),belt:f.belt.filter(b=>b.visible).map(b=>({id:b.id,position:[b.x,b.y,b.z],phase:b.phase,kind:b.kind})),staging:f.staging.filter(p=>p.visible).map(p=>({id:p.id,position:[p.x,p.y,p.z],kind:p.kind})),trucks:f.trucks.map(p=>({id:p.id,position:[p.x,p.y,p.z],yaw:p.yaw,visible:p.visible,waiting:p.waiting})),rejected_pallet:shiftProblemActive('slot-fit',v,t)?{position:[rejectedPallet.x,0,rejectedPallet.z],kind:'oversize'}:null};};
  return {seed:SHIFT_SEED,label:SHIFT_LABEL,at_s:t,source_kind:'visual_fixture',engine_operation:false,operational_admission:false,behaviour_basis:'authored_demo_pace_waits_and_deadlines',order_stream:'same_seed_same_release_times_same_tasks',plan_sha256:plan?.plan_sha256??null,A:describe('A'),B:describe('B'),route_distances:actors.filter(a=>a.role==='picker'||a.vehicle!==null).map(a=>({actor_id:a.id,A_m:a.paths.A.length*2,B_m:a.paths.B.length*2,A_basis:a.paths.A.basis,B_basis:a.paths.B.basis})),original_stock_HUs:bundle.fixture.inputs.initial_stock.length,original_workers:bundle.registry.workers.length};
 }
 return {actors,fleet,rejectedPallet,sample,workers,snapshot,seed:SHIFT_SEED,plan_sha256:plan?.plan_sha256??null};
}
export type TwinShiftGenerator=ReturnType<typeof createTwinShiftGenerator>;
