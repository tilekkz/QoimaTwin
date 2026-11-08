import './twin.css';
import {adaptWarehouseV3,WarehouseAdapterError,WAREHOUSE_BASE_FILES,type WarehouseTexts} from '../warehouseAdapter';
import {createWarehouseScene,type WarehouseView} from '../warehouseScene';
import type {WarehouseBundle,XYZ} from '../warehouseTypes';
import type {BoundCargo} from '../warehouseCargo';
import {ATMO_ZONES,CHAPTERS,DEMO_DURATION_S,DEMO_EVENTS,PRESENTER_STEPS,outboundCandidates,sampleAtmosphere,stateSegments,type AtmoState,type Variant} from './twinScenario';
import {bubbleBudget,reactionsAt,recoveredZones,workerStatus,zoneHistory,type Effects} from './twinScenario';
import {createNavigation} from './twinNavigation';
import {createTwinRenderer,STATE_COLOR,STATE_RU,VARIANT_TITLE,type Mode,type Move,type Pose} from './twinRender';

const $=<T extends HTMLElement=HTMLElement>(sel:string)=>document.querySelector(sel) as T;
const $$=<T extends HTMLElement=HTMLElement>(sel:string)=>[...document.querySelectorAll<T>(sel)];
const app=$('#twin'),host=$('#tw-viewport'),layer=$('#tw-layer'),status=$('#tw-status'),retry=$<HTMLButtonElement>('#tw-retry'),blade=$('#tw-blade');
const play=$<HTMLButtonElement>('#tw-play'),clockOut=$('#tw-clock'),progress=$('#tw-progress'),river=$<HTMLCanvasElement>('#tw-river'),alertDot=$('#tw-alert');
const reduced=matchMedia('(prefers-reduced-motion: reduce)'),phone=matchMedia('(max-width: 720px)');
let observedReduced=reduced.matches;
const RIVER_ZONES=['PACKING_LIGHT_LINE','STANDARD_E','SMALL_E','STAGE_OUT_S_EXPRESS'];
const MODES:Mode[]=['side','swipe','overlay','diff'];
const MODE_LABEL:Record<Mode,string>={side:'Рядом',swipe:'Шторка',overlay:'Наложение',diff:'Отличия'};
const UI_ICON:Record<string,string>={
 side:'<svg viewBox="0 0 24 24"><rect x="3" y="5" width="8" height="14" rx="2.5"/><rect x="13" y="5" width="8" height="14" rx="2.5"/></svg>',
 swipe:'<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="3"/><path d="M12 3v18"/><circle cx="12" cy="12" r="2.2"/></svg>',
 overlay:'<svg viewBox="0 0 24 24"><rect x="3" y="7" width="13" height="12" rx="3"/><rect x="8" y="4" width="13" height="12" rx="3" stroke-dasharray="2.5 2.5"/></svg>',
 diff:'<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="3"/><path d="M12 8.5l1 2.5 2.5 1-2.5 1-1 2.5-1-2.5-2.5-1 2.5-1z"/></svg>',
 pulse:'<svg viewBox="0 0 24 24"><path d="M3 12h4l2.5-6 5 12 2.5-6h4"/></svg>',
 moves:'<svg viewBox="0 0 24 24"><path d="M7 7h11l-3-3M17 17H6l3 3"/></svg>',
 home:'<svg viewBox="0 0 24 24"><path d="M4 9V5a1 1 0 0 1 1-1h4M20 9V5a1 1 0 0 0-1-1h-4M4 15v4a1 1 0 0 0 1 1h4M20 15v4a1 1 0 0 1-1 1h-4"/></svg>',
};
const OVERVIEW={target:[72,1.5,36] as XYZ,span:184};
const fmt=(n:number,d=0)=>n.toLocaleString('ru-RU',{maximumFractionDigits:d,minimumFractionDigits:d});
const mmss=(s:number)=>`${String(Math.floor(s/60)).padStart(2,'0')}:${String(Math.floor(s%60)).padStart(2,'0')}`;
const zoneLabel=(id:string)=>ATMO_ZONES.find(z=>z.id===id)?.label??id;
const esc=(s:string)=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]!));
for(const el of $$('.tw-mi[data-icon]'))el.innerHTML=UI_ICON[el.dataset.icon!]??'';

