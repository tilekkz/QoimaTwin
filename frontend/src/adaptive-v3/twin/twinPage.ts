import './twin.css';
import {adaptWarehouseV3,WarehouseAdapterError,WAREHOUSE_BASE_FILES,type WarehouseTexts} from '../warehouseAdapter';
import {createWarehouseScene,type WarehouseView} from '../warehouseScene';
import type {WarehouseBundle,XYZ} from '../warehouseTypes';
import type {BoundCargo} from '../warehouseCargo';
import {ATMO_ZONES,CHAPTERS,DEMO_DURATION_S,DEMO_EVENTS,PRESENTER_STEPS,outboundCandidates,sampleAtmosphere,stateSegments,type AtmoState,type Variant} from './twinScenario';
import {bubbleBudget,reactionsAt,recoveredZones,workerStatus,zoneHistory,type Effects} from './twinScenario';
import {createNavigation} from './twinNavigation';
import {createMinimap} from './twinMinimap';
import {NOT_RUN,PORT_RU,SCENARIOS,STATUS_RU,type PortCount,type ScenarioCard} from './twinScenarios';
import {KIND_RU,buildIndex,search,shortId,type SearchEntry,type SearchHit,type SearchIndex,type SearchKind} from './twinSearch';
import {SIDE_SHIFT,createTwinRenderer,STATE_COLOR,STATE_RU,VARIANT_TITLE,type Mode,type Move,type Pose} from './twinRender';

const $=<T extends HTMLElement=HTMLElement>(sel:string)=>document.querySelector(sel) as T;
const $$=<T extends HTMLElement=HTMLElement>(sel:string)=>[...document.querySelectorAll<T>(sel)];
const app=$('#twin'),host=$('#tw-viewport'),layer=$('#tw-layer'),status=$('#tw-status'),retry=$<HTMLButtonElement>('#tw-retry'),blade=$('#tw-blade');
const play=$<HTMLButtonElement>('#tw-play'),clockOut=$('#tw-clock'),progress=$('#tw-progress'),river=$<HTMLCanvasElement>('#tw-river'),alertDot=$('#tw-alert');
const reduced=matchMedia('(prefers-reduced-motion: reduce)'),phone=matchMedia('(max-width: 720px)');
let observedReduced=reduced.matches;
const RIVER_ZONES=['PACKING_LIGHT_LINE','STANDARD_E','SMALL_E','STAGE_OUT_S_EXPRESS'];
const MODES:Mode[]=['side','swipe'];
/** Only two ways to compare remain; old links and API calls with other names land on «Рядом». */
const asMode=(m:string|null|undefined):Mode=>m==='swipe'?'swipe':'side';
const UI_ICON:Record<string,string>={
 side:'<svg viewBox="0 0 24 24"><rect x="3" y="5" width="8" height="14" rx="2.5"/><rect x="13" y="5" width="8" height="14" rx="2.5"/></svg>',
 swipe:'<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="3"/><path d="M12 3v18"/><circle cx="12" cy="12" r="2.2"/></svg>',
 pulse:'<svg viewBox="0 0 24 24"><path d="M3 12h4l2.5-6 5 12 2.5-6h4"/></svg>',
 moves:'<svg viewBox="0 0 24 24"><path d="M7 7h11l-3-3M17 17H6l3 3"/></svg>',
 home:'<svg viewBox="0 0 24 24"><path d="M4 9V5a1 1 0 0 1 1-1h4M20 9V5a1 1 0 0 0-1-1h-4M4 15v4a1 1 0 0 0 1 1h4M20 15v4a1 1 0 0 1-1 1h-4"/></svg>',
};
const OVERVIEW={target:[72,1.5,36] as XYZ,span:184};
/** «Рядом» frames both warehouses standing side by side; «Шторка» frames the single one. */
const SIDE_TARGET:XYZ=[72,1.5,36+SIDE_SHIFT[2]/2];
/** On a phone the pair stands diagonally in a tall view, so it can be framed closer. */
const sideOverview=()=>({target:SIDE_TARGET,span:phone.matches?178:250});
const overview=()=>mode==='side'?sideOverview():OVERVIEW;
/** Presenter focus points are written for one warehouse; in «Рядом» they frame the same spot in both copies. */
const focusFor=(f:{target:XYZ;span:number},m:Mode)=>m!=='side'?f:f.span>=OVERVIEW.span-1?sideOverview():{target:[f.target[0],f.target[1],f.target[2]+SIDE_SHIFT[2]/2] as XYZ,span:Math.max(f.span*1.25,120)};
const fmt=(n:number,d=0)=>n.toLocaleString('ru-RU',{maximumFractionDigits:d,minimumFractionDigits:d});
const mmss=(s:number)=>`${String(Math.floor(s/60)).padStart(2,'0')}:${String(Math.floor(s%60)).padStart(2,'0')}`;
const ZONE_EXTRA:Record<string,string>={FLEX_W:'FLEX запад',FLEX_E:'FLEX восток',RESERVE_W:'Резерв запад',RESERVE_E:'Резерв восток',STAGE_IN_W_BULK:'Приёмка запад · навал',STAGE_IN_E_PARCEL:'Приёмка восток · посылки',STAGE_IN_N_W:'Приёмка север-запад',STAGE_IN_N_E:'Приёмка север-восток',STAGE_OUT_E_B2B:'Отгрузка восток · B2B',STAGE_OUT_W_RETAIL:'Отгрузка запад · розница'};
const zoneLabel=(id:string)=>ATMO_ZONES.find(z=>z.id===id)?.label??ZONE_EXTRA[id]??id;
const esc=(s:string)=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]!));
for(const el of $$('.tw-mi[data-icon]'))el.innerHTML=UI_ICON[el.dataset.icon!]??'';

type Phase='initial'|'loading'|'ready'|'error'|'disposed';
let phase:Phase='initial',serial=0,controller:AbortController|undefined,bundle:WarehouseBundle|undefined;
let scene:Awaited<ReturnType<typeof createWarehouseScene>>|undefined,twin:ReturnType<typeof createTwinRenderer>|undefined;
const urlMode=new URL(location.href).searchParams.get('mode') as Mode;
let mode:Mode=asMode(urlMode);
let t=0,playing=!reduced.matches&&!document.hidden,speed=4,last=0,raf=0,split=.5,moves:Move[]=[],nowKey='',selectedId:string|null=null;
/* ---------- effects & sound preferences ---------- */
const store={get:(k:string)=>{try{return localStorage.getItem(k);}catch{return null;}},set:(k:string,v:string)=>{try{localStorage.setItem(k,v);}catch{/* private mode: keep in memory only */}}};
const EFFECTS:Effects[]=['full','calm','off'];
let effects:Effects=EFFECTS.includes(store.get('qoima.twin.effects') as Effects)?store.get('qoima.twin.effects') as Effects:reduced.matches?'calm':'full';
function applyEffects(){app.dataset.effects=effects;for(const b of $$<HTMLButtonElement>('[data-effects]'))b.setAttribute('aria-pressed',String(b.dataset.effects===effects));twin?.setEffects(effects,bubbleBudget(effects,phone.matches));}
for(const b of $$<HTMLButtonElement>('[data-effects]'))b.addEventListener('click',()=>{effects=b.dataset.effects as Effects;store.set('qoima.twin.effects',effects);applyEffects();});
phone.addEventListener('change',()=>{applyEffects();layoutPanels();});
window.addEventListener('resize',()=>requestAnimationFrame(positionBlade));
/** Soft synthesized cues. Muted until the viewer turns sound on; at most 4 voices, per-kind cooldown,
 *  only on forward playback crossings: seek, reset and presenter jumps stay silent. */
