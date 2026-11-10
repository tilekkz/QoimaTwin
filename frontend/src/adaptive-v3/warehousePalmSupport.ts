import * as THREE from 'three';
import type {XYZ} from './warehouseTypes';

type Side='L'|'R';
type Pad='lower'|'upper';
export type WarehousePalmSupportPatch={
 readonly area_m2:number;
 readonly coverage_ratio:number;
 readonly centroid_hu_m:XYZ|null;
 readonly maximum_plane_gap_m:number;
};
export type WarehousePalmSupportRow={
 readonly side:Side;
 readonly lower:WarehousePalmSupportPatch;
 readonly upper:WarehousePalmSupportPatch;
 readonly lower_centroid_z_offset_m:number|null;
};
type NativePad={triangles:THREE.Triangle[];area:number};
type NativeHand={side:Side;hand:THREE.Object3D;lower:NativePad;upper:NativePad};
const EPS=2e-6;
const SCOPE='Current native lower/upper pad triangles projected onto nominal whole-HU side rectangles X=±.16,Y=[0,.24],Z=[-.12,.12]; actual cargo-triangle clearance/contact checked independently.';

function clip(poly:THREE.Vector3[],axis:'y'|'z',bound:number,greater:boolean){
 const out:THREE.Vector3[]=[];
 for(let i=0;i<poly.length;i++){
  const a=poly[i],b=poly[(i+1)%poly.length],da=greater?a[axis]-bound:bound-a[axis],db=greater?b[axis]-bound:bound-b[axis];
  if(da>=0)out.push(a);
  if((da>=0)!==(db>=0))out.push(a.clone().lerp(b,da/(da-db)));
 }
 return out;
}

/** Cache source hand-local faces once. Neither construction nor sampling updates actor matrices/TRS. */
export function createWarehousePalmSupport(actorRoot:THREE.Object3D){
 const hands:NativeHand[]=(['L','R'] as const).map(side=>{
  const hand=actorRoot.getObjectByName('joint__hand_'+side);
  if(!hand)throw new Error('NATIVE_PALM_SUPPORT_HAND_REQUIRED');
  const pads:Record<Pad,NativePad>={lower:{triangles:[],area:0},upper:{triangles:[],area:0}};
  hand.traverse(node=>{
   if(!(node instanceof THREE.Mesh)||node.userData.roleBadge)return;
   const chain:THREE.Object3D[]=[];for(let n:THREE.Object3D|null=node;n&&n!==hand;n=n.parent)chain.unshift(n);
   const toHand=new THREE.Matrix4();
   for(const n of chain)toHand.multiply(new THREE.Matrix4().compose(n.position,n.quaternion,n.scale));
   const position=node.geometry.getAttribute('position'),indices=node.geometry.index;
   if(!position)return;
   for(let i=0;i<(indices?.count??position.count);i+=3){
    const points=[0,1,2].map(j=>new THREE.Vector3().fromBufferAttribute(position,indices?indices.getX(i+j):i+j).applyMatrix4(toHand));
    if(!points.every(p=>Math.abs(p.z-.06)<=EPS))continue;
    const triangle=new THREE.Triangle(points[0],points[1],points[2]);
    if(triangle.getNormal(new THREE.Vector3()).z<.99999)continue;
    const kind:Pad|null=points.every(p=>p.y<-.07)?'lower':points.every(p=>p.y>=-.07)?'upper':null;
    if(kind){pads[kind].triangles.push(triangle);pads[kind].area+=triangle.getArea();}
   }
  });
  if(!(pads.lower.area>1e-8&&pads.upper.area>1e-8))throw new Error('NATIVE_LOWER_AND_UPPER_PALM_FACES_REQUIRED');
  return {side,hand,...pads};
 });

 function sample(cargoRootWorld:THREE.Matrix4):WarehousePalmSupportRow[]{
  if(!cargoRootWorld?.isMatrix4||!cargoRootWorld.elements.every(Number.isFinite)||Math.abs(cargoRootWorld.determinant())<1e-12)
   throw new TypeError('FINITE_INVERTIBLE_PALM_SUPPORT_CARGO_FRAME_REQUIRED');
  const inverseCargo=cargoRootWorld.clone().invert();
  return hands.map(({side,hand,lower,upper})=>{
   if(!hand.matrixWorld.elements.every(Number.isFinite))throw new TypeError('FINITE_PALM_SUPPORT_HAND_FRAME_REQUIRED');
   const toHU=new THREE.Matrix4().multiplyMatrices(inverseCargo,hand.matrixWorld),plane=side==='L'?-.16:.16;
   function support(pad:NativePad):WarehousePalmSupportPatch{
    let area_m2=0,maximum_plane_gap_m=0,weightedY=0,weightedZ=0;
    for(const triangle of pad.triangles){
     let poly=[triangle.a,triangle.b,triangle.c].map(p=>p.clone().applyMatrix4(toHU));
     maximum_plane_gap_m=Math.max(maximum_plane_gap_m,...poly.map(p=>Math.abs(p.x-plane)));
     for(const[axis,bound,greater]of [['y',0,true],['y',.24,false],['z',-.12,true],['z',.12,false]] as const){if(!poly.length)break;poly=clip(poly,axis,bound,greater);}
     for(let i=1;i+1<poly.length;i++){
      const a=poly[0],b=poly[i],c=poly[i+1],area=Math.abs((b.y-a.y)*(c.z-a.z)-(b.z-a.z)*(c.y-a.y))*.5;
      area_m2+=area;weightedY+=area*(a.y+b.y+c.y)/3;weightedZ+=area*(a.z+b.z+c.z)/3;
     }
    }
    return {area_m2,coverage_ratio:area_m2/pad.area,centroid_hu_m:area_m2>1e-15?[plane,weightedY/area_m2,weightedZ/area_m2]:null,maximum_plane_gap_m};
   }
   const lowerSupport=support(lower),upperSupport=support(upper);
   return {side,lower:lowerSupport,upper:upperSupport,lower_centroid_z_offset_m:lowerSupport.centroid_hu_m?.[2]??null};
  });
 }
 return Object.freeze({sample,scope:SCOPE});
}
