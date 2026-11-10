import fs from 'node:fs/promises';
import * as T from '../../../../../frontend/node_modules/three/build/three.module.js';
import {GLTFLoader} from '../../../../../frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js';
const b=await fs.readFile('frontend/public/models/v3/worker-base.glb');
const {scene}=await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'');
const root=scene.getObjectByName('worker_base_root');
const seat=new T.Vector3(0,.84,-.65);
root.position.copy(seat.clone().sub(new T.Vector3(0,.55,-.035)));
for(const s of ['L','R']) {
 scene.getObjectByName('joint__thigh_'+s).rotation.x=-Math.PI/2;
 scene.getObjectByName('joint__shin_'+s).rotation.x=Math.PI/2;
 scene.getObjectByName('joint__upper_arm_'+s).rotation.x=-.55;
 scene.getObjectByName('joint__forearm_'+s).rotation.x=-1.0;
 scene.getObjectByName('joint__upper_arm_'+s).rotation.z=s==='L'?.23:-.23;
}
scene.updateMatrixWorld(true);
const total=new T.Box3();
root.traverse(n=>{
 if(n.userData.anchor_id)console.log(n.name,n.getWorldPosition(new T.Vector3()).toArray());
 if(n.isMesh){const box=new T.Box3().setFromObject(n,true);total.union(box);console.log(n.parent.name,JSON.parse(n.userData.source_parts_json),box.min.toArray(),box.max.toArray());}
});
console.log('TOTAL',total.min.toArray(),total.max.toArray());