type Phase='initial'|'loading'|'ready'|'error'|'disposed';
let phase:Phase='initial',serial=0,controller:AbortController|undefined,bundle:WarehouseBundle|undefined;
let scene:Awaited<ReturnType<typeof createWarehouseScene>>|undefined,twin:ReturnType<typeof createTwinRenderer>|undefined;
const urlMode=new URL(location.href).searchParams.get('mode') as Mode;
let mode:Mode=MODES.includes(urlMode)?urlMode:'side';
let t=0,playing=!reduced.matches&&!document.hidden,speed=4,last=0,raf=0,split=.5,moves:Move[]=[],nowKey='',selectedId:string|null=null;
/* ---------- effects & sound preferences ---------- */
const store={get:(k:string)=>{try{return localStorage.getItem(k);}catch{return null;}},set:(k:string,v:string)=>{try{localStorage.setItem(k,v);}catch{/* private mode: keep in memory only */}}};
const EFFECTS:Effects[]=['full','calm','off'];
let effects:Effects=EFFECTS.includes(store.get('qoima.twin.effects') as Effects)?store.get('qoima.twin.effects') as Effects:reduced.matches?'calm':'full';
function applyEffects(){app.dataset.effects=effects;for(const b of $$<HTMLButtonElement>('[data-effects]'))b.setAttribute('aria-pressed',String(b.dataset.effects===effects));twin?.setEffects(effects,bubbleBudget(effects,phone.matches));}
for(const b of $$<HTMLButtonElement>('[data-effects]'))b.addEventListener('click',()=>{effects=b.dataset.effects as Effects;store.set('qoima.twin.effects',effects);applyEffects();});
phone.addEventListener('change',applyEffects);
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
 const shown:Variant[]=mode==='overlay'||mode==='diff'?['B']:['A','B'],fired=new Set<Cue>();
 for(const v of shown)for(const e of DEMO_EVENTS[v])if(e.at_s>from&&e.at_s<=to)fired.add(e.cause.startsWith('Отказ')?'refuse':e.state==='nodata'?'danger':e.state);
 for(const k of fired)cue(k);
}
syncSound();
function setPhase(next:Phase,message:string){phase=next;app.dataset.phase=next;status.textContent=message;retry.hidden=next!=='error';syncSound();}

/* ---------- floating surfaces ---------- */
const show=(el:HTMLElement,open:boolean)=>{el.dataset.open=String(open);el.toggleAttribute('inert',!open);};
const sheets=$$('.tw-sheet'),openers=$$<HTMLButtonElement>('button[data-open]'),menu=$('#tw-menu'),menuBtn=$<HTMLButtonElement>('#tw-menu-btn'),modes=$('#tw-modes'),modeBtn=$<HTMLButtonElement>('#tw-mode-btn');
let sheet:string|null=null;
function setPop(which:'menu'|'modes'|null){show(menu,which==='menu');menuBtn.setAttribute('aria-expanded',String(which==='menu'));show(modes,which==='modes');modeBtn.setAttribute('aria-expanded',String(which==='modes'));}
function setSheet(name:string|null){
 sheet=name;for(const s of sheets)if(s.dataset.sheet!=='sel')show(s,s.dataset.sheet===name);
 for(const b of openers)b.setAttribute('aria-expanded',String(b.dataset.open===name));
 if(name&&phone.matches)select(null);setPop(null);if(name==='time')requestAnimationFrame(drawRiver);
}
for(const b of openers)b.addEventListener('click',()=>setSheet(sheet===b.dataset.open?null:b.dataset.open!));
for(const b of $$('[data-close]'))b.addEventListener('click',()=>{if(b.closest<HTMLElement>('.tw-sheet')?.dataset.sheet==='sel')select(null);else setSheet(null);});
menuBtn.addEventListener('click',()=>setPop(menu.dataset.open==='true'?null:'menu'));
modeBtn.addEventListener('click',()=>{const open=modes.dataset.open!=='true';if(open)setSheet(null);setPop(open?'modes':null);});
document.addEventListener('pointerdown',e=>{const tgt=e.target as HTMLElement;if(!tgt.closest('#tw-menu,#tw-menu-btn,#tw-modes,#tw-mode-btn'))setPop(null);});

