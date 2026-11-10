import * as THREE from 'three';

export type WarehouseLensCamera=THREE.OrthographicCamera|THREE.PerspectiveCamera;
export type WarehouseLensView={camera:WarehouseLensCamera;viewport:{x:number;y:number;w:number;h:number};caption:string;cacheKey?:string;draw:(camera:WarehouseLensCamera,stage:'all'|'static'|'dynamic')=>void};
/** An off-axis camera crop, rendered at native lens resolution. Never samples the main canvas. */
const STYLE_ID='warehouse-magnifier-style';
const SIZE=224,MIN_ZOOM=2,MAX_ZOOM=10;
const STYLES=`
.warehouse-magnifier-toggle{position:absolute;right:16px;top:16px;z-index:30;display:inline-flex;align-items:center;gap:8px;min-height:42px;padding:10px 14px;border:1px solid #ffffffd9;border-radius:24px;background:#f7faf7ed;color:#183e40;box-shadow:0 3px 16px #173b4020;font:600 12px/1.2 system-ui,sans-serif;cursor:pointer;backdrop-filter:blur(12px)}
.warehouse-magnifier-toggle:hover{background:#fff}.warehouse-magnifier-toggle[aria-pressed=true]{background:#137f76;color:white;border-color:#52bbae}.warehouse-magnifier-toggle:focus-visible{outline:3px solid #e5a431;outline-offset:3px}.warehouse-magnifier-toggle svg{width:18px;height:18px;flex:none}.warehouse-magnifier-toggle span{white-space:nowrap}
#tw-viewport>.warehouse-magnifier-toggle{top:82px;right:20px}
.warehouse-magnifier-source-active{cursor:crosshair!important}
.warehouse-magnifier-lens{position:fixed;z-index:1000;box-sizing:border-box;width:${SIZE}px;height:${SIZE}px;pointer-events:none!important;isolation:isolate;border:3px solid #fffffff5;border-radius:50%;background:transparent;box-shadow:0 0 0 1px #0c766f99,0 12px 38px #123e4445,0 2px 5px #173e4029;overflow:hidden;contain:layout paint}
.warehouse-magnifier-lens[hidden]{display:none!important}.warehouse-magnifier-lens:after{content:'';position:absolute;inset:50% auto auto 50%;width:12px;height:12px;transform:translate(-50%,-50%);background:linear-gradient(#fff 0 0) center/1px 12px no-repeat,linear-gradient(#fff 0 0) center/12px 1px no-repeat;filter:drop-shadow(0 0 1px #164348)}
.warehouse-magnifier-caption{position:absolute;left:50%;bottom:13px;transform:translateX(-50%);padding:5px 10px;border:1px solid #ffffff70;border-radius:14px;background:#174a45d9;color:white;font:600 11px/1.2 system-ui,sans-serif;white-space:nowrap}
.warehouse-magnifier-help{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
`;

