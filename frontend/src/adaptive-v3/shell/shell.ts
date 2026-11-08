/**
 * Shared QoimaTwin V3 shell for the classic pages (warehouse, staff, skills, model stand, start).
 * Loaded as its own module script, so page controllers stay untouched: it swaps the page header for one
 * navigation bar of the same height and adds the shared theme. Deep links from the old header are kept.
 * The full-screen compare page has its own floating version of the same menu.
 */
import './shell.css';

export const SECTIONS=[
 {href:'home-v3.html',label:'Старт',hint:'Идея и выбор демонстрации'},
 {href:'twin-v3.html',label:'Сравнение',hint:'Склад как сейчас и после перестройки'},
 {href:'warehouse-v3.html',label:'Склад',hint:'Исходный снимок и осмотр грузов'},
 {href:'staff-v3.html',label:'Команда',hint:'24 работника и их роли'},
 {href:'skills-v3.html',label:'Навыки',hint:'Допуски к постам и технике'},
 {href:'stand-v3.html',label:'Модели',hint:'Стенд принятых 3D-моделей'},
] as const;

const LOGO='<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11.5" cy="11" r="5.6"/><path d="M15.6 15.2l3.6 3.6"/></svg>';
const MENU='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 8h14M5 12h14M5 16h14"/></svg>';
const esc=(s:string)=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]!));

function mount(){
 const page=location.pathname.split('/').pop()||'home-v3.html';
 const old=document.querySelector<HTMLElement>('body > header');
 document.body.classList.add('qs');
 // Keep contextual/query/fragment and legacy destinations; the six main sections already have tabs.
 const sections=new Set(SECTIONS.map(s=>new URL(s.href,location.href).href)),seen=new Set<string>();
 const extras=old?[...old.querySelectorAll<HTMLAnchorElement>('a[href]')].filter(a=>{if(sections.has(a.href)||seen.has(a.href))return false;seen.add(a.href);return true;}):[];
 const tabs=SECTIONS.map(s=>`<a href="${s.href}"${s.href===page?' aria-current="page"':''}>${s.label}</a>`).join('');
 const bar=document.createElement('header');bar.className='qs-bar';
 bar.innerHTML=`<a class="qs-brand glass" href="home-v3.html" aria-label="QoimaTwin — на старт"><span class="qs-logo">${LOGO}</span><span>QoimaTwin</span></a>
  <nav class="qs-tabs" aria-label="Разделы">${tabs}</nav>
  <div class="qs-right">${extras.map(a=>`<a class="qs-extra" href="${esc(a.getAttribute('href')!)}">${esc(a.textContent!.trim())}</a>`).join('')}
   <button class="qs-more glass" type="button" aria-expanded="false" aria-controls="qs-menu" aria-label="Разделы">${MENU}</button></div>
  <nav id="qs-menu" class="qs-menu glass" aria-label="Разделы" data-open="false" inert>${SECTIONS.map(s=>`<a href="${s.href}"${s.href===page?' aria-current="page"':''}><b>${s.label}</b><span>${s.hint}</span></a>`).join('')}${extras.length?`<div class="qs-menu-context">${extras.map(a=>`<a href="${esc(a.getAttribute('href')!)}"><b>${esc(a.textContent!.trim())}</b></a>`).join('')}</div>`:''}</nav>`;
 if(old)old.replaceWith(bar);else document.body.prepend(bar);
 const more=bar.querySelector<HTMLButtonElement>('.qs-more')!,menu=bar.querySelector<HTMLElement>('#qs-menu')!;
 const setOpen=(open:boolean,restoreFocus=false)=>{if(!open&&restoreFocus&&menu.contains(document.activeElement))more.focus();menu.dataset.open=String(open);menu.toggleAttribute('inert',!open);more.setAttribute('aria-expanded',String(open));};
 more.addEventListener('click',()=>setOpen(menu.dataset.open!=='true'));
 document.addEventListener('pointerdown',e=>{if(!(e.target as HTMLElement).closest('.qs-more,#qs-menu'))setOpen(false);});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&menu.dataset.open==='true')setOpen(false,true);});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
