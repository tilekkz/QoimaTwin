import {isWarehouseScenarioPlan,type WarehouseScenarioPlan} from './warehouseScenarioExecution';

/** One absolute visual clock; no timer and no engine-side event effects. */
export function createWarehouseScenarioClock(plan:WarehouseScenarioPlan){
 if(!isWarehouseScenarioPlan(plan))throw Error('ISSUED_SCENARIO_PLAN_REQUIRED');
 let at=0,playing=false,rate=1,disposed=false;
 const live=()=>{if(disposed)throw Error('SCENARIO_CLOCK_DISPOSED');};
 const sample=()=>{live();return plan.sample(at);};
 function seek(seconds:number){live();if(!Number.isFinite(seconds))throw Error('INVALID_SCENARIO_TIME');at=Math.max(0,Math.min(plan.duration_s,seconds));if(at===plan.duration_s)playing=false;return sample();}
 return Object.freeze({sample,seek,advance(elapsed_s:number){live();if(!Number.isFinite(elapsed_s)||elapsed_s<0)throw Error('INVALID_SCENARIO_ELAPSED');return playing?seek(at+elapsed_s*rate):sample();},play(){live();if(at===plan.duration_s)at=0;playing=true;return sample();},pause(){live();playing=false;return sample();},reset(){live();playing=false;at=0;return sample();},setRate(value:number){live();if(![.5,1,2,4,10,30,60].includes(value))throw Error('INVALID_SCENARIO_RATE');rate=value;return sample();},snapshot(){live();return Object.freeze({at_s:at,playing,rate,duration_s:plan.duration_s,disposed:false});},dispose(){playing=false;disposed=true;}});
}
