import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {createWorkerInstance,disposeWorkerInstance} from '../../../frontend/src/adaptive-v3/workerRoles.ts';
import {attachLiveCalibration} from './controller.mjs?revision=3291e8a9f70286e1527a7153f954b96941f9f419cdb64d58cceb4aa059dfe53d';

const host=document.querySelector('#views'),slider=document.querySelector('#timeline'),playButton=document.querySelector('#play');
const sha=async b=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(v=>v.toString(16).padStart(2,'0')).join('');
const fetched=async url=>{const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error(url+' HTTP '+r.status);return r.arrayBuffer();};
let renderer,observer,actor,controller,request=0,disposed=false;
try{
 const manifest=JSON.parse(new TextDecoder().decode(await fetched('./manifest.json')));
 const traceBytes=await fetched('./trace.json');if(await sha(traceBytes)!==manifest.trace_sha256)throw Error('Replay fingerprint mismatch');
 const trace=JSON.parse(new TextDecoder().decode(traceBytes));
 if(!trace.calibration_only||trace.engine_operation!==false||trace.completed_jobs!==0)throw Error('Wrong replay scope');
 const models=['worker-base','small-carton'];
 const bytes=await Promise.all(models.map(async id=>{const data=await fetched('/models/v3/'+id+'.glb');if(await sha(data)!==manifest.sources['frontend/public/models/v3/'+id+'.glb'])throw Error('Native GLB fingerprint mismatch: '+id);return data;}));
 const loader=new GLTFLoader(),[body,cargo]=await Promise.all(bytes.map(b=>loader.parseAsync(b,'')));
 actor=createWorkerInstance(body.scene,'P02','picker');
 const scene=new THREE.Scene();scene.background=new THREE.Color('#e7e9e4');scene.add(actor.root);
 const rawSources=new Map();
 const source=async path=>{if(!rawSources.has(path))rawSources.set(path,(async()=>{const pin=manifest.source_paths?.[path];if(!pin)throw Error('Unpinned live source: '+path);const data=await fetched(pin.url);if(await sha(data)!==pin.sha256)throw Error('Live source fingerprint mismatch '+path);return new Uint8Array(data);})());return rawSources.get(path);};
 const attached=await attachLiveCalibration({scene,actor,cargoTemplate:cargo.scene,source,manifest});controller=attached.controller;const cargoParts=attached.cargoParts;
 if(cargoParts.length!==4)throw Error('Expected the same four original cargo parts');
 scene.add(new THREE.HemisphereLight('#ffffff','#5d6b67',2.2));
 for(const[position,intensity]of [[[12,8,52],2.2],[[2,7,44],1.3],[[7,6,32],1.8]]){const light=new THREE.DirectionalLight('#fff8ee',intensity);light.position.set(...position);scene.add(light);}
 const floor=new THREE.Mesh(new THREE.PlaneGeometry(144,72),new THREE.MeshStandardMaterial({color:'#c9d0c9',roughness:1}));floor.rotation.x=-Math.PI/2;floor.position.set(72,-.0005,36);scene.add(floor);
 const grid=new THREE.GridHelper(32,64,'#91a99c','#b8c6bb');grid.position.set(8,-.0003,40);scene.add(grid);
 const routeGeometry=new THREE.BufferGeometry().setFromPoints([[10.75,.001,49],[6,.001,49],[6,.001,38]].map(p=>new THREE.Vector3(...p)));
 scene.add(new THREE.Line(routeGeometry,new THREE.LineBasicMaterial({color:'#b69b66'})));
 renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;host.append(renderer.domElement);
 renderer.domElement.setAttribute('aria-label','Три ракурса одного работника с коробкой');
 const cameras=[0,1,2].map(()=>new THREE.PerspectiveCamera(35,1,.01,150)),nodes=new Map();actor.root.traverse(n=>{if(n.name.startsWith('joint__'))nodes.set(n.name,n);});
 const reduced=matchMedia('(prefers-reduced-motion: reduce)'),frames=trace.frames;
 let index=0,playing=false,started=0,elapsed=0,lastLive=controller.snapshot();
 const metrics={frames:0,maximum_apply_ms:0,maximum_contact_gap_m:0,maximum_sole_error_m:0};
 function render(){const width=Math.max(1,host.clientWidth),height=Math.max(1,host.clientHeight);renderer.setSize(width,height,false);const target=new THREE.Vector3(0,.80,.18).applyMatrix4(actor.root.matrixWorld),rotation=new THREE.Quaternion().setFromRotationMatrix(actor.root.matrixWorld);const offsets=[[0,.20,3.2],[3.2,.30,.05],[2.55,1.1,2.55]];renderer.setScissorTest(true);for(let i=0;i<3;i++){const left=Math.floor(width*i/3),right=Math.floor(width*(i+1)/3),camera=cameras[i];camera.position.copy(target).add(new THREE.Vector3(...offsets[i]).applyQuaternion(rotation));camera.lookAt(target);camera.aspect=(right-left)/height;camera.updateProjectionMatrix();renderer.setViewport(left,0,right-left,height);renderer.setScissor(left,0,right-left,height);renderer.render(scene,camera);}renderer.setScissorTest(false);}
 function applyAt(seconds){if(disposed)throw Error('Replay disposed');const before=performance.now();lastLive=controller.apply(seconds);metrics.maximum_apply_ms=Math.max(metrics.maximum_apply_ms,performance.now()-before);metrics.frames++;metrics.maximum_contact_gap_m=Math.max(metrics.maximum_contact_gap_m,...lastLive.contacts.map(c=>c.gap_m));metrics.maximum_sole_error_m=Math.max(metrics.maximum_sole_error_m,...lastLive.feet.map(f=>f.error_m));index=find(lastLive.at_s);scene.updateMatrixWorld(true);slider.value=String(lastLive.at_s);document.querySelector('#state').textContent=lastLive.at_s.toFixed(2)+' / '+controller.duration_s.toFixed(2)+' с · '+lastLive.gait_stage;render();return snapshot();}
 function find(t){let a=0,b=frames.length-1;while(a<b){const m=Math.floor((a+b)/2);if(frames[m].at_s<t)a=m+1;else b=m;}return a>0&&Math.abs(frames[a-1].at_s-t)<Math.abs(frames[a].at_s-t)?a-1:a;}
 function stop(){playing=false;cancelAnimationFrame(request);request=0;playButton.textContent='Воспроизвести';playButton.setAttribute('aria-pressed','false');}
 function tick(now){if(!playing||disposed)return;try{const t=Math.min(controller.duration_s,elapsed+(now-started)/1000);applyAt(t);if(t>=controller.duration_s){stop();return;}request=requestAnimationFrame(tick);}catch(error){stop();document.querySelector('#error').textContent=String(error?.stack??error);}}
 function snapshot(){const f=lastLive;return {index,at_s:f.at_s,gait_stage:f.gait_stage,playing,disposed,passed_native_gate:trace.passed_native_gate,render_mode:'live_original_controller',motion_profile:f.motion_profile,trace_reference_only:true,live_contacts:f.contacts,live_feet:f.feet,metrics:{...metrics},actor_id:actor.actorId,role:actor.role,body_uuid:actor.root.uuid,body_world_matrix:actor.root.matrixWorld.toArray(),cargo_mesh_uuids:cargoParts.map(n=>n.uuid),cargo_world_matrices:cargoParts.map(n=>n.matrixWorld.toArray()),joints:Object.fromEntries([...nodes].map(([name,n])=>[name,{position:n.position.toArray(),quaternion:n.quaternion.toArray(),scale:n.scale.toArray()}])),canvas_count:host.querySelectorAll('canvas').length,source_kind:'visual_fixture',engine_operation:false,runtime_scene_joined:false,source_pickup_executed:false,completed_jobs:0};}
 playButton.onclick=()=>{if(playing){stop();return;}if(document.hidden||reduced.matches)return;if(lastLive.at_s===controller.duration_s)applyAt(0);playing=true;elapsed=lastLive.at_s;started=performance.now();playButton.textContent='Пауза';playButton.setAttribute('aria-pressed','true');request=requestAnimationFrame(tick);};
 document.querySelector('#start').onclick=()=>{stop();applyAt(0);};slider.max=String(controller.duration_s);slider.oninput=()=>{stop();applyAt(Number(slider.value));};
 document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});reduced.addEventListener('change',()=>{if(reduced.matches)stop();});
 document.querySelector('#verdict').textContent=(manifest.motion_style==='grounded_carry'?'Спокойный перенос с двойной опорой':'Исходный темп переноса')+' · контакт с грузом и опора стоп проверяются при каждом кадре.';
 document.querySelector('#fingerprint').textContent='След SHA256 '+manifest.trace_sha256+' · '+frames.length+' точных кадров';
 for(const button of document.querySelectorAll('button,input'))button.disabled=false;
 observer=new ResizeObserver(render);observer.observe(host);applyAt(0);
 window.__loadedWalkReplay={snapshot,seek:t=>{stop();return applyAt(t);},frame:i=>{stop();return applyAt(frames[i].at_s);},duration_s:controller.duration_s,source_hashes:manifest.sources,trace_sha256:manifest.trace_sha256};
 addEventListener('pagehide',()=>{stop();disposed=true;observer.disconnect();const resources=new Set();for(const root of [scene,body.scene,cargo.scene])root.traverse(n=>{if(n.geometry&&n.material){resources.add(n.geometry);for(const m of Array.isArray(n.material)?n.material:[n.material]){resources.add(m);for(const value of Object.values(m))if(value?.isTexture)resources.add(value);}}});const released=new WeakSet();for(const r of resources)r.addEventListener('dispose',()=>released.add(r));controller.dispose();disposeWorkerInstance(actor);for(const r of resources)if(!released.has(r))r.dispose();rawSources.clear();renderer.dispose();renderer.forceContextLoss();},{once:true});
}catch(error){document.querySelector('#error').textContent=String(error?.stack??error);observer?.disconnect();renderer?.dispose();}
