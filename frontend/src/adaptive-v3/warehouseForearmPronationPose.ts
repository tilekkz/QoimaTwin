import * as THREE from 'three';

const SOURCE_SHA='542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163';
const GAIN=.5,axisError=1e-10,normError=5e-7;
type Side='L'|'R';
const ARM_NAMES=['L','R'].flatMap(side=>['upper_arm','forearm','palm_roll','hand'].map(j=>'joint__'+j+'_'+side));

/** Representation-invariant native pure-Y coordinate, including mirrored pi seam. */
export function decodeWarehousePureYRoll(q:THREE.Quaternion,side:Side):number{
 const values=q.toArray(),normSquared=values.reduce((sum,v)=>sum+v*v,0);
 if(!values.every(Number.isFinite)||Math.abs(q.x)>axisError||Math.abs(q.z)>axisError||Math.abs(normSquared-1)>normError)
  throw Error('INVALID_ORIGINAL_PURE_Y_ROLL');
 const norm=Math.hypot(q.y,q.w);let y=q.y/norm,w=q.w/norm;
 if(w<0){y=-y;w=-w;}
 if(Math.abs(w)<=1e-12)return side==='L'?Math.PI:-Math.PI;
 return 2*Math.atan2(y,w);
}

/** Construct from the private verified original GLB template BEFORE arm pose apply.
 * Only the two named leaf mesh quaternions are written. No positions, scales,
 * geometry, materials, metadata or bone quaternions are written by this helper.
 */
