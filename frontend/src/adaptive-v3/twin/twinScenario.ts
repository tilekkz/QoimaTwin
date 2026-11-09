/**
 * Frozen demonstration episode for the A/B comparison page.
 * Source kind is always 'visual_fixture': these events are a staged showcase of the
 * cause → wave → recovery mechanism, never an engine run or a measured KPI.
 * Sampling is absolute in time, so seek/reset always restore the same states.
 */
import type {InitialCargo,V3Record,WarehouseBundle,WarehouseSlot,XYZ} from '../warehouseTypes';

export type AtmoState='control'|'danger'|'sos'|'nodata';
export type Variant='A'|'B';
export type AtmoEvent={at_s:number;zone_id:string;state:AtmoState;cause:string;from_zone_id?:string;resource_id?:string};
export type ZoneSample={state:AtmoState;cause:string;since_s:number};

export const DEMO_DURATION_S=240;
export const DEMO_SOURCE={source_kind:'visual_fixture',engine_operation:false,fixture_id:'v3:twin:packing-branch-overload:demo:001'} as const;

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
];
/** Process dependencies: storage/pick zones feed the light packing line. Waves may only travel along these. */
export const INFLUENCE_EDGES:[string,string][]=[
 ['SMALL_E','PACKING_LIGHT_LINE'],['STANDARD_E','PACKING_LIGHT_LINE'],
 ['SMALL_W','PACKING_LIGHT_LINE'],['STANDARD_W','PACKING_LIGHT_LINE'],
];
const CALM:Record<string,string>={
 PACKING_LIGHT_LINE:'Очередь на ветках в норме',STANDARD_E:'Отбор передаёт на линию вовремя',SMALL_E:'Отбор передаёт на линию вовремя',
 STANDARD_W:'Отбор передаёт на линию вовремя',SMALL_W:'Отбор передаёт на линию вовремя',HEAVY_W:'Независимый участок, свой погрузчик',
 HEAVY_E:'Независимый участок, свой погрузчик',LONG_W:'Независимый участок',LONG_E:'Независимый участок',STAGE_OUT_S_EXPRESS:'Ворота свободны',
};
const longRefusal:AtmoEvent[]=[
 {at_s:110,zone_id:'STAGE_OUT_S_EXPRESS',state:'danger',resource_id:'OUT_S_EXPRESS',cause:'Отказ: LONG_BUNDLE не допускается в ворота OUT_S_EXPRESS, там разрешены только SMALL и STANDARD'},
 {at_s:124,zone_id:'STAGE_OUT_S_EXPRESS',state:'control',resource_id:'OUT_E_B2B',cause:'Длинномер направлен в допустимые ворота OUT_E_B2B'},
];
export const DEMO_EVENTS:Record<Variant,readonly AtmoEvent[]>={
 A:[
  {at_s:30,zone_id:'PACKING_LIGHT_LINE',state:'danger',resource_id:'PK03',cause:'Очередь на ветку PK03 растёт'},
  {at_s:58,zone_id:'PACKING_LIGHT_LINE',state:'sos',resource_id:'PK03',cause:'PK03 недоступен, буфер его ветки заполнен'},
  {at_s:72,zone_id:'STANDARD_E',state:'danger',from_zone_id:'PACKING_LIGHT_LINE',cause:'Обратное давление: отбор ждёт свободную ячейку ветки'},
  {at_s:86,zone_id:'SMALL_E',state:'danger',from_zone_id:'PACKING_LIGHT_LINE',cause:'Обратное давление: отбор ждёт свободную ячейку ветки'},
  ...longRefusal,
  {at_s:150,zone_id:'PACKING_LIGHT_LINE',state:'danger',resource_id:'PK03',cause:'PK03 снова работает, очередь уходит'},
  {at_s:166,zone_id:'STANDARD_E',state:'control',from_zone_id:'PACKING_LIGHT_LINE',cause:'Ветка снова принимает передачи'},
  {at_s:176,zone_id:'SMALL_E',state:'control',from_zone_id:'PACKING_LIGHT_LINE',cause:'Ветка снова принимает передачи'},
  {at_s:200,zone_id:'PACKING_LIGHT_LINE',state:'control',resource_id:'PK03',cause:'Очередь ниже нижнего порога и держится'},
 ],
 B:[
  {at_s:30,zone_id:'PACKING_LIGHT_LINE',state:'danger',resource_id:'PK03',cause:'Очередь на ветку PK03 растёт'},
  {at_s:46,zone_id:'PACKING_LIGHT_LINE',state:'danger',resource_id:'PK05',cause:'Поток ветки PK03 переведён на свободный PK05'},
  {at_s:60,zone_id:'STANDARD_E',state:'danger',from_zone_id:'PACKING_LIGHT_LINE',cause:'Ветка почти полна, отбор ждёт'},
  {at_s:88,zone_id:'STANDARD_E',state:'control',from_zone_id:'PACKING_LIGHT_LINE',cause:'Ветка разгружается'},
  {at_s:104,zone_id:'PACKING_LIGHT_LINE',state:'control',resource_id:'PK05',cause:'Очередь ниже нижнего порога и держится'},
  ...longRefusal,
 ],
};
export const CHAPTERS:{at_s:number;label:string}[]=[
 {at_s:0,label:'Контроль'},{at_s:30,label:'Очередь растёт'},{at_s:58,label:'SOS у PK03'},{at_s:72,label:'Волна назад'},
 {at_s:104,label:'B в контроле'},{at_s:110,label:'Отказ LONG'},{at_s:150,label:'Восстановление A'},
];

