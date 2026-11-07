import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/examples/jsm/postprocessing/GTAOPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import {createWorkerRolesFixture, applyWorkerRole, type WorkerRole} from './workerRoles';

type View = 'front' | 'side' | 'rear' | 'quarter' | 'top';
type ReferenceManifest = {references: {reference_id: string; artifact: {path: string}}[]; asset_reference_bindings: Record<string,string>};
const element = <T extends HTMLElement = HTMLElement>(id:string) => document.getElementById(id) as T;
const host = element('canvas-host');
const shell = element('stand');
const modelInput = element<HTMLInputElement>('model-id');
const base = import.meta.env.BASE_URL;
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
controls.enableDamping = true;
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
  if(rolesFixture)model.traverse(collect);else model.traverseVisible(collect);
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
  const shadow=key.shadow.camera;shadow.left=-radius*2;shadow.right=radius*2;shadow.top=radius*2;shadow.bottom=-radius*2;shadow.near=.01;shadow.far=wholeRadius*12;shadow.updateProjectionMatrix();key.shadow.normalBias=Math.min(.04,radius*.003);key.shadow.bias=-.003/(shadow.far-shadow.near);
  const direction={front:new THREE.Vector3(0,.025,1),side:new THREE.Vector3(1,.025,0),rear:new THREE.Vector3(0,.025,-1),quarter:new THREE.Vector3(1.2,.9,1.5),top:new THREE.Vector3(0,1,.0001)}[view].normalize();
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
  return {modelId,phase,view,focus:activeFocus,fixture:rolesFixture?'five-role-visual-QA':null,roles:rolesSnapshot(),dimensions_m:dimensions(),bounds_m:{min:bounds.isEmpty()?[]:bounds.min.toArray(),max:bounds.isEmpty()?[]:bounds.max.toArray()},screen_bounds_px:points.length?screen:null,canvas:{width:host.clientWidth,height:host.clientHeight},anchors,nodes,materials:[...materials],triangles,metadata,camera:{type:camera.type,position:camera.position.toArray(),target:controls.target.toArray()},presentation:{contact_shading:contactShade.enabled,radius_m:contactShade.gtaoMaterial.uniforms.radius.value},renderer:{calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,memory:renderer.info.memory}};
}

function diagnostics(){
  const state=snapshot();['x','y','z'].forEach((axis,i)=>element('size-'+axis).textContent=state.dimensions_m[i].toFixed(3));
  element('triangles').textContent=state.triangles.toLocaleString('ru-RU');element('materials').textContent=String(state.materials.length);element('diagnostics').textContent=JSON.stringify(state,null,2);
}

function updateReference(){
  const id=manifest?.asset_reference_bindings[modelId];const entry=manifest?.references.find(r=>r.reference_id===id);
  const link=element<HTMLAnchorElement>('reference-link');const img=element<HTMLImageElement>('reference');
  link.hidden=!entry;
  if(entry){const name=entry.artifact.path.split('/').at(-1)!;img.src=base+'references/v3/'+name;link.href=img.src;element('reference-note').textContent=id+' · независимый production reference';}
  else{img.removeAttribute('src');element('reference-note').textContent=modelId==='calibration'?'Калибровочный образец проверяется по размерам и опорным точкам.':'Для этой модели независимый референс не назначен.';}
}

async function loadModel(id:string){
  const token=++serial;
  if(!/^[a-z0-9][a-z0-9-]{0,63}$/.test(id)){setStatus('error','Неверный идентификатор','Используйте буквы a–z, цифры и дефисы.');return;}
  modelId=id;modelInput.value=id;element('model-title').textContent=id.replaceAll('-',' ');updateReference();
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
    }else model=gltf.scene;
    scene.add(model);
    model.traverse(node=>{if(node instanceof THREE.Mesh){node.castShadow=node.userData.cast_shadow!==false&&node.userData.shell_component_class!=='floor_support';node.receiveShadow=true;}});
    collectPoints();
    const centre=bounds.getCenter(new THREE.Vector3());const radius=Math.max(bounds.getSize(new THREE.Vector3()).length()/2,.1);
    ground.position.set(centre.x,Math.min(0,bounds.min.y)-.002,centre.z);ground.scale.set(radius*5,radius*5,1);
    key.target.position.copy(centre);key.position.copy(centre).add(new THREE.Vector3(-1.8,3,2.4).multiplyScalar(radius));fill.position.copy(centre).add(new THREE.Vector3(2,1,-1).multiplyScalar(radius));
    fit(view);setStatus('ready',rolesFixture?'Пять ролей · визуальный стенд':id.replaceAll('-',' '),rolesFixture?'Пять образцов ролей · масштаб 1:1 · это стенд моделей':'Масштаб 1:1 в метрах · вращайте и приближайте');diagnostics();
    const url=new URL(location.href);url.searchParams.set('asset',id);history.replaceState(null,'',url);
  }catch(error){if(token!==serial)return;releaseModel();points=[];bounds.makeEmpty();const detail=error instanceof Error?error.message:String(error);setStatus('error','Модель не открылась',detail.includes('404')?'Файл модели не найден. Проверьте имя или экспорт и нажмите «Открыть».':'Не удалось проверить модель. Подробности — в данных проверки; повторите экспорт или загрузку.');element('diagnostics').textContent=detail;}
}

