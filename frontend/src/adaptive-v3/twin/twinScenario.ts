/**
 * Frozen demonstration episode for the A/B comparison page.
 * Source kind is always 'visual_fixture': these events are a staged showcase of the
 * cause → wave → recovery mechanism, never an engine run or a measured KPI.
 * Sampling is absolute in time, so seek/reset always restore the same states.
 */
import type {InitialCargo,V3Record,WarehouseBundle,WarehouseSlot,XYZ} from '../warehouseTypes';
import {SHIFT_DURATION_S,SHIFT_PROBLEMS,shiftProblemEvents} from './twinShiftProblems';

export type AtmoState='control'|'danger'|'sos'|'nodata';
export type Variant='A'|'B';
export type AtmoEvent={at_s:number;zone_id:string;state:AtmoState;cause:string;from_zone_id?:string;resource_id?:string};
export type ZoneSample={state:AtmoState;cause:string;since_s:number};

export const DEMO_DURATION_S=SHIFT_DURATION_S;
export const DEMO_SOURCE={source_kind:'visual_fixture',engine_operation:false,fixture_id:'v3:twin:busy-shift:demo:001'} as const;

/** Layout zone IDs from layout-manifest.json; labels are for people. */
export const ATMO_ZONES:{id:string;label:string}[]=[
 {id:'PACKING_LIGHT_LINE',label:'Упаковка и линия'},
 {id:'STANDARD_E',label:'STANDARD восток'},
 {id:'SMALL_E',label:'SMALL восток'},
 {id:'STANDARD_W',label:'STANDARD запад'},
 {id:'SMALL_W',label:'SMALL запад'},
 {id:'HEAVY_W',label:'HEAVY запад'},
 {id:'HEAVY_E',label:'HEAVY восток'},
 {id:'LONG_W',label:'LONG запад'},
 {id:'LONG_E',label:'LONG восток'},
 {id:'STAGE_OUT_S_EXPRESS',label:'Экспресс-отгрузка'},
 {id:'STAGE_IN_W_BULK',label:'Приёмка запад'},
 {id:'STAGE_IN_N_W',label:'Приёмка север'},
 {id:'STAGE_IN_E_PARCEL',label:'Приёмка посылок'},
 {id:'STAGE_OUT_W_RETAIL',label:'Розничная отгрузка'},
 {id:'STAGE_OUT_E_B2B',label:'Отгрузка B2B'},
];
/** Process dependencies: picking feeds packing, then express dispatch. Waves only travel along these. */
export const INFLUENCE_EDGES:[string,string][]=[
 ['SMALL_E','PACKING_LIGHT_LINE'],['STANDARD_E','PACKING_LIGHT_LINE'],
 ['SMALL_W','PACKING_LIGHT_LINE'],['STANDARD_W','PACKING_LIGHT_LINE'],
 ['PACKING_LIGHT_LINE','STAGE_OUT_S_EXPRESS'],
];
const CALM:Record<string,string>={
 PACKING_LIGHT_LINE:'Очередь на ветках в норме',STANDARD_E:'Отбор передаёт на линию вовремя',SMALL_E:'Отбор передаёт на линию вовремя',
 STANDARD_W:'Отбор передаёт на линию вовремя',SMALL_W:'Отбор передаёт на линию вовремя',HEAVY_W:'Независимый участок, свой погрузчик',
 HEAVY_E:'Независимый участок, свой погрузчик',LONG_W:'Независимый участок',LONG_E:'Независимый участок',STAGE_OUT_S_EXPRESS:'Ворота свободны',
};
export const DEMO_EVENTS:Record<Variant,readonly AtmoEvent[]>={
 A:shiftProblemEvents('A'),B:shiftProblemEvents('B'),
};
export const CHAPTERS:{at_s:number;label:string}[]=[
 ...SHIFT_PROBLEMS.map(p=>({at_s:p.start,label:p.title})),{at_s:1500,label:'Очередь к концу смены'},
];

