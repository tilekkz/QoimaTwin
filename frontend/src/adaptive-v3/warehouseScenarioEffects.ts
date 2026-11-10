import {createSfxController} from '../replay/sfx';
import type {VisualFrame,Role} from '../replay/types';
import {isWarehouseScenarioPlan,type WarehouseScenarioPlan,type WarehouseScenarioSample} from './warehouseScenarioExecution';

/** Audio projection of admitted common-clock events. It never drives the Scene,
 * changes cargo ownership or supplies missing action/animation poses. */
export function createWarehouseScenarioEffects(plan:WarehouseScenarioPlan,options:Parameters<typeof createSfxController>[0]={}){
 if(!isWarehouseScenarioPlan(plan))throw Error('ISSUED_SCENARIO_PLAN_REQUIRED');
 const sound=createSfxController(options);
 let previous:WarehouseScenarioSample|undefined,disposed=false,crossed=0;
 function apply(at_s:number,state:{playing:boolean;speed:number;discontinuity?:boolean;terminal?:boolean},wall_s?:number){
  if(disposed)throw Error('SCENARIO_EFFECTS_DISPOSED');
  if(!Number.isFinite(state.speed)||state.speed<=0)throw Error('INVALID_EFFECT_SPEED');
  const sample=plan.sample(at_s),jump=state.discontinuity||!previous||sample.at_s<previous.at_s;
  const from=previous?.at_s??sample.at_s;
  const events=jump||!state.playing?[]:plan.events.flatMap((e,seq)=>{
   if(e.at_s<=from||e.at_s>sample.at_s||e.kind!=='completed_visual')return [];
   const job=plan.jobs.find(j=>j.job_id===e.job_id)!;
   // Delivery into a port buffer is not a dispatched shipment.
   if(job.native_case==='long_crossdock'||job.native_case==='source_long_transfer')return [];
   return [{seq,at_s:e.at_s,phase:0,kind:job.direction==='inbound'?'pallet_putaway':'order_dispatched',entity_id:e.handling_unit_id,payload:{actor_id:job.actor_id,job_id:job.job_id}}];
  });
  crossed+=events.length;
  const frame:VisualFrame={time:sample.at_s,duration:plan.duration_s,source:'visual-fixture',label:'Общий сценарий склада',
   events,pulses:[],labels:[],orderStages:{},warnings:[],
   // Belt motion has no admitted shared-clock controller yet; do not synthesize it.
   line:{blocked:true,blockedSegmentIds:[]},
   actors:Object.fromEntries(sample.actors.map(a=>{
    const before=previous?.actors.find(p=>p.actor_id===a.actor_id);
    const moved=!state.terminal&&!jump&&!!before&&Math.hypot(...a.position.map((v,i)=>v-before.position[i]))>1e-7;
    return [a.actor_id,{id:a.actor_id,role:a.role as Role,vehicleId:a.vehicle_id??undefined,pos:[...a.position],yaw:a.yaw_rad,cartYaw:a.yaw_rad,
     state:moved?'TRAVEL':'IDLE',operation:'',phase:0,pose:{jointRotations:{},rootOffset:[0,0,0],wheelAngle:0,lift:0}}];
   })),
   cargo:Object.fromEntries(sample.cargo.filter(c=>c.visible&&c.position!==null).map(c=>[c.handling_unit_id,{
    id:c.handling_unit_id,kind:'lot',orderIds:[],pos:[...c.position!],yaw:c.yaw_rad,visible:c.visible,stage:c.location.kind,attachment:{kind:'world'}
   }]))
  };
  sound.update(frame,{...state,discontinuity:!!jump},wall_s);
  previous=sample;return snapshot();
 }
 function snapshot(){return {...sound.getState(),at_s:previous?.at_s??null,crossed_completion_events:crossed,source_kind:'visual_fixture',engine_operation:false};}
 return {apply,snapshot,unlock:sound.unlock,setMuted:sound.setMuted,setVolume:sound.setVolume,stop:sound.stop,
  dispose(){if(disposed)return;sound.dispose();previous=undefined;disposed=true;}};
}
