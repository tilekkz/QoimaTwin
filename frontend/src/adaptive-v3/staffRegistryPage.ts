import './staffRegistry.css';
import {validateWorkerRegistry,clipStandUrl,type WorkerRegistry,type RoleLegend} from './workerRegistry';

type Fault={kind:'network'|'timeout'|'not_found'|'validation'|'server';message:string};
type State={kind:'initial'|'loading';data:null;error:null}|{kind:'error';data:null;error:Fault}|{kind:'ready'|'refreshing'|'stale';data:WorkerRegistry;error:Fault|null};
const node=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id) as T;
const main=node('staff-catalogue'),query=node<HTMLInputElement>('worker-query'),filter=node<HTMLSelectElement>('role-filter'),refresh=node<HTMLButtonElement>('refresh-registry'),retry=node<HTMLButtonElement>('retry-load');
let state:State={kind:'initial',data:null,error:null},serial=0,controller:AbortController|undefined,disposed=false,lastSuccess:string|null=null,renderedData:WorkerRegistry|null=null;
const initialParams=new URL(location.href).searchParams;query.value=(initialParams.get('q')??'').slice(0,64);let desiredRole=initialParams.get('role')??'all';
const icons:Record<string,string>={cart:'<path d="M7 7h4l3 13h14l3-10H12M15 25h.1M27 25h.1" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',carton:'<path d="m8 11 11-6 11 6-11 6Zm0 0v12l11 6V17m0 12 11-6V11" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linejoin="round"/>',incoming_arrow:'<path d="M19 5v14m-6-6 6 6 6-6M8 20v7h22v-7" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="square" stroke-linejoin="miter"/>',outgoing_arrow:'<path d="M19 20V6m-6 6 6-6 6 6M8 20v7h22v-7" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="square" stroke-linejoin="miter"/>',forklift:'<path d="M6 24V14h10v10m-8-10V7h10v17M24 6v22h8M5 27h14m3-5h6" fill="none" stroke="currentColor" stroke-width="2.5"/><circle cx="10" cy="27" r="3" fill="currentColor"/><circle cx="20" cy="27" r="3" fill="currentColor"/>'};
function badge(role:RoleLegend){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.classList.add('role-badge');svg.setAttribute('viewBox','0 0 38 48');svg.setAttribute('aria-hidden','true');svg.innerHTML=icons[role.icon]+`<text x="19" y="43" text-anchor="middle">${role.code}</text>`;return svg;}
function element<K extends keyof HTMLElementTagNameMap>(tag:K,text?:string,className?:string){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;}
function legend(data:WorkerRegistry){
  const host=node('role-legend');host.replaceChildren();filter.replaceChildren(new Option('Все роли','all'));
  for(const r of data.roles){const card=element('div',undefined,'role-card');card.dataset.role=r.role;card.style.setProperty('--role-color',r.color);card.append(badge(r));const copy=element('div');copy.append(element('strong',r.label),element('span',`${r.code} · ${r.count} чел.`));card.append(copy);host.append(card);filter.add(new Option(r.label,r.role));}
}
function members(){
  const data=state.data;if(!data)return;const term=query.value.trim().toUpperCase(),selected=filter.value,workers=data.workers.filter(w=>(selected==='all'||w.baseline_role===selected)&&w.actor_id.includes(term));
  const list=node('worker-list'),expanded=new Set([...list.querySelectorAll('details[open]')].map(d=>d.closest<HTMLElement>('[data-actor-id]')?.dataset.actorId));list.replaceChildren();node('result-count').textContent=`Показано ${workers.length} из 24`;
  node('empty-results').hidden=workers.length!==0;node('empty-query').textContent=`По запросу «${query.value.trim()}»${selected==='all'?'':' в выбранной роли'} совпадений нет. Поиск выполняется по ID работников.`;
  for(const w of workers){
    const role=data.roles.find(r=>r.role===w.baseline_role)!,item=element('li',undefined,'worker-card'),header=element('header'),copy=element('div');item.dataset.actorId=w.actor_id;item.dataset.role=w.baseline_role;item.style.setProperty('--role-color',role.color);
    const label=element('div',undefined,'worker-role'),dot=element('span',undefined,'role-dot');dot.setAttribute('aria-hidden','true');label.append(dot,document.createTextNode(role.label));copy.append(element('h3',w.actor_id),label);header.append(badge(role),copy);item.append(header);
    if(w.assigned_vehicle_id)item.append(element('p','Техника: '+w.assigned_vehicle_id,'worker-vehicle'));
    const details=element('details'),summary=element('summary',`Клипы роли · ${w.clip_ids.length}`),clips=element('ul');details.open=expanded.has(w.actor_id);details.append(summary,clips);
    for(const id of w.clip_ids){const c=data.clips.find(c=>c.clip_id===id)!,li=element('li'),a=element('a',c.label);a.href=clipStandUrl(c);a.dataset.clipId=id;li.append(a,element('small',c.duration_s?`${c.duration_s} с · визуальный клип`:'Статичная поза'),element('p',c.prerequisites));clips.append(li);}
    item.append(details);list.append(item);
  }
}
function render(){
  main.dataset.phase=state.kind;const data=state.data,busy=state.kind==='initial'||state.kind==='loading'||state.kind==='refreshing',fault=state.error;
  refresh.disabled=false;refresh.setAttribute('aria-disabled',String(busy));refresh.setAttribute('aria-busy',String(busy));retry.hidden=!(state.kind==='error'||state.kind==='stale')||fault?.kind==='not_found'||fault?.kind==='validation';retry.disabled=busy;node('package-help').hidden=!(fault?.kind==='not_found'||fault?.kind==='validation');node('catalogue-content').hidden=!data;
  refresh.hidden=!data&&(fault?.kind==='not_found'||fault?.kind==='validation');
  query.disabled=!data;filter.disabled=!data;node<HTMLButtonElement>('clear-filters').disabled=!data;
  const text=state.kind==='initial'?'':state.kind==='loading'?'Загружаем реестр работников…':state.kind==='refreshing'?'Обновляем каталог. Текущий список доступен.':state.kind==='ready'?`Реестр загружен · 24 исходных ID · ${new Date(lastSuccess!).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'})}`:state.kind==='stale'?`${fault?.message} Показан сохранённый список от ${new Date(lastSuccess!).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'})}.`:fault?.message??'Не удалось загрузить каталог.';
  node('load-status').textContent=text;
  if(data){if(data!==renderedData){legend(data);filter.value=data.roles.some(r=>r.role===desiredRole)?desiredRole:'all';renderedData=data;}members();}
}
class LoadFault extends Error{constructor(readonly detail:Fault){super(detail.message);}}
async function load(){
  const token=++serial,previous=state.data;controller?.abort();controller=new AbortController();const owned=controller;let timeout=false,shownAt=0;
  state=previous?{kind:'refreshing',data:previous,error:null}:{kind:'initial',data:null,error:null};render();
  const show=setTimeout(()=>{if(token===serial&&!disposed&&state.kind==='initial'){shownAt=performance.now();state={kind:'loading',data:null,error:null};render();}},200),timer=setTimeout(()=>{timeout=true;owned.abort();},8000);
  try{
    const response=await fetch(import.meta.env.BASE_URL+'data/v3/worker-registry-v3.json',{signal:owned.signal,cache:'no-store'});
    if(!response.ok)throw new LoadFault(response.status===404?{kind:'not_found',message:'Файл реестра не найден в пакете V3. Используйте полный пакет или откройте каталог моделей.'}:{kind:'server',message:'Реестр временно недоступен. Повторите загрузку.'});
    let data:WorkerRegistry;try{data=validateWorkerRegistry(await response.json());}catch{throw new LoadFault({kind:'validation',message:'Данные реестра не соответствуют составу команды V3. Откройте каталог моделей или используйте проверенный пакет.'});}
    if(shownAt&&performance.now()-shownAt<300)await new Promise(r=>setTimeout(r,300-(performance.now()-shownAt)));
    if(token!==serial||disposed)return;lastSuccess=new Date().toISOString();state={kind:'ready',data,error:null};render();
  }catch(error){
    if(token!==serial||disposed)return;const fault=error instanceof LoadFault?error.detail:timeout?{kind:'timeout' as const,message:'Загрузка заняла слишком много времени. Повторите попытку.'}:{kind:'network' as const,message:'Нет связи с локальным каталогом. Проверьте подключение и повторите загрузку.'};state=previous?{kind:'stale',data:previous,error:fault}:{kind:'error',data:null,error:fault};render();
  }finally{clearTimeout(show);clearTimeout(timer);}
}
function remember(){const url=new URL(location.href);if(query.value)url.searchParams.set('q',query.value);else url.searchParams.delete('q');desiredRole=filter.value;if(desiredRole!=='all')url.searchParams.set('role',desiredRole);else url.searchParams.delete('role');history.replaceState(null,'',url);members();}
function clear(){query.value='';filter.value='all';remember();query.focus();}
query.addEventListener('input',remember);filter.addEventListener('change',remember);node('staff-filters').addEventListener('submit',event=>{event.preventDefault();remember();});node('clear-filters').addEventListener('click',clear);node('empty-clear').addEventListener('click',clear);refresh.addEventListener('click',()=>{if(state.kind!=='initial'&&state.kind!=='loading'&&state.kind!=='refreshing')void load();});retry.addEventListener('click',()=>void load().then(()=>{if(state.data)query.focus();else if(!retry.hidden)retry.focus();else node('package-help').focus();}));
window.addEventListener('offline',()=>{if(state.data){state={kind:'stale',data:state.data,error:{kind:'network',message:'Подключение потеряно. Поиск в загруженном каталоге доступен.'}};render();}});
const snapshot=()=>({phase:state.kind,error_kind:state.error?.kind??null,actor_count:state.data?.workers.length??0,roles:state.data?.roles??[],worker_ids:state.data?.workers.map(w=>w.actor_id)??[],visible_ids:[...document.querySelectorAll<HTMLElement>('[data-actor-id]')].map(e=>e.dataset.actorId),query:query.value,role_filter:filter.value,clip_links:document.querySelectorAll('[data-clip-id]').length,source_kind:'visual_fixture',engine_operation:false,last_success:lastSuccess});
Object.assign(window,{__QOIMA_STAFF_V3__:{snapshot,reload:load}});
window.addEventListener('pagehide',()=>{disposed=true;serial++;controller?.abort();});render();void load();
window.addEventListener('pageshow',event=>{if(event.persisted){disposed=false;void load();}});