/** Defence walk-through: 3–5 minutes, each step restores the same absolute state (time, mode, camera). */
export type PresenterStep={title:string;text:string;t:number;mode:'side'|'swipe';focus:{target:XYZ;span:number};sheet?:'now'|'diff'|'source';play?:boolean;
 /** Scenario card (N0–N4) to open on this step: its zones are outlined and framed. */
 scenario?:string};
const OVERVIEW={target:[72,1.5,36] as XYZ,span:184};
export const PRESENTER_STEPS:PresenterStep[]=[
 {title:'Два склада · одна нагрузка',text:'Склад 144 × 72 м, исходные 530 ГЕ и 24 работника сохранены. Дополнительная бригада, техника и груз относятся к насыщенной демонстрационной смене.',t:0,mode:'side',focus:OVERVIEW,play:true},
 {title:'A спешит · B работает спокойно',text:'Один поток демо-заказов и одна шкала. В A люди торопятся и ждут ресурсы; в B идут спокойно. Темп, задержки и сроки заданы сценарием, а длины путей считаются по геометрии.',t:85,mode:'side',focus:OVERVIEW,sheet:'now'},
 {title:'Приёмка и затор у ворот',text:'В A поздняя машина и паллеты в буфере задерживают приёмку. В B грузы подаются последовательно. Дополнительные паллеты и машины — демонстрационные.',t:100,mode:'side',focus:{target:[24,0,16],span:48}},
 {title:'Линия остановилась',text:'В A конвейер и коробки стоят во время затора; у работников появляются сигналы ожидания. В B тот же входной поток продолжает движение.',t:120,mode:'swipe',focus:{target:[93,0,8],span:64}},
 {title:'Проезд и упаковка',text:'Погрузчик ждёт буфер в A, позже упаковка просит помощь. Выберите проблему в «Состоянии», чтобы увидеть её участок и причины.',t:335,mode:'side',focus:{target:[58,0,16],span:96},sheet:'now'},
 {title:'Пополнение и негабарит',text:'Отбор ждёт пополнение, а негабаритная демо-паллета остаётся перед стеллажом. B показывает спокойную обработку, без этих постановочных задержек.',t:660,mode:'side',focus:{target:[72,0,36],span:96}},
 {title:'Не успели к рейсу',text:'В A накапливаются ожидающие задания и просрочки. Все счётчики считаются из демо-заданий; это не результаты расчётного движка.',t:950,mode:'side',focus:{target:[30,0,8],span:50},sheet:'now'},
 {title:'Геометрия и демонстрация',text:'Дистанции A и B рассчитаны по маршрутам. Темп, очереди и сроки — постановка для объяснения работы склада. Сценарии N0–N4 и исходные факты доступны отдельно.',t:1500,mode:'side',focus:OVERVIEW,sheet:'source'},
];

export function sampleAtmosphere(variant:Variant,t:number):Record<string,ZoneSample>{
 const out:Record<string,ZoneSample>={};
 for(const z of ATMO_ZONES)out[z.id]={state:'control',cause:CALM[z.id]??'',since_s:0};
 for(const e of DEMO_EVENTS[variant])if(e.at_s<=t&&out[e.zone_id])out[e.zone_id]={state:e.state,cause:e.cause,since_s:e.at_s};
 return out;
}
/** Wave pulses that are in flight at t: they run for `window_s` before the receiving zone changes. */
export function activePulses(variant:Variant,t:number,window_s=8){
 return DEMO_EVENTS[variant].filter(e=>e.from_zone_id&&t>=e.at_s-window_s&&t<=e.at_s)
  .map(e=>({from:e.from_zone_id!,to:e.zone_id,state:e.state,progress:(t-(e.at_s-window_s))/window_s}));
}
export function stateSegments(variant:Variant,zone:string){
 const out:{from_s:number;to_s:number;state:AtmoState}[]=[];let from=0,state:AtmoState='control';
 for(const e of DEMO_EVENTS[variant].filter(e=>e.zone_id===zone)){if(e.state!==state){out.push({from_s:from,to_s:e.at_s,state});from=e.at_s;state=e.state;}}
 out.push({from_s:from,to_s:DEMO_DURATION_S,state});return out;
}
export function eventsUpTo(variant:Variant,t:number){return DEMO_EVENTS[variant].filter(e=>e.at_s<=t);}
/** "Why is this zone here?": its own events up to t, oldest first, each with the zone the wave came from. */
export function zoneHistory(variant:Variant,zone:string,t:number){
 return DEMO_EVENTS[variant].filter(e=>e.zone_id===zone&&e.at_s<=t).map(e=>({at_s:e.at_s,state:e.state,cause:e.cause,from_id:e.from_zone_id??null,from:e.from_zone_id?ATMO_ZONES.find(z=>z.id===e.from_zone_id)?.label??e.from_zone_id:null}));
}
/** Zones back in Контроль at t after having been in trouble earlier in the episode. */
export function recoveredZones(variant:Variant,t:number){
 const s=sampleAtmosphere(variant,t);
 return ATMO_ZONES.map(z=>z.id).filter(id=>s[id].state==='control'&&DEMO_EVENTS[variant].some(e=>e.zone_id===id&&e.at_s<=t&&e.state!=='control'));
}

