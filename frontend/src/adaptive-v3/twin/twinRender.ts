/**
 * A/B drawing on the warehouse scene's single WebGL renderer.
 * One scene, two cargo states: B differs from A only by admitted HU relocations, so each pass swaps
 * the HU instance matrices captured from the real cargo state, draws, then restores A.
 * Overlays (zone states, wave pulses, move markers) live in a separate scene drawn on top.
 */
import * as THREE from 'three';
import type {V3Record,WarehouseBundle,XYZ} from '../warehouseTypes';
import {createWarehouseCargo} from '../warehouseCargo';
import {createTwinInventoryScene} from './twinInventoryScene';
import type {createTwinInventory} from './twinInventory';
import type {TwinShiftScene} from './twinShiftScene';
import type {WarehouseLayoutPlan} from '../warehouseLayoutPlan';
import type {WarehouseLayoutAccessResult} from '../warehouseLayoutAccess';
import {createTwinLayoutVariant,type TwinLayoutPlan} from './twinLayoutVariant';
import {ATMO_ZONES,activePulses,sampleAtmosphere,type AtmoState,type Variant} from './twinScenario';
import {reactionsAt,visibleReactions,type Bubble,type Effects,type WorkerSpot} from './twinScenario';

export type Mode='side'|'swipe';
export type Pose={position:XYZ;yaw:number;dims:XYZ};
export type Move={id:string;sku:string;archetype:string;from_slot:string;to_slot:string;port_id:string;before_m:number;after_m:number;move_m:number;a:Pose;b:Pose};
export type Pick={variant:Variant;kind:'HU'|'module'|'actor';id:string};
type Rect={x:number;y:number;w:number;h:number};
/** One render pass; `round` lists which window corners this pass owns (tl, tr, bl, br) on the region rectangle. */
type Pass={variant:Variant;vp:Rect;sc:Rect;zoom:number;round:string[];shift:THREE.Vector3};
/** «Рядом»: B stands next to A in the same space, long walls parallel, with an aisle between them. */
export const SIDE_GAP_M=12,SIDE_SHIFT:XYZ=[0,0,72+SIDE_GAP_M];
const NO_SHIFT=new THREE.Vector3(),B_SHIFT=new THREE.Vector3(...SIDE_SHIFT);

