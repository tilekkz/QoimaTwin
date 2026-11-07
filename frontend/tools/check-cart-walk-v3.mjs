import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import ts from 'typescript';
import * as T from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

const root=path.resolve('..'),work=path.join(root,'work/P03-walk-qa'),out=path.join(root,'assets/v3/iterations/picking-cart/P03.4');await mkdir(work,{recursive:true});await mkdir(out,{recursive:true});
const sha=b=>createHash('sha256').update(b).digest('hex'),sourceHashes={};
for(const [name,relative] of [['workerRoles','workerRoles'],['workerRolesFixture','workerRolesFixture'],['grip','motion/grip'],['cartWalk','motion/cartWalk']]){
 const source=await readFile('src/adaptive-v3/'+relative+'.ts','utf8');sourceHashes[relative]=sha(source);
 let code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
 code=code.replaceAll("from 'three'",`from '${pathToFileURL(path.join(root,'frontend/node_modules/three/build/three.module.js')).href}'`)
  .replaceAll("from 'three/examples/jsm/utils/BufferGeometryUtils.js'",`from '${pathToFileURL(path.join(root,'frontend/node_modules/three/examples/jsm/utils/BufferGeometryUtils.js')).href}'`)
  .replaceAll("from './workerRoles'","from './workerRoles.mjs'").replaceAll("from './workerRolesFixture'","from './workerRolesFixture.mjs'");
 await writeFile(path.join(work,name+'.mjs'),code);
}
const {createWorkerInstance,disposeWorkerInstance}=await import(pathToFileURL(path.join(work,'workerRoles.mjs')));
const {bindPickerGrip,validatePickerPushPose}=await import(pathToFileURL(path.join(work,'grip.mjs')));
const {createCartWalk,validateCartWalkTimeline,cartWalkAt}=await import(pathToFileURL(path.join(work,'cartWalk.mjs')));
const pose=validatePickerPushPose(JSON.parse(await readFile('public/data/v3/picker-push-pose.json','utf8'))),timeline=validateCartWalkTimeline(JSON.parse(await readFile('public/data/v3/picker-cart-walk.json','utf8')));
assert.throws(()=>cartWalkAt(timeline,NaN));assert.throws(()=>validateCartWalkTimeline({...timeline,pelvis_drop_m:.03}));
const files=['frontend/public/models/v3/worker-base.glb','frontend/public/models/v3/picking-cart-tote-fixture.glb','frontend/public/data/v3/picker-cart-walk.json'];
const fileHashes={};for(const f of files)fileHashes[f]=sha(await readFile(path.join(root,f)));
const loader=new GLTFLoader(),parse=async f=>{const b=await readFile(f);return (await loader.parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene;};
const source=await parse('public/models/v3/worker-base.glb'),fixture=await parse('public/models/v3/picking-cart-tote-fixture.glb');
const originalSource=JSON.stringify(source.toJSON()),cart=fixture.getObjectByName('picking-cart'),tote=fixture.getObjectByName('order-tote'),actor=createWorkerInstance(source,'P01','picker');
cart.attach(tote);const binding=bindPickerGrip(cart,actor,pose),originalBinding=JSON.stringify(binding.snapshot()),motion=createCartWalk(binding,timeline);
const actorUuid=actor.root.uuid,toteUuid=tote.uuid,cartUuid=cart.uuid;
const all=[];cart.traverse(n=>all.push(n));
const matrices=()=>all.map(n=>[n.uuid,...n.matrixWorld.elements]);
const limits=JSON.parse(await readFile('../assets/v3/specs/worker-base.dimensions.json','utf8')).joints;
const stateBefore=JSON.stringify(binding.snapshot());let worstGrip=0,worstFloor=0,maxCorrection=0,maxStanceSlide=0;const ranges={};const stancePrevious={};const nativeFrames=[];
function meshMinY(node){let minimum=Infinity;node.traverseVisible(n=>{if(n.isMesh){const p=n.geometry.getAttribute('position');for(let i=0;i<p.count;i++)minimum=Math.min(minimum,new T.Vector3().fromBufferAttribute(p,i).applyMatrix4(n.matrixWorld).y);}});return minimum;}
for(let i=0;i<=900;i++){
 const t=i/100,state=motion.apply(t);assert.equal(actor.root.uuid,actorUuid);assert.equal(tote.uuid,toteUuid);assert.equal(cart.uuid,cartUuid);assert.equal(tote.parent,cart);
 assert(state.actualFeet.some(f=>f.target.stance));
 actor.root.traverse(n=>{if(!limits[n.name])return;n.rotation.toArray().slice(0,3).forEach((a,j)=>assert(a>=limits[n.name].limits_radians_xyz[j][0]-1e-6&&a<=limits[n.name].limits_radians_xyz[j][1]+1e-6,'Rig limit '+n.name));});
 for(const hand of state.grip.hands){worstGrip=Math.max(worstGrip,hand.error_m,hand.axis_error);assert(hand.error_m<2e-5&&hand.axis_error<2e-5);}
 for(const f of state.actualFeet){
  assert(Math.abs(f.world[1]-f.target.lift)<1e-6);assert(Math.abs(f.world[2]-(-.7975+f.target.travel))<1e-6);
  if(f.target.stance){if(stancePrevious[f.side]&&Math.abs(stancePrevious[f.side].target-f.target.travel)<1e-10){const drift=Math.hypot(...f.world.map((v,j)=>v-stancePrevious[f.side].point[j]));maxStanceSlide=Math.max(maxStanceSlide,drift);assert(drift<1e-6);}stancePrevious[f.side]={target:f.target.travel,point:f.world};}else delete stancePrevious[f.side];
  for(const type of ['thigh','shin','foot']){const node=actor.root.getObjectByName('joint__'+type+'_'+f.side),angles=node.rotation.toArray().slice(0,3);angles.forEach((a,j)=>assert(a>=limits[node.name].limits_radians_xyz[j][0]-1e-6&&a<=limits[node.name].limits_radians_xyz[j][1]+1e-6));ranges[node.name]??=[Infinity,-Infinity];ranges[node.name]=[Math.min(ranges[node.name][0],angles[0]),Math.max(ranges[node.name][1],angles[0])];}
 }
 for(const w of state.wheels){assert(Math.abs(w.angle-state.distance/.075)<1e-10);maxCorrection=Math.max(maxCorrection,w.floor_correction_m);const bottom=meshMinY(cart.getObjectByName('joint__wheel_'+w.label));worstFloor=Math.max(worstFloor,Math.abs(bottom));assert(Math.abs(bottom)<2e-6);}
 if(i%10===0){
  const joints={};actor.root.traverse(n=>{if(n.name.startsWith('joint__'))joints[n.name]={position:n.position.toArray(),euler:n.rotation.toArray().slice(0,3)};});
  nativeFrames.push({time:t,state:{distance:state.distance,drop:state.drop,feet:state.feet},cart:cart.position.toArray(),worker:actor.root.position.toArray(),joints,wheels:Object.fromEntries(state.wheels.map(w=>[w.label,{position:cart.getObjectByName('joint__wheel_'+w.label).position.toArray(),euler:[w.angle,0,0]}]))});
 }
}
// Direct and shuffled seeks must reproduce every node, not only a clock label.
for(let i=0;i<100;i++){
 const t=((i*719)%900)/100;motion.apply(t);const direct=matrices();motion.apply(((i*137)%900)/100);motion.apply(t);assert.deepEqual(matrices(),direct);
}
motion.apply(0);assert.equal(JSON.stringify(binding.snapshot()),stateBefore);
const startVelocity=(cartWalkAt(timeline,1.0001).distance-cartWalkAt(timeline,.9999).distance)/.0002,endVelocity=(cartWalkAt(timeline,8.0001).distance-cartWalkAt(timeline,7.9999).distance)/.0002;assert(Math.abs(startVelocity)<.0001&&Math.abs(endVelocity)<.0001);
motion.dispose();motion.dispose();assert.equal(JSON.stringify(binding.snapshot()),originalBinding);assert.throws(()=>motion.apply(1));binding.release();assert.equal(actor.disposed,false);assert.equal(JSON.stringify(source.toJSON()),originalSource);disposeWorkerInstance(actor);
const report={task_id:'P03.4',passed:true,source_hashes:sourceHashes,input_hashes:fileHashes,actual_samples:901,native_pose_frames:nativeFrames.length,arbitrary_whole_node_seeks:100,stable_actor_cart_and_tote_uuid:true,source_meshes_unchanged:true,maximum_grip_or_axis_error:worstGrip,maximum_actual_wheel_floor_error_m:worstFloor,maximum_floor_correction_m:maxCorrection,maximum_stance_slide_m:maxStanceSlide,leg_angle_ranges_rad:ranges,all_leg_angles_inside_accepted_limits:true,initial_and_dispose_restore_binding:true,source_kind:'visual_fixture',engine_operation:false};
await writeFile(path.join(out,'actual-runtime-walk-checks.json'),JSON.stringify(report,null,2)+'\n');await writeFile(path.join(out,'runtime-native-poses.json'),JSON.stringify({input_hashes:fileHashes,frames:nativeFrames},null,2)+'\n');console.log(JSON.stringify(report));
