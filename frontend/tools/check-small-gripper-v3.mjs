import assert from'node:assert/strict';
import{readFile,writeFile,mkdir}from'node:fs/promises';
import path from'node:path';
import{pathToFileURL}from'node:url';
import{createHash}from'node:crypto';
import ts from'typescript';
import*as T from'three';
import{GLTFLoader}from'three/examples/jsm/loaders/GLTFLoader.js';
const dir='../assets/v3/iterations/small-package-gripper/P03.5.3.2',cache=path.resolve('../work/v3/small-gripper-check');await mkdir(cache,{recursive:true});
let code=ts.transpileModule(await readFile('src/adaptive-v3/motion/smallGripper.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
code=code.replaceAll("from 'three'",`from '${pathToFileURL(path.resolve('node_modules/three/build/three.module.js')).href}'`);await writeFile(path.join(cache,'smallGripper.mjs'),code);
const{bindSmallGripper}=await import(pathToFileURL(path.join(cache,'smallGripper.mjs')));
const bytes=await readFile('public/models/v3/small-package-gripper.glb'),glb=(await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'')).scene;
const root=glb.getObjectByName('small-package-gripper');assert(root);
const profiles=JSON.parse(await readFile(dir+'/native-mechanism-profiles.json','utf8'));
const fingerprint=()=>{root.updateWorldMatrix(true,true);const nodes=[];root.traverse(n=>nodes.push([n.uuid,...n.position.toArray(),...n.quaternion.toArray(),...(n.morphTargetInfluences??[])]));return JSON.stringify(nodes);};
const original=fingerprint(),controller=bindSmallGripper(root);assert.throws(()=>bindSmallGripper(root));let maximumError=0,verticesChecked=0;
for(const state of profiles.states){
 controller.apply(state.opening);const parts=new Map(state.parts.map(p=>[p.name,p.vertices]));root.updateWorldMatrix(true,true);
 root.traverse(n=>{
  if(!n.isMesh)return;let owner=n;while(owner&&!owner.userData.source_parts_json)owner=owner.parent;assert(owner);
  const names=JSON.parse(owner.userData.source_parts_json),expected=names.flatMap(name=>{assert(parts.has(name),name);return parts.get(name);}),actual=[];
  for(let i=0;i<n.geometry.getAttribute('position').count;i++)actual.push(n.getVertexPosition(i,new T.Vector3()).applyMatrix4(n.matrixWorld).toArray());
  for(const[a,b]of[[actual,expected],[expected,actual]])for(const point of a){let best=Infinity;for(const p of b)best=Math.min(best,(p[0]-point[0])**2+(p[1]-point[1])**2+(p[2]-point[2])**2);const error=Math.sqrt(best);maximumError=Math.max(maximumError,error);verticesChecked++;assert(error<3e-6,`${owner.name}: runtime/native ${error}`);}
 });
 assert(Math.abs(controller.snapshot().jaw_gap_m-(.04+.014*state.opening))<1e-12);
}
const accepted=new Map();for(let i=0;i<=100;i++){controller.apply(i/100);accepted.set(i,fingerprint());}
for(let i=0;i<100;i++){const index=(i*37)%101;controller.apply(index/100);assert.equal(fingerprint(),accepted.get(index));}
const beforeInvalid=fingerprint();for(const u of[NaN,Infinity,-Infinity,-.001,1.001]){assert.throws(()=>controller.apply(u));assert.equal(fingerprint(),beforeInvalid);}
controller.dispose();assert.equal(fingerprint(),original);assert.throws(()=>controller.apply(0));
let maximumThumbAngleError=0,buttonFrames=0;
const nativeContacts=JSON.parse(await readFile(dir+'/native-contacts.json','utf8'));
const button=bindSmallGripper(root);
for(const frame of nativeContacts.states){if(frame.raised)continue;const state=button.apply(frame.opening);assert.equal(state.manual_drive,true);maximumThumbAngleError=Math.max(maximumThumbAngleError,Math.abs(state.manual_thumb_press_rad-frame.manual_thumb_press_rad));buttonFrames++;}
assert(maximumThumbAngleError<1e-5);button.dispose();assert.equal(fingerprint(),original);
const rebound=bindSmallGripper(root);rebound.dispose();
root.scale.x=2;root.updateWorldMatrix(true,true);assert.throws(()=>bindSmallGripper(root));root.scale.x=1;root.updateWorldMatrix(true,true);
const report={task_id:'P03.5.3.2',passed:true,source_kind:'synthetic_design',engine_operation:false,glb_sha256:createHash('sha256').update(bytes).digest('hex'),native_states_compared:profiles.states.length,vertex_comparisons:verticesChecked,maximum_runtime_native_vertex_error_m:maximumError,morph_target_retained:true,arbitrary_seeks:100,invalid_openings_rejected:5,exclusive_binding:true,dispose_restores_every_node_and_morph:true,rebind_after_dispose:true,scaled_tool_rejected:true,actual_native_thumb_button_frames:buttonFrames,maximum_native_runtime_thumb_angle_difference_rad:maximumThumbAngleError,scope:'Tool controller/native geometry at9openings and101absolute seek states, plus actual native thumb/button press comparison; no complete pick clip or engine operation.'};
await writeFile(dir+'/runtime-checks.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
