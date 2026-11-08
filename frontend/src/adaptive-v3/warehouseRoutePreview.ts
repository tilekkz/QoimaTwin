import {validateRoutePolicy,createWarehouseRouter,type RouteQuery,type RoutePlan} from './warehouseRouting';
import {compileVehicleRoutePreview,createRouteDistanceSampler,type VehicleRoutePreview} from './warehouseRoutePose';
import type {createWarehouseScene} from './warehouseScene';
import type {WarehouseBundle,XYZ} from './warehouseTypes';

type Scene=Awaited<ReturnType<typeof createWarehouseScene>>;
type Phase='idle'|'loading'|'ready'|'blocked'|'error'|'disposed';
const element=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id) as T;
const demos={
 'F01-heavy':{label:'FL01 · западная приёмка → HEAVY',actor:'F01',vehicle:'FL01',from:'v3:service:IN_W_BULK',to:'v3:module:HEAVY_W:001:B1:vehicle:node'},
 'F02-long':{label:'FL02 · B2B → LONG',actor:'F02',vehicle:'FL02',from:'v3:service:OUT_E_B2B',to:'v3:module:LONG_E:001:B1:vehicle:node'},
 'LONG-express-rejected':{label:'Проверка отказа · LONG → EXPRESS',actor:'F02',vehicle:'FL02',from:'v3:module:LONG_E:001:B1:vehicle:node',to:'v3:service:OUT_S_EXPRESS'},
} as const;

