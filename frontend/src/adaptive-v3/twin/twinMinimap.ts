/**
 * Plan card: both warehouses from above (north up, A on top, B below, where B stands in «Рядом»), zones tinted by
 * their state, and the ground footprint of the current view. It is a way to get somewhere, not a second view:
 * hovering names the zone, a click flies close to that zone (or close to the clicked aisle point) in that copy.
 */
import type {XYZ} from '../warehouseTypes';
import type {TwinLayoutPlan} from './twinLayoutVariant';
import {STATE_COLOR,STATE_RU} from './twinRender';
import type {AtmoState,Variant} from './twinScenario';

type Rect2={min:[number,number];max:[number,number]};
export type MiniData={size:[number,number];shiftZ:number;zones:(Rect2&{id:string;label:string})[];modules:(Rect2&{id?:string})[];zonesB?:(Rect2&{id:string;label:string})[];modulesB?:Rect2[]};
export type MiniFrame={shared:boolean;quad:[number,number][]|null;states:Record<Variant,Record<string,AtmoState>>};
type Hit={v:Variant;p:XYZ;zone:string|null};

const PAD=4,HINT=matchMedia('(hover: hover)').matches?'Наведите на участок · клик — подлететь':'Нажмите на участок, чтобы подлететь';
export function createMinimap(canvas:HTMLCanvasElement,caption:HTMLElement,d:MiniData,o:{zone:(z:Rect2,v:Variant)=>void;point:(p:XYZ,v:Variant)=>void;hover:(z:Rect2|null,v:Variant)=>void}){
 const [WX,WZ]=d.size,gap=(d.shiftZ-WZ)/2,ext={x:[-PAD,WX+PAD],z:[-PAD,d.shiftZ+WZ+PAD]};
 const ctx=canvas.getContext('2d')!;let k=1,last:MiniFrame|null=null,hover:Hit|null=null,layoutPlan:TwinLayoutPlan|null=null;
 const zonesFor=(v:Variant)=>{if(v==='A')return d.zones;if(!layoutPlan)return d.zonesB??d.zones;const map=new Map(d.zones.map(z=>[z.id,z]));for(const z of layoutPlan.zones)map.set(z.zone_id,{id:z.zone_id,label:map.get(z.zone_id)?.label??z.zone_id,...z.floor_bounds_xz_m});return [...map.values()];};
 // In B the modules that the layout adds or moves carry the same colours as in 3D (teal new, violet moved).
 const aById=new Map(d.modules.filter(m=>m.id).map(m=>[m.id!,m]));
 const modulesFor=(v:Variant):(Rect2&{mark?:'new'|'moved'})[]=>v==='B'&&layoutPlan?layoutPlan.modules.map(m=>{const r:Rect2={min:[m.outer_bounds_world.min[0],m.outer_bounds_world.min[2]],max:[m.outer_bounds_world.max[0],m.outer_bounds_world.max[2]]},a=aById.get(m.module_id),moved=!!a&&[0,1].some(i=>Math.abs(a.min[i]-r.min[i])>1e-6||Math.abs(a.max[i]-r.max[i])>1e-6);return {...r,mark:m.is_new?'new':moved?'moved':undefined};}):v==='B'?(d.modulesB??d.modules):d.modules;
 const toPx=(x:number,z:number):[number,number]=>[(x-ext.x[0])*k,(z-ext.z[0])*k];
 /** Pointer → which copy, the point in that copy's own coordinates, and the zone there (aisles have none). */
 function hitAt(e:PointerEvent):Hit|null{
  const r=canvas.getBoundingClientRect(),x=(e.clientX-r.left)/k+ext.x[0],zw=(e.clientY-r.top)/k+ext.z[0];
  const v:Variant=zw>WZ+gap?'B':'A',z=v==='B'?zw-d.shiftZ:zw;if(x<0||x>WX||z<0||z>WZ)return null;
  const zone=zonesFor(v).find(q=>x>=q.min[0]&&x<=q.max[0]&&z>=q.min[1]&&z<=q.max[1])?.id??null;
  return {v,p:[x,0,z],zone};
 }
 const rectIn=(b:Rect2,dz:number,inset=0)=>{const [x0,y0]=toPx(b.min[0],b.min[1]+dz),[x1,y1]=toPx(b.max[0],b.max[1]+dz);return [x0+inset,y0+inset,x1-x0-2*inset,y1-y0-2*inset] as const;};
 // The plan itself (footprints, zone tints, 264 module outlines) changes only with zone states or size, while the
 // view frame moves with every camera frame: draw the plan once into a cached layer and only blit it per frame.
 const base=document.createElement('canvas'),bctx=base.getContext('2d')!;let baseKey='';
 function drawBase(f:MiniFrame,w:number,h:number,dpr:number){
  const key=`${w}x${h}@${dpr}|${layoutPlan?.plan_sha256??'source'}|${JSON.stringify(f.states)}`;if(key===baseKey)return;baseKey=key;
  base.width=canvas.width;base.height=canvas.height;bctx.setTransform(dpr,0,0,dpr,0,0);bctx.clearRect(0,0,w,h);
  for(const [v,dz] of [['A',0],['B',d.shiftZ]] as const){
   bctx.fillStyle='rgba(255,255,255,.92)';bctx.strokeStyle='rgba(20,40,36,.3)';bctx.lineWidth=1;
   bctx.beginPath();bctx.roundRect(...rectIn({min:[0,0],max:[WX,WZ]},dz),4);bctx.fill();bctx.stroke();
   for(const z of zonesFor(v)){
    // Zones outside the demo episode have no state: drawn neutral, never as «in control».
    const s=f.states[v][z.id];
    bctx.fillStyle=s?STATE_COLOR[s]+(s==='control'?'1c':'9a'):'rgba(30,50,46,.05)';bctx.beginPath();bctx.roundRect(...rectIn(z,dz,.6),2);bctx.fill();
    if(s&&s!=='control'){bctx.strokeStyle=STATE_COLOR[s];bctx.lineWidth=1;bctx.stroke();}
   }
   for(const m of modulesFor(v)){bctx.fillStyle=m.mark==='new'?'rgba(14,128,118,.8)':m.mark==='moved'?'rgba(91,111,216,.75)':'rgba(30,50,46,.2)';bctx.fillRect(...rectIn(m,dz));}
   const [lx,ly]=toPx(2,dz+2);bctx.fillStyle='#0E5F57';bctx.font='700 10px system-ui,sans-serif';bctx.textBaseline='top';bctx.fillText(v,lx,ly);
  }
 }
 function draw(f:MiniFrame|null=last){
  if(!f)return;last=f;
  const w=canvas.clientWidth;if(!w)return;k=w/(ext.x[1]-ext.x[0]);const h=Math.round((ext.z[1]-ext.z[0])*k),dpr=devicePixelRatio||1;
  if(canvas.height!==Math.round(h*dpr)||canvas.width!==Math.round(w*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);canvas.style.height=h+'px';baseKey='';}
  drawBase(f,w,h,dpr);
  ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(base,0,0);ctx.setTransform(dpr,0,0,dpr,0,0);
  if(hover?.zone){const z=zonesFor(hover.v).find(q=>q.id===hover!.zone);if(z){ctx.beginPath();ctx.roundRect(...rectIn(z,hover.v==='B'?d.shiftZ:0,.6),2);ctx.fillStyle='rgba(14,95,87,.16)';ctx.fill();ctx.strokeStyle='#0E5F57';ctx.lineWidth=1.6;ctx.stroke();}}
  if(f.quad)for(const dz of f.shared?[0,d.shiftZ]:[0]){
   // In «Шторка» each copy shows the same frame; keep it inside that copy's half of the map.
   ctx.save();if(f.shared){const [,y0]=toPx(0,dz-gap),[,y1]=toPx(0,dz+WZ+gap);ctx.beginPath();ctx.rect(0,y0,w,y1-y0);ctx.clip();}
   ctx.beginPath();f.quad.forEach(([x,z],i)=>{const [px,py]=toPx(x,z+dz);if(i)ctx.lineTo(px,py);else ctx.moveTo(px,py);});ctx.closePath();
   ctx.fillStyle='rgba(14,128,118,.1)';ctx.fill();ctx.setLineDash([3,2]);ctx.strokeStyle='#0E8076';ctx.lineWidth=1.4;ctx.stroke();ctx.restore();
  }
 }
 function setHover(h:Hit|null){
  if(h?.v===hover?.v&&h?.zone===hover?.zone){hover=h;return;}hover=h;draw();
  const z=h?.zone?zonesFor(h.v).find(q=>q.id===h.zone):null,s=z&&last?last.states[h!.v][z.id]:null;o.hover(z??null,h?.v??'A');
  caption.innerHTML=z?`<b>${h!.v}</b><span>${z.label}</span>${s?`<i data-s="${s}">${STATE_RU[s]}</i>`:''}`:h?`<b>${h.v}</b>Проход`:HINT;
  canvas.style.cursor=h?'pointer':'default';
 }
 caption.textContent=HINT;
 canvas.addEventListener('pointermove',e=>{if(e.pointerType==='mouse')setHover(hitAt(e));});
 canvas.addEventListener('pointerleave',()=>setHover(null));
 canvas.addEventListener('click',e=>{const h=hitAt(e as PointerEvent);if(!h)return;const z=h.zone&&zonesFor(h.v).find(q=>q.id===h.zone);if(z)o.zone(z,h.v);else o.point(h.p,h.v);});
 return {draw,setLayoutPlan(plan:TwinLayoutPlan|null){layoutPlan=plan?structuredClone(plan):null;baseKey='';hover=null;draw();},layoutSnapshot:()=>({candidate_id:layoutPlan?.candidate_id??null,modules_A:d.modules.length,modules_B:modulesFor('B').length,zones_B:zonesFor('B').length})};
}