/* ---------- camera fly-to ---------- */
const homeBtn=$<HTMLButtonElement>('#tw-home');let flyRaf=0,flyTarget:{target:XYZ;span:number}|null=null;
const homeShown=()=>{const s=scene?.frameState();if(s)homeBtn.dataset.shown=String(Math.abs(s.span-OVERVIEW.span)>1||s.target.some((v,i)=>Math.abs(v-OVERVIEW.target[i])>1));};
function fly(target:XYZ,span:number){
 if(!scene)return;nav?.stop();cancelAnimationFrame(flyRaf);flyTarget={target:[...target],span};const sc=scene,from=sc.frameState();
 // Gentle start and landing; longer trips take a little longer so the speed never spikes.
 const trip=Math.hypot(target[0]-from.target[0],target[2]-from.target[2])/Math.max(span,from.span)+Math.abs(Math.log(span/from.span)),start=performance.now(),dur=reduced.matches?0:Math.min(1500,850+trip*420);
 const ease=(x:number)=>x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2,ls=Math.log(from.span),le=Math.log(span);
 const step=(now:number)=>{flyRaf=0;if(reconcileReducedMotion()||scene!==sc||phase!=='ready')return;const k=dur?Math.min(1,(now-start)/dur):1,e=ease(k);sc.frameAt(from.target.map((v,i)=>v+(target[i]-v)*e) as XYZ,Math.exp(ls+(le-ls)*e));if(k<1)flyRaf=requestAnimationFrame(step);else flyTarget=null;};
 flyRaf=requestAnimationFrame(step);homeBtn.dataset.shown=String(Math.abs(span-OVERVIEW.span)>1||target.some((v,i)=>Math.abs(v-OVERVIEW.target[i])>1));
}
homeBtn.addEventListener('click',()=>fly(OVERVIEW.target,OVERVIEW.span));

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
 setPlaying(false);seek(s.t);setMode(s.mode);setSheet(s.sheet&&!phone.matches?s.sheet:null);fly(s.focus.target,s.focus.span);if(s.play)setPlaying(true);
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
 river.setAttribute('aria-valuenow',String(Math.round(t)));twin?.setTime(t);if(sheet==='time')drawRiver();renderNow();renderWorkerStatus();
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
function setMode(next:Mode,animate=true){
 const changed=next!==mode;mode=next;app.dataset.mode=next;
 clearTimeout(switchTimer);switchTimer=0;host.classList.remove('is-switching');
 for(const b of $$<HTMLButtonElement>('.tw-modes button'))b.setAttribute('aria-checked',String(b.dataset.mode===next));
 $('#tw-mode-icon').innerHTML=UI_ICON[next];$('#tw-mode-label').textContent=MODE_LABEL[next];blade.hidden=next!=='swipe';
 const url=new URL(location.href);url.searchParams.set('mode',next);history.replaceState(null,'',url);
 if(changed&&animate&&!reduced.matches&&phase==='ready'){host.classList.add('is-switching');switchTimer=window.setTimeout(()=>{switchTimer=0;twin?.setMode(mode);host.classList.remove('is-switching');},120);}
 else twin?.setMode(next);
}
for(const b of $$<HTMLButtonElement>('.tw-modes button'))b.addEventListener('click',()=>{setMode(b.dataset.mode as Mode);setPop(null);});
const setSplit=(f:number)=>{split=Math.min(.92,Math.max(.08,f));blade.style.left=split*100+'%';blade.setAttribute('aria-valuenow',String(Math.round(split*100)));twin?.setSplit(split);};
blade.addEventListener('pointerdown',e=>{blade.setPointerCapture(e.pointerId);e.preventDefault();});
blade.addEventListener('pointermove',e=>{if(!blade.hasPointerCapture(e.pointerId))return;const r=host.getBoundingClientRect();setSplit((e.clientX-r.left)/r.width);});
blade.addEventListener('keydown',e=>{const d=e.key==='ArrowLeft'?-.04:e.key==='ArrowRight'?.04:0;if(d){e.preventDefault();setSplit(split+d);}});
document.addEventListener('keydown',e=>{
 if(e.key==='Escape'){setPop(null);if(stepIndex>=0)endPresent();else if(sheet)setSheet(null);else select(null);return;}
 if(phase!=='ready'||e.altKey||e.ctrlKey||e.metaKey)return;const target=e.target as HTMLElement;if(target.closest('input,select,textarea,[role="slider"]'))return;
 // Presentation clickers send PageDown/PageUp; arrows work too while the walk-through is open.
 if(stepIndex>=0&&['ArrowRight','PageDown','ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();if(e.key==='ArrowRight'||e.key==='PageDown')nextPresent();else goStep(stepIndex-1);return;}
 if(e.key==='p'||e.key==='з'){if(stepIndex>=0)endPresent();else goStep(0);return;}
 if(/^[1-4]$/.test(e.key)){setMode(MODES[Number(e.key)-1]);return;}
 if(e.key==='+'||e.key==='='||e.key==='-'||e.key==='_'){e.preventDefault();nav?.zoomBy(e.key==='-'||e.key==='_'?1.35:1/1.35);return;}
 if(e.key==='0'){fly(OVERVIEW.target,OVERVIEW.span);return;}
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
$('#tw-now').addEventListener('click',e=>{
 const b=(e.target as HTMLElement).closest<HTMLButtonElement>('.tw-issue,.tw-src');if(!b)return;const k=b.dataset.k!,id=k.slice(2);
 // A wave link always opens its source; an issue row toggles.
 openIssue=b.classList.contains('tw-src')||openIssue!==k?k:null;nowKey='';
 // Expanding a row should not replay the entry animation of every row.
 const box=$('#tw-now');box.classList.add('tw-quiet');renderNow();requestAnimationFrame(()=>box.classList.remove('tw-quiet'));
 const f=openIssue&&twin?.zoneFocus(id);if(f)fly(f.target,f.span);
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
function select(id:string|null,kind='HU'){
 selectedId=id;selectedKind=kind;statusKey='';const moved=moves.find(m=>m.id===id);twin?.setSelected(moved?id:null);twin?.setSelectedActor(kind==='actor'?id:null);
 for(const b of $$<HTMLButtonElement>('.tw-moves button'))b.setAttribute('aria-pressed',String(b.dataset.id===id));
 const panel=sheets.find(s=>s.dataset.sheet==='sel')!;if(!id||!bundle){show(panel,false);return;}
 if(phone.matches&&sheet)setSheet(null);
 const box=$('#tw-selection'),kv=(rows:[string,string][])=>`<dl class="tw-kv">${rows.map(([k,v])=>`<dt>${k}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`;
 if(kind==='HU'){const hu=bundle.fixture.inputs.initial_stock.find(h=>h.handling_unit_id===id);if(!hu)return;
  $('#sh-sel').textContent='Груз';
  const route=moved?`<div class="tw-route"><div><small>Было · A</small><span>${esc(hu.location.slot_id.replace('v3:slot:',''))}</span></div>${ARROW}<div><small>Стало · B</small><span>${esc(moved.to_slot.replace('v3:slot:',''))}</span></div></div>`:`<div class="tw-route"><div style="grid-column:1/-1"><small>Адрес</small><span>${esc(hu.location.slot_id.replace('v3:slot:',''))} · не переносится</span></div></div>`;
  if(moved){const a=moved.a.position,b=moved.b.position,d=Math.hypot(a[0]-b[0],a[2]-b[2]);fly([(a[0]+b[0])/2,0,(a[2]+b[2])/2],Math.min(184,Math.max(18,d*1.5+10)));}
  else{const pos=scene?.getCargoBindings().find(b=>b.handling_unit_id===id)?.position;if(pos)fly([pos[0],0,pos[2]],16);}
  box.innerHTML=`<h3>${esc(hu.sku_id)}</h3><p class="tw-sub">${esc(hu.archetype_id)} · ${fmt(hu.gross_mass_kg,2)} кг</p>${route}`+kv([['Количество',fmt(hu.quantity_units)+' ед.'],['Габариты',hu.dimensions_xyz_m.map(x=>fmt(x,2)).join(' × ')+' м'],...(moved?[['Ворота',moved.port_id],['До ворот',`${fmt(moved.before_m)} → ${fmt(moved.after_m)} м`],['Перенос',`${fmt(moved.move_m)} м по прямой`]] as [string,string][]:[])]);}
 else{const w=bundle.registry.workers.find(w=>w.actor_id===id);if(!w)return;$('#sh-sel').textContent='Работник';
  const spot=twin?.workers().find(s=>s.actor_id===id),head=twin?.actorPosition(id);if(head)fly([head[0],0,head[2]],20);
  box.innerHTML=`<h3>${esc(w.actor_id)}</h3><p class="tw-sub">${esc(bundle.registry.roles.find(r=>r.role===w.baseline_role)?.label??w.baseline_role)}${spot?.zone_id?` · ${esc(zoneLabel(spot.zone_id))}`:''}</p><div id="tw-wstatus" class="tw-wstatus"></div>`+kv([['Техника',w.assigned_vehicle_id??'—'],['В варианте B','та же роль и место']])+`<p class="tw-note">Реакции — часть демонстрационного эпизода: они объясняют причину и не меняют груз, время или результаты.</p><a href="skills-v3.html?actor=${encodeURIComponent(id)}">Навыки и допуски →</a>`;}
 show(panel,true);renderWorkerStatus();
}
let selectedKind='HU',statusKey='';
function renderWorkerStatus(){
 const box=document.getElementById('tw-wstatus');if(!box||!twin||selectedKind!=='actor'||!selectedId)return;const spots=twin.workers(),id=selectedId;
 const rows=(['A','B'] as Variant[]).map(v=>[v,reactionsAt(v,t,spots).find(r=>r.actor_id===id)?.bubble??'calm',workerStatus(v,t,spots,id)] as const),key=JSON.stringify(rows);
 if(key===statusKey)return;statusKey=key;
 box.innerHTML=rows.map(([v,b,text])=>`<p data-b="${b}"><b>${v}</b><span>${esc(text)}</span></p>`).join('');
}
/** A tap (not a drag) in the viewport selects what is under it; the navigation tells taps and drags apart. */
function tapAt(x:number,y:number){if(phase!=='ready')return;const hit=twin?.pick(x,y);if(hit&&hit.kind!=='module')select(hit.id,hit.kind);}
let nav:ReturnType<typeof createNavigation>|undefined;

/* ---------- loading ---------- */
async function readLocal(path:string,signal:AbortSignal){const r=await fetch(import.meta.env.BASE_URL+path.replace(/^\//,''),{signal,cache:'no-store'});if(!r.ok)throw Error(r.status===404?'В локальном пакете не хватает данных склада V3.':'Данные склада временно недоступны. Повторите загрузку.');return r.text();}
const pose=(b:BoundCargo):Pose=>({position:[...b.position],yaw:b.yaw_rad,dims:[...b.cargo.dimensions_xyz_m]});
function clearSelectionState(){selectedId=null;selectedKind='HU';statusKey='';for(const button of $$<HTMLButtonElement>('.tw-moves button'))button.setAttribute('aria-pressed','false');show(sheets.find(s=>s.dataset.sheet==='sel')!,false);$('#tw-selection').replaceChildren();}
function disposeAll(){silenceAudio();nav?.dispose();nav=undefined;cancelAnimationFrame(raf);raf=0;cancelAnimationFrame(flyRaf);flyRaf=0;flyTarget=null;clearTimeout(switchTimer);switchTimer=0;host.classList.remove('is-switching');twin?.dispose();twin=undefined;scene?.dispose();scene=undefined;bundle=undefined;moves=[];nowKey='';clearSelectionState();endPresent();}
async function load(){
 const token=++serial;controller?.abort();controller=new AbortController();const owned=controller;disposeAll();setPhase('loading','Открываем склад…');
 const timeout=setTimeout(()=>owned.abort(),45000);
 try{
  const keys=Object.keys(WAREHOUSE_BASE_FILES) as (keyof WarehouseTexts)[],values=await Promise.all(keys.map(k=>readLocal(WAREHOUSE_BASE_FILES[k],owned.signal)));
  const data=await adaptWarehouseV3(Object.fromEntries(keys.map((k,i)=>[k,values[i]])) as WarehouseTexts);if(token!==serial)return;
  const tw=createTwinRenderer(data,layer,()=>reduced.matches);twin=tw;tw.onBubble(id=>select(id,'actor'));
  const sc=await createWarehouseScene(host,data,{signal:owned.signal,progress:(done,total)=>{if(token===serial)setPhase('loading',`Собираем склад · ${Math.round(done/total*100)}%`);},select:()=>{},renderPass:tw.renderPass});
  if(token!==serial){sc.dispose();return;}scene=sc;bundle=data;setPhase('loading','Проверяем перестройку…');
  // B: greedy, each move admitted by the real cargo rules; rejected candidates leave state untouched.
  const accepted:{c:ReturnType<typeof outboundCandidates>[number];slot_id:string;after_m:number;move_m:number}[]=[];
  for(const c of outboundCandidates(data))for(const cand of c.candidates){const r=sc.applyCargoBindings([{handling_unit_id:c.hu.handling_unit_id,destination:{kind:'storage_slot',slot_id:cand.slot_id}}]);if(r?.ok){accepted.push({c,...cand});break;}}
  tw.capture('B');const posesB=new Map(sc.getCargoBindings().map(b=>[b.handling_unit_id,pose(b)]));
  sc.resetCargoBindings();tw.capture('A');const posesA=new Map(sc.getCargoBindings().map(b=>[b.handling_unit_id,pose(b)]));
  moves=accepted.map(({c,slot_id,after_m,move_m})=>({id:c.hu.handling_unit_id,sku:c.hu.sku_id,archetype:c.hu.archetype_id,from_slot:c.from_slot,to_slot:slot_id,port_id:c.port_id,before_m:c.before_m,after_m,move_m,a:posesA.get(c.hu.handling_unit_id)!,b:posesB.get(c.hu.handling_unit_id)!}));
  tw.setMoves(moves,id=>select(id,'HU'));
  nav=createNavigation({host,wheelAlso:[layer],scene:sc,ground:tw.ground,reduced:()=>reduced.matches,onTap:tapAt,onInput:()=>{cancelAnimationFrame(flyRaf);flyRaf=0;flyTarget=null;},onMove:homeShown});
  setPhase('ready','');
  setMode(mode,false);setSplit(split);renderMoves();tw.setReady();applyEffects();seek(t);sc.setView('overview' as WarehouseView);setPlaying(playing);
  // Start page link «Режим защиты» opens straight into the walk-through.
  if(new URL(location.href).searchParams.get('present')==='1')goStep(0);
 }catch(error){
  if(token!==serial)return;const aborted=owned.signal.aborted;owned.abort();disposeAll();
  setPhase('error',aborted&&!(error instanceof WarehouseAdapterError)?'Загрузка заняла слишком много времени. Попробуйте ещё раз.':error instanceof Error?error.message:'Не удалось открыть склад. Попробуйте ещё раз.');
 }finally{clearTimeout(timeout);}
}
retry.addEventListener('click',()=>void load());
host.addEventListener('webglcontextlost',e=>{e.preventDefault();if(phase!=='ready')return;disposeAll();setPhase('error','Графика браузера перезапустилась. Откройте склад заново.');},true);
function finishCameraMotion(){nav?.stop();cancelAnimationFrame(flyRaf);flyRaf=0;if(flyTarget&&scene)scene.frameAt(flyTarget.target,flyTarget.span);flyTarget=null;}
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
