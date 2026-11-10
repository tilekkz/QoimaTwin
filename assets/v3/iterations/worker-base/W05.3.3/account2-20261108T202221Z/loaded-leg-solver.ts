/** Carry-only native hip X/Y/Z, shin X with source turn twist Y; no source-target changes. */
function solveLoadedLegs(rig:ReturnType<typeof deriveNativeWorkerGaitRig>,p:WorkerGaitPose):WorkerGaitPose{
 if(p.at_s===0||p.stage==='route_end')return p;
 const rotations={...p.joint_rotations};let maximumError=0;
 for(const leg of rig.legs){
  const side=leg.side,target=p.feet[side],wrap=(a:number)=>Math.atan2(Math.sin(a),Math.cos(a));
  const desired=new THREE.Quaternion().setFromAxisAngle(axisY,wrap(target.yaw_rad-p.yaw_rad));
  const goal=new THREE.Vector3(...target.point).sub(new THREE.Vector3(...p.root_world)).applyAxisAngle(axisY,-p.yaw_rad).sub(new THREE.Vector3(...leg.sole).applyQuaternion(desired)).sub(new THREE.Vector3(...leg.hip));
  const names=['joint__thigh_'+side,'joint__shin_'+side,'joint__foot_'+side];
  const old1=new THREE.Euler().setFromQuaternion(new THREE.Quaternion(...p.joint_rotations[names[0]]),'XYZ'),old2=new THREE.Euler().setFromQuaternion(new THREE.Quaternion(...p.joint_rotations[names[1]]),'XYZ');
  const relativeYaw=wrap(target.yaw_rad-p.yaw_rad),twist=relativeYaw*.30,hipYaw=THREE.MathUtils.clamp((side==='L'?1:-1)*.30*Math.min(.30,Math.abs(old1.x)),relativeYaw-twist-.19,relativeYaw-twist+.19),values=[old1.x,0,old2.x],a=new THREE.Vector3(...leg.a),b=new THREE.Vector3(...leg.b),q1=new THREE.Quaternion(),q2=new THREE.Quaternion(),q12=new THREE.Quaternion();
  function point(v:number[]){q1.setFromEuler(new THREE.Euler(v[0],hipYaw,v[1],'XYZ'));q2.setFromEuler(new THREE.Euler(v[2],twist,0,'XYZ'));q12.copy(q1).multiply(q2);return a.clone().applyQuaternion(q1).add(b.clone().applyQuaternion(q12));}
  for(let i=0;i<50;i++){
   const current=point(values),error=goal.clone().sub(current);if(error.length()<1e-11)break;
   const columns=values.map((_,j)=>{const v=[...values];v[j]+=1e-6;return point(v).sub(current).multiplyScalar(1e6);});
   const jac=new THREE.Matrix3().set(columns[0].x,columns[1].x,columns[2].x,columns[0].y,columns[1].y,columns[2].y,columns[0].z,columns[1].z,columns[2].z);
   requireValue(Math.abs(jac.determinant())>1e-15,'LOADED_LEG_SINGULAR',{at_s:p.at_s,side,values});
   error.applyMatrix3(jac.invert());for(let j=0;j<3;j++)values[j]+=THREE.MathUtils.clamp(error.getComponent(j),-.2,.2);
  }
  const error=point(values).distanceTo(goal);requireValue(error<=2e-7,'LOADED_LEG_UNREACHABLE',{at_s:p.at_s,side,error,values});maximumError=Math.max(maximumError,error);
  const angles=[new THREE.Euler(values[0],hipYaw,values[1],'XYZ'),new THREE.Euler(values[2],twist,0,'XYZ'),new THREE.Euler().setFromQuaternion(q12.clone().invert().multiply(desired),'XYZ')];
  for(let i=0;i<3;i++){const ranges=rig.nodes.find(n=>n.name===names[i])!.limits!,v=[angles[i].x,angles[i].y,angles[i].z];requireValue(v.every((x,k)=>x>=ranges[k][0]-1e-8&&x<=ranges[k][1]+1e-8),'LOADED_LEG_JOINT_LIMIT',{at_s:p.at_s,side,joint:names[i],v,ranges});rotations[names[i]]=new THREE.Quaternion().setFromEuler(angles[i]).toArray();}
 }
 return {...p,joint_rotations:rotations,maximum_IK_error_m:maximumError};
}
