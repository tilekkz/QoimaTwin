import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { layout, actors, assignment } from '../contracts';
import { createReplayController } from '../replay/core';
import { createVisualFixture } from '../replay/fixture';
import { adaptRunV2 } from '../replay/adapter';
import { createSfxController } from '../replay/sfx';
import type { ReplayState, VisualFrame } from '../replay/types';
import { createWarehouseMotion } from './warehouseMotion';
import { conveyorVisualPlan } from './conveyorLayout';
import { createWarehouseLabels } from './warehouseLabels';

export const assetCatalog = [
  {id:'standing-worker',label:'Сотрудник',note:'Новые пропорции, лицо и цельный жилет',reference:'v2/standing-worker.png'},
  {id:'picker-worker',label:'Комплектовщик',note:'Поза работы с тележкой',reference:'v2/standing-worker.png'},
  {id:'driver',label:'Водитель',note:'Посадочная поза под сиденье погрузчика',reference:'v2/driver.png'},
  {id:'picking-cart',label:'Тележка',note:'Отдельная тара и четыре поворотные опоры',reference:'picker-cart-reference.png'},
  {id:'rack-high',label:'Стеллаж 5,4 м',note:'Три адресуемых уровня',reference:'v2/tall-rack-reference.png'},
  {id:'conveyor-high',label:'Конвейер',note:'Лента, привод, направляющие и опоры',reference:'v2/conveyor.png'},
  {id:'conveyor-corner',label:'Поворот линии',note:'Соединение транспортных секций',reference:'v2/conveyor.png'},
  {id:'conveyor-diverter',label:'Отвод линии',note:'Узел подачи и распределения',reference:'v2/conveyor.png'},
  {id:'order-tote',label:'Оборотный tote',note:'Полый контейнер с ручками и рёбрами',reference:'v2/order-tote.png'},
  {id:'sealed-parcel',label:'Посылка',note:'Закрытая упаковка после поста',reference:'v2/sealed-parcel.png'},
  {id:'packing-station',label:'Упаковочный пост',note:'Шесть независимых рабочих мест',reference:'packing-station-reference.png'},
  {id:'forklift',label:'Погрузчик',note:'Два автомобиля с водителями',reference:'forklift.png'},
  {id:'dock',label:'Док',note:'Ворота, отбойники и платформа',reference:'v2/large-environment-reference.png'},
  {id:'crate',label:'Складская коробка',note:'Символ партии с конечным остатком',reference:'crate-reference.png'},
  {id:'pallet',label:'Паллета',note:'Настил, девять опор и карманы под вилы',reference:'buffer-pallet.png'},
  {id:'buffer-pallet',label:'Паллетный буфер',note:'Временное размещение грузов',reference:'buffer-pallet.png'},
  {id:'environment-shell',label:'Здание 72 × 48',note:'Модульная архитектура высотой 8 м',reference:'v2/large-environment-reference.png'},
  {id:'rack-low',label:'Стеллаж · LOD',note:'Дальний каркас, три уровня сохранены',reference:'v2/tall-rack-reference.png'},
  {id:'worker-low',label:'Персонал · LOD',note:'Дальний силуэт, высота 1,7 м',reference:'v2/standing-worker.png'},
  {id:'conveyor-low',label:'Линия · LOD',note:'Полный масштаб при низкой детализации',reference:'v2/conveyor.png'},
  {id:'tote-low',label:'Tote · LOD',note:'Полый дальний контейнер',reference:'v2/order-tote.png'},
] as const;
export type AssetId=typeof assetCatalog[number]['id'];
export type ViewId=AssetId|'overview';
export type SceneStatus={mode:ViewId;calls:number;triangles:number;slotCount:number;selected:string;ready:boolean;actors:number;occupied:number;cells:number;quality:string;camera:number[];target:number[];actorPositions:Record<string,number[]>;viewportFootprint:number[][];replay:ReplayState;blocked:boolean;orderStages:Record<string,string>;reducedMotion:boolean;sourceLabel:string;activeLabels:VisualFrame['labels'];audio:ReturnType<ReturnType<typeof createSfxController>['getState']>;warnings:string[]};
type Transform={id:string;position:THREE.Vector3;rotation?:number;scale?:THREE.Vector3;color?:THREE.Color};
type Part={geometry:THREE.BufferGeometry;material:THREE.MeshStandardMaterial};
type Batch={meshes:THREE.InstancedMesh[];set:(values:Transform[])=>void};
type LodGroup={near:Batch;far:Batch;values:Transform[];threshold:number};
const reused=new Set<string>();
const roleColor:Record<string,string>={picker:'#3C6469',packer:'#566e85',receiver:'#926e4c',shipper:'#60705b',forklift_driver:'#ac8034'};