/** Demonstration slotting idea for B: pre-place each outbound HU in a free slot nearer its outbound port.
 * Returns ranked candidates only; the page must pass every move through the real cargo admission. */
export type MoveCandidate={hu:InitialCargo;port_id:string;from_slot:string;before_m:number;candidates:{slot_id:string;after_m:number;move_m:number}[]};
const flat=(a:XYZ,b:XYZ)=>Math.hypot(a[0]-b[0],a[2]-b[2]);
export function outboundCandidates(bundle:WarehouseBundle,minGain_m=10,limit=12):MoveCandidate[]{
 const ports=new Map((bundle.layout.data.ports as V3Record[]).map(p=>[p.port_id as string,p.world_pos as XYZ]));
 const slots=new Map(bundle.layout.slots.map(s=>[s.slot_id,s]));
 const occupied=new Set(bundle.fixture.inputs.initial_stock.map(h=>h.location.slot_id));
 const at=(s:WarehouseSlot)=>bundle.layout.modules[s.module_index].world_pos;
 const free=bundle.layout.slots.filter(s=>!occupied.has(s.slot_id)&&!s.reserve_only&&!s.retrieval_blocked);
 const out:MoveCandidate[]=[];
 for(const r of bundle.fixture.inputs.requests){
  if(r.direction!=='outbound'||r.initial_location_kind!=='storage_slot')continue;
  const hu=bundle.fixture.inputs.initial_stock.find(h=>h.handling_unit_id===r.handling_unit_id),port=ports.get(r.port_id);
  const from=hu&&slots.get(hu.location.slot_id);if(!hu||!port||!from)continue;
  const before=flat(at(from),port);
  const candidates=free.map(s=>({slot_id:s.slot_id,after_m:flat(at(s),port),move_m:flat(at(s),at(from))}))
   .filter(c=>c.after_m<=before-minGain_m).sort((a,b)=>a.after_m-b.after_m||a.slot_id.localeCompare(b.slot_id)).slice(0,limit);
  out.push({hu,port_id:r.port_id,from_slot:from.slot_id,before_m:before,candidates});
 }
 return out;
}

/* ---------- worker reactions ----------
 * Which workers show a thought bubble at time t, and why. Pure and absolute in t (same answer after any seek);
 * variety comes from a stable hash of actor ID + zone interval, never per-frame randomness.
 * Reactions are presentation only: they never change cargo, durations or any measured result. */
export type Bubble='wait'|'question'|'alert'|'help'|'relief';
export type WorkerSpot={actor_id:string;zone_id:string|null};
export type Reaction={actor_id:string;zone_id:string;bubble:Bubble;text:string;priority:number};
export type Effects='full'|'calm'|'off';

/** Seconds a positive reaction stays after a zone returns to Контроль. */
export const RELIEF_S=10;
/** Desktop / phone budgets from the atmosphere spec; 'calm' halves them. */
export function bubbleBudget(effects:Effects,phone:boolean){if(effects==='off')return 0;const n=phone?3:6;return effects==='calm'?Math.ceil(n/2):n;}

