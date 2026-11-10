import * as THREE from 'three';
import {mergeGeometries} from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import {deriveNativeWorkerGaitRig,compileNativeWorkerGait} from '../warehouseWorkerGait';
import {WORKER_ROLE_DEFINITIONS} from '../workerRoles';
import type {WarehouseBundle,XYZ} from '../warehouseTypes';
import type {WarehouseLayoutPlan} from '../warehouseLayoutPlan';
import type {WarehouseLayoutAccessResult} from '../warehouseLayoutAccess';
import type {RoutePolicy} from '../warehouseRouting';
import type {Effects,Variant} from './twinScenario';
import {createTwinShiftGenerator} from './twinShift';
import type {ShiftPose} from './twinShiftRoutes';
import {shiftProblemActive} from './twinShiftProblems';

type Part={mesh:THREE.InstancedMesh;tint:boolean;poses:THREE.Matrix4[];carry:THREE.Matrix4[];work:THREE.Matrix4[];seat:THREE.Matrix4;rest:THREE.Matrix4};
type Batch={mesh:THREE.InstancedMesh;count:number;native:boolean};
const ONE=new THREE.Vector3(1,1,1);
const CART_SIDES=[-.28,.28],CART_AXLES=[0,.66],WHEEL_SIDES=[-.54,.54],WHEEL_AXLES=[-.73,.35],MAST_SIDES=[-.48,.48],TRUCK_SIDES=[-1.17,1.17],TRUCK_AXLES=[-2.9,-1.7,2.8];
/** Instanced native people, shared low-poly equipment and no extra lights/shadows.
 * All dynamic buffers live on layer 1, outside the warehouse's static depth cache. */
