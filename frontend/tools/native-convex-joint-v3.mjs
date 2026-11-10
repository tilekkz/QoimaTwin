/** Independent native-solid support separation. No hierarchy/adjacency exceptions. */
import assert from 'node:assert/strict';
import * as T from 'three';

const vertexKey=v=>v.toArray().map(x=>x.toFixed(9)).join(',');
const unique=points=>[...new Map(points.map(p=>[vertexKey(p),p])).values()];
const V=()=>new T.Vector3();

/** Input triangles must describe one actual closed, outward-oriented component. */
export function describeNativeJointSolid(triangles,{tolerance=1e-7,requireConvex=false}={}){
 assert(triangles.length>=4,'Closed solid triangles required');
 const vertices=unique(triangles.flatMap(t=>[t.a,t.b,t.c]));
 assert(vertices.every(p=>p.toArray().every(Number.isFinite)),'Finite native vertices required');
 const origin=vertices.reduce((a,p)=>a.add(p),V()).divideScalar(vertices.length);
 const edges=new Map(),planes=[],directions=[];let signedVolume=0;
 for(const t of triangles){
  assert(t.getArea()>1e-13,'Noncollapsed native triangles required');
  const points=[t.a,t.b,t.c],normal=t.getNormal(V()),constant=normal.dot(t.a);
  if(!planes.some(p=>p.normal.distanceTo(normal)<1e-7&&Math.abs(p.constant-constant)<tolerance))planes.push({normal,constant});
  signedVolume+=t.a.clone().sub(origin).dot(t.b.clone().sub(origin).cross(t.c.clone().sub(origin)))/6;
  for(let i=0;i<3;i++){
   const a=vertexKey(points[i]),b=vertexKey(points[(i+1)%3]),key=[a,b].sort().join('|'),edge=edges.get(key)??{count:0,orientation:0};
   assert(a!==b,'Distinct native triangle vertices required');edge.count++;edge.orientation+=a<b?1:-1;edges.set(key,edge);
   const d=points[(i+1)%3].clone().sub(points[i]).normalize();
   if(!directions.some(x=>Math.abs(x.dot(d))>1-1e-10))directions.push(d);
  }
 }
 assert([...edges.values()].every(e=>e.count===2&&e.orientation===0),'Closed consistently oriented native component required');
 const maximumConvexityViolation=Math.max(...planes.flatMap(p=>vertices.map(v=>p.normal.dot(v)-p.constant)));
 if(requireConvex)assert(maximumConvexityViolation<=tolerance,'Actual component must be convex for complete SAT classification');
 assert(signedVolume>1e-12,'Positive native closed-solid volume required');
 return {vertices,planes,directions,signed_volume_m3:signedVolume,convex:maximumConvexityViolation<=tolerance,maximum_convexity_violation_m:maximumConvexityViolation,triangle_count:triangles.length};
}

export function describeConvexNativeSolid(triangles,options={}){return describeNativeJointSolid(triangles,{...options,requireConvex:true});}

/** All face normals plus all edge cross products: the complete convex SAT axes. */
export function separateNativeJointSolids(a,b,{tolerance=2e-6}={}){
 const axes=[];const add=n=>{if(n.lengthSq()<1e-18)return;const axis=n.clone().normalize();if(!axes.some(x=>Math.abs(x.dot(axis))>1-1e-10))axes.push(axis);};
 for(const p of [...a.planes,...b.planes])add(p.normal);
 for(const u of a.directions)for(const v of b.directions)add(u.clone().cross(v));
 let gap=-Infinity,axis=null,intervals=null;
 for(const n of axes){
  const av=a.vertices.map(p=>n.dot(p)),bv=b.vertices.map(p=>n.dot(p));
  const ai=[Math.min(...av),Math.max(...av)],bi=[Math.min(...bv),Math.max(...bv)];
  const current=Math.max(bi[0]-ai[1],ai[0]-bi[1]);
  if(current>gap){gap=current;axis=n.toArray();intervals=[ai,bi];}
 }
 return {separated_within_native_tolerance:gap>=-tolerance,strictly_separated:gap>0,
  maximum_separating_projection_gap_m:gap,axis_world:axis,projection_intervals_m:intervals,
  axes_tested:axes.length,tolerance_m:tolerance,both_components_convex:a.convex&&b.convex,
  interpretation:'A positive separating support gap bounds every actual native triangle even for concave components; no convex-hull replacement is made. A negative result is inconclusive for concave components and is never penetration depth or Euclidean clearance. Native tolerance applies only at a coincident fitted seam; no bone-name exception.'};
}

export function separateConvexNativeSolids(a,b,options={}){assert(a.convex&&b.convex,'Both actual native components must be convex for complete SAT classification');return separateNativeJointSolids(a,b,options);}
