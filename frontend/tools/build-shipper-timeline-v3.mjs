import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,stat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
import ts from 'typescript';
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

const front=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),root=path.dirname(front),cache=path.join(root,'work/v3/shipper-elbow-diagnosis/builder'),hash=b=>createHash('sha256').update(b).digest('hex'),hashes={};
async function source(p){const b=await readFile(path.join(root,p));hashes[p]=hash(b);return b;}
await mkdir(cache,{recursive:true});
for(const [folder,name]of [['motion/','shipper'],['','workerRoles'],['','workerRolesFixture']]){
 let code=ts.transpileModule((await source('frontend/src/adaptive-v3/'+folder+name+'.ts')).toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
 code=code.replace(/from '(three(?:\/[^']+)?)'/g,(_,p)=>'from '+JSON.stringify(pathToFileURL(path.join(front,'node_modules',p==='three'?'three/build/three.module.js':p)).href)).replace(/from '(\.\/\w+)'/g,"from '$1.mjs'");await writeFile(path.join(cache,name+'.mjs'),code);
}
const {createWorkerInstance,disposeWorkerInstance}=await import(pathToFileURL(path.join(cache,'workerRoles.mjs'))),{solveShipperArmPose,validateShipperTimeline,SHIPPER_CONTACT_TANGENT_TWIST_RAD}=await import(pathToFileURL(path.join(cache,'shipper.mjs')));
const original=await source('frontend/public/data/v3/packer-seam-end.json'),base=JSON.parse(original),labels=['Ожидание посылки','Проверка этикетки','Этикетка проверена','Подвод руки','Подвод к посылке','Укладка на выход','Посылка установлена','Возврат руки','Возврат руки','Отход от ленты','Возврат в ожидание','Проверка завершена','Отгрузка подготовлена','Готово'];
const keys=base.keys.map((k,i)=>({t:k.t*2+(k.t>2.7?6:0)+(k.t>5.5?6:0),label:labels[i],joints:Object.fromEntries(Object.entries(k.joints).filter(([name])=>name.endsWith('_R')||name==='joint__head'))}));
const d={schema_id:'qoima.visual-shipper.v3',source_kind:'visual_fixture',engine_operation:false,units:'m',duration_s:27,scan_duration_s:2.5,body_root_m:[-.39,0,1.85],body_yaw_rad:Math.PI,package_id:'v3:fixture:package:SMALL001',contents_HU_ref:'v3:fixture:HU:SMALL001',pallet_HU_ref:'v3:fixture:HU:OUTBOUND01',contact:{local_m:base.contacts.R.local_m,workcell_m:[-.69,1.17,1.39],surface:'rear_paper_and_tape'},placement:{start_s:5.4,duration_s:6,distance_m:.16,pelvis_drop_m:.008,swing_lift_m:.012,cycles:2,return_start_s:17,return_duration_s:6},keys,scope:'Prepared visual scan and160mm supported placement of one existing1.02kg parcel on the stopped outbound belt. Real hand-wall contact and two grounded step-together cycles; heavy455kgpallet remains staged for mechanical dispatch. No stock creation, actual decoding/engine shipment or cycle-time claim.',provenance:{P04_timeline_sha256:hash(original)}};
const loader=new GLTFLoader(),loaded=[];
async function native(name,node){const bytes=await source('frontend/public/models/v3/'+name+'.glb'),scene=(await loader.parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'')).scene;loaded.push(scene);return scene.getObjectByName(node);}
const cell=await native('shipper-workcell-fixture','shipper_workcell_root'),template=await native('worker-manual','worker_base_root'),actor=createWorkerInstance(template,'S01','shipper');
try{
 cell.add(actor.root);actor.root.position.fromArray(d.body_root_m);actor.root.rotation.y=d.body_yaw_rad;cell.updateWorldMatrix(true,true);
 // Select the native flexion branch, then solve the whole short noncontact approach.
 const seed={joint__shoulder_lift_R:[0,0,0],joint__upper_arm_R:[-1.554535414553638,.22,.5004477981549706],joint__forearm_R:[-.9385946275559596,0,0],joint__elbow_swivel_R:[1.2,0,0],joint__palm_roll_R:[0,-3*Math.PI/16,0],joint__hand_R:[0,0,0]};
 const poses=new Map();for(const gap of [0,.01,.02])poses.set(gap,solveShipperArmPose(actor.root,cell,seed,[d.contact.workcell_m[0],d.contact.workcell_m[1],d.contact.workcell_m[2]+gap],d.contact.local_m));
 for(let i=3;i<=9;i++){const gap=i===3||i===9?.02:i===5||i===6?0:.01;Object.assign(keys[i].joints,structuredClone(poses.get(gap)));}
 d.provenance.worker_manual_glb_sha256=hashes['frontend/public/models/v3/worker-manual.glb'];d.provenance.workcell_glb_sha256=hashes['frontend/public/models/v3/shipper-workcell-fixture.glb'];d.provenance.arm_solver_sha256=hashes['frontend/src/adaptive-v3/motion/shipper.ts'];d.provenance.contact_tangent_twist_rad=SHIPPER_CONTACT_TANGENT_TWIST_RAD;d.provenance.pose_scope='P06.4 native low-pole branch with original contact point/normal/body/timings and tangent twist; noncontact lead gaps1cm/2cm';
 validateShipperTimeline(d);for(const [p,h]of Object.entries(hashes))assert.equal(hash(await readFile(path.join(root,p))),h,'Concurrent builder input drift: '+p);
 const output=path.join(front,'public/data/v3/shipper-v3.json'),result=JSON.stringify(d,null,2)+'\n';
 if(process.argv.includes('--check-only')){const before=await stat(output),bytes=await readFile(output);assert.equal(bytes.toString(),result,'Shipper timeline must be regenerated');assert.equal((await stat(output)).mtimeMs,before.mtimeMs);}else await writeFile(output,result);
 console.log(JSON.stringify({keys:keys.length,duration_s:d.duration_s,scan_duration_s:d.scan_duration_s,check_only:process.argv.includes('--check-only'),candidate_only:true,timeline_sha256:hash(result)}));
}finally{disposeWorkerInstance(actor);const disposed=new Set();for(const scene of loaded)scene.traverse(n=>{if(n instanceof THREE.Mesh)for(const r of [n.geometry,...(Array.isArray(n.material)?n.material:[n.material])])if(!disposed.has(r)){disposed.add(r);r.dispose();}});}
