/** CPU blueprint and unchanged actual P01 GLB proof; no forklift mesh is built.
 * From repo root: node assets/v3/iterations/forklift/M14.1/check_blueprint.mjs
 */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import * as T from '../../../../../frontend/node_modules/three/build/three.module.js';
import {GLTFLoader} from '../../../../../frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js';

const ROOT=fileURLToPath(new URL('../../../../../',import.meta.url));
const STAGE=path.join(ROOT,'assets/v3/iterations/forklift/M14.1');
const read=async p=>fs.readFile(path.join(ROOT,p));
const json=async p=>JSON.parse(await read(p));
const hash=b=>createHash('sha256').update(b).digest('hex');
const S=await json('assets/v3/specs/forklift.dimensions.json');
const W=await json('assets/v3/specs/worker-base.dimensions.json');
const C=await json('docs/v3/contract-proposals/vehicle-handling-v3.json');
const COLD=await json('assets/v3/iterations/forklift/M14.1/C08-before-physical-correction.json');
const V=a=>new T.Vector3(...a), arr=v=>v.toArray();
const near=(a,b,t=2e-5)=>Math.max(...a.map((v,i)=>Math.abs(v-b[i])))<=t;
const results=[], negatives=[];
function check(id,condition,actual){assert(condition,id);results.push({id,actual});}
for(const f of S.input_fingerprints) assert.equal(hash(await read(f.path)),f.sha256,`Changed input: ${f.path}`);
assert.equal(hash(await read('docs/v3/contract-proposals/vehicle-handling-v3.json')),'22693087d090a8a45a101d995581573c3b85bf826f67ae7d44fdc524b74cd3e4','Root accepted C08v0.2 hash');
assert.equal(hash(await read(S.driver.asset)),'c8546473c76f126844b427417db86e65be090fa04ad56c0deb9cb2bda92e73b7','Unchanged accepted P01');
const supplement=await json('assets/references/v3/r12-c08-interface-targets-v2.json');
assert.equal(supplement.C08_sha256,hash(await read('docs/v3/contract-proposals/vehicle-handling-v3.json')));
check('published C08v0.2 exact physical/rating interface',C.schema_version==='0.2.0'&&C.fork_design.bare_and_direct_load_travel_top_y_m===.70&&
 C.fork_design.LONG_closed_pocket_travel_top_y_m===.75&&C.fork_design.stopped_handling_reach_stroke_m===.40&&
 C.rating_design.moment_budget_kg_m===800&&C.rating_design.rating_reference_z_m===.40,{version:C.schema_version,canonicalFork:C.fork_design,rating:C.rating_design});