document.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(button=>button.addEventListener('click',()=>{fit(button.dataset.view as View);diagnostics();}));
element('reset-view').addEventListener('click',()=>{fit();diagnostics();});
element('model-form').addEventListener('submit',event=>{event.preventDefault();void loadModel(modelInput.value.trim());});
const resize=new ResizeObserver(()=>{renderer.setSize(host.clientWidth,host.clientHeight,false);composer.setSize(host.clientWidth,host.clientHeight);contactShade.setSize(Math.max(1,Math.round(host.clientWidth*renderer.getPixelRatio()*.65)),Math.max(1,Math.round(host.clientHeight*renderer.getPixelRatio()*.65)));if(model)fit();});resize.observe(host);
function tick(){frameId=requestAnimationFrame(tick);controls.update();renderer.info.reset();composer.render();}tick();
const api={load:loadModel,view:(next:View)=>{fit(next);diagnostics();},focus:(name:string,next:View='quarter')=>{const n=model?.getObjectByName(name);if(!n)throw Error('Unknown node '+name);fit(next,n);diagnostics();},snapshot,node:(name:string)=>{const n=model?.getObjectByName(name);return n?{position:n.getWorldPosition(new THREE.Vector3()).toArray(),localPosition:n.position.toArray(),rotation:n.rotation.toArray().slice(0,3)}:null;},setNode:(name:string,values:{position?:[number,number,number];rotation?:[number,number,number]})=>{const n=model?.getObjectByName(name);if(!n)throw Error('Unknown node '+name);if(values.position)n.position.fromArray(values.position);if(values.rotation)n.rotation.set(...values.rotation);collectPoints();diagnostics();}};
Object.assign(window,{__QOIMA_STAND_V3__:{...api,roles:rolesSnapshot,setRole:(actorId:string,role:WorkerRole)=>{const instance=rolesFixture?.instances.find(a=>a.actorId===actorId);if(!instance)throw Error('Unknown QA actor '+actorId);applyWorkerRole(instance,role);collectPoints();diagnostics();},resetRoles:()=>{if(!rolesFixture)throw Error('Role fixture is not loaded');rolesFixture.reset();collectPoints();diagnostics();}}});
void fetch(base+'references/v3/manifest.json').then(r=>{if(!r.ok)throw Error('Reference manifest unavailable');return r.json() as Promise<ReferenceManifest>;}).then(value=>{manifest=value;updateReference();}).catch(()=>{element('reference-note').textContent='Каталог референсов временно недоступен.';});
void loadModel(new URL(location.href).searchParams.get('asset')||'calibration');
window.addEventListener('pagehide',()=>{cancelAnimationFrame(frameId);resize.disconnect();controls.dispose();releaseModel();ground.geometry.dispose();(ground.material as THREE.Material).dispose();environment.dispose();contactShade.dispose();beauty.dispose();output.dispose();composer.dispose();renderer.dispose();},{once:true});
}
void initialize().catch(error=>{
  shell.dataset.phase='error';element('status').dataset.error='true';element('status-title').textContent='Стенд не запустился';element('status-copy').textContent='Обновите страницу в браузере с поддержкой WebGL.';element('diagnostics').textContent=error instanceof Error?error.message:String(error);
  document.querySelectorAll<HTMLButtonElement>('[data-view],#reset-view').forEach(button=>button.disabled=true);
});
