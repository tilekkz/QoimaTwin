/**
 * Camera for the A/B page. Left drag (one finger) orbits around the target, right/middle drag, Shift+drag or two
 * fingers pan with the grabbed point staying under the pointer, wheel and pinch zoom towards the cursor. Everything
 * settles with exponential smoothing and a little inertia. A and B always share one camera. Input is captured on
 * the viewport host before the scene's OrbitControls sees it; everything moves through scene.frameAt(target, span, dir).
 */
import type {XYZ} from '../warehouseTypes';

type Scene={frameAt(target:XYZ,span:number,dir?:XYZ):void;frameState():{target:XYZ;span:number;dir:XYZ}};
export type NavOptions={
 host:HTMLElement;scene:Scene;
 /** Overlay layers above the canvas (bubbles, pins, badges): wheel over them still zooms, clicks stay theirs. */
 wheelAlso?:HTMLElement[];
 /** World point on the horizontal plane y=planeY under a host-relative screen point, or null outside any view. */
 ground:(x:number,y:number,planeY:number)=>XYZ|null;
 reduced:()=>boolean;
 onTap:(x:number,y:number)=>void;
 /** Any user camera input: lets the page cancel an animated fly-to. */
 onInput:()=>void;
 onMove:()=>void;
};
export const SPAN_MIN=10,SPAN_MAX=300;
/** Time constants (s): how quickly zoom reaches its goal and how long a flick keeps sliding or turning. */
const TAU_ZOOM=.11,TAU_GLIDE=.32,TAU_SPIN=.28;
/** Covers both warehouses when B stands beside A in «Рядом». */
const BOUNDS={x:[-12,156],z:[-12,168]};
/** Orbit: radians per pixel, and the elevation range (from a low oblique view to straight down). */
const ROT=.0065,ELEV:[number,number]=[.2,1.52];
type Kind='orbit'|'pan';

const angles=(d:XYZ)=>({yaw:Math.atan2(d[0],d[2]),elev:Math.asin(Math.max(-1,Math.min(1,d[1]/Math.hypot(...d))))});
const dirOf=(yaw:number,elev:number):XYZ=>[Math.cos(elev)*Math.sin(yaw),Math.sin(elev),Math.cos(elev)*Math.cos(yaw)];

