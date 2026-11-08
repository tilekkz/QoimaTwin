import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/examples/jsm/postprocessing/GTAOPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import {createWorkerRolesFixture, createWorkerInstance, disposeWorkerInstance, applyWorkerRole, type WorkerRole, type WorkerInstance} from './workerRoles';
import {createPickupFixture,validatePickupTimeline} from './forkliftPickup';
import {bindSeatedDriver,validateSeatedDriverPose} from './seatedDriver';
import {bindPickerGrip,validatePickerPushPose} from './motion/grip';
import {createCartWalk,validateCartWalkTimeline} from './motion/cartWalk';
import {createPackerAction,validatePackerTimeline,type PackerMode} from './motion/packer';
import {bindSmallGripper} from './motion/smallGripper';
import {createSmallPickMotion,validateSmallPickTimeline} from './motion/smallPick';
import {createReceiverAction,validateReceiverTimeline,type ReceiverMode} from './motion/receiver';
import {createShipperAction,validateShipperTimeline,type ShipperMode} from './motion/shipper';

type View = 'front' | 'side' | 'rear' | 'quarter' | 'top';
type ReferenceManifest = {references: {reference_id: string; artifact: {path: string}}[]; asset_reference_bindings: Record<string,string>};
const element = <T extends HTMLElement = HTMLElement>(id:string) => document.getElementById(id) as T;
const host = element('canvas-host');
const shell = element('stand');
const modelInput = element<HTMLInputElement>('model-id');
const base = import.meta.env.BASE_URL;
const assetTitles:Record<string,string>={'shipper-workcell-fixture':'Отгрузочный пост · посылка','receiver-workcell-fixture':'Пост приёмки · паллета','worker-small-pick':'Комплектовщик · ручной захват','small-package-gripper':'Ручной захват SMALL','small-gripper-contact-fixture':'Захват SMALL · проверка контакта','packer-workcell-fixture':'Упаковочный пост','floor-markings':'Разметка зон склада','environment-markings-fixture':'Разметка и шесть портов','small-unit':'Первичная упаковка SMALL','small-case-open-partial':'Открытая коробка · 4 упаковки','picker-pick-source-fixture':'Источник отбора и тележка'};
async function initialize(){
const scene = new THREE.Scene();
scene.background = new THREE.Color('#d8dcdb');
const renderer = new THREE.WebGLRenderer({antialias:true,alpha:false});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.04;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
host.append(renderer.domElement);
renderer.domElement.setAttribute('aria-label','Трёхмерная модель; вращение и приближение мышью');
const perspective = new THREE.PerspectiveCamera(32,1,.001,1000);
const orthographic = new THREE.OrthographicCamera(-1,1,1,-1,.001,1000);
let camera: THREE.PerspectiveCamera | THREE.OrthographicCamera = perspective;
const target=new THREE.WebGLRenderTarget(1,1,{type:THREE.HalfFloatType,samples:4});
const composer=new EffectComposer(renderer,target);
const beauty=new RenderPass(scene,camera);
const contactShade=new GTAOPass(scene,camera,1,1);
contactShade.blendIntensity=.7;
contactShade.updateGtaoMaterial({radius:.08,thickness:.25,distanceExponent:1.4,distanceFallOff:.8,scale:1.5,samples:16,screenSpaceRadius:false});
contactShade.updatePdMaterial({radius:7,samples:16,rings:2});
const output=new OutputPass();
composer.addPass(beauty);composer.addPass(contactShade);composer.addPass(output);
renderer.info.autoReset=false;
const controls = new OrbitControls(camera,renderer.domElement);
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
controls.enableDamping = !reducedMotion.matches;
controls.dampingFactor = .12;
controls.maxPolarAngle = Math.PI*.52;
controls.minZoom = .2;
controls.maxZoom = 15;
const hemisphere = new THREE.HemisphereLight('#fff7e9','#7d9290',1.15);
scene.add(hemisphere);
const key = new THREE.DirectionalLight('#fff5df',3.1);
key.castShadow = true;
key.shadow.mapSize.set(2048,2048);
key.shadow.bias = -.00015;
key.shadow.normalBias = .006;
key.shadow.radius = 3;
scene.add(key,key.target);
const fill = new THREE.DirectionalLight('#e3edff',.8);scene.add(fill);
const room = new RoomEnvironment();
const pmrem = new THREE.PMREMGenerator(renderer);
const environment = pmrem.fromScene(room,.04);
scene.environment = environment.texture;
scene.environmentIntensity = .22;
room.dispose();pmrem.dispose();
const ground = new THREE.Mesh(new THREE.PlaneGeometry(1,1),new THREE.MeshStandardMaterial({color:'#d5d7d3',roughness:1}));
ground.rotation.x = -Math.PI/2;ground.receiveShadow = true;scene.add(ground);
const loader = new GLTFLoader();
let model:THREE.Group | undefined;
let workerTemplate:THREE.Object3D | undefined;
let rolesFixture:ReturnType<typeof createWorkerRolesFixture> | undefined;
let pickupFixture:ReturnType<typeof createPickupFixture> | undefined;
let seatedDriver:ReturnType<typeof bindSeatedDriver> | undefined;
let driverActor:WorkerInstance|undefined;
let figureActor:WorkerInstance|undefined;
let pickerGrip:ReturnType<typeof bindPickerGrip>|undefined;
let walkFixture:ReturnType<typeof createCartWalk>|undefined;
let packerAction:ReturnType<typeof createPackerAction>|undefined;
let gripperTool:ReturnType<typeof bindSmallGripper>|undefined;
let smallPickMotion:ReturnType<typeof createSmallPickMotion>|undefined;
let receiverAction:ReturnType<typeof createReceiverAction>|undefined;
let shipperAction:ReturnType<typeof createShipperAction>|undefined;
function activeCycle(){return shipperAction??receiverAction??smallPickMotion??packerAction??walkFixture??pickupFixture;}
let pickupPlaying=false,pickupAnchorTime=0,pickupAnchorWall=0;
let view:View='quarter';
let modelId='calibration';
let phase='loading';
let bounds = new THREE.Box3();
let points:THREE.Vector3[]=[];
let serial=0;
let manifest:ReferenceManifest | undefined;
let frameId=0;
let activeFocus:string|null=null;

function disposeObject(object:THREE.Object3D){
  const geometries=new Set<THREE.BufferGeometry>();const materials=new Set<THREE.Material>();const textures=new Set<THREE.Texture>();
  object.traverse(node=>{if(node instanceof THREE.Mesh){geometries.add(node.geometry);for(const mat of Array.isArray(node.material)?node.material:[node.material]){materials.add(mat);for(const value of Object.values(mat))if(value instanceof THREE.Texture)textures.add(value);}}});
  geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());
}