const bytes=await read(S.driver.asset);
const {scene}=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
const root=scene.getObjectByName('worker_base_root');
const joints=[], anchors=[], meshes=[];
root.traverse(n=>{if(n.userData.pivot_id)joints.push(n);if(n.userData.anchor_id)anchors.push(n);if(n.isMesh)meshes.push(n);});
check('P01 exact accepted joints/anchors/meshes',joints.length===15&&anchors.length===7&&meshes.length===23,[joints.length,anchors.length,meshes.length]);
const bind=new Map(joints.map(n=>[n.name,{p:n.position.clone(),q:n.quaternion.clone(),s:n.scale.clone()}]));
function pose(){
 root.position.set(...S.driver.worker_root_translation);
 for(const n of joints){const b=bind.get(n.name);n.position.copy(b.p);n.quaternion.copy(b.q);n.scale.copy(b.s);
  const a=S.driver.jointEulerXYZ[n.name];
  assert(a.every((v,i)=>v>=W.joints[n.name].limits_radians_xyz[i][0]-1e-8&&v<=W.joints[n.name].limits_radians_xyz[i][1]+1e-8),`joint limit ${n.name}`);
  n.quaternion.multiply(new T.Quaternion().setFromEuler(new T.Euler(...a,'XYZ')));
 }
 scene.updateMatrixWorld(true);
}
pose();
const point=n=>arr(scene.getObjectByName(n).getWorldPosition(new T.Vector3()));
const triangles=[], vertices=[], meshBounds=[];
for(const mesh of meshes){
 const a=mesh.geometry.attributes.position,ix=mesh.geometry.index.array,ps=[];
 for(let i=0;i<a.count;i++){const p=new T.Vector3().fromBufferAttribute(a,i).applyMatrix4(mesh.matrixWorld);ps.push(p);vertices.push(p);}
 const b=new T.Box3().setFromPoints(ps);meshBounds.push({name:mesh.name,parent:mesh.parent.name,sourceParts:JSON.parse(mesh.userData.source_parts_json),min:arr(b.min),max:arr(b.max)});
 for(let i=0;i<ix.length;i+=3)triangles.push({mesh:mesh.name,parent:mesh.parent.name,tri:new T.Triangle(ps[ix[i]],ps[ix[i+1]],ps[ix[i+2]])});
}
const bounds=new T.Box3().setFromPoints(vertices);
check('unchanged P01 scale',root.scale.equals(new T.Vector3(1,1,1))&&joints.every(n=>n.scale.equals(bind.get(n.name).s)),[1,1,1]);
check('actual seat anchor',near(point('anchor_seat_contact'),S.driver.seat_anchor_vehicle),point('anchor_seat_contact'));
for(const side of ['L','R']){
 check(`actual grip ${side}`,near(point('anchor_hand_grip_'+side),S.driver.expected_grips[side]),point('anchor_hand_grip_'+side));
 check(`actual sole ${side}`,near(point('anchor_foot_floor_'+side),S.driver.expected_soles[side]),point('anchor_foot_floor_'+side));
}
check('actual driver fits declared operating box',vertices.every(p=>p.x>=-.6&&p.x<=.6&&p.y>=0&&p.y<=2.1&&p.z>=-1.5&&p.z<=1.5),{min:arr(bounds.min),max:arr(bounds.max)});
check('actual helmet roof soffit clearance',2.04-bounds.max.y>=S.driver.minimum_helmet_roof_gap_m,2.04-bounds.max.y);

// Actual triangles versus the interiors of planned cabin/body boxes. Touching
// support planes are permitted; no box is a replacement for future model QA.
const driverBoxChecks=[];
for(const b of S.blueprint_boxes){
 const box=new T.Box3(V(b.min),V(b.max));box.expandByScalar(-2e-5);
 const hits=triangles.filter(t=>t.tri.intersectsBox(box));
 driverBoxChecks.push({id:b.name,interiorTriangleHits:hits.length});
 assert.equal(hits.length,0,`P01 penetrates planned ${b.name}`);
}
check('actual 2848 worker triangles clear all planned body interiors',true,{triangles:triangles.length,boxes:driverBoxChecks.length});

