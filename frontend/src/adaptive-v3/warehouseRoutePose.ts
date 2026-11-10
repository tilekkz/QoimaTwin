import type {WarehouseArc,WarehouseBundle,XYZ} from './warehouseTypes';
import type {RoutePlan} from './warehouseRouting';

type Wheels={front_L:number;front_R:number;rear_L:number;rear_R:number};
export type RoutePose={position:XYZ;yaw_rad:number;front_axle_position:XYZ|null;arc_id:string|null;route_distance_m:number;motion_direction:number;virtual_steer_rad:number;rear_steer_rad:{L:number;R:number};wheel_angles_rad:Wheels};
type ArcSample=Omit<RoutePose,'route_distance_m'>;
const axleOffset=.4,wheelbase=1.4,halfTrack=.35,frontRadius=.3,rearRadius=.225;
const wheels=():Wheels=>({front_L:0,front_R:0,rear_L:0,rear_R:0});
const wrap=(angle:number)=>Math.atan2(Math.sin(angle),Math.cos(angle));
const clamp=(value:number,min:number,max:number)=>Math.min(max,Math.max(min,value));
function finite(value:number){if(!Number.isFinite(value))throw Error('INVALID_ROUTE_POSITION');return value;}
export function rearWheelAngles(virtual:number){
 finite(virtual);if(Math.abs(virtual)>Math.PI/3+1e-9)throw Error('STEERING_LIMIT');if(Math.abs(virtual)<1e-12)return{L:0,R:0};const q=-wheelbase/Math.tan(virtual);return{L:Math.atan(-wheelbase/(q+halfTrack)),R:Math.atan(-wheelbase/(q-halfTrack))};
}

/** Original L07/L09 analytic front-axle curve, with independent physical chassis heading. */
export function sampleVehicleArc(arc:WarehouseArc,u:number):ArcSample{
 u=clamp(finite(u),0,1);const g=arc.fields.geometry as Record<string,unknown>,a=g.start_yaw_rad as number,b=g.end_yaw_rad as number,yaw=a+(b-a)*u,direction=arc.fields.motion_direction as number;
 let front:XYZ,virtual=0,rolling=wheels();
 if(g.kind==='line'){
  const start=g.front_axle_start_xz_m as number[],end=g.front_axle_end_xz_m as number[];if(Math.abs(b-a)>1e-8)throw Error('IN_PLACE_YAW_FORBIDDEN');front=[start[0]+(end[0]-start[0])*u,0,start[1]+(end[1]-start[1])*u];const distance=direction*arc.length_m*u;rolling={front_L:distance/frontRadius,front_R:distance/frontRadius,rear_L:distance/rearRadius,rear_R:distance/rearRadius};
 }else if(g.kind==='rear_steer_arc'){
  const centre=g.icr_world_xz_m as number[],q=g.icr_vehicle_local_x_m as number;if(!Number.isFinite(q)||Math.abs(q)<halfTrack)throw Error('INVALID_VEHICLE_ARC');front=[centre[0]-q*Math.cos(yaw),0,centre[1]+q*Math.sin(yaw)];virtual=Math.atan(-wheelbase/q);const angle=direction*Math.abs(b-a)*u;rolling={front_L:angle*Math.abs(-halfTrack-q)/frontRadius,front_R:angle*Math.abs(halfTrack-q)/frontRadius,rear_L:angle*Math.hypot(-halfTrack-q,wheelbase)/rearRadius,rear_R:angle*Math.hypot(halfTrack-q,wheelbase)/rearRadius};
 }else throw Error('INVALID_VEHICLE_ARC');
 return{position:[front[0]-axleOffset*Math.sin(yaw),0,front[2]-axleOffset*Math.cos(yaw)],yaw_rad:yaw,front_axle_position:front,arc_id:arc.arc_id,motion_direction:direction,virtual_steer_rad:virtual,rear_steer_rad:rearWheelAngles(virtual),wheel_angles_rad:rolling};
}

