import type {WorkerRole} from './workerRoles';
import {workerById,type WorkerRegistry,type SourceRef} from './workerRegistry';

export type VisualHandler='observe'|'manual'|'forklift';
export type VisualWorkerProfile={worker_id:string;baseline_role:WorkerRole;initial_role:WorkerRole;allowed_roles:WorkerRole[];walk_speed_m_s:number;skill_levels:Partial<Record<WorkerRole,number>>;allowed_vehicle_ids:string[];allowed_handlers:VisualHandler[];allowed_equipment:string[];source_kind:'visual_fixture';engine_operation:false;operational_admission:false};
export type VisualWorkerProfiles={schema_id:string;namespace:'v3';layout_version:string;source_kind:'visual_fixture';engine_operation:false;operational_admission:false;worker_count:24;registry_ref:SourceRef;handling_policy:{manual_mass_limit_kg:15;kind:'synthetic_design';physical_admission_required:true;cargo_admission_required:true};cross_trained_worker_ids:string[];profiles:VisualWorkerProfile[];source_hashes:Record<string,string>;assumptions:{kind:'synthetic_design';statement:string;current_role_policy:string;handling_policy:string};scope:string};
const equipment:Record<WorkerRole,readonly string[]>={picker:['picking-cart','small-package-gripper'],packer:['packing-station'],receiver:['packing-station','fixed-scanner'],shipper:['packing-station','fixed-scanner','conveyor-straight'],forklift_driver:['forklift']};
const same=(a:unknown,b:unknown)=>JSON.stringify(a)===JSON.stringify(b),record=(x:unknown):x is Record<string,unknown>=>typeof x==='object'&&x!==null&&!Array.isArray(x);
function freeze<T>(v:T):T{if(v&&typeof v==='object'){for(const x of Object.values(v))freeze(x);Object.freeze(v);}return v;}
export function validateWorkerProfiles(value:unknown,registry:WorkerRegistry,registrySha256:string):VisualWorkerProfiles{
  const d=value as VisualWorkerProfiles;
  if(!record(d)||d.schema_id!=='qoima.visual-worker-profiles.v3'||d.namespace!=='v3'||d.layout_version!=='qoima-144x72-v3'||d.source_kind!=='visual_fixture'||d.engine_operation!==false||d.operational_admission!==false||d.worker_count!==24||!record(d.registry_ref)||d.registry_ref.path!=='frontend/public/data/v3/worker-registry-v3.json'||!/^[a-f0-9]{64}$/.test(registrySha256)||d.registry_ref.sha256!==registrySha256)throw Error('Версии реестра и профилей V3 не совпадают.');
  if(!same(d.handling_policy,{manual_mass_limit_kg:15,kind:'synthetic_design',physical_admission_required:true,cargo_admission_required:true})||!same(d.cross_trained_worker_ids,['P01','P02'])||!Array.isArray(d.profiles)||d.profiles.length!==24||new Set(d.profiles.map(p=>p?.worker_id)).size!==24)throw Error('Некорректные правила навыков V3.');
  for(const p of d.profiles){
    if(!record(p)||typeof p.worker_id!=='string')throw Error('Нет ID профиля.');const w=workerById(registry,p.worker_id),allowed:WorkerRole[]=[w.baseline_role];if(['P01','P02'].includes(w.actor_id))allowed.push('packer');
    const skills=Object.fromEntries(allowed.map(role=>[role,role===w.baseline_role?1:.8])),vehicles=w.assigned_vehicle_id?[w.assigned_vehicle_id]:[],handlers=w.baseline_role==='forklift_driver'?['observe','forklift']:['observe','manual'],tools=[...new Set(allowed.flatMap(role=>equipment[role]))];
    if(p.baseline_role!==w.baseline_role||p.initial_role!==w.initial_role||!same(p.allowed_roles,allowed)||p.walk_speed_m_s!==1.2||!same(p.skill_levels,skills)||!same(p.allowed_vehicle_ids,vehicles)||!same(p.allowed_handlers,handlers)||!same(p.allowed_equipment,tools)||p.source_kind!=='visual_fixture'||p.engine_operation!==false||p.operational_admission!==false||['current_role','initial_pos','world_pos'].some(key=>Object.hasOwn(p,key)))throw Error('Профиль меняет исходный состав или объявленные навыки '+w.actor_id);
  }
  if(!record(d.source_hashes)||d.source_hashes[d.registry_ref.path]!==registrySha256||!Object.entries(d.source_hashes).every(([p,h])=>/^[a-zA-Z0-9_./-]+$/.test(p)&&!p.split('/').includes('..')&&typeof h==='string'&&/^[a-f0-9]{64}$/.test(h))||d.assumptions?.kind!=='synthetic_design'||typeof d.scope!=='string')throw Error('Нет подтверждённых источников профиля.');
  return freeze(structuredClone(d));
}
export function profileById(profiles:VisualWorkerProfiles,id:string):VisualWorkerProfile{const p=profiles.profiles.find(p=>p.worker_id===id);if(!p)throw Error('Неизвестный работник '+id);return p;}

