import './scenario.css';
import {adaptWarehouseV3,WAREHOUSE_BASE_FILES,type WarehouseTexts} from './warehouseAdapter';
import {validateRoutePolicy,createWarehouseRouter} from './warehouseRouting';
import {createStaffingComparison} from './workerRoleAssignment';
import {createWarehouseStaffingScene} from './warehouseStaffingScene';
import {createWarehouseScene} from './warehouseScene';
import {compileWarehouseScenarioExecution,type WarehouseScenarioPlan,type WarehouseScenarioSample, type ScenarioExecutionJob} from './warehouseScenarioExecution';
import {createWarehouseScenarioClock} from './warehouseScenarioClock';
import {createWarehouseScenarioScene} from './warehouseScenarioScene';
import {WAREHOUSE_SCENARIO_SOURCES,type WarehouseScenarioId} from './warehouseScenarioSources';
import {verifyWarehouseHeavyInboundSources} from './warehouseHeavyInboundBinding';
import {compileWarehouseHeavyInboundPlan} from './warehouseHeavyInboundPlan';
import {validateAdditionalHeavyPacket,createWarehouseAdditionalHeavyCases,compileWarehouseAdditionalHeavyCase} from './warehouseAdditionalHeavyCases';
import {createWarehouseManualWorkflowRoute} from './warehouseManualWorkflowRoute';
import {createWarehouseManualTransfer,type WarehouseManualTransfer} from './warehouseScenarioManualTransfer';
import {createWarehouseScenarioEffects} from './warehouseScenarioEffects';
import {createWarehouseScenarioVisualCues} from './warehouseScenarioVisualCues';
import {summarizeWarehouseScenarioCosts,compareWarehouseScenarioCosts} from './warehouseScenarioCosts';
import {compileWarehouseLongSourceOperationPlan} from './warehouseLongSourceOperationPlan';
import {validateWarehouseSourceLongConcurrencyCertificate,SOURCE_LONG_CONCURRENCY_CERTIFICATE} from './warehouseSourceLongConcurrency';
import {mountWarehouseRelocationCosts} from './warehouseRelocationCostPanel';
import {createWarehouseReceivingWorkflowRoute,validateWarehouseReceivingN1Input} from './warehouseReceivingWorkflowRoute';
import {createWarehouseReceivingManualTransfer,type WarehouseReceivingManualTransfer} from './warehouseReceivingManualTransfer';
import {createWarehouseStaffingPendingWork} from './warehouseStaffingPendingWork';
import {renderWarehouseScenarioComparison} from './warehouseScenarioComparisonRender';
import type {WebGLRenderer,Scene as NativeScene,OrthographicCamera} from 'three';
import type {XYZ,WarehouseRequest,V3Record} from './warehouseTypes';

