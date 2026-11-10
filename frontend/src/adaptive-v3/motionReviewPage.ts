import * as THREE from 'three';
import {createMotionReviewSetup,loadMotionReviewSources,type MotionCarryPose} from './motionReviewSetup';
import type {WarehousePalmSupportRow} from './warehousePalmSupport';
import './motionReview.css';

type LiveFrame={at_s:number;gait_stage:string;motion_profile:Record<string,unknown>;
 carry_pose?:MotionCarryPose;breathing?:{enabled:boolean;angle_rad:number;period_s:number;amplitude_rad:number};
 readonly forearm_pronation?:Readonly<Record<string,unknown>>;
 grip_support?:WarehousePalmSupportRow[];
 contacts:{gap_m:number}[];feet:{error_m:number;native_bottom_y_m:number;stance:boolean}[]};
type Setup=Awaited<ReturnType<typeof createMotionReviewSetup>>;
type Sources=Awaited<ReturnType<typeof loadMotionReviewSources>>;
const element=<T extends HTMLElement>(selector:string)=>{
 const node=document.querySelector<T>(selector);if(!node)throw Error('Missing motion review interface');return node;
};
const root=element('#motion-review'),host=element('#motion-views'),slider=element<HTMLInputElement>('#motion-timeline');
const playButton=element<HTMLButtonElement>('#motion-play'),playLabel=element('#motion-play-label');
const resetButton=element<HTMLButtonElement>('#motion-reset'),halfButton=element<HTMLButtonElement>('#motion-half');
const loading=element('#motion-loading'),errorMessage=element('#motion-error'),reducedNotice=element('#motion-reduced');
const timeOutput=element<HTMLOutputElement>('#motion-time'),phaseOutput=element('#motion-phase');
const tabs=[...document.querySelectorAll<HTMLButtonElement>('[data-camera]')];
const reduced=matchMedia('(prefers-reduced-motion: reduce)'),mobile=matchMedia('(max-width: 779px)');
const lifetime=new AbortController(),fetchLifetime=new AbortController();
let setup:Setup|undefined,sources:Sources|undefined,renderer:THREE.WebGLRenderer|undefined,observer:ResizeObserver|undefined;
let disposed=false,playing=false,request=0,started=0,elapsed=0,rate:1|.5=1,selectedCamera=0,lastLive:LiveFrame|undefined;
let cachedWidth=0,cachedHeight=0;
let activeBreathing=false;
const cameras=[0,1,2].map(()=>new THREE.PerspectiveCamera(35,1,.01,180));
const cameraOffsets=[[0,.20,3.6],[3.6,.30,.05],[2.65,1.1,2.65]];
const joints=new Map<string,THREE.Object3D>();
const metrics={frames:0,maximum_apply_ms:0,maximum_contact_gap_m:0,maximum_sole_error_m:0};
const decimal=(value:number)=>value.toFixed(2).replace('.',',');

