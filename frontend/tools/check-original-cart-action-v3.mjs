/** Real native rack/cargo buffers, all candidate instances. No WebGL or physics sweep. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const here=path.dirname(fileURLToPath(import.meta.url)),repo=path.resolve(here,'../..'),flags=new Map();
for(let i=2;i<process.argv.length;i+=2){assert(process.argv[i]==='--out'&&process.argv[i+1],'Use optional --out work/path');flags.set(process.argv[i],process.argv[i+1]);}
const own=path.resolve(repo,flags.get('--out')??('work/v3/full-tz-closeout-20261109/original-cart/portable-'+Date.now())),relativeOut=path.relative(path.join(repo,'work'),own);assert(relativeOut&&!relativeOut.startsWith('..')&&!path.isAbsolute(relativeOut),'Output must be a fresh folder under repository work/');await fs.mkdir(own,{recursive:true});await assert.rejects(()=>fs.access(path.join(own,'action-native-checks.json')),{code:'ENOENT'});
const ts=(await import(pathToFileURL(path.join(repo,'frontend/node_modules/typescript/lib/typescript.js')))).default;
const requireFrontend=createRequire(path.join(repo,'frontend/package.json')),seen=new Map(),pins={};
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');pins['frontend/tools/check-original-cart-action-v3.mjs']=sha(await fs.readFile(fileURLToPath(import.meta.url)));
const checker_provenance={"derived_from":"work/v3/full-tz-closeout-20261109/original-cart/check-action.mjs","derived_source_sha256":"87cd78926afda986dea2ab1705a4b8df186d084bc9a0bbdc0c0b8edc68d30e0a","native_oracle_source_sha256":"0c29f18a3180776fef95b2dfb2f3cb01bcd07b30e495547440bbc3a3e5b11193","native_oracle_import_adaptation_sha256":"9654a66adb2c0b5ebac95dc7fa4d8d297e94cb6bbb588d419d9b31e4fd7b827a","original151_report_preserved":true,"portable_move_verification":"syntax only; no native matrix rerun"};
async function compile(input){
 if(seen.has(input))return seen.get(input);
 const output=path.join(own,'runtime',path.relative(repo,input)+'.mjs');seen.set(input,output);await fs.mkdir(path.dirname(output),{recursive:true});
 const bytes=await fs.readFile(input);pins[path.relative(repo,input).replaceAll('\\','/')]=sha(bytes);
 if(input.endsWith('.json')){await fs.writeFile(output,'export default '+bytes+';\n');return output;}
 const result=ts.transpileModule(bytes.toString(),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext},reportDiagnostics:true});assert(!result.diagnostics?.length);
 let code=result.outputText;for(const hit of [...code.matchAll(/\b(from\s*|import\s*)['"]([^'"]+)['"]/g)]){
  const name=hit[2];let target;if(name.startsWith('.')){const base=path.resolve(path.dirname(input),name);for(const p of [base,base+'.ts',base+'.json',path.join(base,'index.ts')]){try{if((await fs.stat(p)).isFile()){target=await compile(p);break;}}catch(e){if(e.code!=='ENOENT')throw e;}}assert(target,name);}
  else if(name.startsWith('node:'))continue;else target=name==='three'?path.join(repo,'frontend/node_modules/three/build/three.module.js'):requireFrontend.resolve(name);
  code=code.replace(hit[0],hit[1]+JSON.stringify(pathToFileURL(target).href));
 }await fs.writeFile(output,code);return output;
}
const T=await import(pathToFileURL(path.join(repo,'frontend/node_modules/three/build/three.module.js'))),{GLTFLoader}=await import(pathToFileURL(path.join(repo,'frontend/node_modules/three/examples/jsm/loaders/GLTFLoader.js'))),loader=new GLTFLoader();
const mod=async name=>import(pathToFileURL(await compile(path.join(repo,'frontend/src/adaptive-v3/'+name+'.ts'))));
const {createWorkerInstance}=await mod('workerRoles'),{solveWarehouseManualPadPose}=await mod('warehouseScenarioManualTransfer'),{createWarehouseForearmPronationPose}=await mod('warehouseForearmPronationPose');
const modelPath='frontend/public/models/v3/worker-base.glb',bytes=await fs.readFile(path.join(repo,modelPath));pins[modelPath]=sha(bytes);const template=(await loader.parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'')).scene,actor=createWorkerInstance(template,'P01','picker'),root=actor.root;
const pronation=createWarehouseForearmPronationPose(root,template.getObjectByName('worker_base_root'),sha(bytes));


// Native topology/SAT functions embedded unchanged; no ignored work dependency.
/** Numeric native-solid oracle. Read-only source geometry; no pose search or admission waiver. */
const topologyTolerance=1e-9,convexTolerance=5e-8;
const key=v=>v.toArray().join(','),v3=v=>new T.Vector3(...v);
function extractComponents(mesh){
 const p=mesh.geometry.attributes.position,ix=mesh.geometry.index,count=(ix?.count??p.count)/3;
 const triangles=Array.from({length:count},(_,id)=>({id,v:[0,1,2].map(j=>new T.Vector3().fromBufferAttribute(p,ix?ix.getX(3*id+j):3*id+j))}));
 const edges=new Map(),parent=triangles.map((_,i)=>i),find=i=>parent[i]===i?i:(parent[i]=find(parent[i]));
 for(const t of triangles)for(let j=0;j<3;j++){const a=key(t.v[j]),b=key(t.v[(j+1)%3]),k=[a,b].sort().join('|'),list=edges.get(k)??[];list.push({triangle:t.id,direction:a<b?1:-1});edges.set(k,list);}
 for(const list of edges.values())if(list.length===2)parent[find(list[0].triangle)]=find(list[1].triangle);
 const groups=new Map();for(const t of triangles){const i=find(t.id),g=groups.get(i)??[];g.push(t);groups.set(i,g);}
 return [...groups.values()].sort((a,b)=>a[0].id-b[0].id).map((tris,component)=>{
  const vertices=[...new Map(tris.flatMap(t=>t.v).map(v=>[key(v),v])).values()],localEdges=new Map();
  for(const t of tris)for(let j=0;j<3;j++){const a=key(t.v[j]),b=key(t.v[(j+1)%3]),k=[a,b].sort().join('|'),list=localEdges.get(k)??[];list.push({triangle:t.id,direction:a<b?1:-1});localEdges.set(k,list);}
  const badEdges=[...localEdges].filter(([,r])=>r.length!==2||r[0].direction+r[1].direction!==0);
  let volume=0,minArea=Infinity;const planes=[];
  for(const t of tris){const n=t.v[1].clone().sub(t.v[0]).cross(t.v[2].clone().sub(t.v[0])),twiceArea=n.length();minArea=Math.min(minArea,twiceArea/2);volume+=t.v[0].dot(t.v[1].clone().cross(t.v[2]))/6;n.divideScalar(twiceArea);planes.push({normal:n,offset:n.dot(t.v[0]),triangle:t.id});}
  const convexViolation=Math.max(...planes.flatMap(f=>vertices.map(v=>f.normal.dot(v)-f.offset)));
  return {id:mesh.name+'#'+component,mesh:mesh.name,bone:mesh.parent.name,node:mesh,source_parts:JSON.parse(mesh.userData.source_parts_json??'[]'),triangle_ids:tris.map(t=>t.id),triangles:tris,vertices,planes,edge_triangle_ids:[...localEdges.values()].map(list=>list.map(r=>r.triangle)),edges:[...localEdges.keys()].map(k=>{const[a,b]=k.split('|');return v3(b.split(',').map(Number)).sub(v3(a.split(',').map(Number)));}),topology:{triangle_count:tris.length,vertex_count:vertices.length,edge_count:localEdges.size,bad_edges:badEdges.length,signed_volume_m3:volume,minimum_triangle_area_m2:minArea,maximum_convex_halfspace_violation_m:convexViolation,closed_oriented:badEdges.length===0&&volume>0&&minArea>0,convex:convexViolation<=convexTolerance}};
 });
}
function worldComponent(c){
 const m=c.node.matrixWorld,nm=new T.Matrix3().getNormalMatrix(m),vertices=c.vertices.map(v=>v.clone().applyMatrix4(m));
 return {...c,vertices,planes:c.planes.map(f=>{const normal=f.normal.clone().applyMatrix3(nm).normalize(),local=f.normal.clone().multiplyScalar(f.offset).applyMatrix4(m);return {normal,offset:normal.dot(local),triangle:f.triangle};}),edges:c.edges.map(e=>e.clone().transformDirection(m)),box:new T.Box3().setFromPoints(vertices)};
}
const compact=v=>v.toArray();
/** Positive signed_gap_m separates; negative is minimum SAT translation overlap, NOT point depth. */
function convexPair(a,b,{includeIntersection=false}={}){
 assert(a.topology.closed_oriented&&b.topology.closed_oriented,'Open/inconsistent surface is not a solid');assert(a.topology.convex&&b.topology.convex,'SAT oracle requires validated convex native components');
 let best={gap:-Infinity},axisCount=0;
 // Evaluate ALL native face normals and ALL native triangle-edge cross-products.
 // Deliberately no angular axis merging: tiny native float deviations remain represented.
 const axis=(nx,ny,nz,kind,i,j)=>{const length=Math.hypot(nx,ny,nz);if(length<1e-14)return;nx/=length;ny/=length;nz/=length;axisCount++;
  let amin=Infinity,amax=-Infinity,bmin=Infinity,bmax=-Infinity;for(const v of a.vertices){const x=nx*v.x+ny*v.y+nz*v.z;if(x<amin)amin=x;if(x>amax)amax=x;}for(const v of b.vertices){const x=nx*v.x+ny*v.y+nz*v.z;if(x<bmin)bmin=x;if(x>bmax)bmax=x;}const plus=bmin-amax,minus=amin-bmax,gap=Math.max(plus,minus);if(gap>best.gap){const sign=plus>=minus?1:-1;best={gap,axis:new T.Vector3(nx*sign,ny*sign,nz*sign),origin:kind==='edge-cross'?{kind,components:[a.id,b.id],native_edge_indices:[i,j],native_edge_triangle_ids:[a.edge_triangle_ids?.[i],b.edge_triangle_ids?.[j]],edge_directions:[compact(a.edges[i]),compact(b.edges[j])]}:{kind:'face',side:kind,component:kind==='A'?a.id:b.id,triangle:(kind==='A'?a:b).planes[i].triangle}};}};
 for(let i=0;i<a.planes.length;i++){const n=a.planes[i].normal;axis(n.x,n.y,n.z,'A',i,0);}for(let i=0;i<b.planes.length;i++){const n=b.planes[i].normal;axis(n.x,n.y,n.z,'B',i,0);}for(let i=0;i<a.edges.length;i++)for(let j=0;j<b.edges.length;j++){const x=a.edges[i],y=b.edges[j];axis(x.y*y.z-x.z*y.y,x.z*y.x-x.x*y.z,x.x*y.y-x.y*y.x,'edge-cross',i,j);}
 const activeA=a.planes.map(f=>({side:'A',component:a.id,triangle:f.triangle,normal:compact(f.normal),offset_m:f.offset})).filter(f=>Math.abs(Math.abs(v3(f.normal).dot(best.axis))-1)<1e-8);
 const activeB=b.planes.map(f=>({side:'B',component:b.id,triangle:f.triangle,normal:compact(f.normal),offset_m:f.offset})).filter(f=>Math.abs(Math.abs(v3(f.normal).dot(best.axis))-1)<1e-8);
 const result={components:[a.id,b.id],bones:[a.bone,b.bone],signed_gap_m:best.gap,separated:best.gap>topologyTolerance,shared_volume:best.gap< -topologyTolerance,axis_A_to_B:compact(best.axis),move_A_for_separation_m:compact(best.axis.clone().multiplyScalar(-Math.max(0,-best.gap))),minimum_translation_to_touch_m:Math.max(0,-best.gap),axis_origin:best.origin,active_parallel_faces:[...activeA,...activeB],axis_count:axisCount};
 if(includeIntersection&&result.shared_volume)result.intersection=intersectionPolytope(a,b);
 return result;
}
/** Exact convex intersection vertices: own native vertices + every native edge clipped to other halfspaces. */
function intersectionPolytope(a,b){
 const pts=[],put=(p,origin)=>{if(!pts.some(x=>x.p.distanceToSquared(p)<1e-20))pts.push({p,origin});},inside=(p,c)=>c.planes.every(f=>f.normal.dot(p)<=f.offset+1e-10);
 for(const [from,to]of[[a,b],[b,a]]){
  for(let i=0;i<from.vertices.length;i++)if(inside(from.vertices[i],to))put(from.vertices[i].clone(),{component:from.id,vertex_index:i});
  const seen=new Set();for(const t of from.triangles)for(let j=0;j<3;j++){
   const localA=t.v[j],localB=t.v[(j+1)%3],k=[key(localA),key(localB)].sort().join('|');if(seen.has(k))continue;seen.add(k);
   const s=localA.clone().applyMatrix4(from.node.matrixWorld),e=localB.clone().applyMatrix4(from.node.matrixWorld),d=e.clone().sub(s);let lo=0,hi=1;
   for(const f of to.planes){const denominator=f.normal.dot(d),rhs=f.offset-f.normal.dot(s);if(Math.abs(denominator)<1e-14){if(rhs< -1e-10){lo=1;hi=0;break;}continue;}const u=rhs/denominator;if(denominator>0)hi=Math.min(hi,u);else lo=Math.max(lo,u);if(lo>hi+1e-12)break;}
   if(lo<=hi+1e-12&&lo<=1&&hi>=0){if(lo>=0&&lo<=1)put(s.clone().addScaledVector(d,lo),{component:from.id,edge_triangle:t.id,edge:j,u:lo});if(hi>=0&&hi<=1)put(s.clone().addScaledVector(d,hi),{component:from.id,edge_triangle:t.id,edge:j,u:hi});}
  }
 }
 const centre=new T.Vector3();for(const x of pts)centre.add(x.p);if(pts.length)centre.divideScalar(pts.length);
 const margin=(p,c)=>Math.min(...c.planes.map(f=>f.offset-f.normal.dot(p)));
 return {vertex_count:pts.length,vertices:pts.map(x=>({point_m:compact(x.p),origin:x.origin})),vertex_mean_point_m:compact(centre),vertex_mean_halfspace_margins_m:[margin(centre,a),margin(centre,b)],scope:'Contains all convex-intersection extreme vertices plus native triangulation-diagonal boundary points, within numeric tolerances; point mean is one interior sample, not a volume centroid or maximum penetration.'};
}
function makeOracle(root){const components=[];root.traverse(n=>{if(n.isMesh&&!n.userData.roleBadge)components.push(...extractComponents(n));});const map=new Map(components.map(c=>[c.id,c]));return {components,byId:map,world:id=>worldComponent(map.get(id)),pair:(aid,bid,options)=>convexPair(worldComponent(map.get(aid)),worldComponent(map.get(bid)),options),evaluatePairs:(pairs,options)=>{const cache=new Map();for(const id of new Set(pairs.flat()))cache.set(id,worldComponent(map.get(id)));return pairs.map(([a,b])=>convexPair(cache.get(a),cache.get(b),options));}};}