export function createWarehouseForearmPronationPose(actorRoot:THREE.Object3D,sourceRoot:THREE.Object3D,sourceModelSHA:string){
 if(sourceModelSHA!==SOURCE_SHA||actorRoot.userData.asset_id!=='worker-base'||sourceRoot.name!=='worker_base_root'||!actorRoot.scale.equals(sourceRoot.scale))throw Error('ORIGINAL_PRONATION_SOURCE_REQUIRED');
 const sourceNodes=new Map<string,THREE.Object3D>();sourceRoot.traverse(n=>{if(sourceNodes.has(n.name))throw Error('DUPLICATE_PRONATION_SOURCE_NODE');sourceNodes.set(n.name,n);});
 const overlays:THREE.Object3D[]=[],actorNodes=new Map<string,THREE.Object3D>();actorRoot.traverse(n=>{if(n===actorRoot)return;if(n.userData.roleBadge===true){overlays.push(n);return;}if(actorNodes.has(n.name))throw Error('DUPLICATE_PRONATION_ACTOR_NODE');actorNodes.set(n.name,n);});
 if(actorNodes.size!==sourceNodes.size-1||overlays.length!==1||!(overlays[0] as THREE.Mesh).isMesh||!overlays[0]!.name.startsWith('role_badge__')||overlays[0]!.children.length!==0)throw Error('ONLY_FACTORY_ROLE_OVERLAY_SUPPORTED');
 const sourceBadge=[...sourceNodes.values()].find(n=>{try{return (JSON.parse(n.userData.source_parts_json??'[]') as string[]).includes('role_badge_base');}catch{return false;}});
 if(!sourceBadge||overlays[0]!.parent!==actorNodes.get(sourceBadge.parent!.name))throw Error('FACTORY_ROLE_OVERLAY_PARENT_REQUIRED');
 const sameAttribute=(a:THREE.BufferAttribute|THREE.InterleavedBufferAttribute,b:THREE.BufferAttribute|THREE.InterleavedBufferAttribute)=>{
  if((a as THREE.InterleavedBufferAttribute).isInterleavedBufferAttribute||(b as THREE.InterleavedBufferAttribute).isInterleavedBufferAttribute)return false;
  const x=a as THREE.BufferAttribute,y=b as THREE.BufferAttribute;if(x.itemSize!==y.itemSize||x.count!==y.count||x.normalized!==y.normalized||x.array.constructor!==y.array.constructor||x.array.byteLength!==y.array.byteLength)return false;
  const bytes=new Uint8Array(x.array.buffer,x.array.byteOffset,x.array.byteLength),source=new Uint8Array(y.array.buffer,y.array.byteOffset,y.array.byteLength);return bytes.every((v,i)=>v===source[i]);
 };
 const sameGeometry=(a:THREE.BufferGeometry,b:THREE.BufferGeometry)=>{
  const keys=Object.keys(a.attributes).sort(),expected=Object.keys(b.attributes).sort();if(keys.join('|')!==expected.join('|')||keys.some(k=>!sameAttribute(a.attributes[k]!,b.attributes[k]!)))return false;
  if(!!a.index!==!!b.index||(a.index&&b.index&&!sameAttribute(a.index,b.index)))return false;
  const morphKeys=Object.keys(a.morphAttributes).sort(),sourceKeys=Object.keys(b.morphAttributes).sort();if(morphKeys.join('|')!==sourceKeys.join('|'))return false;
  for(const k of morphKeys){const x=a.morphAttributes[k as keyof typeof a.morphAttributes]??[],y=b.morphAttributes[k as keyof typeof b.morphAttributes]??[];if(x.length!==y.length||x.some((v,i)=>!sameAttribute(v,y[i]!)))return false;}
  return JSON.stringify(a.groups)===JSON.stringify(b.groups)&&Object.is(a.drawRange.start,b.drawRange.start)&&Object.is(a.drawRange.count,b.drawRange.count)&&a.morphTargetsRelative===b.morphTargetsRelative;
 };
 // World/home placement is owned by the controller, so the actor-root placement
 // is not compared to the asset's local origin. All native child rest TRS is.
 for(const [name,native]of sourceNodes){const actual=native===sourceRoot?actorRoot:actorNodes.get(name);if(!actual)throw Error('NATIVE_PRONATION_MEMBERSHIP_REQUIRED:'+name);
  if(native!==sourceRoot){const parent=native.parent===sourceRoot?actorRoot:actorNodes.get(native.parent!.name);if(actual.parent!==parent)throw Error('NATIVE_PRONATION_PARENT_REQUIRED:'+name);if(!actual.position.equals(native.position)||!actual.scale.equals(native.scale)||!actual.quaternion.equals(native.quaternion))throw Error('PRONATION_CONSTRUCT_BEFORE_ARM_APPLY_REQUIRED:'+name);}
  const actualChildren=actual.children.filter(n=>n.userData.roleBadge!==true),nativeChildren=native.children.map(n=>actorNodes.get(n.name));if(actualChildren.length!==nativeChildren.length||actualChildren.some((n,i)=>n!==nativeChildren[i]))throw Error('NATIVE_PRONATION_CHILD_ORDER_REQUIRED:'+name);
  if((native as THREE.Mesh).isMesh){if(!(actual as THREE.Mesh).isMesh||!sameGeometry((actual as THREE.Mesh).geometry,(native as THREE.Mesh).geometry))throw Error('ORIGINAL_PRONATION_GEOMETRY_REQUIRED:'+name);}
 }
 for(const name of ARM_NAMES)if(!actorNodes.has(name))throw Error('EIGHT_NATIVE_PRONATION_JOINTS_REQUIRED');
 const rows=(['L','R'] as const).map(side=>{
  const meshName=side==='L'?'worker-base__batch_11':'worker-base__batch_14',rollName='joint__palm_roll_'+side,foreName='joint__forearm_'+side;
  const mesh=actorNodes.get(meshName) as THREE.Mesh|undefined,roll=actorNodes.get(rollName),nativeMesh=sourceNodes.get(meshName),nativeRoll=sourceNodes.get(rollName);
  if(!mesh?.isMesh||!roll||!nativeMesh||!nativeRoll||mesh.parent?.name!==foreName||roll.parent?.name!==foreName||nativeMesh.parent?.name!==foreName||nativeRoll.parent?.name!==foreName)throw Error('ORIGINAL_PRONATION_PARENTAGE_REQUIRED');
  const bindRollY=nativeRoll.userData.neutral_runtime_y_rad,expectedBind=side==='L'?Math.PI/2:-Math.PI/2;
  if(bindRollY!==expectedBind||Math.abs(decodeWarehousePureYRoll(nativeRoll.quaternion,side)-expectedBind)>1e-12||nativeRoll.position.lengthSq()===0)throw Error('ORIGINAL_PRONATION_BIND_REQUIRED');
  return {side,mesh,roll,meshName,rollName,meshParent:mesh.parent,rollParent:roll.parent,meshPosition:nativeMesh.position.clone(),meshScale:nativeMesh.scale.clone(),rollPosition:nativeRoll.position.clone(),rollScale:nativeRoll.scale.clone(),axis:nativeRoll.position.clone().normalize(),bindRollY,bindMeshQuaternion:nativeMesh.quaternion.clone()};
 });
 let disposed=false;
 function sample(){
  if(disposed)throw Error('ORIGINAL_PRONATION_DISPOSED');
  return rows.map(row=>{
   if(row.mesh.parent!==row.meshParent||row.roll.parent!==row.rollParent||!row.mesh.position.equals(row.meshPosition)||!row.mesh.scale.equals(row.meshScale)||!row.roll.position.equals(row.rollPosition)||!row.roll.scale.equals(row.rollScale))throw Error('ORIGINAL_PRONATION_NATIVE_FRAME_CHANGED');
   const rollY=decodeWarehousePureYRoll(row.roll.quaternion,row.side),theta=(row.bindRollY-rollY)*GAIN;
   return {row,rollY,theta,quaternion:new THREE.Quaternion().setFromAxisAngle(row.axis,theta).multiply(row.bindMeshQuaternion)};
  });
 }
 const source_flags=Object.freeze({source_kind:'visual_fixture' as const,engine_operation:false as const,source_model_sha256:SOURCE_SHA,contract:'original542-half-palm-roll-canonical-v2' as const,gain:GAIN,writes_mesh_quaternions_only:true as const,mesh_names:Object.freeze(rows.map(row=>row.meshName))});
 function snapshot(){return Object.freeze({source_flags,rows:sample().map(({row,rollY,theta,quaternion})=>Object.freeze({side:row.side,mesh_name:row.meshName,roll_joint:row.rollName,bind_roll_y_rad:row.bindRollY,current_roll_y_rad:rollY,theta_rad:theta,axis_forearm_local:row.axis.toArray(),bind_mesh_quaternion:row.bindMeshQuaternion.toArray(),expected_mesh_quaternion:quaternion.toArray(),actual_mesh_quaternion:row.mesh.quaternion.toArray()}))});}
 function apply(){const expected=sample();for(const {row,quaternion}of expected)row.mesh.quaternion.copy(quaternion);return snapshot();}
 // Source bind reset only. Controller reset() remains apply(0), which is a
 // held-pose reset and must recompute this mapping after its eight arm writes.
 function reset(){for(const row of rows)row.mesh.quaternion.copy(row.bindMeshQuaternion);}
 function dispose(){if(disposed)return;reset();disposed=true;}
 return Object.freeze({apply,snapshot,reset,dispose,source_flags});
}