function releaseModel(){
  pickupPlaying=false;pickupFixture=undefined;element('cycle-controls').hidden=true;
  element('packer-modes').hidden=true;
  element('receiver-modes').hidden=true;
  element('shipper-modes').hidden=true;
  element('gripper-controls').hidden=true;
  if(smallPickMotion){smallPickMotion.dispose();smallPickMotion=undefined;}
  if(shipperAction){shipperAction.dispose();shipperAction=undefined;}
  if(receiverAction){receiverAction.dispose();receiverAction=undefined;}
  if(gripperTool){gripperTool.dispose();gripperTool=undefined;}
  if(packerAction){packerAction.dispose();packerAction=undefined;}
  if(walkFixture){walkFixture.dispose();walkFixture=undefined;}
  // The role instance owns only its tints/badge. Detach it before disposing
  // the vehicle, then release its shared worker template exactly once.
  if(seatedDriver){seatedDriver.release();seatedDriver=undefined;}
  if(pickerGrip){pickerGrip.release();pickerGrip=undefined;}
  if(driverActor){disposeWorkerInstance(driverActor);driverActor=undefined;}
  if(figureActor){disposeWorkerInstance(figureActor);figureActor=undefined;}
  if(model)scene.remove(model);
  if(rolesFixture){rolesFixture.dispose();rolesFixture=undefined;}
  else if(model)disposeObject(model);
  if(workerTemplate){disposeObject(workerTemplate);workerTemplate=undefined;}
  model=undefined;
}

function setStatus(next:string,title:string,copy:string){
  phase=next;shell.dataset.phase=next;element('status-title').textContent=title;element('status-copy').textContent=copy;element('status').dataset.error=String(next==='error');
  document.querySelectorAll<HTMLButtonElement>('[data-view],#reset-view').forEach(button=>button.disabled=next!=='ready');
}

function collectPoints(){
  points=[];if(!model)return;model.updateMatrixWorld(true);
  const collect=(node:THREE.Object3D)=>{if(node instanceof THREE.Mesh&&node.visible){const attribute=node.geometry.getAttribute('position');for(let i=0;i<attribute.count;i++)points.push(new THREE.Vector3().fromBufferAttribute(attribute,i).applyMatrix4(node.matrixWorld));}};
  // Role solo inspection keeps the fixture's metric bounds stable while hiding neighbours.
  const cycle=activeCycle();
  if(cycle){
    // Keep framing stable across the complete action, including a high load
    // at the forward end of its reach, rather than chasing the current frame.
    const restore=cycle.snapshot().time;
    for(const key of cycle.timeline.keys){cycle.apply(key.t);model.updateMatrixWorld(true);model.traverseVisible(collect);}
    cycle.apply(restore);
  }else if(rolesFixture)model.traverse(collect);else model.traverseVisible(collect);
  if(!points.length||points.some(p=>![p.x,p.y,p.z].every(Number.isFinite)))throw Error('В GLB нет корректной конечной геометрии.');
  bounds=new THREE.Box3().setFromPoints(points);
}