/** Optional display-only controller. Route releases neither stock nor a completed job. */
export function createWarehouseRoutePreview(bundle:WarehouseBundle,scene:Scene,callbacks:{focusActor:(id:string)=>boolean;overview:()=>void}){
 const select=element<HTMLSelectElement>('route-select'),play=element<HTMLButtonElement>('route-play'),reset=element<HTMLButtonElement>('route-reset'),retry=element<HTMLButtonElement>('route-retry'),slider=element<HTMLInputElement>('route-seek'),follow=element<HTMLInputElement>('route-follow'),speed=element<HTMLSelectElement>('route-speed'),status=element('route-status'),readout=element('route-time'),events=new AbortController();
 let phase:Phase='idle',selected='',plan:RoutePlan|null=null,clip:VehicleRoutePreview|undefined,playing=false,at=0,raf=0,lastTick=0,serial=0,disposed=false,error:string|null=null,router:ReturnType<typeof createWarehouseRouter>|undefined,loading:Promise<ReturnType<typeof createWarehouseRouter>>|undefined,policyController:AbortController|undefined;
 const url=(key:string,value:string)=>{const target=new URL(location.href);if(value)target.searchParams.set(key,value);else target.searchParams.delete(key);history.replaceState(null,'',target);};
 select.replaceChildren(new Option('Исходный снимок · без маршрута',''));for(const [id,demo]of Object.entries(demos))select.add(new Option(demo.label,id));follow.checked=new URL(location.href).searchParams.get('route_follow')==='1';
 function controls(){const ready=phase==='ready';select.value=selected;play.disabled=reset.disabled=slider.disabled=speed.disabled=follow.disabled=!ready;play.textContent=playing?'Пауза':'Показать движение';retry.hidden=phase!=='error';slider.max=String(clip?.duration_s??0);slider.value=String(at);readout.textContent=clip?`${at.toFixed(1).replace('.',',')} / ${clip.duration_s.toFixed(1).replace('.',',')} с`:'—';}
 function pause(){playing=false;if(raf)cancelAnimationFrame(raf);raf=0;controls();}
 function setFollow(value:boolean){const wanted=Boolean(value&&clip&&phase==='ready');if(wanted)callbacks.focusActor(plan!.actor_id);follow.checked=wanted;url('route_follow',wanted?'1':'');scene.setFollowActor(wanted?plan!.actor_id:null);return wanted;}
 function seek(value:number){if(!clip||phase!=='ready'||!Number.isFinite(value))return false;at=Math.max(0,Math.min(clip.duration_s,value));scene.applyVehicleRoutePose(plan!.vehicle_id!,clip.sample(at));slider.value=String(at);readout.textContent=`${at.toFixed(1).replace('.',',')} / ${clip.duration_s.toFixed(1).replace('.',',')} с`;return true;}
 function tick(now:number){raf=0;if(!playing||!clip||disposed)return;const elapsed=Math.min(.1,Math.max(0,(now-lastTick)/1000));lastTick=now;seek(at+elapsed*Number(speed.value));if(at>=clip.duration_s){pause();status.textContent='Маршрут просмотрен. Запас и задания не изменены.';}else raf=requestAnimationFrame(tick);}
 function setPlaying(value:boolean){if(phase!=='ready'||!clip)return false;if(!value){pause();return true;}if(playing)return true;if(at>=clip.duration_s)seek(0);playing=true;lastTick=performance.now();controls();raf=requestAnimationFrame(tick);return true;}
 async function ensureRouter(){
  if(router)return router;if(loading)return loading;const owned=new AbortController();policyController=owned;let timedOut=false;const timer=setTimeout(()=>{timedOut=true;owned.abort();},8000);
  const operation=(async()=>{try{const response=await fetch(import.meta.env.BASE_URL+'data/v3/route-policy-v3.json',{signal:owned.signal,cache:'no-store'});if(!response.ok)throw Error(response.status===404?'В пакете нет правил маршрутов V3.':'Правила маршрутов временно недоступны.');const policy=await validateRoutePolicy(await response.text(),bundle);return createWarehouseRouter(bundle,policy);}catch(e){if(timedOut)throw Error('Правила маршрута загружаются слишком долго. Повторите попытку.');throw e;}finally{clearTimeout(timer);}})();loading=operation;
  try{const result=await operation;if(!disposed&&!owned.signal.aborted)router=result;return result;}finally{if(loading===operation)loading=undefined;}
 }
 async function activate(id:string){
  if(disposed)return false;const token=++serial;pause();clip=undefined;plan=null;at=0;error=null;selected=id;scene.resetRoutePreview();callbacks.overview();url('route',id);
  if(!id){policyController?.abort();loading=undefined;phase='idle';status.textContent='Выберите маршрут для осмотра. Груз и задания останутся без изменений.';setFollow(false);controls();return true;}
  if(!Object.hasOwn(demos,id)){phase='error';error='UNKNOWN_ROUTE_DEMO';status.textContent='Такого демонстрационного маршрута нет. Выберите маршрут из списка.';selected='';controls();retry.hidden=true;return false;}
  phase='loading';status.textContent='Проверяем допустимые рёбра маршрута…';controls();
  try{
   const source=await ensureRouter();if(token!==serial||disposed)return false;const demo=demos[id as keyof typeof demos],query:RouteQuery={source_kind:'visual_fixture',engine_operation:false,mode:'forklift',actor_id:demo.actor,vehicle_id:demo.vehicle,cargo_archetype_id:id==='LONG-express-rejected'?'LONG_BUNDLE':null,from_node_id:demo.from,to_node_id:demo.to,service_port_id:id==='LONG-express-rejected'?'OUT_S_EXPRESS':null,closed_arc_ids:[]};plan=source.route(query);
   if(!plan.ok){phase='blocked';status.textContent='Длинномер не допускается к этому порту. '+plan.reason;setFollow(false);controls();return false;}
   clip=compileVehicleRoutePreview(bundle,plan);const sampler=createRouteDistanceSampler(bundle,plan),points:XYZ[]=[];for(let i=0;i<sampler.arcs.length;i++){const arc=sampler.arcs[i],geometry=arc.fields.geometry as Record<string,unknown>,steps=geometry.kind==='rear_steer_arc'?90:1;for(let n=0;n<=steps;n++){if(i&&n===0)continue;points.push(sampler.sample(sampler.offsets[i]+arc.length_m*n/steps).position);}}
   phase='ready';scene.setRouteTrace(points);controls();seek(0);setFollow(follow.checked);status.textContent='Только осмотр пустой машины. Время демонстрационное; груз и задания не изменяются.';return true;
  }catch(e){if(token!==serial||disposed)return false;phase='error';error=e instanceof Error?e.message:'ROUTE_LOAD_FAILED';status.textContent=error.includes('POLICY_')?'Правила маршрута не совпадают с пакетом V3. Используйте согласованные данные.':e instanceof TypeError?'Нет связи с правилами маршрута. Повторите загрузку.':error;clip=undefined;plan=null;scene.resetRoutePreview();controls();return false;}
 }
 select.addEventListener('change',()=>void activate(select.value),{signal:events.signal});play.addEventListener('click',()=>setPlaying(!playing),{signal:events.signal});reset.addEventListener('click',()=>{pause();seek(0);status.textContent='Показ маршрута сброшен. Груз и задания не изменены.';},{signal:events.signal});slider.addEventListener('input',()=>{const value=Number(slider.value);pause();seek(value);},{signal:events.signal});follow.addEventListener('change',()=>setFollow(follow.checked),{signal:events.signal});retry.addEventListener('click',()=>void activate(selected).then(ok=>{if(ok)select.focus();else if(!retry.hidden)retry.focus();}),{signal:events.signal});document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();},{signal:events.signal});
 function dispose(){if(disposed)return;disposed=true;serial++;pause();policyController?.abort();events.abort();phase='disposed';clip=undefined;plan=null;scene.resetRoutePreview();}
 controls();status.textContent='Выберите маршрут для осмотра. Груз и задания останутся без изменений.';const restored=new URL(location.href).searchParams.get('route');if(restored)void activate(restored);
 return Object.freeze({activate,seek,pause,setPlaying,setFollow,dispose,snapshot:()=>({phase,selected,playing,at_s:at,duration_s:clip?.duration_s??null,error,plan,pose:clip?.sample(at)??null,follow:follow.checked,active_animation_frame:raf!==0,source_kind:'visual_fixture',engine_operation:false,completed_jobs:0,phases:clip?.phases??[]})});
}