export function createWarehouseMagnifier(host:HTMLElement,renderer:THREE.WebGLRenderer,requestRender:()=>void,viewAt:(x:number,y:number)=>WarehouseLensView|null){
 const source=renderer.domElement,doc=host.ownerDocument,win=doc.defaultView!;
 if(!doc.getElementById(STYLE_ID)){const style=doc.createElement('style');style.id=STYLE_ID;style.textContent=STYLES;doc.head.append(style);}
 const lifetime=new AbortController(),events={signal:lifetime.signal};
 const button=doc.createElement('button');button.type='button';button.className='warehouse-magnifier-toggle';button.setAttribute('aria-label','Лупа');button.setAttribute('aria-pressed','false');button.title='Лупа · колесо меняет увеличение · Esc выключает';
 button.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5M10.5 7v7M7 10.5h7"/></svg><span>Лупа</span>';
 const label=button.querySelector('span')!;
 const help=doc.createElement('span');help.className='warehouse-magnifier-help';help.id='warehouse-magnifier-help-'+Math.random().toString(36).slice(2);help.textContent='Включите лупу и наведите на склад. Увеличение от 2 до 10. Колесо или плюс и минус меняют увеличение. Стрелки перемещают лупу, Escape выключает.';button.setAttribute('aria-describedby',help.id);
 const lens=doc.createElement('div');lens.className='warehouse-magnifier-lens';lens.hidden=true;lens.setAttribute('aria-hidden','true');lens.dataset.kind='optical-3d';
 const caption=doc.createElement('span');caption.className='warehouse-magnifier-caption';lens.append(caption);
 host.append(button,help);doc.body.append(lens);
 const oldTabIndex=source.getAttribute('tabindex');if(oldTabIndex===null)source.tabIndex=0;
 let enabled=false,disposed=false,lost=false,zoom=4,point:{x:number;y:number}|null=null,draws=0;
 let staticTarget:THREE.WebGLRenderTarget|undefined,staticKey='',staticMaterial:THREE.ShaderMaterial|undefined,staticScene:THREE.Scene|undefined;
 let lensCamera:WarehouseLensCamera|undefined,projectionKey='';
 let target:THREE.WebGLRenderTarget|undefined,material:THREE.ShaderMaterial|undefined,geometry:THREE.PlaneGeometry|undefined,composite:THREE.Scene|undefined;
 const shownZoom=()=>zoom.toLocaleString('ru-RU',{maximumFractionDigits:1})+'×';
 function sync(){button.setAttribute('aria-pressed',String(enabled));label.textContent=enabled?'Лупа '+shownZoom():'Лупа';lens.dataset.zoom=String(zoom);source.classList.toggle('warehouse-magnifier-source-active',enabled);}
 function hide(){projectionKey='';lens.hidden=true;delete host.parentElement?.dataset.lensVisible;}
 function inside(x:number,y:number){const r=source.getBoundingClientRect();return x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom&&r.width>0&&r.height>0;}
 function ensureStaticTarget(){
  if(!staticTarget){
   staticTarget=new THREE.WebGLRenderTarget(target!.width,target!.height,{samples:target!.samples,type:THREE.HalfFloatType});staticTarget.depthTexture=new THREE.DepthTexture(target!.width,target!.height);
   staticMaterial=new THREE.ShaderMaterial({uniforms:{image:{value:staticTarget.texture},depth:{value:staticTarget.depthTexture}},depthTest:true,depthWrite:true,depthFunc:THREE.AlwaysDepth,
    vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}',
    fragmentShader:'uniform sampler2D image;uniform sampler2D depth;varying vec2 vUv;void main(){gl_FragColor=texture2D(image,vUv);gl_FragDepth=texture2D(depth,vUv).r;}'});
   const quad=new THREE.Mesh(geometry!,staticMaterial);quad.frustumCulled=false;staticScene=new THREE.Scene();staticScene.add(quad);
  }else if(staticTarget.width!==target!.width){staticTarget.setSize(target!.width,target!.height);staticKey='';}
 }
 function ensureTarget(){
  const pixels=Math.round(SIZE*Math.min(win.devicePixelRatio||1,2));
  if(!target){
   target=new THREE.WebGLRenderTarget(pixels,pixels,{samples:Math.min(4,renderer.capabilities.maxSamples),type:THREE.HalfFloatType});
   material=new THREE.ShaderMaterial({uniforms:{image:{value:target.texture},edge:{value:1/pixels}},depthTest:false,depthWrite:false,transparent:true,
    vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}',
    fragmentShader:'uniform sampler2D image;uniform float edge;varying vec2 vUv;void main(){float r=length(vUv-.5);if(r>.5)discard;vec4 c=texture2D(image,vUv);float ring=smoothstep(.481,.491,r);c.rgb=mix(c.rgb,vec3(.93,.99,.97),ring);gl_FragColor=vec4(c.rgb,1.-smoothstep(.5-edge,.5,r));\n#include <tonemapping_fragment>\n#include <colorspace_fragment>\n}'});
   geometry=new THREE.PlaneGeometry(2,2);const quad=new THREE.Mesh(geometry,material);quad.frustumCulled=false;composite=new THREE.Scene();composite.add(quad);
  }else if(target.width!==pixels)target.setSize(pixels,pixels);
  material!.uniforms.edge.value=1/pixels;
 }
 // Called by the owner's completed frame, never by a second animation loop.
 /** With a still pointer the live layer inside the lens refreshes at ~30 Hz; between refreshes the last image is only
  *  composited again. Any pointer, zoom or view change renders at once, so following the cursor stays per-frame. */
 const LIVE_REFRESH_MS=33;let liveAt=-1e9,liveTarget:unknown=null;
 function render(){
  if(disposed||!enabled||lost||doc.hidden||!point)return;
  if(!inside(point.x,point.y)){hide();return;}
  const rect=source.getBoundingClientRect(),x=point.x-rect.left,y=point.y-rect.top,view=viewAt(x,y);
  if(!view){hide();return;}
  ensureTarget();
  const vp=view.viewport,patch=SIZE/zoom,key=[x,y,zoom,vp.x,vp.y,vp.w,vp.h,...view.camera.matrixWorld.elements,...view.camera.projectionMatrix.elements].join(',');
  const projectionChanged=key!==projectionKey||!lensCamera;
  if(projectionChanged){
   lensCamera=view.camera.clone();lensCamera.setViewOffset(vp.w,vp.h,x-vp.x-patch/2,y-vp.y-patch/2,patch,patch);lensCamera.updateMatrixWorld();projectionKey=key;
  }
  const camera=lensCamera!;
  // Keep the GPU image inside its source canvas, even when a viewer is partially scrolled.
  const minX=Math.max(8,rect.left),maxX=Math.min(win.innerWidth-8,rect.right)-SIZE;
  const minY=Math.max(8,rect.top),maxY=Math.min(win.innerHeight-8,rect.bottom)-SIZE;
  const preferred=point.x+SIZE+32<Math.min(win.innerWidth,rect.right)?point.x+26:point.x-SIZE-26;
  const left=Math.max(minX,Math.min(maxX,preferred)),top=Math.max(minY,Math.min(maxY,point.y-SIZE/2));
  // Only intersecting chrome needs a mask; masking every panel adds compositor work even far from the lens.
  const surface=host.parentElement;if(projectionChanged&&surface?.classList.contains('tw-app'))for(const child of surface.children){
   if(child===host||!(child instanceof win.HTMLElement))continue;const r=child.getBoundingClientRect(),hit=r.right>left&&r.left<left+SIZE&&r.bottom>top&&r.top<top+SIZE;
   child.toggleAttribute('data-lens-obscured',hit);if(hit){child.style.setProperty('--warehouse-mask-left',(r.left-rect.left)+'px');child.style.setProperty('--warehouse-mask-top',(r.top-rect.top)+'px');}
  }
  const previous={target:renderer.getRenderTarget(),viewport:renderer.getViewport(new THREE.Vector4()),scissor:renderer.getScissor(new THREE.Vector4()),scissorTest:renderer.getScissorTest(),autoClear:renderer.autoClear,shadowAuto:renderer.shadowMap.autoUpdate};
  const now=performance.now(),reuse=!projectionChanged&&liveTarget===target&&now-liveAt<LIVE_REFRESH_MS;
  try{
   renderer.setRenderTarget(target!);renderer.setScissorTest(false);renderer.autoClear=true;renderer.shadowMap.autoUpdate=false;
   if(reuse){}
   else if(view.cacheKey!==undefined){
    ensureStaticTarget();
    const key=view.cacheKey+'|'+camera.matrixWorld.elements+'|'+camera.projectionMatrix.elements+'|'+target!.width;
    if(key!==staticKey){renderer.setRenderTarget(staticTarget!);view.draw(camera,'static');staticKey=key;}
    renderer.setRenderTarget(target!);renderer.autoClear=true;renderer.render(staticScene!,camera);renderer.autoClear=false;view.draw(camera,'dynamic');
   }else view.draw(camera,'all');
   if(!reuse){liveAt=now;liveTarget=target;}
   renderer.setRenderTarget(previous.target);renderer.setScissorTest(false);renderer.autoClear=false;
   renderer.setViewport(left-rect.left,rect.height-(top-rect.top)-SIZE,SIZE,SIZE);renderer.render(composite!,camera);
  }finally{
   renderer.setRenderTarget(previous.target);renderer.setViewport(previous.viewport);renderer.setScissor(previous.scissor);renderer.setScissorTest(previous.scissorTest);renderer.autoClear=previous.autoClear;renderer.shadowMap.autoUpdate=previous.shadowAuto;
  }
  if(lens.style.left!==left+'px')lens.style.left=left+'px';if(lens.style.top!==top+'px')lens.style.top=top+'px';const text=view.caption+' · '+shownZoom();if(caption.textContent!==text)caption.textContent=text;
  if(surface){surface.dataset.lensVisible='true';surface.style.setProperty('--warehouse-lens-x',(left-rect.left+SIZE/2)+'px');surface.style.setProperty('--warehouse-lens-y',(top-rect.top+SIZE/2)+'px');}
  lens.hidden=false;lens.dataset.draws=String(++draws);lens.dataset.captures=String(draws);lens.dataset.caption=view.caption;lens.dataset.pointX=String(x);lens.dataset.pointY=String(y);lens.dataset.pixels=String(target!.width);
 }
 function setEnabled(value:boolean,keyboard=false){
  if(disposed||lost)return;enabled=value;
  if(!enabled){point=null;hide();}else if(keyboard){const r=source.getBoundingClientRect();point={x:r.left+r.width/2,y:r.top+r.height/2};}
  sync();requestRender();
 }
 function changeZoom(delta:number){zoom=Math.max(MIN_ZOOM,Math.min(MAX_ZOOM,Math.round((zoom+delta)*2)/2));sync();requestRender();}
 button.addEventListener('click',e=>{e.stopPropagation();setEnabled(!enabled,e.detail===0);},events);
 for(const type of ['pointerdown','pointerup'])button.addEventListener(type,e=>e.stopPropagation(),events);
 for(const type of ['pointerdown','pointerup'])host.addEventListener(type,e=>{if(e.target instanceof win.Node&&button.contains(e.target))e.stopImmediatePropagation();},{...events,capture:true});
 // Labels, badges, pins and thought bubbles float above the canvas; the lens keeps working over them and only hides
 // over real controls (dock, panels, menus, this button) or outside the canvas.
 const overScene=(t:EventTarget|null)=>t===source||(t instanceof win.Element&&!!t.closest('.tw-layer')&&!button.contains(t));
 doc.addEventListener('pointermove',e=>{if(!enabled||e.pointerType==='touch')return;if(!overScene(e.target)||!inside(e.clientX,e.clientY)){if(point){point=null;hide();requestRender();}return;}point={x:e.clientX,y:e.clientY};requestRender();},events);
 doc.documentElement.addEventListener('pointerleave',e=>{if(e.pointerType==='touch'||!point)return;point=null;hide();if(enabled)requestRender();},events);
 host.addEventListener('wheel',e=>{if(!enabled||e.target!==source)return;e.preventDefault();e.stopImmediatePropagation();if(!e.deltaY)return;point={x:e.clientX,y:e.clientY};changeZoom(e.deltaY<0?.5:-.5);},{...events,capture:true,passive:false});
 const editing=(value:EventTarget|null)=>value instanceof win.HTMLElement&&(value.isContentEditable||!!value.closest('input,textarea,select,[role=slider]'));
 doc.addEventListener('keydown',e=>{
  if(!enabled||editing(e.target))return;
  if(e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();setEnabled(false);button.focus({preventScroll:true});return;}
  if(e.key==='+'||e.key==='='||e.key==='-'){e.preventDefault();e.stopImmediatePropagation();changeZoom(e.key==='-'?-.5:.5);return;}
  if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;
  e.preventDefault();e.stopImmediatePropagation();const r=source.getBoundingClientRect(),step=e.shiftKey?36:14;
  point??={x:r.left+r.width/2,y:r.top+r.height/2};point.x=Math.max(r.left+1,Math.min(r.right-1,point.x+(e.key==='ArrowRight'?step:e.key==='ArrowLeft'?-step:0)));point.y=Math.max(r.top+1,Math.min(r.bottom-1,point.y+(e.key==='ArrowDown'?step:e.key==='ArrowUp'?-step:0)));requestRender();
 },{...events,capture:true});
 const invalidate=()=>{hide();if(enabled)requestRender();};
 win.addEventListener('resize',invalidate,events);win.addEventListener('scroll',()=>{point=null;invalidate();},{...events,capture:true});
 doc.addEventListener('visibilitychange',()=>{if(doc.hidden){point=null;hide();}else if(enabled)requestRender();},events);
 source.addEventListener('webglcontextlost',()=>{staticKey='';lost=true;enabled=false;point=null;hide();sync();button.disabled=true;button.title='Лупа недоступна: восстанавливается графический контекст.';},events);
 source.addEventListener('webglcontextrestored',()=>{staticKey='';lost=false;button.disabled=false;button.title='Лупа · колесо меняет увеличение · Esc выключает';sync();},events);
 sync();
 function dispose(){if(disposed)return;disposed=true;enabled=false;point=null;lifetime.abort();hide();source.classList.remove('warehouse-magnifier-source-active');if(oldTabIndex===null)source.removeAttribute('tabindex');else source.setAttribute('tabindex',oldTabIndex);button.remove();help.remove();lens.remove();target?.dispose();staticTarget?.depthTexture?.dispose();staticTarget?.dispose();staticMaterial?.dispose();staticScene?.clear();geometry?.dispose();material?.dispose();composite?.clear();}
 return {render,dispose,snapshot:()=>({enabled,visible:!lens.hidden&&!disposed,zoom,draws,captures:draws,disposed,pending_frame:false,kind:'optical-3d',target_pixels:target?.width??0})};
}