function fit(next:View=view,focus?:THREE.Object3D){
  view=next;document.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.view===view)));
  if(!model||!points.length)return;
  if(rolesFixture){const solo=focus?rolesFixture.instances.find(a=>a.root===focus||a.root.getObjectById(focus.id)):undefined;for(const a of rolesFixture.instances)a.root.visible=!solo||a===solo;}
  const aspect=Math.max(.1,host.clientWidth/Math.max(1,host.clientHeight));
  const usableX=Math.max(.55,(host.clientWidth-70)/host.clientWidth);const usableY=Math.max(.45,(host.clientHeight-190)/host.clientHeight);
  activeFocus=focus?.name??null;
  const fitPoints=focus?[] as THREE.Vector3[]:points;
  if(focus){model.updateMatrixWorld(true);focus.traverseVisible(node=>{if(node instanceof THREE.Mesh){const p=node.geometry.getAttribute('position');for(let i=0;i<p.count;i++)fitPoints.push(new THREE.Vector3().fromBufferAttribute(p,i).applyMatrix4(node.matrixWorld));}});}
  if(!fitPoints.length)throw Error('У выбранного узла нет геометрии.');
  const fitBounds=focus?new THREE.Box3().setFromPoints(fitPoints):bounds;
  const centre=fitBounds.getCenter(new THREE.Vector3());const radius=Math.max(fitBounds.getSize(new THREE.Vector3()).length()/2,.03);
  // A close inspection gets its own shadow projection; keep the directional
  // light distant enough to include world-height occluders at that location.
  const wholeRadius=Math.max(bounds.getSize(new THREE.Vector3()).length()/2,.1);
  key.target.position.copy(centre);key.position.copy(centre).add(new THREE.Vector3(-1.8,3,2.4).multiplyScalar(wholeRadius));
  const shadow=key.shadow.camera;shadow.left=-radius*2;shadow.right=radius*2;shadow.top=radius*2;shadow.bottom=-radius*2;shadow.near=.01;shadow.far=wholeRadius*12;shadow.updateProjectionMatrix();
  // Bias scales with the inspection size. A fixed3mm depth bias detached the
  // shadow of a60mm package and erased contact under thin cardboard/tape.
  key.shadow.normalBias=Math.min(.04,Math.max(.00001,radius*.0004));
  key.shadow.bias=-Math.min(.003,Math.max(.000005,radius*.0002))/(shadow.far-shadow.near);
  // Look down the working-arm side from the aisle; the opposite diagonal
  // hides the tool behind the worker or the back of the rack.
  const direction={front:new THREE.Vector3(0,.025,1),side:new THREE.Vector3(1,.025,0),rear:new THREE.Vector3(0,.025,-1),quarter:smallPickMotion?new THREE.Vector3(-1.2,2.1,1.5):modelId==='shipper-workcell-fixture'?new THREE.Vector3(-1.5,1.2,1.2):modelId==='receiver-workcell-fixture'?new THREE.Vector3(1.5,1.2,-1.2):new THREE.Vector3(1.2,.9,1.5),top:new THREE.Vector3(0,1,.0001)}[view].normalize();
  camera=view==='quarter'?perspective:orthographic;camera.up.set(0,1,0);camera.position.copy(centre).addScaledVector(direction,radius*4);camera.lookAt(centre);
  const inverse=camera.quaternion.clone().invert();const projected=new THREE.Vector3();
  let half=.025;let distance=radius;const tan=Math.tan(THREE.MathUtils.degToRad(perspective.fov/2));
  for(const point of fitPoints){projected.copy(point).sub(centre).applyQuaternion(inverse);half=Math.max(half,Math.abs(projected.y)/usableY,Math.abs(projected.x)/(aspect*usableX));distance=Math.max(distance,projected.z+Math.max(Math.abs(projected.y)/(tan*usableY),Math.abs(projected.x)/(tan*aspect*usableX)));}
  if(camera instanceof THREE.OrthographicCamera){
    half*=1.08;camera.left=-half*aspect;camera.right=half*aspect;camera.top=half;camera.bottom=-half;camera.zoom=1;
  }else{
    camera.aspect=aspect;camera.position.copy(centre).addScaledVector(direction,distance*1.08);
  }
  camera.near=Math.max(.001,radius*.002);camera.far=Math.max(100,radius*50);camera.updateProjectionMatrix();
  beauty.camera=camera;contactShade.camera=camera;
  const perspectiveFlag=camera instanceof THREE.PerspectiveCamera?1:0;
  if(contactShade.gtaoMaterial.defines.PERSPECTIVE_CAMERA!==perspectiveFlag){contactShade.gtaoMaterial.defines.PERSPECTIVE_CAMERA=perspectiveFlag;contactShade.gtaoMaterial.needsUpdate=true;}
  // Contact shading reveals real tube bores, bevels and nested joints. Its
  // radius is metric, and the large warehouse engineering preview stays cheap.
  contactShade.enabled=Math.max(...bounds.getSize(new THREE.Vector3()).toArray())<=8;
  contactShade.updateGtaoMaterial({radius:THREE.MathUtils.clamp(radius*.12,.012,.30),thickness:THREE.MathUtils.clamp(radius*.4,.02,.8)});
  controls.object=camera;controls.target.copy(centre);controls.minDistance=radius*.15;controls.maxDistance=radius*30;controls.update();
}

function dimensions(){return bounds.isEmpty()?[0,0,0]:bounds.getSize(new THREE.Vector3()).toArray();}
function rolesSnapshot(){return rolesFixture?.instances.map(instance=>{
  const tinted:Record<string,{uuid:string;color:string}>={};
  instance.root.traverse(node=>{if(node instanceof THREE.Mesh)for(const m of Array.isArray(node.material)?node.material:[node.material])if(/^V3_Worker_Role/.test(m.name)&&m instanceof THREE.MeshStandardMaterial)tinted[m.name]={uuid:m.uuid,color:'#'+m.color.getHexString()};});
  return {actorId:instance.actorId,role:instance.role,disposed:instance.disposed,root:instance.root.name,tinted};
})??[];}
function snapshot(){
  const anchors:Record<string,number[]>={};const nodes:string[]=[];const materials=new Set<string>();let triangles=0;let metadata:Record<string,unknown>={};
  model?.updateMatrixWorld(true);
  model?.traverse(node=>{nodes.push(node.name);if(node.userData.asset_id===modelId)metadata=node.userData;if(node.userData.kind==='anchor'||/^anchor[_:]/i.test(node.name))anchors[node.name]=node.getWorldPosition(new THREE.Vector3()).toArray();});
  model?.traverseVisible(node=>{if(node instanceof THREE.Mesh){triangles+=(node.geometry.index?.count??node.geometry.getAttribute('position').count)/3;for(const m of Array.isArray(node.material)?node.material:[node.material])materials.add(m.name);}});
  camera.updateMatrixWorld(true);const screen={min_x:Infinity,min_y:Infinity,max_x:-Infinity,max_y:-Infinity};const projected=new THREE.Vector3();
  for(const point of points){projected.copy(point).project(camera);const x=(projected.x+1)*host.clientWidth/2;const y=(1-projected.y)*host.clientHeight/2;screen.min_x=Math.min(screen.min_x,x);screen.max_x=Math.max(screen.max_x,x);screen.min_y=Math.min(screen.min_y,y);screen.max_y=Math.max(screen.max_y,y);}
  const cycle=activeCycle();
  return {modelId,phase,view,focus:activeFocus,gripper:gripperTool?.snapshot()??null,fixture:shipperAction?'shipper-visual-QA':receiverAction?'receiver-visual-QA':smallPickMotion?'small-pick-visual-QA':packerAction?'packer-seam-end-visual-QA':walkFixture?'picker-cart-walk-visual-QA':pickupFixture?'pallet-pickup-visual-QA':seatedDriver?'seated-driver-visual-QA':pickerGrip?'picker-grip-visual-QA':rolesFixture?'five-role-visual-QA':null,grip:pickerGrip?.snapshot()??null,driver:seatedDriver?.snapshot()??null,action:cycle?{...cycle.snapshot(),playing:pickupPlaying,reduced_motion:reducedMotion.matches}:null,roles:rolesSnapshot(),dimensions_m:dimensions(),bounds_m:{min:bounds.isEmpty()?[]:bounds.min.toArray(),max:bounds.isEmpty()?[]:bounds.max.toArray()},screen_bounds_px:points.length?screen:null,canvas:{width:host.clientWidth,height:host.clientHeight},anchors,nodes,materials:[...materials],triangles,metadata,camera:{type:camera.type,position:camera.position.toArray(),target:controls.target.toArray()},presentation:{contact_shading:contactShade.enabled,radius_m:contactShade.gtaoMaterial.uniforms.radius.value,camera_inertia:controls.enableDamping,ground_y_m:ground.position.y},renderer:{calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,memory:renderer.info.memory}};
}