export function createRouteDistanceSampler(bundle:WarehouseBundle,plan:RoutePlan){
 if(!plan.ok||plan.source_kind!=='visual_fixture'||plan.engine_operation!==false||plan.operational_admission!==false||plan.length_m===null)throw Error('ROUTE_NOT_ADMITTED');
 const vehicle=plan.graph==='vehicle',graph=vehicle?bundle.layout.vehicle:bundle.layout.walk,lookup=new Map(graph.arcs.map(a=>[a.arc_id,a])),nodes=new Map(graph.nodes.map((n,i)=>[n.node_id,i])),start=nodes.get(plan.from_node_id),end=nodes.get(plan.to_node_id);if(start===undefined||end===undefined)throw Error('UNKNOWN_ROUTE_NODE');
 const arcs=plan.arc_ids.map(id=>{const arc=lookup.get(id);if(!arc)throw Error('UNKNOWN_ROUTE_ARC');return arc;}),offsets:number[]=[],yawOffsets:number[]=[],rollingOffsets:Wheels[]=[];let total=0,node=start,previousYaw=graph.nodes[start].yaw_rad??0,rolling=wheels();
 for(const arc of arcs){if(arc.from_node_index!==node)throw Error('ROUTE_DISCONNECTED');offsets.push(total);rollingOffsets.push({...rolling});if(vehicle){const first=sampleVehicleArc(arc,0),last=sampleVehicleArc(arc,1),adjustment=previousYaw+wrap(first.yaw_rad-previousYaw)-first.yaw_rad;if(Math.abs(wrap(first.yaw_rad-previousYaw))>1e-7)throw Error('IN_PLACE_YAW_FORBIDDEN');yawOffsets.push(adjustment);previousYaw=last.yaw_rad+adjustment;for(const key of Object.keys(rolling) as (keyof Wheels)[])rolling[key]+=last.wheel_angles_rad[key];}else yawOffsets.push(0);total+=arc.length_m;node=arc.to_node_index;}
 if(node!==end||Math.abs(total-plan.length_m)>1e-7||(!arcs.length&&start!==end))throw Error('ROUTE_LENGTH_MISMATCH');
 function sample(distance:number):RoutePose{
  distance=clamp(finite(distance),0,total);if(!arcs.length)return{position:[...graph.nodes[start!].world_pos],yaw_rad:graph.nodes[start!].yaw_rad??0,front_axle_position:vehicle?[graph.nodes[start!].world_pos[0]+axleOffset*Math.sin(previousYaw),0,graph.nodes[start!].world_pos[2]+axleOffset*Math.cos(previousYaw)]:null,arc_id:null,route_distance_m:0,motion_direction:0,virtual_steer_rad:0,rear_steer_rad:{L:0,R:0},wheel_angles_rad:wheels()};
  let lo=0,hi=arcs.length;while(lo+1<hi){const mid=(lo+hi)>>1;if(offsets[mid]<=distance)lo=mid;else hi=mid;}const arc=arcs[lo],u=clamp((distance-offsets[lo])/arc.length_m,0,1);
  if(vehicle){const pose=sampleVehicleArc(arc,u);pose.yaw_rad+=yawOffsets[lo];for(const key of Object.keys(rolling) as (keyof Wheels)[])pose.wheel_angles_rad[key]+=rollingOffsets[lo][key];return{...pose,route_distance_m:distance};}
  const a=graph.nodes[arc.from_node_index].world_pos,b=graph.nodes[arc.to_node_index].world_pos;return{position:[a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u,a[2]+(b[2]-a[2])*u],yaw_rad:Math.atan2(b[0]-a[0],b[2]-a[2]),front_axle_position:null,arc_id:arc.arc_id,route_distance_m:distance,motion_direction:1,virtual_steer_rad:0,rear_steer_rad:{L:0,R:0},wheel_angles_rad:wheels()};
 }
 return Object.freeze({length_m:total,arcs:Object.freeze(arcs),offsets:Object.freeze(offsets),sample});
}

