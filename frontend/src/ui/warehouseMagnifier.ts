/** A live screen-space lens. Capture once after the complete composed WebGL frame. */
const STYLE_ID='warehouse-magnifier-style';
const SIZE=224,MIN_ZOOM=1.5,MAX_ZOOM=6;
const STYLES=`
.warehouse-magnifier-toggle{position:absolute;right:16px;top:16px;z-index:30;display:inline-flex;align-items:center;gap:8px;min-height:42px;padding:10px 14px;border:1px solid #ffffffd9;border-radius:24px;background:#f7faf7ed;color:#183e40;box-shadow:0 3px 16px #173b4020;font:600 12px/1.2 system-ui,sans-serif;cursor:pointer;backdrop-filter:blur(12px)}
.warehouse-magnifier-toggle:hover{background:#fff}.warehouse-magnifier-toggle[aria-pressed=true]{background:#137f76;color:white;border-color:#52bbae}.warehouse-magnifier-toggle:focus-visible{outline:3px solid #e5a431;outline-offset:3px}.warehouse-magnifier-toggle svg{width:18px;height:18px;flex:none}.warehouse-magnifier-toggle span{white-space:nowrap}
#tw-viewport>.warehouse-magnifier-toggle{top:82px;right:20px}
.warehouse-magnifier-source-active{cursor:crosshair!important}
.warehouse-magnifier-lens{position:fixed;z-index:1000;width:${SIZE}px;height:${SIZE}px;pointer-events:none!important;isolation:isolate;border:3px solid #fffffff5;border-radius:50%;background:#dce1db;box-shadow:0 0 0 1px #0c766f99,0 12px 38px #123e4445,0 2px 5px #173e4029;overflow:hidden;contain:layout paint}
.warehouse-magnifier-lens[hidden]{display:none!important}.warehouse-magnifier-lens canvas{display:block;width:100%;height:100%;border-radius:50%}.warehouse-magnifier-lens:after{content:'';position:absolute;inset:50% auto auto 50%;width:12px;height:12px;transform:translate(-50%,-50%);background:linear-gradient(#fff 0 0) center/1px 12px no-repeat,linear-gradient(#fff 0 0) center/12px 1px no-repeat;filter:drop-shadow(0 0 1px #164348)}
.warehouse-magnifier-caption{position:absolute;left:50%;bottom:13px;transform:translateX(-50%);padding:5px 10px;border:1px solid #ffffff70;border-radius:14px;background:#174a45d9;color:white;font:600 11px/1.2 system-ui,sans-serif;white-space:nowrap}
.warehouse-magnifier-help{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
`;