function diagnostics(){
  const state=snapshot();['x','y','z'].forEach((axis,i)=>element('size-'+axis).textContent=state.dimensions_m[i].toFixed(3));
  element('triangles').textContent=state.triangles.toLocaleString('ru-RU');element('materials').textContent=String(state.materials.length);element('diagnostics').textContent=JSON.stringify(state,null,2);
}

function updateReference(){
  const referenceAsset=smallPickMotion?'small-package-gripper':pickupFixture||seatedDriver?'forklift':modelId;
  const id=manifest?.asset_reference_bindings[referenceAsset];const entry=manifest?.references.find(r=>r.reference_id===id);
  const link=element<HTMLAnchorElement>('reference-link');const img=element<HTMLImageElement>('reference');
  link.hidden=!entry;
  if(entry){const name=entry.artifact.path.split('/').at(-1)!;img.src=base+'references/v3/'+name;link.href=img.src;element('reference-note').textContent=id+' · независимый production reference';}
  else{img.removeAttribute('src');element('reference-note').textContent=modelId==='calibration'?'Калибровочный образец проверяется по размерам и опорным точкам.':'Для этой модели независимый референс не назначен.';}
}

async function loadModel(id:string){
  const token=++serial;
  if(!/^[a-z0-9][a-z0-9-]{0,63}$/.test(id)){setStatus('error','Неверный идентификатор','Используйте буквы a–z, цифры и дефисы.');return;}
  modelId=id;modelInput.value=id;element('model-title').textContent=assetTitles[id]??id.replaceAll('-',' ');updateReference();
  (ground.material as THREE.MeshStandardMaterial).color.set(id==='floor-markings'?'#AFB6AF':'#d5d7d3');
  setStatus('loading','Загружаем '+id,'Читаем локальный GLB и проверяем геометрию…');
  releaseModel();points=[];bounds.makeEmpty();
  for(const field of ['size-x','size-y','size-z','triangles','materials'])element(field).textContent='—';element('diagnostics').textContent='Загружаем модель…';
  try{
    const gltf=await loader.loadAsync(base+'models/v3/'+id+'.glb');
    if(token!==serial){disposeObject(gltf.scene);return;}
    let tagged:THREE.Object3D|undefined;gltf.scene.traverse(node=>{if(node.userData.asset_id===id)tagged=node;});
    if(!tagged||tagged.userData.namespace!=='v3'||tagged.userData.units!=='m'||tagged.userData.up_axis!=='Y'){
      disposeObject(gltf.scene);throw Error('GLB не содержит согласованные asset_id / namespace v3 / metre / Y-up данные.');
    }
    if(id==='worker-base'&&new URL(location.href).searchParams.get('fixture')==='roles'){
      workerTemplate=gltf.scene;rolesFixture=createWorkerRolesFixture(workerTemplate);model=rolesFixture.root;
      element('model-title').textContent='Пять ролей · визуальный стенд';
    }else if(id==='picker-figure'||id==='worker-manual'||id==='worker-small-pick'){
      workerTemplate=gltf.scene;figureActor=createWorkerInstance(workerTemplate,'P01','picker');
      model=new THREE.Group();model.name='picker_figure_inspection';model.add(figureActor.root);
    }else model=gltf.scene;
    if(id==='small-package-gripper'){gripperTool=bindSmallGripper(tagged);element('gripper-controls').hidden=false;element<HTMLInputElement>('gripper-opening').value='0';element('gripper-gap').textContent='40 мм';}
    const requestedFixture=new URL(location.href).searchParams.get('fixture');
    if(id==='shipper-workcell-fixture'&&requestedFixture==='shipper'){
      const [wr,tr]=await Promise.allSettled([loader.loadAsync(base+'models/v3/worker-manual.glb'),fetch(base+'data/v3/shipper-v3.json').then(async r=>{if(!r.ok)throw Error('Описание отгрузки недоступно.');return validateShipperTimeline(await r.json());})]);
      if(token!==serial){if(wr.status==='fulfilled')disposeObject(wr.value.scene);return;}
      if(wr.status==='rejected'||tr.status==='rejected'){if(wr.status==='fulfilled')disposeObject(wr.value.scene);throw wr.status==='rejected'?wr.reason:(tr as PromiseRejectedResult).reason;}
      workerTemplate=wr.value.scene;figureActor=createWorkerInstance(workerTemplate,'S01','shipper');
      const cell=model.getObjectByName('shipper_workcell_root');if(!cell)throw Error('Нет поста отгрузки.');
      shipperAction=createShipperAction(cell,figureActor,tr.value);
      const mode=new URL(location.href).searchParams.get('mode');if(mode==='scan'||mode==='idle'||mode==='blocked')shipperAction.setMode(mode);
      element('shipper-modes').hidden=false;configureShipperCycle();element('model-title').textContent='Отгрузчик · посылка';
    }
    if(id==='receiver-workcell-fixture'&&requestedFixture==='receiver'){
      const [wr,tr]=await Promise.allSettled([loader.loadAsync(base+'models/v3/worker-manual.glb'),fetch(base+'data/v3/receiver-v3.json').then(async r=>{if(!r.ok)throw Error('Описание приёмки недоступно.');return validateReceiverTimeline(await r.json());})]);
      if(token!==serial){if(wr.status==='fulfilled')disposeObject(wr.value.scene);return;}
      if(wr.status==='rejected'||tr.status==='rejected'){if(wr.status==='fulfilled')disposeObject(wr.value.scene);throw wr.status==='rejected'?wr.reason:(tr as PromiseRejectedResult).reason;}
      workerTemplate=wr.value.scene;figureActor=createWorkerInstance(workerTemplate,'R01','receiver');
      const cell=model.getObjectByName('receiver_workcell_root');if(!cell)throw Error('Нет поста приёмки.');
      receiverAction=createReceiverAction(cell,figureActor,tr.value);
      const mode=new URL(location.href).searchParams.get('mode');if(mode==='scan'||mode==='idle'||mode==='blocked')receiverAction.setMode(mode);
      element('receiver-modes').hidden=false;configureReceiverCycle();element('model-title').textContent='Приёмщик · паллета';
    }
    if(id==='packer-workcell-fixture'&&requestedFixture==='packer'){
      const [wr,tr]=await Promise.allSettled([loader.loadAsync(base+'models/v3/worker-manual.glb'),fetch(base+'data/v3/packer-seam-end.json').then(async r=>{if(!r.ok)throw Error('Описание упаковки недоступно.');return validatePackerTimeline(await r.json());})]);
      if(wr.status==='rejected')throw wr.reason;
      if(token!==serial){disposeObject(wr.value.scene);return;}
      if(tr.status==='rejected'){disposeObject(wr.value.scene);throw tr.reason;}
      workerTemplate=wr.value.scene;figureActor=createWorkerInstance(workerTemplate,'PK01','packer');
      const cell=model.getObjectByName('packer_workcell_root');if(!cell)throw Error('Нет упаковочного поста.');
      packerAction=createPackerAction(cell,figureActor,tr.value);
      const mode=new URL(location.href).searchParams.get('mode');if(mode==='idle'||mode==='blocked')packerAction.setMode(mode);
      element('packer-modes').hidden=false;
      configureCycle('Прижим края ленты',[[0,'Начало'],[2.1,'Подвод'],[3.2,'Прижим'],[4.9,'Проверка'],[7.5,'Готово']]);
      element('model-title').textContent='Упаковщик · прижим края ленты';
    }
    if(id==='picker-pick-source-fixture'&&requestedFixture==='pick'){
      const [wr,gr,tr]=await Promise.allSettled([loader.loadAsync(base+'models/v3/worker-small-pick.glb'),loader.loadAsync(base+'models/v3/small-package-gripper.glb'),fetch(base+'models/v3/small-pick-v3.json').then(async r=>{if(!r.ok)throw Error('Описание отбора недоступно.');return validateSmallPickTimeline(await r.json());})]);
      const releaseFetched=()=>{if(wr.status==='fulfilled')disposeObject(wr.value.scene);if(gr.status==='fulfilled')disposeObject(gr.value.scene);};
      if(token!==serial){releaseFetched();return;}
      if(wr.status==='rejected'||gr.status==='rejected'||tr.status==='rejected'){releaseFetched();throw wr.status==='rejected'?wr.reason:gr.status==='rejected'?gr.reason:(tr as PromiseRejectedResult).reason;}
      workerTemplate=wr.value.scene;model.add(gr.value.scene);figureActor=createWorkerInstance(workerTemplate,'P01','picker');
      const cell=model.getObjectByName('picker_pick_source_fixture_root'),tool=gr.value.scene.getObjectByName('small-package-gripper');if(!cell||!tool)throw Error('Не найден источник или ручной инструмент.');
      smallPickMotion=createSmallPickMotion(cell,figureActor,tool,tr.value);updateReference();
      configureCycle('Отбор двух упаковок',[[0,'Начало'],[3.5,'Захват'],[14.4,'Отход'],[33.2,'Лоток'],[36,'Готово']]);
      element('model-title').textContent='Отбор SMALL · проверка';
    }
    if(id==='picking-cart-tote-fixture'&&['grip','walk'].includes(requestedFixture??'')){
      const workerAsset=new URL(location.href).searchParams.get('worker')==='manual'?'worker-manual':'worker-base';
      const [workerResult,poseResult]=await Promise.allSettled([loader.loadAsync(base+'models/v3/'+workerAsset+'.glb'),fetch(base+'data/v3/picker-push-pose.json').then(async r=>{if(!r.ok)throw Error('Поза комплектовщика недоступна.');return validatePickerPushPose(await r.json());})]);
      if(workerResult.status==='rejected')throw workerResult.reason;
      const worker=workerResult.value;
      if(poseResult.status==='rejected'){disposeObject(worker.scene);throw poseResult.reason;}
      const pose=poseResult.value;
      if(token!==serial){disposeObject(worker.scene);disposeObject(gltf.scene);return;}
      workerTemplate=worker.scene;
      const cart=model.getObjectByName('picking-cart');if(!cart)throw Error('В сборке нет тележки.');
      figureActor=createWorkerInstance(workerTemplate,'P01','picker');pickerGrip=bindPickerGrip(cart,figureActor,pose);
      element('model-title').textContent='Комплектовщик с тележкой';
    }
    if(id==='picking-cart-tote-fixture'&&requestedFixture==='walk'){
      const response=await fetch(base+'data/v3/picker-cart-walk.json');if(!response.ok)throw Error('Описание движения недоступно.');
      const timeline=validateCartWalkTimeline(await response.json());if(token!==serial)return;
      const cart=pickerGrip!.cart,tote=model.getObjectByName('order-tote');if(!tote)throw Error('В сборке нет ящика.');
      cart.updateWorldMatrix(true,true);cart.attach(tote);walkFixture=createCartWalk(pickerGrip!,timeline);
      configureCycle('Ходьба с тележкой',[[0,'Начало'],[1,'Движение'],[3.5,'Шаг'],[8,'Остановка'],[9,'Готово']]);
      element('model-title').textContent='Комплектовщик ведёт тележку';
    }
    if((id==='forklift'&&requestedFixture==='driver')||(id==='forklift-pallet-low-fixture'&&requestedFixture==='pickup')){
      const [worker,poseResponse]=await Promise.all([loader.loadAsync(base+'models/v3/worker-base.glb'),fetch(base+'data/v3/seated-driver-pose.json')]);
      if(token!==serial){disposeObject(worker.scene);disposeObject(gltf.scene);return;}
      workerTemplate=worker.scene;
      if(!poseResponse.ok)throw Error('Поза водителя недоступна.');
      const driverPose=validateSeatedDriverPose(await poseResponse.json());
      if(token!==serial)return;
      const vehicle=model.getObjectByName('forklift_root');if(!vehicle)throw Error('В сборке нет погрузчика.');
      // The isolated stand owns this one sample. Production binding consumes
      // the existing registry instance, so seating never duplicates a worker.
      driverActor=createWorkerInstance(workerTemplate,'F01','forklift_driver');
      seatedDriver=bindSeatedDriver(vehicle,driverActor,driverPose);
      if(requestedFixture==='driver')element('model-title').textContent='Водитель в погрузчике';
      updateReference();
    }
    if(id==='forklift-pallet-low-fixture'&&new URL(location.href).searchParams.get('fixture')==='pickup'){
      const response=await fetch(base+'data/v3/pallet-pickup-cycle.json');
      if(!response.ok)throw Error('Описание цикла недоступно.');
      const timeline=validatePickupTimeline(await response.json());
      if(token!==serial){disposeObject(gltf.scene);return;}
      pickupFixture=createPickupFixture(model,timeline);
      configureCycle('Подхват паллеты',[[0,'Начало'],[8,'Подхват'],[14,'Перевозка'],[22,'На опоре'],[30,'Готово']]);element('model-title').textContent='Подхват и установка паллеты';updateReference();
    }
    scene.add(model);
    model.traverse(node=>{if(node instanceof THREE.Mesh){
      node.castShadow=node.userData.cast_shadow!==false&&node.userData.shell_component_class!=='floor_support';node.receiveShadow=true;
      if(node.userData.surface_paint===true){
        node.castShadow=false;node.renderOrder=2;
        for(const material of Array.isArray(node.material)?node.material:[node.material]){
          material.polygonOffset=true;material.polygonOffsetFactor=-1;material.polygonOffsetUnits=-2;material.depthWrite=false;
        }
      }
      // Closed native solids can retain their original double-sided colour
      // material while casting only their back faces. This removes the legacy
      // rack's self-shadow stripes without a millimetre-scale contact gap.
      for(const m of Array.isArray(node.material)?node.material:[node.material])if(m.side===THREE.DoubleSide)m.shadowSide=THREE.BackSide;
    }});
    collectPoints();
    const centre=bounds.getCenter(new THREE.Vector3());const radius=Math.max(bounds.getSize(new THREE.Vector3()).length()/2,.1);
    // Keep only a numerical depth bias below actual support. A fixed2mm gap
    // visibly floated a60mm package and its half-millimetre peeled tape.
    const floorBias=Math.min(.002,Math.max(.00001,radius*.00005));
    ground.position.set(centre.x,Math.min(0,bounds.min.y)-floorBias,centre.z);ground.scale.set(radius*5,radius*5,1);
    key.target.position.copy(centre);key.position.copy(centre).add(new THREE.Vector3(-1.8,3,2.4).multiplyScalar(radius));fill.position.copy(centre).add(new THREE.Vector3(2,1,-1).multiplyScalar(radius));
    fit(view);setStatus('ready',shipperAction?'Отгрузчик · посылка':receiverAction?'Приёмщик · паллета':smallPickMotion?'Отбор SMALL · проверка':packerAction?'Упаковщик · прижим края ленты':walkFixture?'Комплектовщик ведёт тележку':pickupFixture?'Подхват и установка паллеты':seatedDriver?'Водитель в погрузчике':rolesFixture?'Пять ролей · визуальный стенд':assetTitles[id]??id.replaceAll('-',' '),shipperAction?'Визуальный стенд · сканирование и укладка посылки на выход':receiverAction?'Визуальный стенд · сканирование и подтверждение установленной паллеты':smallPickMotion?'Визуальный стенд · подготовленный источник и один работник':packerAction?'Визуальный стенд · финальная проверка уже закрытой посылки':activeCycle()?'Выберите этап или запустите цикл справа':seatedDriver?'Масштаб 1:1 · посадка и органы управления':rolesFixture?'Пять образцов ролей · масштаб 1:1 · это стенд моделей':id==='picker-pick-source-fixture'?'Отдельный стенд источника · отбор ещё не запущен':'Масштаб 1:1 в метрах · вращайте и приближайте');diagnostics();
    const url=new URL(location.href);url.searchParams.set('asset',id);history.replaceState(null,'',url);
  }catch(error){if(token!==serial)return;releaseModel();points=[];bounds.makeEmpty();const detail=error instanceof Error?error.message:String(error);setStatus('error','Модель не открылась',detail.includes('404')?'Файл модели не найден. Проверьте имя или экспорт и нажмите «Открыть».':'Не удалось проверить модель. Подробности — в данных проверки; повторите экспорт или загрузку.');element('diagnostics').textContent=detail;}
}

