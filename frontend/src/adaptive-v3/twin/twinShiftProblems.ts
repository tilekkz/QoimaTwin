import type {AtmoState,Variant} from './twinScenario';

/** Authored incidents, never engine output. The geometry and incoming jobs are shared;
 * the delay, urgency and recovery are explicitly staged for the defence. */
export type ShiftProblem={id:string;start:number;end:number;zone:string;state:AtmoState;title:string;cause:string;calm:string;kind:'late-truck'|'gate-queue'|'blocked'|'replenishment'|'jam'|'packing'|'slot-fit'|'late-order'};
export const SHIFT_DURATION_S=1800;
export const SHIFT_PROBLEMS:readonly ShiftProblem[]=[
 {id:'late-inbound',start:0,end:150,zone:'STAGE_IN_N_W',state:'danger',title:'Опаздывает машина',cause:'Машина приёмки опаздывает; бригада ждёт поставку',calm:'Приёмка идёт по окнам; бригада разгружает без спешки',kind:'late-truck'},
 {id:'gate-queue',start:20,end:280,zone:'STAGE_IN_W_BULK',state:'sos',title:'Затор у ворот',cause:'Паллеты заняли буфер приёмки; следующая машина ждёт снаружи',calm:'Паллеты сразу уходят из приёмки в свободный маршрут',kind:'gate-queue'},
 {id:'belt-jam',start:58,end:230,zone:'PACKING_LIGHT_LINE',state:'sos',title:'Конвейер остановлен',cause:'Затор ветки PK03: коробки остановились, упаковка не успевает',calm:'Поток равномерно распределён по упаковочным постам',kind:'jam'},
 {id:'pick-overload',start:72,end:320,zone:'SMALL_E',state:'sos',title:'Отбор перегружен',cause:'Срочный отбор: комплектовщики спешат, тележки ждут передачи',calm:'Тот же поток заказов: ровная ходьба и короткие остановки у ячеек',kind:'replenishment'},
 {id:'forklift-block',start:160,end:390,zone:'HEAVY_W',state:'danger',title:'Погрузчик перекрыл проезд',cause:'Погрузчик ждёт свободный буфер; паллета задерживает движение в проезде',calm:'Погрузчики последовательно проходят свободные проезды',kind:'blocked'},
 {id:'packing-crew',start:300,end:520,zone:'PACKING_LIGHT_LINE',state:'sos',title:'Не хватает упаковщиков',cause:'Два упаковщика ждут помощь; коробки и тележки накапливаются',calm:'Упаковщики работают в ровном ритме, передача без очереди',kind:'packing'},
 {id:'replenishment',start:420,end:680,zone:'STANDARD_W',state:'danger',title:'Ждут пополнение',cause:'Отбор ждёт пополнение: «жду погрузчик», «не успеваю»',calm:'Пополнение доставляется между очередными заданиями',kind:'replenishment'},
 {id:'oversize',start:600,end:850,zone:'LONG_E',state:'sos',title:'Груз не входит в ячейку',cause:'Негабаритная демо-паллета остановлена перед стеллажом; адрес не подходит',calm:'Габариты демо-груза проверены до подачи к стеллажу',kind:'slot-fit'},
 {id:'late-orders',start:900,end:1120,zone:'STAGE_OUT_S_EXPRESS',state:'sos',title:'Заказы к рейсу опоздали',cause:'Отправка ждёт отбор и упаковку; очередь заказов просрочена',calm:'Заказы передаются к рейсу в своих временных окнах',kind:'late-order'},
 {id:'second-wave',start:1200,end:1800,zone:'STAGE_OUT_E_B2B',state:'danger',title:'Вторая волна отгрузки',cause:'Буфер отгрузки перегружен: «нет места», очередь остаётся до конца демо-смены',calm:'Вторая волна уходит последовательно, буфер остаётся свободным',kind:'gate-queue'},
];
export function shiftProblemActive(kind:ShiftProblem['kind'],variant:Variant,t:number){
 if(variant==='B')return false;for(const p of SHIFT_PROBLEMS)if(p.kind===kind&&t>=p.start&&(t<p.end||t===SHIFT_DURATION_S&&p.end===SHIFT_DURATION_S))return true;return false;
}
export function shiftProblemEvents(variant:Variant){
 // Late dispatch explicitly waits for packing; retain that provenance for the UI's «why» link.
 return SHIFT_PROBLEMS.flatMap(p=>variant==='A'?[{at_s:p.start,zone_id:p.zone,state:p.state,cause:p.cause,...(p.kind==='late-order'?{from_zone_id:'PACKING_LIGHT_LINE'}:{})},...(p.end<SHIFT_DURATION_S?[{at_s:p.end,zone_id:p.zone,state:'control' as const,cause:'Участок восстановился после задержки: '+p.title.toLowerCase()}]:[])]:[{at_s:p.start,zone_id:p.zone,state:'control' as const,cause:p.calm}]).sort((a,b)=>a.at_s-b.at_s);
}