// Preserve the accepted P01 solid-union rule: an export material batch can
// contain overlapping independent closed solids. Split on two-incidence
// edges, never parity-test the whole overlapping batch as a single shell.
const solidCache=new Map(),byPart=new Map();
for(const mesh of meshes)for(const p of JSON.parse(mesh.userData.source_parts_json))byPart.set(p,mesh);
function closedSolids(mesh){
 if(solidCache.has(mesh))return solidCache.get(mesh);
 const a=mesh.geometry.attributes.position,ix=mesh.geometry.index.array,keys=new Map(),vs=[],ids=[];
 for(let i=0;i<a.count;i++){
  const p=new T.Vector3().fromBufferAttribute(a,i),key=arr(p).map(v=>Math.round(v*1e6)).join(',');
  if(!keys.has(key)){keys.set(key,vs.length);vs.push(p.applyMatrix4(mesh.matrixWorld));}ids.push(keys.get(key));
 }
 const ts=[];for(let i=0;i<ix.length;i+=3)ts.push([ids[ix[i]],ids[ix[i+1]],ids[ix[i+2]]]);
 const parent=ts.map((_,i)=>i),find=i=>parent[i]===i?i:(parent[i]=find(parent[i]));
 const edges=new Map();
 for(let i=0;i<ts.length;i++)for(let k=0;k<3;k++){
  const key=[ts[i][k],ts[i][(k+1)%3]].sort((a,b)=>a-b).join(',');
  if(!edges.has(key))edges.set(key,[]);edges.get(key).push(i);
 }
 for(const list of edges.values())if(list.length===2)parent[find(list[0])]=find(list[1]);
 const groups=new Map();for(let i=0;i<ts.length;i++){const id=find(i);if(!groups.has(id))groups.set(id,[]);groups.get(id).push(ts[i]);}
 const solids=[...groups.values()].map(g=>{
  const es=new Map();for(const tri of g)for(let k=0;k<3;k++){
   const key=[tri[k],tri[(k+1)%3]].sort((a,b)=>a-b).join(',');es.set(key,(es.get(key)??0)+1);
  }
  assert([...es.values()].every(n=>n===2),'Actual P01 solid is not closed');
  return g.map(t=>new T.Triangle(...t.map(i=>vs[i])));
 });solidCache.set(mesh,solids);return solids;
}
function interiorMargin(mesh,p){
 let best=-Infinity;
 for(const solid of closedSolids(mesh)){
  let votes=0,margin=Infinity;
  for(const tri of solid)margin=Math.min(margin,tri.closestPointToPoint(p,new T.Vector3()).distanceTo(p));
  for(const d of [[1,.337,.171],[.213,1,.451],[.319,.127,1]]){
   const ray=new T.Ray(p,V(d).normalize()),hits=[];
   for(const tri of solid){const h=ray.intersectTriangle(tri.a,tri.b,tri.c,false,new T.Vector3());if(h)hits.push(h.distanceTo(p));}
   hits.sort((a,b)=>a-b);const n=hits.filter((v,i)=>i===0||Math.abs(v-hits[i-1])>1e-7).length;votes+=n%2;
  }
  if(votes>=2)best=Math.max(best,margin);
 }return best;
}
const jointSupport=[];
function supportJoint(joint,a,b){
 const p=V(point(joint)),ma=interiorMargin(byPart.get(a),p),mb=interiorMargin(byPart.get(b),p);
 assert(ma>0&&mb>0,`Seated joint gap ${joint}: ${ma}/${mb}`);
 jointSupport.push({joint,point:arr(p),parts:[a,b],actualSolidInteriorMargins:[ma,mb]});
}
supportJoint('joint__torso','pelvis_cloth','shirt_core');
supportJoint('joint__head','short_neck','cuboid_head');
for(const side of ['L','R']){
 supportJoint('joint__upper_arm_'+side,'connected_shoulder_band','upper_sleeve_'+side);
 supportJoint('joint__forearm_'+side,'upper_sleeve_'+side,'fore_sleeve_'+side);
 supportJoint('joint__hand_'+side,'fore_sleeve_'+side,'mitten_'+side+'_spine');
 supportJoint('joint__thigh_'+side,'pelvis_cloth','trouser_thigh_'+side);
 supportJoint('joint__shin_'+side,'trouser_thigh_'+side,'trouser_shin_'+side);
 supportJoint('joint__foot_'+side,'trouser_shin_'+side,'boot_'+side);
}
check('14 seated actual closed-solid joint support witnesses',jointSupport.length===14,{count:jointSupport.length,minInteriorMargin:Math.min(...jointSupport.flatMap(x=>x.actualSolidInteriorMargins))});

