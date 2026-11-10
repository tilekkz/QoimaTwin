import {adaptWarehouseV3,type WarehouseTexts} from './warehouseAdapter';
import {checkVisualWorkerCapability} from './workerProfiles';
import {holderByDestination,isCargoHolderCatalogue,type CargoHolderCatalogue} from './warehouseCargoHolders';
import supportBindings from './warehouseSupportBindings.json';
import type {RoleClip} from './workerRegistry';
import type {WarehouseBundle,V3Record} from './warehouseTypes';

export type ActionTimelineReason='INVALID_BUNDLE'|'INVALID_REQUEST'|'INVALID_CATALOGUE'|'INVALID_HOLDER_CATALOGUE'|'SOURCE_UNAVAILABLE'|'SOURCE_HASH_MISMATCH'|'SOURCE_BUNDLE_MISMATCH'|'UNKNOWN_CLIP'|'UNKNOWN_ACTOR'|'ROLE_NOT_ELIGIBLE'|'RESOURCE_REQUIRED'|'UNKNOWN_RESOURCE'|'RESOURCE_UNAVAILABLE'|'RESOURCE_NOT_ALLOWED'|'VEHICLE_PAIR_MISMATCH'|'INVALID_INTERVAL'|'CLIP_DURATION_MISMATCH'|'DUPLICATE_ACTION'|'INVALID_DEPENDENCY'|'DEPENDENCY_CYCLE'|'DEPENDENCY_NOT_FINISHED'|'RESOURCE_CAPACITY_EXCEEDED'|'INVALID_TIME'|'INVALID_TIMELINE'|'TIMELINE_SOURCE_MISMATCH'|'INVALID_SPEED'|'INVALID_ADVANCE'|'CLOCK_DISPOSED';
const scope={source_kind:'visual_fixture' as const,engine_operation:false as const,operational_admission:false as const,physical_join:false as const,cost_evaluated:false as const,completed_jobs:0 as const};
export class WarehouseActionError extends Error{
 constructor(readonly reason:ActionTimelineReason,message:string,readonly action_id:string|null=null,readonly resource_id:string|null=null){super(message);this.name='WarehouseActionError';}
}
export type ActionResource={resource_id:string;kind:'actor'|'vehicle'|'cart'|'post'|'HU';canonical_id:string;capacity:1;available:boolean};
export type WarehouseActionCatalogue={source_kind:'visual_fixture';engine_operation:false;operational_admission:false;physical_join:false;fixture_id:string;layout_content_hash:string;clips:RoleClip[];resources:ActionResource[];source_hashes:Record<string,string>;counts:{actors:24;vehicles:2;posts:6;carts:0|1;handling_units:530};scope:string};
export type WarehouseActionRequest={action_id:string;actor_id:string;clip_id:string;start_s:number;end_s:number;depends_on:string[];vehicle_id:string|null;cart_id:string|null;post_id:string|null;handling_unit_id:string|null};
export type CompiledWarehouseAction=WarehouseActionRequest&{clip:RoleClip;claims:{resource_id:string;quantity:1}[];skill_level:number;role_transition_required:boolean;native_admission_required:true;cargo_admission_required:boolean};
export type WarehouseActionEvent={at_s:number;kind:'interval_start'|'interval_end';action_id:string;actor_id:string};
export type WarehouseActionSample={source_kind:'visual_fixture';engine_operation:false;operational_admission:false;physical_join:false;cost_evaluated:false;completed_jobs:0;at_s:number;duration_s:number;active:(CompiledWarehouseAction&{local_clip_time_s:number})[];events_at_time:WarehouseActionEvent[]};
export type WarehouseActionTimeline={source_kind:'visual_fixture';engine_operation:false;operational_admission:false;physical_join:false;cost_evaluated:false;completed_jobs:0;timeline_id:string;fixture_id:string;duration_s:number;actions:CompiledWarehouseAction[];events:WarehouseActionEvent[];calendars:{resource:ActionResource;intervals:{action_id:string;start_s:number;end_s:number;quantity:1}[]}[];sample:(at_s:number)=>WarehouseActionSample;eventsBetween:(from_s:number,to_s:number)=>WarehouseActionEvent[]};
export type WarehouseActionCompilation={ok:boolean;reason:'TIMELINE_OK'|ActionTimelineReason;message:string;action_id:string|null;resource_id:string|null;source_kind:'visual_fixture';engine_operation:false;operational_admission:false;physical_join:false;cost_evaluated:false;completed_jobs:0;timeline:WarehouseActionTimeline|null};
type CatalogueState={bundle:WarehouseBundle;verifiedBundle:WarehouseBundle;resources:Map<string,ActionResource>;clips:Map<string,RoleClip>};
const catalogues=new WeakMap<object,CatalogueState>(),timelines=new WeakMap<object,WarehouseActionCatalogue>();
const object=(v:unknown):v is V3Record=>!!v&&typeof v==='object'&&!Array.isArray(v)&&[Object.prototype,null].includes(Object.getPrototypeOf(v));
const keys=(v:V3Record,names:string[])=>Object.keys(v).length===names.length&&names.every(n=>Object.hasOwn(v,n));
const id=(v:unknown):v is string=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9:_-]{0,199}$/.test(v);
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const compare=(a:string,b:string)=>a<b?-1:a>b?1:0;
function freeze<T>(v:T):T{if(v&&typeof v==='object'&&!Object.isFrozen(v)){for(const child of Object.values(v))freeze(child);Object.freeze(v);}return v;}
/** Read-only JSON-tree check: never freeze foreign input or invoke an accessor. */
function deeplyImmutable(value:unknown):boolean{
 const visiting=new WeakSet<object>(),visited=new WeakSet<object>(),stack:{value:unknown;leave?:boolean}[]=[{value}];
 try{while(stack.length){const entry=stack.pop()!,current=entry.value;if(current===null)continue;
   if(typeof current!=='object'){if(!['string','boolean','number'].includes(typeof current)||typeof current==='number'&&!Number.isFinite(current))return false;continue;}
   if(entry.leave){visiting.delete(current);visited.add(current);continue;}if(visited.has(current))continue;if(visiting.has(current)||!Object.isFrozen(current))return false;
   const prototype=Object.getPrototypeOf(current);if(Array.isArray(current)?prototype!==Array.prototype:prototype!==Object.prototype&&prototype!==null)return false;
   const descriptors=Object.getOwnPropertyDescriptors(current);if(Reflect.ownKeys(descriptors).some(key=>typeof key!=='string'))return false;
   visiting.add(current);stack.push({value:current,leave:true});for(const descriptor of Object.values(descriptors)){if(!Object.hasOwn(descriptor,'value'))return false;stack.push({value:descriptor.value});}
  }return true;}catch{return false;}
}
const acceptedSupportBindings=freeze(structuredClone(supportBindings));
function reject(reason:ActionTimelineReason,message:string,action_id:string|null=null,resource_id:string|null=null):never{throw new WarehouseActionError(reason,message,action_id,resource_id);}
const sha=async(bytes:Uint8Array)=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes as BufferSource))].map(n=>n.toString(16).padStart(2,'0')).join('');
const baseFiles={fixture:'frontend/public/data/v3/warehouse-fixture-v3.json',layout:'frontend/public/data/adaptive-v3/layout-manifest.json',registry:'frontend/public/data/v3/worker-registry-v3.json',profiles:'frontend/public/data/v3/worker-profiles-v3.json'} as const;
export function isWarehouseActionCatalogue(value:unknown,bundle?:WarehouseBundle):value is WarehouseActionCatalogue{return !!value&&typeof value==='object'&&catalogues.has(value)&&(!bundle||catalogues.get(value)!.bundle===bundle);}
export function isWarehouseActionTimeline(value:unknown,catalogue?:WarehouseActionCatalogue):value is WarehouseActionTimeline{return !!value&&typeof value==='object'&&timelines.has(value)&&(!catalogue||timelines.get(value)===catalogue);}
export function warehouseActionTimelineCatalogue(timeline:WarehouseActionTimeline){if(!isWarehouseActionTimeline(timeline))return reject('INVALID_TIMELINE','Нужна зарегистрированная временная шкала V3.');return timelines.get(timeline)!;}