export function createTwinShiftScene(scene:THREE.Scene,bundle:WarehouseBundle,policy:RoutePolicy,plan:WarehouseLayoutPlan|null,access:WarehouseLayoutAccessResult|null){
 let generator=createTwinShiftGenerator(bundle,policy,plan,access),at=0,variant:Variant='A',disposed=false,effects:Effects='full',detail=true,viewReady=false,clipPadX=0,clipPadY=0;
 const root=new THREE.Group();root.name='twin_seeded_demo_shift';root.userData.demoShift=true;
 const owned:(THREE.BufferGeometry|THREE.Material)[]=[],batches:Batch[]=[],parts:Part[]=[],saved:{node:THREE.Object3D;visible:boolean}[]=[];
 const own=<T extends THREE.BufferGeometry|THREE.Material>(r:T)=>{owned.push(r);return r;};
 const temp=new THREE.Object3D(),matrix=new THREE.Matrix4(),partMatrix=new THREE.Matrix4(),color=new THREE.Color(),workerMatrices=generator.actors.map(()=>new THREE.Matrix4());
 const viewMatrix=new THREE.Matrix4(),viewPoint=new THREE.Vector3(),nativeVisibleIds:string[]=[],farVisibleIds:string[]=[];
 function setView(camera:THREE.OrthographicCamera){viewMatrix.multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse);clipPadX=6*camera.zoom/(camera.right-camera.left);clipPadY=6*camera.zoom/(camera.top-camera.bottom);viewReady=true;}
 function inView(p:ShiftPose){if(!viewReady)return true;viewPoint.set(p.x,p.y+1,p.z).applyMatrix4(viewMatrix);return Math.abs(viewPoint.x)<=1+clipPadX&&Math.abs(viewPoint.y)<=1+clipPadY;}
 function batch(geometry:THREE.BufferGeometry,material:THREE.Material,capacity:number){
  const mesh=new THREE.InstancedMesh(geometry,material,capacity);mesh.name='demo_shift_batch';mesh.frustumCulled=false;mesh.layers.set(1);mesh.userData.demoShift=true;mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);root.add(mesh);const b={mesh,count:0,native:false};batches.push(b);return b;
 }
 const material=(c:string)=>own(new THREE.MeshStandardMaterial({color:c,roughness:.8,metalness:.04}));
 const cube=own(new THREE.BoxGeometry(1,1,1)),dark=material('#263D46'),rubber=material('#263131'),yellow=material('#E5AE32'),wood=material('#B17C46'),carton=material('#BE956A'),teal=material('#207B84');
 const peopleCount=generator.actors.length,vehicleCount=generator.fleet.length;
 const cubeBatches={dark:batch(cube,dark,1000),yellow:batch(cube,yellow,400),wood:batch(cube,wood,1000),carton:batch(cube,carton,1000),teal:batch(cube,teal,500),rubber:batch(cube,rubber,500)};
 const wheelGeometry=own(new THREE.CylinderGeometry(1,1,1,10).rotateZ(Math.PI/2)),wheels=batch(wheelGeometry,rubber,vehicleCount*4+peopleCount*4+36);
 const haloGeometry=own(new THREE.RingGeometry(.45,.64,16).rotateX(-Math.PI/2)),haloMat=own(new THREE.MeshBasicMaterial({color:'#ECAA38',transparent:true,opacity:.85,depthWrite:false})),halos=batch(haloGeometry,haloMat,peopleCount+vehicleCount);
 const extraMat=own(new THREE.MeshBasicMaterial({color:'#0B877D',transparent:true,opacity:.7,depthWrite:false})),extraRings=batch(own(new THREE.RingGeometry(.36,.41,12).rotateX(-Math.PI/2)),extraMat,peopleCount);
 const pulseGeo=own(new THREE.OctahedronGeometry(.2,0)),alerts=batch(pulseGeo,own(new THREE.MeshBasicMaterial({color:'#D64242'})),peopleCount);
 const truckWhite=material('#D5E3E1'),truckBody=batch(cube,truckWhite,portsCount(bundle)*4),truckWheels=batch(wheelGeometry,rubber,portsCount(bundle)*6),aprons=batch(cube,material('#BDCFC5'),portsCount(bundle));
 const gateFrames=bundle.layout.data.ports as {world_pos:XYZ;outward_normal:XYZ}[];
 function portsCount(b:WarehouseBundle){return(b.layout.data.ports as unknown[]).length;}
 function put(b:Batch,base:THREE.Matrix4,x:number,y:number,z:number,sx:number,sy:number,sz:number){
  temp.position.set(x,y,z);temp.rotation.set(0,0,0);temp.scale.set(sx,sy,sz);temp.updateMatrix();matrix.multiplyMatrices(base,temp.matrix);b.mesh.setMatrixAt(b.count++,matrix);
 }
 function pose(p:ShiftPose,out:THREE.Matrix4,x=0,y=0,z=0){temp.position.set(p.x+x,p.y+y,p.z+z);temp.rotation.set(0,p.yaw,0);temp.scale.copy(ONE);temp.updateMatrix();out.copy(temp.matrix);}
 function cargo(base:THREE.Matrix4,pallet:boolean,large=false){
  if(pallet){put(cubeBatches.wood,base,0,.1,0,1.12,.2,.92);put(cubeBatches.carton,base,0,.66,0,large?1.7:.94,.92,.78);put(cubeBatches.wood,base,0,1.13,0,large?1.7:.94,.035,.04);}
  else{put(cubeBatches.teal,base,0,.07,0,.56,.14,.4);put(cubeBatches.carton,base,0,.26,0,.44,.3,.32);}
 }
 function cart(base:THREE.Matrix4,loaded:boolean){
  put(cubeBatches.dark,base,0,.28,.33,.62,.08,.74);for(const x of CART_SIDES){put(cubeBatches.teal,base,x,.67,.33,.035,.8,.72);for(const z of CART_AXLES)put(wheels,base,x,.12,z,.075,.12,.12);}
  put(cubeBatches.teal,base,0,.85,-.02,.6,.04,.04);put(cubeBatches.teal,base,0,.65,.68,.6,.04,.04);
  put(cubeBatches.teal,base,0,.48,.33,.58,.035,.7);if(loaded){put(cubeBatches.carton,base,0,.68,.34,.49,.37,.53);put(cubeBatches.carton,base,.08,.96,.36,.3,.2,.32);}
 }
 function forklift(base:THREE.Matrix4,loaded:boolean){
  put(cubeBatches.yellow,base,0,.62,-.25,1.12,.7,1.45);put(cubeBatches.dark,base,0,.34,-.15,1.04,.22,1.55);
  for(const x of WHEEL_SIDES)for(const z of WHEEL_AXLES)put(wheels,base,x,.27,z,.22,.27,.27);
  put(cubeBatches.dark,base,0,1.12,-.48,.65,.12,.55);put(cubeBatches.dark,base,0,1.38,-.72,.65,.6,.13);
  for(const x of MAST_SIDES){put(cubeBatches.yellow,base,x,1.56,-.6,.055,1.27,.055);put(cubeBatches.yellow,base,x,1.56,.43,.055,1.27,.055);put(cubeBatches.dark,base,x,1.06,.69,.09,1.9,.1);put(cubeBatches.dark,base,x*.65,.2,1.03,.10,.08,.72);}
  put(cubeBatches.yellow,base,0,2.2,-.08,1.08,.08,1.2);put(cubeBatches.dark,base,0,.86,.77,1.03,.12,.12);
  if(loaded){put(cubeBatches.wood,base,0,.32,1.04,1.03,.16,.78);put(cubeBatches.carton,base,0,.84,1.04,.9,.88,.7);put(cubeBatches.teal,base,0,1.28,1.04,.06,.04,.72);}
 }
 // Native body geometry and foot-planted gait are sampled once. Runtime only writes matrices.
 const original:THREE.Object3D[]=[];scene.traverse(n=>{if(n.userData.semanticKind==='actor')original.push(n);});
 const prototype=original.find(n=>n.userData.semanticId==='P01');if(!prototype)throw Error('SHIFT_NATIVE_WORKER_MISSING');
 const clone=prototype.clone(true);clone.position.set(0,0,0);clone.quaternion.identity();clone.scale.set(1,1,1);clone.updateMatrixWorld(true);
 const gait=compileNativeWorkerGait(deriveNativeWorkerGaitRig(prototype),[[0,0,0],[0,0,3]],0,1.2);
 const meshes:THREE.Mesh[]=[];clone.traverse(n=>{if(n instanceof THREE.Mesh&&!n.userData.roleBadge)meshes.push(n);});
 const restJoints=new Map<string,THREE.Quaternion>();clone.traverse(n=>{if(n.name.startsWith('joint__'))restJoints.set(n.name,n.quaternion.clone());});
 const reset=()=>{for(const[name,q]of restJoints)clone.getObjectByName(name)!.quaternion.copy(q);};
 const sampleParts=(out:THREE.Matrix4[])=>{clone.updateMatrixWorld(true);for(let i=0;i<meshes.length;i++)out[i]=meshes[i].matrixWorld.clone();};
 const walks:THREE.Matrix4[][]=[],carries:THREE.Matrix4[][]=[],works:THREE.Matrix4[][]=[],rest:THREE.Matrix4[]=[],seat:THREE.Matrix4[]=[];
 sampleParts(rest);
 const walkPhases=gait.phases.filter(p=>p.kind==='walk_step'),middle=walkPhases[Math.floor(walkPhases.length/2)],next=walkPhases[Math.floor(walkPhases.length/2)+2],from=middle.start_s,to=next.start_s;
 const handlingArms=()=>{for(const side of['L','R']){const arm=clone.getObjectByName('joint__upper_arm_'+side)!,fore=clone.getObjectByName('joint__forearm_'+side)!;arm.quaternion.copy(restJoints.get(arm.name)!);fore.quaternion.copy(restJoints.get(fore.name)!);arm.rotateX(-.5);fore.rotateX(-.5);}};
 for(let k=0;k<24;k++){reset();const p=gait.sample(from+(to-from)*k/24);for(const[name,q]of Object.entries(p.joint_rotations))clone.getObjectByName(name)?.quaternion.fromArray(q);const row:THREE.Matrix4[]=[];sampleParts(row);for(const m of row)m.premultiply(new THREE.Matrix4().makeTranslation(0,-p.body_drop_m,0));walks.push(row);handlingArms();const carry:THREE.Matrix4[]=[];sampleParts(carry);for(const m of carry)m.premultiply(new THREE.Matrix4().makeTranslation(0,-p.body_drop_m,0));carries.push(carry);}
 for(let k=0;k<12;k++){reset();for(const side of['L','R']){const arm=clone.getObjectByName('joint__upper_arm_'+side)??clone.getObjectByName('joint__upperarm_'+side),fore=clone.getObjectByName('joint__forearm_'+side);if(arm)arm.rotateX(-.5-.12*Math.sin(k*Math.PI/6));if(fore)fore.rotateX(-.5);}const row:THREE.Matrix4[]=[];sampleParts(row);works.push(row);}
 reset();for(const side of['L','R']){clone.getObjectByName('joint__thigh_'+side)?.rotateX(-Math.PI/2);clone.getObjectByName('joint__shin_'+side)?.rotateX(Math.PI/2);}sampleParts(seat);
 // Group rest mesh components by source material; instancing retains original geometry.
 for(let i=0;i<meshes.length;i++){
  const source=meshes[i],sourceMat=Array.isArray(source.material)?source.material[0]:source.material;
  const tint=/RoleVest|RoleHeadwear/.test(sourceMat.name),mat=own(sourceMat.clone());if(tint&&(mat instanceof THREE.MeshStandardMaterial))mat.color.set('#ffffff');
  const nativeBatch=batch(source.geometry,mat,peopleCount);nativeBatch.native=true;const inst=nativeBatch.mesh;inst.userData.semanticKind='actor';inst.userData.semanticIds=generator.actors.map(a=>a.id);inst.userData.demoShift=true;
  for(let k=0;k<peopleCount;k++)inst.setColorAt(k,color.set(tint?WORKER_ROLE_DEFINITIONS[generator.actors[k].role].color:'#ffffff'));if(inst.instanceColor)inst.instanceColor.needsUpdate=true;
  parts.push({mesh:inst,tint,poses:walks.map(row=>row[i]),carry:carries.map(row=>row[i]),work:works.map(row=>row[i]),rest:rest[i],seat:seat[i]});
 }
 // A 132-triangle silhouette at overview scale; the original native rig is used
 // close up. Height comes from the native rest bounds, never a world/B coordinate.
 const nativeBounds=new THREE.Box3();for(let i=0;i<meshes.length;i++){const g=meshes[i].geometry;if(!g.boundingBox)g.computeBoundingBox();nativeBounds.union(g.boundingBox!.clone().applyMatrix4(rest[i]));}
 const height=(nativeBounds.max.y-nativeBounds.min.y)/1.7;
 const silhouettes=[
  [0,1.11,0,.42,.52,.25],[0,.78,0,.34,.18,.26],[-.11,.42,0,.13,.56,.15],[.11,.42,0,.13,.56,.15],
  [-.11,.07,.04,.16,.14,.26],[.11,.07,.04,.16,.14,.26],[-.28,1.04,0,.11,.51,.14],[.28,1.04,0,.11,.51,.14],
  [0,1.5,0,.24,.24,.24],[0,1.66,0,.29,.07,.28],[0,1.625,.12,.29,.035,.1],
 ];
 const farParts=silhouettes.map(([x,y,z,w,h,d])=>new THREE.BoxGeometry(w*height,h*height,d*height).translate(x*height,y*height,z*height));
 const merged=mergeGeometries(farParts);
 for(const g of farParts)g.dispose();const far=merged?batch(own(merged),material('#FFFFFF'),peopleCount):null;
 if(far){const standing=generator.actors.filter(a=>a.vehicle===null);far.mesh.userData.semanticKind='actor';far.mesh.userData.semanticIds=standing.map(a=>a.id);for(let i=0;i<standing.length;i++)far.mesh.setColorAt(i,color.set(WORKER_ROLE_DEFINITIONS[standing[i].role].color));}
 // Originals remain intact for inspection/restoration, hidden only while this demo layer is mounted.
 for(const n of original){saved.push({node:n,visible:n.visible});n.visible=false;}
 for(const id of['FL01','FL02']){const n=scene.getObjectByName('vehicle__'+id);if(n){saved.push({node:n,visible:n.visible});n.visible=false;}}
 scene.add(root);root.updateWorldMatrix(true,true);
 const base=new THREE.Matrix4();
 function apply(v:Variant,t:number){
  if(disposed)return;const f=generator.sample(v,t);variant=v;at=t=f.at;for(const b of batches)b.count=0;let nativeIndex=0;nativeVisibleIds.length=0;farVisibleIds.length=0;
  for(let i=0;i<f.workers.length;i++){
   const p=f.workers[i];if(!inView(p))continue;const driver=p.vehicle!==null,m=workerMatrices[i],shift=p.cart?-.48:0;
   pose(p,m,Math.sin(p.yaw)*shift,driver?.4:0,Math.cos(p.yaw)*shift);
   if(driver){const veh=f.vehicles[p.vehicle!];pose(veh,m,0,.27,0);}
   if(far&&!detail&&!driver){far.mesh.setMatrixAt(far.count,m);far.mesh.setColorAt(far.count++,color.set(WORKER_ROLE_DEFINITIONS[p.role].color));farVisibleIds.push(p.id);}
   const frame=Math.floor(p.step*24)%24,workFrame=Math.floor(t*3+i)%12;
   if(detail||!far||driver){for(const part of parts){partMatrix.multiplyMatrices(m,driver?part.seat:p.moving?p.cart||p.loaded?part.carry[frame]:part.poses[frame]:p.working||p.cart?part.work[workFrame]:part.rest);part.mesh.setMatrixAt(nativeIndex,partMatrix);if(part.tint)part.mesh.setColorAt(nativeIndex,color.set(WORKER_ROLE_DEFINITIONS[p.role].color));}nativeVisibleIds.push(p.id);nativeIndex++;}
   if(p.cart){pose(p,base);cart(base,p.loaded);}
   else if(p.loaded&&!driver&&p.role!=='packer'){put(cubeBatches.carton,m,0,1.03,.4,.42,.34,.34);}
   if(p.extra){pose(p,base);put(extraRings,base,0,.025,0,1,1,1);}
   if(p.waiting&&effects!=='off'){pose(p,base);put(halos,base,0,.035,0,1,1,1);if(effects==='full')put(alerts,base,0,2.2,0,1,1,1);}
  }
  for(const part of parts){part.mesh.count=nativeIndex;part.mesh.userData.semanticIds=nativeVisibleIds;part.mesh.instanceMatrix.needsUpdate=true;if(part.tint&&part.mesh.instanceColor)part.mesh.instanceColor.needsUpdate=true;}
  if(far){far.mesh.userData.semanticIds=farVisibleIds;if(far.mesh.instanceColor)far.mesh.instanceColor.needsUpdate=true;}
  for(const p of f.vehicles)if(inView(p)){pose(p,base);forklift(base,p.loaded);}
  for(const p of f.belt)if(p.visible){pose(p,base);cargo(base,false);}
  for(const p of f.staging)if(p.visible){pose(p,base);cargo(base,true,p.kind==='oversize');}
  // The rejected oversize pallet is beside LONG, placed from the plan-derived fleet path.
  if(shiftProblemActive('slot-fit',v,t)){pose(generator.rejectedPallet,base);cargo(base,true,true);if(effects!=='off')put(alerts,base,0,1.7,0,2,2,2);}
  for(const g of gateFrames){const alongX=Math.abs(g.outward_normal[2])>0,tx=alongX?1:0,tz=alongX?0:g.outward_normal[0]>0?1:-1;temp.position.set(g.world_pos[0]+g.outward_normal[0]*5.2+tx*7,-.025,g.world_pos[2]+g.outward_normal[2]*5.2+tz*7);temp.rotation.set(0,0,0);temp.scale.copy(ONE);temp.updateMatrix();base.copy(temp.matrix);put(aprons,base,0,0,0,alongX?22:10,.05,alongX?10:22);}
  for(const p of f.trucks)if(p.visible){pose(p,base);put(truckBody,base,0,1.9,-.8,2.5,2.8,5.8);put(cubeBatches.teal,base,0,1.15,2.9,2.4,1.8,1.5);put(cubeBatches.dark,base,0,1.78,3.45,2.08,.62,.08);for(const x of TRUCK_SIDES)for(const z of TRUCK_AXLES)put(truckWheels,base,x,.5,z,.22,.5,.5);put(cubeBatches.dark,base,0,.6,-.5,2.3,.32,7);}
  for(const b of batches){if(b.native)continue;b.mesh.count=b.count;b.mesh.instanceMatrix.needsUpdate=true;}
  root.updateWorldMatrix(true,false);
 }
 function actorPosition(v:Variant,t:number,id:string):XYZ|undefined{const p=generator.sample(v,t).workers.find(w=>w.id===id);if(!p)return undefined;const offset=p.cart?-.48:0;return[p.x+Math.sin(p.yaw)*offset,p.vehicle!==null?2.45:2.1,p.z+Math.cos(p.yaw)*offset];}
 function workers(v:Variant,t:number){return generator.workers(v,t);}
 function setPlan(next:WarehouseLayoutPlan|null,nextAccess:WarehouseLayoutAccessResult|null){if(disposed)return;const nextGenerator=createTwinShiftGenerator(bundle,policy,next,nextAccess);generator=nextGenerator;apply(variant,at);}
 function snapshot(){return generator.snapshot(at);}
 function dispose(){if(disposed)return;disposed=true;root.removeFromParent();for(const s of saved)s.node.visible=s.visible;for(const b of batches)b.mesh.dispose();for(const o of owned)o.dispose();}
 return {apply,actorPosition,workers,setPlan,snapshot,setView,routeSummary:()=>{let A_m=0,B_m=0,count=0;for(const a of generator.actors)if(a.cart||a.vehicle!==null){A_m+=a.paths.A.length*2;B_m+=a.paths.B.length*2;count++;}return {count,A_m,B_m};},actorInfo:(id:string)=>{const a=generator.actors.find(a=>a.id===id);return a?{id:a.id,role:a.role,extra:a.extra,zone:a.zone,A_m:a.paths.A.length*2,B_m:a.paths.B.length*2,vehicle:a.vehicle===null?null:generator.fleet[a.vehicle].id}:null;},summary:(v:Variant,t:number)=>generator.sample(v,t).summary,carrierFrames:()=>[],dynamicObjects:()=>[root],setEffects:(v:Effects)=>{effects=v;},setDetail:(v:boolean)=>{detail=v;},dispose};
}
export type TwinShiftScene=ReturnType<typeof createTwinShiftScene>;