export const BUBBLE_RU:Record<Bubble,string>={wait:'Ждёт',question:'Разбирается',alert:'Сигналит о проблеме',help:'Зовёт помощь',relief:'Снова в ритме'};

function hash(s:string){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return h>>>0;}

/** Previous state of a zone before its current interval (for "relief after trouble"). */
function previousState(variant:Variant,zone:string,since:number):AtmoState{
 let prev:AtmoState='control';for(const e of DEMO_EVENTS[variant])if(e.zone_id===zone&&e.at_s<since)prev=e.state;return prev;
}

/** All candidate reactions at t, highest priority first. Workers outside atmosphere zones never react. */
export function reactionsAt(variant:Variant,t:number,workers:readonly WorkerSpot[]):Reaction[]{
 const sample=sampleAtmosphere(variant,t),out:Reaction[]=[];
 const byZone=new Map<string,string[]>();
 for(const w of workers)if(w.zone_id&&sample[w.zone_id])byZone.set(w.zone_id,[...(byZone.get(w.zone_id)??[]),w.actor_id]);
 for(const [zone,ids]of byZone){
  const z=sample[zone],seed=`${variant}:${zone}:${z.since_s}`;
  // Stable order inside the zone for this interval: decides who signals, who asks, who waits.
  const order=[...ids].sort((a,b)=>hash(seed+a)-hash(seed+b)||a.localeCompare(b));
  if(z.state==='sos')order.forEach((id,i)=>out.push({actor_id:id,zone_id:zone,bubble:i===0?'alert':i===1?'help':i===2?'question':'wait',text:i===0?`Не успеваю: ${z.cause}`:i===1?'Нужна помощь, нет места':i===2?'Жду погрузчик':`Ждёт: ${z.cause}`,priority:30-i}));
  else if(z.state==='danger')order.forEach((id,i)=>out.push({actor_id:id,zone_id:zone,bubble:i%3===2?'question':'wait',text:i%3===2?`Разбирается: ${z.cause}`:`Ждёт: ${z.cause}`,priority:20-i}));
  else if(z.state==='control'&&z.since_s>0&&t-z.since_s<=RELIEF_S&&previousState(variant,zone,z.since_s)!=='control')
   order.slice(0,Math.max(1,Math.ceil(order.length/3))).forEach((id,i)=>out.push({actor_id:id,zone_id:zone,bubble:'relief',text:`Снова в ритме: ${z.cause}`,priority:10-i}));
  else if(variant==='B')order.slice(0,1).forEach(id=>out.push({actor_id:id,zone_id:zone,bubble:'relief',text:'Без спешки: всё по плану · демонстрационная смена',priority:5}));
 }
 return out.sort((a,b)=>b.priority-a.priority||a.actor_id.localeCompare(b.actor_id));
}

/** Applies the effect budget. Zones take turns (most urgent first) so a wave stays visible beyond its source;
 *  the selected worker always keeps its bubble. */
export function visibleReactions(all:readonly Reaction[],budget:number,selected:string|null){
 if(budget<=0)return [];
 const sel=all.find(r=>r.actor_id===selected),byZone=new Map<string,Reaction[]>();
 for(const r of all)if(r!==sel)byZone.set(r.zone_id,[...(byZone.get(r.zone_id)??[]),r]);
 const out=sel?[sel]:[],queues=[...byZone.values()];
 for(let i=0;out.length<budget&&queues.some(q=>i<q.length);i++)for(const q of queues)if(q[i]&&out.length<budget)out.push(q[i]);
 return out;
}

/** Plain-language status for the worker card; computed over all workers so it matches the bubble. */
export function workerStatus(variant:Variant,t:number,workers:readonly WorkerSpot[],actor_id:string){
 if(!workers.find(w=>w.actor_id===actor_id)?.zone_id)return 'Вне участков эпизода, обычный ритм';
 return reactionsAt(variant,t,workers).find(r=>r.actor_id===actor_id)?.text??'Спокойно: участок под контролем';
}
