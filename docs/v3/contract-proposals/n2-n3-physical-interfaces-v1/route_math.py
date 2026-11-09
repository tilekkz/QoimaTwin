"""Analytic pose/profile checks; no builder imports, renderer, engine or scheduler."""
import math

def wrap(a):return (a+math.pi)%(2*math.pi)-math.pi
def transform(p,yaw,v):
 c,s=math.cos(yaw),math.sin(yaw)
 return [p[0]+c*v[0]+s*v[2],p[1]+v[1],p[2]-s*v[0]+c*v[2]]
def evaluate(g,u):
 t=g['start_yaw_rad']+(g['end_yaw_rad']-g['start_yaw_rad'])*u
 if g['kind']=='line':
  a,b=g['front_axle_start_xz_m'],g['front_axle_end_xz_m'];f=[a[i]+u*(b[i]-a[i]) for i in range(2)]
 elif g['kind']=='rear_steer_arc':
  x,z=g['icr_world_xz_m'];r=g['icr_vehicle_local_x_m'];f=[x-r*math.cos(t),z+r*math.sin(t)]
 else:raise ValueError('UNSUPPORTED_GEOMETRY')
 return [f[0]-.4*math.sin(t),0,f[1]-.4*math.cos(t)],t
def line(a,b,yaw):return {'kind':'line','front_axle_start_xz_m':[a[0]+.4*math.sin(yaw),a[2]+.4*math.cos(yaw)],'front_axle_end_xz_m':[b[0]+.4*math.sin(yaw),b[2]+.4*math.cos(yaw)],'start_yaw_rad':yaw,'end_yaw_rad':yaw}
def arc(icr,c,start,end):return {'kind':'rear_steer_arc','icr_world_xz_m':icr,'icr_vehicle_local_x_m':c,'front_axle_radius_m':abs(c),'start_yaw_rad':start,'end_yaw_rad':end}
def reverse(g):
 d=dict(g);d['start_yaw_rad'],d['end_yaw_rad']=g['end_yaw_rad'],g['start_yaw_rad']
 if g['kind']=='line':d['front_axle_start_xz_m'],d['front_axle_end_xz_m']=g['front_axle_end_xz_m'],g['front_axle_start_xz_m']
 return d
def root_length(g):
 if g['kind']=='line':return math.dist(g['front_axle_start_xz_m'],g['front_axle_end_xz_m'])
 return math.hypot(g['icr_vehicle_local_x_m'],.4)*abs(g['end_yaw_rad']-g['start_yaw_rad'])
def pose_error(a,b):return max(math.dist(a[0],b[0]),abs(wrap(a[1]-b[1])))
def _trig_range(a,b,lo,hi):
 low,high=sorted([lo,hi]);pts=[low,high];phase=math.atan2(b,a)
 for k in range(math.floor((low-phase)/math.pi)-1,math.ceil((high-phase)/math.pi)+2):
  t=phase+k*math.pi
  if low<=t<=high:pts.append(t)
 vals=[a*math.cos(t)+b*math.sin(t) for t in pts]
 return min(vals),max(vals)
def padded(box,padding=.25):return {'min':[box['min'][0]-padding,box['min'][1],box['min'][2]-padding],'max':[box['max'][0]+padding,box['max'][1]+padding,box['max'][2]+padding]}
def sweep_bounds(g,box,u0=0,u1=1):
 mins=[math.inf,box['min'][1],math.inf];maxs=[-math.inf,box['max'][1],-math.inf]
 if g['kind']=='line':
  for u in [u0,u1]:
   p,t=evaluate(g,u)
   for x in [box['min'][0],box['max'][0]]:
    for z in [box['min'][2],box['max'][2]]:
     q=transform(p,t,[x,0,z]);mins[0]=min(mins[0],q[0]);maxs[0]=max(maxs[0],q[0]);mins[2]=min(mins[2],q[2]);maxs[2]=max(maxs[2],q[2])
 else:
  lo=g['start_yaw_rad']+(g['end_yaw_rad']-g['start_yaw_rad'])*u0;hi=g['start_yaw_rad']+(g['end_yaw_rad']-g['start_yaw_rad'])*u1;c=g['icr_vehicle_local_x_m'];ox,oz=g['icr_world_xz_m']
  for x in [box['min'][0],box['max'][0]]:
   for z in [box['min'][2],box['max'][2]]:
    a,b=_trig_range(x-c,z-.4,lo,hi);mins[0]=min(mins[0],ox+a);maxs[0]=max(maxs[0],ox+b)
    a,b=_trig_range(z-.4,-(x-c),lo,hi);mins[2]=min(mins[2],oz+a);maxs[2]=max(maxs[2],oz+b)
 return {'min':mins,'max':maxs}
def disjoint(a,b):return any(a['max'][i]<=b['min'][i]+1e-10 or b['max'][i]<=a['min'][i]+1e-10 for i in range(3))
def rect_overlap(g,box,obstacle,u):
 p,t=evaluate(g,u);c,s=math.cos(t),math.sin(t);verts=[transform(p,t,[x,0,z]) for x in [box['min'][0],box['max'][0]] for z in [box['min'][2],box['max'][2]]];other=[[x,0,z] for x in [obstacle['min'][0],obstacle['max'][0]] for z in [obstacle['min'][2],obstacle['max'][2]]]
 if box['max'][1]<=obstacle['min'][1] or box['min'][1]>=obstacle['max'][1]:return False
 for ax,az in [(1,0),(0,1),(c,-s),(s,c)]:
  a=[v[0]*ax+v[2]*az for v in verts];b=[v[0]*ax+v[2]*az for v in other]
  if min(max(a),max(b))-max(min(a),min(b))<=1e-10:return False
 return True
def prove_segment(g,components,obstacles,max_depth=18):
 tested=0;unresolved=[]
 for ci,original in enumerate(components):
  box=padded(original)
  for obs in obstacles:
   stack=[(0.,1.,0)]
   while stack:
    lo,hi,depth=stack.pop();tested+=1;bound=sweep_bounds(g,box,lo,hi)
    if disjoint(bound,obs['bounds']):continue
    mid=(lo+hi)/2
    if rect_overlap(g,box,obs['bounds'],mid):return {'passed':False,'reason':'PADDED_PROFILE_OBSTACLE_INTERSECTION','component_index':ci,'obstacle':obs['id'],'u':mid,'pose':evaluate(g,mid),'interval_bounds':bound,'interval_tests':tested,'source':obs.get('source')}
    if depth>=max_depth:unresolved.append({'component_index':ci,'obstacle':obs['id'],'u_interval':[lo,hi],'bounds':bound});continue
    stack.extend([(lo,mid,depth+1),(mid,hi,depth+1)])
 if unresolved:return {'passed':False,'reason':'ANALYTIC_INTERVAL_UNRESOLVED','interval_tests':tested,'unresolved':unresolved}
 return {'passed':True,'interval_tests':tested,'proof':'Continuous analytic per-component swept AABB intervals with exact trig extrema, recursively separated from source obstacle reservation bounds. Not native triangles or traffic scheduling.'}

def floor_contained(g,components):
 bounds=[sweep_bounds(g,padded(b)) for b in components]
 return all(b['min'][0]>=-1e-9 and b['max'][0]<=144+1e-9 and b['min'][2]>=-1e-9 and b['max'][2]<=72+1e-9 for b in bounds)
