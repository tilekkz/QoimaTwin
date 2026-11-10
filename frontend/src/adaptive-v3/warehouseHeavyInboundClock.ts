import type {WarehouseHeavyInboundPlan,HeavyInboundSample} from './warehouseHeavyInboundPlan';
import {isWarehouseHeavyInboundPlan} from './warehouseHeavyInboundPlan';

/** Explicit elapsed time, without a timer. Seeking/reset never performs an engine action. */
export function createWarehouseHeavyInboundClock(plan:WarehouseHeavyInboundPlan){
 if(!isWarehouseHeavyInboundPlan(plan))throw Error('INVALID_HEAVY_PLAN');
 let at=0,playing=false,rate=1,disposed=false;
 const usable=()=>{if(disposed)throw Error('HEAVY_INBOUND_CLOCK_DISPOSED');};
 function sample():Readonly<HeavyInboundSample>{usable();return plan.sample(at);}
 function seek(seconds:number){usable();if(!Number.isFinite(seconds))throw Error('INVALID_TIME');at=Math.max(0,Math.min(plan.duration_s,seconds));if(at===plan.duration_s)playing=false;return sample();}
 function advance(elapsed_s:number){usable();if(!Number.isFinite(elapsed_s)||elapsed_s<0)throw Error('INVALID_ELAPSED_TIME');return playing?seek(at+elapsed_s*rate):sample();}
 return Object.freeze({sample,seek,advance,play(){usable();if(at===plan.duration_s)at=0;playing=true;return sample();},pause(){usable();playing=false;return sample();},reset(){usable();playing=false;at=0;return sample();},setRate(value:number){usable();if(![.5,1,2,4].includes(value))throw Error('INVALID_RATE');rate=value;return sample();},snapshot(){usable();return Object.freeze({at_s:at,playing,rate,duration_s:plan.duration_s});},dispose(){disposed=true;playing=false;}});
}
