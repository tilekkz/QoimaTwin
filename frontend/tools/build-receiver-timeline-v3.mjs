import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {solveReceiverArmPath} from './solve-receiver-v3.mjs';
const front=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),sha=b=>createHash('sha256').update(b).digest('hex');
const source=await readFile(path.join(front,'public/data/v3/packer-seam-end.json')),previous=JSON.parse(source),arm=await solveReceiverArmPath();
const labels=['Ожидание паллеты','Сканирование этикетки','Этикетка проверена','Подвод к терминалу','Подтверждение приёмки','Нажатие подтверждения','Паллета принята','Возврат руки','Возврат руки','Возврат в ожидание','Проверка паллеты','Проверка завершена','Приёмка завершена','Готово'];
const keys=previous.keys.map((k,i)=>({t:k.t<=1.1?k.t*2:k.t<=5.5?k.t*2+1.6:k.t<=6.1?12.6+(k.t-5.5)/.6*2.4:k.t*2+2.8,label:labels[i],joints:Object.fromEntries(Object.entries(k.joints).filter(([name])=>name.endsWith('_R')||name==='joint__head'))}));
for(let i=3;i<=9;i++)Object.assign(keys[i].joints,arm.poses[i===3||i===9?'approach':i===5||i===6?'contact':'lead']);
const timeline={schema_id:'qoima.visual-receiver.v3',source_kind:'visual_fixture',engine_operation:false,units:'m',duration_s:17.8,body_root_m:arm.body_root_m,body_yaw_rad:arm.body_yaw_rad,HU_ref:'v3:fixture:HU:RECEIVE01',preparation:{duration_s:2.4,return_duration_s:2.4,abduction_z_rad:.15,windows:{upper:[0,1],fold:[0,1],swivel:[0,1],hand:[0,1]},waypoints:arm.preparation_waypoints},contact:arm.contact,keys,
 scope:'Visual scanning cue and actual terminal confirmation of one already floor-supported pallet. Original17.8s clock and ordered preparation retained. P05.4 uses the low elbow branch and a2cm-to1cm free approach; the terminal contact point and opposed pad/screen normals, body, rig, HU and numeric limits are unchanged. No human pallet lift, stock creation or backend receipt.',
 provenance:{P04_timeline_sha256:sha(source),arm_solution_input_hashes:arm.input_hashes,natural_elbow_branch:{shoulder_yaw_rad:-.2,elbow_swivel_rad:1.5,palm_roll_rad:-5*Math.PI/16,tangent_twist_rad:Math.PI/6,free_approach_gap_m:[.02,.01],contact_lead_gap_m:.01},historical_contact_evidence_is_current_acceptance:false}};
const target=path.join(front,'public/data/v3/receiver-v3.json'),bytes=JSON.stringify(timeline,null,2)+'\n';
if(process.argv.includes('--check-only'))assert.equal(await readFile(target,'utf8'),bytes,'Receiver timeline is not reproducible from current source');else await writeFile(target,bytes);
console.log(JSON.stringify({check_only:process.argv.includes('--check-only'),keys:keys.length,actor:'R01',HU:timeline.HU_ref,duration_s:17.8,sha256:sha(bytes),endpoint_only:true}));