const $=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id) as T;
const root=$('scenario-app'),host=$('sc-viewport'),scenario=$<HTMLSelectElement>('sc-scenario'),rate=$<HTMLSelectElement>('sc-rate'),timeline=$<HTMLInputElement>('sc-timeline'),play=$<HTMLButtonElement>('sc-play'),reduced=matchMedia('(prefers-reduced-motion: reduce)');
type Scene=Awaited<ReturnType<typeof createWarehouseScene>>;
let phase:'loading'|'ready'|'error'|'disposed'='loading',epoch=0,abort:AbortController|undefined,base:Scene|undefined,native:ReturnType<typeof createWarehouseScenarioScene>|undefined,plan:WarehouseScenarioPlan|undefined,clock:ReturnType<typeof createWarehouseScenarioClock>|ReturnType<typeof createStaffClock>|undefined,raf=0,last=0,selected:string|null=null,variant:'A'|'B'='A',view='overview',rowsKey='',frameKey='';
let staffing:Awaited<ReturnType<typeof createStaffingComparison>>|undefined,staffNative:Awaited<ReturnType<typeof createWarehouseStaffingScene>>|undefined;
let effects:ReturnType<typeof createWarehouseScenarioEffects>|undefined,costKey='';
let visualCues:ReturnType<typeof createWarehouseScenarioVisualCues>|undefined;
let sourceRequestIds=new Set<string>();
let pairedPlans:Readonly<{A:WarehouseScenarioPlan;B:WarehouseScenarioPlan}>|undefined,comparison=false,comparisonFrame:ReturnType<typeof renderWarehouseScenarioComparison>|null=null;
const keys=Object.keys(WAREHOUSE_BASE_FILES) as (keyof WarehouseTexts)[],controls=()=>[...document.querySelectorAll<HTMLButtonElement|HTMLSelectElement|HTMLInputElement>('#sc-play,#sc-reset,#sc-timeline,#sc-rate,#sc-scenario,#sc-sound,#sc-volume,#sc-compare,[data-view],[data-variant]')];
const sha=async(value:string)=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)))].map(v=>v.toString(16).padStart(2,'0')).join('');
const fmt=(n:number)=>`${String(Math.floor(n/60)).padStart(2,'0')}:${String(Math.floor(n%60)).padStart(2,'0')}`;
const esc=(v:unknown)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const cargoNames:Record<string,string>={SMALL_CARTON:'Малый короб',STANDARD_CARTON:'Обычный короб',HEAVY_BOX:'Тяжёлый короб',PALLET_LOAD:'Паллета',IBC:'Контейнер IBC',LONG_BUNDLE:'Длинномер',DRUM:'Бочка',FRAGILE_CRATE:'Хрупкий груз'};
const statuses:Record<string,string>={not_released:'По расписанию',queued:'В очереди',travelling:'В пути',native_join_required:'Ожидает обработки',completed_visual:'Завершено',refused:'Отказ'};
const reasons:Record<string,string>={NATIVE_JOIN_REQUIRED:'Маршрут подготовлен; захват и передача этого груза ещё не связаны в общий процесс.',RESOURCE_BUSY:'Подходящий работник или техника заняты.',NO_COMPATIBLE_FREE_SLOT:'Нет свободной совместимой ячейки.',PORT_CARGO_FORBIDDEN:'Эти ворота не принимают такой груз.',PORT_PAIR_FORBIDDEN:'Закреплённая техника не обслуживает эти ворота.',MANUAL_OVERWEIGHT:'Масса груза превышает допустимую для ручного переноса.',NO_PATH:'Для этого груза нет допустимого маршрута.',HORIZON_EXCEEDED:'Действие не помещается в выбранное время смены.'};
Object.assign(reasons,{
 NATIVE_PICKUP_JOIN_REQUIRED:'Исполнитель прибыл. Захват этого груза пока не подключён к общему процессу.',
 NATIVE_PEDESTRIAN_TIMING_REQUIRED:'Для этого пути ещё не подготовлено движение исполнителя.',
 PARTIAL_MANUAL_PACKING_SHIPPING_JOIN_REQUIRED:'Короб доставлен на упаковочный стол; упаковка и отгрузка ещё не завершены.',
 RESOURCE_BUSY_UNTIL_HORIZON:'Подходящие ресурсы заняты до конца показанного интервала.',
 HANDLER_UNAVAILABLE:'Нет доступного исполнителя с нужным допуском.',
 POST_OR_SHIPPER_UNAVAILABLE:'Нет доступного упаковочного поста или отгрузчика.',
 NO_COMPATIBLE_SERVICE_NODE:'Нет допустимого подхода к грузу или воротам.',
 HU_NOT_YET_RECEIVED:'Груз ещё не принят на склад.',
 UNKNOWN_HU:'Груза нет среди учтённых поступлений и складских остатков.',
 PORT_DIRECTION_MISMATCH:'Направление заявки не соответствует этим воротам.',
 NATIVE_ADDITIONAL_TARGET_OCCUPIED:'Выбранное место уже занято другим грузом.'
});
function jobStatus(job:ScenarioExecutionJob&{status:string}){return job.native_case==='source_long_transfer'&&job.status==='completed_visual'?'За воротами':statuses[job.status]??job.status;}
function reasonText(reason:string){if(reason.startsWith('PROVED_'))return '';return reasons[reason]??'Для этого действия пока нет полностью подготовленного допустимого процесса.';}
const manualPhaseNames:Record<string,string>={participants_clear_table:'Освобождаем упаковочный пост',approach:'Комплектовщик идёт к ячейке',source_connector:'Подход к коробу',acquire:'Захват короба',extract:'Извлечение из ячейки',upright_lift:'Подъём короба',loaded_walk:'Перенос к упаковке',table_connector:'Подход к упаковочному столу',table_setdown:'Короб ставят на стол',table_release:'Передача на упаковку',picker_back_from_table:'Комплектовщик освобождает пост',picker_returns_home:'Комплектовщик возвращается',packer_returns_to_post:'Упаковщик подходит к посту',packer_approaches_supported_HU:'Подготовка упаковки',packer_reaches_carton:'Подготовка упаковки',packing_whole_HU:'Упаковка короба',packer_releases_supported_HU:'Упаковка завершена',packer_clears_post:'Упаковщик освобождает пост',packer_yields_for_shipper:'Освобождаем место для отгрузчика',shipper_approaches_post:'Отгрузчик идёт к посту',shipper_final_connector:'Подход к упакованному коробу',shipper_grasps_same_HU:'Захват для отгрузки',shipper_extracts_from_conveyor:'Короб снимают с линии',shipper_lowers_clear_carton:'Подготовка переноса',shipper_carries_to_port:'Перенос к воротам',held_HU_enters_finite_port_buffer:'Вход в выделенную зону отгрузки',port_service_while_HU_is_held:'Передача за ворота',shipper_recovers_after_boundary_handover:'Передача завершена',shipper_returns_home:'Отгрузчик возвращается',packer_returns_home:'Упаковщик возвращается',completed_visual:'Цикл завершён'};
const receivingPhaseNames:Record<string,string>={receiver_empty_approach:'Приёмщик идёт к зоне поступления',receiver_prepares_native_hands:'Подготовка к приёмке',receiver_checks_held_whole_HU:'Проверка поступившего короба',receiver_carries_whole_HU:'Приёмщик несёт короб в ячейку',receiver_lowers_clear_HU:'Подготовка размещения',receiver_inserts_into_free_L1:'Короб ставят в свободную ячейку',receiver_releases_supported_HU:'Короб размещён',receiver_returns_home:'Приёмщик возвращается',receiving_completed_visual:'Приёмка завершена'};
function setState(value:typeof phase,message=''){phase=value;root.dataset.state=value;$('sc-loading').hidden=value!=='loading';$('sc-error').hidden=value!=='error';if(value==='error')$('sc-error-text').textContent=message;for(const c of controls())c.disabled=value!=='ready';syncSound();}
function pause(){effects?.stop();visualCues?.stop();if(raf)cancelAnimationFrame(raf);raf=0;last=0;clock?.pause();play.setAttribute('aria-pressed','false');play.textContent='Воспроизвести';}
function dispose(){pause();visualCues?.dispose();visualCues=undefined;effects?.dispose();effects=undefined;costKey='';sourceRequestIds.clear();staffNative?.dispose();staffNative=undefined;staffing=undefined;native?.dispose();native=undefined;clock?.dispose();clock=undefined;base?.dispose();base=undefined;plan=undefined;pairedPlans=undefined;comparisonFrame=null;frameKey='';rowsKey='';}
function fail(error:unknown){console.error('SCENARIO_VIEWER_REFUSED',error);dispose();setState('error','Не удалось проверить исходные данные или подготовить действия. Повторите загрузку.');}
function frame(target:XYZ,span:number,dir:XYZ){const key=JSON.stringify([target,span,dir]);if(key!==frameKey){frameKey=key;base?.frameAt(target,span,dir);}}
function renderScenarioPass(token:number,signal:AbortSignal,id:WarehouseScenarioId|'N4',renderer:WebGLRenderer,scene:NativeScene,camera:OrthographicCamera){
 if(token!==epoch||signal.aborted)return;
 if(phase!=='ready'){renderer.render(scene,camera);return;}
 if(!comparison){comparisonFrame=null;renderer.render(scene,camera);return;}
 const frameClock=clock,frameNative=native,frameStaff=staffNative;
 if(!frameClock||(id==='N4'?!frameStaff:!frameNative))return;
 const seconds=frameClock.snapshot().at_s,selectedVariant=variant;
 try{
  comparisonFrame=renderWarehouseScenarioComparison(renderer,scene,camera,{comparison,variant:selectedVariant,applyVariant:next=>{
   if(token!==epoch||signal.aborted||phase!=='ready'||clock!==frameClock)throw Error('STALE_SCENARIO_COMPARISON_FRAME');
   if(id==='N4')frameStaff!.apply(next,seconds);else frameNative!.apply(seconds);
  }});
 }catch(error){queueMicrotask(()=>{if(token===epoch&&!signal.aborted&&phase==='ready')fail(error);});}
}
function setVariant(next:'A'|'B'){
 if(phase!=='ready'||!clock||!['A','B'].includes(next)||next===variant)return;
 variant=next;if(pairedPlans)plan=pairedPlans[next];
 for(const button of document.querySelectorAll<HTMLButtonElement>('[data-variant]'))button.setAttribute('aria-pressed',String(button.dataset.variant===next));
 rowsKey='';costKey='';displayCurrent(clock.sample());
}
function setComparison(next:boolean){
 if(phase!=='ready'||!clock||typeof next!=='boolean')return;
 comparison=next;root.dataset.comparison=String(next);$('sc-compare').setAttribute('aria-pressed',String(next));$('sc-compare-labels').hidden=!next;
 frameKey='';displayCurrent(clock.sample());
}
function camera(sample:WarehouseScenarioSample){
 if(view==='top'){frame([72,0,36],164,[0,1,.0001]);return;}
 if(view!=='job'||!selected){frame([72,1.5,36],184,[0,1.15,1]);return;}
 const job=sample.jobs.find(j=>j.job_id===selected),actor=sample.actors.find(a=>a.job_id===selected),cargo=sample.cargo.find(c=>c.handling_unit_id===job?.handling_unit_id),p=cargo?.visible?cargo.position:actor?.position;
 if(job?.native_case==='source_long_transfer'&&sample.native_source_long){const native=sample.native_source_long,part=plan?.native_source_long_plan?.phases.find(p=>sample.at_s>=p.start_s&&sample.at_s<p.end_s),v=part?.moving_actor==='F01'?native.vehicles.find(v=>v.actor_id==='F01'):native.vehicles.find(v=>v.actor_id==='F02'),item=part?.moving_actor==='F01'?native.bridge.position:native.cargo.holder==='source_slot'?native.cradle.position:native.cargo.position;frame(v?[(item[0]+v.position[0])/2,1,(item[2]+v.position[2])/2]:[item[0],1,item[2]],16,[1,.95,1]);return;}
 const receipt=sample.native_receiving.find(r=>r.job_id===selected);
 let direction:XYZ=[.9,.95,1];
 if(receipt&&cargo&&(cargo.location.kind==='storage_slot'||['receiver_lowers_clear_HU','receiver_inserts_into_free_L1','receiver_releases_supported_HU'].includes(receipt.sample.phase_id))){
  const yaw=cargo.yaw_rad-Math.PI,c=Math.cos(yaw),s=Math.sin(yaw);direction=[.9*c-s,.95,-.9*s-c];
 }
 frame(p?[p[0],.9,p[2]]:[72,1.5,36],p?12:184,p?direction:[0,1.15,1]);
}
function details(job:ScenarioExecutionJob&{status:string},sample:WarehouseScenarioSample){const cargo=sample.cargo.find(h=>h.handling_unit_id===job.handling_unit_id);$('sc-detail-title').textContent=`${job.native_case==='source_long_transfer'?'Через восточные ворота':job.native_case==='long_crossdock'?'В буфер отгрузки':job.direction==='inbound'?'Приёмка':'Отгрузка'} · ${cargoNames[cargo?.archetype_id??'']??'Груз'}`;const parts=[!sourceRequestIds.has(job.request_id)?'Дополнительная демонстрационная заявка':null,`${job.port_id} · ${jobStatus(job)}`,`Груз: ${job.handling_unit_id}`,cargo?`${cargo.gross_mass_kg} кг · ${cargo.quantity_units} ед. · ${cargo.dimensions_xyz_m.join(' × ')} м`:null,job.actor_ids.length?`Исполнители: ${job.actor_ids.join(', ')}${job.vehicle_id?' / '+job.vehicle_id:''}`:null,job.destination_slot_id?`Ячейка: ${job.destination_slot_id}`:null,job.native_case==='long_crossdock'?'Оснастка: 40 кг. Общая поднимаемая масса: 240 кг. Подготовка поставщиком и забор получателем показаны как внешние границы.':null,job.native_case==='source_long_transfer'?'Оснастка 40 кг; съёмный инструмент 5 кг. Через ворота идёт груз с оснасткой: 240 кг. За воротами он остаётся на F02; разгрузка получателем не показана.':null,job.native_case==='source_long_transfer'&&job.arrival_s!==null&&job.arrival_s>job.deadline_at_s?`Полный проход: ${fmt(job.arrival_s)} · срок заявки: ${fmt(job.deadline_at_s)} · опоздание: ${fmt(job.arrival_s-job.deadline_at_s)}`:null,job.reason?reasonText(job.reason):null];$('sc-detail-text').textContent=parts.filter(Boolean).join(' · ');}
function display(sample:WarehouseScenarioSample){
 native!.apply(sample.at_s);effects?.apply(sample.at_s,{playing:clock!.snapshot().playing,speed:clock!.snapshot().rate});visualCues?.apply(sample,{playing:clock!.snapshot().playing,reduced_motion:reduced.matches});displayCosts(sample);timeline.value=String(sample.at_s);$('sc-time').textContent=`${fmt(sample.at_s)} / ${fmt(sample.duration_s)}`;const c=sample.counts;$('sc-stock').textContent=String(c.onsite_handling_units);$('sc-upstream').textContent=String(c.upstream_handling_units);$('sc-downstream').textContent=String(c.downstream_handling_units);$('sc-completed').textContent=String(c.completed_visual);$('sc-resources').textContent=`${c.workers} / ${c.vehicles}`;$('sc-live-summary').textContent=`В пути: ${c.travelling} · В очереди: ${c.queued} · Ожидают обработки: ${c.native_join_required}`;$('sc-phase').textContent=c.travelling?'Работники и техника следуют к задачам':c.native_join_required?'Проверенные маршруты и ожидающие действия':'Заявки смены';$('sc-request-count').textContent=String(c.requests)+(c.requests-sourceRequestIds.size?' · '+(c.requests-sourceRequestIds.size)+' доп.':'');
 if(!selected&&sample.jobs.length)selected=sample.jobs[0]!.job_id;const key=JSON.stringify([selected,sample.jobs.map(j=>[j.job_id,j.status,j.reason])]);if(key!==rowsKey){rowsKey=key;$('sc-jobs').innerHTML=sample.jobs.map(j=>{const cargo=sample.cargo.find(h=>h.handling_unit_id===j.handling_unit_id);return `<button class="sc-job" role="listitem" type="button" data-job="${esc(j.job_id)}" data-status="${j.status==='native_join_required'?'blocked':j.status==='completed_visual'?'completed':j.status}" aria-pressed="${j.job_id===selected}"><strong>${j.direction==='inbound'?'↓':'↑'} ${esc(cargoNames[cargo?.archetype_id??'']??'Груз')}</strong><em>${esc(jobStatus(j))}</em><small>${esc(j.port_id)}</small><small>${fmt(j.requested_at_s)}</small></button>`;}).join('');}
 const ports=[...new Set(sample.jobs.map(j=>j.port_id))].sort();$('sc-port-status').innerHTML=ports.map(id=>{const jobs=sample.jobs.filter(j=>j.port_id===id),active=jobs.filter(j=>['travelling','native_join_required'].includes(j.status)).length;return `<span class="sc-port" data-active="${active>0}">${esc(id)}${active?' · '+active:''}</span>`;}).join('');const job=sample.jobs.find(j=>j.job_id===selected),receipt=sample.native_receiving.find(r=>r.job_id===selected);if(job)details(job,sample);if(job?.native_case&&sample.native_manual&&job.handling_unit_id===sample.native_manual.handling_unit_id)$('sc-phase').textContent=manualPhaseNames[sample.native_manual.phase_id]??'Обработка короба';else if(receipt)$('sc-phase').textContent=receivingPhaseNames[receipt.sample.phase_id]??'Приёмка короба';else if(job?.native_case==='long_crossdock')$('sc-phase').textContent=sample.native_long?.cargo.attached?'Перенос закреплённого длинномера':sample.native_long?.cargo.location==='outbound_buffer'?'Длинномер доставлен в буфер отгрузки':'Приём закреплённого длинномера';if(job?.native_case==='source_long_transfer'&&sample.native_source_long){const location=sample.native_source_long.cargo.location;$('sc-phase').textContent=location==='source_slot'?'Подготовка оснастки и подход к грузу':location==='controlled_pre_retention_handling'?'Подбор и фиксация длинномера':location==='outside_gate_retained'?'Длинномер за воротами; остаётся на погрузчике':'Перевозка закреплённого длинномера';}camera(sample);base!.requestRender();
}
function seek(value:number){if(phase!=='ready'||!clock)return;pause();displayCurrent(clock.seek(value));}
function tick(now:number){raf=0;if(phase!=='ready'||!clock)return;if(document.hidden){pause();return;}const elapsed=last?(now-last)/1000:0;last=now;try{displayCurrent(clock.advance(elapsed));if(clock.snapshot().playing)raf=requestAnimationFrame(tick);else pause();}catch(error){fail(error);}}
function setPlaying(value:boolean){if(phase!=='ready'||!clock)return;pause();if(value){displayCurrent(clock.play());play.setAttribute('aria-pressed','true');play.textContent='Пауза';raf=requestAnimationFrame(tick);}}
async function text(url:string,signal:AbortSignal){const result=await fetch(import.meta.env.BASE_URL+url.replace(/^\//,''),{signal,cache:'no-store'});if(!result.ok)throw Error('SCENARIO_SOURCE_UNAVAILABLE:'+url);return result.text();}
async function load(){
 const token=++epoch;
 abort?.abort();
 const own=abort=new AbortController(),id=scenario.value as WarehouseScenarioId|'N4';
 dispose();setState('loading');
 const timer=setTimeout(()=>own.abort(),60000);
 let pendingNative:ReturnType<typeof createWarehouseScenarioScene>|undefined;
 let pendingManual:WarehouseManualTransfer|undefined;
 let pendingReceiving:WarehouseReceivingManualTransfer[]=[];
 try{
  const [values,policyText,inputText]=await Promise.all([
   Promise.all(keys.map(k=>text(WAREHOUSE_BASE_FILES[k],own.signal))),
   text('/data/v3/route-policy-v3.json',own.signal),
   id==='N4'?Promise.resolve(''):text(WAREHOUSE_SCENARIO_SOURCES[id].url,own.signal)
  ]);
  if(token!==epoch)return;own.signal.throwIfAborted();
  if(id!=='N4'&&await sha(inputText)!==WAREHOUSE_SCENARIO_SOURCES[id].sha256)throw Error('SCENARIO_INPUT_HASH_MISMATCH');
  const texts=Object.fromEntries(keys.map((k,i)=>[k,values[i]!])) as WarehouseTexts;
  const bundle=await adaptWarehouseV3(texts),policy=await validateRoutePolicy(policyText,bundle);
  const input:unknown=id==='N4'?null:JSON.parse(inputText);
  const originalRequestIds=id==='N4'?[]:(input as {inputs:{requests:WarehouseRequest[]}}).inputs.requests.map(q=>q.request_id);
  const heavy=id==='N2'?compileWarehouseHeavyInboundPlan(bundle,await verifyWarehouseHeavyInboundSources(texts,await text('/data/v3/heavy-inbound-fixture.json',own.signal))):undefined;
  const additional=id==='N2'?createWarehouseAdditionalHeavyCases(bundle).map(c=>c):[];
  const connectorText=id==='N2'||id==='N3'?await text('/data/v3/additional-heavy-connectors.json',own.signal):undefined;
  const packet=additional.length?await validateAdditionalHeavyPacket(connectorText!):undefined;
  const additionalPlans=packet?additional.map(c=>compileWarehouseAdditionalHeavyCase(bundle,policy,c,packet)):[];
  const sourceLong=id==='N3'?await compileWarehouseLongSourceOperationPlan(bundle,policy,connectorText!,await text('/data/v3/long-source-tool-route.json',own.signal)):undefined;
  if(token!==epoch)return;own.signal.throwIfAborted();
  let context:Parameters<typeof createWarehouseScenarioScene>[0]|undefined;
  const sc=await createWarehouseScene(host,bundle,{
   signal:own.signal,
   progress:(done,total)=>{if(token===epoch)$('sc-loading').textContent=`Собираем склад · ${Math.round(done/total*100)}%`;},
   select:()=>{},renderPass:(renderer,scene,camera)=>{if(token!==epoch||own.signal.aborted)return;context=scene;renderScenarioPass(token,own.signal,id,renderer,scene,camera);}
  });
  if(token!==epoch){sc.dispose();return;}
  if(own.signal.aborted){sc.dispose();own.signal.throwIfAborted();}
  base=sc;
  if(!context)throw Error('SCENARIO_SCENE_CONTEXT_MISSING');
  if(id==='N4'){
   const pendingText=await text(WAREHOUSE_SCENARIO_SOURCES.N0.url,own.signal);
   if(token!==epoch)return;own.signal.throwIfAborted();
   if(await sha(pendingText)!==WAREHOUSE_SCENARIO_SOURCES.N0.sha256)throw Error('STAFFING_PENDING_INPUT_HASH_MISMATCH');
   const pendingPlan=await compileWarehouseScenarioExecution(bundle,policy,JSON.parse(pendingText),{scenario_id:'N0',allow_semantic_rebase:true});
   if(token!==epoch)return;own.signal.throwIfAborted();
   const pendingWork=await createWarehouseStaffingPendingWork(bundle,pendingPlan);
   if(token!==epoch)return;own.signal.throwIfAborted();
   const nextStaffing=await createStaffingComparison(bundle,createWarehouseRouter(bundle,policy).route,{pending_work:pendingWork});
   if(token!==epoch)return;own.signal.throwIfAborted();
   for(const [actor,station]of [['P01','PK05'],['P02','PK06']] as const){
    const result=await nextStaffing.assign({event_id:'v3:staffing3d:'+actor,actor_id:actor,target_role:'packer',station_id:station,at_s:40,until_s:360,handoff_s:8});
    if(token!==epoch)return;own.signal.throwIfAborted();
    if(!result.ok)throw Error('STAFFING_ASSIGNMENT_REFUSED:'+result.reason);
   }
   const nextStaffNative=await createWarehouseStaffingScene(context,bundle,nextStaffing,{signal:own.signal});
   if(token!==epoch){nextStaffNative.dispose();return;}
   if(own.signal.aborted){nextStaffNative.dispose();own.signal.throwIfAborted();}
   staffing=nextStaffing;staffNative=nextStaffNative;clock=createStaffClock();clock.setRate(Number(rate.value));timeline.max='600';
   rowsKey='';frameKey='';setState('ready');
   $('sc-pair').textContent='A/B: те же заявки и штат · меняются назначения';
   $('sc-description').textContent='Два обученных комплектовщика переходят на свободные посты, меняют роль и возвращаются. Те же 24 человека.';
   $('sc-reduced').hidden=!reduced.matches;displayCurrent(clock.sample());return;
  }
  pendingNative=createWarehouseScenarioScene(context,bundle);
  const recipe=createWarehouseManualWorkflowRoute(bundle,policy,{port_id:id==='N1'?'OUT_S_EXPRESS':'OUT_W_RETAIL'});
  const readSource=async(path:string)=>{
   const response=await fetch(import.meta.env.BASE_URL+path.replace(/^frontend\/public\//,''),{signal:own.signal,cache:'no-store'});
   if(!response.ok)throw Error('SCENARIO_MODEL_UNAVAILABLE');return response.arrayBuffer();
  };
  pendingManual=await createWarehouseManualTransfer(context,bundle,recipe,{readSource});
  if(token!==epoch)return;own.signal.throwIfAborted();
  const n1Request=id==='N1'?await validateWarehouseReceivingN1Input(inputText,bundle,{allow_semantic_rebase:true}):undefined;
  if(token!==epoch)return;own.signal.throwIfAborted();
  const firstReceipt=createWarehouseReceivingWorkflowRoute(bundle,policy,n1Request?{n1_request:n1Request}:{});
  pendingReceiving.push(await createWarehouseReceivingManualTransfer(context,bundle,firstReceipt,{signal:own.signal,readSource}));
  if(token!==epoch)return;own.signal.throwIfAborted();
  if(id!=='N1'){
   const extraReceipt=createWarehouseReceivingWorkflowRoute(bundle,policy,{port_id:'IN_E_PARCEL',native_manual_dependency:pendingManual,reserved_slot_ids:[firstReceipt.target.slot_id]});
   const extension=extraReceipt.extra_materialization;
   if(!extension)throw Error('RECEIVING_EXTRA_DECLARATION_REQUIRED');
   const materialized=input as {inputs:{requests:WarehouseRequest[]};upstream_handling_units?:V3Record[]};
   materialized.inputs.requests.push(structuredClone(extension.request));
   materialized.upstream_handling_units??=[];
   materialized.upstream_handling_units.push(structuredClone(extension.upstream_handling_unit));
   pendingReceiving.push(await createWarehouseReceivingManualTransfer(context,bundle,extraReceipt,{signal:own.signal,readSource}));
   if(token!==epoch)return;own.signal.throwIfAborted();
  }
  const sourceLongConcurrency=sourceLong?await validateWarehouseSourceLongConcurrencyCertificate(await text('/'+SOURCE_LONG_CONCURRENCY_CERTIFICATE.path,own.signal),bundle,sourceLong,pendingManual):undefined;
  if(token!==epoch)return;own.signal.throwIfAborted();
  if(sourceLong)await pendingNative.prepareSourceLong(sourceLong,{signal:own.signal,readSource});
  if(token!==epoch)return;own.signal.throwIfAborted();
  const compileOptions={
   scenario_id:id,allow_semantic_rebase:true,native_heavy_plan:heavy,
   native_additional_heavy_plans:additionalPlans,native_manual_case:pendingManual,native_source_long_plan:sourceLong,native_source_long_concurrency_certificate:sourceLongConcurrency,native_receiving_cases:pendingReceiving,
   pedestrian_motion:pendingNative.preparePedestrianRoute
  };
  const planA=await compileWarehouseScenarioExecution(bundle,policy,input,{...compileOptions,variant:'A'});
  if(token!==epoch)return;own.signal.throwIfAborted();
  const planB=await compileWarehouseScenarioExecution(bundle,policy,input,{...compileOptions,variant:'B'});
  if(token!==epoch)return;own.signal.throwIfAborted();
  const pairCheck=compareWarehouseScenarioCosts(planA,planB);
  if(pairCheck.result!=='tie'||pairCheck.winner!==null||planA.native_manual_case!==planB.native_manual_case||planA.native_heavy_plan!==planB.native_heavy_plan||planA.native_long_crossdock_plan!==planB.native_long_crossdock_plan||planA.native_source_long_plan!==planB.native_source_long_plan||planA.native_receiving_cases?.some((p,i)=>p!==planB.native_receiving_cases?.[i])||planA.native_additional_heavy_plans?.some((p,i)=>p!==planB.native_additional_heavy_plans?.[i]))throw Error('SCENARIO_NOOP_PAIR_REQUIRED');
  if(token!==epoch)return;own.signal.throwIfAborted();
  pendingNative.bind(planA,{native_heavy_plan:heavy,native_additional_heavy_plans:additionalPlans,native_manual_case:pendingManual,native_source_long_plan:sourceLong,native_receiving_cases:pendingReceiving});
  native=pendingNative;pendingNative=undefined;pendingManual=undefined;pairedPlans=Object.freeze({A:planA,B:planB});plan=pairedPlans[variant];
  sourceRequestIds=new Set(originalRequestIds);
  pendingReceiving=[];
  clock=createWarehouseScenarioClock(planA);clock.setRate(Number(rate.value));effects=createWarehouseScenarioEffects(planA);visualCues=createWarehouseScenarioVisualCues(context,bundle,planA);timeline.max=String(plan.duration_s);
  rowsKey='';frameKey='';setState('ready');
  $('sc-pair').textContent='A/B: одинаковые заявки · размещение сохранено';
  $('sc-description').textContent=id==='N2'?'Тяжёлая приёмка: конечные места, допустимая техника и очередь входящих грузов.':id==='N3'?'Исходный длинномер забирают из стеллажа, закрепляют и перевозят через восточные ворота. Те же два погрузчика и исходные заявки.':id==='N1'?'Меняется поток заявок между воротами; исходный состав склада сохраняется.':'Обычная смена. Если перестройка не обоснована, размещение сохраняется.';
  $('sc-reduced').hidden=!reduced.matches;displayCurrent(clock.sample());
 }catch(error){for(const receipt of pendingReceiving)receipt.dispose();pendingReceiving=[];pendingManual?.dispose();pendingManual=undefined;pendingNative?.dispose();pendingNative=undefined;if(token===epoch)fail(error);}
 finally{for(const receipt of pendingReceiving)receipt.dispose();pendingManual?.dispose();pendingNative?.dispose();clearTimeout(timer);}
}
function syncSound(){
 const state=effects?.snapshot();
 const button=$<HTMLButtonElement>('sc-sound'),volume=$<HTMLInputElement>('sc-volume');
 button.disabled=phase!=='ready'||!effects;
 button.setAttribute('aria-pressed',String(!!state&&!state.muted));
 button.textContent=state&&!state.muted?'Звук включён':'Звук выключен';
 volume.disabled=phase!=='ready'||!state||state.muted;
 if(state)volume.value=String(state.volume);
}
$('sc-sound').addEventListener('click',()=>{
 const own=effects;if(!own||phase!=='ready')return;
 if(!own.snapshot().muted){own.setMuted(true);syncSound();return;}
 void own.unlock().then(ok=>{if(effects!==own||phase!=='ready')return;own.setMuted(!ok);syncSound();if(!ok)$('sc-sound').textContent='Повторить включение звука';});
});
$('sc-volume').addEventListener('input',()=>{effects?.setVolume(Number($<HTMLInputElement>('sc-volume').value));});
function displayCosts(sample:WarehouseScenarioSample){
 $('sc-costs').hidden=false;
 const key=String(Math.floor(sample.at_s));
 if(key===costKey&&clock?.snapshot().playing)return;
 costKey=key;const c=summarizeWarehouseScenarioCosts(plan!,sample.at_s),format=(v:number)=>v.toLocaleString('ru-RU',{maximumFractionDigits:0})+' с';
 $('sc-wait-cost').textContent=format(c.request_wait_s);
 $('sc-person-cost').textContent=format(c.person_reservation_s);
 $('sc-vehicle-cost').textContent=format(c.vehicle_reservation_s);
 $('sc-relocation-cost').textContent=c.inventory_relocation_s===null?'Не рассчитано':format(c.inventory_relocation_s);
}
play.addEventListener('click',()=>setPlaying(!clock?.snapshot().playing));$('sc-reset').addEventListener('click',()=>{if(clock){pause();displayCurrent(clock.reset());}});timeline.addEventListener('input',()=>seek(Number(timeline.value)));rate.addEventListener('change',()=>{clock?.setRate(Number(rate.value));});scenario.addEventListener('change',()=>{selected=null;void load();});$('sc-retry').addEventListener('click',()=>void load());$('sc-jobs').addEventListener('click',event=>{const button=(event.target as HTMLElement).closest<HTMLButtonElement>('[data-job],[data-worker]');if(button&&clock){selected=button.dataset.job??button.dataset.worker!;rowsKey='';displayCurrent(clock.sample());}});
for(const button of document.querySelectorAll<HTMLButtonElement>('[data-view]'))button.addEventListener('click',()=>{view=button.dataset.view!;frameKey='';for(const other of document.querySelectorAll<HTMLButtonElement>('[data-view]'))other.setAttribute('aria-pressed',String(other===button));if(clock)displayCurrent(clock.sample());});
for(const button of document.querySelectorAll<HTMLButtonElement>('[data-variant]'))button.addEventListener('click',()=>setVariant(button.dataset.variant as 'A'|'B'));
$('sc-compare').addEventListener('click',()=>setComparison(!comparison));
reduced.addEventListener('change',()=>{$('sc-reduced').hidden=!reduced.matches;if(reduced.matches)pause();});document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});host.addEventListener('webglcontextlost',event=>{event.preventDefault();if(phase==='ready'){dispose();setState('error','Графика браузера перезапустилась. Повторите загрузку.');}},true);window.addEventListener('pagehide',()=>{epoch++;abort?.abort();dispose();setState('disposed');});
Object.assign(window,{__QOIMA_SCENARIO_V3__:{snapshot:()=>({phase,variant,scenario_id:scenario.value,clock:clock?.snapshot()??null,sample:clock?.sample()??null,effects:effects?.snapshot()??null,visual_cues:visualCues?.snapshot()??null,costs:plan?summarizeWarehouseScenarioCosts(plan,clock?.snapshot().at_s):null,comparison:{enabled:comparison,selected_variant:variant,frame:comparisonFrame,paired:!!pairedPlans,costs:pairedPlans?compareWarehouseScenarioCosts(pairedPlans.A,pairedPlans.B,clock?.snapshot().at_s):null},staffing:staffing?{A:staffing.sample('A',clock?.snapshot().at_s??0),B:staffing.sample('B',clock?.snapshot().at_s??0),pending_work:staffing.pending_work??null}:null,native:native?.snapshot()??staffNative?.snapshot()??null,plan:plan?{variant:plan.variant,scenario_id:plan.scenario_id,materialized_input_sha256:plan.materialized_input_sha256,source_epoch:plan.source_epoch,source_request_ids:[...sourceRequestIds],supplemental_request_ids:plan.jobs.filter(j=>!sourceRequestIds.has(j.request_id)).map(j=>j.request_id),visual_extensions:plan.visual_extensions,placement:plan.placement,jobs:plan.jobs,routes:plan.routes,events:plan.events}:null,source_kind:'visual_fixture',engine_operation:false}),seek,setPlaying,setVariant,setComparison,setScenario:(id:WarehouseScenarioId|'N4')=>{if(id==='N4'||id in WAREHOUSE_SCENARIO_SOURCES){scenario.value=id;selected=null;return load();}},reload:load}});

function createStaffClock(){let at=0,playing=false,speed=1,disposed=false;const live=()=>{if(disposed)throw Error('STAFFING_CLOCK_DISPOSED');};const sample=()=>{live();return at;};const seek=(seconds:number)=>{live();if(!Number.isFinite(seconds))throw Error('INVALID_STAFFING_TIME');at=Math.max(0,Math.min(600,seconds));if(at===600)playing=false;return at;};return{sample,seek,advance:(elapsed:number)=>{live();if(!Number.isFinite(elapsed)||elapsed<0)throw Error('INVALID_STAFFING_ELAPSED');return playing?seek(at+elapsed*speed):at;},play:()=>{live();if(at===600)at=0;playing=true;return at;},pause:()=>{live();playing=false;return at;},reset:()=>{live();playing=false;at=0;return at;},setRate:(value:number)=>{live();if(![1,4,10,30,60].includes(value))throw Error('INVALID_STAFFING_RATE');speed=value;return at;},snapshot:()=>{live();return{at_s:at,playing,rate:speed,duration_s:600,disposed:false};},dispose:()=>{disposed=true;playing=false;}};}
function displayCurrent(value:WarehouseScenarioSample|number){if(typeof value==='number')displayStaff(value);else display(value);}
function displayStaff(seconds:number){
 $('sc-costs').hidden=true;
 const staffFrame=staffing!.sample(variant,seconds),shown=staffNative!.apply(variant,seconds),actual=new Map(shown.actors.map(a=>[a.actor_id,a]));timeline.value=String(seconds);$('sc-time').textContent=fmt(seconds)+' / 10:00';$('sc-stock').textContent='530';$('sc-upstream').textContent='0';$('sc-downstream').textContent='0';$('sc-completed').textContent='0';$('sc-resources').textContent='24 / 2';$('sc-request-count').textContent='24 человека';const moving=staffFrame.workers.filter(w=>['walking','returning'].includes(w.phase)).length;$('sc-phase').textContent=moving?'Работники переходят между постами':'Распределение ролей';$('sc-live-summary').textContent='На переходе: '+moving+' · Незавершённая работа сохранена';
 if(!selected||!staffFrame.workers.some(w=>w.actor_id===selected))selected='P01';const roles:Record<string,string>={picker:'Комплектовщик',packer:'Упаковщик',receiver:'Приёмщик',shipper:'Отгрузка',forklift_driver:'Водитель'},phases:Record<string,string>={baseline:'На своём месте',break:'Перерыв',handoff:'Передача задачи',walking:'Переход',assigned:'Новая роль',returning:'Возврат',restored:'Исходная роль'};const key=JSON.stringify([selected,staffFrame.workers.map(w=>[w.actor_id,w.effective_role,w.phase])]);if(key!==rowsKey){rowsKey=key;$('sc-jobs').innerHTML=[...staffFrame.workers].sort((a,b)=>Number(['P01','P02','K05','K06'].includes(b.actor_id))-Number(['P01','P02','K05','K06'].includes(a.actor_id))).map(w=>'<button class="sc-job" type="button" data-worker="'+esc(w.actor_id)+'" aria-pressed="'+(selected===w.actor_id)+'"><strong>'+esc(w.actor_id)+' · '+esc(roles[w.effective_role])+'</strong><em>'+esc(phases[w.phase])+'</em><small>'+esc(w.station_id??'Склад')+'</small></button>').join('');}
 $('sc-port-status').innerHTML=['PK05','PK06'].map(station=>'<span class="sc-port" data-active="'+staffFrame.workers.some(w=>w.station_id===station&&w.available)+'">'+station+'</span>').join('');const worker=staffFrame.workers.find(w=>w.actor_id===selected)!;$('sc-detail-title').textContent=worker.actor_id+' · '+roles[worker.effective_role];$('sc-detail-text').textContent=phases[worker.phase]+(worker.retained_task?worker.retained_task.remaining_work_s===null?' · Исходная заявка сохранена в очереди; остаток времени не измерен':' · Незавершённое задание сохранено: '+worker.retained_task.remaining_work_s+' с':'')+' · Роль меняется после прихода на пост; идентификатор работника сохраняется.';const p=actual.get(worker.actor_id)?.position??worker.planned_position_m;if(view==='job')frameAtStaff(p);else if(view==='top')frame([72,0,36],164,[0,1,.0001]);else frame([72,1.5,36],184,[0,1.15,1]);base!.requestRender();
}
function frameAtStaff(p:readonly number[]){frame([p[0]!,.9,p[2]!],12,[.9,.95,1]);}

const unmountRelocationCosts=mountWarehouseRelocationCosts(document.getElementById('sc-relocation-host')!);
window.addEventListener('pagehide',unmountRelocationCosts,{once:true});
const requestedScenario=new URLSearchParams(location.search).get('scenario');if(requestedScenario&&[...Object.keys(WAREHOUSE_SCENARIO_SOURCES),'N4'].includes(requestedScenario))scenario.value=requestedScenario;
void load();
