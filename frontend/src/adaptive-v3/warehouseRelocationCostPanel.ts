import binding from './warehouseRelocationCostBinding.json';
type Case={horizon_periods:number;comparison_inputs_sha256:string;decision:'keep_no_op';candidate_transfers:2;selected_transfers:0;cost:{gross_saving_proxy_s:number;initial_travel_take_place_loaded_and_return_proxy_s:number;wait_proxy_s:number;one_off_total_proxy_s:number;net_saving_proxy_s:number}};
type View={schema_id:string;source_kind:string;engine_operation:boolean;native_execution_admitted:boolean;headcount:number;handling_units:number;period_has_clock_hours:boolean;cases:Case[]};
export function mountWarehouseRelocationCosts(host:HTMLElement){
 const box=document.createElement('section');box.className='sc-costs';box.id='sc-relocation-check';
 const title=document.createElement('h2');title.textContent='Проверка двух перестановок';
 const choices=document.createElement('div');choices.className='sc-variants';choices.setAttribute('role','group');choices.setAttribute('aria-label','Горизонт расчётного примера');
 const status=document.createElement('p');status.setAttribute('role','status');status.textContent='Проверяем полную цену переносов…';
 const values=document.createElement('dl');
 const note=document.createElement('p');note.textContent='Расчётный пример по текущим маршрутам: подход к грузу, обработка, перенос, ожидание и обратный путь. Период — повтор потока, а не часы. Оценка не исполняет перестановки и не является измерением труда.';
 const retry=document.createElement('button');retry.type='button';retry.textContent='Повторить';retry.hidden=true;
 box.append(title,choices,status,values,note,retry);host.append(box);
 let request:AbortController|undefined,disposed=false;
 const seconds=(n:number)=>n.toLocaleString('ru-RU',{maximumFractionDigits:1})+' с';
 function show(c:Case){
  box.dataset.period=String(c.horizon_periods);status.textContent='Сохраняем размещение: эти переносы не окупаются.';
  for(const button of choices.querySelectorAll('button'))button.setAttribute('aria-pressed',String(Number(button.dataset.period)===c.horizon_periods));
  values.replaceChildren();
  for(const[label,n]of [['Ожидаемая экономия',c.cost.gross_saving_proxy_s],['Подход, обработка и пути',c.cost.initial_travel_take_place_loaded_and_return_proxy_s],['Ожидание ресурсов',c.cost.wait_proxy_s],['Цена переносов целиком',c.cost.one_off_total_proxy_s]] as const){const group=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=seconds(n);group.append(dt,dd);values.append(group);}
 }
 async function load(){request?.abort();const own=request=new AbortController();retry.hidden=true;box.dataset.state='loading';
  try{
   const response=await fetch(import.meta.env.BASE_URL+binding.url,{signal:own.signal,cache:'no-cache'});if(!response.ok)throw Error('RELOCATION_VIEW_UNAVAILABLE');const bytes=await response.arrayBuffer();
   const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');if(hash!==binding.sha256)throw Error('RELOCATION_VIEW_CHANGED');
   const d=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes)) as View;
   if(d.schema_id!=='qoima.relocation-full-cost-view.v1'||d.source_kind!=='analytical_fixture'||d.engine_operation!==false||d.native_execution_admitted!==false||d.headcount!==24||d.handling_units!==530||d.period_has_clock_hours!==false||d.cases.length!==2)throw Error('RELOCATION_VIEW_SCOPE');
   for(const[c,i]of d.cases.map((c,i)=>[c,i] as const)){const cost=c.cost;if(c.horizon_periods!==i+1||c.decision!=='keep_no_op'||c.candidate_transfers!==2||c.selected_transfers!==0||!/^[a-f0-9]{64}$/.test(c.comparison_inputs_sha256)||Object.values(cost).some(n=>typeof n==='number'&&!Number.isFinite(n))||Math.abs(cost.one_off_total_proxy_s-cost.initial_travel_take_place_loaded_and_return_proxy_s-cost.wait_proxy_s)>1e-7||Math.abs(cost.net_saving_proxy_s-cost.gross_saving_proxy_s+cost.one_off_total_proxy_s)>1e-7||cost.net_saving_proxy_s>=0)throw Error('RELOCATION_VIEW_ARITHMETIC');}
   if(disposed||own.signal.aborted)return;choices.replaceChildren();for(const c of d.cases){const button=document.createElement('button');button.type='button';button.dataset.period=String(c.horizon_periods);button.textContent=c.horizon_periods===1?'1 период':'2 периода';button.addEventListener('click',()=>show(c));choices.append(button);}box.dataset.state='ready';show(d.cases[0]!);
  }catch{if(disposed||own.signal.aborted)return;box.dataset.state='error';status.textContent='Не удалось загрузить проверенную цену переносов.';choices.replaceChildren();values.replaceChildren();retry.hidden=false;}
 }
 retry.addEventListener('click',()=>void load());void load();return()=>{disposed=true;request?.abort();box.remove();};
}