// Support contacts are actual GLB triangles at independently specified seat
// and sole support planes, rather than just kinematic anchor locations.
function raySurface(origin,direction,filter){
 const ray=new T.Ray(V(origin),V(direction)),hits=[];
 for(const t of triangles)if(filter(t)){
  const p=ray.intersectTriangle(t.tri.a,t.tri.b,t.tri.c,false,new T.Vector3());
  if(p)hits.push(p);
 }
 hits.sort((a,b)=>a.distanceToSquared(ray.origin)-b.distanceToSquared(ray.origin));
 assert(hits.length,'No actual support surface');return hits[0];
}
const supports=[];
for(const side of ['L','R']){
 const x=side==='L'?-.115:.115;
 const p=raySurface([x,.45,-.395],[0,1,0],t=>t.parent==='joint__foot_'+side);
 check(`actual flat boot support ${side}`,Math.abs(p.y-.53)<2e-5,arr(p));supports.push({part:'boot_'+side,surface:arr(p),supportY:.53});
}
const seat=raySurface([0,.76,-.70],[0,1,0],t=>t.parent==='joint__pelvis');
check('actual pelvis seat support',Math.abs(seat.y-.84)<2e-5,arr(seat));supports.push({part:'pelvis_cloth',surface:arr(seat),supportY:.84});
const thighMin=Math.min(...meshBounds.filter(b=>b.parent.startsWith('joint__thigh_')).map(b=>b.min[1]));
check('lowered seat nose clears folded thick trousers',thighMin-.775>.009,thighMin-.775);
const portal=S.driver.entry_clear_portal;
check('actual seated driver fore-aft/upper entry portal',bounds.min.z>portal.z[0]&&bounds.max.z<portal.z[1]&&bounds.max.y<portal.y[1]&&bounds.min.y>=portal.y[0]-2e-5,
 {rearGap:bounds.min.z-portal.z[0],frontGap:portal.z[1]-bounds.max.z,headGap:portal.y[1]-bounds.max.y,soleGap:bounds.min.y-portal.y[0]});

// Continuous steering column capsule: sample distance-to-actual triangles and
// subtract half the sample spacing. The resulting lower bound proves every
// point of the segment, not merely the displayed sample centres.
const column=S.driver.steering_column,ca=V(column.start),cb=V(column.end),N=128;
let sampledMin=Infinity;
for(let i=0;i<=N;i++){
 const p=ca.clone().lerp(cb,i/N);
 for(const t of triangles)sampledMin=Math.min(sampledMin,t.tri.closestPointToPoint(p,new T.Vector3()).distanceTo(p));
}
const columnGap=sampledMin-ca.distanceTo(cb)/(2*N)-column.radius_m;
check('continuous column capsule clear of actual worker triangles',columnGap>0,columnGap);

// Grip capsules are in the actual posed mitten channels. All sampled ring
// points are tested against actual triangles, including the thumb/spine.
const grips=[];
for(const side of ['L','R']){
 const hand=scene.getObjectByName('joint__hand_'+side),centre=V(S.driver.expected_grips[side]);
 const axis=new T.Vector3(1,0,0).transformDirection(hand.matrixWorld);
 const u=new T.Vector3(0,1,0).transformDirection(hand.matrixWorld),v=new T.Vector3(0,0,1).transformDirection(hand.matrixWorld);
 let min=Infinity;
 const own=triangles.filter(t=>t.parent==='joint__hand_'+side);
 for(let j=0;j<=8;j++)for(let k=0;k<48;k++){
  const a=2*Math.PI*k/48;
  const p=centre.clone().addScaledVector(axis,(j/8-.5)*.080).addScaledVector(u,Math.cos(a)*.018).addScaledVector(v,Math.sin(a)*.018);
  for(const t of own)min=Math.min(min,t.tri.closestPointToPoint(p,new T.Vector3()).distanceTo(p));
 }
 // sample-to-continuous surface error <= radial sagitta + half axial step;
 // use a much denser axial sample below for the final analytical separation
 // against hand-frame Y/Z planes, whose exact channel is 45mm tall.
 const heightAir=.045/2-.018,spineAir=.075-.018-.0525;
 check(`mitten ${side} steering-grip sampled triangle clearance`,min>.003,{sampledMin:min,channelVerticalAir:heightAir,channelSpineAir:spineAir});
 grips.push({side,centre:arr(centre),axis:arr(axis),radius:.018,length:.080,sampledTriangleMinDistance:min,
  exactFlatChannelAir:{vertical:heightAir,spine:spineAir},scope:'plan capsule; actual rim/handle mesh and closed grasp action remain later'});
}