function stop(){
 playing=false;cancelAnimationFrame(request);request=0;
 playLabel.textContent='Воспроизвести';playButton.setAttribute('aria-pressed','false');
 const icon=playButton.querySelector('.mr-play-icon');if(icon)icon.textContent='▶';
}
function teardown(){
 if(disposed)return;stop();disposed=true;
 lifetime.abort();fetchLifetime.abort();observer?.disconnect();
 // Calibration must release its binding before the private worker or any shared geometry.
 try{setup?.dispose();}finally{
  sources?.clear();renderer?.dispose();renderer?.forceContextLoss();renderer?.domElement.remove();
  root.querySelectorAll<HTMLButtonElement|HTMLInputElement>('button,input').forEach(control=>{control.disabled=true;});
 }
}
function fail(error:unknown){
 // Keep the underlying reason available to development tools, without putting source IDs in the user flow.
 root.dataset.failure=error instanceof Error?error.message:String(error);
 try{teardown();}finally{root.dataset.state='error';loading.hidden=true;errorMessage.hidden=false;}
}
function render(){
 if(!renderer||!setup||disposed)return;
 const width=Math.max(1,host.clientWidth),height=Math.max(1,host.clientHeight);
 if(width!==cachedWidth||height!==cachedHeight){renderer.setSize(width,height,false);cachedWidth=width;cachedHeight=height;}
 const actor=setup.actor.root,target=new THREE.Vector3(0,.80,.18).applyMatrix4(actor.matrixWorld);
 const rotation=new THREE.Quaternion().setFromRotationMatrix(actor.matrixWorld);
 const visibleCameras=mobile.matches?[selectedCamera]:[0,1,2];
 renderer.setScissorTest(true);
 for(let column=0;column<visibleCameras.length;column++){
  const index=visibleCameras[column],camera=cameras[index];
  const left=Math.floor(width*column/visibleCameras.length),right=Math.floor(width*(column+1)/visibleCameras.length);
  camera.position.copy(target).add(new THREE.Vector3(...cameraOffsets[index]).applyQuaternion(rotation));
  camera.lookAt(target);camera.aspect=(right-left)/height;camera.updateProjectionMatrix();
  renderer.setViewport(left,0,right-left,height);renderer.setScissor(left,0,right-left,height);renderer.render(setup.scene,camera);
 }
 renderer.setScissorTest(false);
}
function applyAt(seconds:number){
 if(disposed||!setup)throw Error('Motion review unavailable');
 syncMotionPreference();
 syncBreathing();
 const before=performance.now();lastLive=setup.controller.apply(seconds) as unknown as LiveFrame;
 metrics.maximum_apply_ms=Math.max(metrics.maximum_apply_ms,performance.now()-before);metrics.frames++;
 metrics.maximum_contact_gap_m=Math.max(metrics.maximum_contact_gap_m,...lastLive.contacts.map(contact=>contact.gap_m));
 metrics.maximum_sole_error_m=Math.max(metrics.maximum_sole_error_m,...lastLive.feet.map(foot=>foot.error_m));
 setup.scene.updateMatrixWorld(true);
 slider.value=String(lastLive.at_s);
 slider.setAttribute('aria-valuetext',decimal(lastLive.at_s)+' из '+decimal(setup.controller.duration_s)+' секунды');
 timeOutput.value=decimal(lastLive.at_s)+' / '+decimal(setup.controller.duration_s)+' с';
 const stage=lastLive.gait_stage,phase=stage==='prepare'?'prepare':stage==='turn_step'?'turn':stage==='settle'||stage==='route_end'?'stop':'walk';
 phaseOutput.textContent={prepare:'Подготовка',walk:'Перенос',turn:'Поворот',stop:'Остановка'}[phase];
 for(const node of document.querySelectorAll<HTMLElement>('[data-phase]')){
  if(node.dataset.phase===phase)node.setAttribute('aria-current','step');else node.removeAttribute('aria-current');
 }
 render();return snapshot();
}
function tick(now:number){
 if(!playing||disposed||!setup)return;
 if(reduced.matches){updateReducedMotion();return;}
 try{
  const time=Math.min(setup.controller.duration_s,elapsed+(now-started)/1000*rate);
  applyAt(time);
  if(time>=setup.controller.duration_s){stop();return;}
  request=requestAnimationFrame(tick);
 }catch(error){fail(error);}
}
function play(){
 if(reduced.matches){updateReducedMotion();return snapshot();}
 if(disposed||!setup||!lastLive||document.hidden)return snapshot();
 if(playing)return snapshot();
 if(lastLive.at_s>=setup.controller.duration_s)applyAt(0);
 elapsed=lastLive.at_s;started=performance.now();playing=true;
 playLabel.textContent='Пауза';playButton.setAttribute('aria-pressed','true');
 const icon=playButton.querySelector('.mr-play-icon');if(icon)icon.textContent='Ⅱ';
 request=requestAnimationFrame(tick);return snapshot();
}
function pause(){stop();return snapshot();}
function seek(seconds:number){stop();return applyAt(seconds);}
function setRate(next:1|.5){
 if(next!==1&&next!==.5)throw Error('Unsupported review playback rate');
 if(playing&&lastLive){elapsed=lastLive.at_s;started=performance.now();}
 rate=next;halfButton.setAttribute('aria-pressed',String(rate===.5));return snapshot();
}
function setCamera(index:number){
 selectedCamera=Math.max(0,Math.min(2,index));
 for(const [i,tab] of tabs.entries()){tab.setAttribute('aria-selected',String(i===selectedCamera));tab.tabIndex=i===selectedCamera?0:-1;}
 host.setAttribute('aria-label',mobile.matches?['Работник с коробкой спереди','Работник с коробкой сбоку','Работник с коробкой в объёме'][selectedCamera]:'Работник с коробкой: спереди, сбоку и в объёме');
 render();
}
function syncMotionPreference(){
 if(reduced.matches)stop();reducedNotice.hidden=!reduced.matches;
 playButton.disabled=root.dataset.state!=='ready'||reduced.matches;
}
function updateReducedMotion(){
 syncMotionPreference();
 if(syncBreathing()&&lastLive)applyAt(lastLive.at_s);
}
function syncBreathing(){
 const enabled=sources?.manifest.breathing===true&&!reduced.matches;
 if(!setup||disposed||activeBreathing===enabled)return false;
 lastLive=setup.controller.setBreathingEnabled(enabled) as unknown as LiveFrame;
 activeBreathing=enabled;return true;
}
function armAnatomy(){
 if(!setup||disposed)return [];
 return (['L','R'] as const).map(side=>{
  const shoulder=joints.get('joint__upper_arm_'+side)!.getWorldPosition(new THREE.Vector3());
  const elbow=joints.get('joint__forearm_'+side)!.getWorldPosition(new THREE.Vector3());
  const wrist=joints.get('joint__palm_roll_'+side)!.getWorldPosition(new THREE.Vector3());
  const upper=elbow.clone().sub(shoulder),forearm=wrist.clone().sub(elbow);
  const upperTilt=THREE.MathUtils.radToDeg(upper.angleTo(new THREE.Vector3(0,-1,0)));
  const elbowInner=THREE.MathUtils.radToDeg(upper.clone().negate().angleTo(forearm));
  return {side,shoulder_world_m:shoulder.toArray(),elbow_world_m:elbow.toArray(),wrist_world_m:wrist.toArray(),upper_direction_world:upper.normalize().toArray(),forearm_direction_world:forearm.normalize().toArray(),upper_tilt_from_down_deg:upperTilt,elbow_inner_deg:elbowInner};
 });
}
function snapshot(){
 const actor=setup?.actor;
 return {
  status:root.dataset.state,disposed,playing,playback_rate:rate,at_s:lastLive?.at_s??0,duration_s:setup?.controller.duration_s??0,
  gait_stage:lastLive?.gait_stage??null,motion_profile:lastLive?.motion_profile??null,render_mode:'live_original_controller',
  carry_pose:lastLive?.carry_pose??sources?.manifest.carry_pose??'source',
  body_asset_path:setup?.bodyAssetPath??null,
  ...(lastLive?.carry_pose==='original_hold'?{forearm_pronation:lastLive.forearm_pronation}:{}),
  arm_anatomy:armAnatomy(),
  grip_support:lastLive?.grip_support??[],
  breathing:lastLive?.breathing??{enabled:false,angle_rad:0},configured_breathing:sources?.manifest.breathing===true,
  actor_id:actor?.actorId??null,role:actor?.role??null,body_uuid:actor?.root.uuid??null,actor_disposed:actor?.disposed??false,
  body_world_matrix:actor?.root.matrixWorld.toArray()??[],
  joints:Object.fromEntries([...joints].map(([name,node])=>[name,{position:node.position.toArray(),quaternion:node.quaternion.toArray(),scale:node.scale.toArray()}])),
  cargo_mesh_uuids:setup?.cargoParts.map(mesh=>mesh.uuid)??[],cargo_world_matrices:setup?.cargoParts.map(mesh=>mesh.matrixWorld.toArray())??[],
  live_contacts:lastLive?.contacts??[],live_feet:lastLive?.feet??[],metrics:{...metrics},
  canvas_count:host.querySelectorAll('canvas').length,selected_camera:selectedCamera,visible_camera_count:mobile.matches?1:3,
  reduced_motion:reduced.matches,cached_source_count:sources?.cachedSourceCount()??0,root_matrix_auto_update:actor?.root.matrixAutoUpdate,
  scope:setup?.scope??null,source_kind:'visual_fixture',engine_operation:false,runtime_scene_joined:false,source_pickup_executed:false,completed_jobs:0,
  binding_disposed:disposed&&setup?setup.controller.bindingSnapshot().disposed:false,
 };
}
function framing(){
 if(!setup||disposed)return [];
 const box=new THREE.Box3().setFromObject(setup.actor.root);
 for(const mesh of setup.cargoParts)box.union(new THREE.Box3().setFromObject(mesh));
 return (mobile.matches?[selectedCamera]:[0,1,2]).map(index=>{
  const points=[0,1,2,3,4,5,6,7].map(bits=>new THREE.Vector3(bits&1?box.max.x:box.min.x,bits&2?box.max.y:box.min.y,bits&4?box.max.z:box.min.z).project(cameras[index]));
  return {camera:index,min_x:Math.min(...points.map(p=>p.x)),max_x:Math.max(...points.map(p=>p.x)),min_y:Math.min(...points.map(p=>p.y)),max_y:Math.max(...points.map(p=>p.y))};
 });
}
const hook={snapshot,seek,play,pause,reset:()=>seek(0),setRate,setCamera,
 framing,destroy:()=>{teardown();root.dataset.state='disposed';return snapshot();},get duration_s(){return setup?.controller.duration_s??0;}};