type Cue='danger'|'sos'|'control'|'refuse';
const CUE_NOTES:Record<Cue,[number,number,OscillatorType][]>={danger:[[660,0,'sine']],sos:[[440,0,'triangle'],[370,.2,'triangle']],control:[[523,0,'sine'],[784,.14,'sine']],refuse:[[196,0,'triangle']]};
let audio:AudioContext|undefined,master:GainNode|undefined,soundOn=false,volume=Number(store.get('qoima.twin.volume')??.5);const lastCue:Partial<Record<Cue,number>>={},voices=new Map<OscillatorNode,GainNode>();
const soundBtn=$<HTMLButtonElement>('#tw-sound'),volumeIn=$<HTMLInputElement>('#tw-volume');
function syncSound(){soundBtn.disabled=phase!=='ready';soundBtn.setAttribute('aria-pressed',String(soundOn));soundBtn.querySelector('span')!.textContent=soundOn?'Звук включён':'Звук выключен';volumeIn.disabled=!soundOn||phase!=='ready';volumeIn.value=String(volume);if(master)master.gain.value=soundOn&&!document.hidden&&phase==='ready'?volume*.35:0;}
function silenceAudio(close=false){
 if(master)master.gain.value=0;
 for(const [voice,gain]of voices){voice.onended=null;try{voice.stop();}catch{/* An already ended voice still needs disconnection. */}voice.disconnect();gain.disconnect();}voices.clear();
 if(close){const previous=audio;audio=undefined;master=undefined;soundOn=false;for(const kind of Object.keys(lastCue) as Cue[])delete lastCue[kind];if(previous)void previous.close().catch(()=>{});syncSound();}
}
soundBtn.addEventListener('click',()=>{if(phase!=='ready')return;soundOn=!soundOn;if(soundOn&&!audio){audio=new AudioContext();master=audio.createGain();master.connect(audio.destination);}if(soundOn){const context=audio!;void context.resume().catch(()=>{if(audio!==context)return;soundOn=false;silenceAudio();syncSound();});}else silenceAudio();syncSound();if(soundOn)cue('control');});
volumeIn.addEventListener('input',()=>{volume=Number(volumeIn.value);store.set('qoima.twin.volume',String(volume));syncSound();});
function cue(kind:Cue){
 if(!soundOn||!audio||!master||document.hidden||phase!=='ready'||voices.size>=4)return;const now=audio.currentTime;if(now-(lastCue[kind]??-9)<.9)return;lastCue[kind]=now;
 for(const [f,at,type] of CUE_NOTES[kind]){if(voices.size>=4)break;const o=audio.createOscillator(),g=audio.createGain(),t0=now+at,len=kind==='refuse'?.18:.38;voices.set(o,g);
  o.type=type;o.frequency.value=f;g.gain.setValueAtTime(0,t0);g.gain.linearRampToValueAtTime(.5,t0+.02);g.gain.exponentialRampToValueAtTime(.001,t0+len);o.connect(g).connect(master);o.start(t0);o.stop(t0+len+.02);o.onended=()=>{voices.delete(o);o.disconnect();g.disconnect();};}
}
function cuesBetween(from:number,to:number){
 const shown:Variant[]=['A','B'],fired=new Set<Cue>();
 for(const v of shown)for(const e of DEMO_EVENTS[v])if(e.at_s>from&&e.at_s<=to)fired.add(e.cause.startsWith('Отказ')?'refuse':e.state==='nodata'?'danger':e.state);
 for(const k of fired)cue(k);
}
syncSound();
function setPhase(next:Phase,message:string){phase=next;app.dataset.phase=next;status.textContent=message;retry.hidden=next!=='error';syncSound();}

/* ---------- floating surfaces ---------- */
const show=(el:HTMLElement,open:boolean)=>{el.dataset.open=String(open);el.toggleAttribute('inert',!open);};
const sheets=$$('.tw-sheet'),openers=$$<HTMLButtonElement>('button[data-open]'),menu=$('#tw-menu'),menuBtn=$<HTMLButtonElement>('#tw-menu-btn'),modeBtns=$$<HTMLButtonElement>('[data-mode]');
let sheet:string|null=null;
function setPop(which:'menu'|null){show(menu,which==='menu');menuBtn.setAttribute('aria-expanded',String(which==='menu'));}
/** Desktop panels open on the right and the comparison window narrows instead of hiding under them. */
function layoutPanels(){
 const right=!phone.matches&&!!sheet&&sheet!=='time',sel=!phone.matches&&sheets.find(s=>s.dataset.sheet==='sel')?.dataset.open==='true';
 app.dataset.right=String(right);twin?.setInset((right?376:0)+(sel?(right?346:346):0));positionBlade();drawMini();
}
function setSheet(name:string|null){
 sheet=name;app.dataset.sheet=name??'';for(const s of sheets)if(s.dataset.sheet!=='sel')show(s,s.dataset.sheet===name);
 for(const b of openers)b.setAttribute('aria-expanded',String(b.dataset.open===name));
 if(name&&phone.matches)select(null);setPop(null);if(name==='time')requestAnimationFrame(drawRiver);layoutPanels();
 if(name!=='source'&&openScn)openScenario(null);
}
for(const b of openers)b.addEventListener('click',()=>setSheet(sheet===b.dataset.open?null:b.dataset.open!));
for(const b of $$('[data-close]'))b.addEventListener('click',()=>{if(b.closest<HTMLElement>('.tw-sheet')?.dataset.sheet==='sel')select(null);else setSheet(null);});
menuBtn.addEventListener('click',()=>setPop(menu.dataset.open==='true'?null:'menu'));
document.addEventListener('pointerdown',e=>{const tgt=e.target as HTMLElement;if(!tgt.closest('#tw-menu,#tw-menu-btn'))setPop(null);if(!tgt.closest('#tw-search,#tw-search-btn'))setSearch(false);});

