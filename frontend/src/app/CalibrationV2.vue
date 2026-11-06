<script setup lang="ts">
import {onMounted,onBeforeUnmount,ref} from 'vue';
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls.js';
const host=ref<HTMLDivElement>();const phase=ref('loading');const error=ref('');const diagnostics=ref<Record<string,unknown>>({});
let disposed=false;let cleanup=()=>{};
onMounted(async()=>{
  Object.assign(window,{__QOIMA_CALIBRATION_V2__:undefined});
  try{
    const gltf=await new GLTFLoader().loadAsync(`${import.meta.env.BASE_URL}models/v2/calibration-v2.glb`);
    const release=()=>gltf.scene.traverse(object=>{if(object instanceof THREE.Mesh){object.geometry.dispose();(Array.isArray(object.material)?object.material:[object.material]).forEach(material=>material.dispose());}});
    cleanup=release;
    if(disposed){release();return;}
    gltf.scene.updateMatrixWorld(true);const positions:Record<string,number[]>={};const sizes:Record<string,number[]>={};
    let metadata:Record<string,unknown>|undefined;
    gltf.scene.traverse(object=>{
      if(object.userData.asset_id==='calibration-v2')metadata=object.userData;
      if(object.name.startsWith('calibration_anchor__')||object.name.startsWith('calibration_axis_end__'))positions[object.name]=object.getWorldPosition(new THREE.Vector3()).toArray();
      if(object.userData.calibration_asset)sizes[object.userData.calibration_asset]=new THREE.Box3().setFromObject(object).getSize(new THREE.Vector3()).toArray();
    });
    if(!metadata||metadata.layout_version!=='qoima-72x48-v2')throw new Error('GLB calibration version does not match v2');
    const expected=JSON.parse(String(metadata.expected_runtime_anchors_json)) as Record<string,number[]>;
    for(const key of ['origin','worker_floor','worker_head','rack_floor','belt_top','rack_bin_01','rack_bin_02','rack_bin_03'])if(!Array.isArray(expected[key])||expected[key].length!==3)throw new Error('Missing calibration anchor: '+key);
    for(const [name,target]of Object.entries(expected)){
      const actual=positions['calibration_anchor__'+name];if(!actual||actual.some((value,index)=>Math.abs(value-target[index])>.02))throw new Error('Calibration anchor mismatch: '+name);
    }
    for(const [axis,target]of Object.entries({X:[1,0,0],Y:[0,1,0],Z:[0,0,1]})){
      const actual=positions['calibration_axis_end__'+axis];if(!actual||actual.some((value,index)=>Math.abs(value-target[index])>.02))throw new Error('Calibration axis mismatch: '+axis);
    }
    if(!sizes['standing-worker']||!sizes['rack-high']||!sizes['conveyor-high']||Math.abs(sizes['standing-worker'][1]-1.7)>.02||Math.abs(sizes['rack-high'][1]-5.4)>.02)throw new Error('Calibration model dimensions mismatch');
    const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(1);renderer.outputColorSpace=THREE.SRGBColorSpace;
    renderer.toneMapping=THREE.ACESFilmicToneMapping;host.value!.appendChild(renderer.domElement);
    const scene=new THREE.Scene();scene.background=new THREE.Color('#e6e7e0');scene.add(gltf.scene,new THREE.HemisphereLight(0xfff4db,0x7a8b89,2));
    const light=new THREE.DirectionalLight(0xffffff,2.5);light.position.set(-5,12,8);scene.add(light);
    const camera=new THREE.PerspectiveCamera(40,1,.01,100);camera.position.set(10,7,12);
    const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(3,2.2,0);controls.update();
    const resize=()=>{renderer.setSize(host.value!.clientWidth,host.value!.clientHeight);camera.aspect=host.value!.clientWidth/host.value!.clientHeight;camera.updateProjectionMatrix();};resize();
    const observer=new ResizeObserver(resize);observer.observe(host.value!);let raf=0;
    const draw=()=>{controls.update();renderer.render(scene,camera);raf=requestAnimationFrame(draw);};draw();
    cleanup=()=>{cancelAnimationFrame(raf);observer.disconnect();controls.dispose();renderer.dispose();release();};
    diagnostics.value={webgl:true,localGlb:true,layoutVersion:metadata.layout_version,positions,sizes};
    Object.assign(window,{__QOIMA_CALIBRATION_V2__:diagnostics.value});phase.value='ready';
  }catch(reason){cleanup();error.value=String(reason);phase.value='error';}
});
onBeforeUnmount(()=>{disposed=true;cleanup();});
</script>
<template><main class="calibration-v2" :data-phase="phase"><div ref="host" class="calibration-canvas"></div><aside><a href="./">← Большой склад</a><h1>Калибровка v2</h1><p>Метры · Y вверх · человек 1,7 м · rack 5,4 м · лента 0,9 м</p><p v-if="phase!=='ready'" role="status">{{error||'Загрузка GLB…'}}</p><details><summary>Координаты после GLB</summary><pre id="diagnostics-v2">{{JSON.stringify(diagnostics,null,2)}}</pre></details></aside></main></template>
<style>.calibration-v2{height:100dvh;position:relative;background:#e6e7e0}.calibration-canvas{position:absolute;inset:0}.calibration-v2 aside{position:absolute;left:28px;top:25px;max-width:440px;padding:18px;background:#f4f2e4dd;font:12px 'Segoe UI',sans-serif}.calibration-v2 h1{font-size:22px;font-weight:400}.calibration-v2 pre{max-height:220px;overflow:auto;font-size:10px}.calibration-v2 a{color:#46614f}</style>