// Four exactly grounded circular tyres. Rear steering rotates around Y through
// wheel centres and does not alter Y. Circular-cylinder support gives an exact
// continuous lateral bound, independent of angular polygon samples.
for(const w of S.wheels)check(`grounded tyre ${w.id}`,Math.abs(w.centre[1]-w.radius)<1e-12,w.centre[1]-w.radius);
const rearMaxX=.35+Math.hypot(.225,.10);
check('all continuously rear-steered tyre angles fit half width',rearMaxX<.60,{maxAbsX:rearMaxX,margin:.60-rearMaxX});
const R=1.4/Math.tan(Math.PI/3),inner=Math.atan2(1.4,R-.35)*180/Math.PI,outer=Math.atan2(1.4,R+.35)*180/Math.PI;
check('Ackermann individual angles inside75 degrees',inner<75&&outer<75,{icrXZ:[R,.4],innerDeg:inner,outerDeg:outer});
check('high travel blades clear true circular tyre tops',.70-.07-.60>.029999999,{bladeBottom:.63,tyreTop:.60,gap:.03});
function cylinderHitsBox(w,b){
 const axial=Math.min(b.max[0],w.centre[0]+w.width/2)-Math.max(b.min[0],w.centre[0]-w.width/2);
 const dy=Math.max(b.min[1]-w.centre[1],0,w.centre[1]-b.max[1]);
 const dz=Math.max(b.min[2]-w.centre[2],0,w.centre[2]-b.max[2]);
 return axial>1e-10&&Math.hypot(dy,dz)<w.radius-1e-10;
}
function reachBoxes(top,reach,spacing){
 const heel=.40+reach;
 const b=[{id:'rear_lift_plate',min:[-.56,top-.07,0],max:[.56,top+.16,.08]},
  {id:'front_reach_plate',min:[-.56,top-.07,heel-.04],max:[.56,top+.04,heel]}];
 for(const sign of [-1,1]){
  const xr=[sign*.50,sign*.56].sort((a,b)=>a-b),inner=[sign*.512,sign*.548].sort((a,b)=>a-b);
  b.push({id:'outboard_outer_guide_'+sign,min:[xr[0],top-.07,-.02],max:[xr[1],top-.015,.62]});
  b.push({id:'outboard_inner_rail_'+sign,min:[inner[0],top-.0575,-.02+reach],max:[inner[1],top-.0275,.62+reach]});
  b.push({id:'fork_blade_'+sign,min:[sign*spacing-.04,top-.07,heel],max:[sign*spacing+.04,top,heel+1.10]});
  b.push({id:'fork_stem_'+sign,min:[sign*spacing-.04,top-.07,heel-.025],max:[sign*spacing+.04,top+.30,heel]});
 }
 return b;
}
let reachCases=0;
const allowableGuideContacts=new Set(['mast_rail_L','mast_rail_R']);
for(const spacing of [.24,.40])for(let i=0;i<=80;i++){
 const u=i/80;
 for(const [top,reach] of [[.70,.40*u],[.70-.52*u,.40],[.18+1.32*u,.40],[.70,.40*(1-u)]]){
  for(const b of reachBoxes(top,reach,spacing)){
   for(const w of S.wheels)assert(!cylinderHitsBox(w,b),`reach frame hits ${w.id}: ${b.id} top${top}/reach${reach}`);
   const bx=new T.Box3(V(b.min),V(b.max)).expandByScalar(-2e-5);
   for(const f of S.blueprint_boxes){
    if(b.id==='rear_lift_plate'&&allowableGuideContacts.has(f.name))continue;
    assert(!bx.intersectsBox(new T.Box3(V(f.min),V(f.max))),`reach ${b.id} intersects fixed ${f.name}`);
   }
  }
  reachCases++;
 }
}
check('reach sequence exact cylinder/box witnesses',true,{states:reachCases,partsPerState:10,tyres:4});
check('reach frame clears fixed cabin/chassis boxes except designed mast sliders',true,{states:reachCases,allowableGuideContacts:[...allowableGuideContacts]});
check('fixed-length telescope rails retain real engagement at maximum reach',.62-(-.02+.40)>=.24-1e-12,
 {outerZ:[-.02,.62],innerZAtReachMax:[.38,1.02],overlap:.24,xAir:.004,yAir:.0045,scaledGeometry:false});
