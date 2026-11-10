import type {WarehouseBundle,XYZ,V3Bounds} from '../warehouseTypes';
import type {WarehouseLayoutPlan} from '../warehouseLayoutPlan';
import type {WarehouseLayoutAccessResult} from '../warehouseLayoutAccess';
import {createWarehouseRouter,type RoutePolicy} from '../warehouseRouting';

export type ShiftPath={points:XYZ[];cumulative:Float64Array;length:number;basis:string};
export function shiftPath(points:XYZ[],basis:string):ShiftPath{
 const cumulative=new Float64Array(points.length);for(let i=1;i<points.length;i++)cumulative[i]=cumulative[i-1]+Math.hypot(points[i][0]-points[i-1][0],points[i][2]-points[i-1][2]);
 return {points,cumulative,length:cumulative.at(-1)??0,basis};
}
export type ShiftPose={x:number;y:number;z:number;yaw:number;moving:boolean;working:boolean;waiting:boolean;loaded:boolean;phase:string;step:number};
export function sampleShiftPath(path:ShiftPath,distance:number,out:ShiftPose,smooth:boolean){
 const d=Math.max(0,Math.min(path.length,distance));let i=1;while(i<path.points.length-1&&path.cumulative[i]<d)i++;
 const a=path.points[Math.max(0,i-1)],b=path.points[Math.min(i,path.points.length-1)],span=path.cumulative[i]-path.cumulative[i-1],u=span>0?(d-path.cumulative[i-1])/span:0;
 out.x=a[0]+(b[0]-a[0])*u;out.y=0;out.z=a[2]+(b[2]-a[2])*u;out.yaw=Math.atan2(b[0]-a[0],b[2]-a[2]);
 // Rotate while decelerating into a corner, without cutting its safe graph edges.
 if(smooth&&i+1<path.points.length&&span*(1-u)<.6){const c=path.points[i+1],next=Math.atan2(c[0]-b[0],c[2]-b[2]),delta=Math.atan2(Math.sin(next-out.yaw),Math.cos(next-out.yaw));out.yaw+=delta*(1-span*(1-u)/.6)*.5;}
}

type Rect={min:[number,number];max:[number,number]};
/** Conservative, metre-grid computed aisles, used only by the labelled demo fleet
 * and gate crew. Every edge is checked against the actual A/B equipment envelopes.
 * This is geometry for visual motion, never physical handling admission. */
export function createShiftAisles(bundle:WarehouseBundle,plan:WarehouseLayoutPlan|null,radius:number){
 const floor=plan?.floor_bounds??(bundle.layout.data.envelope as {bounds:V3Bounds}).bounds;
 const conveyor=bundle.layout.data.conveyor as {physical_modules:{floor_bounds_xz:Rect}[];packing_stations:{table_origin:XYZ;table_dimensions_m:XYZ}[]};
 const rects:Rect[]=(plan?.modules??bundle.layout.modules).map(m=>({min:[m.outer_bounds_world.min[0],m.outer_bounds_world.min[2]],max:[m.outer_bounds_world.max[0],m.outer_bounds_world.max[2]]}));
 for(const c of conveyor.physical_modules)rects.push(c.floor_bounds_xz);
 for(const p of conveyor.packing_stations)rects.push({min:[p.table_origin[0]-p.table_dimensions_m[0]/2,p.table_origin[2]-p.table_dimensions_m[2]/2],max:[p.table_origin[0]+p.table_dimensions_m[0]/2,p.table_origin[2]+p.table_dimensions_m[2]/2]});
 const minX=floor.min[0]+radius+.02,minZ=floor.min[2]+radius+.02,maxX=floor.max[0]-radius-.02,maxZ=floor.max[2]-radius-.02;
 const nx=Math.floor(maxX-minX)+1,nz=Math.floor(maxZ-minZ)+1,size=nx*nz,free=new Uint8Array(size),previous=new Int32Array(size),queue=new Int32Array(size);
 const clear=(x:number,z:number)=>x>=minX&&x<=maxX&&z>=minZ&&z<=maxZ&&rects.every(b=>x<b.min[0]-radius-.02||x>b.max[0]+radius+.02||z<b.min[1]-radius-.02||z>b.max[1]+radius+.02);
 for(let z=0;z<nz;z++)for(let x=0;x<nx;x++)free[z*nx+x]=+clear(minX+x,minZ+z);
 function nearest(p:XYZ){let best=-1,dist=Infinity;for(let i=0;i<size;i++)if(free[i]){const d=(minX+i%nx-p[0])**2+(minZ+Math.floor(i/nx)-p[2])**2;if(d<dist){dist=d;best=i;}}if(best<0)throw Error('SHIFT_AISLES_EMPTY');return best;}
 function route(a:XYZ,b:XYZ):ShiftPath{
  const from=nearest(a),to=nearest(b);previous.fill(-1);let head=0,tail=1;queue[0]=from;previous[from]=from;
  while(head<tail&&previous[to]===-1){const i=queue[head++],x=i%nx,z=Math.floor(i/nx);for(const n of [x?i-1:-1,x+1<nx?i+1:-1,z?i-nx:-1,z+1<nz?i+nx:-1])if(n>=0&&free[n]&&previous[n]===-1){previous[n]=i;queue[tail++]=n;}}
  if(previous[to]===-1)throw Error('SHIFT_AISLE_ROUTE_DISCONNECTED');
  const ids=[to];while(ids.at(-1)!==from)ids.push(previous[ids.at(-1)!]);ids.reverse();const points:XYZ[]=[];
  for(const i of ids){const p:XYZ=[minX+i%nx,0,minZ+Math.floor(i/nx)];if(points.length>1){const v=points[points.length-2],w=points.at(-1)!;if(v[0]===w[0]&&w[0]===p[0]||v[2]===w[2]&&w[2]===p[2]){points[points.length-1]=p;continue;}}points.push(p);}
  if(points.length===1)points.push([...points[0]]);return shiftPath(points,plan?'computed_B_clear_aisles':'computed_A_clear_aisles');
 }
 return {route,clear,radius};
}