/** Defence walk-through: 3–5 minutes, each step restores the same absolute state (time, mode, camera). */
export type PresenterStep={title:string;text:string;t:number;mode:'side'|'swipe';focus:{target:XYZ;span:number};sheet?:'now'|'diff'|'source';play?:boolean;
 /** Scenario card (N0–N4) to open on this step: its zones are outlined and framed. */
 scenario?:string};
const OVERVIEW={target:[72,1.5,36] as XYZ,span:184};
export const PRESENTER_STEPS:PresenterStep[]=[
 {title:'Склад 144 × 72 м',text:'530 грузовых единиц восьми типов, 132 модуля хранения, 24 работника, три входа и три выхода. Слева склад как сейчас, справа — после перестройки.',t:0,mode:'side',focus:OVERVIEW},
 {title:'Спокойная смена',text:'Все участки справляются с потоком. Зелёный значит под контролем: активных ограничений нет.',t:12,mode:'side',focus:OVERVIEW,play:true},
 {title:'Очередь у поста PK03',text:'Очередь на ветку PK03 растёт, и упаковка переходит в «Опасность». Сначала меняется только источник проблемы.',t:34,mode:'side',focus:{target:[91,0,5],span:40}},
 {title:'SOS и волна назад',text:'PK03 недоступен, буфер ветки заполнен. Давление идёт назад по связям процесса: отбор STANDARD и SMALL на востоке начинает ждать. Независимые зоны остаются зелёными.',t:88,mode:'side',focus:OVERVIEW,sheet:'now'},
 {title:'Отказ длинномера — локально',text:'Длинномер нельзя отгрузить через OUT_S_EXPRESS: там разрешены только SMALL и STANDARD. Отказ виден только у этих ворот и не окрашивает весь склад.',t:114,mode:'side',focus:{target:[30,0,8],span:48}},
 {title:'Что меняет перестройка',text:'B показывает допустимые адреса ближе к исходящим воротам. Числа переносов — расстояния по прямой; физические переносы, ожидание ресурсов и их время здесь не выполняются.',t:104,mode:'side',focus:OVERVIEW,sheet:'diff'},
 {title:'B возвращается раньше',text:'После перестройки поток PK03 уходит на свободный PK05, и упаковка возвращается в контроль к 01:44. Без перестройки — только к 03:20.',t:110,mode:'swipe',focus:OVERVIEW},
 {title:'Что дальше: сценарии N0–N4',text:'Для N0 и N1 входы зафиксированы. Тяжёлая приёмка и длинномер имеют отдельный пакет физических интерфейсов. В каталоге работников доступна учебная проверка смены роли с путём и возвратом. Расчёта эффективности ещё нет.',t:240,mode:'side',focus:OVERVIEW,sheet:'source',scenario:'N1'},
 {title:'Честный вывод',text:'Это демонстрационный эпизод: он показывает механизм «причина → волна → решение → восстановление». Числа эффективности появятся, когда подключим расчётный движок.',t:240,mode:'side',focus:OVERVIEW,sheet:'source'},
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
  if(z.state==='sos')order.forEach((id,i)=>out.push({actor_id:id,zone_id:zone,bubble:i===0?'alert':i===1?'help':i===2?'question':'wait',text:i===0?`Сигналит: ${z.cause}`:i===1?'Зовёт помощь: ресурс заблокирован':i===2?'Разбирается, что с ресурсом':`Ждёт: ${z.cause}`,priority:30-i}));
  else if(z.state==='danger')order.forEach((id,i)=>out.push({actor_id:id,zone_id:zone,bubble:i%3===2?'question':'wait',text:i%3===2?`Разбирается: ${z.cause}`:`Ждёт: ${z.cause}`,priority:20-i}));
  else if(z.state==='control'&&z.since_s>0&&t-z.since_s<=RELIEF_S&&previousState(variant,zone,z.since_s)!=='control')
   order.slice(0,Math.max(1,Math.ceil(order.length/3))).forEach((id,i)=>out.push({actor_id:id,zone_id:zone,bubble:'relief',text:`Снова в ритме: ${z.cause}`,priority:10-i}));
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
