import{readFile,writeFile}from'node:fs/promises';
import{createHash}from'node:crypto';
import{mkdir}from'node:fs/promises';
import{pathToFileURL}from'node:url';
import path from'node:path';
import ts from'typescript';
import*as T from'three';
import{GLTFLoader}from'three/examples/jsm/loaders/GLTFLoader.js';
const out='../assets/v3/iterations/packer/P04.1/',left=JSON.parse(await readFile(out+'table-L-native.json','utf8')).admitted[0],right=JSON.parse(await readFile(out+'front-tail-R-native.json','utf8')).admitted.find(r=>r.body.root[0]===.3&&r.body.root[2]===.7&&r.body.lean===0);
if(!left||!right)throw Error('Native candidate missing');
const b=await readFile('public/models/v3/worker-manual.glb'),scene=(await new GLTFLoader().parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene;
const neutral={joint__upper_arm_L:[0,0,-.15],joint__upper_arm_R:[0,0,.15]};
const scratch=path.resolve('../work/P04-build');await mkdir(scratch,{recursive:true});
let code=ts.transpileModule(await readFile('src/adaptive-v3/motion/packer.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
code=code.replaceAll("from 'three'",`from '${pathToFileURL(path.resolve('node_modules/three/build/three.module.js')).href}'`);await writeFile(path.join(scratch,'packer.mjs'),code);
const{solvePackerArmPose}=await import(pathToFileURL(path.join(scratch,'packer.mjs')));
scene.position.set(.3,0,.7);scene.rotation.y=Math.PI;
const L=left.candidate.pose,R=right.candidate.pose,LP=solvePackerArmPose(scene,new T.Group(),L,[.65,.89,.52],left.candidate.contact_local,'L'),RP=solvePackerArmPose(scene,new T.Group(),R,[0,1.17,.28],right.candidate.contact_local),head={joint__head:[.15,0,0]},escape=solvePackerArmPose(scene,new T.Group(),R,[-.08,1.17,.38],right.candidate.contact_local);
const keys=[
 [0,'Ожидание',{}],[.7,'Подвод к опоре',{...LP,...head}],[1.1,'Кисть на кромке стола',{...L,...head}],
 [1.5,'Подготовка кисти',{...L,...escape,...head}],[2.1,'Подвод к ленте',{...L,...RP,...head}],[2.7,'Прижим края ленты',{...L,...R,...head}],
 [3.7,'Край ленты прижат',{...L,...R,...head}],[4.3,'Освобождение посылки',{...L,...RP,...head}],
 [4.9,'Проверка упаковки',{...L,...RP,...head}],[5.5,'Возврат кисти',{...L,...escape,...head}],[6.1,'Возврат руки',{...L,...head}],
 [6.7,'Возврат от опоры',{...LP}],[7.1,'Ожидание следующей посылки',{}],[7.5,'Проверка завершена',{}]
].map(([t,label,joints])=>({t,label,joints:{...neutral,...joints}}));
const hash=async p=>createHash('sha256').update(await readFile('../'+p)).digest('hex');
const inputs={};for(const p of ['assets/v3/blender/worker-manual.blend','frontend/public/models/v3/worker-manual.glb','assets/v3/blender/packing-station.blend','assets/v3/blender/sealed-parcel.blend','frontend/public/models/v3/packer-workcell-fixture.glb','assets/v3/iterations/packer/P04.1/hand-interface.json','assets/v3/iterations/packer/P04.1/front-tail-R-native.json','assets/v3/iterations/packer/P04.1/table-L-native.json'])inputs[p]=await hash(p);
const data={schema_id:'qoima.visual-packer-seam-end.v3',source_kind:'visual_fixture',engine_operation:false,units:'m',duration_s:7.5,
 scope:'Final front tape-tail press and visual inspection of one existing closed taped parcel. Not carton folding, packing contents, label creation, transport, inventory mutation or an actual engine run.',
 body_root_m:[.3,0,.7],body_yaw_rad:Math.PI,package_id:'v3:fixture:package:SMALL001',contents_HU_ref:'v3:fixture:HU:SMALL001',
 contacts:{L:{local_m:left.candidate.contact_local,workcell_m:[.65,.89,.45],surface:'worktop_R front edge'},R:{local_m:right.candidate.contact_local,workcell_m:[0,1.17,.24],surface:'front tape tail of existing parcel'}},
 keys,source_hashes:inputs,negative_top_seam_probe:'assets/v3/iterations/packer/P04.1/top-seam-probe/native-contact-search.json'};
await writeFile('public/data/v3/packer-seam-end.json',JSON.stringify(data,null,2)+'\n');
console.log(JSON.stringify({keys:keys.length,duration_s:data.duration_s,source_kind:data.source_kind,scope:data.scope}));
