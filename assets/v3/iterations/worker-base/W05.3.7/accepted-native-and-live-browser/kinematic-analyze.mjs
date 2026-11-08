import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const output=path.dirname(fileURLToPath(import.meta.url));
const repo=path.resolve(output,'../../..'),front=path.join(repo,'frontend');
const sha=b=>createHash('sha256').update(b).digest('hex');
const pins={
 'frontend/src/adaptive-v3/warehouseLoadedWalkCalibration.ts':'0435b5e93d4d674ffc7b0f11c2b8c0af214380437cc2cce938dcef9a9586d2e8',
 'frontend/src/adaptive-v3/warehouseWorkerGait.ts':'1909f2fcb42fad2de4776c98e2632f49609355669b0c25274227cbee184b79b3',
 'docs/adaptive-v3/evidence/W05.3.3-checks.json':'c2c56f4585305f4f5f7066c574914d6bc9e8b4b423d023491275b17024e2b118',
 'work/v3/loaded-walk-calibration-check/replay-trace.json':'29215652964588876a6f3af06da37d8c09111445ae8ccde15a0111708092379a',
 'frontend/public/models/v3/worker-base.glb':'542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163',
 'frontend/public/data/v3/worker-base-carry-pose.json':'f33bdb63db8fc78af68af173926a0a59267eda9f83b484a98e71ec4f375bac7b',
};
const inputs={};for(const[p,expected]of Object.entries(pins)){inputs[p]=await readFile(path.join(repo,p));assert.equal(sha(inputs[p]),expected,`Input changed: ${p}`);}
await mkdir(path.join(output,'cache'),{recursive:true});
const threeURL=pathToFileURL(path.join(front,'node_modules/three/build/three.module.js')).href;
const T=await import(threeURL),{GLTFLoader}=await import(pathToFileURL(path.join(front,'node_modules/three/examples/jsm/loaders/GLTFLoader.js'))),{default:ts}=await import(pathToFileURL(path.join(front,'node_modules/typescript/lib/typescript.js')));
const loaded=inputs['frontend/src/adaptive-v3/warehouseLoadedWalkCalibration.ts'].toString(),gaitSource=inputs['frontend/src/adaptive-v3/warehouseWorkerGait.ts'].toString();
const ast=ts.createSourceFile('loaded.ts',loaded,ts.ScriptTarget.Latest,true,ts.ScriptKind.TS);
const solver=ast.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='solveLoadedLegs');assert(solver);
const solverTS=`import * as THREE from ${JSON.stringify(threeURL)};const axisY=new THREE.Vector3(0,1,0);function requireValue(v,reason,details={}){if(!v)throw Object.assign(new Error(reason),{reason,details});}\n${solver.getFullText(ast)}\nexport {solveLoadedLegs};`;
const transpile=s=>ts.transpileModule(s,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
await writeFile(path.join(output,'cache/loaded-leg-solver.mjs'),transpile(solverTS));
await writeFile(path.join(output,'cache/warehouseWorkerGait.mjs'),transpile(gaitSource).replace("from 'three'",`from ${JSON.stringify(threeURL)}`).replace('from "three"',`from ${JSON.stringify(threeURL)}`));
const {solveLoadedLegs}=await import(pathToFileURL(path.join(output,'cache/loaded-leg-solver.mjs'))),{deriveNativeWorkerGaitRig,compileNativeWorkerGait}=await import(pathToFileURL(path.join(output,'cache/warehouseWorkerGait.mjs')));
const bytes=inputs['frontend/public/models/v3/worker-base.glb'];
const model=(await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'')).scene;
const root=model.getObjectByName('worker_base_root'),rig=deriveNativeWorkerGaitRig(root);
// The exact route starts aligned with the first segment, so fixed bounds cannot
// trigger the conditional retreat. Exact trace comparison below checks this.
const gait=compileNativeWorkerGait(rig,[[10.75,0,49],[6,0,49],[6,0,38]],-Math.PI/2,1.2,[]);
const trace=JSON.parse(inputs['work/v3/loaded-walk-calibration-check/replay-trace.json']);assert.equal(trace.duration_s,gait.duration_s);
const legNames=['L','R'].flatMap(side=>['thigh','shin','foot'].map(j=>'joint__'+j+'_'+side)),axisY=new T.Vector3(0,1,0),wrap=x=>Math.atan2(Math.sin(x),Math.cos(x));
const euler=q=>new T.Euler().setFromQuaternion(new T.Quaternion(...q),'XYZ').toArray().slice(0,3);
const range=()=>({min:Infinity,max:-Infinity,min_at_s:null,max_at_s:null});
const add=(r,v,t)=>{if(v<r.min){r.min=v;r.min_at_s=t;}if(v>r.max){r.max=v;r.max_at_s=t;}};
function hull(points){
 const p=[...new Map(points.map(v=>[v.join(','),v])).values()].sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
 const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);const l=[],u=[];
 for(const v of p){while(l.length>1&&cross(l.at(-2),l.at(-1),v)<=0)l.pop();l.push(v);}
 for(const v of p.toReversed()){while(u.length>1&&cross(u.at(-2),u.at(-1),v)<=0)u.pop();u.push(v);}
 return l.slice(0,-1).concat(u.slice(0,-1));
}
function hullDistance(poly,p){
 let inside=true,d=Infinity;
 for(let i=0;i<poly.length;i++){const a=poly[i],b=poly[(i+1)%poly.length],dx=b[0]-a[0],dy=b[1]-a[1];if(dx*(p[1]-a[1])-dy*(p[0]-a[0])<-1e-10)inside=false;const t=Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)));d=Math.min(d,Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy));}
 return inside?0:d;
}
const soleHulls=Object.fromEntries(rig.legs.map(l=>{const min=Math.min(...l.vertices.map(v=>v[1]));return[l.side,hull(l.vertices.filter(v=>Math.abs(v[1]-min)<2e-6).map(v=>[v[0]-l.sole[0],v[2]-l.sole[2]]))];}));
function legInfo(p,side){
 const l=rig.legs.find(l=>l.side===side),qs=['thigh','shin','foot'].map(j=>new T.Quaternion(...p.joint_rotations['joint__'+j+'_'+side]));
 const ankleQ=qs[0].clone().multiply(qs[1]).multiply(qs[2]);
 const lower=new T.Vector3(...l.b).applyQuaternion(qs[1]);
 // Source shin/ankle translations are oblique in the sagittal plane. The
 // signed *geometric* bend includes that rest shape, unlike shin Euler X.
 const signed=wrap(Math.atan2(lower.z,lower.y)-Math.atan2(l.a[2],l.a[1]));
 const a=new T.Vector3(...l.a),fullBend=a.angleTo(lower);
 const knee=new T.Vector3(...l.hip).add(a.clone().applyQuaternion(qs[0]));
 const ankle=knee.clone().add(new T.Vector3(...l.b).applyQuaternion(qs[0].clone().multiply(qs[1])));
 const sole=ankle.clone().add(new T.Vector3(...l.sole).applyQuaternion(ankleQ)).applyAxisAngle(axisY,p.yaw_rad).add(new T.Vector3(...p.root_world));
 const target=p.feet[side];
 const rootFoot=new T.Vector3(...p.root_world).sub(new T.Vector3(...target.point)).applyAxisAngle(axisY,-target.yaw_rad);
 return{signed_bend_rad:signed,full_3d_bend_rad:fullBend,knee_root_local_m:knee.toArray(),ankle_root_local_m:ankle.toArray(),sole_world_m:sole.toArray(),sole_error_m:sole.distanceTo(new T.Vector3(...target.point)),root_projection_outside_sole_hull_m:hullDistance(soleHulls[side],[rootFoot.x,rootFoot.z]),root_lateral_from_sole_m:rootFoot.x,sole_pitch_roll_error_rad:2*Math.acos(Math.min(1,Math.abs(ankleQ.dot(new T.Quaternion().setFromAxisAngle(axisY,target.yaw_rad-p.yaw_rad)))))};
}
function newStats(){return{samples:0,joints:Object.fromEntries(legNames.map(n=>[n,{quaternion_component_ranges:[range(),range(),range(),range()],euler_xyz_ranges_rad:[range(),range(),range()]}])),knee:Object.fromEntries(['L','R'].map(s=>[s,{joint_x_negative_samples:0,geometric_backbend_samples:0,signed_bend_rad:range(),full_3d_bend_rad:range()}])),root_y_m:range(),sole_error_m:range(),root_projection_outside_stance_sole_hull_m:range(),single_support_samples:0,double_support_samples:0,maximum_orientation_error_rad:0,maximum_IK_error_m:0};}
function accumulate(stat,p){
 stat.samples++;add(stat.root_y_m,p.root_world[1],p.at_s);stat.maximum_IK_error_m=Math.max(stat.maximum_IK_error_m,p.maximum_IK_error_m);
 for(const n of legNames){const q=p.joint_rotations[n],e=euler(q);q.forEach((v,k)=>add(stat.joints[n].quaternion_component_ranges[k],v,p.at_s));e.forEach((v,k)=>add(stat.joints[n].euler_xyz_ranges_rad[k],v,p.at_s));}
 let planted=0;
 for(const side of ['L','R']){const info=legInfo(p,side),k=stat.knee[side];add(k.signed_bend_rad,info.signed_bend_rad,p.at_s);add(k.full_3d_bend_rad,info.full_3d_bend_rad,p.at_s);if(euler(p.joint_rotations['joint__shin_'+side])[0]<-1e-8)k.joint_x_negative_samples++;if(info.signed_bend_rad<-1e-8)k.geometric_backbend_samples++;add(stat.sole_error_m,info.sole_error_m,p.at_s);stat.maximum_orientation_error_rad=Math.max(stat.maximum_orientation_error_rad,info.sole_pitch_roll_error_rad);if(p.feet[side].stance){planted++;add(stat.root_projection_outside_stance_sole_hull_m,info.root_projection_outside_sole_hull_m,p.at_s);}}
 if(planted===1)stat.single_support_samples++;if(planted===2)stat.double_support_samples++;
}
const accepted=newStats(),dense=newStats(),byStage={},rows=[];
const byLegRole=Object.fromEntries(['L','R'].map(s=>[s,Object.fromEntries(['stance','swing'].map(r=>[r,{samples:0,signed_geometric_bend_rad:range(),joints:Object.fromEntries(['thigh','shin','foot'].map(j=>[j,[range(),range(),range()]]))}]))]));
let maxTraceQDifference=0,maxTraceRootDifference=0;const arms=new Set();
for(const f of trace.frames){
 const p=solveLoadedLegs(rig,gait.sample(f.at_s));assert.equal(p.stage,f.gait_stage);
 maxTraceRootDifference=Math.max(maxTraceRootDifference,...p.root_world.map((v,k)=>Math.abs(v-f.actor_root_world_matrix[12+k])));
 for(const n of legNames)for(let k=0;k<4;k++)maxTraceQDifference=Math.max(maxTraceQDifference,Math.abs(p.joint_rotations[n][k]-f.joints[n].quaternion[k]));
 for(const [n,v]of Object.entries(f.joints))if(/joint__(upper_arm|forearm|palm_roll|hand)_/.test(n))arms.add(n+JSON.stringify(v.quaternion));
 accumulate(accepted,p);byStage[p.stage]??=newStats();accumulate(byStage[p.stage],p);
 for(const side of ['L','R']){const info=legInfo(p,side),role=byLegRole[side][p.feet[side].stance?'stance':'swing'];role.samples++;add(role.signed_geometric_bend_rad,info.signed_bend_rad,p.at_s);for(const j of ['thigh','shin','foot']){const n='joint__'+j+'_'+side,e=euler(p.joint_rotations[n]);e.forEach((v,k)=>add(role.joints[j][k],v,p.at_s));rows.push([p.at_s,p.stage,side,j,...p.joint_rotations[n],...e,p.feet[side].stance,info.signed_bend_rad,p.root_world[1],p.feet[side].lift_m,info.root_projection_outside_sole_hull_m]);}}
}
assert(maxTraceQDifference<1e-13);assert(maxTraceRootDifference<1e-13);assert.equal(arms.size,8);
const phaseRows=[],phaseStats=[];
for(let i=0;i<gait.phases.length;i++){
 const phase=gait.phases[i],duration=phase.end_s-phase.start_s,stat=newStats();
 for(let j=0;j<=100;j++){const t=phase.start_s+duration*j/100,p=solveLoadedLegs(rig,gait.sample(t));accumulate(stat,p);accumulate(dense,p);}
 const mid=solveLoadedLegs(rig,gait.sample((phase.start_s+phase.end_s)/2));
 const swingDistance=phase.swing?new T.Vector3(...phase.feet_from[phase.swing].point).distanceTo(new T.Vector3(...phase.feet_to[phase.swing].point)):0;
 const speed=mid.speed_m_s,advance=phase.profile?new T.Vector3(...gait.sample(phase.end_s).root_world).setY(0).distanceTo(new T.Vector3(...gait.sample(phase.start_s).root_world).setY(0)):0;
 const stride={index:i,kind:phase.kind,swing:phase.swing,start_s:phase.start_s,end_s:phase.end_s,duration_s:duration,mid_speed_m_s:speed,root_advance_m:advance,swing_distance_m:swingDistance,peak_swing_horizontal_velocity_bound_m_s:swingDistance*1.875/duration,peak_swing_vertical_velocity_m_s:phase.swing?.018*Math.PI/duration:0,peak_swing_horizontal_acceleration_bound_m_s2:swingDistance*(10/Math.sqrt(3))/(duration*duration),peak_swing_vertical_acceleration_m_s2:phase.swing?.036*Math.PI*Math.PI/(duration*duration):0,heading_delta_rad:phase.yaw_to-phase.yaw_from,root_y_m:stat.root_y_m,knee:stat.knee};
 phaseStats.push(stride);phaseRows.push([i,phase.kind,phase.swing??'',phase.start_s,phase.end_s,duration,speed,advance,swingDistance,stride.peak_swing_horizontal_velocity_bound_m_s]);
}
// Uniform time integration prevents epsilon-heavy accepted sample counts from
// being mistaken for percentages of duration. No collision probes are run.
const nTime=20000,dt=gait.duration_s/nTime;let single=0,double=0,negativeX={L:0,R:0},backbend={L:0,R:0};
const supportHull={outside_time_s:0,outside_distance_integral_m_s:0,maximum_outside_distance_m:0};
for(let i=0;i<nTime;i++){
 const p=solveLoadedLegs(rig,gait.sample((i+.5)*dt)),planted=['L','R'].filter(s=>p.feet[s].stance);
 if(planted.length===1)single+=dt;else if(planted.length===2)double+=dt;
 for(const side of ['L','R']){const info=legInfo(p,side);if(euler(p.joint_rotations['joint__shin_'+side])[0]<-1e-8)negativeX[side]+=dt;if(info.signed_bend_rad<-1e-8)backbend[side]+=dt;}
 if(planted.length===1){const d=legInfo(p,planted[0]).root_projection_outside_sole_hull_m;if(d>1e-6)supportHull.outside_time_s+=dt;supportHull.outside_distance_integral_m_s+=d*dt;supportHull.maximum_outside_distance_m=Math.max(supportHull.maximum_outside_distance_m,d);}
}
const walking=phaseStats.filter(p=>p.kind==='walk_step'),turning=phaseStats.filter(p=>p.kind==='turn_step');
const groups=[];for(const ph of gait.phases.filter(p=>p.profile)){if(!groups.some(g=>g.start_s===ph.profile.start_s))groups.push(ph.profile);}
const profiles=groups.map(g=>{const ps=phaseStats.filter(p=>p.kind==='walk_step'&&p.start_s>=g.start_s-1e-8&&p.end_s<=g.start_s+g.duration_s+1e-8),cruise=ps.filter(p=>Math.abs(p.duration_s-p.root_advance_m/g.peak_m_s)<1e-8);return{...g,footfall_count:ps.length,mean_footfalls_per_s:ps.length/g.duration_s,cruise_footfall_interval_s:cruise[0]?.duration_s,cruise_footfalls_per_s:cruise[0]?1/cruise[0].duration_s:null,cruise_same_foot_cycle_s:cruise[0]?2*cruise[0].duration_s:null,cruise_swing_distance_m:cruise[0]?.swing_distance_m,cruise_root_advance_m:cruise[0]?.root_advance_m,cruise_peak_swing_horizontal_velocity_m_s:Math.max(...cruise.map(p=>p.peak_swing_horizontal_velocity_bound_m_s)),cruise_peak_swing_horizontal_acceleration_m_s2:Math.max(...cruise.map(p=>p.peak_swing_horizontal_acceleration_bound_m_s2)),cruise_phase_count:cruise.length};});
const supportIntervals=Object.fromEntries(['L','R'].map(side=>{const intervals=[];for(const phase of gait.phases){const role=phase.swing===side?'swing':'stance',previous=intervals.at(-1);if(previous&&previous.role===role&&Math.abs(previous.end_s-phase.start_s)<1e-10)previous.end_s=phase.end_s;else intervals.push({role,start_s:phase.start_s,end_s:phase.end_s});}for(const r of intervals)r.duration_s=r.end_s-r.start_s;return[side,intervals];}));
const intervalSummary=Object.fromEntries(['L','R'].map(side=>[side,Object.fromEntries(['stance','swing'].map(role=>{const a=supportIntervals[side].filter(i=>i.role===role);return[role,{count:a.length,total_s:a.reduce((s,i)=>s+i.duration_s,0),minimum_interval_s:Math.min(...a.map(i=>i.duration_s)),maximum_interval_s:Math.max(...a.map(i=>i.duration_s))}];}))]));
const carrySpeed=.7,hold=.06,swingFraction=1-2*hold;
const carryGait=compileNativeWorkerGait(rig,[[10.75,0,49],[6,0,49],[6,0,38]],-Math.PI/2,carrySpeed,[]);
const smooth=u=>u*u*u*(10+u*(-15+6*u));
function candidateSample(t){
 const pure=carryGait.sample(t),phase=carryGait.phases.find(p=>pure.at_s>=p.start_s&&pure.at_s<p.end_s);
 if(!phase||!phase.swing||pure.at_s===0)return solveLoadedLegs(rig,pure);
 const u=(pure.at_s-phase.start_s)/(phase.end_s-phase.start_s),v=Math.max(0,Math.min(1,(u-hold)/swingFraction)),ease=smooth(v),side=phase.swing,from=phase.feet_from[side],to=phase.feet_to[side],lift=.018*Math.sin(Math.PI*v)**2;
 const feet={...pure.feet,[side]:{point:new T.Vector3(...from.point).lerp(new T.Vector3(...to.point),ease).add(new T.Vector3(0,lift,0)).toArray(),yaw_rad:from.yaw_rad+wrap(to.yaw_rad-from.yaw_rad)*ease,stance:u<=hold||u>=1-hold,lift_m:lift}};
 // Recompute root drop from these changed actual feet using the unchanged
 // source reach formula. Root horizontal position, heading, and profile clock
 // continue advancing through both support windows.
 const position=new T.Vector3(...pure.root_world);position.y+=pure.body_drop_m;let drop=0;
 for(const leg of rig.legs){const foot=feet[leg.side],local=new T.Vector3(...foot.point).sub(position).applyAxisAngle(axisY,-pure.yaw_rad),ankle=local.sub(new T.Vector3(...leg.sole).applyAxisAngle(axisY,foot.yaw_rad-pure.yaw_rad)),dx=ankle.x-leg.hip[0],dz=ankle.z-leg.hip[2],length=new T.Vector3(...leg.a).length()+new T.Vector3(...leg.b).length();drop=Math.max(drop,leg.hip[1]-ankle.y-Math.sqrt(Math.max(0,length*length-dx*dx-dz*dz)));}
 drop=Math.max(0,drop)+phase.margin_from+(phase.margin_to-phase.margin_from)*smooth(u);position.y-=drop;
 return solveLoadedLegs(rig,{...pure,root_world:position.toArray(),body_drop_m:drop,feet});
}
const candidateSubdivisions=1000,candidateTimes=new Set([0,carryGait.duration_s]);for(const p of carryGait.phases){for(let j=0;j<=candidateSubdivisions;j++)candidateTimes.add(p.start_s+(p.end_s-p.start_s)*j/candidateSubdivisions);for(const u of [hold,1-hold])for(const e of [-1e-8,0,1e-8])candidateTimes.add(p.start_s+(p.end_s-p.start_s)*u+e);}
const candidateStats=newStats(),candidateFailures=[],candidatePhaseRows=[];let minimumLimitMargin=Infinity,maximumHorizontalSourceRootDifference=0,maximumSourceYawDifference=0,maximumNewPureFootDifference=0,maximumRootYChange=0;
for(const t of [...candidateTimes].sort((a,b)=>a-b)){
 try{
  const p=candidateSample(t),pure=carryGait.sample(t);accumulate(candidateStats,p);
  maximumHorizontalSourceRootDifference=Math.max(maximumHorizontalSourceRootDifference,Math.abs(p.root_world[0]-pure.root_world[0]),Math.abs(p.root_world[2]-pure.root_world[2]));maximumSourceYawDifference=Math.max(maximumSourceYawDifference,Math.abs(p.yaw_rad-pure.yaw_rad));maximumRootYChange=Math.max(maximumRootYChange,Math.abs(p.root_world[1]-pure.root_world[1]));
  for(const side of ['L','R'])maximumNewPureFootDifference=Math.max(maximumNewPureFootDifference,new T.Vector3(...p.feet[side].point).distanceTo(new T.Vector3(...pure.feet[side].point)));
  for(const n of legNames){const e=euler(p.joint_rotations[n]),limits=rig.nodes.find(r=>r.name===n).limits;for(let k=0;k<3;k++)minimumLimitMargin=Math.min(minimumLimitMargin,e[k]-limits[k][0],limits[k][1]-e[k]);}
 }catch(error){candidateFailures.push({at_s:t,message:error.message,details:error.details??null});}
}
const candidateSupport={double_support_s:.7+(carryGait.duration_s-.7)*2*hold,single_support_s:(carryGait.duration_s-.7)*swingFraction,cruise_each_foot_stance_fraction_of_samefoot_cycle:(1+2*hold)/2};
const candidateProfiles=[];
for(const p of carryGait.phases){
 const duration=p.end_s-p.start_s;if(p.profile&&!candidateProfiles.some(g=>g.start_s===p.profile.start_s))candidateProfiles.push({...p.profile,cruise_step_interval_s:(p.profile.length_m/Math.ceil(p.profile.length_m/.22))/p.profile.peak_m_s});
 if(p.swing)candidatePhaseRows.push({kind:p.kind,swing:p.swing,start_s:p.start_s,end_s:p.end_s,liftoff_s:p.start_s+hold*duration,landing_s:p.end_s-hold*duration,phase_duration_s:duration,swing_duration_s:swingFraction*duration,double_support_before_s:hold*duration,double_support_after_s:hold*duration});
}
let maximumBoundaryRootDifference=0,maximumBoundaryFootDifference=0,maximumBoundaryJointAngleDifference=0;
for(const phase of carryGait.phases){const t=phase.end_s;if(t>=carryGait.duration_s)continue;try{const a=candidateSample(t-1e-8),b=candidateSample(t+1e-8);maximumBoundaryRootDifference=Math.max(maximumBoundaryRootDifference,new T.Vector3(...a.root_world).distanceTo(new T.Vector3(...b.root_world)));for(const side of ['L','R'])maximumBoundaryFootDifference=Math.max(maximumBoundaryFootDifference,new T.Vector3(...a.feet[side].point).distanceTo(new T.Vector3(...b.feet[side].point)));for(const n of legNames)maximumBoundaryJointAngleDifference=Math.max(maximumBoundaryJointAngleDifference,new T.Quaternion(...a.joint_rotations[n]).angleTo(new T.Quaternion(...b.joint_rotations[n])));}catch{}}
const candidate={kind:'one scratch carry-only stance/timing adapter; no production patch or new native gate',label:'explicit carry calibration / geometry-artistic style cap',carry_peak_speed_cap_m_s:carrySpeed,source_profile_speed_m_s:1.2,duration_s:carryGait.duration_s,added_duration_s:carryGait.duration_s-gait.duration_s,original_unloaded_duration_s:gait.duration_s,root_acceleration_peak_m_s2:.8,turn_step_duration_s:.32,foot_hold_fraction_each_end:hold,swing_fraction:swingFraction,source_gait_file_unchanged:true,original_pure_targets_unchanged:false,actual_changed_targets_re_solved:true,source_limits_unchanged:true,static_eight_arm_grip_unchanged:true,root_horizontal_and_yaw_match_carry_profile:maximumHorizontalSourceRootDifference===0&&maximumSourceYawDifference===0,maximum_changed_foot_target_vs_pure_carry_gait_m:maximumNewPureFootDifference,maximum_root_y_change_vs_pure_carry_gait_m:maximumRootYChange,minimum_original_joint_limit_margin_rad:minimumLimitMargin,sample_count:candidateTimes.size,joint_feasibility_passed:candidateFailures.length===0,failures:candidateFailures,statistics:candidateStats,support:candidateSupport,profiles:candidateProfiles.map(p=>({...p,cruise_footfalls_per_s:1/p.cruise_step_interval_s,cruise_swing_duration_s:p.cruise_step_interval_s*swingFraction,cruise_same_foot_cycle_s:p.cruise_step_interval_s*2,cruise_double_support_across_boundary_s:p.cruise_step_interval_s*2*hold,cruise_root_progress_during_double_support_m:p.cruise_step_interval_s*2*hold*carrySpeed,cruise_peak_swing_horizontal_velocity_m_s:3.75*carrySpeed/swingFraction})),phase_support_intervals:candidatePhaseRows,boundary_continuity_20ns:{maximum_root_difference_m:maximumBoundaryRootDifference,maximum_foot_difference_m:maximumBoundaryFootDifference,maximum_joint_angle_difference_rad:maximumBoundaryJointAngleDifference},new_collision_gate_run:false,limitations:['Joint/FK feasibility is not native material, foreign collision or continuous collision acceptance; the changed actual poses need the unchanged native gate before integration.','No lateral root transfer or heel/toe articulation was added.','No mass distribution, centre of mass, force or dynamic balance was measured.','A future loaded controller must expose the explicit 28.47 second candidate duration and support/phase times; the original accepted 20.345 second proof remains separate.']};
const summary={schema:'qoima.posture-naturalness.v1',scope:'read-only exact source/accepted-trace kinematics and one numeric carry-only retiming study',provenance:pins,graph:{project:'qoima-twin',generation:'2026-11-08T05:55:56Z',tier:'Verify with exact source fallback',exact_symbol_results:0,has_more:false,coverage:'three exact source/report paths no_recorded_issue / not_tracked; direct full source reads; no reindex'},source_rig_legs:rig.legs.map(({vertices,...l})=>({...l,upper_segment_length_m:new T.Vector3(...l.a).length(),lower_segment_length_m:new T.Vector3(...l.b).length(),rest_signed_sagittal_knee_bend_rad:wrap(Math.atan2(l.b[2],l.b[1])-Math.atan2(l.a[2],l.a[1])),sole_contact_hull_local_xz_m:soleHulls[l.side]})),source_limits:Object.fromEntries(rig.nodes.filter(n=>legNames.includes(n.name)).map(n=>[n.name,n.limits])),duration_s:gait.duration_s,accepted_frame_count:trace.frames.length,maximum_recompiled_joint_component_difference:maxTraceQDifference,maximum_recompiled_root_component_difference_m:maxTraceRootDifference,frozen_arm_quaternions_distinct_count:arms.size,accepted,dense_phase_100_subdivisions:dense,by_stage:byStage,by_leg_role:byLegRole,support_intervals:supportIntervals,support_interval_summary:intervalSummary,phase_counts:Object.fromEntries(['prepare','walk_step','retreat_step','turn_step','settle'].map(k=>[k,gait.phases.filter(p=>p.kind===k).length])),profiles,turn:{count:turning.length,total_s:turning.reduce((a,p)=>a+p.duration_s,0),footfall_interval_s:.32,footfalls_per_s:1/.32,stance_half_width_m:gait.assumptions.turn_stance_half_width_m},source_support_model:{swing_per_phase:'one leg for each entire open step interval; opposite foot planted; both planted only at instantaneous boundaries',double_support_positive_duration_during_steps_s:0,prepare_s:.35,settle_s:.35,single_support_exact_s:gait.duration_s-.7,double_support_exact_s:.7,root_lateral_route_sway_m:0,foot_world_pitch_roll_rad:0,heel_toe_roll:'none; whole sole remains world-horizontal through stance and swing'},uniform_time_integration:{samples:nTime,dt_s:dt,single_support_s:single,double_support_s:double,negative_knee_joint_x_duration_s:negativeX,geometric_backbend_duration_s:backbend,stance_root_projection_hull:supportHull,interpretation:'Root projection is not centre of mass. Polygon is convex hull of unchanged native sole bottom vertices within original 2um floor tolerance.'},phase_statistics:phaseStats,candidate};
await writeFile(path.join(output,'measurements.json'),JSON.stringify(summary,null,2)+'\n');
await writeFile(path.join(output,'timing-study.json'),JSON.stringify(candidate,null,2)+'\n');
await writeFile(path.join(output,'accepted-six-leg-quaternions.csv'),[['at_s','stage','side','joint','qx','qy','qz','qw','euler_x','euler_y','euler_z','stance','signed_geometric_knee_bend_rad','root_y_m','lift_m','root_projection_outside_sole_hull_m'].join(','),...rows.map(r=>r.join(','))].join('\n')+'\n');
await writeFile(path.join(output,'phase-timing.csv'),[['phase_index','kind','swing','start_s','end_s','duration_s','mid_speed_m_s','root_advance_m','swing_distance_m','peak_swing_horizontal_velocity_m_s'].join(','),...phaseRows.map(r=>r.join(','))].join('\n')+'\n');
// Recheck source pins after all read-only work.
for(const[p,expected]of Object.entries(pins))assert.equal(sha(await readFile(path.join(repo,p))),expected);
console.log(JSON.stringify({duration:gait.duration_s,phase_counts:summary.phase_counts,profiles,accepted:{root_y:accepted.root_y_m,knee:accepted.knee,sole_error:accepted.sole_error_m},uniform:summary.uniform_time_integration,candidate:{...candidate,statistics:{root_y_m:candidateStats.root_y_m,sole_error_m:candidateStats.sole_error_m,knee:candidateStats.knee},phase_support_intervals:undefined,failures:candidateFailures.length?candidateFailures.slice(0,3):[]},maxTraceQDifference,maxTraceRootDifference},null,2));
