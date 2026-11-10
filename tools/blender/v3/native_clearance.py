"""Native closed-solid clearance: transverse triangles and true solid containment.

A nearest triangle normal alone cannot classify a point beside a distant edge.
Use the closed mesh's solid angle for containment; contacts retain the2um gate.
"""
import math
import numpy as np
from v3_common import runtime_xyz,xyz

def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def length(a):return math.sqrt(dot(a,a))
def faces(part):
 if '_clearance_faces' not in part:
  result=[]
  for tri in part['triangles']:
   v=[tuple(part['verts'][i]) for i in tri];n=cross(sub(v[1],v[0]),sub(v[2],v[0]));size=length(n)
   if size>1e-15:result.append((v,tuple(x/size for x in n)))
   else:result.append((v,(0,0,0)))
  part['_clearance_faces']=result
 return part['_clearance_faces']
def within(part,p,margin):return all(part['low'][i]+margin<p[i]<part['high'][i]-margin for i in range(3))
def contains(part,point,epsilon=2e-6):
 if not within(part,point,epsilon):return False
 hit,_,index,distance=part['bvh'].find_nearest(xyz(point))
 if hit is None or distance<=epsilon:return False
 return abs(solid_angle(part,point))>2*math.pi

def solid_angle(part,point):
 if '_clearance_array' not in part:part['_clearance_array']=np.asarray([v for v,_ in faces(part)],dtype=np.float64)
 vertices=part['_clearance_array']-np.asarray(point,dtype=np.float64);a,b,c=vertices[:,0],vertices[:,1],vertices[:,2]
 la,lb,lc=[np.linalg.norm(v,axis=1) for v in [a,b,c]]
 numerator=np.einsum('ij,ij->i',a,np.cross(b,c));denominator=la*lb*lc+np.einsum('ij,ij->i',a,b)*lc+np.einsum('ij,ij->i',b,c)*la+np.einsum('ij,ij->i',c,a)*lb
 return float(np.sum(2*np.arctan2(numerator,denominator)))

def plane_segment(verts,distances,axis):
 points=[]
 for i in range(3):
  j=(i+1)%3;a,b=distances[i],distances[j]
  if a==0:points.append(dot(verts[i],axis))
  if a*b<0:
   u=a/(a-b);p=tuple(x+(y-x)*u for x,y in zip(verts[i],verts[j]));points.append(dot(p,axis))
 return (min(points),max(points)) if points else None
def penetration(a,b,epsilon=2e-6):
 if any(a['high'][i]<=b['low'][i]+epsilon or a['low'][i]>=b['high'][i]-epsilon for i in range(3)):return None
 fa,fb=faces(a),faces(b)
 for ia,ib in a['bvh'].overlap(b['bvh']):
  va,na=fa[ia];vb,nb=fb[ib];da=[dot(nb,sub(v,vb[0])) for v in va];db=[dot(na,sub(v,va[0])) for v in vb]
  if min(da)<-epsilon and max(da)>epsilon and min(db)<-epsilon and max(db)>epsilon:
   axis=cross(na,nb);size=length(axis)
   if size>1e-12:
    axis=tuple(x/size for x in axis);sa,sb=plane_segment(va,da,axis),plane_segment(vb,db,axis)
    if sa and sb and min(sa[1],sb[1])-max(sa[0],sb[0])>epsilon:
     # Segment length is not penetration depth: a long tangency can cross
     # triangles by nanometres. Require a true >epsilon interior witness.
     mid=(min(sa[1],sb[1])+max(sa[0],sb[0]))/2;d1=dot(na,va[0]);d2=dot(nb,vb[0]);c1=cross(nb,axis);c2=cross(axis,na)
     point=tuple((d1*c1[i]+d2*c2[i])/size+mid*axis[i] for i in range(3));inward=tuple(-na[i]-nb[i] for i in range(3));n=length(inward)
     if n>1e-12:
      inward=tuple(x/n for x in inward);factor=-dot(inward,na)
      if factor>1e-12:
       for depth in[1.25,2,4]:
        witness=tuple(point[i]+inward[i]*epsilon*depth/factor for i in range(3))
        if contains(a,witness,epsilon) and contains(b,witness,epsilon):return dict(kind='transverse_surface_shared_interior',a=a['name'],b=b['name'],triangles=[ia,ib],point=witness)
  if dot(na,nb)>.999999 and max(map(abs,da))<=epsilon:
   p=tuple(sum(v[i] for v in va)/3-na[i]*epsilon*3 for i in range(3))
   if contains(a,p,epsilon) and contains(b,p,epsilon):return dict(kind='cooriented_surface_shared_interior',a=a['name'],b=b['name'],point=p)
 for source,target in[(a,b),(b,a)]:
  # BVH overlap omits some exactly coplanar pairs. Probe inward at native
  # face centres only after a near-surface witness, retaining true containment.
  for verts,normal in faces(source):
   centre=tuple(sum(v[i] for v in verts)/3 for i in range(3))
   if not within(target,centre,-epsilon):continue
   hit,_,_,distance=target['bvh'].find_nearest(xyz(centre))
   if hit is None or distance>epsilon:continue
   p=tuple(centre[i]-normal[i]*epsilon*3 for i in range(3))
   if contains(source,p,epsilon) and contains(target,p,epsilon):return dict(kind='coincident_face_shared_interior',a=source['name'],b=target['name'],point=p)
  for sample in source['samples']:
   p=runtime_xyz(sample)
   if within(target,p,epsilon) and contains(target,p,epsilon):return dict(kind='sample_inside_closed_solid',a=source['name'],b=target['name'],point=p)
 return None


def touching(a,b,epsilon=2e-6):
 if any(a['high'][i]<b['low'][i]-epsilon or a['low'][i]>b['high'][i]+epsilon for i in range(3)):return False
 if a['bvh'].overlap(b['bvh']):return True
 for source,target in[(a,b),(b,a)]:
  if any(target['bvh'].find_nearest(p)[3]<=epsilon for p in source['samples']):return True
 return bool(penetration(a,b,epsilon))

def connected_parts(parts):
 adj={p['name']:set() for p in parts};links=[]
 for i,a in enumerate(parts):
  for b in parts[i+1:]:
   if touching(a,b):adj[a['name']].add(b['name']);adj[b['name']].add(a['name']);links.append([a['name'],b['name']])
 reached={parts[0]['name']};queue=list(reached)
 while queue:
  for n in adj[queue.pop()]-reached:reached.add(n);queue.append(n)
 assert reached==set(adj),('unconnected physical parts',sorted(set(adj)-reached))
 return links