export type VisualCapabilityDemand={source_kind:'visual_fixture';engine_operation:false;target_role:WorkerRole;handler:VisualHandler;cargo_mass_kg:number|null;vehicle_id:string|null;required_equipment:string[]};
export type VisualCapabilityResult={eligible:boolean;reason:'CAPABILITY_OK'|'INVALID_REQUEST'|'UNKNOWN_WORKER'|'ROLE_NOT_ELIGIBLE'|'INVALID_MASS'|'HANDLER_NOT_ALLOWED'|'MANUAL_OVERWEIGHT'|'VEHICLE_NOT_ALLOWED'|'EQUIPMENT_NOT_ALLOWED';skill_level:number|null;physical_admission_required:true;cargo_admission_required:true;source_kind:'visual_fixture';engine_operation:false};
/** Capability only: never assign a role/job or admit cargo/geometry/resources. */
export function checkVisualWorkerCapability(profiles:VisualWorkerProfiles,workerId:string,value:unknown):VisualCapabilityResult{
  const result=(eligible:boolean,reason:VisualCapabilityResult['reason'],skill_level:number|null=null):VisualCapabilityResult=>Object.freeze({eligible,reason,skill_level,physical_admission_required:true,cargo_admission_required:true,source_kind:'visual_fixture',engine_operation:false});
  const d=value as VisualCapabilityDemand;
  if(typeof workerId!=='string'||!record(d)||d.source_kind!=='visual_fixture'||d.engine_operation!==false||!Object.hasOwn(equipment,d.target_role)||!['observe','manual','forklift'].includes(d.handler)||!(d.vehicle_id===null||typeof d.vehicle_id==='string')||!Array.isArray(d.required_equipment)||d.required_equipment.some(x=>typeof x!=='string')||new Set(d.required_equipment).size!==d.required_equipment.length)return result(false,'INVALID_REQUEST');
  const p=profiles.profiles.find(p=>p.worker_id===workerId);if(!p)return result(false,'UNKNOWN_WORKER');
  if(!p.allowed_roles.includes(d.target_role))return result(false,'ROLE_NOT_ELIGIBLE');
  if(d.cargo_mass_kg!==null&&(typeof d.cargo_mass_kg!=='number'||!Number.isFinite(d.cargo_mass_kg)||d.cargo_mass_kg<=0)||d.handler!=='observe'&&d.cargo_mass_kg===null)return result(false,'INVALID_MASS');
  if(!p.allowed_handlers.includes(d.handler))return result(false,'HANDLER_NOT_ALLOWED');
  if(d.handler==='manual'&&d.cargo_mass_kg!==null&&d.cargo_mass_kg>profiles.handling_policy.manual_mass_limit_kg)return result(false,'MANUAL_OVERWEIGHT');
  if(d.vehicle_id!==null&&!p.allowed_vehicle_ids.includes(d.vehicle_id)||d.handler==='forklift'&&d.vehicle_id===null)return result(false,'VEHICLE_NOT_ALLOWED');
  if(d.required_equipment.some(e=>!p.allowed_equipment.includes(e)||!equipment[d.target_role].includes(e)))return result(false,'EQUIPMENT_NOT_ALLOWED');
  return result(true,'CAPABILITY_OK',p.skill_levels[d.target_role]!);
}
