import * as THREE from 'three';
import {isWarehouseScenarioPlan,type WarehouseScenarioPlan,type WarehouseScenarioSample} from './warehouseScenarioExecution';
import type {WarehouseBundle,XYZ} from './warehouseTypes';

type Kind='received'|'dispatched'|'buffered'|'refused';
type Cue={key:string;kind:Kind;at_s:number;position:XYZ;job_id:string;handling_unit_id:string;reason:string};
const COLORS:Record<Kind,number>={received:0x138b75,dispatched:0x2387bd,buffered:0x9b761a,refused:0xb35639};
const TTL=.7,COOLDOWN=.35,LIMIT=3;

/** Small local event marks only. They never move cargo, reserve resources or
 * substitute an unsupported action. All objects/materials belong to this view. */
export function createWarehouseScenarioVisualCues(scene:THREE.Scene,bundle:WarehouseBundle,plan:WarehouseScenarioPlan){
 if(!isWarehouseScenarioPlan(plan))throw Error('ISSUED_SCENARIO_PLAN_REQUIRED');
 const root=new THREE.Group();root.name='scenario_visual_event_marks';root.userData.semanticKind='visual_effect';scene.add(root);
 const geometry=new THREE.RingGeometry(.25,.34,32);
 const slots=Array.from({length:LIMIT},()=>{
  const material=new THREE.MeshBasicMaterial({color:COLORS.received,transparent:true,opacity:.8,depthWrite:false,side:THREE.DoubleSide});
  const mesh=new THREE.Mesh(geometry,material);mesh.rotation.x=-Math.PI/2;mesh.visible=false;mesh.renderOrder=3;root.add(mesh);
  return {mesh,material,cue:null as Cue|null,until:0};
 });
 const ports=new Map(bundle.fixture.inputs.ports.map(p=>[String(p.port_id),p.service_node_world_pos as XYZ]));
 const jobs=new Map(plan.jobs.map(j=>[j.job_id,j]));
 const signals:{key:string;kind:Kind;at_s:number;job_id:string;handling_unit_id:string;reason:string}[]=[];
 for(const [i,e]of plan.events.entries())if(e.kind==='completed_visual'){
  const j=jobs.get(e.job_id);if(!j)continue;
  signals.push({key:'completion:'+i,kind:(j.native_case==='long_crossdock'||j.native_case==='source_long_transfer')?'buffered':j.direction==='inbound'?'received':'dispatched',at_s:e.at_s,job_id:e.job_id,handling_unit_id:e.handling_unit_id,reason:j.reason});
 }
 for(const j of plan.jobs)if(!j.actor_id)signals.push({key:'refusal:'+j.job_id,kind:'refused',at_s:j.requested_at_s,job_id:j.job_id,handling_unit_id:j.handling_unit_id,reason:j.reason});
 signals.sort((a,b)=>a.at_s-b.at_s||a.key.localeCompare(b.key));
 const lastShown=new Map<Kind,number>();let previous:number|undefined,lastWall=-Infinity,disposed=false,shown=0;
 function clear(){for(const s of slots){s.mesh.visible=false;s.cue=null;s.until=0;}}
 function snapshot(){return {source_kind:'visual_fixture' as const,engine_operation:false,disposed,shown_events:shown,maximum_visible:LIMIT,active:slots.filter(s=>s.mesh.visible&&s.cue).map(s=>({...s.cue!,position:[...s.cue!.position] as XYZ})),changes_inventory:false};}
 function apply(sample:WarehouseScenarioSample,state:{playing:boolean;discontinuity?:boolean;reduced_motion?:boolean},wall_s=performance.now()/1000){
  if(disposed)throw Error('SCENARIO_VISUAL_CUES_DISPOSED');
  if(!Number.isFinite(wall_s)||!Number.isFinite(sample.at_s)||sample.at_s<0||sample.at_s>plan.duration_s)throw Error('INVALID_VISUAL_CUE_TIME');
  const jump=state.discontinuity||previous===undefined||sample.at_s<previous||wall_s<lastWall;
  for(const slot of slots)if(wall_s>=slot.until){slot.mesh.visible=false;slot.cue=null;}
  if(jump||!state.playing){clear();lastShown.clear();previous=sample.at_s;lastWall=wall_s;return snapshot();}
  const crossed=signals.filter(e=>e.at_s>previous!&&e.at_s<=sample.at_s).reverse();
  for(const e of crossed){
   if(wall_s-(lastShown.get(e.kind)??-Infinity)<COOLDOWN)continue;
   const slot=slots.find(s=>!s.mesh.visible);if(!slot)break;
   const job=jobs.get(e.job_id)!,cargo=sample.cargo.find(c=>c.handling_unit_id===e.handling_unit_id),point=(e.kind==='received'||e.kind==='buffered')&&cargo?.visible&&cargo.position?cargo.position:ports.get(job.port_id);
   if(!point||point.length!==3||!point.every(Number.isFinite))continue;
   const position:[number,number,number]=[point[0],point[1]+.016,point[2]];
   const radius=cargo ? Math.hypot(cargo.dimensions_xyz_m[0],cargo.dimensions_xyz_m[2])/2+.12 : .5;
   slot.cue={...e,position};slot.mesh.position.fromArray(position);slot.mesh.scale.setScalar(radius/.34);slot.material.color.setHex(COLORS[e.kind]);slot.material.opacity=.8;slot.mesh.visible=true;slot.until=wall_s+TTL;lastShown.set(e.kind,wall_s);shown++;
  }
  for(const s of slots)if(s.mesh.visible)s.material.opacity=state.reduced_motion ? .8 : .8*Math.max(0,(s.until-wall_s)/TTL);
  previous=sample.at_s;lastWall=wall_s;return snapshot();
 }
 return {apply,snapshot,stop:clear,dispose(){if(disposed)return;clear();root.removeFromParent();geometry.dispose();for(const s of slots)s.material.dispose();root.clear();disposed=true;}};
}
