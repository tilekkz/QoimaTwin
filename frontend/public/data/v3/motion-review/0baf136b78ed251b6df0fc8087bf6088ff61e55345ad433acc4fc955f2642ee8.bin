import * as THREE from 'three';

const TORSO='joint__torso',PELVIS='joint__pelvis';
const PERIOD_S=4.6,AMPLITUDE_RAD=.0012,axisX=new THREE.Vector3(1,0,0);

export type WarehouseCarryBreathingSample={
 readonly at_s:number;
 readonly enabled:boolean;
 readonly angle_rad:number;
 readonly torso_quaternion:THREE.Quaternion;
 readonly cargo_delta_root:THREE.Matrix4;
};

/**
 * Capture after native rest validation, before the first animated frame.
 * Sampling never mutates the actor. The caller restores its native frame, copies
 * torso_quaternion to joint__torso, then uses actorWorld*cargo_delta_root*cargoLocal.
 * Pelvis and legs are siblings of the torso branch and receive no breath motion.
 */
export function createWarehouseCarryBreathing(actorRoot:THREE.Object3D){
 const torso=actorRoot.getObjectByName(TORSO),pelvis=actorRoot.getObjectByName(PELVIS);
 if(actorRoot.userData.asset_id!=='worker-base'||!torso||!pelvis||torso.parent!==pelvis||pelvis.parent!==actorRoot||!actorRoot.matrixAutoUpdate||!pelvis.matrixAutoUpdate||!torso.matrixAutoUpdate)
  throw new Error('NATIVE_CARRY_BREATHING_RIG_REQUIRED');
 const unit=new THREE.Vector3(1,1,1);
 if([actorRoot,pelvis,torso].some(node=>node.scale.distanceTo(unit)>1e-10))throw new Error('RIGID_CARRY_BREATHING_FRAME_REQUIRED');
 // Build in actor-root coordinates from local TRS; actor/ancestor world yaw and
 // translation never enter the reference, even when constructed away from home.
 const parentRoot=new THREE.Matrix4().compose(pelvis.position,pelvis.quaternion,pelvis.scale);
 const referencePosition=torso.position.clone(),referenceQuaternion=torso.quaternion.clone(),referenceScale=torso.scale.clone();
 const referenceRoot=new THREE.Matrix4().compose(referencePosition,referenceQuaternion,referenceScale).premultiply(parentRoot),referenceInverse=referenceRoot.clone().invert();
 function sample(seconds:number,enabled=true):WarehouseCarryBreathingSample{
  if(!Number.isFinite(seconds))throw new TypeError('INVALID_CARRY_BREATHING_TIME');
  if(typeof enabled!=='boolean')throw new TypeError('INVALID_CARRY_BREATHING_ENABLED');
  const at_s=Math.max(0,seconds),phase=(at_s%PERIOD_S)/PERIOD_S;
  const angle_rad=enabled?AMPLITUDE_RAD*.5*(1-Math.cos(2*Math.PI*phase)):0;
  const torso_quaternion=referenceQuaternion.clone(),cargo_delta_root=new THREE.Matrix4();
  if(angle_rad!==0){
   torso_quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(axisX,angle_rad));
   cargo_delta_root.compose(referencePosition,torso_quaternion,referenceScale).premultiply(parentRoot).multiply(referenceInverse);
  }
  return {at_s,enabled,angle_rad,torso_quaternion,cargo_delta_root};
 }
 return Object.freeze({torso_name:TORSO,period_s:PERIOD_S,amplitude_rad:AMPLITUDE_RAD,sample});
}
