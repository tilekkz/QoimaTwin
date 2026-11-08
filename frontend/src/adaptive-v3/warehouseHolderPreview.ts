import type {createWarehouseScene} from './warehouseScene';
import type {WarehouseBundle} from './warehouseTypes';
import type {CargoDestination} from './warehouseCargo';

type Scene=Awaited<ReturnType<typeof createWarehouseScene>>;
type Phase='idle'|'loading'|'ready'|'blocked'|'error'|'disposed';
const el=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id) as T;
const demos:Record<string,{label:string;archetype:string;destination:CargoDestination}>={
 'actor-small':{label:'P01 · коробка в руках',archetype:'SMALL_CARTON',destination:{kind:'actor',actor_id:'P01',anchor_id:'two-hand-small'}},
 'cart-small':{label:'C01 · коробка в верхнем tote',archetype:'SMALL_CARTON',destination:{kind:'cart',cart_id:'C01',anchor_id:'upper-tote'}},
 'belt-small':{label:'Линия · малый короб',archetype:'SMALL_CARTON',destination:{kind:'belt',cell_id:'V3-C-MAIN-000'}},
 'belt-standard':{label:'Линия · стандартный короб',archetype:'STANDARD_CARTON',destination:{kind:'belt',cell_id:'V3-C-MAIN-000'}},
};
for(const [archetype,label]of Object.entries({HEAVY_BOX:'тяжёлый ящик',PALLET_LOAD:'паллетный груз',IBC:'IBC',LONG_BUNDLE:'длинномер с cradle',DRUM:'бочка',FRAGILE_CRATE:'хрупкий груз'}))demos['vehicle-'+archetype]={label:'FL01 · '+label,archetype,destination:{kind:'vehicle',vehicle_id:'FL01',anchor_id:'forks'}};

/** Stationary contact inspection only. A reset restores the frozen stock snapshot. */
export function createWarehouseHolderPreview(bundle:WarehouseBundle,scene:Scene,callbacks:{stopRoutes:()=>Promise<unknown>|undefined;focusCargo:(id:string)=>boolean;refresh:()=>void}){
 const select=el<HTMLSelectElement>('holder-select'),reset=el<HTMLButtonElement>('holder-reset'),retry=el<HTMLButtonElement>('holder-retry'),status=el('holder-status'),events=new AbortController();
 let phase:Phase='idle',selected='',error:string|null=null,errorKind:string|null=null,activeHU:string|null=null,serial=0,disposed=false,loading:AbortController|undefined;
 select.replaceChildren(new Option('Исходное размещение',''));for(const [id,d]of Object.entries(demos))select.add(new Option(d.label,id));
 function controls(){select.value=selected;select.disabled=disposed;reset.disabled=disposed||(phase==='idle'&&!loading);retry.hidden=phase!=='error';}
 function resetHolders(){if(disposed)return false;serial++;loading?.abort();loading=undefined;scene.resetCargoBindings();phase='idle';selected='';error=errorKind=null;activeHU=null;status.textContent='Выберите опору для осмотра контакта. Действия и задания ещё не выполняются.';callbacks.refresh();controls();return true;}
 async function activate(id:string){
  if(disposed)return false;if(!id)return resetHolders();const token=++serial;loading?.abort();loading=new AbortController();const owned=loading;selected=id;error=errorKind=null;activeHU=null;
  if(!Object.hasOwn(demos,id)){phase='blocked';selected='';status.textContent='Эта опора не зарегистрирована. Выберите вариант из списка.';controls();return false;}
  await callbacks.stopRoutes();if(token!==serial||disposed)return false;scene.resetCargoBindings();callbacks.refresh();phase='loading';status.textContent='Готовим проверенные опоры и позу…';controls();
  let timedOut=false;const timer=setTimeout(()=>{timedOut=true;owned.abort();},12000);
  try{
   await scene.ensureCargoHolders(owned.signal);if(token!==serial||disposed||owned.signal.aborted)return false;
   const demo=demos[id],hu=bundle.fixture.inputs.initial_stock.find(h=>h.archetype_id===demo.archetype)!;
   const result=scene.applyCargoBindings([{handling_unit_id:hu.handling_unit_id,destination:demo.destination}]);if(!result.ok){phase='blocked';error=result.reason;status.textContent='Размещение на опоре отклонено: '+result.reason;controls();return false;}
   activeHU=hu.handling_unit_id;phase='ready';status.textContent=demo.destination.kind==='actor'?'Статическое удержание той же коробки. Контакт пальцев; трение — модельное допущение.':'Груз на исходной опоре в масштабе 1:1. Это осмотр контакта; перевозка и задания ещё не выполняются.';callbacks.refresh();callbacks.focusCargo(activeHU);controls();return true;
  }catch(e){if(token!==serial||disposed)return false;phase='error';error=e instanceof Error?e.message:'HOLDER_LOAD_FAILED';errorKind=timedOut?'timeout':e instanceof TypeError?'network':'package';status.textContent=timedOut?'Опоры загружаются слишком долго. Повторите попытку.':'Не удалось подготовить опоры. Исходный склад доступен; повторите загрузку.';controls();return false;}
  finally{clearTimeout(timer);if(loading===owned)loading=undefined;}
 }
 select.addEventListener('change',()=>void activate(select.value),{signal:events.signal});reset.addEventListener('click',resetHolders,{signal:events.signal});retry.addEventListener('click',()=>void activate(selected).then(ok=>{if(ok)select.focus();else if(!retry.hidden)retry.focus();}),{signal:events.signal});
 function dispose(){if(disposed)return;resetHolders();disposed=true;serial++;loading?.abort();events.abort();phase='disposed';controls();}
 controls();status.textContent='Выберите опору для осмотра контакта. Действия и задания ещё не выполняются.';
 return {activate,reset:resetHolders,dispose,snapshot:()=>({phase,selected,error,error_kind:errorKind,active_HU:activeHU,source_kind:'visual_fixture',engine_operation:false,operational_admission:false,actions_scheduled:0,completed_jobs:0})};
}
