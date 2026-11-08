import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../..');
const {GLTFLoader}=await import(pathToFileURL(path.join(root,'frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js')));
const b=await readFile(path.join(root,'frontend/public/models/v3/worker-base.glb'));
const s=(await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene;
for(const name of ['worker_base_root','joint__pelvis','joint__torso','joint__head','joint__upper_arm_L','joint__forearm_L','joint__palm_roll_L','joint__hand_L']){const n=s.getObjectByName(name);console.log(JSON.stringify({name,parent:n.parent?.name,position:n.position.toArray(),rotation:n.rotation.toArray(),scale:n.scale.toArray(),data:n.userData}));}
const j=JSON.parse(await readFile(path.join(root,'frontend/public/data/adaptive-v3/layout-manifest.json'),'utf8'));
for(const k of ['modules','slots'])console.log(k,JSON.stringify(j.data.storage[k].columns));
const f=JSON.parse(await readFile(path.join(root,'frontend/public/data/v3/warehouse-fixture-v3.json'),'utf8'));console.log('sourceHU',JSON.stringify(f.inputs.initial_stock.find(x=>x.handling_unit_id==='v3:HU:initial:DEMO_095:04')));
