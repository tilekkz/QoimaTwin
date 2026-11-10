import assert from 'node:assert/strict';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import ts from 'typescript';
import * as THREE from 'three';

const root=path.resolve(import.meta.dirname,'../..');
const own=path.join(root,'work/v3/full-tz-closeout-20261109/scenario-comparison-render');
await mkdir(own,{recursive:true});
const source='frontend/src/adaptive-v3/warehouseScenarioComparisonRender.ts';
const bytes=await readFile(path.join(root,source));
const hash=b=>createHash('sha256').update(b).digest('hex');
const code=ts.transpileModule(bytes.toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext},reportDiagnostics:true});
assert.equal(code.diagnostics?.filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
const runtime=path.join(own,'render.mjs');
const threeURL=pathToFileURL(path.join(root,'frontend/node_modules/three/build/three.module.js')).href;
await writeFile(runtime,code.outputText.replace("from 'three'",`from '${threeURL}'`));
const {renderWarehouseScenarioComparison:render}=await import(pathToFileURL(runtime));

/** State/projection oracle only: this deliberately creates no WebGL context. */
class StateRenderer {
 viewport=new THREE.Vector4(13,17,1200,881);
 scissor=new THREE.Vector4(4,7,350,450);
 scissorTest=false;
 autoClear=true; autoClearColor=false; autoClearDepth=true; autoClearStencil=false;
 target={name:'existing-caller-target'};
 draws=[]; clears=[]; renderHook=null;
 getViewport(out){return out.copy(this.viewport);}
 getScissor(out){return out.copy(this.scissor);}
 getScissorTest(){return this.scissorTest;}
 getRenderTarget(){return this.target;}
 setRenderTarget(target){this.target=target;}
 setViewport(...args){this.viewport.copy(args.length===1?args[0]:new THREE.Vector4(...args));}
 setScissor(...args){this.scissor.copy(args.length===1?args[0]:new THREE.Vector4(...args));}
 setScissorTest(value){this.scissorTest=value;}
 clear(...flags){this.clears.push({flags,scissor:this.scissor.toArray(),scissorTest:this.scissorTest});}
 render(scene,camera){
  this.draws.push({scene,camera,projection:camera.projectionMatrix.toArray(),world:camera.matrixWorld.toArray(),viewport:this.viewport.toArray(),scissor:this.scissor.toArray(),scissorTest:this.scissorTest,autoClear:this.autoClear});
  this.renderHook?.(scene,camera,this.draws.length);
 }
}
const rendererState=r=>({viewport:r.viewport.toArray(),scissor:r.scissor.toArray(),scissorTest:r.scissorTest,autoClear:r.autoClear,clear:[r.autoClearColor,r.autoClearDepth,r.autoClearStencil],target:r.target});
const cameraState=c=>({left:c.left,right:c.right,top:c.top,bottom:c.bottom,near:c.near,far:c.far,zoom:c.zoom,view:c.view?{...c.view}:null,projection:c.projectionMatrix.toArray(),inverse:c.projectionMatrixInverse.toArray(),world:c.matrixWorld.toArray(),worldInverse:c.matrixWorldInverse.toArray(),position:c.position.toArray(),quaternion:c.quaternion.toArray(),scale:c.scale.toArray(),parent:c.parent});
function fixture(){
 const renderer=new StateRenderer(),scene=new THREE.Scene(),warehouse=new THREE.Object3D();warehouse.userData={handling_unit_id:'same-HU',actor_id:'same-actor'};scene.add(warehouse);
 const parent=new THREE.Object3D();parent.position.set(4,2,-7);parent.rotation.y=.31;
 const camera=new THREE.OrthographicCamera(-92,92,46,-46,.1,1000);camera.position.set(170,140,180);camera.lookAt(72,0,36);camera.zoom=1.27;camera.setViewOffset(1200,900,20,10,1160,860);parent.add(camera);parent.updateMatrixWorld(true);camera.updateProjectionMatrix();
 const calls=[];const applyVariant=variant=>{calls.push(variant);warehouse.position.x=variant==='A'?0:5;};
 return{renderer,scene,camera,warehouse,calls,applyVariant};
}
const checks=[];
{
 const f=fixture(),before=rendererState(f.renderer),cam=cameraState(f.camera),viewIdentity=f.camera.view,ids=f.scene.children.map(n=>n.uuid);
 const frame=render(f.renderer,f.scene,f.camera,{comparison:true,variant:'B',applyVariant:f.applyVariant});
 assert.deepEqual(f.calls,['A','B','B']);assert.equal(f.warehouse.position.x,5);
 assert.deepEqual(frame.panes.map(p=>p.viewport),[[13,458,1200,440],[13,17,1200,440]]);
 assert.equal(frame.panes[0].aspect,frame.panes[1].aspect);assert.equal(frame.panes[0].aspect,1200/440);
 assert.deepEqual(rendererState(f.renderer),before);assert.deepEqual(cameraState(f.camera),cam);assert.equal(f.camera.view,viewIdentity);
 assert.deepEqual(f.scene.children.map(n=>n.uuid),ids);assert(Object.isFrozen(frame)&&Object.isFrozen(frame.panes)&&frame.panes.every(p=>Object.isFrozen(p)&&Object.isFrozen(p.viewport)));
 for(const draw of f.renderer.draws){
  assert.equal(draw.scene,f.scene);assert.notEqual(draw.camera,f.camera);assert.deepEqual(draw.world,cam.world);
  assert.deepEqual(draw.viewport,draw.scissor);assert(draw.scissorTest);assert.equal(draw.autoClear,false);
  assert.equal(draw.projection[0],cam.projection[0]);assert.equal(draw.projection[12],cam.projection[12]);
  assert(Math.abs(draw.projection[0]*draw.viewport[2]-draw.projection[5]*draw.viewport[3])<1e-12,'same projected unit scale horizontally/vertically');
  assert(Math.abs(draw.projection[13]/draw.projection[5]-cam.projection[13]/cam.projection[5])<1e-12,'same optical Y centre within matrix arithmetic');
  for(const index of [2,6,10,14,15])assert.equal(draw.projection[index],cam.projection[index],'depth mapping retained');
 }
 assert.equal(f.renderer.clears.length,1);assert.deepEqual(f.renderer.clears[0].scissor,before.viewport);
 checks.push('same_scene_two_equal_aspect_stacked_passes_A_above_B_no_population_copy');
 checks.push('parented_world_camera_horizontal_projection_and_pixel_isotropy_preserved');
 checks.push('odd_height_clear_seam_and_all_viewport_scissor_clearflags_target_projection_state_restored');
}
{
 const f=fixture(),before=rendererState(f.renderer),cam=cameraState(f.camera);f.renderer.autoClear=false;const auto=rendererState(f.renderer);
 const frame=render(f.renderer,f.scene,f.camera,{comparison:false,variant:'A',applyVariant:f.applyVariant});
 assert.deepEqual(f.calls,['A','A']);assert.equal(frame.panes.length,1);assert.deepEqual(f.renderer.draws[0].projection,cam.projection);assert.deepEqual(f.renderer.draws[0].viewport,before.viewport);assert.deepEqual(rendererState(f.renderer),auto);assert.deepEqual(cameraState(f.camera),cam);
 checks.push('single_variant_renders_full_original_projection_and_restores_false_autoClear');
}
for(const kind of ['apply_A','apply_B','render_second']){
 const f=fixture(),before=rendererState(f.renderer),cam=cameraState(f.camera),failure=new Error(kind);
 f.renderer.renderHook=(_s,_c,n)=>{if(kind==='render_second'&&n===2)throw failure;};
 const apply=variant=>{f.applyVariant(variant);if(kind==='apply_'+variant)throw failure;};
 assert.throws(()=>render(f.renderer,f.scene,f.camera,{comparison:true,variant:'A',applyVariant:apply}),e=>e===failure||(e instanceof AggregateError&&e.errors.includes(failure)));
 assert.equal(f.calls.at(-1),'A');assert.deepEqual(rendererState(f.renderer),before);assert.deepEqual(cameraState(f.camera),cam);
 f.renderer.renderHook=null;render(f.renderer,f.scene,f.camera,{comparison:false,variant:'A',applyVariant:f.applyVariant});
}
checks.push('apply_and_render_exceptions_restore_selected_variant_state_and_release_guard');
{
 const f=fixture(),before=rendererState(f.renderer),cam=cameraState(f.camera),renderFailure=new Error('render'),restoreFailure=new Error('restore');let rendered=false;
 f.renderer.renderHook=()=>{rendered=true;throw renderFailure;};
 assert.throws(()=>render(f.renderer,f.scene,f.camera,{comparison:true,variant:'B',applyVariant:v=>{f.applyVariant(v);if(rendered)throw restoreFailure;}}),e=>e instanceof AggregateError&&e.errors[0]===renderFailure&&e.errors[1]===restoreFailure);
 assert.deepEqual(rendererState(f.renderer),before);assert.deepEqual(cameraState(f.camera),cam);
 checks.push('restore_failure_keeps_original_failure_and_still_restores_renderer_camera');
}
for(const key of ['renderer','scene','camera']){
 const f=fixture(),before=rendererState(f.renderer),cam=cameraState(f.camera);let attempted=false;
 render(f.renderer,f.scene,f.camera,{comparison:true,variant:'B',applyVariant:v=>{
  f.applyVariant(v);if(attempted)return;attempted=true;
  const other=fixture();const r=key==='renderer'?f.renderer:other.renderer,s=key==='scene'?f.scene:other.scene,c=key==='camera'?f.camera:other.camera;
  assert.throws(()=>render(r,s,c,{comparison:true,variant:'A',applyVariant:()=>assert.fail('reentrant callback ran')}),/REENTRANT/);
 }});
 assert.deepEqual(rendererState(f.renderer),before);assert.deepEqual(cameraState(f.camera),cam);
}
checks.push('reentrant_renderer_scene_or_camera_refused_before_nested_mutation');
{
 const f=fixture(),cam=cameraState(f.camera),view=f.camera.view;
 render(f.renderer,f.scene,f.camera,{comparison:true,variant:'A',applyVariant:v=>{f.applyVariant(v);f.camera.zoom=7;f.camera.clearViewOffset();f.camera.updateProjectionMatrix();}});
 assert.deepEqual(cameraState(f.camera),cam);assert.equal(f.camera.view,view);
 checks.push('source_projection_fields_matrices_and_existing_view_object_restored_after_callback');
}
for(const value of [null,{comparison:'yes',variant:'A',applyVariant(){}},{comparison:true,variant:'C',applyVariant(){}}]){
 const f=fixture(),before=rendererState(f.renderer);assert.throws(()=>render(f.renderer,f.scene,f.camera,value),/OPTIONS/);assert.deepEqual(rendererState(f.renderer),before);assert.equal(f.calls.length,0);
}
for(const bad of [0,1,NaN,Infinity]){
 const f=fixture();f.renderer.viewport.w=bad;const before=rendererState(f.renderer);assert.throws(()=>render(f.renderer,f.scene,f.camera,{comparison:true,variant:'A',applyVariant:f.applyVariant}),/VIEWPORT/);assert.deepEqual(rendererState(f.renderer),before);assert.equal(f.calls.length,0);
}
checks.push('invalid_options_and_nonfinite_or_too_small_viewport_are_inert');
{
 const f=fixture(),before=rendererState(f.renderer);f.camera.projectionMatrix.elements[5]=0;assert.throws(()=>render(f.renderer,f.scene,f.camera,{comparison:true,variant:'A',applyVariant:f.applyVariant}),/ORTHOGRAPHIC/);assert.deepEqual(rendererState(f.renderer),before);assert.equal(f.calls.length,0);
 checks.push('singular_or_nonorthographic_projection_refused_before_mutation');
}
{
 const f=fixture();f.camera.position.x+=3;f.camera.rotation.z+=.07;f.camera.parent.position.z-=2;
 const before=cameraState(f.camera),expectedParent=f.camera.parent.clone(false),expected=f.camera.clone(false);expectedParent.add(expected);expectedParent.updateMatrixWorld(true);
 render(f.renderer,f.scene,f.camera,{comparison:true,variant:'A',applyVariant:f.applyVariant});
 for(const draw of f.renderer.draws)assert.deepEqual(draw.world,expected.matrixWorld.toArray());
 assert.deepEqual(cameraState(f.camera),before,'caller stale matrices are not mutated');
 checks.push('fresh_frameAt_and_parent_TRS_evaluated_before_renderer_without_mutating_stale_source_matrices');
}
assert.equal(hash(await readFile(path.join(root,source))),hash(bytes),'source drift');
const report={passed:true,source_kind:'visual_fixture',engine_operation:false,scope:'Real Three.js orthographic matrices/scene identities plus a no-WebGL renderer-state oracle. No GPU/browser/native case admission or performance certificate.',checks,source_hashes:{[source]:hash(bytes),'frontend/tools/check-warehouse-scenario-comparison-render-v3.mjs':hash(await readFile(import.meta.filename))},limitations:['Page owns same-input paired-plan guard and absolute-time sampling.','One logical warehouse is drawn twice; this helper creates camera copies only.','Actual native N4 A/B and N0–N3 source cases require the separate affected browser integration run.']};
await writeFile(path.join(own,'checks.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:true,checks:checks.length,source_sha256:hash(bytes),report:path.join(own,'checks.json')}));