declare global{interface Window{__QOIMA_MOTION_REVIEW_V3__?:typeof hook}}

async function boot(){
 sources=await loadMotionReviewSources(new URL('./data/v3/motion-review/manifest.json',document.baseURI),fetchLifetime.signal);
 const loaded=await createMotionReviewSetup(sources.readSource,{carry_pose:sources.manifest.carry_pose,breathing:sources.manifest.breathing,worker_model_path:sources.manifest.worker_model_path});
 if(disposed){loaded.dispose();sources.clear();return;}
 setup=loaded;
 activeBreathing=sources.manifest.breathing===true;
 if(Math.abs(setup.controller.duration_s-sources.manifest.duration_s)>1e-9)throw Error('Motion duration differs from the accepted source');
 setup.actor.root.traverse(node=>{if(node.name.startsWith('joint__'))joints.set(node.name,node);});
 renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});
 renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputColorSpace=THREE.SRGBColorSpace;
 renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;
 renderer.domElement.setAttribute('aria-hidden','true');host.append(renderer.domElement);
 renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();if(!disposed)fail(Error('3D context lost'));},{signal:lifetime.signal});
 slider.max=String(setup.controller.duration_s);
 applyAt(0);
 observer=new ResizeObserver(render);observer.observe(host);
 playButton.addEventListener('click',()=>{try{if(playing)pause();else play();}catch(error){fail(error);}},{signal:lifetime.signal});
 resetButton.addEventListener('click',()=>{try{seek(0);}catch(error){fail(error);}},{signal:lifetime.signal});
 halfButton.addEventListener('click',()=>setRate(rate===1?.5:1),{signal:lifetime.signal});
 slider.addEventListener('input',()=>{try{seek(Number(slider.value));}catch(error){fail(error);}},{signal:lifetime.signal});
 for(const [index,tab] of tabs.entries()){
  tab.addEventListener('click',()=>setCamera(index),{signal:lifetime.signal});
  tab.addEventListener('keydown',event=>{
   let next=index;
   if(event.key==='ArrowRight')next=(index+1)%3;
   else if(event.key==='ArrowLeft')next=(index+2)%3;
   else if(event.key==='Home')next=0;else if(event.key==='End')next=2;else return;
   event.preventDefault();setCamera(next);tabs[next].focus();
  },{signal:lifetime.signal});
 }
 document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();},{signal:lifetime.signal});
 reduced.addEventListener('change',updateReducedMotion,{signal:lifetime.signal});
 mobile.addEventListener('change',()=>setCamera(selectedCamera),{signal:lifetime.signal});
 root.querySelectorAll<HTMLButtonElement|HTMLInputElement>('button,input').forEach(control=>{control.disabled=false;});
 root.dataset.state='ready';loading.hidden=true;setCamera(selectedCamera);updateReducedMotion();
 window.__QOIMA_MOTION_REVIEW_V3__=hook;
}
addEventListener('pagehide',teardown,{once:true});
if(import.meta.hot)import.meta.hot.dispose(teardown);
void boot().catch(error=>{if(!disposed)fail(error);});