/** Verify bytes against the existing accepted registry. The reader supplies bytes, never durations or capacities. */
export async function registerWarehouseActionCatalogue(bundle:WarehouseBundle,readSource:(path:string)=>Promise<Uint8Array>,holders?:CargoHolderCatalogue):Promise<WarehouseActionCatalogue>{
 if(!bundle||!deeplyImmutable(bundle)||bundle.source_kind!=='visual_fixture'||bundle.engine_operation!==false||typeof readSource!=='function')reject('INVALID_BUNDLE','Нужен полностью неизменяемый проверенный visual fixture V3.');
 if(holders&&!isCargoHolderCatalogue(holders,bundle))reject('INVALID_HOLDER_CATALOGUE','Опоры относятся к другому пакету склада.');
 const source_hashes:Record<string,string>={},texts={} as WarehouseTexts;
 async function read(path:string,expected?:string){let bytes:Uint8Array;try{const value=await readSource(path);if(!(value instanceof Uint8Array))throw Error('bytes required');bytes=new Uint8Array(value);}catch{reject('SOURCE_UNAVAILABLE','Нет проверенного источника: '+path);}
  const hash=await sha(bytes!);if(expected&&hash!==expected)reject('SOURCE_HASH_MISMATCH','Источник изменился после проверки: '+path);source_hashes[path]=hash;return bytes!;
 }
 for(const [key,path]of Object.entries(baseFiles)){const bytes=await read(path);try{texts[key as keyof WarehouseTexts]=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{reject('SOURCE_BUNDLE_MISMATCH','Источник не содержит корректный UTF-8 документ V3: '+path);}}
 let verified:WarehouseBundle;try{verified=await adaptWarehouseV3(texts);}catch{reject('SOURCE_BUNDLE_MISMATCH','Источники не совпадают с принятым пакетом V3.');}
 if(!deeplyImmutable(verified!)||JSON.stringify(bundle)!==JSON.stringify(verified!))reject('SOURCE_BUNDLE_MISMATCH','Каталог не соответствует этому снимку склада.');
 const canonical=verified!;
 for(const [path,expected]of Object.entries(canonical.registry.source_hashes))await read(path,expected);
 let hasCart=false;
 if(holders){const cart=holderByDestination(holders,{kind:'cart',cart_id:'C01',anchor_id:'upper-tote'});if(cart){if(cart.source_refs['frontend/public/'+acceptedSupportBindings.cart.path]!==acceptedSupportBindings.cart.sha256)reject('INVALID_HOLDER_CATALOGUE','Для C01 нужен принятый комплект с одним tote.');for(const b of Object.values(acceptedSupportBindings))await read('frontend/public/'+b.path,b.sha256);hasCart=true;}}
 const resources:ActionResource[]=[];
 function resource(kind:ActionResource['kind'],canonical_id:string,available=true){resources.push({resource_id:kind+':'+canonical_id,kind,canonical_id,capacity:1,available});}
 for(const w of canonical.registry.workers)resource('actor',w.actor_id);for(const v of canonical.registry.vehicles)resource('vehicle',v.vehicle_id);
 const stations=(canonical.layout.data.conveyor as V3Record).packing_stations as V3Record[];
 if(stations.length!==6||new Set(stations.map(s=>s.pack_id)).size!==6)reject('INVALID_BUNDLE','Нужны шесть исходных постов.');
 for(const station of stations)resource('post',station.pack_id as string);resource('cart','C01',hasCart);for(const h of canonical.fixture.inputs.initial_stock)resource('HU',h.handling_unit_id);
 const catalogue=freeze({source_kind:'visual_fixture' as const,engine_operation:false as const,operational_admission:false as const,physical_join:false as const,fixture_id:canonical.fixture.fixture_id,layout_content_hash:canonical.layout.layout_content_hash,clips:structuredClone(canonical.registry.clips),resources,source_hashes,counts:{actors:24 as const,vehicles:2 as const,posts:6 as const,carts:(hasCart?1:0) as 0|1,handling_units:530 as const},scope:'Source-bound interval/resource validation only. All capacities are the existing exclusive physical identities, not extra actor pools. Source clips remain warehouse_joined:false; calendar acceptance does not admit geometry, cargo, role transitions or an engine operation.'});
 catalogues.set(catalogue,{bundle,verifiedBundle:canonical,resources:new Map(resources.map(r=>[r.resource_id,r])),clips:new Map(catalogue.clips.map(c=>[c.clip_id,c]))});return catalogue;
}

/** Atomic pure compilation: a rejected batch creates no issued timeline and changes no existing plan. */
export function compileWarehouseActionTimeline(bundle:WarehouseBundle,catalogue:WarehouseActionCatalogue,value:unknown):WarehouseActionCompilation{
 try{
  if(!isWarehouseActionCatalogue(catalogue,bundle))reject('INVALID_CATALOGUE','Нужен исходный зарегистрированный каталог для этого склада.');
  if(!object(value)||!keys(value,['timeline_id','actions'])||!id(value.timeline_id)||!Array.isArray(value.actions)||value.actions.length>4096)reject('INVALID_REQUEST','Некорректная временная шкала действий.');
  const state=catalogues.get(catalogue)!,sourceBundle=state.verifiedBundle,actions:CompiledWarehouseAction[]=[],seen=new Set<string>();
  function ticks(v:unknown){if(!finite(v)||v<0||v>sourceBundle.fixture.clock.duration_s||Math.abs(v*1e6-Math.round(v*1e6))>1e-6)reject('INVALID_INTERVAL','Время должно быть конечным числом секунд с точностью до микросекунды.');return Math.round(v*1e6);}
  const fields=['action_id','actor_id','clip_id','start_s','end_s','depends_on','vehicle_id','cart_id','post_id','handling_unit_id'];
  for(const raw of value.actions){
   if(!object(raw)||!keys(raw,fields)||!id(raw.action_id)||!id(raw.actor_id)||!id(raw.clip_id)||!Array.isArray(raw.depends_on)||raw.depends_on.some(d=>!id(d))||new Set(raw.depends_on).size!==raw.depends_on.length||['vehicle_id','cart_id','post_id','handling_unit_id'].some(k=>raw[k]!==null&&!id(raw[k])))reject('INVALID_REQUEST','У действия есть неизвестные или некорректные поля.');
   const action=raw as unknown as WarehouseActionRequest;if(seen.has(action.action_id))reject('DUPLICATE_ACTION','ID действия должен быть единственным.',action.action_id);seen.add(action.action_id);
   const worker=sourceBundle.registry.workers.find(w=>w.actor_id===action.actor_id);if(!worker)reject('UNKNOWN_ACTOR','Работник отсутствует в исходных 24 ID.',action.action_id);
   const clip=state.clips.get(action.clip_id);if(!clip)reject('UNKNOWN_CLIP','Клип отсутствует в принятом каталоге.',action.action_id);
   const start=ticks(action.start_s),end=ticks(action.end_s);if(end<=start)reject('INVALID_INTERVAL','Интервал должен иметь положительную длительность.',action.action_id);
   if(clip.duration_s>0&&end-start!==Math.round(clip.duration_s*1e6))reject('CLIP_DURATION_MISMATCH','Длительность отличается от принятого клипа.',action.action_id);
   const requiredEquipment:string[]=[];
   if(clip.role==='forklift_driver'){if(!action.vehicle_id)reject('RESOURCE_REQUIRED','Нужен исходный погрузчик водителя.',action.action_id);if(action.vehicle_id!==worker!.assigned_vehicle_id)reject('VEHICLE_PAIR_MISMATCH','Водитель закреплён за другой машиной.',action.action_id,'vehicle:'+action.vehicle_id);requiredEquipment.push('forklift');}
   else if(action.vehicle_id)reject('RESOURCE_NOT_ALLOWED','Этот клип не использует погрузчик.',action.action_id,'vehicle:'+action.vehicle_id);
   const needsCart=['picker_walk','picker_pick'].includes(clip.clip_id),needsPost=['packer','receiver','shipper'].includes(clip.role);
   if(needsCart&&!action.cart_id)reject('RESOURCE_REQUIRED','Для клипа нужна существующая тележка C01.',action.action_id);
   if(action.cart_id){if(clip.role!=='picker')reject('RESOURCE_NOT_ALLOWED','Тележка не объявлена для этой роли.',action.action_id,'cart:'+action.cart_id);requiredEquipment.push('picking-cart');}
   if(needsPost&&!action.post_id)reject('RESOURCE_REQUIRED','Нужен один из шести существующих постов.',action.action_id);
   if(action.post_id){if(!needsPost)reject('RESOURCE_NOT_ALLOWED','Этот клип не занимает пост.',action.action_id,'post:'+action.post_id);requiredEquipment.push('packing-station');}
   if(['picker_pick','packer_finish','receiver_receive','shipper_place','driver_pickup'].includes(clip.clip_id)&&!action.handling_unit_id)reject('RESOURCE_REQUIRED','Укажите исходную HU для исключительного резервирования; это не перенос груза.',action.action_id);
   const capability=checkVisualWorkerCapability(sourceBundle.profiles,action.actor_id,{source_kind:'visual_fixture',engine_operation:false,target_role:clip.role,handler:'observe',cargo_mass_kg:null,vehicle_id:action.vehicle_id,required_equipment:requiredEquipment});
   if(!capability.eligible)reject('ROLE_NOT_ELIGIBLE','Профиль не допускает эту роль или оборудование.',action.action_id);
   const ids=['actor:'+action.actor_id,...(action.vehicle_id?['vehicle:'+action.vehicle_id]:[]),...(action.cart_id?['cart:'+action.cart_id]:[]),...(action.post_id?['post:'+action.post_id]:[]),...(action.handling_unit_id?['HU:'+action.handling_unit_id]:[])];
   for(const resourceId of ids){const resource=state.resources.get(resourceId);if(!resource)reject('UNKNOWN_RESOURCE','Неизвестный ресурс: '+resourceId,action.action_id,resourceId);if(!resource.available)reject('RESOURCE_UNAVAILABLE','Ресурс ещё не представлен в этой сцене: '+resourceId,action.action_id,resourceId);}
   actions.push({...structuredClone(action),start_s:start/1e6,end_s:end/1e6,clip,claims:ids.map(resource_id=>({resource_id,quantity:1 as const})),skill_level:capability.skill_level!,role_transition_required:worker!.baseline_role!==clip.role,native_admission_required:true,cargo_admission_required:action.handling_unit_id!==null});
  }
  const byId=new Map(actions.map(a=>[a.action_id,a])),indegree=new Map(actions.map(a=>[a.action_id,a.depends_on.length])),outgoing=new Map<string,string[]>();
  for(const a of actions)for(const dep of a.depends_on){if(!byId.has(dep)||dep===a.action_id)reject('INVALID_DEPENDENCY','Зависимость должна ссылаться на другое существующее действие.',a.action_id);const next=outgoing.get(dep)??[];next.push(a.action_id);outgoing.set(dep,next);}
  const ready=actions.filter(a=>!a.depends_on.length).map(a=>a.action_id);let visited=0;for(let i=0;i<ready.length;i++){visited++;for(const next of outgoing.get(ready[i])??[]){indegree.set(next,indegree.get(next)!-1);if(!indegree.get(next))ready.push(next);}}
  if(visited!==actions.length)reject('DEPENDENCY_CYCLE','Зависимости действий образуют цикл.');
  for(const a of actions)for(const dep of a.depends_on)if(byId.get(dep)!.end_s>a.start_s)reject('DEPENDENCY_NOT_FINISHED','Предыдущее действие ещё не закончено.',a.action_id);
  const calendars:WarehouseActionTimeline['calendars']=[];
  for(const resource of catalogue.resources){const intervals=actions.filter(a=>a.claims.some(c=>c.resource_id===resource.resource_id)).map(a=>({action_id:a.action_id,start_s:a.start_s,end_s:a.end_s,quantity:1 as const}));if(!intervals.length)continue;
   const boundaries=intervals.flatMap(a=>[{at:a.start_s,delta:1,id:a.action_id},{at:a.end_s,delta:-1,id:a.action_id}]).sort((a,b)=>a.at-b.at||a.delta-b.delta||compare(a.id,b.id));let used=0;for(const b of boundaries){used+=b.delta;if(used>resource.capacity)reject('RESOURCE_CAPACITY_EXCEEDED','Ресурс уже занят другим действием.',b.id,resource.resource_id);}
   calendars.push({resource,intervals:intervals.sort((a,b)=>a.start_s-b.start_s||compare(a.action_id,b.action_id))});
  }
  actions.sort((a,b)=>a.start_s-b.start_s||compare(a.action_id,b.action_id));const duration_s=Math.max(0,...actions.map(a=>a.end_s));
  const events:WarehouseActionEvent[]=actions.flatMap(a=>[{at_s:a.start_s,kind:'interval_start' as const,action_id:a.action_id,actor_id:a.actor_id},{at_s:a.end_s,kind:'interval_end' as const,action_id:a.action_id,actor_id:a.actor_id}]).sort((a,b)=>a.at_s-b.at_s||(a.kind===b.kind?0:a.kind==='interval_end'?-1:1)||compare(a.action_id,b.action_id));
  function time(value:number){if(!finite(value))reject('INVALID_TIME','Время должно быть конечным числом.');return Math.max(0,Math.min(duration_s,value));}
  function sample(value:number):WarehouseActionSample{const at_s=time(value);return freeze({...scope,at_s,duration_s,active:actions.filter(a=>a.start_s<=at_s&&at_s<a.end_s).map(a=>({...a,local_clip_time_s:a.clip.duration_s===0?0:Math.min(a.clip.duration_s,at_s-a.start_s)})),events_at_time:events.filter(e=>e.at_s===at_s)});}
  function eventsBetween(from:number,to:number){const a=time(from),b=time(to);if(b<a)reject('INVALID_TIME','Диапазон событий должен идти вперёд.');return freeze(events.filter(e=>e.at_s>a&&e.at_s<=b));}
  const timeline=freeze({...scope,timeline_id:value.timeline_id,fixture_id:sourceBundle.fixture.fixture_id,duration_s,actions,events,calendars,sample,eventsBetween});timelines.set(timeline,catalogue);
  return freeze({...scope,ok:true,reason:'TIMELINE_OK' as const,message:'Интервалы и ресурсы согласованы; физические переходы требуют отдельной проверки.',action_id:null,resource_id:null,timeline});
 }catch(error){if(!(error instanceof WarehouseActionError))throw error;return freeze({...scope,ok:false,reason:error.reason,message:error.message,action_id:error.action_id,resource_id:error.resource_id,timeline:null});}
}