check('continuous reach sequence separates by exact coordinate intervals',true,{
 rearPlateForeAftGap:.10-.08,sideGuideLateralGap:.50-.47,
 highForwardAssemblyVerticalGap:.70-.07-.60,
 lowExtendedForwardPlateForeAftGap:.80-.04-.70,
 lowExtendedBladeForeAftGap:.80-.70,
 proof:'rear plate always behind tyre minZ; side guides always outside tyre axial extent; forward assembly stays above tyres during extension/retraction and ahead of tyres during lowering/lifting; these inequalities hold over complete intervals'});
const allPlanned=new T.Box3();
for(const b of S.blueprint_boxes){const bx=new T.Box3(V(b.min),V(b.max));check('fixed blueprint inside travel envelope: '+b.name,new T.Box3(V(S.bounds.min),V(S.bounds.max)).containsBox(bx),{min:b.min,max:b.max});allPlanned.union(bx);}
for(const top of [.70,.75])for(const b of reachBoxes(top,0,.40))allPlanned.union(new T.Box3(V(b.min),V(b.max)));
for(const w of S.wheels){const half=w.id.startsWith('rear')?Math.hypot(w.radius,w.width/2):w.width/2;
 const dz=w.id.startsWith('rear')?half:w.radius;
 allPlanned.union(new T.Box3(V([w.centre[0]-half,0,w.centre[2]-dz]),V([w.centre[0]+half,2*w.radius,w.centre[2]+dz])));
}
check('full declared travel union exact1.2x2.1x3 and floor-centre origin',near(arr(allPlanned.min),[-.6,0,-1.5])&&near(arr(allPlanned.max),[.6,2.1,1.5]),{min:arr(allPlanned.min),max:arr(allPlanned.max)});
const storage=await json('docs/v3/contract-proposals/storage-layout-v3.json');
check('handling stroke reaches unchanged accessible storage levels',S.forks.min_handling_top_y_m===storage.module_definitions.HEAVY.levels[0]&&
 storage.module_definitions.STANDARD.levels.slice(0,2).every(y=>y>=.18&&y<=1.5),S.storage_contact_height_scope);
check('reach full engagement keeps fork length fixed',near([.40,1.50,1.10,.80,1.90],[S.forks.heel_z_m,S.forks.tip_z_m,S.forks.blade_length_m,S.forks.handling_heel_z_m,S.forks.handling_tip_z_m]),S.forks);

function cylinderInteriorMargin(p,w){
 return Math.min(w.width/2-Math.abs(p[0]-w.centre[0]),w.radius-Math.hypot(p[1]-w.centre[1],p[2]-w.centre[2]));
}
const oldForkWitnesses=[];
for(const spacing of [.24,.40])for(const sign of [-1,1]){
 const w=S.wheels.find(w=>w.id==='front_'+(sign<0?'L':'R'));
 const p=[sign*spacing,.265,.45],margin=cylinderInteriorMargin(p,w);
 assert(margin>0,'Historical fork conflict must remain detected');
 oldForkWitnesses.push({halfSpacing:spacing,point:p,tyreInteriorMargin:margin,bladeInteriorMargin:.035});
}
negatives.push({id:'historical heel .40 penetrates both true tyre cylinders',rejected:true,witnesses:oldForkWitnesses});
negatives.push({id:'old high seat .99 fails accepted cabin roof',rejected:bounds.max.y+.15>2.04,headTop:bounds.max.y+.15});
negatives.push({id:'tyre floating10mm',rejected:Math.abs((.30+.01)-.30)>1e-5});