export function createShiftPickRoutes(bundle:WarehouseBundle,policy:RoutePolicy,plan:WarehouseLayoutPlan|null,access:WarehouseLayoutAccessResult|null){
 const router=createWarehouseRouter(bundle,policy),arcs=new Map(bundle.layout.walk.arcs.map(a=>[a.arc_id,a]));
 const cache=new Map<string,ShiftPath>();
 function route(module_id:string,pack_id:string,variant:'A'|'B'){
  const key=variant+module_id+pack_id,existing=cache.get(key);if(existing)return existing;
  const mi=bundle.layout.modules.findIndex(m=>m.module_id===module_id),slot=bundle.layout.slots.find(s=>s.module_index===mi&&!s.reserve_only&&!s.retrieval_blocked)!;
  if(!slot)throw Error('SHIFT_PICK_SLOT_MISSING');
  const target=bundle.layout.walk.nodes[slot.cart_stop_node_index].node_id,from='v3:cart-stop:'+pack_id;let path:ShiftPath;
  if(variant==='B'&&plan&&access){
   const endpoints=access.manual.manual_cart.endpoints,a=endpoints.find(e=>e.source_node_id===from),b=endpoints.find(e=>e.module_id===module_id&&e.source_node_id===target)??endpoints.find(e=>e.module_id===module_id);
   if(!a||!b)throw Error('SHIFT_B_ENDPOINT_MISSING');const result=access.route({mode:'manual_cart',from_node_id:a.node_id,to_node_id:b.node_id,layout_version:plan.layout_version,plan_sha256:plan.plan_sha256});
   if(!result.ok)throw Error('SHIFT_B_PICK_ROUTE_REFUSED');path=shiftPath(result.points_world,'validated_B_manual_cart_geometry');
  }else{
   const result=router.route({source_kind:'visual_fixture',engine_operation:false,mode:'manual_cart',actor_id:'P01',vehicle_id:null,cargo_archetype_id:null,from_node_id:from,to_node_id:target,service_port_id:null,closed_arc_ids:[]});
   if(!result.ok)throw Error('SHIFT_A_PICK_ROUTE_REFUSED:'+result.reason);const points:XYZ[]=[bundle.layout.walk.nodes.find(n=>n.node_id===from)!.world_pos];
   for(const id of result.arc_ids)points.push(bundle.layout.walk.nodes[arcs.get(id)!.to_node_index].world_pos);path=shiftPath(points,'canonical_A_manual_cart_graph');
  }
  cache.set(key,path);return path;
 }
 return {route};
}
