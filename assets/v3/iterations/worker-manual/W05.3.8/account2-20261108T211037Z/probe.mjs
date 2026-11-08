/** W05.3.8 scratch only. Never writes a source, accepted pose, or production file. */
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const out=path.dirname(fileURLToPath(import.meta.url)),repo=path.resolve(out,'../../../..');
const rel=p=>path.join(repo,p),sha=b=>createHash('sha256').update(b).digest('hex'),pins={};
const read=async p=>{const b=await readFile(rel(p));pins[p]=sha(b);return b;};
const save=(name,v)=>writeFile(path.join(out,name),JSON.stringify(v,null,2)+'\n');
const T=await import(pathToFileURL(rel('frontend/node_modules/three/build/three.module.js'))),{GLTFLoader}=await import(pathToFileURL(rel('frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js'))),{default:ts}=await import(pathToFileURL(rel('frontend/node_modules/typescript/lib/typescript.js')));
for(const p of ['work/v3/cart-clearance-next/report.md','work/v3/cart-clearance-next/checks.json','work/v3/cart-clearance-next/probe.mjs','frontend/src/adaptive-v3/motion/cartWalk.ts','frontend/src/adaptive-v3/motion/grip.ts','frontend/public/data/v3/picker-push-pose.json','frontend/public/data/v3/picker-cart-walk.json','frontend/src/adaptive-v3/workerRoles.ts','frontend/src/adaptive-v3/warehouseSupportBindings.json','docs/adaptive-v3/specs/P03.5.3.3.md','docs/adaptive-v3/evidence/P03.5.3.3.json','assets/v3/specs/worker-base.dimensions.json','frontend/node_modules/three/package.json','frontend/node_modules/three/build/three.module.js','frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js','frontend/node_modules/typescript/lib/typescript.js'])await read(p);
const originalFrames=JSON.parse(await read('assets/v3/iterations/worker-base/P03.5.1/gait/runtime-native-poses.json')),last=originalFrames.frames.at(-1);assert.equal(last.time,9);assert.equal(last.state.drop,0);
for(const p of ['tools/blender/v3/build_worker_base.py','tools/blender/v3/build_worker_manual.py','tools/blender/v3/verify_manual_reach.py','docs/adaptive-v3/specs/P03.5.1.md','frontend/src/adaptive-v3/warehouseSupportKit.ts','frontend/src/adaptive-v3/warehouseHolderScene.ts'])await read(p);
const loader=new GLTFLoader();async function load(p){const b=await read(p);return(await loader.parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'')).scene;}
const ws=await load('frontend/public/models/v3/worker-manual.glb'),worker=ws.getObjectByName('worker_base_root'),cart=await load('frontend/public/models/v3/picking-cart-tote-fixture.glb'),world=new T.Scene();world.add(worker,cart);
worker.position.set(16.0425,0,44.38);worker.rotation.y=Math.PI/2;cart.position.set(16.84,0,44.38);cart.rotation.y=Math.PI/2;
for(const[name,p]of Object.entries(last.joints)){const n=worker.getObjectByName(name);assert(n,name);n.position.fromArray(p.position);n.rotation.set(...p.euler,'XYZ');}
for(const[label,p]of Object.entries(last.wheels)){const n=cart.getObjectByName('joint__wheel_'+label);assert(n);n.position.fromArray(p.position);n.rotation.set(...p.euler,'XYZ');}
world.updateMatrixWorld(true);
const all=[];world.traverse(n=>all.push(n));const originals=new Map(all.map(n=>[n,{p:n.position.clone(),q:n.quaternion.clone(),s:n.scale.clone(),parent:n.parent,m:n.matrix.clone(),mw:n.matrixWorld.clone(),auto:n.matrixAutoUpdate,worldAuto:n.matrixWorldAutoUpdate,g:n.geometry,material:n.material}]));
function reset(){for(const[n,s]of originals){assert.equal(n.parent,s.parent);n.position.copy(s.p);n.quaternion.copy(s.q);n.scale.copy(s.s);n.matrix.copy(s.m);n.matrixWorld.copy(s.mw);n.matrixAutoUpdate=s.auto;n.matrixWorldAutoUpdate=s.worldAuto;}}
const matrixRows=()=>all.map(n=>[n.uuid,...n.matrix.elements,...n.matrixWorld.elements]);
const meshes=root=>{const a=[];root.traverseVisible(n=>{if(n.isMesh)a.push(n);});return a;};
const helperSource=(await read('frontend/tools/solve-worker-base-carry-v3.mjs')).toString();
const helper=helperSource.slice(helperSource.indexOf('function components('),helperSource.indexOf('function clip('));assert(helper.includes('whole-mesh interior'));
const H=new Function('T','EPS','PROBE',helper+';return {geometry,witness,winding,nearest,interior};')(T,2e-6,.00025);
const gm=root=>meshes(root).map(H.geometry);
const hands=['L','R'].map(side=>{
 const hand=worker.getObjectByName('joint__hand_'+side),anchor=worker.getObjectByName('anchor_hand_grip_'+side),centre=anchor.getWorldPosition(new T.Vector3()),inv=hand.matrixWorld.clone().invert();
 return {side,hand,anchor,centre,opening:new T.Vector3(0,0,1).transformDirection(hand.matrixWorld),meshes:meshes(hand).map(m=>{
  const g=H.geometry(m);
  return {name:m.name,parts:g.source_parts,triangles:g.tris.length,components:g.parts.map(p=>({name:p.name,triangles:p.ids,bounds_hand:new T.Box3().setFromPoints(p.tris.flatMap(t=>[t.a,t.b,t.c]).map(v=>v.clone().applyMatrix4(inv)))}))};
 })};
});
const initial={schema_id:'qoima.cart-release.scratch.v1',accepted:false,scope:'ISOLATED_NATIVE_P01_C01_TERMINAL_T9_ONLY',setup:{worker_world:worker.getWorldPosition(new T.Vector3()).toArray(),cart_world:cart.getWorldPosition(new T.Vector3()).toArray(),yaw_rad:Math.PI/2,wheel_angle_rad:last.wheels.rear_L.euler[0],hands:hands.map(h=>({side:h.side,centre_world:h.centre.toArray(),opening_world:h.opening.toArray(),grip_error_m:h.centre.distanceTo(cart.getObjectByName('anchor_grip_'+h.side).getWorldPosition(new T.Vector3())),meshes:h.meshes}))},cart_meshes:gm(cart).map(g=>({name:g.name,parts:g.source_parts,triangles:g.tris.length,bounds:g.box})),source_hashes:pins};
await save('source-hashes-before.json',pins);await save('inspection.json',initial);
// Adapt the exact native arm analytic construction in scratch, with an absolute
// actor-local target delta. No import of private code and no accepted-pose writer.
const cartSource=(await read('frontend/src/adaptive-v3/motion/cartWalk.ts')).toString(),ast=ts.createSourceFile('cartWalk.ts',cartSource,ts.ScriptTarget.Latest,true);
let armFunction;for(const n of ast.statements)if(ts.isFunctionDeclaration(n)&&n.name?.text==='prepareArm')armFunction=n.getText(ast);
assert(armFunction);armFunction=armFunction.replace('function solve(drop:number)','function solve(delta:THREE.Vector3)').replace('goal.y+=drop','goal.add(delta)');
const makeArm=new Function('THREE',ts.transpileModule(armFunction,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText+';return prepareArm;')(T),solvers=hands.map(h=>makeArm(worker,h.side,cart));
const startMatrices=matrixRows(),jointNodes=all.filter(n=>n.name.startsWith('joint__')),fixed=all.filter(n=>!hands.some(h=>worker.getObjectByName('joint__upper_arm_'+h.side).getObjectById(n.id))),feet=['L','R'].map(s=>worker.getObjectByName('anchor_foot_floor_'+s));
const fixedMatrices=new Map(fixed.map(n=>[n,n.matrixWorld.clone()])),footPoints=feet.map(n=>n.getWorldPosition(new T.Vector3()));
const nativeSoles=feet.map((n,i)=>{const side=['L','R'][i],foot=worker.getObjectByName('joint__foot_'+side),bottom=Math.min(...gm(foot).flatMap(m=>m.tris.flatMap(t=>[t.a.y,t.b.y,t.c.y])));assert(Math.abs(bottom)<=2e-6);assert(Math.abs(footPoints[i].y)<=2e-6);const legs=['thigh','shin','foot'].map(j=>({joint:'joint__'+j+'_'+side,euler:worker.getObjectByName('joint__'+j+'_'+side).rotation.toArray().slice(0,3)}));assert(legs.every(j=>j.euler.every(a=>Math.abs(a)<1e-10)));return {side,anchor_world_m:footPoints[i].toArray(),native_mesh_bottom_world_y_m:bottom,source_rest_leg_joints:legs,source_geometric_knee_rest_retained:true};});
function resourceFingerprint(){return all.filter(n=>n.isMesh).map(n=>({uuid:n.uuid,geometry_uuid:n.geometry.uuid,attributes:Object.fromEntries(Object.entries(n.geometry.attributes).map(([k,a])=>{const v=a.array??a.data.array;return[k,sha(Buffer.from(v.buffer,v.byteOffset,v.byteLength))];})),index:n.geometry.index?sha(Buffer.from(n.geometry.index.array.buffer,n.geometry.index.array.byteOffset,n.geometry.index.array.byteLength)):null,materials:(Array.isArray(n.material)?n.material:[n.material]).map(m=>sha(JSON.stringify(m.toJSON())))}));}
const initialResources=resourceFingerprint();
const terminalCartReference=new T.Matrix4().makeRotationY(Math.PI/2).setPosition(16,0,44.38).multiply(new T.Matrix4().makeTranslation(...last.cart)),terminalWorkerReference=terminalCartReference.clone().multiply(new T.Matrix4().makeTranslation(...last.worker));
let terminalJoin=0;function compareReference(n,m){terminalJoin=Math.max(terminalJoin,...m.elements.map((v,k)=>Math.abs(v-n.matrixWorld.elements[k])));for(const c of n.children)compareReference(c,m.clone().multiply(c.matrix));}compareReference(cart,terminalCartReference);compareReference(worker,terminalWorkerReference);assert(terminalJoin<=2e-6);
const smooth=u=>u*u*u*(10+u*(-15+6*u)),distance=.04449999582767,duration=1.5;
const localOpening=new T.Vector3(0,-.9238795325112867,.38268343236508984),delta=localOpening.clone().multiplyScalar(-distance);
function apply(t,failSecondIK=false){if(!Number.isFinite(t))throw Error('finite time required');const before=all.map(n=>[n,n.position.clone(),n.quaternion.clone(),n.scale.clone(),n.matrix.clone(),n.matrixWorld.clone()]);try{reset();if(t<0||t>duration)throw Error('outside scratch extraction');if(t!==0)solvers.forEach((solve,i)=>solve(failSecondIK&&i===1?new T.Vector3(0,20,0):delta.clone().multiplyScalar(smooth(t/duration))));world.updateMatrixWorld(true);for(const n of jointNodes){const lim=JSON.parse(n.userData.limits_xyz_json??'null');if(lim)n.rotation.toArray().slice(0,3).forEach((a,k)=>assert(a>=lim[k][0]-1e-8&&a<=lim[k][1]+1e-8,'native limit '+n.name));if(/finger|shoulder_lift|elbow_swivel|palm_roll/.test(n.name)){const o=originals.get(n);assert(n.position.equals(o.p)&&n.quaternion.equals(o.q),'unchanged native manual control '+n.name);}}return hands.map(h=>{const target=h.centre.clone().addScaledVector(h.opening,-distance*smooth(t/duration));const error=h.anchor.getWorldPosition(new T.Vector3()).distanceTo(target);assert(error<=2e-6);return {side:h.side,error_m:error};});}catch(e){for(const[n,p,q,s,m,mw]of before){n.position.copy(p);n.quaternion.copy(q);n.scale.copy(s);n.matrix.copy(m);n.matrixWorld.copy(mw);}throw e;}}
const cartMeshes=gm(cart),nativeBody=gm(worker);const barMesh=cartMeshes.find(m=>m.source_parts.includes('straight_grip_bar'));assert(barMesh);
const closedTopology=[...nativeBody,...cartMeshes].map(m=>{const edges=new Map(),key=v=>v.toArray().join(',');for(const t of m.tris)for(const[a,b]of [[t.a,t.b],[t.b,t.c],[t.c,t.a]]){const aa=key(a),bb=key(b),k=aa<bb?aa+'|'+bb:bb+'|'+aa,e=edges.get(k)??{count:0,balance:0};e.count++;e.balance+=aa<bb?1:-1;edges.set(k,e);}const boundary=[...edges.values()].filter(e=>e.count===1).length,unbalanced=[...edges.values()].filter(e=>e.balance!==0).length;assert.equal(boundary,0,'closed native mesh '+m.name);assert.equal(unbalanced,0,'oriented native mesh '+m.name);return {mesh:m.name,native_triangles:m.tris.length,edges:edges.size,boundary_edges:boundary,unbalanced_orientations:unbalanced};});await save('native-closed-topology.json',closedTopology);
const barComponents=barMesh.parts.filter(p=>hands.every(h=>p.box.distanceToPoint(h.centre)<.023));assert.equal(barComponents.length,1);const barPart=barComponents[0];
await save('native-bar-component.json',{whole_mesh:barMesh.name,component:barPart.name,original_triangle_indices:barPart.ids,bounds_world:barPart.box});
// Exact original adjacent same-chain articulation remains explicitly identified.
// Changed nonadjacent hand/cart, forearm/torso, or opposite limbs are never waived.
function bone(n){while(n&&n!==worker){if(n.name.startsWith('joint__')&&!/finger|palm_roll|shoulder_lift|elbow_swivel/.test(n.name))return n.name;n=n.parent;}return '';}
const adjacent=(a,b)=>{const aa=bone(a),bb=bone(b);if(!aa||!bb)return false;if(aa===bb)return true;const eq=(x,y)=>[aa,bb].sort().join('|')===[x,y].sort().join('|');if(eq('joint__head','joint__torso')||eq('joint__torso','joint__pelvis'))return true;for(const side of ['L','R']){if(eq('joint__upper_arm_'+side,'joint__torso')||eq('joint__thigh_'+side,'joint__pelvis'))return true;for(const [x,y]of [['upper_arm','forearm'],['forearm','hand'],['thigh','shin'],['shin','foot']])if(eq('joint__'+x+'_'+side,'joint__'+y+'_'+side))return true;}return false;};
const baseline=[];for(let i=0;i<nativeBody.length;i++)for(let j=i+1;j<nativeBody.length;j++){const a=nativeBody[i],b=nativeBody[j];if(adjacent(a.node,b.node)){const w=H.witness(a,b,true);if(w.found)baseline.push({meshes:[a.name,b.name],bones:[bone(a.node),bone(b.node)],witness:w});}}
const initialSelf=[];for(let i=0;i<nativeBody.length;i++)for(let j=i+1;j<nativeBody.length;j++){const a=nativeBody[i],b=nativeBody[j],w=H.witness(a,b,true);if(w.found)initialSelf.push({meshes:[a.name,b.name],bones:[bone(a.node),bone(b.node)],source_parts:[a.source_parts,b.source_parts],original_same_or_arm_adjacent:adjacent(a.node,b.node),...w});}
await save('terminal-t9-native-self.json',{scope:'Source t9, before extraction; no skipped unchanged pairs. Original articulation joins and nonadjacent interiors listed separately; decorative source ink still present.',all_native_pairs:nativeBody.length*(nativeBody.length-1)/2,witnesses:initialSelf});
const throat=hands.map(h=>{
 const inv=h.hand.matrixWorld.clone().invert(),centre=h.anchor.position.clone(),point=(z,y)=>new T.Vector3(centre.x,y,z).applyMatrix4(h.hand.matrixWorld),axis=new T.Vector3(0,1,0).transformDirection(h.hand.matrixWorld);
 const lower=gm(h.hand).find(g=>g.source_parts.includes('mitten_'+h.side+'_lower_pad')),upper=gm(h.hand).find(g=>g.source_parts.includes('mitten_'+h.side+'_upper_pad'));
 const slices=[centre.z,.05,.055].map(z=>{const origin=point(z,centre.y),ray=(g,d)=>{const r=new T.Ray(origin,d);let best=Infinity,tri;g.tris.forEach((t,k)=>{const p=r.intersectTriangle(t.a,t.b,t.c,false,new T.Vector3());if(p&&p.distanceTo(origin)<best){best=p.distanceTo(origin);tri=k;}});return {distance_m:best,triangle:tri};};const a=ray(lower,axis.clone().negate()),b=ray(upper,axis);return {hand_local_z_m:z,lower:a,upper:b,actual_native_throat_m:a.distance_m+b.distance_m};});
 const verts=barPart.tris.flatMap(t=>[t.a,t.b,t.c]).map(v=>v.clone().applyMatrix4(inv));const ys=verts.map(v=>v.y),diameter=Math.max(...ys)-Math.min(...ys);
 return {side:h.side,slices,bar_native_y_diameter_in_hand_frame_m:diameter,nominal_diameter_m:.045,minimum_slice_margin_m:Math.min(...slices.map(s=>s.actual_native_throat_m))-diameter,original_manual_controls:jointNodes.filter(n=>n.name.endsWith('_'+h.side)&&/finger|palm|shoulder|swivel/.test(n.name)).map(n=>({name:n.name,parent:n.parent.name,position:n.position.toArray(),euler:n.rotation.toArray().slice(0,3),metadata:n.userData}))};
});await save('native-throat.json',throat);
const rows=[],collisions=[];let worstIK=0,worstFixed=0,worstSole=0,pairs=0,probes=0,crossings=0;
await save('candidate-pose-samples.json',{accepted:false,stage:'STARTED',source_hashes:pins,baseline_original_adjacent_joins:baseline});
for(let i=0;i<=100;i++){
 const t=duration*i/100,ik=apply(t);worstIK=Math.max(worstIK,...ik.map(x=>x.error_m));
 for(const[n,m]of fixedMatrices)worstFixed=Math.max(worstFixed,...m.elements.map((v,k)=>Math.abs(v-n.matrixWorld.elements[k])));
 feet.forEach((n,k)=>worstSole=Math.max(worstSole,n.getWorldPosition(new T.Vector3()).distanceTo(footPoints[k])));
 const body=gm(worker),frameHits=[];
 const test=(a,b,kind)=>{pairs++;const w=H.witness(a,b,true);probes+=w.probes;crossings+=w.crossing_pairs;if(w.found)frameHits.push({kind,meshes:[a.name,b.name],bones:[bone(a.node),bone(b.node)],source_parts:[a.source_parts,b.source_parts],...w});};
 for(const a of body)for(const b of cartMeshes)test(a,b,'body_cart');
 for(let a=0;a<body.length;a++)for(let b=a+1;b<body.length;b++){
  const x=body[a],y=body[b],unchanged=x.matrix_world.every((v,k)=>v===nativeBody[a].matrix_world[k])&&y.matrix_world.every((v,k)=>v===nativeBody[b].matrix_world[k]);
  if(unchanged)continue;
  const originalAdjacent=adjacent(x.node,y.node)&&baseline.some(p=>p.meshes.includes(x.name)&&p.meshes.includes(y.name));
  if(!originalAdjacent)test(x,y,'body_self');
 }
 const angles={};worker.traverse(n=>{if(n.name.startsWith('joint__'))angles[n.name]=n.rotation.toArray().slice(0,3);});
 rows.push({time_s:t,withdrawal_m:distance*smooth(i/100),ik,jointEulerXYZ:angles,collisions:frameHits});if(frameHits.length)collisions.push({time_s:t,withdrawal_m:distance*smooth(i/100),hits:frameHits});
 if(i%20===0){await save('candidate-pose-samples.json',{accepted:false,stage:'EXTRACTION_PROBE',frames:rows,baseline_original_adjacent_joins:baseline});console.log(JSON.stringify({frame:i,time_s:t,hits:frameHits.length,first:frameHits[0]}));}
}
await save('candidate-pose-samples.json',{accepted:false,frames:rows,baseline_original_adjacent_joins:baseline});
const seeks=[];for(const t of [0,.75,1.5,.015,1.2,.75,0]){apply(t);const a=matrixRows();apply(duration-t);apply(t);assert.deepEqual(matrixRows(),a);seeks.push(t);}
apply(.75);const preBad=matrixRows();let badTimes=0;for(const t of [NaN,Infinity,-Infinity,-1,2]){assert.throws(()=>apply(t));assert.deepEqual(matrixRows(),preBad);badTimes++;}
assert.throws(()=>apply(.3,true));assert.deepEqual(matrixRows(),preBad);
reset();assert.deepEqual(matrixRows(),startMatrices);reset();assert.deepEqual(matrixRows(),startMatrices);
// Move the actual unchanged cart/bar, deliberately into a native pad. This is
// an isolated forbidden-intrusion negative control, immediately rolled back.
const pad=gm(worker).find(g=>g.source_parts.includes('mitten_L_lower_pad'));
cart.position.addScaledVector(new T.Vector3(0,1,0).transformDirection(hands[0].hand.matrixWorld),-.002);world.updateMatrixWorld(true);
const movedBar=gm(cart).find(g=>g.name===barMesh.name),intrusionControl=H.witness(pad,movedBar,true);assert(intrusionControl.found,'Actual source bar intrusion control must be detected');reset();assert.deepEqual(matrixRows(),startMatrices);
const forbiddenInitial=initialSelf.filter(w=>!w.original_same_or_arm_adjacent);
const physicalTerminal=forbiddenInitial.filter(w=>w.bones.some(b=>b.startsWith('joint__forearm_'))&&w.source_parts.some(p=>p.includes('shirt_core')));
assert.equal(physicalTerminal.length,2);
const independentWitness=physicalTerminal.map(w=>{const p=new T.Vector3(...w.point_m);return {meshes:w.meshes,point_m:w.point_m,checks:w.meshes.map(name=>{const mesh=nativeBody.find(m=>m.name===name);let solidAngle=0,depth=Infinity;for(const tri of mesh.tris){const av=tri.a.clone().sub(p),bv=tri.b.clone().sub(p),cv=tri.c.clone().sub(p),aa=av.length(),bb=bv.length(),cc=cv.length();solidAngle+=2*Math.atan2(av.dot(bv.clone().cross(cv)),aa*bb*cc+av.dot(bv)*cc+bv.dot(cv)*aa+cv.dot(av)*bb);depth=Math.min(depth,tri.closestPointToPoint(p,new T.Vector3()).distanceTo(p));}assert(Math.abs(solidAngle)>2*Math.PI&&depth>2e-6);return {mesh:name,whole_mesh_solid_angle_rad:solidAngle,depth_m:depth};})};});
let disposed=false;function dispose(){if(disposed)return;reset();disposed=true;}apply(.6);dispose();dispose();assert.deepEqual(matrixRows(),startMatrices);
for(const[n,s]of originals){assert(n.position.equals(s.p)&&n.quaternion.equals(s.q)&&n.scale.equals(s.s));assert.equal(n.parent,s.parent);assert.equal(n.geometry,s.g);assert.equal(n.material,s.material);}
assert.deepEqual(resourceFingerprint(),initialResources);
const drift=[],actualAfter={};for(const[p,h]of Object.entries(pins)){actualAfter[p]=sha(await readFile(rel(p)));if(actualAfter[p]!==h)drift.push(p);}
const oldPins=JSON.parse(await readFile(rel('work/v3/cart-clearance-next/checks.json'))).source_hashes,acceptedInputPins=['frontend/src/adaptive-v3/motion/cartWalk.ts','frontend/src/adaptive-v3/motion/grip.ts','frontend/public/data/v3/picker-push-pose.json','frontend/public/data/v3/picker-cart-walk.json','frontend/public/models/v3/worker-manual.glb','frontend/public/models/v3/picking-cart-tote-fixture.glb','assets/v3/iterations/worker-base/P03.5.1/gait/runtime-native-poses.json'];for(const p of acceptedInputPins)assert.equal(pins[p],oldPins[p],p+' accepted input pin');
const report={...initial,accepted:false,status:collisions.length?'BLOCKED_NATIVE_MATERIAL_INTERIOR':'EXTRACTION_SAMPLES_PASS_SETTLE_NOT_ADMITTED',source_hashes:pins,accepted_input_pins_match_previous_probe:true,terminal_t9_maximum_world_matrix_element_delta:terminalJoin,frames:rows.length,whole_native_mesh_pairs:pairs,witness_probes:probes,edge_triangle_pairs:crossings,closed_native_mesh_topology:closedTopology,maximum_ik_error_m:worstIK,maximum_fixed_matrix_element_delta:worstFixed,maximum_sole_drift_m:worstSole,backward_repeated_seeks:seeks,invalid_time_exact_rollback:badTimes,second_arm_unreachable_ik_exact_rollback:true,reset_idempotent_exact:true,dispose_idempotent_exact:true,actual_native_bar_intrusion_control:intrusionControl,independent_terminal_witness_recheck:independentWitness,input_drift:drift,initial_self:initialSelf,initial_forbidden_nonadjacent:forbiddenInitial,throat,collisions};
report.native_soles=nativeSoles;report.native_geometry_material_buffers_and_uuids_unchanged=true;report.runtime={node:process.version,three:T.REVISION};
await save('probe-results.json',report);await save('source-hashes-after.json',actualAfter);
console.log(JSON.stringify({status:report.status,frames:rows.length,pairs,probes,crossings,worstIK,worstFixed,worstSole,collisionFrames:collisions.length,first:collisions[0],drift},null,2));