function configureCycle(title:string,checkpoints:[number,string][]){
  element('cycle-controls').hidden=false;element('cycle-title').textContent=title;
  const cycle=activeCycle()!;element<HTMLInputElement>('cycle-time').max=String(cycle.timeline.duration_s);
  document.querySelectorAll<HTMLButtonElement>('[data-cycle-time]').forEach((b,i)=>{b.dataset.cycleTime=String(checkpoints[i][0]);b.textContent=checkpoints[i][1];});updatePickupUi();
}
function configureShipperCycle(){
  if(!shipperAction)return;
  configureCycle(shipperAction.snapshot().mode==='scan'?'Сканирование посылки':'Укладка на выход',shipperAction.snapshot().mode==='scan'?[[0,'Начало'],[.5,'Луч'],[1.2,'Этикетка'],[1.8,'Проверено'],[2.5,'Готово']]:[[0,'Начало'],[1.8,'Скан'],[7.9,'Укладка'],[11.5,'Уложено'],[27,'Готово']]);
}
function configureReceiverCycle(){
  if(!receiverAction)return;
  configureCycle(receiverAction.snapshot().mode==='scan'?'Сканирование паллеты':'Приёмка паллеты',receiverAction.snapshot().mode==='scan'?[[0,'Начало'],[.5,'Луч'],[1.2,'Этикетка'],[1.8,'Проверено'],[2.5,'Готово']]:[[0,'Начало'],[1.8,'Скан'],[7.8,'Контакт'],[9.2,'Принято'],[17.8,'Готово']]);
}
function updatePickupUi(){
  const cycle=activeCycle();if(!cycle)return;
  const action=cycle.snapshot(),play=element<HTMLButtonElement>('cycle-play');
  const stationary=Boolean(shipperAction&&['idle','blocked'].includes(shipperAction.snapshot().mode))||Boolean(packerAction&&packerAction.snapshot().mode!=='pack')||Boolean(receiverAction&&['idle','blocked'].includes(receiverAction.snapshot().mode));
  play.textContent=pickupPlaying?'Пауза':action.complete?'Повторить':'Воспроизвести';play.setAttribute('aria-pressed',String(pickupPlaying));play.disabled=reducedMotion.matches||stationary;
  const label=element('cycle-phase');if(label.textContent!==action.label)label.textContent=action.label;
  element('cycle-clock').textContent=stationary?'Вне операции':action.time.toFixed(1)+' / '+cycle.timeline.duration_s+' с';
  const slider=element<HTMLInputElement>('cycle-time');slider.value=String(action.time);slider.disabled=stationary;slider.setAttribute('aria-valuetext',action.time.toFixed(1)+' с — '+action.label);
  element('cycle-motion-note').textContent=stationary?(shipperAction?'Работа не выполняется. Выберите «Укладка» или «Сканирование».':receiverAction?'Работа не выполняется. Выберите «Приёмка» или «Сканирование».':'Работа не выполняется. Выберите «Упаковка», чтобы проверить действие.'):reducedMotion.matches?'Системная настройка ограничивает движение. Выберите этап или время для статичного просмотра.':'Цикл запускается вручную. Можно остановить и проверить любой момент.';
  document.querySelectorAll<HTMLButtonElement>('[data-cycle-time]').forEach(b=>{b.disabled=stationary;b.setAttribute('aria-pressed',String(Math.abs(Number(b.dataset.cycleTime)-action.time)<.01));});
  document.querySelectorAll<HTMLButtonElement>('[data-packer-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.packerMode===packerAction?.snapshot().mode)));
  document.querySelectorAll<HTMLButtonElement>('[data-receiver-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.receiverMode===receiverAction?.snapshot().mode)));
  document.querySelectorAll<HTMLButtonElement>('[data-shipper-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.shipperMode===shipperAction?.snapshot().mode)));
}
function seekPickup(time:number){const cycle=activeCycle();if(!cycle)throw Error('Цикл не загружен.');pickupPlaying=false;cycle.apply(time);updatePickupUi();diagnostics();}
function pausePickup(){
  const cycle=activeCycle();if(pickupPlaying&&cycle)cycle.apply(pickupAnchorTime+(performance.now()-pickupAnchorWall)/1000);
  pickupPlaying=false;updatePickupUi();if(cycle)diagnostics();
}
function playPickup(){
  const cycle=activeCycle();if(!cycle||reducedMotion.matches||(shipperAction&&['idle','blocked'].includes(shipperAction.snapshot().mode))||(packerAction&&packerAction.snapshot().mode!=='pack')||(receiverAction&&['idle','blocked'].includes(receiverAction.snapshot().mode)))return false;
  if(cycle.snapshot().complete)cycle.apply(0);
  pickupAnchorTime=cycle.snapshot().time;pickupAnchorWall=performance.now();pickupPlaying=true;updatePickupUi();return true;
}
element('cycle-play').addEventListener('click',()=>pickupPlaying?pausePickup():playPickup());
function setGripperOpening(value:number){if(!gripperTool)throw Error('Ручной захват не загружен.');const state=gripperTool.apply(value);element<HTMLInputElement>('gripper-opening').value=String(value);element('gripper-gap').textContent=(state.jaw_gap_m*1000).toFixed(1)+' мм';collectPoints();diagnostics();return state;}
element<HTMLInputElement>('gripper-opening').addEventListener('input',event=>setGripperOpening(Number((event.target as HTMLInputElement).value)));
function setPackerMode(mode:PackerMode){if(!packerAction)throw Error('Упаковщик не загружен.');pickupPlaying=false;packerAction.setMode(mode);const url=new URL(location.href);url.searchParams.set('mode',mode);history.replaceState(null,'',url);collectPoints();fit(view);updatePickupUi();diagnostics();}
document.querySelectorAll<HTMLButtonElement>('[data-packer-mode]').forEach(b=>b.addEventListener('click',()=>setPackerMode(b.dataset.packerMode as PackerMode)));
function setReceiverMode(mode:ReceiverMode){if(!receiverAction)throw Error('Приёмщик не загружен.');pickupPlaying=false;receiverAction.setMode(mode);const url=new URL(location.href);url.searchParams.set('mode',mode);history.replaceState(null,'',url);configureReceiverCycle();collectPoints();fit(view);diagnostics();}
document.querySelectorAll<HTMLButtonElement>('[data-receiver-mode]').forEach(b=>b.addEventListener('click',()=>setReceiverMode(b.dataset.receiverMode as ReceiverMode)));
function setShipperMode(mode:ShipperMode){if(!shipperAction)throw Error('Отгрузчик не загружен.');pickupPlaying=false;shipperAction.setMode(mode);const url=new URL(location.href);url.searchParams.set('mode',mode);history.replaceState(null,'',url);configureShipperCycle();collectPoints();fit(view);diagnostics();}
document.querySelectorAll<HTMLButtonElement>('[data-shipper-mode]').forEach(b=>b.addEventListener('click',()=>setShipperMode(b.dataset.shipperMode as ShipperMode)));
element<HTMLInputElement>('cycle-time').addEventListener('input',event=>seekPickup(Number((event.target as HTMLInputElement).value)));
document.querySelectorAll<HTMLButtonElement>('[data-cycle-time]').forEach(b=>b.addEventListener('click',()=>seekPickup(Number(b.dataset.cycleTime))));
const onMotionChange=()=>{pausePickup();controls.enableDamping=!reducedMotion.matches;updatePickupUi();};reducedMotion.addEventListener('change',onMotionChange);
const onVisibility=()=>{if(document.hidden)pausePickup();};document.addEventListener('visibilitychange',onVisibility);

document.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(button=>button.addEventListener('click',()=>{fit(button.dataset.view as View);diagnostics();}));
element('reset-view').addEventListener('click',()=>{fit();diagnostics();});
element('model-form').addEventListener('submit',event=>{event.preventDefault();void loadModel(modelInput.value.trim());});
const resize=new ResizeObserver(()=>{renderer.setSize(host.clientWidth,host.clientHeight,false);composer.setSize(host.clientWidth,host.clientHeight);contactShade.setSize(Math.max(1,Math.round(host.clientWidth*renderer.getPixelRatio()*.65)),Math.max(1,Math.round(host.clientHeight*renderer.getPixelRatio()*.65)));if(model)fit();});resize.observe(host);
function tick(){frameId=requestAnimationFrame(tick);const cycle=activeCycle();if(pickupPlaying&&cycle){const action=cycle.apply(pickupAnchorTime+(performance.now()-pickupAnchorWall)/1000);if(action.complete)pickupPlaying=false;updatePickupUi();}controls.update();renderer.info.reset();composer.render();}tick();
const api={load:loadModel,view:(next:View)=>{fit(next);diagnostics();},focus:(name:string,next:View='quarter')=>{const n=model?.getObjectByName(name);if(!n)throw Error('Unknown node '+name);fit(next,n);diagnostics();},snapshot,node:(name:string)=>{const n=model?.getObjectByName(name);return n?{position:n.getWorldPosition(new THREE.Vector3()).toArray(),localPosition:n.position.toArray(),rotation:n.rotation.toArray().slice(0,3)}:null;},setNode:(name:string,values:{position?:[number,number,number];rotation?:[number,number,number]})=>{const n=model?.getObjectByName(name);if(!n)throw Error('Unknown node '+name);if(values.position)n.position.fromArray(values.position);if(values.rotation)n.rotation.set(...values.rotation);collectPoints();diagnostics();}};
Object.assign(window,{__QOIMA_STAND_V3__:{...api,gripper:{setOpening:setGripperOpening,snapshot:()=>gripperTool?.snapshot()??null},cycle:{seek:seekPickup,play:playPickup,pause:pausePickup,snapshot:()=>{const cycle=activeCycle();return cycle?{...cycle.snapshot(),playing:pickupPlaying,reduced_motion:reducedMotion.matches}:null;}},packer:{setMode:setPackerMode,snapshot:()=>packerAction?.snapshot()??null},receiver:{setMode:setReceiverMode,snapshot:()=>receiverAction?.snapshot()??null},shipper:{setMode:setShipperMode,snapshot:()=>shipperAction?.snapshot()??null},roles:rolesSnapshot,setRole:(actorId:string,role:WorkerRole)=>{const instance=rolesFixture?.instances.find(a=>a.actorId===actorId);if(!instance)throw Error('Unknown QA actor '+actorId);applyWorkerRole(instance,role);collectPoints();diagnostics();},resetRoles:()=>{if(!rolesFixture)throw Error('Role fixture is not loaded');rolesFixture.reset();collectPoints();diagnostics();}}});
void fetch(base+'references/v3/manifest.json').then(r=>{if(!r.ok)throw Error('Reference manifest unavailable');return r.json() as Promise<ReferenceManifest>;}).then(value=>{manifest=value;updateReference();}).catch(()=>{element('reference-note').textContent='Каталог референсов временно недоступен.';});
void loadModel(new URL(location.href).searchParams.get('asset')||'calibration');
window.addEventListener('pagehide',()=>{cancelAnimationFrame(frameId);resize.disconnect();reducedMotion.removeEventListener('change',onMotionChange);document.removeEventListener('visibilitychange',onVisibility);controls.dispose();releaseModel();ground.geometry.dispose();(ground.material as THREE.Material).dispose();environment.dispose();contactShade.dispose();beauty.dispose();output.dispose();composer.dispose();renderer.dispose();},{once:true});
}
void initialize().catch(error=>{
  shell.dataset.phase='error';element('status').dataset.error='true';element('status-title').textContent='Стенд не запустился';element('status-copy').textContent='Обновите страницу в браузере с поддержкой WebGL.';element('diagnostics').textContent=error instanceof Error?error.message:String(error);
  document.querySelectorAll<HTMLButtonElement>('[data-view],#reset-view').forEach(button=>button.disabled=true);
});