export async function mountWarehouse(host:HTMLElement,onStatus:(value:SceneStatus)=>void){
  if(layout.layout_version!=='qoima-72x48-v2'||layout.schema_version!=='2.0')throw new Error('Требуется layout qoima-72x48-v2');
  const renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'low-power',preserveDrawingBuffer:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.25));renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.2;
  const scene=new THREE.Scene();scene.background=new THREE.Color('#e6e7e0');
  const camera=new THREE.PerspectiveCamera(39,1,.025,450);
  const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.dampingFactor=.12;
  controls.maxPolarAngle=Math.PI/2-.015;controls.maxDistance=240;controls.minDistance=.3;
  scene.add(new THREE.HemisphereLight(0xfff7df,0x74828a,1.9));
  const light=new THREE.DirectionalLight(0xffefd4,2.7);light.position.set(-15,50,-25);light.castShadow=true;scene.add(light);
  light.shadow.mapSize.set(1024,1024);Object.assign(light.shadow.camera,{left:-12,right:12,top:12,bottom:-12,near:.1,far:150});light.shadow.bias=-.0002;light.shadow.normalBias=.025;scene.add(light.target);renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  light.shadow.camera.updateProjectionMatrix();
  const fill=new THREE.DirectionalLight(0xc5ddeb,.9);fill.position.set(60,30,55);scene.add(fill);
  const resources={geometry:new Set<THREE.BufferGeometry>(),material:new Set<THREE.Material>()};
  const templates=new Map<string,THREE.Group>();const partCache=new Map<string,Part[]>();
  const replay=createReplayController(createVisualFixture());
  const audio=createSfxController();
  const preference=matchMedia('(prefers-reduced-motion: reduce)');let reducedMotion=preference.matches;replay.setReducedMotion(reducedMotion);
  let frame=replay.getFrame();let motion:ReturnType<typeof createWarehouseMotion>|undefined;
  let lastTime=performance.now();let previousFollow=new THREE.Vector3();let followInitialized=false;
  const floorLabels=createWarehouseLabels();
  const materialCache=new Map<string,THREE.MeshStandardMaterial>();
  let current=new THREE.Group();let mode:ViewId='overview';let selected='';let quality='low';
  let disposed=false;let raf=0;let tick=0;let lastCamera=new THREE.Vector3(Infinity,0,0);
  let lods:LodGroup[]=[];let pickables:THREE.Object3D[]=[];let following='';let followingOrder='';
  const actorTransforms=new Map<string,Transform>();const logicalPositions=new Map<string,number[]>();
  const dummy=new THREE.Object3D();const black=new THREE.Color('#ffffff');
  const selection=new THREE.Box3Helper(new THREE.Box3(),0xd39a27);selection.visible=false;scene.add(selection);
  const shadowCanvas=document.createElement('canvas');shadowCanvas.width=128;shadowCanvas.height=128;
  const shadowContext=shadowCanvas.getContext('2d')!;
  const gradient=shadowContext.createRadialGradient(64,64,5,64,64,64);
  gradient.addColorStop(0,'rgba(24,36,32,.26)');gradient.addColorStop(.45,'rgba(24,36,32,.13)');gradient.addColorStop(1,'rgba(24,36,32,0)');
  shadowContext.fillStyle=gradient;shadowContext.fillRect(0,0,128,128);
  const shadowTexture=new THREE.CanvasTexture(shadowCanvas);
  const shadowGeometry=new THREE.PlaneGeometry(1,1).rotateX(-Math.PI/2);resources.geometry.add(shadowGeometry);
  const shadowMaterial=new THREE.MeshBasicMaterial({map:shadowTexture,transparent:true,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-1});resources.material.add(shadowMaterial);
  const contactShadows=(values:{position:number[];size:number[]}[])=>{
    const mesh=new THREE.InstancedMesh(shadowGeometry,shadowMaterial,values.length);
    values.forEach((value,index)=>{dummy.position.fromArray(value.position);dummy.rotation.set(0,0,0);dummy.scale.set(value.size[0],1,value.size[1]);dummy.updateMatrix();mesh.setMatrixAt(index,dummy.matrix);});
    mesh.computeBoundingSphere();mesh.renderOrder=1;current.add(mesh);
  };
  const viewportFootprint=()=>{
    camera.updateMatrixWorld();const raycaster=new THREE.Raycaster();const plane=new THREE.Plane(new THREE.Vector3(0,1,0),0);const points:number[][]=[];
    for(const corner of [[-1,-1],[1,-1],[1,1],[-1,1]]){raycaster.setFromCamera(new THREE.Vector2(...corner),camera);const point=raycaster.ray.intersectPlane(plane,new THREE.Vector3());if(!point)return[];points.push(point.toArray());}return points;
  };
  const counts=()=>({racks:layout.racks.length,slots:layout.slots.length,occupied:assignment.initial_lots.length,actors:actors.actors.length,vehicles:actors.vehicles.length,packs:layout.pack_stations.length,conveyorCells:layout.conveyor.total_cell_count,skuCount:Object.keys(assignment.active_assignment).length});
  const state=():SceneStatus=>({mode,calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,slotCount:mode==='overview'?layout.slots.length:0,selected,ready:true,actors:actors.actors.length,occupied:assignment.initial_lots.length,cells:layout.conveyor.total_cell_count,quality,camera:camera.position.toArray(),target:controls.target.toArray(),actorPositions:Object.fromEntries([...actorTransforms].filter(([id])=>frame.actors[id]).map(([id,value])=>[id,value.position.toArray()])),replay:replay.getState(),blocked:frame.line.blocked,orderStages:frame.orderStages,reducedMotion,viewportFootprint:viewportFootprint(),sourceLabel:frame.label,activeLabels:frame.labels,audio:audio.getState(),warnings:frame.warnings});
  const fit=(bounds:THREE.Box3,direction=new THREE.Vector3(1.1,1.25,-1.55))=>{
    const sphere=bounds.getBoundingSphere(new THREE.Sphere());direction.normalize();
    const rotation=new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().lookAt(direction,new THREE.Vector3(),camera.up)).invert();
    const tangent=Math.tan(THREE.MathUtils.degToRad(camera.fov)/2);let distance=sphere.radius;
    for(const x of [bounds.min.x,bounds.max.x])for(const y of [bounds.min.y,bounds.max.y])for(const z of [bounds.min.z,bounds.max.z]){
      const point=new THREE.Vector3(x,y,z).sub(sphere.center).applyQuaternion(rotation);
      distance=Math.max(distance,point.z+Math.abs(point.y)/(tangent*.84),point.z+Math.abs(point.x)/(tangent*camera.aspect*.88));
    }
    controls.target.copy(sphere.center);camera.position.copy(sphere.center).addScaledVector(direction,distance*1.04);
    controls.minDistance=Math.max(.2,sphere.radius*.04);controls.update();lastCamera.set(Infinity,0,0);
  };
  const getParts=(id:string):Part[]=>{
    if(partCache.has(id))return partCache.get(id)!;
    const root=templates.get(id);if(!root)throw new Error(`Нет модели ${id}`);root.updateMatrixWorld(true);
    const groups=new Map<string,{geometry:THREE.BufferGeometry[];material:THREE.MeshStandardMaterial}>();
    root.traverse(object=>{
      if(!(object instanceof THREE.Mesh)||Array.isArray(object.material))return;
      for(let ancestor:THREE.Object3D|null=object;ancestor;ancestor=ancestor.parent)if(ancestor.userData.runtime_default_visible===false)return;
      const mat=object.material as THREE.MeshStandardMaterial;
      const signature=[mat.color.getHex(),mat.roughness,mat.metalness,mat.emissive.getHex()].join(':');
      let material=materialCache.get(signature);if(!material){material=mat;materialCache.set(signature,mat);}
      const group=groups.get(signature)||{geometry:[],material};
      group.geometry.push(object.geometry.clone().applyMatrix4(object.matrixWorld));groups.set(signature,group);
    });
    const parts:Part[]=[];
    for(const group of groups.values()){
      const geometry=mergeGeometries(group.geometry,false);group.geometry.forEach(geo=>geo.dispose());
      if(!geometry)throw new Error(`Несовместимая геометрия ${id}`);resources.geometry.add(geometry);parts.push({geometry,material:group.material});
    }
    partCache.set(id,parts);return parts;
  };
  const createBatch=(name:string,id:string,capacity:number,values:Transform[]=[],kind='asset',role?:string):Batch=>{
    const meshes=getParts(id).map(part=>{
      let material=part.material;
      if(role&&/cloth|shirt|trouser|uniform/i.test(material.name)){
        const key=`role:${role}:${material.uuid}`;let tint=materialCache.get(key);
        if(!tint){tint=material.clone();tint.color.set(roleColor[role]||'#527b74');resources.material.add(tint);materialCache.set(key,tint);}material=tint;
      }
      const mesh=new THREE.InstancedMesh(part.geometry,material,Math.max(capacity,1));
      mesh.castShadow=true;mesh.receiveShadow=true;mesh.name=name;mesh.count=0;mesh.visible=false;mesh.userData.kind=kind;current.add(mesh);pickables.push(mesh);return mesh;
    });
    const batch:Batch={meshes,set(entries){
      for(const mesh of meshes){
        mesh.count=entries.length;mesh.visible=entries.length>0;mesh.userData.ids=entries.map(entry=>entry.id);
        entries.forEach((entry,index)=>{
          dummy.position.copy(entry.position);dummy.rotation.set(0,entry.rotation||0,0);dummy.scale.copy(entry.scale||new THREE.Vector3(1,1,1));dummy.updateMatrix();mesh.setMatrixAt(index,dummy.matrix);
          mesh.setColorAt(index,entry.color||black);
        });
        mesh.instanceMatrix.needsUpdate=true;if(mesh.instanceColor)mesh.instanceColor.needsUpdate=true;
        if(entries.length){mesh.computeBoundingBox();mesh.computeBoundingSphere();}
      }
    }};batch.set(values);return batch;
  };
  const add=(name:string,id:string,values:Transform[],kind='asset',role?:string)=>createBatch(name,id,values.length,values,kind,role);
  const makeLod=(name:string,near:string,far:string,values:Transform[],threshold:number,kind:string)=>{
    lods.push({near:createBatch(`${name}:near`,near,values.length,[],kind),far:createBatch(`${name}:far`,far,values.length,values,kind),values,threshold});
  };
  const transform=(id:string,pos:number[],rotation=0):Transform=>({id,position:new THREE.Vector3().fromArray(pos),rotation});
  const buildOverview=()=>{
    current.add(floorLabels.mesh);
    add('architecture','environment-shell',[transform('ENVIRONMENT',[0,0,0])]);
    contactShadows(layout.racks.map(rack=>({position:[rack.root[0],.008,rack.root[2]],size:[1.35,1.9]})));
    for(let aisle=1;aisle<=12;aisle++){
      const prefix=`R_A${String(aisle).padStart(2,'0')}_`;
      makeLod(`racks:A${aisle}`,'rack-high','rack-low',layout.racks.filter(rack=>rack.rack_id.startsWith(prefix)).map(rack=>transform(rack.rack_id,rack.root,rack.rack_id.endsWith('_R')?Math.PI:0)),18,'rack');
      const ids=new Set(layout.racks.filter(rack=>rack.rack_id.startsWith(prefix)).map(rack=>rack.rack_id));
      const occupied=assignment.initial_lots.filter(lot=>ids.has(layout.slots.find(slot=>slot.slot_id===lot.slot_id)!.rack_id));
      const values=occupied.map(lot=>{const slot=layout.slots.find(slot=>slot.slot_id===lot.slot_id)!;return transform(lot.slot_id,slot.bin_anchor,slot.rack_id.endsWith('_R')?Math.PI:0);});
      makeLod(`lots:A${aisle}`,'crate','__crate-low',values,12,'slot');
    }
    const plan=conveyorVisualPlan();
    makeLod('conveyor:front-zone','conveyor-high','conveyor-low',plan.cells,9,'cell');
    for(const model of ['conveyor-corner','conveyor-diverter'])add('conveyor junctions:'+model,model,plan.junctions.filter(junction=>junction.model===model),'junction');
    add('docks','dock',[transform('RECEIVING_DOCK',[0,0,36],Math.PI/2),transform('SHIPPING_DOCK',[72,0,3],-Math.PI/2)]);
    add('relocation buffer','buffer-pallet',[transform('REL_BUFFER',[66,0,42])]);
    motion=createWarehouseMotion({group:current,templates,camera,selected:()=>selected,roleColors:roleColor,batch:createBatch});
    motion.update(frame,replay.getRun(),reducedMotion);
    for(const [id,value]of motion.positions)actorTransforms.set(id,value);
    for(const actor of Object.values(frame.actors))logicalPositions.set(actor.id,[...actor.pos]);
    // Induction ports are rendered by the actual feed/loop junctions above.
  };
  const updateLod=()=>{
    if(mode!=='overview'||camera.position.distanceToSquared(lastCamera)<.25)return;
    lastCamera.copy(camera.position);
    for(const group of lods){
      const near:Transform[]=[];const far:Transform[]=[];
      for(const value of group.values){
        const chosen=value.id===selected||selected.startsWith(value.id.replace('R_','S_'));
        ((chosen||camera.position.distanceTo(value.position)<group.threshold*(quality==='high'?1.3:1))?near:far).push(value);
      }
      group.near.set(near);group.far.set(far);
    }
  };
  const setMode=(next:ViewId)=>{
    motion?.dispose();motion=undefined;
    current.traverse(object=>{if(object instanceof THREE.InstancedMesh)object.dispose();});
    scene.remove(current);current=new THREE.Group();scene.add(current);mode=next;selected='';following='';followingOrder='';followInitialized=false;selection.visible=false;
    lods=[];pickables=[];actorTransforms.clear();logicalPositions.clear();
    if(next==='overview')buildOverview();else{
      replay.pause();audio.stop();
      add(`stand:${next}`,next,[transform(next,[0,0,0])]);
      if(next!=='environment-shell'){
        const bounds=new THREE.Box3().setFromObject(current);const size=bounds.getSize(new THREE.Vector3());const centre=bounds.getCenter(new THREE.Vector3());
        contactShadows([{position:[centre.x,bounds.min.y+.002,centre.z],size:[Math.max(.65,size.x*1.5),Math.max(.5,size.z*1.5)]}]);
      }
    }
    current.updateMatrixWorld(true);
    const bounds=next==='overview'?new THREE.Box3(new THREE.Vector3(0,0,0),new THREE.Vector3(72,8,48)):new THREE.Box3().setFromObject(current);
    fit(bounds,next==='overview'||next==='environment-shell'?new THREE.Vector3(1.1,1.25,-1.55):new THREE.Vector3(1.15,.7,1.6));
    updateLod();onStatus(state());
  };
  const focusBounds=(id:string,bounds:THREE.Box3)=>{
    selected=id;selection.box.copy(bounds);selection.visible=true;
    // Peripheral work is viewed from the open interior, clear of dock walls
    // and the first storage row. The same angle then follows the moving load.
    const centre=bounds.getCenter(new THREE.Vector3());
    const direction=centre.x<7?new THREE.Vector3(.6,1.15,1.4):centre.x>63?new THREE.Vector3(-1.2,1.15,1.1):new THREE.Vector3(1.5,1,-1.4);
    fit(bounds,direction);updateLod();onStatus(state());
  };
  const focusSlot=(id:string)=>{
    following='';followingOrder='';followInitialized=false;
    const slot=layout.slots.find(item=>item.slot_id===id);if(!slot)return;
    focusBounds(id,new THREE.Box3(new THREE.Vector3().fromArray(slot.bin_anchor).add(new THREE.Vector3(-.55,-.35,-.8)),new THREE.Vector3().fromArray(slot.bin_anchor).add(new THREE.Vector3(.55,.5,.8))));
  };
  const selectActor=(id:string)=>{const actor=actorTransforms.get(id);if(actor){following=id;followingOrder='';followInitialized=false;const bounds=motion?.boundsFor(id)||new THREE.Box3(actor.position.clone().add(new THREE.Vector3(-.65,0,-.5)),actor.position.clone().add(new THREE.Vector3(.65,1.8,1.2)));focusBounds(id,bounds.expandByScalar(.12));}};
  const followOrder=(id?:string)=>{
    const cargo=Object.values(frame.cargo).filter(cargo=>cargo.visible&&cargo.orderIds.length&&cargo.attachment.kind!=='cargo').find(cargo=>!id||cargo.orderIds.includes(id));
    if(cargo){selectActor(cargo.id);followingOrder=id||cargo.orderIds[0];}
  };
  const resolveOrderFollow=()=>{
    if(!followingOrder)return;
    const cargo=Object.values(frame.cargo).find(cargo=>cargo.visible&&cargo.orderIds.includes(followingOrder)&&cargo.attachment.kind!=='cargo');
    if(cargo){following=cargo.id;selected=cargo.id;}
    else{following='';followingOrder='';selected='';selection.visible=false;followInitialized=false;}
  };
  const restoreFollowingAfterSeek=(before?:THREE.Vector3)=>{
    resolveOrderFollow();const target=actorTransforms.get(following);if(!target)return;
    if(before){const delta=target.position.clone().sub(before);camera.position.add(delta);controls.target.add(delta);}
    const bounds=motion?.boundsFor(following);if(bounds){selection.box.copy(bounds.expandByScalar(.08));selection.visible=true;}
    previousFollow.copy(target.position);followInitialized=true;lastCamera.set(Infinity,0,0);
  };
  const flow=()=>{following='';followingOrder='';fit(new THREE.Box3(new THREE.Vector3(7,0,1),new THREE.Vector3(64,3,13)));};
  const docks=(kind='receiving')=>{following='';followingOrder='';fit(kind==='receiving'?new THREE.Box3(new THREE.Vector3(0,0,14),new THREE.Vector3(7,8,46)):new THREE.Box3(new THREE.Vector3(63,0,0),new THREE.Vector3(72,6,12)));};
  const top=()=>{following='';followingOrder='';fit(new THREE.Box3().setFromObject(current),new THREE.Vector3(.001,1,-.001));};
  const inspect=(view:string)=>{
    const directions:Record<string,THREE.Vector3>={front:new THREE.Vector3(0,.05,1),side:new THREE.Vector3(1,.05,0),rear:new THREE.Vector3(0,.05,-1),quarter:new THREE.Vector3(1.15,.7,1.6)};
    fit(new THREE.Box3().setFromObject(current),directions[view]||directions.quarter);
  };
  const pointer=new THREE.Vector2();const ray=new THREE.Raycaster();let down=[0,0];
  const onDown=(event:PointerEvent)=>{down=[event.clientX,event.clientY];};
  const onUp=(event:PointerEvent)=>{
    if(mode!=='overview'||Math.hypot(event.clientX-down[0],event.clientY-down[1])>5)return;
    const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(pointer,camera);
    const hit=ray.intersectObjects(current.children,true).find(hit=>{
      for(let ancestor:THREE.Object3D|null=hit.object;ancestor;ancestor=ancestor.parent)if(!ancestor.visible)return false;
      if(hit.instanceId!==undefined&&hit.object.userData.ids?.[hit.instanceId])return true;
      let object:THREE.Object3D|null=hit.object;while(object){if(object.userData.entityId)return true;object=object.parent;}return false;
    });
    if(!hit)return;
    if(hit.instanceId===undefined){let object:THREE.Object3D|null=hit.object;while(object){if(object.userData.entityId){selectActor(object.userData.entityId);return;}object=object.parent;}return;}
    const id=hit.object.userData.ids[hit.instanceId] as string;
    if(hit.object.userData.kind==='rack'){
      const slot=layout.slots.filter(item=>item.rack_id===id).sort((a,b)=>Math.abs(a.bin_anchor[1]-hit.point.y)-Math.abs(b.bin_anchor[1]-hit.point.y))[0];if(slot)focusSlot(slot.slot_id);
    }else if(hit.object.userData.kind==='slot')focusSlot(id);else if(actorTransforms.has(id))selectActor(id);
    else{following='';followingOrder='';selected=id;selection.visible=false;onStatus(state());}
  };
  const inspectEntity=(id:string)=>{
    const rig=motion?.inspectRig(id);if(rig)return{representation:'rig',...rig};
    for(const object of pickables){
      if(!(object instanceof THREE.InstancedMesh)||!object.visible)continue;
      const index=(object.userData.ids||[]).indexOf(id);if(index<0)continue;
      const matrix=new THREE.Matrix4();object.getMatrixAt(index,matrix);object.updateWorldMatrix(true,false);matrix.premultiply(object.matrixWorld);
      return{representation:'instance',rootWorld:new THREE.Vector3().setFromMatrixPosition(matrix).toArray(),matrixWorld:matrix.toArray()};
    }return undefined;
  };
  const observer=new ResizeObserver(()=>{const rect=host.getBoundingClientRect();if(rect.width&&rect.height){renderer.setSize(rect.width,rect.height);camera.aspect=rect.width/rect.height;camera.updateProjectionMatrix();}});
  const preferenceChanged=()=>{reducedMotion=preference.matches;replay.setReducedMotion(reducedMotion);if(reducedMotion)replay.pause();};preference.addEventListener('change',preferenceChanged);
  const dispose=()=>{disposed=true;audio.dispose();floorLabels.dispose();motion?.dispose();preference.removeEventListener('change',preferenceChanged);cancelAnimationFrame(raf);observer.disconnect();controls.dispose();renderer.domElement.removeEventListener('pointerdown',onDown);renderer.domElement.removeEventListener('pointerup',onUp);resources.geometry.forEach(value=>value.dispose());resources.material.forEach(value=>value.dispose());shadowTexture.dispose();current.traverse(object=>{if(object instanceof THREE.InstancedMesh)object.dispose();});selection.geometry.dispose();(selection.material as THREE.Material).dispose();renderer.dispose();renderer.domElement.remove();};
  try{
    const loader=new GLTFLoader();
    await Promise.all(assetCatalog.map(async asset=>{
      const file=`${import.meta.env.BASE_URL}models/${reused.has(asset.id)?'':'v2/'}${asset.id}.glb`;
      const result=await loader.loadAsync(file);
      if(disposed||!host.isConnected){result.scene.traverse(object=>{if(object instanceof THREE.Mesh){object.geometry.dispose();(Array.isArray(object.material)?object.material:[object.material]).forEach(material=>material.dispose());}});throw new Error('Viewer was closed while loading');}
      templates.set(asset.id,result.scene);
      result.scene.traverse(object=>{if(object instanceof THREE.Mesh){resources.geometry.add(object.geometry);(Array.isArray(object.material)?object.material:[object.material]).forEach(mat=>resources.material.add(mat));}});
      let valid=false;result.scene.traverse(object=>{if(object.userData.asset_id===asset.id&&object.userData.layout_version===layout.layout_version)valid=true;});
      if(!valid)throw new Error(`Модель ${asset.label}: требуется экспорт ${layout.layout_version}`);
    }));
    const scanner=templates.get('packing-station')!.getObjectByName('pivot_scanner')?.clone(true);
    const scannerRoot=new THREE.Group();if(scanner){scannerRoot.add(scanner);scannerRoot.updateMatrixWorld(true);const grip=scannerRoot.getObjectByName('anchor_scanner_grip')?.getWorldPosition(new THREE.Vector3());if(grip)scanner.position.sub(grip);}templates.set('__hand-scanner',scannerRoot);
    const workProp=templates.get('packing-station')!.getObjectByName('pivot_packing_carton')?.clone(true);
    const workRoot=new THREE.Group();if(workProp){workProp.userData.runtime_default_visible=true;workRoot.add(workProp);}templates.set('__packing-wip',workRoot);
    const proxy=new THREE.Group();const material=new THREE.MeshStandardMaterial({color:'#b99561',roughness:.8});
    const geometry=new THREE.BoxGeometry(.55,.45,.65);resources.geometry.add(geometry);resources.material.add(material);proxy.add(new THREE.Mesh(geometry,material));templates.set('__crate-low',proxy);
    host.appendChild(renderer.domElement);renderer.setSize(host.clientWidth,host.clientHeight);camera.aspect=host.clientWidth/host.clientHeight;camera.updateProjectionMatrix();observer.observe(host);
    renderer.domElement.addEventListener('pointerdown',onDown);renderer.domElement.addEventListener('pointerup',onUp);setMode('overview');
    const refresh=()=>{
      frame=replay.getFrame();
      if(mode==='overview'&&motion){
        motion.update(frame,replay.getRun(),reducedMotion);actorTransforms.clear();
        for(const [id,value]of motion.positions)actorTransforms.set(id,value);
        for(const actor of Object.values(frame.actors))logicalPositions.set(actor.id,[...actor.pos]);
      }
    };
    const animate=()=>{
      if(disposed)return;const now=performance.now();const dt=Math.max(0,(now-lastTime)/1000);lastTime=now;
      frame=replay.advance(dt);audio.update(frame,replay.getState());
      if(mode==='overview'&&motion){
        motion.update(frame,replay.getRun(),reducedMotion);actorTransforms.clear();
        for(const [id,value]of motion.positions)actorTransforms.set(id,value);
        for(const actor of Object.values(frame.actors))logicalPositions.set(actor.id,[...actor.pos]);
        resolveOrderFollow();
        const followed=following&&actorTransforms.get(following);
        if(followed){
          if(!reducedMotion){
            if(followInitialized){const delta=followed.position.clone().sub(previousFollow);camera.position.add(delta);controls.target.add(delta);}
            previousFollow.copy(followed.position);followInitialized=true;
          }
        }
        if(selected&&actorTransforms.has(selected)){const bounds=motion.boundsFor(selected);if(bounds){selection.box.copy(bounds.expandByScalar(.08));selection.visible=true;}}
        else if(selected&&frame.cargo[selected]&&!frame.cargo[selected].visible){selection.visible=false;selected='';}

      }
      controls.update();if(tick%4===0)updateLod();
      camera.position.y=Math.max(.15,camera.position.y);controls.target.y=Math.max(.02,controls.target.y);
      if(quality==='high'&&light.target.position.distanceToSquared(controls.target)>9){light.target.position.copy(controls.target);light.position.copy(controls.target).add(new THREE.Vector3(-15,40,-25));}
      renderer.render(scene,camera);if(++tick%12===0)onStatus(state());raf=requestAnimationFrame(animate);
    };animate();
    return{dispose,setMode,audio,inspectEntity,inspectRig:(id:string)=>motion?.inspectRig(id),getPerfState:()=>({calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,memory:renderer.info.memory,pixelRatio:renderer.getPixelRatio(),quality,replay:replay.getState()}),loadRun:(input:unknown)=>{const run=adaptRunV2(input);replay.setRun(run);audio.stop();following='';followingOrder='';followInitialized=false;selected='';selection.visible=false;refresh();onStatus(state());},loadVisualDemo:()=>{replay.setRun(createVisualFixture());audio.stop();following='';followingOrder='';followInitialized=false;selected='';selection.visible=false;refresh();onStatus(state());},replay:{play:()=>replay.play(),pause:()=>{replay.pause();audio.stop();},seek:(time:number)=>{const before=actorTransforms.get(following)?.position.clone();replay.seek(time);audio.update(replay.getFrame(),{...replay.getState(),discontinuity:true});followInitialized=false;refresh();restoreFollowingAfterSeek(before);onStatus(state());},reset:()=>{const before=actorTransforms.get(following)?.position.clone();replay.reset();audio.update(replay.getFrame(),{...replay.getState(),discontinuity:true});followInitialized=false;refresh();restoreFollowingAfterSeek(before);onStatus(state());},setSpeed:(speed:number)=>replay.setSpeed(speed),getState:replay.getState,getFrame:replay.getFrame,getRun:replay.getRun},setReducedMotion:(value:boolean)=>{reducedMotion=value;replay.setReducedMotion(value);refresh();},overview:()=>setMode('overview'),top,focusSlot,flow,docks,selectActor,followOrder,inspect,setQuality:(value:string)=>{quality=value;renderer.setPixelRatio(value==='low'?1:Math.min(devicePixelRatio,1.25));renderer.shadowMap.enabled=value==='high';current.traverse(object=>{if(object instanceof THREE.Mesh){object.castShadow=true;object.receiveShadow=true;}});light.target.position.copy(controls.target);light.position.copy(controls.target).add(new THREE.Vector3(-15,40,-25));lastCamera.set(Infinity,0,0);updateLod();},getState:()=>({...state(),counts:counts(),motion:motion?.getState(),following,followingOrder,distance:camera.position.distanceTo(controls.target),layoutVersion:layout.layout_version,logicalActorPositions:Object.fromEntries(logicalPositions),slotRegistry:Object.fromEntries(layout.slots.map(slot=>[slot.slot_id,{rackId:slot.rack_id,anchor:slot.bin_anchor,level:slot.level}])),renderedRegistry:Object.fromEntries(['actor','rack','slot','cell','vehicle','pack','tote'].map(kind=>[kind,[...new Set([...pickables.filter(object=>object.visible&&object.userData.kind===kind).flatMap(object=>object.userData.ids||[]),...(motion?.visibleEntityIds(kind)||[]),...(kind==='tote'?Object.values(frame.cargo).filter(cargo=>cargo.visible&&cargo.kind==='tote').map(cargo=>cargo.id):[])])]])),conveyorJunctions:conveyorVisualPlan().junctions.map(junction=>({id:junction.id,position:junction.position.toArray(),model:junction.model,rotation:junction.rotation})),memory:renderer.info.memory,instancedMeshes:current.children.filter(object=>object instanceof THREE.InstancedMesh).length})};
  }catch(error){dispose();throw error;}
}