export function createWarehouseMagnifier(host:HTMLElement,source:HTMLCanvasElement,requestRender:()=>void){
 const doc=host.ownerDocument,win=doc.defaultView!;
 if(!doc.getElementById(STYLE_ID)){const style=doc.createElement('style');style.id=STYLE_ID;style.textContent=STYLES;doc.head.append(style);}
 const lifetime=new AbortController(),events={signal:lifetime.signal};
 const button=doc.createElement('button');button.type='button';button.className='warehouse-magnifier-toggle';button.setAttribute('aria-label','Лупа');button.setAttribute('aria-pressed','false');button.title='Лупа · колесо меняет увеличение · Esc выключает';
 button.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5M10.5 7v7M7 10.5h7"/></svg><span>Лупа</span>';
 const label=button.querySelector('span')!;
 const help=doc.createElement('span');help.className='warehouse-magnifier-help';help.id='warehouse-magnifier-help-'+Math.random().toString(36).slice(2);help.textContent='Включите лупу и наведите на склад. Колесо или плюс и минус меняют увеличение. Стрелки перемещают лупу, Escape выключает.';button.setAttribute('aria-describedby',help.id);
 const lens=doc.createElement('div');lens.className='warehouse-magnifier-lens';lens.hidden=true;lens.setAttribute('aria-hidden','true');
 const caption=doc.createElement('span');caption.className='warehouse-magnifier-caption';
 host.append(button,help);doc.body.append(lens);
 const oldTabIndex=source.getAttribute('tabindex');if(oldTabIndex===null)source.tabIndex=0;
 let enabled=false,disposed=false,lost=false,zoom=3,point:{x:number;y:number}|null=null,raf=0,draws=0,captures=0,pendingCapture=false;
 let cache:HTMLCanvasElement|undefined,cacheContext:CanvasRenderingContext2D|null=null,lensCanvas:HTMLCanvasElement|undefined,lensContext:CanvasRenderingContext2D|null=null,valid=false;
 const shownZoom=()=>zoom.toLocaleString('ru-RU',{maximumFractionDigits:1})+'×';
 function sync(){button.setAttribute('aria-pressed',String(enabled));label.textContent=enabled?'Лупа '+shownZoom():'Лупа';caption.textContent=shownZoom()+' · колесо / Esc';lens.dataset.zoom=String(zoom);source.classList.toggle('warehouse-magnifier-source-active',enabled);}
 function hide(){lens.hidden=true;if(raf)win.cancelAnimationFrame(raf);raf=0;}
 function schedule(){if(!raf&&!disposed&&enabled&&point&&!doc.hidden)raf=win.requestAnimationFrame(paint);}
 function inside(x:number,y:number){const r=source.getBoundingClientRect();return x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom&&r.width>0&&r.height>0;}
 function paint(){
  raf=0;if(disposed||!enabled||lost||doc.hidden||!point||!valid||!cache||!lensContext||!lensCanvas){hide();return;}
  const rect=source.getBoundingClientRect();if(!inside(point.x,point.y)){hide();return;}
  const scale=cache.width/rect.width,scaleY=cache.height/rect.height,sw=SIZE/zoom*scale,sh=SIZE/zoom*scaleY;
  const sx=(point.x-rect.left)*scale-sw/2,sy=(point.y-rect.top)*scaleY-sh/2;
  const width=lensCanvas.width,height=lensCanvas.height;
  lensContext.fillStyle='#dce1db';lensContext.fillRect(0,0,width,height);lensContext.imageSmoothingEnabled=true;lensContext.imageSmoothingQuality='high';
  // Canvas clips a crop at the source boundary without moving the inspected point.
  lensContext.drawImage(cache,sx,sy,sw,sh,0,0,width,height);
  const left=point.x+SIZE+32<win.innerWidth?point.x+26:point.x-SIZE-26;
  lens.style.left=Math.max(8,Math.min(win.innerWidth-SIZE-8,left))+'px';lens.style.top=Math.max(8,Math.min(win.innerHeight-SIZE-8,point.y-SIZE/2))+'px';
  lens.hidden=false;lens.dataset.draws=String(++draws);lens.dataset.captures=String(captures);
 }
 function ensureCanvas(){
  if(lensCanvas)return true;
  cache=doc.createElement('canvas');cacheContext=cache.getContext('2d');lensCanvas=doc.createElement('canvas');lensContext=lensCanvas.getContext('2d');
  if(!cacheContext||!lensContext){cache=undefined;lensCanvas=undefined;button.disabled=true;button.title='Лупа недоступна: браузер не создал графический слой.';return false;}
  const ratio=Math.min(win.devicePixelRatio||1,2);lensCanvas.width=Math.round(SIZE*ratio);lensCanvas.height=Math.round(SIZE*ratio);lens.append(lensCanvas,caption);return true;
 }
 function setEnabled(value:boolean,keyboard=false){
  if(disposed||lost)return;
  enabled=value&&ensureCanvas();valid=false;
  if(!enabled){point=null;hide();if(cache){cache.width=cache.height=0;}}
  else if(keyboard){const r=source.getBoundingClientRect();point={x:r.left+r.width/2,y:r.top+r.height/2};}
  sync();if(enabled)requestRender();
 }
 function changeZoom(delta:number){zoom=Math.max(MIN_ZOOM,Math.min(MAX_ZOOM,Math.round((zoom+delta)*2)/2));sync();schedule();}
 function capture(){
  pendingCapture=false;
  if(disposed||!enabled||lost||doc.hidden||!point||!cache||!cacheContext||!source.width||!source.height)return;
  if(cache.width!==source.width||cache.height!==source.height){cache.width=source.width;cache.height=source.height;}
  cacheContext.drawImage(source,0,0);valid=true;captures++;if(raf)win.cancelAnimationFrame(raf);paint();
 }
 // Some composed views also finish rendering outside their parent scene's frame callback.
 // A microtask observes the completed synchronous multipass, before the drawing buffer is presented.
 function queueCapture(){if(pendingCapture||disposed||!enabled||!point||doc.hidden)return;pendingCapture=true;win.queueMicrotask(()=>{if(pendingCapture)capture();});}
 button.addEventListener('click',e=>{e.stopPropagation();setEnabled(!enabled,e.detail===0);},events);
 for(const type of ['pointerdown','pointerup'])button.addEventListener(type,e=>e.stopPropagation(),events);
 // The Twin camera captures input at the host. Keep this tool's native button out of that gesture.
 for(const type of ['pointerdown','pointerup'])host.addEventListener(type,e=>{if(e.target instanceof win.Node&&button.contains(e.target))e.stopImmediatePropagation();},{...events,capture:true});
 source.addEventListener('pointermove',e=>{if(!enabled||e.pointerType==='touch')return;const entering=!point;point={x:e.clientX,y:e.clientY};if(entering||!valid)requestRender();schedule();},events);
 source.addEventListener('pointerleave',()=>{point=null;valid=false;hide();},events);
 host.addEventListener('wheel',e=>{if(!enabled||e.target!==source)return;e.preventDefault();e.stopImmediatePropagation();if(!e.deltaY)return;point={x:e.clientX,y:e.clientY};changeZoom(e.deltaY<0?.5:-.5);if(!valid)requestRender();},{...events,capture:true,passive:false});
 const editing=(target:EventTarget|null)=>target instanceof win.HTMLElement&&(target.isContentEditable||!!target.closest('input,textarea,select,[role=slider]'));
 doc.addEventListener('keydown',e=>{
  if(!enabled||editing(e.target))return;
  if(e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();setEnabled(false);button.focus({preventScroll:true});return;}
  if(e.key==='+'||e.key==='='||e.key==='-'){e.preventDefault();e.stopImmediatePropagation();changeZoom(e.key==='-'?-.5:.5);return;}
  if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;
  e.preventDefault();e.stopImmediatePropagation();const r=source.getBoundingClientRect(),step=e.shiftKey?36:14;
  point??={x:r.left+r.width/2,y:r.top+r.height/2};point.x=Math.max(r.left+1,Math.min(r.right-1,point.x+(e.key==='ArrowRight'?step:e.key==='ArrowLeft'?-step:0)));point.y=Math.max(r.top+1,Math.min(r.bottom-1,point.y+(e.key==='ArrowDown'?step:e.key==='ArrowUp'?-step:0)));if(!valid)requestRender();schedule();
 },{...events,capture:true});
 const invalidate=()=>{valid=false;hide();if(enabled&&point)requestRender();};
 win.addEventListener('resize',invalidate,events);win.addEventListener('scroll',()=>{point=null;valid=false;hide();},{...events,capture:true});
 doc.addEventListener('visibilitychange',()=>{if(doc.hidden){point=null;valid=false;hide();}},events);
 source.addEventListener('webglcontextlost',()=>{lost=true;enabled=false;point=null;valid=false;hide();sync();button.disabled=true;},events);
 source.addEventListener('webglcontextrestored',()=>{lost=false;button.disabled=false;valid=false;sync();},events);
 sync();
 function dispose(){if(disposed)return;disposed=true;enabled=false;point=null;pendingCapture=false;lifetime.abort();hide();source.classList.remove('warehouse-magnifier-source-active');if(oldTabIndex===null)source.removeAttribute('tabindex');else source.setAttribute('tabindex',oldTabIndex);button.remove();help.remove();lens.remove();if(cache)cache.width=cache.height=0;if(lensCanvas)lensCanvas.width=lensCanvas.height=0;cache=undefined;lensCanvas=undefined;cacheContext=null;lensContext=null;}
 return {capture,queueCapture,dispose,snapshot:()=>({enabled,visible:!lens.hidden&&!disposed,zoom,draws,captures,disposed,pending_frame:raf!==0})};
}
