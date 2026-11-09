import type {WorkerRole} from './workerRoles';

export type SourceRef={path:string;sha256:string};
export type RoleLegend={role:WorkerRole;label:string;color:string;code:string;icon:string;count:number};
export type RoleClip={clip_id:string;role:WorkerRole;label:string;asset_id:string;fixture:string|null;mode:string|null;duration_s:number;clock_kind:string;accepted_task:string;proof:SourceRef;sources:SourceRef[];prerequisites:string;fixture_actor_id:string;canonical_actor_id:string;warehouse_joined:false};
export type RegistryWorker={actor_id:string;baseline_role:WorkerRole;initial_role:WorkerRole;clip_ids:string[];assigned_vehicle_id:string|null;legacy_station_ref:string|null};
export type WorkerRegistry={schema_id:string;namespace:'v3';layout_version:string;source_kind:'visual_fixture';engine_operation:false;operational_admission:false;actor_count:24;vehicle_count:2;packing_station_count:6;roles:RoleLegend[];workers:RegistryWorker[];vehicles:{vehicle_id:string;driver_actor_id:string}[];clips:RoleClip[];fixture_aliases:{fixture_actor_id:string;canonical_actor_id:string;clip_ids:string[];scope:string}[];source_hashes:Record<string,string>;scope:string};
const definitions={picker:{color:'#3478F6',code:'01',icon:'cart',count:12},packer:{color:'#F28C28',code:'02',icon:'carton',count:6},receiver:{color:'#9B59D0',code:'03',icon:'incoming_arrow',count:2},shipper:{color:'#2AA56A',code:'04',icon:'outgoing_arrow',count:2},forklift_driver:{color:'#F4C542',code:'05',icon:'forklift',count:2}} as const;
const ids=new Map<string,WorkerRole>();
for(const[prefix,count,role]of [['P',12,'picker'],['K',6,'packer'],['R',2,'receiver'],['S',2,'shipper'],['F',2,'forklift_driver']] as const)for(let i=1;i<=count;i++)ids.set(prefix+String(i).padStart(2,'0'),role);
const expectedClips:Record<string,readonly[WorkerRole,string,string|null,string|null,number,string]>={
  picker_idle:['picker','worker-manual',null,null,0,'P03'],picker_walk:['picker','picking-cart-tote-fixture','walk',null,9,'P03'],picker_pick:['picker','picker-pick-source-fixture','pick',null,36,'P03.5.3.3'],
  packer_finish:['packer','packer-workcell-fixture','packer','pack',7.5,'P04'],packer_idle:['packer','packer-workcell-fixture','packer','idle',0,'P04'],packer_blocked:['packer','packer-workcell-fixture','packer','blocked',0,'P04'],
  receiver_scan:['receiver','receiver-workcell-fixture','receiver','scan',2.5,'P05'],receiver_receive:['receiver','receiver-workcell-fixture','receiver','receive',17.8,'P05'],receiver_idle:['receiver','receiver-workcell-fixture','receiver','idle',0,'P05'],receiver_blocked:['receiver','receiver-workcell-fixture','receiver','blocked',0,'P05'],
  shipper_scan:['shipper','shipper-workcell-fixture','shipper','scan',2.5,'P06'],shipper_place:['shipper','shipper-workcell-fixture','shipper','place',27,'P06'],shipper_idle:['shipper','shipper-workcell-fixture','shipper','idle',0,'P06'],shipper_blocked:['shipper','shipper-workcell-fixture','shipper','blocked',0,'P06'],
  driver_seated:['forklift_driver','forklift','driver',null,0,'P07'],driver_pickup:['forklift_driver','forklift-pallet-low-fixture','pickup',null,30,'P07'],
};
const record=(x:unknown):x is Record<string,unknown>=>typeof x==='object'&&x!==null&&!Array.isArray(x);
const text=(x:unknown):x is string=>typeof x==='string'&&x.length>0;
const role=(x:unknown):x is WorkerRole=>typeof x==='string'&&Object.hasOwn(definitions,x);
const unique=(x:unknown[]):boolean=>new Set(x).size===x.length;
const ref=(x:unknown):x is SourceRef=>record(x)&&text(x.path)&&/^[a-zA-Z0-9_/-]+(?:\.[a-zA-Z0-9_-]+)+$/.test(x.path)&&!x.path.split('/').includes('..')&&typeof x.sha256==='string'&&/^[a-f0-9]{64}$/.test(x.sha256);
function freeze<T>(v:T,seen=new WeakSet<object>()):T{if(v&&typeof v==='object'&&!seen.has(v)){seen.add(v);for(const x of Object.values(v))freeze(x,seen);Object.freeze(v);}return v;}

