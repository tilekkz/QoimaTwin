/**
 * Plan card: both warehouses from above (north up, A on top, B below, where B stands in «Рядом»), zones tinted by
 * their state, and the ground footprint of the current view. It is a way to get somewhere, not a second view:
 * hovering names the zone, a click flies close to that zone (or close to the clicked aisle point) in that copy.
 */
import type {XYZ} from '../warehouseTypes';
import {STATE_COLOR,STATE_RU} from './twinRender';
import type {AtmoState,Variant} from './twinScenario';

type Rect2={min:[number,number];max:[number,number]};
export type MiniData={size:[number,number];shiftZ:number;zones:(Rect2&{id:string;label:string})[];modules:Rect2[]};
export type MiniFrame={shared:boolean;quad:[number,number][]|null;states:Record<Variant,Record<string,AtmoState>>};
type Hit={v:Variant;p:XYZ;zone:string|null};

const PAD=4,HINT='Наведите на участок · клик — подлететь';
export function createMinimap(canvas:HTMLCanvasElement,caption:HTMLElement,d:MiniData,o:{zone:(z:Rect2,v:Variant)=>void;point:(p:XYZ,v:Variant)=>void;hover:(z:Rect2|null,v:Variant)=>void}){
 const [WX,WZ]=d.size,gap=(d.shiftZ-WZ)/2,ext={x:[-PAD,WX+PAD],z:[-PAD,d.shiftZ+WZ+PAD]};
 const ctx=canvas.getContext('2d')!;let k=1,last:MiniFrame|null=null,hover:Hit|null=null;
 const toPx=(x:number,z:number):[number,number]=>[(x-ext.x[0])*k,(z-ext.z[0])*k];
 /** Pointer → which copy, the point in that copy's own coordinates, and the zone there (aisles have none). */
 function hitAt(e:PointerEvent):Hit|null{
  const r=canvas.getBoundingClientRect(),x=(e.clientX-r.left)/k+ext.x[0],zw=(e.clientY-r.top)/k+ext.z[0];
  const v:Variant=zw>WZ+gap?'B':'A',z=v==='B'?zw-d.shiftZ:zw;if(x<0||x>WX||z<0||z>WZ)return null;
  const zone=d.zones.find(q=>x>=q.min[0]&&x<=q.max[0]&&z>=q.min[1]&&z<=q.max[1])?.id??null;
  return {v,p:[x,0,z],zone};
 }
 function draw(f:MiniFrame|null=last){
  if(!f)return;last=f;
  const w=canvas.clientWidth;if(!w)return;k=w/(ext.x[1]-ext.x[0]);const h=Math.round((ext.z[1]-ext.z[0])*k),dpr=devicePixelRatio||1;
  if(canvas.height!==Math.round(h*dpr)||canvas.width!==Math.round(w*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);canvas.style.height=h+'px';}
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
  for(const [v,dz] of [['A',0],['B',d.shiftZ]] as const){
   const rect=(b:Rect2,inset=0)=>{const [x0,y0]=toPx(b.min[0],b.min[1]+dz),[x1,y1]=toPx(b.max[0],b.max[1]+dz);return [x0+inset,y0+inset,x1-x0-2*inset,y1-y0-2*inset] as const;};
   ctx.fillStyle='rgba(255,255,255,.92)';ctx.strokeStyle='rgba(20,40,36,.3)';ctx.lineWidth=1;
   ctx.beginPath();ctx.roundRect(...rect({min:[0,0],max:[WX,WZ]}),4);ctx.fill();ctx.stroke();
   for(const z of d.zones){
    // Zones outside the demo episode have no state: drawn neutral, never as «in control».
    const s=f.states[v][z.id],on=hover?.v===v&&hover.zone===z.id;
    ctx.fillStyle=s?STATE_COLOR[s]+(on?'66':s==='control'?'1c':'9a'):on?'rgba(14,95,87,.18)':'rgba(30,50,46,.05)';ctx.beginPath();ctx.roundRect(...rect(z,.6),2);ctx.fill();
    if(on||(s&&s!=='control')){ctx.strokeStyle=on?'#0E5F57':STATE_COLOR[s];ctx.lineWidth=on?1.6:1;ctx.stroke();}
   }
   ctx.fillStyle='rgba(30,50,46,.2)';for(const m of d.modules)ctx.fillRect(...rect(m));
   const [lx,ly]=toPx(2,dz+2);ctx.fillStyle='#0E5F57';ctx.font='700 10px system-ui,sans-serif';ctx.textBaseline='top';ctx.fillText(v,lx,ly);
  }
  if(f.quad)for(const dz of f.shared?[0,d.shiftZ]:[0]){
   // In «Шторка» each copy shows the same frame; keep it inside that copy's half of the map.
   ctx.save();if(f.shared){const [,y0]=toPx(0,dz-gap),[,y1]=toPx(0,dz+WZ+gap);ctx.beginPath();ctx.rect(0,y0,w,y1-y0);ctx.clip();}
   ctx.beginPath();f.quad.forEach(([x,z],i)=>{const [px,py]=toPx(x,z+dz);if(i)ctx.lineTo(px,py);else ctx.moveTo(px,py);});ctx.closePath();
   ctx.fillStyle='rgba(14,128,118,.1)';ctx.fill();ctx.setLineDash([3,2]);ctx.strokeStyle='#0E8076';ctx.lineWidth=1.4;ctx.stroke();ctx.restore();
  }
 }
 function setHover(h:Hit|null){
  if(h?.v===hover?.v&&h?.zone===hover?.zone){hover=h;return;}hover=h;draw();
  const z=h?.zone?d.zones.find(q=>q.id===h.zone):null,s=z&&last?last.states[h!.v][z.id]:null;o.hover(z??null,h?.v??'A');
  caption.innerHTML=z?`<b>${h!.v}</b><span>${z.label}</span>${s?`<i data-s="${s}">${STATE_RU[s]}</i>`:''}`:h?`<b>${h.v}</b>Проход`:HINT;
  canvas.style.cursor=h?'pointer':'default';
 }
 caption.textContent=HINT;
 canvas.addEventListener('pointermove',e=>{if(e.pointerType==='mouse')setHover(hitAt(e));});
 canvas.addEventListener('pointerleave',()=>setHover(null));
 canvas.addEventListener('click',e=>{const h=hitAt(e as PointerEvent);if(!h)return;const z=h.zone&&d.zones.find(q=>q.id===h.zone);if(z)o.zone(z,h.v);else o.point(h.p,h.v);});
 return {draw};
}
