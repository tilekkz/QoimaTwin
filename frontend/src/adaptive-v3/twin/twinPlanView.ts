import type {XYZ} from '../warehouseTypes';

export const PLAN_DIR:XYZ=[0,1,0];
/** Floor+wall envelope in the existing shared world; this changes framing only. */
export function fittedWarehouseSpan(side:boolean,width:number,height:number,dir:XYZ,minimum=160){
 // Floating page controls occupy the lower edge; fit inside the usable height.
 const usableHeight=Math.max(1,height-Math.min(128,height*.16));
 const aspect=Math.max(1,width)/usableHeight,depth=side?78:36;
 const [x,y,z]=dir,n=Math.hypot(x,y,z),h=Math.hypot(x,z);
 if(!(n>0))return minimum;
 const right=h>1e-10?[z/h,0,-x/h]:[1,0,0];
 const up=h>1e-10?[-y*x/(n*h),h/n,-y*z/(n*h)]:[0,0,-1];
 const halfWidth=Math.abs(right[0])*72+Math.abs(right[2])*depth;
 const halfHeight=Math.abs(up[0])*72+Math.abs(up[2])*depth+Math.abs(up[1])*6.5;
 return Math.max(minimum,2*(halfWidth+8),2*(halfHeight+8)*aspect);
}

export function createTopPlanControl(o:{button:HTMLButtonElement;side:()=>boolean;size:()=>{w:number;h:number};frame:()=>{dir:XYZ}|undefined;fly:(target:XYZ,span:number,dir:XYZ)=>void}){
 const update=()=>{const d=o.frame()?.dir,top=!!d&&d[1]>.999999&&Math.hypot(d[0],d[2])<.001;o.button.setAttribute('aria-pressed',String(top));};
 const show=()=>{const side=o.side(),size=o.size();o.fly([72,1.5,side?78:36],fittedWarehouseSpan(side,size.w,size.h,PLAN_DIR),PLAN_DIR);};
 o.button.addEventListener('click',show);
 return {update,dispose:()=>o.button.removeEventListener('click',show)};
}
