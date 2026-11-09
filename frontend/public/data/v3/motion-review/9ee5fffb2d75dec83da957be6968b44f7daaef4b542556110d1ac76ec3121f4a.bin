import{readFile,writeFile}from'node:fs/promises';
import{createHash}from'node:crypto';
import ts from'typescript';
const hash=b=>createHash('sha256').update(b).digest('hex'),inputs={};
async function source(p){const b=await readFile('../'+p);inputs[p]=hash(b);return b;}
const original=JSON.parse(await source('contracts/actors.example.json')),policy=JSON.parse(await source('docs/v3/contract-proposals/port-resource-policy-v3.json'));
if(original.actors.length!==24||JSON.stringify(original.actors.map(a=>a.actor_id))!==JSON.stringify(policy.actor_ids))throw Error('Canonical24actor/policy mismatch');
const text=(await source('frontend/src/adaptive-v3/workerRoles.ts')).toString(),ast=ts.createSourceFile('workerRoles.ts',text,ts.ScriptTarget.Latest,true);let declaration;
function visit(n){if(ts.isVariableDeclaration(n)&&n.name.getText(ast)==='WORKER_ROLE_DEFINITIONS')declaration=n;ts.forEachChild(n,visit);}visit(ast);
function literal(n){if(ts.isCallExpression(n)&&n.expression.getText(ast)==='Object.freeze')return literal(n.arguments[0]);if(ts.isObjectLiteralExpression(n))return Object.fromEntries(n.properties.map(p=>[p.name.text??p.name.getText(ast),literal(p.initializer)]));if(ts.isStringLiteral(n))return n.text;throw Error('Role definitions must remain explicit frozen literals');}
const definitions=literal(declaration.initializer),labels={picker:'Комплектовщик',packer:'Упаковщик',receiver:'Приёмщик',shipper:'Отгрузчик',forklift_driver:'Водитель погрузчика'};
const roles=Object.entries(definitions).map(([role,d])=>({role,label:labels[role],...d,count:original.actors.filter(a=>a.role===role).length}));
async function clip(id,role,label,asset_id,fixture,mode,duration_s,task,data_paths,prerequisites,fixture_actor_id,canonical_actor_id){
 const proofPath=`docs/adaptive-v3/evidence/${task}.json`,proofBytes=await source(proofPath),proof=JSON.parse(proofBytes);
 if(proof.passed!==true&&proof.status!=='PASS')throw Error('Unaccepted clip proof '+task);
 const sources=[];for(const p of data_paths){await source(p);sources.push({path:p,sha256:inputs[p]});}
 return {clip_id:id,role,label,asset_id,fixture,mode,duration_s,clock_kind:duration_s?'explanatory_visual_clock':'static_pose',accepted_task:task,proof:{path:proofPath,sha256:hash(proofBytes)},sources,prerequisites,fixture_actor_id,canonical_actor_id,warehouse_joined:false};
}
const clips=[];
clips.push(await clip('picker_idle','picker','Ожидание','worker-manual',null,null,0,'P03',['frontend/public/models/v3/worker-manual.glb'],'Исходная поза; свободные руки.','P01','P01'));
clips.push(await clip('picker_walk','picker','Ведение тележки','picking-cart-tote-fixture','walk',null,9,'P03',['frontend/public/data/v3/picker-cart-walk.json','frontend/public/data/v3/picker-push-pose.json'],'Существующая тележка и лоток; хват уже установлен.','P01','P01'));
clips.push(await clip('picker_pick','picker','Отбор SMALL в лоток','picker-pick-source-fixture','pick',null,36,'P03.5.3.3',['frontend/public/models/v3/small-pick-v3.json','frontend/public/models/v3/worker-small-pick.glb'],'Подготовленный ручной захват; исходные упаковки14/17/20/23 и лоток. Получение/укладка инструмента — отдельное действие.','P01','P01'));
for(const[role,asset,fixture,task,data,modes,actor]of[
 ['packer','packer-workcell-fixture','packer','P04','packer-seam-end.json',[['finish','Финальная проверка ленты','pack',7.5],['idle','Ожидание','idle',0],['blocked','Пост занят','blocked',0]],'K01'],
 ['receiver','receiver-workcell-fixture','receiver','P05','receiver-v3.json',[['scan','Проверка этикетки','scan',2.5],['receive','Подтверждение приёмки','receive',17.8],['idle','Ожидание','idle',0],['blocked','Пост занят','blocked',0]],'R01'],
 ['shipper','shipper-workcell-fixture','shipper','P06','shipper-v3.json',[['scan','Проверка этикетки','scan',2.5],['place','Укладка на выход','place',27],['idle','Ожидание','idle',0],['blocked','Выход занят','blocked',0]],'S01']]){
 const pre=role==='packer'?'Уже закрытая исходная посылка на опоре; клип не складывает коробку и не создаёт содержимое.':role==='receiver'?'Исходная паллета уже на полу у сканера; реальная перевозка и backend-приёмка не выполняются.':'Лёгкая исходная посылка уже на ленте; отдельная тяжёлая паллета на полу для механизированной отгрузки.';
 for(const[suffix,label,mode,duration]of modes)clips.push(await clip(role+'_'+suffix,role,label,asset,fixture,mode,duration,task,['frontend/public/data/v3/'+data,'frontend/public/models/v3/worker-manual.glb'],pre,role==='packer'?'PK01':actor,actor));
}
clips.push(await clip('driver_seated','forklift_driver','В кабине · ожидание','forklift','driver',null,0,'P07',['frontend/public/data/v3/seated-driver-pose.json','frontend/public/models/v3/worker-base.glb'],'Посадка уже установлена; вход/выход из кабины — отдельные действия.','F01','F01'));
clips.push(await clip('driver_pickup','forklift_driver','Подхват и установка паллеты','forklift-pallet-low-fixture','pickup',null,30,'P07',['frontend/public/data/v3/pallet-pickup-cycle.json','frontend/public/data/v3/seated-driver-pose.json'],'Существующая техника, закреплённый водитель и подготовленная паллета; маршрут склада ещё не соединён с клипом.','F01','F01'));
const workers=original.actors.map(a=>({actor_id:a.actor_id,baseline_role:a.role,initial_role:a.role,clip_ids:clips.filter(c=>c.role===a.role).map(c=>c.clip_id),assigned_vehicle_id:a.vehicle_id??null,legacy_station_ref:a.pack_id??null}));
await source('frontend/tools/build-worker-registry-v3.mjs');
const registry={schema_id:'qoima.visual-worker-registry.v3',namespace:'v3',layout_version:'qoima-144x72-v3',source_kind:'visual_fixture',engine_operation:false,operational_admission:false,actor_count:24,vehicle_count:2,packing_station_count:6,roles,workers,vehicles:original.vehicles.map(v=>({vehicle_id:v.vehicle_id,driver_actor_id:v.driver_actor_id})),clips,fixture_aliases:[{fixture_actor_id:'PK01',canonical_actor_id:'K01',clip_ids:clips.filter(c=>c.role==='packer').map(c=>c.clip_id),scope:'Retained isolated P04 QA actor alias; original canonical PK01 is a station, K01 is the worker. Never an extra employee.'}],source_hashes:inputs,scope:'Canonical24IDs/baseline roles and accepted prepared visual clips only. V2 coordinates are not reused; current warehouse placement/joins and P11 skill profiles remain separate. No backend staff update or actual engine run.'};
await writeFile('public/data/v3/worker-registry-v3.json',JSON.stringify(registry,null,2)+'\n');console.log(JSON.stringify({actor_count:workers.length,roles:roles.map(r=>[r.role,r.count]),clips:clips.length,engine_operation:false}));