type Drive={kind:'drive';start_s:number;end_s:number;distance_m:number;length_m:number;virtual_steer_rad:number;motion_direction:number;accel_time_s:number;cruise_time_s:number;peak_speed_m_s:number};
type Steering={kind:'steer';start_s:number;end_s:number;distance_m:number;from_rad:number;to_rad:number};
export type VehicleRoutePreview={source_kind:'visual_fixture';engine_operation:false;operational_admission:false;duration_s:number;phases:readonly(Drive|Steering)[];sample:(at_s:number)=>RoutePose&{at_s:number;speed_m_s:number;stage:'travel'|'steering'|'route_end';completed_jobs:0}};
/** Separate paused route demonstration. Timings are explicit synthetic animation assumptions, never KPI. */
export function compileVehicleRoutePreview(bundle:WarehouseBundle,plan:RoutePlan):VehicleRoutePreview{
 if(plan.graph!=='vehicle')throw Error('VEHICLE_PREVIEW_ONLY');const sampler=createRouteDistanceSampler(bundle,plan),groups:{distance:number;length:number;virtual:number;direction:number}[]=[];
 for(let i=0;i<sampler.arcs.length;i++){const arc=sampler.arcs[i],p=sampleVehicleArc(arc,0),last=groups.at(-1);if(last&&last.direction===p.motion_direction&&Math.abs(last.virtual-p.virtual_steer_rad)<1e-9)last.length+=arc.length_m;else groups.push({distance:sampler.offsets[i],length:arc.length_m,virtual:p.virtual_steer_rad,direction:p.motion_direction});}
 const phases:(Drive|Steering)[]=[];let time=0,previousSteer=0;
 for(const group of groups){const hold=Math.max(.25,1.5*Math.abs(group.virtual-previousSteer)/.5);phases.push({kind:'steer',start_s:time,end_s:time+hold,distance_m:group.distance,from_rad:previousSteer,to_rad:group.virtual});time+=hold;const acceleration=.5,maximum=Math.abs(group.virtual)>1e-9?.5:1.2,peak=Math.min(maximum,Math.sqrt(group.length*acceleration)),ramp=peak/acceleration,cruise=Math.max(0,(group.length-peak*peak/acceleration)/peak),duration=2*ramp+cruise;phases.push({kind:'drive',start_s:time,end_s:time+duration,distance_m:group.distance,length_m:group.length,virtual_steer_rad:group.virtual,motion_direction:group.direction,accel_time_s:ramp,cruise_time_s:cruise,peak_speed_m_s:peak});time+=duration;previousSteer=group.virtual;}
 if(groups.length){const hold=Math.max(.25,1.5*Math.abs(previousSteer)/.5);phases.push({kind:'steer',start_s:time,end_s:time+hold,distance_m:sampler.length_m,from_rad:previousSteer,to_rad:0});time+=hold;}
 function sample(at:number){at=clamp(finite(at),0,time);let phase=phases.find(p=>at>=p.start_s&&at<p.end_s);if(!phase){const p=sampler.sample(sampler.length_m);return{...p,at_s:at,speed_m_s:0,motion_direction:0,virtual_steer_rad:0,rear_steer_rad:{L:0,R:0},stage:'route_end' as const,completed_jobs:0 as const};}
  const elapsed=at-phase.start_s;if(phase.kind==='steer'){const u=elapsed/(phase.end_s-phase.start_s),smooth=u*u*(3-2*u),virtual=phase.from_rad+(phase.to_rad-phase.from_rad)*smooth;return{...sampler.sample(phase.distance_m),at_s:at,motion_direction:0,speed_m_s:0,virtual_steer_rad:virtual,rear_steer_rad:rearWheelAngles(virtual),stage:'steering' as const,completed_jobs:0 as const};}
  const acceleration=phase.peak_speed_m_s/phase.accel_time_s;let distance:number,speed:number;if(elapsed<phase.accel_time_s){speed=acceleration*elapsed;distance=.5*acceleration*elapsed*elapsed;}else if(elapsed<phase.accel_time_s+phase.cruise_time_s){speed=phase.peak_speed_m_s;distance=.5*phase.peak_speed_m_s*phase.accel_time_s+phase.peak_speed_m_s*(elapsed-phase.accel_time_s);}else{const remaining=phase.end_s-at;speed=acceleration*remaining;distance=phase.length_m-.5*acceleration*remaining*remaining;}
  return{...sampler.sample(phase.distance_m+distance),at_s:at,speed_m_s:speed,motion_direction:phase.motion_direction,virtual_steer_rad:phase.virtual_steer_rad,rear_steer_rad:rearWheelAngles(phase.virtual_steer_rad),stage:'travel' as const,completed_jobs:0 as const};
 }
 return Object.freeze({source_kind:'visual_fixture',engine_operation:false,operational_admission:false,duration_s:time,phases:Object.freeze(phases.map(p=>Object.freeze(p))),sample});
}
