import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,realpath} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import * as THREE from 'three';
import ts from 'typescript';

const frontend=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),root=path.dirname(frontend);
const helperPath='frontend/src/adaptive-v3/warehouseCargoGeometry.ts',selfPath='frontend/tools/check-warehouse-cargo-geometry-v3.mjs';
const cache=path.join(root,'work/v3/warehouse-cargo-geometry-check'),out=path.join(root,'docs/adaptive-v3/evidence/W04.2-geometry-calibrations.json');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const helperBytes=await readFile(path.join(root,helperPath)),input_hashes={
 [helperPath]:sha(helperBytes),[selfPath]:sha(await readFile(fileURLToPath(import.meta.url))),
 'frontend/package-lock.json':sha(await readFile(path.join(frontend,'package-lock.json'))),
};
const threeURL=import.meta.resolve('three');
const projectThreeRoot=await realpath(path.join(frontend,'node_modules/three'));
assert.equal(await realpath(fileURLToPath(threeURL)),await realpath(path.join(projectThreeRoot,'build/three.module.js')),'Expected THREE resolved from this frontend dependency, including an explicit node_modules junction');
const threePackage=JSON.parse(await readFile(path.join(projectThreeRoot,'package.json'),'utf8'));
const lock=JSON.parse(await readFile(path.join(frontend,'package-lock.json'),'utf8'));
assert.equal(threePackage.name,'three');assert.equal(threePackage.version,'0.169.0');
assert.equal(lock.packages['node_modules/three'].version,threePackage.version);assert.equal(THREE.REVISION,'169');
await mkdir(cache,{recursive:true});
const compiled=ts.transpileModule(helperBytes.toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText.replace(/from ['"]three['"]/g,`from '${threeURL}'`);
await writeFile(path.join(cache,'warehouseCargoGeometry.mjs'),compiled);
const {createCargoGeometryInspector}=await import(pathToFileURL(path.join(cache,'warehouseCargoGeometry.mjs')).href+'?sha='+input_hashes[helperPath]);
const dimensions=[.5,.25,.5],EPS=2e-6,tests=[],meshes=[];
const matrix=(position=[0,0,0],yaw=0)=>new THREE.Matrix4().compose(new THREE.Vector3(...position),new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),yaw),new THREE.Vector3(1,1,1));
function part(geometry,instanceMatrix=new THREE.Matrix4(),worldMatrix=new THREE.Matrix4()){
 const mesh=new THREE.InstancedMesh(geometry,new THREE.MeshBasicMaterial(),1);mesh.name='calibration_part_'+meshes.length;
 mesh.setMatrixAt(0,instanceMatrix);mesh.matrixAutoUpdate=false;mesh.matrix.copy(worldMatrix);mesh.updateWorldMatrix(true,false);meshes.push(mesh);
 return {mesh,index:0,sourceMatrix:new THREE.Matrix4()};
}
function box(size,position=[0,0,0],worldMatrix=new THREE.Matrix4(),nonIndexed=false){
 let geometry=new THREE.BoxGeometry(...size);if(nonIndexed)geometry=geometry.toNonIndexed();
 return part(geometry,matrix(position),worldMatrix);
}
function cargo(position=[0,0,0],yaw=0,nonIndexed=false){
 return box(dimensions,[0,dimensions[1]/2,0],matrix(position,yaw),nonIndexed);
}
const bound=(position=[0,0,0],yaw=0)=>({handling_unit_id:'calibration:HU',destination:{kind:'storage_slot',slot_id:'calibration:slot'},position,yaw_rad:yaw,model_scale_factor:1,
 cargo:{dimensions_xyz_m:dimensions,gross_mass_kg:1,quantity_units:1}});
function inspect(cargoParts,supportParts,pose=bound()){
 const inspector=createCargoGeometryInspector(new Map([['calibration:HU',cargoParts]]),new Map([['calibration:module',supportParts]]));
 try{return inspector.inspectSupported(pose,'calibration:module');}finally{inspector.dispose?.();}
}
function observed(result){
 return {native_contact_area_sum_m2:result.native_contact_area_sum_m2,maximum_contact_gap_m:result.maximum_contact_gap_m,
  actual_bottom_gap_m:result.actual_bottom_gap_m,centre_inside_support_hull:result.geometric_centre_inside_support_hull,hull_points:result.native_support_hull_xz.length,
  bounds_cargo_local:result.bounds_cargo_local,vertices:result.vertices};
}
function positive(result){
 assert(result.native_contact_area_sum_m2>.20,'Expected finite native bottom/top overlap');
 assert(result.geometric_centre_inside_support_hull,'Footprint centre must lie inside native contact hull');
 assert(result.maximum_contact_gap_m<EPS&&Math.abs(result.actual_bottom_gap_m)<EPS);
 const expectedMin=[-dimensions[0]/2,0,-dimensions[2]/2],expectedMax=[dimensions[0]/2,dimensions[1],dimensions[2]/2];
 result.bounds_cargo_local.min.forEach((v,i)=>assert(Math.abs(v-expectedMin[i])<EPS));result.bounds_cargo_local.max.forEach((v,i)=>assert(Math.abs(v-expectedMax[i])<EPS));
 assert.equal(result.source_kind,'visual_fixture');assert.equal(result.engine_operation,false);
}
function noContact(result){assert.equal(result.native_contact_area_sum_m2,0);assert.equal(result.geometric_centre_inside_support_hull,false);assert.equal(result.native_support_hull_xz.length,0);}
function test(name,scope,run){
 let observation=null;
 try{observation=run();tests.push({case:name,passed:true,scope,observation});}
 catch(error){tests.push({case:name,passed:false,scope,observation,error:error.message});}
 finally{for(const mesh of meshes.splice(0)){mesh.geometry.dispose();mesh.material.dispose();mesh.dispose();}}
}

test('supported_top_positive','Native closed box rests on upward support top.',()=>{
 const result=inspect([cargo()],[box([2,.125,2],[0,-.0625,0])]);positive(result);return observed(result);
});
test('underside_penetration_negative','Cargo bottom coincides with support underside and penetrates the box: never a load-bearing contact.',()=>{
 const result=inspect([cargo([0,1,0])],[box([2,.125,2],[0,1.0625,0])],bound([0,1,0]));noContact(result);return observed(result);
});
test('vertical_gap_negative','A10mm gap is larger than the explicit contact tolerance.',()=>{
 const result=inspect([cargo([0,.01,0])],[box([2,.125,2],[0,-.0625,0])],bound([0,.01,0]));noContact(result);return observed(result);
});
test('adjacent_gap_negative','Coplanar upward deck separated laterally from the cargo footprint.',()=>{
 const result=inspect([cargo()],[box([1,.125,1],[2,-.0625,0])]);noContact(result);return observed(result);
});
test('sparse_one_sided_contacts_negative','Two genuine contact islands exist, but their contact hull excludes the footprint centre.',()=>{
 const result=inspect([cargo()],[box([.0625,.125,.0625],[-.1875,-.0625,-.1875]),box([.0625,.125,.0625],[-.1875,-.0625,.1875])]);
 assert(result.native_contact_area_sum_m2>.007&&result.native_contact_area_sum_m2<.009);assert.equal(result.geometric_centre_inside_support_hull,false);assert(result.native_support_hull_xz.length>=3);return observed(result);
});
test('shared_translated_rotated_top_positive','Nonidentity mesh world transforms preserve real contact and cargo-local dimensions.',()=>{
 const position=[113.125,1.25,55.375],yaw=.63,frame=matrix(position,yaw),result=inspect([cargo(position,yaw)],[box([2,.125,2],[0,-.0625,0],frame)],bound(position,yaw));positive(result);return observed(result);
});
test('float_instance_transforms_top_positive','World translation/yaw encoded in actual Float32 instance matrices, as in the warehouse.',()=>{
 const position=[12.5,.75,7.25],yaw=Math.PI/3,frame=matrix(position,yaw),a=part(new THREE.BoxGeometry(...dimensions),frame.clone().multiply(matrix([0,dimensions[1]/2,0]))),b=part(new THREE.BoxGeometry(2,.125,2),frame.clone().multiply(matrix([0,-.0625,0])));
 const result=inspect([a],[b],bound(position,yaw));positive(result);return observed(result);
});
test('nonindexed_top_positive','Native nonindexed triangle buffers use the same geometry rule.',()=>{
 const result=inspect([cargo([0,0,0],0,true)],[box([2,.125,2],[0,-.0625,0],new THREE.Matrix4(),true)]);positive(result);return observed(result);
});
test('edge_only_zero_overlap_negative','Exact binary-representable contact at an edge has zero supporting area.',()=>{
 const result=inspect([cargo()],[box([1,.125,1],[.75,-.0625,0])]);noContact(result);return observed(result);
});
test('point_only_zero_overlap_negative','One shared corner cannot create a contact polygon.',()=>{
 const result=inspect([cargo()],[box([1,.125,1],[.75,-.0625,.75])]);noContact(result);return observed(result);
});
test('degenerate_support_triangle_negative','Collinear horizontal native vertices contribute no supporting area.',()=>{
 const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute([-1,0,0,0,0,0,1,0,0],3));
 const result=inspect([cargo()],[part(geometry)]);noContact(result);return observed(result);
});
test('inside_out_cargo_negative','A reversed cargo mesh with upward-facing bottom cannot provide a valid downward contact face.',()=>{
 const geometry=new THREE.BoxGeometry(...dimensions),index=geometry.index;
 for(let i=0;i<index.count;i+=3){const a=index.getX(i);index.setX(i,index.getX(i+2));index.setX(i+2,a);}
 const result=inspect([part(geometry,matrix([0,dimensions[1]/2,0]))],[box([2,.125,2],[0,-.0625,0])]);noContact(result);return observed(result);
});
test('inside_out_support_negative','A reversed support mesh exposes its nominal top as a downward face.',()=>{
 const geometry=new THREE.BoxGeometry(2,.125,2),index=geometry.index;
 for(let i=0;i<index.count;i+=3){const a=index.getX(i);index.setX(i,index.getX(i+2));index.setX(i+2,a);}
 const result=inspect([cargo()],[part(geometry,matrix([0,-.0625,0]))]);noContact(result);return observed(result);
});
test('unknown_instance_and_support_rejected','Missing registered native instances are explicit inspection errors.',()=>{
 const inspector=createCargoGeometryInspector(new Map([['calibration:HU',[cargo()]]]),new Map());
 try{assert.throws(()=>inspector.inspectSupported({...bound(),handling_unit_id:'unknown'},'calibration:module'),/UNKNOWN_CARGO_INSTANCE/);assert.throws(()=>inspector.inspectSupported(bound(),'unknown'),/UNKNOWN_STORAGE_SUPPORT/);}finally{inspector.dispose?.();}
 return {explicit_rejections:2};
});

const sourceUnchanged=sha(await readFile(path.join(root,helperPath)))===input_hashes[helperPath]&&sha(await readFile(fileURLToPath(import.meta.url)))===input_hashes[selfPath];
const report={passed:tests.every(t=>t.passed)&&sourceUnchanged,source_kind:'visual_fixture',engine_operation:false,visible:false,browser_launched:false,geometry_calibrations:tests.length,
 tests,source_unchanged_during_check:sourceUnchanged,input_hashes,three_revision:THREE.REVISION,
 scope:'CPU calibration of actual native horizontal triangle contact/intersection and geometric footprint-centre support proxy. Synthetic geometry only; no strength, mass-centre stability, continuous collision, actual warehouse acceptance or engine certification.'};
await writeFile(out,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:report.passed,geometry_calibrations:tests.length,failed_cases:tests.filter(t=>!t.passed).map(t=>({case:t.case,error:t.error})),source_unchanged_during_check:sourceUnchanged,browser_launched:false}));
if(!report.passed)process.exitCode=1;
