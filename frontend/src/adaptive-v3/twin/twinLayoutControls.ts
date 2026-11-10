import './twinLayoutControls.css';

export type LayoutMode='cargo'|'sections';
export type LayoutControlsState={mode:LayoutMode;ready:boolean;busy:boolean;message:string;racksA:number;racksB:number;newRacks:number;changedRacks:number;floorAreaA:number;floorAreaB:number};
export function createLayoutControls(host:HTMLElement,choose:(mode:LayoutMode)=>Promise<void>){
 const box=document.createElement('section');box.id='tw-layout-controls';box.className='tw-scn-body';
 box.innerHTML='<h3>Перестройка склада · B</h3><p>Меняется расположение секций и стеллажей. Исходные товары остаются в своих ячейках; заполнение доступных ячеек выбирается ниже.</p><div class="tw-seg tw-seg-wide" role="group" aria-label="Что перестраивать в варианте B"><button type="button" data-layout="cargo" aria-pressed="true">Только груз</button><button type="button" data-layout="sections" aria-pressed="false">Секции и стеллажи</button></div><p data-layout-status role="status">Готовим планировку…</p><dl class="tw-stats" data-layout-metrics></dl><p class="tw-pref-hint">Сравниваются две планировки, а не процесс монтажа. Стоимость перемещения стеллажей и выполнения работ пока не рассчитана.</p>';
 // Inside the panel's single scrolling body, under its header — not above the header.
 (host.querySelector('.tw-sheet-body')??host).prepend(box);let state:LayoutControlsState|undefined;
 for(const b of box.querySelectorAll<HTMLButtonElement>('[data-layout]'))b.addEventListener('click',()=>{if(state?.ready&&!state.busy)void choose(b.dataset.layout as LayoutMode);});
 function update(next:LayoutControlsState){
  state=next;box.dataset.mode=next.mode;box.dataset.phase=next.busy?'loading':next.ready?'ready':'error';
  for(const b of box.querySelectorAll<HTMLButtonElement>('[data-layout]')){b.disabled=!next.ready||next.busy;b.setAttribute('aria-pressed',String(b.dataset.layout===next.mode));}
  box.querySelector('[data-layout-status]')!.textContent=next.message;
  const metrics=box.querySelector('[data-layout-metrics]')!;metrics.replaceChildren();
  if(!next.ready)return;
  const rows=[['Стеллажей · A → B',`${next.racksA} → ${next.racksB}`],['Добавлено стеллажей',String(next.newRacks)],['Переставлено стеллажей',String(next.changedRacks)],['Площадь стеллажей',`${next.floorAreaA.toFixed(0)} → ${next.floorAreaB.toFixed(0)} м²`],['Исходный товар','530 грузовых единиц'],['Команда','24 человека']];
  // The two counts that are coloured on the floor of B carry the same colour here as their legend.
  const mark:Record<string,string>={'Добавлено стеллажей':'new','Переставлено стеллажей':'moved'};
  for(const [label,value]of rows){const div=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;if(next.mode==='sections'&&mark[label])div.dataset.mark=mark[label];div.append(dt,dd);metrics.append(div);}
 }
 return {update,dispose:()=>box.remove()};
}
