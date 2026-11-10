import binding from './twinPlacementComparisonBinding.json';
import './twinPlacementComparison.css';

type Case={horizon_periods:number;comparison_inputs_sha256:string;baseline_proxy_cost_s:number;adapted_proxy_cost_s:number;relocation_proxy_cost_s:number;net_proxy_saving_s:number;transfer_count:number};
type Comparison={schema_id:string;source_kind:string;engine_operation:boolean;operational_admission:boolean;headcount:number;handling_units:number;queues_modelled:boolean;period_is_hours:boolean;cases:Case[]};
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const near=(a:number,b:number)=>Math.abs(a-b)<1e-6;
export function validatePlacementComparison(value:unknown):Comparison{
 const d=value as Comparison;
 if(!d||d.schema_id!=='qoima.placement-comparison-view.v1'||d.source_kind!=='analytical_fixture'||d.engine_operation!==false||d.operational_admission!==false||d.headcount!==24||d.handling_units!==530||d.queues_modelled!==false||d.period_is_hours!==false||!Array.isArray(d.cases)||d.cases.length!==4)throw Error('Некорректный расчёт размещения.');
 for(const [i,c]of d.cases.entries()){
  if(c.horizon_periods!==[1,2,4,8][i]||!Number.isInteger(c.transfer_count)||c.transfer_count<0||c.transfer_count>8||!/^[a-f0-9]{64}$/.test(c.comparison_inputs_sha256)||![c.baseline_proxy_cost_s,c.adapted_proxy_cost_s,c.relocation_proxy_cost_s,c.net_proxy_saving_s].every(finite)||c.baseline_proxy_cost_s<0||c.adapted_proxy_cost_s<0||c.relocation_proxy_cost_s<0||!near(c.baseline_proxy_cost_s-c.adapted_proxy_cost_s-c.relocation_proxy_cost_s,c.net_proxy_saving_s))throw Error('Стоимость перестановок не прошла проверку.');
 }
 if(d.cases[0].transfer_count!==0||d.cases[0].relocation_proxy_cost_s!==0||!near(d.cases[0].net_proxy_saving_s,0))throw Error('Исходный вариант должен допускать отсутствие переносов.');
 return d;
}

/** A separate, source-bound sensitivity example; choosing a period never changes 3D cargo or staff. */
export function mountPlacementComparison(host:HTMLElement){
 const box=document.createElement('section');box.id='tw-placement-cost';box.className='tw-scn-body';
 const title=document.createElement('h3');title.textContent='Окупаемость перестановок';
 const intro=document.createElement('p');intro.textContent='Расчётный пример для повторяющегося потока. Период — повтор потока, а не часы смены. Очереди и занятость работников здесь не моделируются.';
 const status=document.createElement('p');status.setAttribute('role','status');status.textContent='Загружаем оценку затрат…';
 const controls=document.createElement('div');controls.className='tw-seg tw-seg-wide';controls.setAttribute('role','group');controls.setAttribute('aria-label','Горизонт расчётного примера');
 const metrics=document.createElement('dl');metrics.className='tw-stats';
 const note=document.createElement('p');note.className='tw-pref-hint';note.textContent='В цену входят путь с грузом, обратный путь и резерв на обработку: 12 с для тележки, 40 с для погрузчика. Это отдельный расчётный пример; он не меняет показанную расстановку.';
 const retry=document.createElement('button');retry.type='button';retry.textContent='Повторить загрузку';retry.hidden=true;
 box.append(title,intro,status,controls,metrics,note,retry);host.append(box);
 let request:AbortController|undefined,disposed=false;
 const fmt=(v:number)=>v.toLocaleString('ru-RU',{maximumFractionDigits:1});
 function show(c:Case){
  box.dataset.horizon=String(c.horizon_periods);box.dataset.noop=String(c.transfer_count===0);
  status.textContent=c.transfer_count===0?'На выбранном горизонте выгоднее оставить груз на месте.':c.net_proxy_saving_s>0?'Экономия превышает разовую цену переносов.':'Переносы не окупаются на выбранном горизонте.';
  for(const b of controls.querySelectorAll('button'))b.setAttribute('aria-pressed',String(Number(b.dataset.period)===c.horizon_periods));
  metrics.replaceChildren();
  for(const [label,value]of [['До',fmt(c.baseline_proxy_cost_s)+' с'],['После',fmt(c.adapted_proxy_cost_s)+' с'],['Цена переносов',fmt(c.relocation_proxy_cost_s)+' с'],['Чистая экономия',fmt(c.net_proxy_saving_s)+' с'],['Переносов',String(c.transfer_count)],['Работников','24']]){
   const group=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;group.append(dt,dd);metrics.append(group);
  }
 }
 async function load(){
  request?.abort();const current=request=new AbortController();retry.hidden=true;box.dataset.phase='loading';
  try{
   const response=await fetch(import.meta.env.BASE_URL+binding.url,{signal:current.signal,cache:'no-cache'});if(!response.ok)throw Error('Загрузка недоступна.');const raw=await response.arrayBuffer();
   const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(v=>v.toString(16).padStart(2,'0')).join('');if(hash!==binding.sha256)throw Error('Данные изменились после проверки.');
   const data=validatePlacementComparison(JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw)));if(disposed||current.signal.aborted)return;
   controls.replaceChildren();for(const c of data.cases){const b=document.createElement('button');b.type='button';b.dataset.period=String(c.horizon_periods);b.textContent=String(c.horizon_periods);b.setAttribute('aria-label',`${c.horizon_periods} периодов`);b.addEventListener('click',()=>show(c));controls.append(b);}box.dataset.phase='ready';show(data.cases[0]);
  }catch(error){if(disposed||current.signal.aborted)return;box.dataset.phase='error';status.textContent='Не удалось загрузить проверенную оценку затрат. Повторите попытку.';controls.replaceChildren();metrics.replaceChildren();retry.hidden=false;}
 }
 retry.addEventListener('click',()=>void load());void load();
 return()=>{disposed=true;request?.abort();box.remove();};
}
