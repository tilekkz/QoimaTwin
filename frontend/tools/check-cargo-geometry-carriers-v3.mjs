import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import * as THREE from 'three';
import ts from 'typescript';

// CPU geometry regression: deliberately simple solids isolate transform/cache behavior.
// This checker does not accept a native carrier, a hand clamp, or an action interval.
const cache=path.resolve('../work/v3/cargo-geometry-carriers-check'),input_hashes={};
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
await mkdir(cache,{recursive:true});
for(const file of ['src/adaptive-v3/warehouseCargoGeometry.ts','tools/check-cargo-geometry-carriers-v3.mjs'])input_hashes['frontend/'+file]=sha(await readFile(file));
const source=await readFile('src/adaptive-v3/warehouseCargoGeometry.ts','utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace(/from 'three'/g,`from '${pathToFileURL(path.resolve('node_modules/three/build/three.module.js')).href}'`);
const modulePath=path.join(cache,'warehouseCargoGeometry.mjs');await writeFile(modulePath,code);
const {createCargoGeometryInspector}=await import(pathToFileURL(modulePath));
const material=new THREE.MeshBasicMaterial(),cargoGeometry=new THREE.BoxGeometry(.32,.24,.24).translate(0,.12,0),cargoMesh=new THREE.InstancedMesh(cargoGeometry,material,2);
cargoMesh.position.set(12,0,8);cargoMesh.setMatrixAt(0,new THREE.Matrix4().makeTranslation(200,0,0));
const cargoParts=new Map([['test:HU',[{mesh:cargoMesh,index:1,sourceMatrix:new THREE.Matrix4()}]]]),supports=new Map(),inspector=createCargoGeometryInspector(cargoParts,supports),checks=[];
let bound={handling_unit_id:'test:HU',destination:{kind:'cart',cart_id:'test:cart',anchor_id:'floor'},position:[12,1,8],yaw_rad:0,model_scale_factor:1,cargo:{dimensions_xyz_m:[.32,.24,.24],gross_mass_kg:.94,quantity_units:24}};
function pose(position=bound.position,yaw=bound.yaw_rad){bound={...bound,position:[...position],yaw_rad:yaw};cargoMesh.updateWorldMatrix(true,false);const matrix=new THREE.Matrix4().compose(new THREE.Vector3(...position),new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),yaw),new THREE.Vector3(1,1,1));cargoMesh.setMatrixAt(1,matrix.premultiply(cargoMesh.matrixWorld.clone().invert()));}
function check(name,expected,id='support'){const report=inspector.inspectSupported(bound,id);assert.equal(report.geometric_centre_inside_support_hull,expected,name);if(expected){assert(Math.abs(report.native_contact_area_sum_m2-.32*.24)<1e-7,name+' area');assert(report.maximum_contact_gap_m<=2e-6,name+' gap');}else assert.equal(report.native_contact_area_sum_m2,0,name+' no contact');assert.equal(report.mesh_instances[0].uuid,cargoMesh.uuid);assert.equal(report.mesh_instances[0].index,1);checks.push({case:name,supported:expected});return report;}
const parent=new THREE.Group(),joint=new THREE.Group(),floorGeometry=new THREE.BoxGeometry(1,.1,.6).translate(0,-.05,0),floor=new THREE.Mesh(floorGeometry,material);
floor.name='native_test_floor';parent.add(joint);joint.add(floor);parent.position.set(12,1,8);supports.set('support',[{mesh:floor}]);pose();check('ordinary_mesh_parent_world_transform',true);
const stable=inspector.inspectSupported(bound,'support');assert.deepEqual(inspector.inspectSupported(bound,'support'),stable);checks.push({case:'unchanged_support_repeat_is_identical'});
parent.position.x+=2;check('parent_translation_invalidates_cached_faces',false);pose([14,1,8]);check('cargo_follows_parent_translation',true);
joint.position.y=.2;check('moving_joint_invalidates_cached_faces',false);pose([14,1.2,8]);check('cargo_follows_moving_joint',true);
parent.rotation.y=Math.PI/2;pose(bound.position,Math.PI/2);check('yaw_rotates_horizontal_native_faces',true);
floor.visible=false;check('hidden_support_is_not_admitted',false);floor.visible=true;check('visible_support_returns',true);
parent.visible=false;check('hidden_ancestor_is_not_admitted',false);parent.visible=true;check('visible_ancestor_returns',true);
floorGeometry.translate(0,.01,0);check('position_attribute_version_invalidates_cache',false);pose([14,1.21,8],Math.PI/2);check('cargo_follows_changed_native_floor',true);
const replacement=floorGeometry.clone().translate(0,.02,0);floor.geometry=replacement;check('geometry_replacement_invalidates_cache',false);pose([14,1.23,8],Math.PI/2);check('cargo_follows_replaced_native_geometry',true);
const replacementPosition=replacement.getAttribute('position').clone();for(let i=0;i<replacementPosition.count;i++)replacementPosition.setY(i,replacementPosition.getY(i)+.01);replacement.setAttribute('position',replacementPosition);check('attribute_replacement_invalidates_cache',false);pose([14,1.24,8],Math.PI/2);check('cargo_follows_replaced_attribute',true);
const originalIndices=replacement.index.clone(),reversedIndices=originalIndices.clone();for(let i=0;i<reversedIndices.count;i+=3){const value=reversedIndices.getX(i);reversedIndices.setX(i,reversedIndices.getX(i+1));reversedIndices.setX(i+1,value);}replacement.setIndex(reversedIndices);check('index_replacement_invalidates_upward_face_cache',false);replacement.setIndex(originalIndices);check('restored_upward_faces_return',true);
for(let i=0;i<originalIndices.count;i+=3){const value=originalIndices.getX(i);originalIndices.setX(i,originalIndices.getX(i+1));originalIndices.setX(i+1,value);}originalIndices.needsUpdate=true;check('index_version_invalidates_upward_face_cache',false);
const supportInstances=new THREE.InstancedMesh(new THREE.BoxGeometry(1,.1,.6).translate(0,-.05,0),material,2);supportInstances.name='native_test_instanced_floor';supportInstances.position.set(13,1.24,8);supportInstances.setMatrixAt(0,new THREE.Matrix4().makeTranslation(1,0,0));supportInstances.setMatrixAt(1,new THREE.Matrix4().makeTranslation(10,0,0));supports.set('support',[{mesh:supportInstances,index:0,sourceMatrix:new THREE.Matrix4()}]);check('ordinary_to_instanced_map_replacement',true);
supportInstances.setMatrixAt(0,new THREE.Matrix4().makeTranslation(3,0,0));check('instance_matrix_change_invalidates_cached_faces',false);pose([16,1.24,8],0);check('cargo_follows_support_instance',true);
supports.set('support',[{mesh:supportInstances,index:1,sourceMatrix:new THREE.Matrix4()}]);check('support_instance_index_change_invalidates_cache',false);pose([23,1.24,8]);check('cargo_follows_reselected_support_instance',true);
supports.set('support',[]);check('removed_support_array_invalidates_cache',false);
assert.throws(()=>inspector.inspectSupported(bound,'missing'),/UNKNOWN_STORAGE_SUPPORT/);checks.push({case:'unknown_support_fails_closed'});
supports.set('support',[{mesh:supportInstances,index:7,sourceMatrix:new THREE.Matrix4()}]);assert.throws(()=>inspector.inspectSupported(bound,'support'),/INVALID_SUPPORT_INSTANCE/);checks.push({case:'out_of_range_instance_fails_closed'});
const geometryOnly=inspector.inspectGeometry(bound);assert.equal(geometryOnly.mesh_instances[0].uuid,cargoMesh.uuid);assert(!Object.hasOwn(geometryOnly,'native_contact_area_sum_m2'));assert(!Object.hasOwn(geometryOnly,'geometric_centre_inside_support_hull'));checks.push({case:'side_clamp_geometry_observation_makes_no_support_claim'});
inspector.invalidateSupport();inspector.invalidateSupport('support');inspector.dispose();
for(const geometry of [cargoGeometry,floorGeometry,replacement,supportInstances.geometry])geometry.dispose();cargoMesh.dispose();supportInstances.dispose();material.dispose();
const report={passed:true,source_kind:'visual_fixture',engine_operation:false,operational_admission:false,checks,input_hashes,scope:'Synthetic CPU regression of native triangle transforms, visibility and cache invalidation only. Not native carrier acceptance, hand-contact proof, retention, strength, stability, motion or engine operation.'};
await writeFile('../docs/adaptive-v3/evidence/W04.3-geometry-carrier-checks.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,checks:checks.length,input_hashes:undefined}));