export function createNavigation(o:NavOptions){
 const pointers=new Map<number,{x:number;y:number}>();
 let raf=0,last=0,goal=0,anchor:{p:XYZ;t0:XYZ;s0:number}|null=null,vel:[number,number]=[0,0],spin:[number,number]=[0,0];
 let down:{x:number;y:number;at:number;moved:boolean;kind:Kind}|null=null,trail:{t:number;a:number;b:number}[]=[],pinch:{d:number;mx:number;my:number}|null=null;
 const local=(e:{clientX:number;clientY:number})=>{const r=o.host.getBoundingClientRect();return {x:e.clientX-r.left,y:e.clientY-r.top};};
 const clampT=(t:XYZ):XYZ=>[Math.min(BOUNDS.x[1],Math.max(BOUNDS.x[0],t[0])),t[1],Math.min(BOUNDS.z[1],Math.max(BOUNDS.z[0],t[2]))];
 const clampS=(s:number)=>Math.min(SPAN_MAX,Math.max(SPAN_MIN,s));
 function set(t:XYZ,s:number,d?:XYZ){o.scene.frameAt(clampT(t),clampS(s),d??o.scene.frameState().dir);o.onMove();}
 /** Turns the camera around its target by screen-pixel deltas. */
 function orbitBy(dx:number,dy:number){
  const st=o.scene.frameState(),{yaw,elev}=angles(st.dir);
  set(st.target,st.span,dirOf(yaw-dx*ROT,Math.min(ELEV[1],Math.max(ELEV[0],elev+dy*ROT))));
 }
 /** Zooms by factor f about a screen point immediately (pinch). */
 function zoomNow(x:number,y:number,f:number){
  const {target:t,span:s}=o.scene.frameState(),p=o.ground(x,y,t[1]),s1=clampS(s*f),k=s1/s;
  set(p?[p[0]-(p[0]-t[0])*k,t[1],p[2]-(p[2]-t[2])*k]:t,s1);goal=s1;anchor=null;
 }
 /** Pans so the ground point under (x0,y0) ends up under (x1,y1). */
 function panBy(x0:number,y0:number,x1:number,y1:number){
  const {target:t,span:s}=o.scene.frameState(),a=o.ground(x0,y0,t[1]),b=o.ground(x1,y1,t[1]);if(!a||!b)return;
  set([t[0]+a[0]-b[0],t[1],t[2]+a[2]-b[2]],s);
 }
 function loop(now:number){
  raf=0;const dt=Math.min(.05,(now-last)/1000);last=now;let active=false;
  const still=o.reduced();if(still){vel=[0,0];spin=[0,0];}
  const st=o.scene.frameState(),{target:t,span:s}=st;let nt=t,ns=s,nd=st.dir;
  if(anchor){
   const k=still?1:1-Math.exp(-dt/TAU_ZOOM);ns=Math.exp(Math.log(s)+(Math.log(goal)-Math.log(s))*k);
   if(Math.abs(Math.log(ns/goal))<.002)ns=goal;else active=true;
   const r=ns/anchor.s0,p=anchor.p;nt=[p[0]-(p[0]-anchor.t0[0])*r,t[1],p[2]-(p[2]-anchor.t0[2])*r];
   if(!active)anchor=null;
  }else if(!pointers.size&&Math.hypot(...vel)>.05){
   nt=[t[0]+vel[0]*dt,t[1],t[2]+vel[1]*dt];const d=Math.exp(-dt/TAU_GLIDE);vel=[vel[0]*d,vel[1]*d];active=true;
  }
  if(!pointers.size&&Math.hypot(...spin)>.02){
   const {yaw,elev}=angles(st.dir);nd=dirOf(yaw+spin[0]*dt,Math.min(ELEV[1],Math.max(ELEV[0],elev+spin[1]*dt)));
   const d=Math.exp(-dt/TAU_SPIN);spin=[spin[0]*d,spin[1]*d];active=true;
  }
  if(nt!==t||ns!==s||nd!==st.dir)set(nt,ns,nd);
  if(active)raf=requestAnimationFrame(loop);
 }
 const kick=()=>{if(!raf){last=performance.now();raf=requestAnimationFrame(loop);}};
 function stop(){cancelAnimationFrame(raf);raf=0;anchor=null;vel=[0,0];spin=[0,0];}
 /** Remember where the gesture was, by event time: on a busy main thread events arrive late, and the gesture's own
  *  timing decides the flick. Pan records the target, orbit records the angles. */
 function remember(kind:Kind,ts:number){
  const st=o.scene.frameState(),g=kind==='pan'?{a:st.target[0],b:st.target[2]}:(({yaw,elev})=>({a:yaw,b:elev}))(angles(st.dir));
  trail.push({t:ts,...g});while(trail.length>2&&ts-trail[0].t>100)trail.shift();
 }

 function wheel(e:WheelEvent){
  e.preventDefault();e.stopPropagation();o.onInput();vel=[0,0];spin=[0,0];
  const unit=e.deltaMode===1?16:e.deltaMode===2?400:1,dy=Math.max(-240,Math.min(240,e.deltaY*unit));
  // Trackpad pinch arrives as ctrl+wheel with small deltas.
  const f=Math.exp(dy*(e.ctrlKey?.012:.0016)),{x,y}=local(e),{target:t,span:s}=o.scene.frameState(),p=o.ground(x,y,t[1]);
  goal=clampS((anchor?goal:s)*f);anchor={p:p??t,t0:t,s0:s};
  if(o.reduced()){loop(performance.now());return;}kick();
 }
 function pointerdown(e:PointerEvent){
  if(e.pointerType==='mouse'&&e.button>2)return;e.stopPropagation();if(e.button===1||e.button===2)e.preventDefault();o.host.setPointerCapture(e.pointerId);
  const p=local(e);pointers.set(e.pointerId,p);o.onInput();stop();
  // Mouse: left orbits, right/middle or Shift pans. Touch: one finger orbits, two fingers pan and pinch.
  const kind:Kind=e.pointerType!=='touch'&&(e.button===1||e.button===2||e.shiftKey)?'pan':'orbit';
  if(pointers.size===1){down={...p,at:performance.now(),moved:false,kind};trail=[];}
  else{down=null;const [a,b]=[...pointers.values()];pinch={d:Math.hypot(a.x-b.x,a.y-b.y),mx:(a.x+b.x)/2,my:(a.y+b.y)/2};}
 }
 function pointermove(e:PointerEvent){
  const prev=pointers.get(e.pointerId);if(!prev)return;e.stopPropagation();const p=local(e);
  if(pointers.size>=2&&pinch){
   pointers.set(e.pointerId,p);const [a,b]=[...pointers.values()],d=Math.hypot(a.x-b.x,a.y-b.y),mx=(a.x+b.x)/2,my=(a.y+b.y)/2;
   if(d>8)zoomNow(mx,my,pinch.d/d);panBy(pinch.mx,pinch.my,mx,my);pinch={d,mx,my};return;
  }
  // A tap may wobble a few pixels; only real drags move the camera.
  if(down&&!down.moved&&Math.hypot(p.x-down.x,p.y-down.y)<5)return;
  pointers.set(e.pointerId,p);if(!down)return;down.moved=true;
  if(down.kind==='pan')panBy(prev.x,prev.y,p.x,p.y);else orbitBy(p.x-prev.x,p.y-prev.y);
  remember(down.kind,e.timeStamp);
 }
 function pointerup(e:PointerEvent){
  if(!pointers.delete(e.pointerId))return;e.stopPropagation();
  if(pointers.size<2)pinch=null;
  if(pointers.size===1){const [q]=[...pointers.values()];down={...q,at:performance.now(),moved:true,kind:'pan'};trail=[];return;}
  if(down&&!down.moved&&performance.now()-down.at<600&&e.type==='pointerup'&&e.button===0){const p=local(e);o.onTap(p.x,p.y);}
  else if(down?.moved&&trail.length>1&&!o.reduced()){
   const a=trail[0],b=trail.at(-1)!,dt=(b.t-a.t)/1000;
   if(dt>.01&&e.timeStamp-b.t<80){const v:[number,number]=[(b.a-a.a)/dt,(b.b-a.b)/dt];if(down.kind==='pan')vel=v;else spin=v;kick();}
  }
  down=null;
 }
 const opts={capture:true,passive:false} as const;
 // Right-drag pans, so the browser's context menu stays out of the way on the canvas.
 const swallow=(e:Event)=>{e.preventDefault();e.stopPropagation();};
 const listeners:[string,(e:never)=>void][]=[['wheel',wheel],['pointerdown',pointerdown],['pointermove',pointermove],['pointerup',pointerup],['pointercancel',pointerup],['contextmenu',swallow]];
 for(const [type,fn] of listeners)o.host.addEventListener(type,fn as EventListener,opts);
 for(const el of o.wheelAlso??[])el.addEventListener('wheel',wheel,opts);
 return {
  stop,
  /** Jump to where a smooth zoom was heading (reduced motion, hidden page); glides and turns just stop. */
  finish(){if(anchor){const {target:t}=o.scene.frameState(),r=goal/anchor.s0,p=anchor.p;set([p[0]-(p[0]-anchor.t0[0])*r,t[1],p[2]-(p[2]-anchor.t0[2])*r],goal);}stop();},
  /** Keyboard / button zoom about the view centre. */
  zoomBy(f:number){const {target:t,span:s}=o.scene.frameState();goal=clampS((anchor?goal:s)*f);anchor={p:t,t0:t,s0:s};vel=[0,0];o.onInput();if(o.reduced())loop(performance.now());else kick();},
  /** Keyboard turn by an angle (radians), smoothed like a short flick. */
  turnBy(yaw:number){o.onInput();stop();if(o.reduced()){const st=o.scene.frameState(),{yaw:y,elev}=angles(st.dir);set(st.target,st.span,dirOf(y+yaw,elev));return;}spin=[yaw/TAU_SPIN,0];kick();},
  dispose(){stop();for(const [type,fn] of listeners)o.host.removeEventListener(type,fn as EventListener,opts);for(const el of o.wheelAlso??[])el.removeEventListener('wheel',wheel,opts);},
 };
}