const cartPath='frontend/public/models/v3/picking-cart-tote-fixture.glb',cb=await fs.readFile(path.join(repo,cartPath));pins[cartPath]=sha(cb);const cart=(await loader.parseAsync(cb.buffer.slice(cb.byteOffset,cb.byteOffset+cb.byteLength),'')).scene;cart.updateMatrixWorld(true);const cartParts=[],bodyParts=[];cart.traverse(n=>{if(n.isMesh)cartParts.push(...extractComponents(n));});root.traverse(n=>{if(n.isMesh&&!n.userData.roleBadge)bodyParts.push(...extractComponents(n));});
const resourceBytes=[],materialBytes=[];for(const owner of [root,cart])owner.traverse(n=>{if(!n.isMesh)return;for(const a of [...Object.values(n.geometry.attributes),...(n.geometry.index?[n.geometry.index]:[])])resourceBytes.push({a,bytes:Buffer.from(a.array.buffer,a.array.byteOffset,a.array.byteLength).toString('base64')});for(const m of Array.isArray(n.material)?n.material:[n.material])materialBytes.push({m,json:JSON.stringify(m.toJSON())});});
const scene=new T.Scene();root.position.z=-1.23;scene.add(root,cart);const {createWarehouseOriginalCartAction,isWarehouseOriginalCartAction}=await mod('warehouseOriginalCartAction'),baseline=[];root.traverse(n=>baseline.push({n,p:n.position.clone(),q:n.quaternion.clone(),s:n.scale.clone()}));const baseCart=cart.position.clone(),start=performance.now(),action=createWarehouseOriginalCartAction(actor,cart,template.getObjectByName('worker_base_root'),{worker_sha256:pins[modelPath],cart_sha256:pins[cartPath]}),prepare_s=(performance.now()-start)/1000,frames=[],hits=[],invalid=[],jointErrors=[],criticalBody=[];let maxHeld=0,minWheelGap=Infinity,maxWheelGap=-Infinity;const boxGap=(a,b)=>Math.max(a.min.x-b.max.x,b.min.x-a.max.x,a.min.y-b.max.y,b.min.y-a.max.y,a.min.z-b.max.z,b.min.z-a.max.z);
assert(isWarehouseOriginalCartAction(action));assert(!isWarehouseOriginalCartAction({...action}));const immutable=JSON.stringify(root.toJSON());action.sample(action.duration_s*.5);assert.equal(JSON.stringify(root.toJSON()),immutable);
const times=[...new Set([...Array.from({length:129},(_,i)=>action.duration_s*i/128),...Object.values(action.phases).flatMap(t=>[-.0001,0,.0001].map(d=>Math.max(0,Math.min(action.duration_s,t+d))))])].sort((a,b)=>a-b);for(const t of times){const s=action.apply(t);if(s.held){maxHeld=Math.max(maxHeld,...s.hands.map(h=>h.gap_m));assert(Math.max(...s.hands.map(h=>h.gap_m))<=.001);}for(const r of baseline){if(r.n!==root)assert(r.n.position.equals(r.p),r.n.name+' position');assert(r.n.scale.equals(r.s),r.n.name+' scale');if(r.n.name.startsWith('joint__')&&r.n.userData.limits_xyz_json){const a=[r.n.rotation.x,r.n.rotation.y,r.n.rotation.z],lim=JSON.parse(r.n.userData.limits_xyz_json);if(a.some((v,k)=>v<lim[k][0]-1e-10||v>lim[k][1]+1e-10))jointErrors.push({t,node:r.n.name,a,lim});}}const A=bodyParts.map(worldComponent),B=cartParts.map(worldComponent);for(const a of A)for(const b of B){if(boxGap(a.box,b.box)>.001)continue;if(!a.topology.convex||!b.topology.convex){invalid.push({t,body:a.id,cart:b.id});continue;}const r=convexPair(a,b);if(r.signed_gap_m< -2e-6)hits.push({t,phase:s.phase_id,body:a.id,cart:b.id,gap_m:r.signed_gap_m,body_material:a.node.material.name});}const arm=A.filter(a=>/joint__(upper_arm|forearm|palm_roll|hand)_[LR]/.test(a.bone)),core=A.filter(a=>!/joint__(upper_arm|forearm|palm_roll|hand)_[LR]/.test(a.bone));for(const a of arm)for(const b of core){if(/^joint__upper_arm_[LR]$/.test(a.bone)&&b.bone==='joint__torso'||boxGap(a.box,b.box)>.001)continue;if(!a.topology.convex||!b.topology.convex){criticalBody.push({t,body:a.id,other:b.id,unresolved:true});continue;}const q=convexPair(a,b);if(q.signed_gap_m< -2e-6)criticalBody.push({t,parts:q.components,gap_m:q.signed_gap_m});}const tyres=B.filter(b=>b.node.material.name==='V3_CART_tyre'),wheelGap=Math.min(...tyres.flatMap(b=>b.vertices.map(v=>v.y)));minWheelGap=Math.min(minWheelGap,wheelGap);maxWheelGap=Math.max(maxWheelGap,wheelGap);frames.push({at_s:t,phase:s.phase_id,held:s.held,max_gap_m:Math.max(...s.hands.map(h=>h.gap_m)),actor:s.actual_actor_position,cart:s.actual_cart_position});}
const beforeBad=JSON.stringify(action.snapshot());assert.throws(()=>action.apply(NaN),/FINITE_ORIGINAL_CART_TIME_REQUIRED/);assert.equal(JSON.stringify(action.snapshot()),beforeBad);const deterministic=action.apply(action.phases.grip_at_s+pushDummy());function pushDummy(){return .5;}action.apply(action.duration_s);assert.equal(JSON.stringify(action.apply(action.phases.grip_at_s+.5)),JSON.stringify(deterministic));action.reset();for(const r of baseline){assert(r.n.position.equals(r.p));assert(r.n.quaternion.equals(r.q));assert(r.n.scale.equals(r.s));}assert(cart.position.equals(baseCart));action.dispose();assert(!isWarehouseOriginalCartAction(action));for(const r of resourceBytes)assert.equal(Buffer.from(r.a.array.buffer,r.a.array.byteOffset,r.a.array.byteLength).toString('base64'),r.bytes);for(const r of materialBytes)assert.equal(JSON.stringify(r.m.toJSON()),r.json);for(const[p,h]of Object.entries(pins))assert.equal(sha(await fs.readFile(path.join(repo,p))),h);const report={passed:hits.length===0&&invalid.length===0&&jointErrors.length===0&&criticalBody.length===0,frames:frames.length,prepare_s,duration_s:action.duration_s,phases:action.phases,max_held_pad_error_m:maxHeld,hits,unresolved_cart:invalid,joint_errors:jointErrors,critical_body:criticalBody,native_tyre_floor_gap_m:{minimum:minWheelGap,maximum:maxWheelGap},immutable_buffers:resourceBytes.length,immutable_material_references:materialBytes.length,poses:frames,source_hashes:pins,checker_provenance,scope:'First original542/C01 grip-push-release-withdraw native action probe. No Scene integration/job/stock transfer or wholetraffic certificate. Original shoulder joins retained, no body/cart penetration accepted.'};await fs.writeFile(path.join(own,'action-native-checks.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({...report,source_hashes:undefined,poses:undefined}));