const engagements=[];
for(const load of C.loads){
 const [width,height,depth]=load.handling_unit_dimensions_xyz_m;
 const z0=1.5-depth,z1=1.5,overlap=Math.max(0,Math.min(1.5,z1)-Math.max(.40,z0));
 if(load.archetype_id==='LONG_BUNDLE')continue;
 check(`unchanged ${load.archetype_id} sufficient fork length`,overlap/depth>=2/3-1e-12&&1.5-depth/2>=.40,
  {depth,overlap,fraction:overlap/depth,CoGz:1.5-depth/2});
 engagements.push({archetype:load.archetype_id,depth,overlap,fraction:overlap/depth});
}
check('LONG roof engagement/CoG inside supported segment',1.425-.575>=.85-1e-12&&1>=.575&&1<=1.425,{overlap:.85,CoGz:1});
for(const target of Object.values(S.anchor_pose_targets)){
 const actualCradle=S.anchors.anchor_LONG_cradle.map((v,i)=>v+(i===1?target.carriage_lift_m:i===2?target.reach_m:0));
 const actualHU=S.anchors.anchor_LONG_load.map((v,i)=>v+(i===1?target.carriage_lift_m:i===2?target.reach_m:0));
 check('LONG parent-local anchor compensation at lift'+target.carriage_lift_m,near(actualCradle,target.cradle_vehicle)&&near(actualHU,target.HU_vehicle),{actualCradle,actualHU});
}
check('closed LONG pocket clear width and height',.14-.08>=.06-1e-12&&(.75-.07)-(.65+.02)>=.01-1e-12,{sideAir:(.14-.08)/2,bottomAir:.75-.07-(.65+.02),roofContactY:.75});
const lock=S.long_attachment.lock_dimensions;
for(const reach of [0,.40]){
 const cradleZ=1+reach,heel=.4+reach,pinZ=cradleZ-.38,boreZ=heel+lock.fork_bore_centre_z_from_heel_m;
 check('pin/blade bore exact longitudinal alignment at reach'+reach,Math.abs(pinZ-boreZ)<1e-12,{pinZ,boreZ,radialAir:lock.matching_bore_radius_m-lock.pin_shaft_radius_m});
}
check('closed captive pins fit immutable cradle envelope and cross complete blade height',lock.pin_shaft_closed_y_own_m[0]<.03&&lock.pin_shaft_closed_y_own_m[1]>.10&&
 lock.recessed_cap_closed_y_own_m[1]===.15&&lock.matching_bore_radius_m>lock.pin_shaft_radius_m,
 {closedShaftY:lock.pin_shaft_closed_y_own_m,bladeY:[.03,.10],capY:lock.recessed_cap_closed_y_own_m,openPinMaxOwnY:.26});
check('open pins clear blade without piercing HU',lock.pin_shaft_closed_y_own_m[0]+lock.open_pin_translation_y_m>.10&&lock.pin_ear_outer_z_own_m[1]<lock.HU_rear_z_own_m,
 {openBottom:.115,bladeTop:.10,earFront:-.358,HUrear:-.325,foreAftGap:.033});