export const STATE_RU:Record<AtmoState,string>={control:'Контроль',danger:'Опасность',sos:'SOS',nodata:'Нет данных'};
export const STATE_COLOR:Record<AtmoState,string>={control:'#2FA36B',danger:'#E5A00D',sos:'#E5484D',nodata:'#8A9692'};
export const ICON:Record<AtmoState,string>={
 control:'<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M5 8.3l2 2 4-4.3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
 danger:'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.6l6.8 12H1.2z" fill="currentColor"/><path d="M8 6.2v3.4" stroke="#172322" stroke-width="1.6" stroke-linecap="round"/><circle cx="8" cy="11.6" r=".95" fill="#172322"/></svg>',
 sos:'<svg viewBox="0 0 16 16" aria-hidden="true"><polygon points="5,1.4 11,1.4 14.6,5 14.6,11 11,14.6 5,14.6 1.4,11 1.4,5" fill="currentColor"/><path d="M8 4.4v4.6" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/><circle cx="8" cy="11.4" r="1" fill="#fff"/></svg>',
 nodata:'<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-dasharray="2.4 2"/></svg>',
};
/** Thought-bubble glyphs: symbols instead of comic lines. */
const BUBBLE_ICON:Record<Bubble,string>={
 wait:'<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="5.8" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M8 4.8V8l2.2 1.4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
 question:'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5.6 5.9a2.5 2.5 0 1 1 3.6 2.2c-.8.4-1.2.9-1.2 1.7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="8" cy="12.6" r="1.05" fill="currentColor"/></svg>',
 alert:'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.6v6.6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><circle cx="8" cy="12.7" r="1.25" fill="currentColor"/></svg>',
 help:'<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="5.6" cy="5.4" r="2" fill="currentColor"/><path d="M2.4 13c0-2.2 1.4-3.6 3.2-3.6s3.2 1.4 3.2 3.6" fill="currentColor"/><path d="M11.8 4v5M9.3 6.5h5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
 relief:'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.6 8.4l2.9 2.9 5.9-6.2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};
const BUDGET_MAX=6;
/** Below this scale a 1.7 m worker is under ~6 px tall: show the zone badge only. Desktop side-by-side overview is ~5 px/m. */
const BUBBLE_MIN_PX_PER_M=3.5;
const ACCENT='#0E8076',GHOST='#5E6E6A',GAP='#E9EFEC';
export const VARIANT_TITLE:Record<Variant,string>={A:'Как сейчас',B:'После перестройки'};
/** Soft sky behind the warehouse instead of a flat fill. */
function skyTexture(){const c=document.createElement('canvas');c.width=2;c.height=256;const g=c.getContext('2d')!,gr=g.createLinearGradient(0,0,0,256);gr.addColorStop(0,'#F5F8F6');gr.addColorStop(1,'#D5E0DB');g.fillStyle=gr;g.fillRect(0,0,2,256);const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;return t;}

export function createTwinRenderer(bundle:WarehouseBundle,layer:HTMLElement,reducedMotion:()=>boolean){
 let ctx:{renderer:THREE.WebGLRenderer;scene:THREE.Scene;camera:THREE.OrthographicCamera}|null=null,ready=false,disposed=false;
 let mode:Mode='side',split=.5,t=0,selected:string|null=null,moves:Move[]=[],focus:Partial<Record<Variant,Pose>>|null=null;
 let effects:Effects='full',budget=BUDGET_MAX,selectedActor:string|null=null,onBubble:(id:string,v:Variant)=>void=()=>{},onLabel:(v:Variant)=>void=()=>{};
 const spots:WorkerSpot[]=[],heads=new Map<string,THREE.Vector3>();
 let layout:ReturnType<typeof createTwinLayoutVariant>|undefined;
 let inventory:ReturnType<typeof createTwinInventoryScene>|undefined;
 let motion:TwinShiftScene|undefined;
 const motionLights=new Map<THREE.Object3D,number>();
 const zoneEdgesA=new Map<string,THREE.BufferGeometry>(),zoneEdgesB=new Map<string,THREE.BufferGeometry>();
 const overlay=new THREE.Scene(),owned:(THREE.BufferGeometry|THREE.Material)[]=[];
 const own=<T extends THREE.BufferGeometry|THREE.Material>(x:T)=>{owned.push(x);return x;};
 /** Racks and stored goods retain a colour/depth cache. Moving workers, vehicles and belt cargo
  * render on layer 1 at the current clock time against that depth on every A/B pass. */
 /*  While the camera moves, at most one pass is re-rendered per animation frame; the other is shown as its last
  *  image shifted and scaled to the new camera. With a fixed-orientation orthographic camera that reprojection is
  *  exact for colour and depth (only the edge that scrolls into view is missing for one frame). */
 let version=0,renderedThisFrame=false,frameReset=0,pending=0,lastCam='',camMovedAt=0;
 /*  While the camera turns, no cached image can be reused (reprojection is exact only for a fixed orientation), so
  *  both copies re-render every frame. Then they render at ROTATING_SCALE without the overscan margin (about 6.5×
  *  fewer pixels on an integrated GPU) and once more at full size as soon as the turn stops. */
 const ROTATING_SCALE=.55,ROTATING_HOLD_MS=150;let lastQuat=new THREE.Quaternion(),rotatedAt=-1e9,sharpenTimer=0;
 /** While the camera keeps moving, each pass refreshes at most this often; reprojection fills the frames between. */
 const MOVING_REFRESH_MS=150;
 type Cache={rt:THREE.WebGLRenderTarget;key:string;base:string;pos:THREE.Vector3;quat:THREE.Quaternion;hw:number;hh:number;at:number};
 const caches:Cache[]=[],turnCaches:Cache[]=[];
 const blitMat=own(new THREE.ShaderMaterial({uniforms:{tColor:{value:null},tDepth:{value:null},uScale:{value:new THREE.Vector2(1,1)},uOffset:{value:new THREE.Vector2()},uDepthShift:{value:0}},depthTest:true,depthWrite:true,depthFunc:THREE.AlwaysDepth,
  vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}',
  fragmentShader:'uniform sampler2D tColor;uniform sampler2D tDepth;uniform vec2 uScale;uniform vec2 uOffset;uniform float uDepthShift;varying vec2 vUv;void main(){vec2 st=vUv*uScale+uOffset;if(st.x<0.||st.y<0.||st.x>1.||st.y>1.)discard;gl_FragColor=texture2D(tColor,st);gl_FragDepth=clamp(texture2D(tDepth,st).r+uDepthShift,0.,1.);\n#include <tonemapping_fragment>\n#include <colorspace_fragment>\n}'}));
 const AX={x:new THREE.Vector3(1,0,0),y:new THREE.Vector3(0,1,0),z:new THREE.Vector3(0,0,-1)};
 const OVERSCAN=.15;
 /** Where the current view (half-size hw×hh) lies inside a cached image: uv scale/offset and the depth shift. */
 function mapping(c:Cache,hw:number,hh:number,camera:THREE.OrthographicCamera,shift=NO_SHIFT){
  const d=camera.position.clone().sub(shift).sub(c.pos),q=camera.quaternion,kx=hw/c.hw,ky=hh/c.hh;
  return {kx,ky,ox:(1-kx+d.dot(AX.x.clone().applyQuaternion(q))/c.hw)/2,oy:(1-ky+d.dot(AX.y.clone().applyQuaternion(q))/c.hh)/2,dz:-d.dot(AX.z.clone().applyQuaternion(q))/(camera.far-camera.near)};
 }
 function markRendered(){renderedThisFrame=true;if(!frameReset)frameReset=requestAnimationFrame(()=>{frameReset=0;renderedThisFrame=false;});}
 const blitScene=new THREE.Scene(),blitQuad=new THREE.Mesh(own(new THREE.PlaneGeometry(2,2)),blitMat);blitQuad.frustumCulled=false;blitScene.add(blitQuad);
 /** Turning frames use their own small single-sample images; the full-quality ones stay for the still view. */
 function cacheFor(i:number,w:number,h:number,turning=false){
  const list=turning?turnCaches:caches;let c=list[i];
  if(!c){const rt=new THREE.WebGLRenderTarget(w,h,{type:THREE.HalfFloatType,samples:turning?0:4});rt.depthTexture=new THREE.DepthTexture(w,h);c=list[i]={rt,key:'',base:'',pos:new THREE.Vector3(),quat:new THREE.Quaternion(),hw:1,hh:1,at:0};}
  else if(c.rt.width!==w||c.rt.height!==h){c.rt.setSize(w,h);c.key='';c.base='';}
  return c;
 }
 /** Last frame cost, for the debug API and performance notes. */
 const totals={draws:0,scene_renders:0,reprojected:0};
 let stats={passes:0,rendered:0,reprojected:0,calls:0,triangles:0,cpu_ms:0,scene_ms:0,dom_ms:0};
 const hu:{mesh:THREE.InstancedMesh;pos:Partial<Record<Variant,THREE.Vector3>>;arr:Partial<Record<Variant,Float32Array>>;attr:Partial<Record<Variant,THREE.InstancedBufferAttribute>>}[]=[];

 // Zone state floors.
 const zoneRows=bundle.layout.data.zones as V3Record[],zones=new Map<string,{fill:THREE.Mesh;edge:THREE.LineLoop;center:THREE.Vector3;min:[number,number];max:[number,number]}>();
 for(const z of ATMO_ZONES){
  const row=zoneRows.find(r=>r.zone_id===z.id);if(!row)continue;
  const b=row.floor_bounds_xz_m as {min:[number,number];max:[number,number]},w=b.max[0]-b.min[0],d=b.max[1]-b.min[1],cx=(b.min[0]+b.max[0])/2,cz=(b.min[1]+b.max[1])/2;
  const fill=new THREE.Mesh(own(new THREE.PlaneGeometry(w,d)),own(new THREE.MeshBasicMaterial({transparent:true,depthWrite:false})));fill.rotation.x=-Math.PI/2;fill.position.set(cx,.04,cz);
  const pts=[[b.min[0],b.min[1]],[b.max[0],b.min[1]],[b.max[0],b.max[1]],[b.min[0],b.max[1]]].map(([x,zz])=>new THREE.Vector3(x,.06,zz));
  const edge=new THREE.LineLoop(own(new THREE.BufferGeometry().setFromPoints(pts)),own(new THREE.LineBasicMaterial({transparent:true})));
  overlay.add(fill,edge);zones.set(z.id,{fill,edge,center:new THREE.Vector3(cx,1.2,cz),min:b.min,max:b.max});
 }
 // Highlight: the zone pointed at on the plan or in the state list, outlined on the floor of its own copy.
 const hlFill=own(new THREE.MeshBasicMaterial({color:'#0E8076',transparent:true,opacity:.2,depthWrite:false})),hlEdge=own(new THREE.MeshBasicMaterial({color:'#0E8076',transparent:true,opacity:.95,depthWrite:false,depthTest:false}));
 const hl=new THREE.Group();hl.visible=false;overlay.add(hl);let hlVariant:Variant|null=null,hlKey='';
 type Rect2={min:[number,number];max:[number,number]};
 /** One zone (plan hover) or several (a scenario's focus); null clears. */
 function highlightZone(r:Rect2|Rect2[]|null,v:Variant|null=null){
  const list=r?[r].flat():[],key=list.length?`${v}:${JSON.stringify(list)}`:'';if(key===hlKey)return;hlKey=key;
  for(const c of [...hl.children]){(c as THREE.Mesh).geometry.dispose();hl.remove(c);}
  hlVariant=list.length?v:null;
  for(const q of list){
   const [x0,z0]=q.min,[x1,z1]=q.max,w=x1-x0,d=z1-z0,b=Math.min(.8,w/4,d/4);
   const plane=(cx:number,cz:number,pw:number,pd:number,m:THREE.Material)=>{const p=new THREE.Mesh(new THREE.PlaneGeometry(pw,pd),m);p.rotation.x=-Math.PI/2;p.position.set(cx,.09,cz);p.renderOrder=6;hl.add(p);};
   plane((x0+x1)/2,(z0+z1)/2,w,d,hlFill);
   plane((x0+x1)/2,z0+b/2,w,b,hlEdge);plane((x0+x1)/2,z1-b/2,w,b,hlEdge);plane(x0+b/2,(z0+z1)/2,b,d-2*b,hlEdge);plane(x1-b/2,(z0+z1)/2,b,d-2*b,hlEdge);
  }
  draw();
 }
 // Scenario gate tags: a short value above a gate (requests before → after, or what arrives), in copy A.
 // In «Шторка» both halves stand in one place, so each half shows the tags that fall inside it.
 type GateTag={pos:XYZ;title:string;value:string;d:'up'|'down'|'same'};
 let gateTags:GateTag[]=[];const gateEls:Record<Variant,HTMLElement[]>={A:[],B:[]};
 function setGateTags(list:GateTag[]|null){
  gateTags=list??[];
  for(const v of ['A','B'] as Variant[]){
   const els=gateEls[v];while(els.length<gateTags.length){const e=document.createElement('div');e.className='tw-gate';layers[v].append(e);els.push(e);}
   els.forEach((e,i)=>{const g=gateTags[i];e.hidden=!g;if(!g)return;e.dataset.d=g.d;delete e.dataset.w;e.innerHTML=`<span class="tw-gate-in glass"><b>${g.value}</b><small>${g.title}</small></span>`;});
  }
  draw();
 }
 // Wave pulses: a head and a short fading tail.
 const pulseGeo=own(new THREE.SphereGeometry(1,16,10)),pulses:THREE.Mesh[]=[];
 for(let i=0;i<12;i++){const m=new THREE.Mesh(pulseGeo,own(new THREE.MeshBasicMaterial({transparent:true,depthTest:false})));m.renderOrder=20;m.visible=false;overlay.add(m);pulses.push(m);}
 // Move markers.
 const wasGroup=new THREE.Group(),newGroup=new THREE.Group(),arcGroup=new THREE.Group(),selBox=new THREE.LineSegments(own(new THREE.EdgesGeometry(new THREE.BoxGeometry(1,1,1))),own(new THREE.LineBasicMaterial({color:ACCENT,depthTest:false})));
 selBox.renderOrder=30;selBox.visible=false;overlay.add(wasGroup,newGroup,arcGroup,selBox);
 const place=(o:THREE.Object3D,p:Pose,grow=1)=>{o.position.set(p.position[0],p.position[1]+p.dims[1]/2,p.position[2]);o.rotation.set(0,p.yaw,0);o.scale.set(p.dims[0]*grow,p.dims[1]*grow,p.dims[2]*grow);};
 const unitBox=own(new THREE.BoxGeometry(1,1,1)),unitEdges=own(new THREE.EdgesGeometry(unitBox));
 const wasMat=own(new THREE.LineDashedMaterial({color:GHOST,dashSize:.08,gapSize:.06,depthTest:false})),newFill=own(new THREE.MeshBasicMaterial({color:ACCENT,transparent:true,opacity:.42,depthTest:false})),newEdge=own(new THREE.LineBasicMaterial({color:ACCENT,depthTest:false})),arcMat=own(new THREE.LineBasicMaterial({color:ACCENT,transparent:true,opacity:.85,depthTest:false}));

 // DOM: one layer per variant, clipped to its pass.
 const sky=skyTexture();
 const layers={} as Record<Variant,HTMLElement>,bubbles={} as Record<Variant,HTMLButtonElement[]>,badges={} as Record<Variant,Map<string,HTMLElement>>,pins={} as Record<Variant,HTMLElement[]>,labels={} as Record<Variant,HTMLElement>,rings={} as Record<Variant,HTMLElement>,corners={} as Record<Variant,HTMLElement[]>;
 for(const v of ['A','B'] as Variant[]){
  const el=document.createElement('div');el.className='tw-layer';el.dataset.variant=v;layer.append(el);layers[v]=el;
  corners[v]=['tl','tr','bl','br'].map(c=>{const d=document.createElement('span');d.className='tw-cm';d.dataset.c=c;el.append(d);return d;});
  const label=document.createElement('button');label.type='button';label.className='tw-vlabel glass';label.addEventListener('click',()=>onLabel(v));label.innerHTML=`<b>${v}</b><span>${VARIANT_TITLE[v]}<small>${v==='A'?'Спешка · очереди':'Спокойный ритм'}</small></span>`;el.append(label);labels[v]=label;
  const ring=document.createElement('span');ring.className='tw-ring';ring.hidden=true;el.append(ring);rings[v]=ring;
  badges[v]=new Map();for(const z of ATMO_ZONES){if(!zones.has(z.id))continue;const b=document.createElement('span');b.className='tw-badge';b.hidden=true;el.append(b);badges[v].set(z.id,b);}
  pins[v]=[];
  bubbles[v]=Array.from({length:BUDGET_MAX},()=>{const b=document.createElement('button');b.type='button';b.className='tw-bubble';b.hidden=true;b.addEventListener('click',()=>{if(b.dataset.actor)onBubble(b.dataset.actor,v);});el.append(b);return b;});
 }
 const labelW:Partial<Record<Variant,number>>={},labelH:Partial<Record<Variant,number>>={};
 /** Pixels on the right reserved for open panels on desktop; the window narrows instead of being covered. */
 let inset=0;
 /** Pixels on the left kept for floating cards (the demo-shift card) on desktop, so the framing never sits under them. */
 let insetLeft=0;
 /** Canvas CSS size, refreshed by a ResizeObserver: reading clientWidth in every draw forces a layout. */
 let size:[number,number]|null=null,sizeObs:ResizeObserver|null=null;
 function canvasSize(el:HTMLCanvasElement):[number,number]{
  if(!sizeObs){sizeObs=new ResizeObserver(([e])=>{size=[Math.round(e.contentRect.width),Math.round(e.contentRect.height)];});sizeObs.observe(el);}
  return size??(size=[el.clientWidth,el.clientHeight]);
 }
 const project=(p:THREE.Vector3,vp:Rect)=>{const n=p.clone().project(ctx!.camera);return {x:vp.x+(n.x+1)/2*vp.w,y:vp.y+(1-n.y)/2*vp.h};};
 const inside=(q:{x:number;y:number},sc:Rect)=>q.x>=sc.x&&q.x<=sc.x+sc.w&&q.y>=sc.y&&q.y<=sc.y+sc.h;

 function clearMoveArcs(){
  for(const child of arcGroup.children)if(child instanceof THREE.Line)child.geometry.dispose();
  arcGroup.clear();
 }
 function setMoves(next:Move[],onPin:(id:string)=>void){
  moves=next;wasGroup.clear();newGroup.clear();clearMoveArcs();
  for(const v of ['A','B'] as Variant[]){for(const p of pins[v])p.remove();pins[v]=[];}
  next.forEach((m,i)=>{
   const was=new THREE.LineSegments(unitEdges,wasMat);place(was,m.a,1.06);was.computeLineDistances();was.renderOrder=25;wasGroup.add(was);
   const fill=new THREE.Mesh(unitBox,newFill);place(fill,m.b,1.06);fill.renderOrder=24;const edge=new THREE.LineSegments(unitEdges,newEdge);place(edge,m.b,1.08);edge.renderOrder=26;newGroup.add(fill,edge);
   const a=new THREE.Vector3(m.a.position[0],m.a.position[1]+m.a.dims[1],m.a.position[2]),b=new THREE.Vector3(m.b.position[0],m.b.position[1]+m.b.dims[1],m.b.position[2]);
   const mid=a.clone().lerp(b,.5);mid.y+=Math.max(3,a.distanceTo(b)*.22);
   const arc=new THREE.Line(new THREE.BufferGeometry().setFromPoints(new THREE.QuadraticBezierCurve3(a,mid,b).getPoints(40)),arcMat);arc.renderOrder=22;arcGroup.add(arc);
   for(const v of ['A','B'] as Variant[]){const pin=document.createElement('button');pin.type='button';pin.className='tw-pin';pin.dataset.kind=v==='A'?'was':'new';pin.textContent=String(i+1);pin.setAttribute('aria-label',`Перенос ${i+1}: ${m.sku}, ${v==='A'?'исходное место':'новое место'}`);pin.addEventListener('click',()=>onPin(m.id));layers[v].append(pin);pins[v].push(pin);}
  });
 }
 function capture(variant:Variant,scene:THREE.Scene){applied=null;version++;
  if(!hu.length)scene.traverse(o=>{if(o instanceof THREE.InstancedMesh&&o.userData.semanticKind==='HU'){o.frustumCulled=false;hu.push({mesh:o,pos:{},arr:{},attr:{}});}});
  for(const h of hu){h.pos[variant]=h.mesh.position.clone();h.arr[variant]=new Float32Array(h.mesh.instanceMatrix.array as Float32Array);h.attr={};}
 }
 let applied:Variant|null=null;
 function setLayoutPlan(plan:TwinLayoutPlan|null){
  if(!ctx||!ready)throw Error('WAREHOUSE_LAYOUT_RENDERER_NOT_READY');apply('A');
  const next=plan?createTwinLayoutVariant(ctx.scene,bundle,plan):undefined;
  layout?.dispose();layout=next;if(next)overlay.add(next.paint);applied=null;version++;
  for(const g of zoneEdgesB.values())g.dispose();zoneEdgesB.clear();
  for(const [id,z]of zones){if(!zoneEdgesA.has(id))zoneEdgesA.set(id,z.edge.geometry);z.edge.geometry=zoneEdgesA.get(id)!;const r=next?.zones.get(id)?.floor_bounds_xz_m;if(r)zoneEdgesB.set(id,new THREE.BufferGeometry().setFromPoints([[r.min[0],.06,r.min[1]],[r.max[0],.06,r.min[1]],[r.max[0],.06,r.max[1]],[r.min[0],.06,r.max[1]]].map(p=>new THREE.Vector3(...p))));}
  draw();return layout?.snapshot()??null;
 }
 const variantHead=(id:string,v:Variant)=>{
  const moving=motion?.actorPosition(v,t,id);if(moving)return new THREE.Vector3(...moving);
  const p=heads.get(id)?.clone();return p&&v==='B'&&layout?p.add(layout.actorDelta(id)):p;
 };
 const variantWorkers=(v:Variant='A'):readonly WorkerSpot[]=>motion?.workers(v,t)??spots;
 // «Рядом» draws A then B every frame. Rewriting the cargo matrices on each switch, even only the few moved units,
 // updates a buffer the GPU is still drawing from and stalled an integrated GPU by ~20 ms a frame. Each variant owns
 // a fixed matrix buffer instead; switching only swaps which buffer the meshes read.
 function apply(variant:Variant,updateMotion=true){
  if(applied!==variant){
   applied=variant;
   if(layout)layout.apply(variant);
   else for(const h of hu){
    const pos=h.pos[variant],arr=h.arr[variant];if(!pos||!arr)continue;const moved=!h.mesh.position.equals(pos);h.mesh.position.copy(pos);
    h.mesh.instanceMatrix=h.attr[variant]??=new THREE.InstancedBufferAttribute(arr,16);
    if(moved)h.mesh.updateWorldMatrix(true,false);
   }
  }
  inventory?.apply(variant);if(updateMotion)motion?.apply(variant,t);
 }

 function setInventory(next:ReturnType<typeof createTwinInventory>){
  if(!ctx)throw Error('Warehouse scene is not ready');apply('A');
  inventory??=createTwinInventoryScene(ctx.scene,createWarehouseCargo(bundle).snapshot());
  inventory.setInventory(next);version++;draw();
 }
 function setMotion(next:TwinShiftScene){
  if(!ctx)throw Error('Warehouse scene is not ready');motion?.dispose();motion=next;
  ctx.scene.traverse(node=>{if(node instanceof THREE.Light){if(!motionLights.has(node))motionLights.set(node,node.layers.mask);node.layers.enable(1);}});
  motion.setEffects(effects);version++;draw();
 }
 let motionCalls=0,motionTriangles=0;
 function drawMotion(renderer:THREE.WebGLRenderer,scene:THREE.Scene,camera:THREE.Camera){
  motionCalls=0;motionTriangles=0;if(!motion)return;
  const background=scene.background,mask=camera.layers.mask,autoUpdate=scene.matrixWorldAutoUpdate;
  try{
   scene.background=null;camera.layers.set(1);
   // Dynamic instances only change their buffers. Their object transforms stay at
   // the origin; traversing all hidden native rigs twice per pass wastes the cache.
   for(const light of motionLights.keys()){light.updateWorldMatrix(true,false);if(light instanceof THREE.DirectionalLight)light.target.updateWorldMatrix(true,false);}
   scene.matrixWorldAutoUpdate=false;renderer.render(scene,camera);motionCalls=renderer.info.render.calls;motionTriangles=renderer.info.render.triangles;
  }finally{scene.matrixWorldAutoUpdate=autoUpdate;scene.background=background;camera.layers.mask=mask;}
 }

 function overlayFor(variant:Variant){
  const sample=sampleAtmosphere(variant,t),still=reducedMotion();
  if(layout)layout.paint.visible=variant==='B';
  for(const [id,z]of zones){
   const rect=variant==='B'?layout?.zones.get(id)?.floor_bounds_xz_m:undefined,r=rect??{min:z.min,max:z.max};z.fill.position.set((r.min[0]+r.max[0])/2,.04,(r.min[1]+r.max[1])/2);z.fill.scale.set((r.max[0]-r.min[0])/(z.max[0]-z.min[0]),(r.max[1]-r.min[1])/(z.max[1]-z.min[1]),1);z.center.set((r.min[0]+r.max[0])/2,1.2,(r.min[1]+r.max[1])/2);if(zoneEdgesA.has(id))z.edge.geometry=rect?zoneEdgesB.get(id)!:zoneEdgesA.get(id)!;
   const s=sample[id].state,col=STATE_COLOR[s],fm=z.fill.material as THREE.MeshBasicMaterial,em=z.edge.material as THREE.LineBasicMaterial;
   fm.color.set(col);em.color.set(col);
   fm.opacity=({control:.07,danger:.24,sos:.32,nodata:.1} as const)[s]+(s==='sos'&&!still&&effects==='full'?.08*Math.sin(t*1.7):0);em.opacity=s==='control'?.45:.95;
  }
  let k=0;
  if(effects!=='off')for(const p of activePulses(variant,t)){
   const a=zones.get(p.from)?.center,b=zones.get(p.to)?.center;if(!a||!b)continue;
   for(let i=0;i<4&&k<pulses.length;i++,k++){const q=Math.max(0,p.progress-i*.05),m=pulses[k];m.visible=true;m.position.copy(a).lerp(b,q);m.scale.setScalar(1.3-i*.25);const mat=m.material as THREE.MeshBasicMaterial;mat.color.set(STATE_COLOR[p.state]);mat.opacity=(1-i/4)*(p.state==='control'?.6:.95);}
  }
  for(;k<pulses.length;k++)pulses[k].visible=false;
  wasGroup.visible=true;newGroup.visible=arcGroup.visible=variant==='B';
  // In «Шторка» both copies stand in one place, so the outline shows on both halves.
  hl.visible=!!hlVariant&&(mode==='swipe'||hlVariant===variant);
  // A worker gets only the ring: a box round a person reads as a stretched frame from above.
  const f=selectedActor?null:focusPose(variant);selBox.visible=!!f;if(f)place(selBox,f,moves.some(m=>m.id===selected)?1.35:1.15);
 }
 /** Where the selection stands in this copy: a moved unit, a selected worker, or any other picked object (HU, new slot). */
 function focusPose(v:Variant):Pose|null{
  const filled=selected&&inventory?.bounds(selected,v);if(filled)return filled;
  const m=moves.find(m=>m.id===selected);if(m)return v==='A'?m.a:m.b;
  if(selectedActor){const h=variantHead(selectedActor,v);if(h)return {position:[h.x,0,h.z],yaw:0,dims:[.9,h.y+.15,.9]};}
  return focus?.[v]??null;
 }
 function domFor(pass:Pass,W:number,H:number){
  const {variant:v,vp,sc}=pass,sample=sampleAtmosphere(v,t);
  const el=layers[v];el.hidden=false;el.style.clipPath=`inset(${sc.y}px ${Math.max(0,W-sc.x-sc.w)}px ${Math.max(0,H-sc.y-sc.h)}px ${sc.x}px)`;
  // Reading layout every frame forces a synchronous reflow; the label text never changes, so measure once.
  const lw=labelW[v]||(labelW[v]=labels[v].offsetWidth),lh=labelH[v]||(labelH[v]=labels[v].offsetHeight),narrow=W<720;
  // Desktop stacks the labels as captions at the bottom-left of each half; the top-left belongs to the brand menu.
  // Swipe keeps them either side of the blade; phones put them at the top, under the brand button for A.
  if(mode==='side'){
   // In the shared space each label sits beside its own warehouse, by the short west wall.
   // No room left of the wall (narrow window or a kept left column): sit just above the warehouse's north-west corner instead.
   const q=project(new THREE.Vector3(-4,2,36),vp);if(q.x-lw-6>=sc.x+8){labels[v].style.left=q.x-lw-6+'px';labels[v].style.top=q.y-lh/2+'px';}else{const c=project(new THREE.Vector3(0,2,-1.5),vp);labels[v].style.left=Math.max(sc.x+8,c.x)+'px';labels[v].style.top=c.y-lh-4+'px';}
  }else{labels[v].style.left=(narrow?sc.x+8:v==='A'?sc.x+sc.w-lw-34:sc.x+34)+'px';labels[v].style.top=sc.y+(sc.y<60||narrow?62:12)+'px';}
  const R=region(W,H),r=22;
  corners[v].forEach(c=>{const k=c.dataset.c!;c.hidden=!pass.round.includes(k);if(c.hidden)return;c.style.left=(k[1]==='r'?R.x+R.w-r:R.x)+'px';c.style.top=(k[0]==='b'?R.y+R.h-r:R.y)+'px';});
  // Neighbouring zones put their badges side by side; a badge that would cover an earlier one is lifted above it.
  // Sizes are measured only when the badge content changes, never per frame.
  const placed:[number,number,number,number][]=[];
  for(const [id,b]of badges[v]){
   const s=sample[id].state,z=zones.get(id)!;b.hidden=s==='control';if(b.hidden)continue;
   const q=project(z.center.clone().setY(6),vp);b.hidden=!inside(q,sc);if(b.hidden)continue;
   if(b.dataset.state!==s){b.dataset.state=s;b.innerHTML=`<span class="tw-badge-in glass"><i></i>${ATMO_ZONES.find(a=>a.id===id)!.label}<small>${STATE_RU[s]}</small></span>`;b.dataset.w=String(b.offsetWidth);b.dataset.h=String(b.offsetHeight);}
   const w=Number(b.dataset.w)||160,h=Number(b.dataset.h)||30;let y=q.y;
   for(let k=0;k<4;k++){const hit=placed.find(r=>q.x-w/2<r[2]&&q.x+w/2>r[0]&&y-h<r[3]&&y>r[1]);if(!hit)break;y=hit[1]-4;}
   placed.push([q.x-w/2,y-h,q.x+w/2,y]);
   b.style.transform=`translate(${q.x}px,${y}px) translate(-50%,-100%)`;
  }
  const gatesHere=v==='A'||mode==='swipe';
  gateEls[v].forEach((e,i)=>{const g=gateTags[i];if(!g||!gatesHere){e.hidden=true;return;}const q=project(new THREE.Vector3(g.pos[0],5,g.pos[2]),vp);e.hidden=!inside(q,sc);if(e.hidden)return;
   // Gates sit on the outer walls: keep the whole tag inside the view (width measured once per content).
   const w=Number(e.dataset.w)||(e.dataset.w=String(e.offsetWidth),e.offsetWidth),x=Math.min(sc.x+sc.w-w/2-8,Math.max(sc.x+w/2+8,q.x));e.style.transform=`translate(${x}px,${q.y}px) translate(-50%,-100%)`;});
  moves.forEach((m,i)=>{const pin=pins[v][i],p=v==='A'?m.a:m.b,q=project(new THREE.Vector3(p.position[0],p.position[1]+p.dims[1],p.position[2]),vp);pin.hidden=!inside(q,sc);pin.style.translate=`${q.x}px ${q.y}px`;pin.classList.toggle('is-selected',m.id===selected);});
  // Thought bubbles above heads, within the effect budget; the selected worker always keeps its bubble.
  // Far away the zone badge is the aggregated sign; bubbles appear once people are big enough to read.
  const cam=ctx!.camera,pxPerM=vp.w*cam.zoom/(cam.right-cam.left);
  // The budget is spent only on workers inside this pass, so a close-up is not starved by people off screen.
  const onScreen=pxPerM<BUBBLE_MIN_PX_PER_M?[]:reactionsAt(v,t,variantWorkers(v)).map(r=>({r,q:project(variantHead(r.actor_id,v)??new THREE.Vector3(NaN),vp)})).filter(x=>inside(x.q,sc));
  const shown=visibleReactions(onScreen.map(x=>x.r),v==='B'?Math.min(budget,2):budget,selectedActor),at=new Map(onScreen.map(x=>[x.r.actor_id,x.q]));
  bubbles[v].forEach((b,i)=>{
   const r=shown[i],q=r&&at.get(r.actor_id);
   if(!r||!q){b.hidden=true;delete b.dataset.actor;return;}
   const key=`${r.actor_id}:${r.bubble}`;
   if(b.dataset.key!==key){b.dataset.key=key;b.dataset.b=r.bubble;b.innerHTML=`<span class="tw-bubble-in">${BUBBLE_ICON[r.bubble]}</span>`;if(effects!=='off'&&!reducedMotion())b.animate([{opacity:0,scale:.4},{opacity:1,scale:1}],{duration:400,easing:'cubic-bezier(.16,1,.3,1)'});}
   b.dataset.actor=r.actor_id;b.setAttribute('aria-label',`${r.actor_id}: ${r.text}`);b.title=`${r.actor_id} · ${r.text}`;
   b.hidden=false;b.classList.toggle('is-selected',r.actor_id===selectedActor);b.style.translate=`${q.x}px ${q.y}px`;
  });
  const p=focusPose(v);rings[v].hidden=!p;
  if(p){const q=project(new THREE.Vector3(p.position[0],p.position[1]+p.dims[1]/2,p.position[2]),vp);rings[v].hidden=!inside(q,sc);rings[v].style.transform=`translate(${q.x}px,${q.y}px) translate(-50%,-50%)`;}
 }
 /** The window both warehouses live in: the whole screen minus a margin, and minus the right panels on desktop. */
 function region(W:number,H:number):Rect{const narrow=W<720,m=narrow?8:14,left=narrow?0:insetLeft;return {x:m+left,y:m,w:Math.max(240,W-2*m-left-(narrow?0:inset)),h:H-2*m};}
 /** Zoom for a view so the overview framing (a 16:9 window across the warehouse) still fits it: the full width,
  *  and enough height for short wide views. Tall phone views keep the slightly closer framing they had before. */
 const fit=(r:Rect)=>{const a=r.w/r.h;return Math.max(a<1.4?.82:1,.86*a*9/16);};
 function passes(W:number,H:number):Pass[]{
  const R=region(W,H);
  if(mode==='swipe'){const x=Math.round(R.x+R.w*split),zoom=fit(R);return [{variant:'A',vp:R,sc:{x:R.x,y:R.y,w:x-R.x,h:R.h},zoom,round:['tl','bl'],shift:NO_SHIFT},{variant:'B',vp:R,sc:{x,y:R.y,w:R.x+R.w-x,h:R.h},zoom,round:['tr','br'],shift:NO_SHIFT}];}
  // Side: one view, one camera; B is drawn shifted beside A and merged by depth, so it is one 3D scene.
  return [{variant:'A',vp:R,sc:R,zoom:1,round:['tl','tr','bl','br'],shift:NO_SHIFT},{variant:'B',vp:R,sc:R,zoom:1,round:[],shift:B_SHIFT}];
 }
 function setCamera(camera:THREE.OrthographicCamera,span:number,vp:Rect){const half=span/2,aspect=vp.w/vp.h;camera.left=-half;camera.right=half;camera.top=half/aspect;camera.bottom=-half/aspect;camera.updateProjectionMatrix();}
 /*  draw() is asked for by the play loop, the scene render, camera input and setters, often several times in one
  *  display frame; each call redraws both copies. At most one draw per frame: a later request in the same frame is
  *  folded into one draw on the next frame (skipped if that frame already drew after the request). */
 let lastDrawFrame=-1,deferredDraw=0;
 function draw(){
  if(!ctx||!ready||disposed)return;
  const frame=Number(document.timeline.currentTime??performance.now());
  if(frame===lastDrawFrame){if(!deferredDraw)deferredDraw=requestAnimationFrame(()=>{deferredDraw=0;if(Number(document.timeline.currentTime??performance.now())!==lastDrawFrame)draw();});return;}
  lastDrawFrame=frame;const {renderer,scene,camera}=ctx,[W,H]=canvasSize(renderer.domElement);if(!W||!H)return;
  const base=[camera.left,camera.right,camera.top,camera.bottom] as const,span=base[1]-base[0],list=passes(W,H);
  renderer.setScissorTest(false);renderer.setViewport(0,0,W,H);renderer.setClearColor(GAP);renderer.clear();renderer.setScissorTest(true);
  for(const v of ['A','B'] as Variant[])layers[v].hidden=!list.some(p=>p.variant===v);
  if(lastQuat.angleTo(camera.quaternion)>1e-6){lastQuat.copy(camera.quaternion);rotatedAt=performance.now();}
  const rotating=performance.now()-rotatedAt<ROTATING_HOLD_MS;
  if(rotating){clearTimeout(sharpenTimer);sharpenTimer=window.setTimeout(()=>{sharpenTimer=0;draw();},ROTATING_HOLD_MS+20);}
  const t0=performance.now(),pr=renderer.getPixelRatio()*(rotating?ROTATING_SCALE:1),view=`${version}|${camera.position.toArray()}|${camera.quaternion.toArray()}|${camera.zoom}|${span}`;
  let calls=0,tris=0,tScene=0,tDom=0,rendered=0,reprojected=0,shifted=NO_SHIFT;
  // Plan: passes without a usable image must render; of the merely stale ones only the oldest renders this frame.
  // Each cached image is rendered with a whole-pixel margin around the view, so pans and gentle zoom-outs are
  // still covered by the reprojected image; when they are not, that pass re-renders immediately.
  const plan=list.map((p,i)=>{
   const wpx=Math.round(p.vp.w*pr),hpx=Math.round(p.vp.h*pr),px=rotating?0:Math.round(wpx*OVERSCAN),py=rotating?0:Math.round(hpx*OVERSCAN);
   const c=cacheFor(i,wpx+2*px,hpx+2*py,rotating),base=`${p.variant}|${p.vp.x},${p.vp.y},${p.vp.w}x${p.vp.h}`,key=`${view}|${base}|${p.zoom}`;
   const hw=span*(p.zoom??1)/2/camera.zoom,hh=hw*p.vp.h/p.vp.w,os:[number,number]=[(wpx+2*px)/wpx,(hpx+2*py)/hpx];
   const m=c.base===base&&c.quat.angleTo(camera.quaternion)<1e-6?mapping(c,hw,hh,camera,p.shift):null;
   const usable=!!m&&m.ox>-.002&&m.oy>-.002&&m.ox+m.kx<1.002&&m.oy+m.ky<1.002;
   return {p,c,base,key,hw,hh,os,stale:c.key!==key,usable};
  });
  const camKey=`${camera.position.toArray()}|${camera.quaternion.toArray()}|${camera.zoom}|${span}`,now=performance.now();if(camKey!==lastCam){lastCam=camKey;camMovedAt=now;}const moving=now-camMovedAt<120;
  const oldest=plan.filter(x=>x.stale&&x.usable&&(!moving||now-x.c.at>=MOVING_REFRESH_MS)).sort((a,b)=>a.c.at-b.c.at)[0];
  const renderNow=new Set(plan.filter(x=>x.stale&&(!x.usable||(x===oldest&&!renderedThisFrame))));
  try{
   for(const x of plan){
    const {p,c,base,key,hw,hh,os}=x;
    // Drawing B beside A = drawing B's scene from a camera moved the other way; the scene's own matrices stay untouched.
    camera.position.sub(p.shift);camera.updateMatrixWorld();shifted=p.shift;
    motion?.setDetail(p.vp.w*camera.zoom/span>13);overlayFor(p.variant);
    let k=performance.now();
    if(renderNow.has(x)){
     // Render the padded frustum into the cache.
     camera.left=-hw*os[0]*camera.zoom;camera.right=hw*os[0]*camera.zoom;camera.top=hh*os[1]*camera.zoom;camera.bottom=-hh*os[1]*camera.zoom;camera.updateProjectionMatrix();
     apply(p.variant);renderer.setRenderTarget(c.rt);
     // The first scene render of this draw already updated world matrices; later passes only swap instance data.
     if(rendered)scene.matrixWorldAutoUpdate=false;
     try{renderer.render(scene,camera);}finally{scene.matrixWorldAutoUpdate=true;renderer.setRenderTarget(null);}
     calls+=renderer.info.render.calls;tris+=renderer.info.render.triangles;rendered++;markRendered();
     Object.assign(c,{key,base,hw:hw*os[0],hh:hh*os[1],at:performance.now()});c.pos.copy(camera.position);c.quat.copy(camera.quaternion);
    }
    setCamera(camera,span*(p.zoom??1),p.vp);motion?.setView(camera);
    // Map this view into the cached image: exact crop when the camera is unchanged, shifted/scaled while it moves.
    const u=blitMat.uniforms,m=mapping(c,hw,hh,camera);
    u.uScale.value.set(m.kx,m.ky);u.uOffset.value.set(m.ox,m.oy);u.uDepthShift.value=m.dz;
    if(c.key!==key)reprojected++;
    renderer.setViewport(p.vp.x,H-p.vp.y-p.vp.h,p.vp.w,p.vp.h);renderer.setScissor(p.sc.x,H-p.sc.y-p.sc.h,p.sc.w,p.sc.h);
    u.tColor.value=c.rt.texture;u.tDepth.value=c.rt.depthTexture;
    // A pass that shares the view with an earlier one is merged by depth instead of painted over it.
    const at=plan.indexOf(x),merge=at>0&&plan[at-1].p.vp===p.vp;blitMat.depthFunc=merge?THREE.LessEqualDepth:THREE.AlwaysDepth;
     renderer.autoClear=false;renderer.render(blitScene,camera);calls+=renderer.info.render.calls;tris+=renderer.info.render.triangles;apply(p.variant);drawMotion(renderer,scene,camera);calls+=motionCalls;tris+=motionTriangles;renderer.render(overlay,camera);calls+=renderer.info.render.calls;tris+=renderer.info.render.triangles;renderer.autoClear=true;
    tScene+=performance.now()-k;k=performance.now();domFor(p,W,H);tDom+=performance.now()-k;
    camera.position.add(shifted);camera.updateMatrixWorld();shifted=NO_SHIFT;
   }
   // Something is still shown from an older camera: finish it on the next frame even if nothing else asks.
   if(reprojected&&!pending)pending=requestAnimationFrame(()=>{pending=0;draw();});
  }finally{if(shifted!==NO_SHIFT){camera.position.add(shifted);camera.updateMatrixWorld();}blitMat.depthFunc=THREE.AlwaysDepth;scene.matrixWorldAutoUpdate=true;renderer.autoClear=true;renderer.setRenderTarget(null);[camera.left,camera.right,camera.top,camera.bottom]=base;camera.updateProjectionMatrix();apply('A',false);renderer.setScissorTest(false);renderer.setViewport(0,0,W,H);}
  totals.draws++;totals.scene_renders+=rendered;totals.reprojected+=reprojected;
  stats={passes:list.length,rendered,reprojected,calls,triangles:tris,cpu_ms:+(performance.now()-t0).toFixed(2),scene_ms:+tScene.toFixed(2),dom_ms:+tDom.toFixed(2)};
 }
 /** Host-relative screen point → point on the horizontal plane y=planeY, in the pass under the pointer. */
 function ground(x:number,y:number,planeY:number):XYZ|null{
  if(!ctx)return null;const {renderer,camera}=ctx,[W,H]=canvasSize(renderer.domElement);
  const list=passes(W,H),p=list.find(p=>inside({x,y},p.sc))??list[0];if(!p)return null;
  const base=[camera.left,camera.right,camera.top,camera.bottom] as const;
  try{
   setCamera(camera,(base[1]-base[0])*(p.zoom??1),p.vp);camera.updateMatrixWorld();
   const ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2((x-p.vp.x)/p.vp.w*2-1,-(y-p.vp.y)/p.vp.h*2+1),camera);
   const hit=ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0,1,0),-planeY),new THREE.Vector3());
   return hit?hit.toArray() as XYZ:null;
  }finally{[camera.left,camera.right,camera.top,camera.bottom]=base;camera.updateProjectionMatrix();}
 }
 /** Screen point → semantic object, using the pass under the pointer and that pass's cargo state. */
 function pick(x:number,y:number):Pick|null{
  if(!ctx||!ready)return null;const {renderer,scene,camera}=ctx,[W,H]=canvasSize(renderer.domElement),list=passes(W,H).filter(p=>inside({x,y},p.sc));if(!list.length)return null;
  const base=[camera.left,camera.right,camera.top,camera.bottom] as const;
  // In «Рядом» both copies are under the pointer; the nearest hit wins, as it would in one real scene.
  let best:(Pick&{d:number})|null=null;
  try{
   for(const p of list){
     setCamera(camera,(base[1]-base[0])*(p.zoom??1),p.vp);camera.position.sub(p.shift);camera.updateMatrixWorld();motion?.setView(camera);apply(p.variant);scene.updateMatrixWorld(true);if(!layout)for(const h of hu)h.mesh.computeBoundingSphere();const targets:THREE.Object3D[]=[];scene.traverseVisible(o=>{if(o.userData.semanticKind&&['HU','module','actor','demo-stock'].includes(o.userData.semanticKind)){if(o instanceof THREE.InstancedMesh&&o.userData.demoShift)o.computeBoundingSphere();targets.push(o);}});
    try{
      const ray=new THREE.Raycaster();ray.layers.enable(1);ray.setFromCamera(new THREE.Vector2((x-p.vp.x)/p.vp.w*2-1,-(y-p.vp.y)/p.vp.h*2+1),camera);
     for(const hit of ray.intersectObjects(targets,true)){
      let n:THREE.Object3D|null=hit.object;while(n&&!n.userData.semanticKind)n=n.parent;if(!n)continue;
      const id=hit.instanceId===undefined?n.userData.semanticId:n.userData.semanticIds?.[hit.instanceId];
       if(typeof id==='string'){if(!best||hit.distance<best.d)best={variant:p.variant,kind:n.userData.semanticKind==='demo-stock'?'HU':n.userData.semanticKind,id,d:hit.distance};break;}
     }
    }finally{camera.position.add(p.shift);camera.updateMatrixWorld();}
   }
   return best&&{variant:best.variant,kind:best.kind,id:best.id};
  }finally{[camera.left,camera.right,camera.top,camera.bottom]=base;camera.updateProjectionMatrix();apply('A');if(!layout)for(const h of hu)h.mesh.computeBoundingSphere();}
 }
 return {
  renderPass(renderer:THREE.WebGLRenderer,scene:THREE.Scene,camera:THREE.OrthographicCamera){ctx={renderer,scene,camera};version++;if(scene.background!==sky)scene.background=sky;if(ready)draw();else renderer.render(scene,camera);},
  capture(variant:Variant){if(ctx)capture(variant,ctx.scene);},
  setReady(){
   // Workers stand at their posts in this episode: read head points once and assign each to the zone under it.
   if(ctx&&!spots.length)ctx.scene.traverse(o=>{if(o.userData.semanticKind!=='actor'||typeof o.userData.semanticId!=='string')return;
    const id=o.userData.semanticId,p=new THREE.Box3().setFromObject(o).getCenter(new THREE.Vector3()),top=new THREE.Box3().setFromObject(o).max.y;
    heads.set(id,new THREE.Vector3(p.x,top+.55,p.z));
    const zone=[...zones].find(([,z])=>p.x>=z.min[0]&&p.x<=z.max[0]&&p.z>=z.min[1]&&p.z<=z.max[1])?.[0]??null;spots.push({actor_id:id,zone_id:zone});});
   // Close-ups switch shadows on; compile those shader variants now (behind the loading screen), not mid-zoom.
   if(ctx){const r=ctx.renderer,was=r.shadowMap.enabled;try{r.shadowMap.enabled=true;r.compile(ctx.scene,ctx.camera);}finally{r.shadowMap.enabled=was;}}
   ready=true;draw();},
  workers:variantWorkers,
  setLayoutPlan,installLayoutVariant:setLayoutPlan,
   setInventory,setMotion,
   inventoryBounds:(id:string,v:Variant)=>inventory?.bounds(id,v)??null,
   inventorySnapshot:()=>inventory?.snapshot()??null,
   motionSnapshot:()=>motion?.snapshot()??null,
   shiftSummary:(v:Variant)=>motion?.summary(v,t)??null,
   setShiftPlan:(plan:WarehouseLayoutPlan|null,access:WarehouseLayoutAccessResult|null)=>{motion?.setPlan(plan,access);version++;draw();},
   shiftActor:(id:string)=>motion?.actorInfo(id)??null,
   shiftRoutes:()=>motion?.routeSummary()??null,
  layoutSnapshot:()=>layout?.snapshot()??null,
  layoutBounds:(kind:'HU'|'module'|'actor',id:string,v:Variant='B')=>v==='B'?layout?.bounds(kind,id)??null:null,
  /** Camera framing for a zone floor, for 'take me there' from the state list. */
  zoneFocus(id:string,v:Variant='A'){const source=zones.get(id),planned=v==='B'?layout?.zones.get(id)?.floor_bounds_xz_m:undefined;const z=planned??source;if(!z)return null;const w=z.max[0]-z.min[0],d=z.max[1]-z.min[1],o=mode==='side'&&v==='B'?SIDE_SHIFT[2]:0;return {target:[(z.min[0]+z.max[0])/2,0,(z.min[1]+z.max[1])/2+o] as XYZ,span:Math.min(184,Math.max(24,Math.max(w,d)*1.2+8))};},
  stats:()=>({...stats,totals:{...totals},pixelRatio:ctx?.renderer.getPixelRatio()??0,shadows:ctx?.renderer.shadowMap.enabled??false}),
  actorPosition:(id:string,v:Variant='A')=>variantHead(id,v)?.toArray() as XYZ|undefined,
  setEffects(next:Effects,nextBudget:number){effects=next;motion?.setEffects(next);budget=Math.min(BUDGET_MAX,nextBudget);draw();},
  setSelectedActor(id:string|null){selectedActor=id;draw();},
  onBubble(fn:(id:string,v:Variant)=>void){onBubble=fn;},
  onLabel(fn:(v:Variant)=>void){onLabel=fn;},
  /** Where a variant's copy of the warehouse stands in the shared space (only «Рядом» shifts B). */
  offsetOf:(v:Variant):XYZ=>mode==='side'&&v==='B'?[...SIDE_SHIFT]:[0,0,0],
  setMoves,draw,pick,ground,
  setMode(next:Mode){mode=next;draw();},
  setInset(px:number){if(px===inset)return;inset=px;draw();},
  setInsetLeft(px:number){if(px===insetLeft)return;insetLeft=px;draw();},
  region:()=>ctx?region(...canvasSize(ctx.renderer.domElement)):null,
  setSplit(next:number){split=Math.min(.92,Math.max(.08,next));draw();},
  setTime(next:number){t=next;draw();},
  setSelected(id:string|null){selected=id;draw();},
  /** Marks a picked object that is neither a moved unit nor a worker, per copy (null clears). */
  setFocus(f:Partial<Record<Variant,Pose>>|null){focus=f;draw();},
  highlightZone,setGateTags,
   dispose(){clearTimeout(sharpenTimer);cancelAnimationFrame(deferredDraw);clearMoveArcs();motion?.dispose();motion=undefined;inventory?.dispose();inventory=undefined;for(const[node,mask]of motionLights)node.layers.mask=mask;motionLights.clear();layout?.dispose();layout=undefined;for(const g of zoneEdgesB.values())g.dispose();zoneEdgesB.clear();for(const[id,z]of zones)if(zoneEdgesA.has(id))z.edge.geometry=zoneEdgesA.get(id)!;disposed=true;sizeObs?.disconnect();cancelAnimationFrame(pending);cancelAnimationFrame(frameReset);for(const c of [...caches,...turnCaches]){c.rt.depthTexture?.dispose();c.rt.dispose();}caches.length=0;turnCaches.length=0;for(const x of owned)x.dispose();sky.dispose();overlay.clear();layer.replaceChildren();if(ctx)apply('A');},
 };
}
