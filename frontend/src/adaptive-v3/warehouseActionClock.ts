import {WarehouseActionError,isWarehouseActionTimeline,warehouseActionTimelineCatalogue,type WarehouseActionTimeline,type WarehouseActionEvent} from './warehouseActionTimeline';

/** Deterministic host-driven visual clock. No RAF, audio, geometry, inventory or job completion effects. */
export function createWarehouseActionClock(initial:WarehouseActionTimeline){
 if(!isWarehouseActionTimeline(initial))throw new WarehouseActionError('INVALID_TIMELINE','Нужна зарегистрированная временная шкала V3.');
 const catalogue=warehouseActionTimelineCatalogue(initial);let timeline=initial,at=0,playing=false,speed=1,disposed=false;
 function live(){if(disposed)throw new WarehouseActionError('CLOCK_DISPOSED','Просмотр временной шкалы остановлен.');}
 function frame(crossed_events:WarehouseActionEvent[]=[]){return Object.freeze({...timeline.sample(at),crossed_events:Object.freeze(crossed_events),playing,speed,disposed});}
 function getState(){return Object.freeze({at_s:at,duration_s:timeline.duration_s,playing,speed,disposed,timeline_id:timeline.timeline_id,source_kind:'visual_fixture' as const,engine_operation:false as const,operational_admission:false as const,physical_join:false as const,completed_jobs:0 as const});}
 function play(){live();playing=at<timeline.duration_s;return frame();}
 function pause(){live();playing=false;return frame();}
 function setSpeed(value:number){live();if(!Number.isFinite(value)||value<=0||value>60)throw new WarehouseActionError('INVALID_SPEED','Скорость должна быть больше 0 и не выше 60.');speed=value;return frame();}
 function seek(value:number){live();if(!Number.isFinite(value))throw new WarehouseActionError('INVALID_TIME','Некорректное время просмотра.');at=Math.max(0,Math.min(timeline.duration_s,value));if(at===timeline.duration_s)playing=false;return frame();}
 function reset(){live();at=0;playing=false;return frame();}
 function advance(delta:number){live();if(!Number.isFinite(delta)||delta<0)throw new WarehouseActionError('INVALID_ADVANCE','Шаг часов должен быть конечным неотрицательным числом.');if(!playing||delta===0)return frame();const before=at;at=Math.min(timeline.duration_s,at+delta*speed);if(at===timeline.duration_s)playing=false;return frame(timeline.eventsBetween(before,at));}
 function setTimeline(next:WarehouseActionTimeline){live();if(!isWarehouseActionTimeline(next))throw new WarehouseActionError('INVALID_TIMELINE','Нужна зарегистрированная временная шкала V3.');if(warehouseActionTimelineCatalogue(next)!==catalogue)throw new WarehouseActionError('TIMELINE_SOURCE_MISMATCH','Новая шкала относится к другому исходному каталогу.');timeline=next;at=0;playing=false;return frame();}
 function dispose(){if(disposed)return;playing=false;disposed=true;}
 return Object.freeze({play,pause,setSpeed,seek,reset,advance,setTimeline,getState,getFrame:()=>frame(),getTimeline:()=>timeline,dispose});
}