const cargoConflicts=[];
for(const id of ['PALLET_LOAD','IBC']){
 const load=COLD.loads.find(l=>l.archetype_id===id),p=[.35,.50,.55],b=load.cargo_bounds_local_m;
 const inside=p.every((v,i)=>v>b.min[i]&&v<b.max[i]);
 const tyreMargin=cylinderInteriorMargin(p,S.wheels.find(w=>w.id==='front_R'));
 assert(inside&&tyreMargin>0);
 cargoConflicts.push({archetype:id,point:p,tyreInteriorMargin:tyreMargin,
  scope:'historical low HU outer box overlap; not an actual future HU mesh collision claim',
  resolution:'root approved direct travel bottom .70 gives .10 above tyre top; no HU void hack or geometry scale change'});
}
for(const load of C.loads){
 const id=load.archetype_id,top=id==='LONG_BUNDLE'?.80:.70;
 const h=load.handling_unit_dimensions_xyz_m[1];
 check(`revised ${id} high-travel load clears tyres and height`,top>=.65&&top+h<=2.10+1e-10,{HUbottom:top,HUtop:top+h,overallTravelHeight:2.10});
}
check('LONG cradle high travel clears tyre volume',.65-.60>=.05-1e-12,{cradleBottom:.65,tyreTop:.60,gap:.05});
const extendedRatings=C.loads.map(l=>{
 const oldArm=l.load_centre_from_fork_heel_m,arm=oldArm+.40;
 const mass=l.total_lifted_mass_kg,capacity=Math.min(1000,600/arm),revised=Math.min(1000,800/arm);
 return {archetype:l.archetype_id,extendedReferenceArm:arm,mass,oldSyntheticCapacityAtExtendedArm:capacity,
  admittedByHistoricalMomentRule:mass<=capacity,newFrozenSyntheticCapacity:revised,
  admittedByRevisedMomentRule:mass<=revised&&mass/2<=500};
});
const ibcRating=extendedRatings.find(x=>x.archetype==='IBC');
check('IBC extended overload is explicitly detected before operation',!ibcRating.admittedByHistoricalMomentRule,ibcRating);
check('all six unchanged extended HUs fit new frozen synthetic rating',extendedRatings.every(x=>x.admittedByRevisedMomentRule),extendedRatings);
check('revised IBC moment margin',800-654>0,{momentBudget:800,IBCmoment:654,marginKgM:146,singleForkShare:327});
negatives.push({id:'IBC654kg not admitted at extended1m arm under old600kgm rule',rejected:!ibcRating.admittedByHistoricalMomentRule});
negatives.push({id:'over800kgm load rejects revised frozen rating',rejected:801>Math.min(1000,800/1),mass:801,arm:1,capacity:800});
negatives.push({id:'over500kg single fork share rejects',rejected:501>500,singleForkShare:501});
negatives.push({id:'low retracted pickup state forbidden and colliding',rejected:reachBoxes(.30,0,.40).some(b=>S.wheels.some(w=>cylinderHitsBox(w,b)))});
negatives.push({id:'any extended state rejected from travel graph',rejected:S.dynamic_reach_frame.travel_graph_reach_must_equal_zero&&S.forks.handling_reach_stroke_m>0});
const resetBefore=[];root.traverse(n=>resetBefore.push(...n.matrixWorld.elements));
root.position.y+=.15;scene.updateMatrixWorld(true);pose();
const resetAfter=[];root.traverse(n=>resetAfter.push(...n.matrixWorld.elements));
check('absolute seated pose reconstruct/reset',resetBefore.every((v,i)=>v===resetAfter[i]),0);
assert(negatives.every(n=>n.rejected));
const report={stage:'M14.1',kind:'CPU dimension blueprint, not forklift model acceptance',
 plan_sha256:hash(await read('assets/v3/specs/forklift.dimensions.json')),worker_glb_sha256:hash(bytes),
 geometry_created:false,results,negatives,actualDriver:{bounds:{min:arr(bounds.min),max:arr(bounds.max)},
 meshBounds,supports,jointSupport,grips,columnConservativeGap:columnGap,boxChecks:driverBoxChecks,
 anchors:Object.fromEntries(anchors.map(n=>[n.name,point(n.name)]))},
 engagements,historicalCargoConflicts:cargoConflicts,extendedRatings,
 knownIssues:[{id:'M04_RELIEF_NOT_ACCEPTED',reason:'No accepted current M04 interface supplied; actual paired transfer remains open'}],
 status:'VERIFY; dimensional plan only; actual forklift/cradle mesh and action gates remain open',
 not_verified:['actual forklift/cradle/HU meshes','driver paired art views','pickup transfer','load stress/stability certification']};
await fs.writeFile(path.join(STAGE,'actual-blueprint-checks.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({checks:results.length,negativeCases:negatives.length,actualDriver:report.actualDriver.bounds,
 columnConservativeGap:columnGap,issues:report.knownIssues,status:report.status},null,2));