/* ---------- search ---------- */
const searchBox=$('#tw-search'),searchBtn=$<HTMLButtonElement>('#tw-search-btn'),searchIn=$<HTMLInputElement>('#tw-search-input'),searchList=$('#tw-search-list');
let searchIndex:SearchIndex=[],searchHits:SearchHit[]=[],searchActive=0;
const KIND_ICON:Record<SearchKind,string>={
 actor:'<svg viewBox="0 0 24 24"><circle cx="12" cy="7.5" r="3.2"/><path d="M5.5 20c.6-3.9 3.1-6 6.5-6s5.9 2.1 6.5 6"/></svg>',
 HU:'<svg viewBox="0 0 24 24"><path d="M4 8l8-4 8 4v8l-8 4-8-4z"/><path d="M4 8l8 4 8-4M12 12v8"/></svg>',
 port:'<svg viewBox="0 0 24 24"><path d="M4 20V5h16v15"/><path d="M8 20V9h8v11"/></svg>',
 zone:'<svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="3" stroke-dasharray="3 2.5"/></svg>',
 slot:'<svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 12h16M12 4v16"/></svg>',
};
function indexBundle(b:WarehouseBundle):SearchEntry[]{
 const role=(r:string)=>b.registry.roles.find(x=>x.role===r)?.label??r,byslot=new Map(b.fixture.inputs.initial_stock.map(h=>[h.location.slot_id,h]));
 return [
  ...b.registry.workers.map(w=>({kind:'actor' as const,id:w.actor_id,title:w.actor_id,sub:role(w.baseline_role)+(w.assigned_vehicle_id?` · ${w.assigned_vehicle_id}`:''),keys:[w.actor_id,role(w.baseline_role),w.baseline_role,w.assigned_vehicle_id??'']})),
  ...b.fixture.inputs.initial_stock.map(h=>({kind:'HU' as const,id:h.handling_unit_id,title:h.sku_id,sub:`${h.archetype_id} · ${shortId(h.location.slot_id)}`,keys:[h.handling_unit_id,h.sku_id,h.archetype_id,shortId(h.location.slot_id)]})),
  ...(b.layout.data.ports as {port_id:string;direction:string}[]).map(p=>{const dir=p.direction==='inbound'?'вход':'выход';return {kind:'port' as const,id:p.port_id,title:p.port_id,sub:`ворота · ${dir}`,keys:[p.port_id,'ворота',dir]};}),
  ...(b.layout.data.zones as {zone_id:string}[]).map(z=>({kind:'zone' as const,id:z.zone_id,title:zoneLabel(z.zone_id),sub:`участок · ${z.zone_id}`,keys:[z.zone_id,zoneLabel(z.zone_id)]})),
  ...b.layout.slots.map(sl=>{const h=byslot.get(sl.slot_id);return {kind:'slot' as const,id:sl.slot_id,title:shortId(sl.slot_id),sub:h?`занята · ${h.sku_id}`:'свободна',keys:[sl.slot_id]};}),
 ];
}
const SEARCH_TRIES=['P01','K03','DEMO_001','OUT_S_EXPRESS','Упаковка','SMALL_E:019'];
function renderSearch(){
 const q=searchIn.value;searchHits=search(searchIndex,q);searchActive=Math.min(searchActive,Math.max(0,searchHits.length-1));
 if(!searchHits.length){
  searchList.innerHTML=`<div class="tw-search-empty">${q.trim()?`<p>По запросу «${esc(q.trim())}» ничего нет. Ищите по ID работника, SKU, воротам, участку или ячейке.</p>`:'<p>Например:</p>'}<div class="tw-search-tries">${SEARCH_TRIES.map(x=>`<button type="button" data-try="${esc(x)}">${esc(x)}</button>`).join('')}</div></div>`;
  searchIn.removeAttribute('aria-activedescendant');return;
 }
 let last='';const side=mode==='side';
 searchList.innerHTML=searchHits.map((h,i)=>{const head=h.kind!==last?`<p class="tw-sgroup">${KIND_RU[h.kind]}</p>`:'';last=h.kind;
  return `${head}<button type="button" class="tw-shit" role="option" id="tw-sh-${i}" data-i="${i}" aria-selected="${i===searchActive}"><i>${KIND_ICON[h.kind]}</i><span><b>${esc(h.title)}</b><small>${esc(h.sub)}</small></span>${side?'<span class="tw-shit-copy"><span data-copy="A" title="Показать на складе A">A</span><span data-copy="B" title="Показать на складе B">B</span></span>':''}</button>`;}).join('');
 searchIn.setAttribute('aria-activedescendant',`tw-sh-${searchActive}`);
}
function setSearch(open:boolean){
 if((searchBox.dataset.open==='true')===open)return;show(searchBox,open);searchBtn.setAttribute('aria-expanded',String(open));
 if(open){setPop(null);searchActive=0;renderSearch();requestAnimationFrame(()=>{searchIn.focus();searchIn.select();});}
}
/** Takes the camera to a search hit on the chosen warehouse copy and selects it where that makes sense. */
function goSearch(h:SearchHit,copy:Variant='A'){
 if(!bundle||!twin)return;setSearch(false);const o=twin.offsetOf(copy);
 if(h.kind==='actor'||h.kind==='HU'){select(h.id,h.kind,copy);return;}
 if(h.kind==='slot'){const hu=bundle.fixture.inputs.initial_stock.find(x=>x.location.slot_id===h.id);if(hu){select(hu.handling_unit_id,'HU',copy);return;}
  const sl=bundle.layout.slots.find(x=>x.slot_id===h.id);if(sl){const m=bundle.layout.modules[sl.module_index].world_pos;fly([m[0]+o[0],0,m[2]+o[2]],16);}return;}
 if(h.kind==='port'){const p=(bundle.layout.data.ports as {port_id:string;world_pos:XYZ}[]).find(x=>x.port_id===h.id);if(p)fly([p.world_pos[0]+o[0],0,p.world_pos[2]+o[2]],34);return;}
 const z=(bundle.layout.data.zones as {zone_id:string;floor_bounds_xz_m:{min:[number,number];max:[number,number]}}[]).find(x=>x.zone_id===h.id);
 if(z){const b=z.floor_bounds_xz_m,w=b.max[0]-b.min[0],d=b.max[1]-b.min[1];fly([(b.min[0]+b.max[0])/2+o[0],0,(b.min[1]+b.max[1])/2+o[2]],Math.min(184,Math.max(24,Math.max(w,d)*1.2+8)));}
}
searchBtn.addEventListener('click',()=>setSearch(searchBox.dataset.open!=='true'));
searchIn.addEventListener('input',()=>{searchActive=0;renderSearch();});
searchIn.addEventListener('keydown',e=>{
 if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();if(!searchHits.length)return;searchActive=(searchActive+(e.key==='ArrowDown'?1:-1)+searchHits.length)%searchHits.length;renderSearch();document.getElementById(`tw-sh-${searchActive}`)?.scrollIntoView({block:'nearest'});}
 else if(e.key==='Enter'){e.preventDefault();const h=searchHits[searchActive];if(h)goSearch(h,e.shiftKey?'B':'A');}
 else if(e.key==='Escape'){e.preventDefault();e.stopPropagation();setSearch(false);searchBtn.focus();}
});
searchList.addEventListener('click',e=>{
 const t=e.target as HTMLElement,tryBtn=t.closest<HTMLElement>('[data-try]');if(tryBtn){searchIn.value=tryBtn.dataset.try!;searchActive=0;renderSearch();searchIn.focus();return;}
 const row=t.closest<HTMLElement>('.tw-shit');if(!row)return;goSearch(searchHits[Number(row.dataset.i)],(t.closest<HTMLElement>('[data-copy]')?.dataset.copy as Variant)??'A');
});
document.addEventListener('keydown',e=>{
 if(phase!=='ready')return;const typing=(e.target as HTMLElement).closest('input,textarea,select');
 if(((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k')||(e.key==='/'&&!typing)){e.preventDefault();setSearch(true);}
});

/* ---------- camera fly-to ---------- */
const homeBtn=$<HTMLButtonElement>('#tw-home');let flyRaf=0,flyTarget:{target:XYZ;span:number}|null=null;
/* ---------- minimap ---------- */
let mini:ReturnType<typeof createMinimap>|undefined,miniKey='',zoneRects=new Map<string,{min:[number,number];max:[number,number]}>();
/** Redrawn after every scene render, time step and layout change; skipped when nothing it shows has changed. */
function drawMini(){
 if(!mini||!scene||!twin||phase!=='ready')return;
 const st=scene.frameState(),R=twin.region(),key=JSON.stringify([st,R,mode,nowKey]);if(key===miniKey)return;miniKey=key;
 const quad=R?([[R.x,R.y],[R.x+R.w,R.y],[R.x+R.w,R.y+R.h],[R.x,R.y+R.h]] as const).map(([x,y])=>twin!.ground(x,y,0)):[];
 const states=Object.fromEntries((['A','B'] as Variant[]).map(v=>[v,Object.fromEntries(Object.entries(sampleAtmosphere(v,t)).map(([id,s])=>[id,s.state]))])) as Record<Variant,Record<string,AtmoState>>;
 mini.draw({shared:mode==='swipe',quad:quad.length&&quad.every(Boolean)?quad.map(p=>[p![0],p![2]] as [number,number]):null,states});
}
/** The default isometric direction; «Весь склад», presenter steps and key 0 return to it. */
const HOME_DIR:XYZ=[.9,1.15,1];
const yawElev=(d:XYZ)=>[Math.atan2(d[0],d[2]),Math.asin(d[1]/Math.hypot(...d))] as const;
const homeShown=()=>{const s=scene?.frameState();if(!s)return;const [y,e]=yawElev(s.dir),[hy,he]=yawElev(HOME_DIR);homeBtn.dataset.shown=String(Math.abs(s.span-overview().span)>1||s.target.some((v,i)=>Math.abs(v-overview().target[i])>1)||Math.abs(y-hy)>.02||Math.abs(e-he)>.02);};
/** Animated move; keeps the current viewing angle unless a direction is given. */
function fly(target:XYZ,span:number,dir?:XYZ){
 if(!scene)return;nav?.stop();cancelAnimationFrame(flyRaf);flyTarget={target:[...target],span};const sc=scene,from=sc.frameState();
 const [y0,e0]=yawElev(from.dir),[y1r,e1]=yawElev(dir??from.dir),y1=y0+Math.atan2(Math.sin(y1r-y0),Math.cos(y1r-y0)),turn=Math.hypot(y1-y0,e1-e0);
 // Gentle start and landing; longer trips take a little longer so the speed never spikes.
 const trip=Math.hypot(target[0]-from.target[0],target[2]-from.target[2])/Math.max(span,from.span)+Math.abs(Math.log(span/from.span))+turn,start=performance.now(),dur=reduced.matches?0:Math.min(1500,850+trip*420);
 const ease=(x:number)=>x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2,ls=Math.log(from.span),le=Math.log(span);
 const step=(now:number)=>{flyRaf=0;if(reconcileReducedMotion()||scene!==sc||phase!=='ready')return;const k=dur?Math.min(1,(now-start)/dur):1,e=ease(k);const yy=y0+(y1-y0)*e,ee=e0+(e1-e0)*e;sc.frameAt(from.target.map((v,i)=>v+(target[i]-v)*e) as XYZ,Math.exp(ls+(le-ls)*e),[Math.cos(ee)*Math.sin(yy),Math.sin(ee),Math.cos(ee)*Math.cos(yy)]);if(k<1)flyRaf=requestAnimationFrame(step);else flyTarget=null;};
 flyRaf=requestAnimationFrame(step);homeBtn.dataset.shown=String(Math.abs(span-overview().span)>1||target.some((v,i)=>Math.abs(v-overview().target[i])>1)||(!!dir&&dir!==HOME_DIR));
}
homeBtn.addEventListener('click',()=>fly(overview().target,overview().span,HOME_DIR));

/* ---------- link to this view: same place, moment and mode, opened paused ---------- */
const shareBtn=$<HTMLButtonElement>('#tw-share'),SHARE_LABEL='Ссылка на этот вид';
function viewUrl(){
 const u=new URL(location.href);u.searchParams.delete('present');u.searchParams.set('mode',mode);u.searchParams.set('t',String(Math.round(t)));
 const s=scene?.frameState();if(s){const [y,e]=yawElev(s.dir);u.searchParams.set('cam',[...s.target,s.span,y*180/Math.PI,e*180/Math.PI].map(n=>+n.toFixed(1)).join(','));}
 return u.href;
}
shareBtn.addEventListener('click',async()=>{
 const b=shareBtn.querySelector('b')!,url=viewUrl();history.replaceState(null,'',url);
 try{await navigator.clipboard.writeText(url);b.textContent='Ссылка скопирована';}catch{b.textContent='Ссылка — в адресной строке';}
 setTimeout(()=>{b.textContent=SHARE_LABEL;},1800);
});
function readViewUrl(sc:NonNullable<typeof scene>){
 const q=new URL(location.href).searchParams,tt=Number(q.get('t')),c=q.get('cam')?.split(',').map(Number);
 if(q.has('t')&&Number.isFinite(tt)){playing=false;seek(tt);}
 if(c?.length===6&&c.every(Number.isFinite)){
  const y=c[4]*Math.PI/180,e=Math.min(1.52,Math.max(.2,c[5]*Math.PI/180)),cl=(v:number,a:number,b:number)=>Math.min(b,Math.max(a,v));
  sc.frameAt([cl(c[0],-12,156),c[1],cl(c[2],-12,168)],cl(c[3],10,300),[Math.cos(e)*Math.sin(y),Math.sin(e),Math.cos(e)*Math.cos(y)]);homeShown();
 }
}

/* ---------- defence walk-through ---------- */
const present=$('#tw-present'),pTitle=$('#tw-present-title'),pText=$('#tw-present-text'),pStep=$('#tw-present-step'),pDots=$('#tw-present-dots'),pPrev=$<HTMLButtonElement>('#tw-present-prev'),pNext=$<HTMLButtonElement>('#tw-present-next');
let stepIndex=-1;
pDots.innerHTML=PRESENTER_STEPS.map(()=>'<i></i>').join('');
function goStep(i:number){
 if(phase!=='ready')return;stepIndex=Math.max(0,Math.min(PRESENTER_STEPS.length-1,i));const s=PRESENTER_STEPS[stepIndex];
 app.dataset.presenting='true';show(present,true);setPop(null);select(null);
 pStep.textContent=`Шаг ${stepIndex+1} из ${PRESENTER_STEPS.length}`;[...pDots.children].forEach((d,k)=>d.classList.toggle('is-on',k===stepIndex));
 for(const el of [pTitle,pText])el.style.animation='none';void present.offsetWidth;pTitle.textContent=s.title;pText.textContent=s.text;for(const el of [pTitle,pText])el.style.animation='';
 pPrev.disabled=stepIndex===0;pNext.textContent=stepIndex===PRESENTER_STEPS.length-1?'Завершить':'Дальше';
 setPlaying(false);seek(s.t);setMode(s.mode);setSheet(s.sheet&&!phone.matches?s.sheet:null);const f=focusFor(s.focus,s.mode);fly(f.target,f.span,HOME_DIR);if(s.play)setPlaying(true);
}
function endPresent(){if(stepIndex<0)return;stepIndex=-1;app.dataset.presenting='false';show(present,false);}
function nextPresent(){if(stepIndex<0)return;if(stepIndex>=PRESENTER_STEPS.length-1)endPresent();else goStep(stepIndex+1);}
$('#tw-present-btn').addEventListener('click',()=>goStep(0));
$('#tw-present-close').addEventListener('click',endPresent);
pPrev.addEventListener('click',()=>goStep(stepIndex-1));
pNext.addEventListener('click',nextPresent);

/* ---------- clock ---------- */
const PLAY='<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3.2v9.6c0 .6.6.9 1.1.6l7.4-4.8c.4-.3.4-.9 0-1.2L6.1 2.6C5.6 2.3 5 2.6 5 3.2z"/></svg>',PAUSE='<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3.5" y="2.5" width="3.2" height="11" rx="1.2"/><rect x="9.3" y="2.5" width="3.2" height="11" rx="1.2"/></svg>';
function syncPlay(){play.innerHTML=playing?PAUSE:PLAY;play.setAttribute('aria-label',playing?'Пауза':'Воспроизвести');}
function seek(next:number){
 t=Math.min(DEMO_DURATION_S,Math.max(0,next));clockOut.textContent=mmss(t);progress.style.width=t/DEMO_DURATION_S*100+'%';
 river.setAttribute('aria-valuenow',String(Math.round(t)));twin?.setTime(t);if(sheet==='time')drawRiver();renderNow();renderWorkerStatus();drawMini();
}
function tick(now:number){raf=0;if(reconcileReducedMotion()||!playing||phase!=='ready')return;const dt=Math.min(.1,(now-last)/1000);last=now;const before=t;seek(t+dt*speed);cuesBetween(before,t);if(t>=DEMO_DURATION_S){playing=false;syncPlay();return;}raf=requestAnimationFrame(tick);}
function setPlaying(next:boolean){playing=next;if(!playing&&raf){cancelAnimationFrame(raf);raf=0;}syncPlay();if(playing&&t>=DEMO_DURATION_S)seek(0);if(playing&&!raf&&phase==='ready'){last=performance.now();raf=requestAnimationFrame(tick);}}
play.addEventListener('click',()=>setPlaying(!playing));
for(const b of $$<HTMLButtonElement>('[data-speed]'))b.addEventListener('click',()=>{speed=Number(b.dataset.speed);for(const x of $$('[data-speed]'))x.setAttribute('aria-pressed',String(x===b));});
for(const c of CHAPTERS){const b=document.createElement('button');b.type='button';b.textContent=c.label;b.title=mmss(c.at_s);b.addEventListener('click',()=>{setPlaying(false);seek(c.at_s+.01);});$('#tw-chapters').append(b);}

/* ---------- time river ---------- */
const RL=128,LANE=11,GAP=4,GROUP=12;
function drawRiver(){
 const w=river.clientWidth,h=river.clientHeight,d=Math.min(devicePixelRatio||1,2);if(!w||!h)return;
 if(river.width!==Math.round(w*d)||river.height!==Math.round(h*d)){river.width=Math.round(w*d);river.height=Math.round(h*d);}
 const g=river.getContext('2d')!,sx=(s:number)=>RL+s/DEMO_DURATION_S*(w-RL-6);g.setTransform(d,0,0,d,0,0);g.clearRect(0,0,w,h);
 g.font='500 12px -apple-system,"Segoe UI Variable Text","Segoe UI",system-ui,sans-serif';g.textBaseline='middle';let y=8;
 for(const z of RIVER_ZONES){
  g.fillStyle='#1C2A28';g.textAlign='left';g.fillText(zoneLabel(z),0,y+LANE+GAP/2);
  (['A','B'] as Variant[]).forEach((v,i)=>{
   g.fillStyle='#8A9692';g.textAlign='right';g.fillText(v,RL-10,y+LANE/2+.5);
   for(const s of stateSegments(v,z)){const x0=sx(s.from_s)+1,x1=sx(s.to_s)-1;g.globalAlpha=s.state==='control'?.28:.95;g.fillStyle=STATE_COLOR[s.state];g.beginPath();g.roundRect(x0,y,Math.max(2,x1-x0),LANE,LANE/2);g.fill();}
   g.globalAlpha=1;y+=LANE+(i?0:GAP);
  });
  y+=GROUP;
 }
 const x=sx(t);g.fillStyle='#1C2A28';g.beginPath();g.roundRect(x-1.25,0,2.5,h,1.25);g.fill();g.beginPath();g.arc(x,5,5,0,Math.PI*2);g.fill();
}
const scrub=(e:PointerEvent)=>{const r=river.getBoundingClientRect();seek((e.clientX-r.left-RL)/(r.width-RL-6)*DEMO_DURATION_S);};
river.addEventListener('pointerdown',e=>{river.setPointerCapture(e.pointerId);setPlaying(false);scrub(e);});
river.addEventListener('pointermove',e=>{if(river.hasPointerCapture(e.pointerId))scrub(e);});
river.addEventListener('keydown',e=>{const step=e.key==='ArrowRight'?5:e.key==='ArrowLeft'?-5:0;if(!step)return;e.preventDefault();setPlaying(false);seek(t+step);});
new ResizeObserver(drawRiver).observe(river);

/* ---------- modes, blade ---------- */
let switchTimer=0;
function setMode(requested:Mode,animate=true){
 const next=asMode(requested),changed=next!==mode;mode=next;app.dataset.mode=next;
 clearTimeout(switchTimer);switchTimer=0;host.classList.remove('is-switching');
 for(const b of modeBtns)b.setAttribute('aria-checked',String(b.dataset.mode===next));blade.hidden=next!=='swipe';
 const url=new URL(location.href);url.searchParams.set('mode',next);history.replaceState(null,'',url);
 if(changed&&animate&&!reduced.matches&&phase==='ready'){host.classList.add('is-switching');switchTimer=window.setTimeout(()=>{switchTimer=0;twin?.setMode(mode);host.classList.remove('is-switching');},120);}
 else twin?.setMode(next);
 if(changed&&phase==='ready'&&scene){const o=overview();fly(o.target,o.span);}
 drawMini();
}
for(const b of modeBtns)b.addEventListener('click',()=>setMode(b.dataset.mode as Mode));
/** The blade lives inside the comparison window, which narrows when panels are open. */
function positionBlade(){const R=twin?.region();blade.style.left=R?`${R.x+R.w*split}px`:split*100+'%';}
const setSplit=(f:number)=>{split=Math.min(.92,Math.max(.08,f));positionBlade();blade.setAttribute('aria-valuenow',String(Math.round(split*100)));twin?.setSplit(split);};
blade.addEventListener('pointerdown',e=>{blade.setPointerCapture(e.pointerId);e.preventDefault();});
blade.addEventListener('pointermove',e=>{if(!blade.hasPointerCapture(e.pointerId))return;const r=host.getBoundingClientRect(),R=twin?.region()??{x:0,w:r.width};setSplit((e.clientX-r.left-R.x)/R.w);});
blade.addEventListener('keydown',e=>{const d=e.key==='ArrowLeft'?-.04:e.key==='ArrowRight'?.04:0;if(d){e.preventDefault();setSplit(split+d);}});
document.addEventListener('keydown',e=>{
 if(e.key==='Escape'){setPop(null);if(stepIndex>=0)endPresent();else if(sheet)setSheet(null);else select(null);return;}
 if(phase!=='ready'||e.altKey||e.ctrlKey||e.metaKey)return;const target=e.target as HTMLElement;if(target.closest('input,select,textarea,[role="slider"]'))return;
 // Presentation clickers send PageDown/PageUp; arrows work too while the walk-through is open.
 if(stepIndex>=0&&['ArrowRight','PageDown','ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();if(e.key==='ArrowRight'||e.key==='PageDown')nextPresent();else goStep(stepIndex-1);return;}
 if(e.key==='p'||e.key==='з'){if(stepIndex>=0)endPresent();else goStep(0);return;}
 if(/^[12]$/.test(e.key)){setMode(MODES[Number(e.key)-1]);return;}
 if('qQйЙeEуУ'.includes(e.key)){nav?.turnBy('qQйЙ'.includes(e.key)?-Math.PI/8:Math.PI/8);return;}
 if(e.key==='+'||e.key==='='||e.key==='-'||e.key==='_'){e.preventDefault();nav?.zoomBy(e.key==='-'||e.key==='_'?1.35:1/1.35);return;}
 if(e.key==='0'){fly(overview().target,overview().span,HOME_DIR);return;}
 if(e.key===' '&&!target.closest('button,a')){e.preventDefault();setPlaying(!playing);}
});

/* ---------- sheet content ---------- */
const rank:Record<AtmoState,number>={control:0,nodata:0,danger:1,sos:2};
/** Open "why" chain in the state sheet, as 'A:ZONE_ID'; kept across re-renders while time moves. */
let openIssue:string|null=null;
const CHAIN_VERB:Record<AtmoState,string>={control:'снова под контролем',danger:'опасность',sos:'SOS',nodata:'нет данных'};
function issueRow(v:Variant,id:string,state:AtmoState,cause:string,since:number){
 const k=`${v}:${id}`,open=openIssue===k,hist=open?zoneHistory(v,id,t):[];
 const chain=open?`<ol class="tw-chain">${hist.map(e=>`<li data-state="${e.state}"><time>${mmss(e.at_s)}</time><span><b>${CHAIN_VERB[e.state]}</b> ${esc(e.cause)}${e.from?`<button type="button" class="tw-src" data-k="${v}:${e.from_id}">волна от «${esc(e.from)}» →</button>`:''}</span></li>`).join('')}</ol>`:'';
 return `<div class="tw-issue-wrap" data-expanded="${open}"><button type="button" class="tw-issue" data-state="${state}" data-k="${k}" aria-expanded="${open}"><i></i><span><b>${esc(zoneLabel(id))} · ${STATE_RU[state]}</b>${esc(cause)}<small>с ${mmss(since)} · ${open?'скрыть причины':'почему и где'}</small></span></button>${chain}</div>`;
}
function renderNow(){
 if(phase!=='ready')return;const a=sampleAtmosphere('A',t),b=sampleAtmosphere('B',t),rec={A:recoveredZones('A',t),B:recoveredZones('B',t)},key=JSON.stringify([a,b,rec,openIssue]);if(key===nowKey)return;nowKey=key;
 const worst=[...Object.values(a),...Object.values(b)].reduce<AtmoState>((w,z)=>rank[z.state]>rank[w]?z.state:w,'control');alertDot.dataset.state=worst;
 const box=$('#tw-now');box.replaceChildren();
 for(const [v,s] of [['A',a],['B',b]] as const){
  const col=document.createElement('div');col.className='tw-now-col';col.dataset.v=v;
  const counts={sos:0,danger:0};for(const z of Object.values(s))if(z.state==='sos'||z.state==='danger')counts[z.state]++;
  const calm=Object.values(s).filter(z=>z.state==='control').length;
  col.innerHTML=`<p class="tw-now-head"><b>${v}</b><span>${VARIANT_TITLE[v]}</span><span class="tw-tally">${counts.sos?`<i data-k="sos">${counts.sos} SOS</i>`:''}${counts.danger?`<i data-k="danger">${counts.danger} под риском</i>`:''}<i data-k="ok">${calm} в контроле</i></span></p>`;
  const issues=Object.entries(s).filter(([,z])=>z.state!=='control').sort((x,y)=>rank[y[1].state]-rank[x[1].state]);
  if(!issues.length)col.insertAdjacentHTML('beforeend','<p class="tw-calm"><i></i>Все участки справляются</p>');
  for(const [id,z] of issues)col.insertAdjacentHTML('beforeend',issueRow(v,id,z.state,z.cause,z.since_s));
  if(rec[v].length){col.insertAdjacentHTML('beforeend','<p class="tw-group">Восстановились</p>');for(const id of rec[v])col.insertAdjacentHTML('beforeend',issueRow(v,id,'control',s[id].cause,s[id].since_s));}
  box.append(col);
 }
}
// Pointing at an issue row outlines its zone in the scene, so «where» is answered before the click.
$('#tw-now').addEventListener('pointerover',e=>{const b=(e.target as HTMLElement).closest<HTMLElement>('.tw-issue,.tw-src');const k=b?.dataset.k,r=k?zoneRects.get(k.slice(2)):undefined;if(r)twin?.highlightZone(r,k![0] as Variant);else restoreHl();});
$('#tw-now').addEventListener('pointerleave',()=>restoreHl());

/* ---------- scenarios N0–N4: declared inputs only, shown on the warehouse ---------- */
let openScn:string|null=null,pinnedHl:{min:[number,number];max:[number,number]}[]|null=null;
/** Hover highlights are temporary; when they end, the open scenario's zones come back. */
function restoreHl(){twin?.highlightZone(pinnedHl,'A');}
$('#tw-scn-note').textContent=NOT_RUN;
const portRows=(list:PortCount[])=>list.map(p=>{const d=p.after-p.before;return `<li data-d="${d>0?'up':d<0?'down':'same'}"><span>${esc(PORT_RU[p.port_id]??p.port_id)}</span><b>${p.before}${d?` → ${p.after}`:''}</b></li>`;}).join('');
function scenarioBody(c:ScenarioCard){
 const ports=c.ports?`<div class="tw-scn-ports"><p>Заявок по воротам${c.ports.inbound.concat(c.ports.outbound).some(p=>p.after!==p.before)?' · было → стало':''}</p><ul>${portRows(c.ports.inbound)}</ul><ul>${portRows(c.ports.outbound)}</ul></div>`:'';
 const src=c.source?`<p class="tw-scn-src">${c.source.task} · <span title="${esc(c.source.path)} · sha256 ${c.source.sha256}">входы ${c.source.sha256.slice(0,8)}</span></p>`:'<p class="tw-scn-src">Входы ещё не зафиксированы — это описание кандидата.</p>';
 return `<div class="tw-scn-body"><p>${esc(c.idea)}</p>${ports}<ul class="tw-scn-changes">${c.changes.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><p class="tw-scn-same"><b>Одинаково в A и B.</b> ${esc(c.same)}</p>${src}</div>`;
}
function renderScenarios(){
 $('#tw-scn').innerHTML=SCENARIOS.map(c=>{const open=openScn===c.id;return `<article class="tw-scn" data-open="${open}"><button type="button" class="tw-scn-head" data-scn="${c.id}" aria-expanded="${open}"><span class="tw-scn-n">${c.id}</span><b>${esc(c.title)}</b><i data-status="${c.status}">${STATUS_RU[c.status]}</i></button>${open?scenarioBody(c):''}</article>`;}).join('');
}
/** Opening a card outlines its zones on A and frames them; closing restores the plain view. */
function openScenario(id:string|null){
 openScn=id;const c=SCENARIOS.find(s=>s.id===id);renderScenarios();
 const rects=c?c.focus.map(z=>zoneRects.get(z)).filter((r):r is NonNullable<typeof r>=>!!r):[];pinnedHl=rects.length?rects:null;restoreHl();
 if(!rects.length||phase!=='ready')return;
 const x0=Math.min(...rects.map(r=>r.min[0])),x1=Math.max(...rects.map(r=>r.max[0])),z0=Math.min(...rects.map(r=>r.min[1])),z1=Math.max(...rects.map(r=>r.max[1]));
 const span=Math.min(184,Math.max(48,Math.max(x1-x0,z1-z0)*1.1+12));let cx=(x0+x1)/2,cz=(z0+z1)/2;
 // On a phone the sheet covers the lower half: aim below the zones so they land in the visible top part.
 if(phone.matches&&scene){const d=scene.frameState().dir,h=Math.hypot(d[0],d[2])||1,k=span*.95;cx+=d[0]/h*k;cz+=d[2]/h*k;}
 fly([cx,0,cz],span);
}
$('#tw-scn').addEventListener('click',e=>{const b=(e.target as HTMLElement).closest<HTMLElement>('[data-scn]');if(!b)return;const id=b.dataset.scn!;openScenario(openScn===id?null:id);document.querySelector<HTMLElement>(`[data-scn="${id}"]`)?.focus({preventScroll:true});});
renderScenarios();
$('#tw-now').addEventListener('click',e=>{
 const b=(e.target as HTMLElement).closest<HTMLButtonElement>('.tw-issue,.tw-src');if(!b)return;const k=b.dataset.k!,id=k.slice(2);
 // A wave link always opens its source; an issue row toggles.
 openIssue=b.classList.contains('tw-src')||openIssue!==k?k:null;nowKey='';
 // Expanding a row should not replay the entry animation of every row.
 const box=$('#tw-now');box.classList.add('tw-quiet');renderNow();requestAnimationFrame(()=>box.classList.remove('tw-quiet'));
 const f=openIssue&&twin?.zoneFocus(id,k[0] as Variant);if(f)fly(f.target,f.span);
 document.querySelector<HTMLButtonElement>(`.tw-issue[data-k="${k}"]`)?.focus({preventScroll:true});
});
function renderMoves(){
 const total=moves.reduce((s,m)=>s+m.move_m,0),gain=moves.reduce((s,m)=>s+m.before_m-m.after_m,0),outbound=bundle!.fixture.inputs.requests.filter(r=>r.direction==='outbound').length;
 $('#tw-diff-summary').innerHTML=[['Переносов',`${moves.length}<small> из ${outbound}</small>`],['Ближе к воротам',`${fmt(gain)}<small> м</small>`],['Цена переносов',`${fmt(total)}<small> м</small>`],['Не меняется','530<small> ГЕ · 24 чел.</small>']].map(([k,v])=>`<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
 const list=$('#tw-moves');list.replaceChildren();
 moves.forEach((m,i)=>{const li=document.createElement('li'),b=document.createElement('button');b.type='button';b.dataset.id=m.id;
  b.innerHTML=`<span class="tw-n">${i+1}</span><span><b>${esc(m.sku)}</b><small>${esc(m.archetype)} · к ${esc(m.port_id)}</small></span><span class="tw-gain">−${fmt(m.before_m-m.after_m)} м</span>`;
  b.addEventListener('click',()=>select(m.id,'HU'));li.append(b);list.append(li);});
 if(!moves.length)list.innerHTML='<li class="tw-empty">Ни один перенос не прошёл проверку адреса, поэтому B совпадает с A.</li>';
}
const ARROW='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h13M14 7l5 5-5 5"/></svg>';
function select(id:string|null,kind='HU',copy:Variant='A'){
 const off=twin?.offsetOf(copy)??[0,0,0],offB=twin?.offsetOf('B')??[0,0,0];
 selectedId=id;selectedKind=kind;statusKey='';const moved=moves.find(m=>m.id===id);twin?.setSelected(moved?id:null);twin?.setSelectedActor(kind==='actor'?id:null);
 for(const b of $$<HTMLButtonElement>('.tw-moves button'))b.setAttribute('aria-pressed',String(b.dataset.id===id));
 const panel=sheets.find(s=>s.dataset.sheet==='sel')!;if(!id||!bundle){show(panel,false);layoutPanels();return;}
 if(phone.matches&&sheet)setSheet(null);
 const box=$('#tw-selection'),kv=(rows:[string,string][])=>`<dl class="tw-kv">${rows.map(([k,v])=>`<dt>${k}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`;
 if(kind==='HU'){const hu=bundle.fixture.inputs.initial_stock.find(h=>h.handling_unit_id===id);if(!hu)return;
  $('#sh-sel').textContent='Груз';
  const route=moved?`<div class="tw-route"><div><small>Было · A</small><span>${esc(hu.location.slot_id.replace('v3:slot:',''))}</span></div>${ARROW}<div><small>Стало · B</small><span>${esc(moved.to_slot.replace('v3:slot:',''))}</span></div></div>`:`<div class="tw-route"><div style="grid-column:1/-1"><small>Адрес</small><span>${esc(hu.location.slot_id.replace('v3:slot:',''))} · не переносится</span></div></div>`;
  // A moved unit is framed from its old place in A to its new place in B, wherever B stands.
  if(moved){const a=moved.a.position,b=[moved.b.position[0]+offB[0],moved.b.position[1],moved.b.position[2]+offB[2]],d=Math.hypot(a[0]-b[0],a[2]-b[2]);fly([(a[0]+b[0])/2,0,(a[2]+b[2])/2],Math.min(184,Math.max(18,d*1.5+10)));}
  else{const pos=scene?.getCargoBindings().find(b=>b.handling_unit_id===id)?.position;if(pos)fly([pos[0]+off[0],0,pos[2]+off[2]],16);}
  box.innerHTML=`<h3>${esc(hu.sku_id)}</h3><p class="tw-sub">${esc(hu.archetype_id)} · ${fmt(hu.gross_mass_kg,2)} кг</p>${route}`+kv([['Количество',fmt(hu.quantity_units)+' ед.'],['Габариты',hu.dimensions_xyz_m.map(x=>fmt(x,2)).join(' × ')+' м'],...(moved?[['Ворота',moved.port_id],['До ворот',`${fmt(moved.before_m)} → ${fmt(moved.after_m)} м`],['Перенос',`${fmt(moved.move_m)} м по прямой`]] as [string,string][]:[])]);}
 else{const w=bundle.registry.workers.find(w=>w.actor_id===id);if(!w)return;$('#sh-sel').textContent='Работник';
  const spot=twin?.workers().find(s=>s.actor_id===id),head=twin?.actorPosition(id);if(head)fly([head[0]+off[0],0,head[2]+off[2]],20);
  box.innerHTML=`<h3>${esc(w.actor_id)}</h3><p class="tw-sub">${esc(bundle.registry.roles.find(r=>r.role===w.baseline_role)?.label??w.baseline_role)}${spot?.zone_id?` · ${esc(zoneLabel(spot.zone_id))}`:''}</p><div id="tw-wstatus" class="tw-wstatus"></div>`+kv([['Техника',w.assigned_vehicle_id??'—'],['В варианте B','та же роль и место']])+`<p class="tw-note">Реакции — часть демонстрационного эпизода: они объясняют причину и не меняют груз, время или результаты.</p><a href="skills-v3.html?actor=${encodeURIComponent(id)}">Навыки и допуски →</a>`;}
 show(panel,true);layoutPanels();renderWorkerStatus();
}
let selectedKind='HU',statusKey='';
function renderWorkerStatus(){
 const box=document.getElementById('tw-wstatus');if(!box||!twin||selectedKind!=='actor'||!selectedId)return;const spots=twin.workers(),id=selectedId;
 const rows=(['A','B'] as Variant[]).map(v=>[v,reactionsAt(v,t,spots).find(r=>r.actor_id===id)?.bubble??'calm',workerStatus(v,t,spots,id)] as const),key=JSON.stringify(rows);
 if(key===statusKey)return;statusKey=key;
 box.innerHTML=rows.map(([v,b,text])=>`<p data-b="${b}"><b>${v}</b><span>${esc(text)}</span></p>`).join('');
}
/** A tap (not a drag) in the viewport selects what is under it; the navigation tells taps and drags apart. */
function tapAt(x:number,y:number){if(phase!=='ready')return;const hit=twin?.pick(x,y);if(hit&&hit.kind!=='module')select(hit.id,hit.kind,hit.variant);}
let nav:ReturnType<typeof createNavigation>|undefined;
/* ---------- hover hint: what is under the mouse, before you click ---------- */
const hint=$('#tw-hint');let hintMap=new Map<string,SearchEntry>(),hintXY:[number,number]|null=null,hintTimer=0,hintLast=0,hintKey='';
function hideHint(){clearTimeout(hintTimer);hintTimer=0;hintXY=null;hintKey='';hint.hidden=true;host.classList.remove('is-hot');}
function probeHint(){
 hintTimer=0;hintLast=performance.now();if(!hintXY||!twin||phase!=='ready')return;const [x,y]=hintXY,hit=twin.pick(x,y),e=hit&&hit.kind!=='module'?hintMap.get(hit.id):undefined;
 host.classList.toggle('is-hot',!!e);if(!e||!hit){hint.hidden=true;hintKey='';return;}
 const key=hit.variant+hit.id;if(key!==hintKey){hintKey=key;hint.innerHTML=`${mode==='side'?`<em>${hit.variant}</em>`:''}<b>${esc(e.title)}</b><span>${e.kind==='actor'?'Работник':'Груз'} · ${esc(e.sub)}</span><small>клик — подробнее</small>`;}
 hint.hidden=false;const w=hint.offsetWidth,h=hint.offsetHeight,W=host.clientWidth,H=host.clientHeight;
 hint.style.translate=`${Math.min(x+16,W-w-8)}px ${y+20+h>H-90?y-h-14:y+20}px`;
}
host.addEventListener('pointermove',e=>{
 if(e.pointerType!=='mouse'||e.buttons||phase!=='ready'||e.target!==host.querySelector('canvas')){hideHint();return;}
 const r=host.getBoundingClientRect();hintXY=[e.clientX-r.left,e.clientY-r.top];
 // Picking is a raycast: at most ~12 per second, and only while the mouse actually moves.
 if(!hintTimer)hintTimer=window.setTimeout(probeHint,Math.max(0,80-(performance.now()-hintLast)));
});
host.addEventListener('pointerleave',hideHint);host.addEventListener('pointerdown',hideHint);

/* ---------- loading ---------- */
async function readLocal(path:string,signal:AbortSignal){const r=await fetch(import.meta.env.BASE_URL+path.replace(/^\//,''),{signal,cache:'no-store'});if(!r.ok)throw Error(r.status===404?'В локальном пакете не хватает данных склада V3.':'Данные склада временно недоступны. Повторите загрузку.');return r.text();}
const pose=(b:BoundCargo):Pose=>({position:[...b.position],yaw:b.yaw_rad,dims:[...b.cargo.dimensions_xyz_m]});
function clearSelectionState(){selectedId=null;selectedKind='HU';statusKey='';for(const button of $$<HTMLButtonElement>('.tw-moves button'))button.setAttribute('aria-pressed','false');show(sheets.find(s=>s.dataset.sheet==='sel')!,false);$('#tw-selection').replaceChildren();}
function disposeAll(){silenceAudio();nav?.dispose();nav=undefined;mini=undefined;miniKey='';cancelAnimationFrame(raf);raf=0;cancelAnimationFrame(flyRaf);flyRaf=0;flyTarget=null;clearTimeout(switchTimer);switchTimer=0;host.classList.remove('is-switching');twin?.dispose();twin=undefined;scene?.dispose();scene=undefined;bundle=undefined;moves=[];nowKey='';clearSelectionState();endPresent();}
async function load(){
 const token=++serial;controller?.abort();controller=new AbortController();const owned=controller;disposeAll();setPhase('loading','Открываем склад…');
 const timeout=setTimeout(()=>owned.abort(),45000);
 try{
  const keys=Object.keys(WAREHOUSE_BASE_FILES) as (keyof WarehouseTexts)[],values=await Promise.all(keys.map(k=>readLocal(WAREHOUSE_BASE_FILES[k],owned.signal)));
  const data=await adaptWarehouseV3(Object.fromEntries(keys.map((k,i)=>[k,values[i]])) as WarehouseTexts);if(token!==serial)return;
  const tw=createTwinRenderer(data,layer,()=>reduced.matches);twin=tw;tw.onBubble((id,v)=>select(id,'actor',v));
  // The A/B labels stand by their warehouse: a click takes you to that one, to look at it on its own.
  tw.onLabel(v=>{const o=tw.offsetOf(v);fly([OVERVIEW.target[0],OVERVIEW.target[1],OVERVIEW.target[2]+o[2]],mode==='side'?150:OVERVIEW.span);});
  const sc=await createWarehouseScene(host,data,{signal:owned.signal,progress:(done,total)=>{if(token===serial)setPhase('loading',`Собираем склад · ${Math.round(done/total*100)}%`);},select:()=>{},renderPass:(r,s,c)=>{tw.renderPass(r,s,c);drawMini();}});
  if(token!==serial){sc.dispose();return;}scene=sc;bundle=data;setPhase('loading','Проверяем перестройку…');
  // B: greedy, each move admitted by the real cargo rules; rejected candidates leave state untouched.
  const accepted:{c:ReturnType<typeof outboundCandidates>[number];slot_id:string;after_m:number;move_m:number}[]=[];
  for(const c of outboundCandidates(data))for(const cand of c.candidates){const r=sc.applyCargoBindings([{handling_unit_id:c.hu.handling_unit_id,destination:{kind:'storage_slot',slot_id:cand.slot_id}}]);if(r?.ok){accepted.push({c,...cand});break;}}
  tw.capture('B');const posesB=new Map(sc.getCargoBindings().map(b=>[b.handling_unit_id,pose(b)]));
  sc.resetCargoBindings();tw.capture('A');const posesA=new Map(sc.getCargoBindings().map(b=>[b.handling_unit_id,pose(b)]));
  moves=accepted.map(({c,slot_id,after_m,move_m})=>({id:c.hu.handling_unit_id,sku:c.hu.sku_id,archetype:c.hu.archetype_id,from_slot:c.from_slot,to_slot:slot_id,port_id:c.port_id,before_m:c.before_m,after_m,move_m,a:posesA.get(c.hu.handling_unit_id)!,b:posesB.get(c.hu.handling_unit_id)!}));
  tw.setMoves(moves,id=>select(id,'HU'));
  {const entries=indexBundle(data);searchIndex=buildIndex(entries);hintMap=new Map(entries.filter(e=>e.kind==='actor'||e.kind==='HU').map(e=>[e.id,e]));}
  nav=createNavigation({host,wheelAlso:[layer],scene:sc,ground:tw.ground,reduced:()=>reduced.matches,onTap:tapAt,onInput:()=>{cancelAnimationFrame(flyRaf);flyRaf=0;flyTarget=null;hideHint();},onMove:homeShown});
  type Z={zone_id:string;floor_bounds_xz_m:{min:[number,number];max:[number,number]}};
  // Aisles (CLEAR_*) are not places to go to; the plan lists the working zones only.
  mini=createMinimap($<HTMLCanvasElement>('#tw-mini'),$('#tw-mini-cap'),{size:[144,72],shiftZ:SIDE_SHIFT[2],
   zones:(data.layout.data.zones as Z[]).filter(z=>!z.zone_id.startsWith('CLEAR_')).map(z=>({id:z.zone_id,label:zoneLabel(z.zone_id),...z.floor_bounds_xz_m})),
   modules:data.layout.modules.map(m=>({min:[m.outer_bounds_world.min[0],m.outer_bounds_world.min[2]] as [number,number],max:[m.outer_bounds_world.max[0],m.outer_bounds_world.max[2]] as [number,number]}))},
   // A plan click means «take me there»: close enough to read the racks, at the current viewing angle.
   {zone:(z,v)=>{const o=tw.offsetOf(v),w=z.max[0]-z.min[0],d=z.max[1]-z.min[1];fly([(z.min[0]+z.max[0])/2,0,(z.min[1]+z.max[1])/2+o[2]],Math.min(64,Math.max(26,Math.max(w,d)*1.05+6)));},
    point:(p,v)=>{const o=tw.offsetOf(v);fly([p[0],0,p[2]+o[2]],30);},
    hover:(z,v)=>{if(z)tw.highlightZone(z,v);else restoreHl();}});
  zoneRects=new Map((data.layout.data.zones as Z[]).map(z=>[z.zone_id,z.floor_bounds_xz_m]));
  setPhase('ready','');
  setMode(mode,false);setSplit(split);renderMoves();tw.setReady();applyEffects();seek(t);sc.setView('overview' as WarehouseView);{const o=overview();sc.frameAt(o.target,o.span);}readViewUrl(sc);setPlaying(playing);
  // Start page link «Режим защиты» opens straight into the walk-through.
  if(new URL(location.href).searchParams.get('present')==='1')goStep(0);
  // Start page links open a scenario card straight away.
  {const id=new URL(location.href).searchParams.get('scenario');if(SCENARIOS.some(c=>c.id===id)){setSheet('source');openScenario(id);}}
 }catch(error){
  if(token!==serial)return;const aborted=owned.signal.aborted;owned.abort();disposeAll();
  setPhase('error',aborted&&!(error instanceof WarehouseAdapterError)?'Загрузка заняла слишком много времени. Попробуйте ещё раз.':error instanceof Error?error.message:'Не удалось открыть склад. Попробуйте ещё раз.');
 }finally{clearTimeout(timeout);}
}
retry.addEventListener('click',()=>void load());
host.addEventListener('webglcontextlost',e=>{e.preventDefault();if(phase!=='ready')return;disposeAll();setPhase('error','Графика браузера перезапустилась. Откройте склад заново.');},true);
function finishCameraMotion(){nav?.finish();cancelAnimationFrame(flyRaf);flyRaf=0;if(flyTarget&&scene)scene.frameAt(flyTarget.target,flyTarget.span);flyTarget=null;}
/** Rendering can observe the new matches value before its change event is delivered.
 * Reconcile at motion boundaries too; an explicit play under an unchanged preference stays explicit. */
function reconcileReducedMotion(){
 const next=reduced.matches;if(next===observedReduced)return false;observedReduced=next;if(!next)return false;
 setPlaying(false);finishCameraMotion();clearTimeout(switchTimer);switchTimer=0;host.classList.remove('is-switching');
 for(const animation of layer.getAnimations({subtree:true}))animation.cancel();
 twin?.setMode(mode);twin?.setTime(t);scene?.requestRender();return true;
}
reduced.addEventListener('change',reconcileReducedMotion);
document.addEventListener('visibilitychange',()=>{if(document.hidden){silenceAudio();setPlaying(false);finishCameraMotion();}else syncSound();});
window.addEventListener('pagehide',()=>{serial++;controller?.abort();silenceAudio(true);setPlaying(false);disposeAll();setPhase('disposed','Просмотр остановлен.');});
window.addEventListener('pageshow',e=>{if(e.persisted)void load();});
Object.assign(window,{__QOIMA_TWIN_V3__:{snapshot:()=>({phase,mode,t,split,playing,sheet,selected:selectedId,motion:{reduced:reduced.matches,clock_frame:raf!==0,camera_frame:flyRaf!==0,pending_mode_change:switchTimer!==0,camera:scene?.frameState()??null},moves:moves.map(m=>({id:m.id,from:m.from_slot,to:m.to_slot,before_m:m.before_m,after_m:m.after_m,move_m:m.move_m})),atmosphere:{A:sampleAtmosphere('A',t),B:sampleAtmosphere('B',t)},effects,sound:soundOn,audio:{active_voices:voices.size,state:audio?.state??null},reactions:twin?{A:reactionsAt('A',t,twin.workers()),B:reactionsAt('B',t,twin.workers())}:null,workers:twin?.workers()??[],perf:twin?.stats()??null,source_kind:'visual_fixture',engine_operation:false,scene:scene?.snapshot()??null}),seek,setMode,setPlaying,setSheet,select,present:goStep,endPresent,fly}});
syncPlay();setMode(mode,false);void load();