export function validateWorkerRegistry(value:unknown):WorkerRegistry{
  const d=value as WorkerRegistry;
  if(!record(d)||d.schema_id!=='qoima.visual-worker-registry.v3'||d.namespace!=='v3'||d.layout_version!=='qoima-144x72-v3'||d.source_kind!=='visual_fixture'||d.engine_operation!==false||d.operational_admission!==false||d.actor_count!==24||d.vehicle_count!==2||d.packing_station_count!==6||!text(d.scope))throw Error('Некорректный реестр V3.');
  if(!Array.isArray(d.roles)||d.roles.length!==5||!unique(d.roles.map(r=>r?.role)))throw Error('Нужны пять различных ролей.');
  for(const r of d.roles){if(!record(r)||!role(r.role)||!text(r.label))throw Error('Некорректная роль.');const expected=definitions[r.role];for(const key of ['color','code','icon','count'] as const)if(r[key]!==expected[key])throw Error('Легенда роли не совпадает с моделью.');}
  if(!Array.isArray(d.workers)||d.workers.length!==24||!unique(d.workers.map(w=>w?.actor_id)))throw Error('В реестре должны быть24различных работника.');
  for(const w of d.workers){if(!record(w)||ids.get(w.actor_id)!==w.baseline_role||w.initial_role!==w.baseline_role||!Array.isArray(w.clip_ids)||!w.clip_ids.length||!unique(w.clip_ids))throw Error('Исходные ID или роли работников изменены.');const vehicle=w.actor_id==='F01'?'FL01':w.actor_id==='F02'?'FL02':null,station=w.baseline_role==='packer'?'PK'+w.actor_id.slice(1):null;if(w.assigned_vehicle_id!==vehicle||w.legacy_station_ref!==station||Object.hasOwn(w,'initial_pos'))throw Error('Техника, пост или позиция работника некорректны.');}
  if(!Array.isArray(d.vehicles)||d.vehicles.length!==2||!unique(d.vehicles.map(v=>v.vehicle_id))||!d.vehicles.every(v=>v.vehicle_id==='FL01'?v.driver_actor_id==='F01':v.vehicle_id==='FL02'&&v.driver_actor_id==='F02'))throw Error('Нужны две исходные пары водитель/техника.');
  if(!Array.isArray(d.clips)||d.clips.length!==16||!unique(d.clips.map(c=>c?.clip_id)))throw Error('Некорректный каталог клипов.');
  for(const c of d.clips){if(!record(c)||!text(c.clip_id)||!role(c.role)||!text(c.label)||!text(c.prerequisites)||!Number.isFinite(c.duration_s)||c.duration_s<0||c.duration_s>36||c.warehouse_joined!==false||ids.get(c.canonical_actor_id)!==c.role||!ref(c.proof)||!Array.isArray(c.sources)||!c.sources.length||!c.sources.every(ref)||!/^P\d+(?:\.\d+)*$/.test(c.accepted_task)||!/^[a-z][a-z0-9-]+$/.test(c.asset_id)||!(c.fixture===null||['walk','pick','packer','receiver','shipper','driver','pickup'].includes(c.fixture))||!(c.mode===null||['pack','receive','place','scan','idle','blocked'].includes(c.mode)))throw Error('Некорректная привязка клипа.');
    const expected=expectedClips[c.clip_id];if(!expected||JSON.stringify([c.role,c.asset_id,c.fixture,c.mode,c.duration_s,c.accepted_task])!==JSON.stringify(expected)||c.clock_kind!==(c.duration_s?'explanatory_visual_clock':'static_pose')||c.proof.path!==`docs/adaptive-v3/evidence/${c.accepted_task}.json`)throw Error('Клип не совпадает с принятым комплектом.');
    if(c.fixture_actor_id!==c.canonical_actor_id&&!(c.fixture_actor_id==='PK01'&&c.canonical_actor_id==='K01'&&c.role==='packer'))throw Error('Необъявленный QA ID.');
  }
  for(const w of d.workers){const expected=d.clips.filter(c=>c.role===w.baseline_role).map(c=>c.clip_id);if(expected.length!==w.clip_ids.length||!expected.every(id=>w.clip_ids.includes(id)))throw Error('Клип не соответствует роли работника.');}
  if(!Array.isArray(d.fixture_aliases)||d.fixture_aliases.length!==1)throw Error('Некорректный QA alias.');const a=d.fixture_aliases[0];if(a.fixture_actor_id!=='PK01'||a.canonical_actor_id!=='K01'||!text(a.scope)||!Array.isArray(a.clip_ids)||!unique(a.clip_ids)||a.clip_ids.length!==3||!a.clip_ids.every(id=>d.clips.some(c=>c.clip_id===id&&c.role==='packer')))throw Error('QA ID не совпадает с K01.');
  if(!record(d.source_hashes)||!Object.keys(d.source_hashes).length||!Object.entries(d.source_hashes).every(([path,sha256])=>ref({path,sha256})))throw Error('Нет точных источников реестра.');
  for(const c of d.clips)for(const r of [c.proof,...c.sources])if(d.source_hashes[r.path]!==r.sha256)throw Error('Хеш привязки клипа не совпадает с источником.');
  return freeze(structuredClone(d));
}

export function workerById(registry:WorkerRegistry,id:string):RegistryWorker{const worker=registry.workers.find(w=>w.actor_id===id);if(!worker)throw Error('Неизвестный работник '+id);return worker;}
export function resolveFixtureWorker(registry:WorkerRegistry,id:string,clipId:string):RegistryWorker{
  const clip=registry.clips.find(c=>c.clip_id===clipId);if(!clip)throw Error('Неизвестный клип.');const canonical=registry.fixture_aliases.find(a=>a.fixture_actor_id===id&&a.clip_ids.includes(clipId))?.canonical_actor_id??id,worker=workerById(registry,canonical);if(worker.baseline_role!==clip.role)throw Error('Клип не соответствует роли.');return worker;
}
export function clipStandUrl(clip:RoleClip):string{const params=new URLSearchParams({asset:clip.asset_id});if(clip.fixture)params.set('fixture',clip.fixture);if(clip.mode)params.set('mode',clip.mode);return 'stand-v3.html?'+params.toString();}
