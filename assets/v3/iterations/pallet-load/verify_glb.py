"""Independent actual BIN inspection. Run with bundled Python/NumPy, no bpy."""
from pathlib import Path
import hashlib
import json
import math
import struct

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
PATH = ROOT / "frontend/public/models/v3/pallet-load.glb"
PLAN = json.loads((ROOT / "assets/v3/specs/pallet-load.dimensions.json").read_text())
SOURCE = json.loads((ROOT / "assets/v3/iterations/pallet-load/candidate/geometry-checks.json").read_text())
raw = PATH.read_bytes()
assert struct.unpack_from("<4sII", raw) == (b"glTF", 2, len(raw))
offset=12;chunks={}
while offset < len(raw):
    length,kind=struct.unpack_from("<II",raw,offset);offset+=8
    assert length%4==0
    chunks[kind]=raw[offset:offset+length];offset+=length
assert offset==len(raw)
data=json.loads(chunks[0x4E4F534A]);binary=chunks[0x004E4942]
assert len(data["buffers"])==1 and "uri" not in data["buffers"][0]
assert 0<=len(binary)-data["buffers"][0]["byteLength"]<4
assert not any(data.get(k) for k in ["extensionsRequired","images","textures","skins","animations","cameras"])
formats={5120:"b",5121:"B",5122:"h",5123:"H",5125:"I",5126:"f"}
sizes={"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}


def accessor(index):
    a=data["accessors"][index];assert "sparse" not in a and not a.get("normalized",False)
    v=data["bufferViews"][a["bufferView"]];assert v["buffer"]==0
    fmt="<"+formats[a["componentType"]]*sizes[a["type"]];width=struct.calcsize(fmt)
    stride=v.get("byteStride",width);start=v.get("byteOffset",0)+a.get("byteOffset",0)
    end=start+(a["count"]-1)*stride+width
    assert stride>=width and end<=v.get("byteOffset",0)+v["byteLength"] and end<=len(binary)
    values=np.array([struct.unpack_from(fmt,binary,start+i*stride) for i in range(a["count"])])
    assert np.isfinite(values).all()
    return values


for i in range(len(data["accessors"])):accessor(i)


def matrix(node):
    if "matrix" in node:return np.array(node["matrix"]).reshape(4,4).T
    x,y,z,w=node.get("rotation",[0,0,0,1]);m=np.eye(4)
    m[:3,:3]=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                      [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                      [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])@np.diag(node.get("scale",[1,1,1]))
    m[:3,3]=node.get("translation",[0,0,0]);return m


nodes=data["nodes"];scene=data["scenes"][data.get("scene",0)];assert len(scene["nodes"])==1
root_index=scene["nodes"][0];root=nodes[root_index]
assert root["name"]=="pallet-load__HU" and np.max(np.abs(matrix(root)-np.eye(4)))<1e-7
for k,v in {"asset_id":"pallet-load","namespace":"v3","layout_version":"qoima-144x72-v3","up_axis":"Y","units":"m","forward_axis":"+Z","contains_inventory":False,"operational_admission":False}.items():assert root["extras"][k]==v
world={};parents={}


def visit(index,parent):
    assert index not in world
    world[index]=parent@matrix(nodes[index])
    for child in nodes[index].get("children",[]):
        assert child not in parents;parents[child]=index;visit(child,world[index])


visit(root_index,np.eye(4));assert len(world)==len(nodes)==30
expected_names={"PALLET_LOAD | "+name for name in PLAN["palette"]}
assert {m["name"] for m in data["materials"]}==expected_names
for mat in data["materials"]:
    name=mat["name"].split(" | ")[1];color=PLAN["palette"][name].lstrip("#")
    srgb=[int(color[i:i+2],16)/255 for i in (0,2,4)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in srgb]+[1]
    pbr=mat["pbrMetallicRoughness"]
    assert max(abs(a-b) for a,b in zip(pbr["baseColorFactor"],linear))<1e-6
    assert abs(pbr["roughnessFactor"]-.86)<1e-6 and pbr["metallicFactor"]==0

content_flags=[];triangles=[];materials=[];points=[];normal_lengths=[];parts=[];fingerprint_parts={};mesh_count=0;min_dot=1
for ni,node in enumerate(nodes):
    if "mesh" not in node:continue
    mesh_count+=1;assert parents[ni]==root_index
    meshparts=json.loads(node["extras"]["source_parts_json"]);parts+=meshparts
    is_content_mesh=all(n.startswith("unit_body_") for n in meshparts)
    m=world[ni];normal_matrix=np.linalg.inv(m[:3,:3]).T
    for primitive in data["meshes"][node["mesh"]]["primitives"]:
        assert primitive.get("mode",4)==4 and set(primitive["attributes"])=={"POSITION","NORMAL"}
        p=accessor(primitive["attributes"]["POSITION"]);n=accessor(primitive["attributes"]["NORMAL"])
        assert len(p)==len(n)
        p=(np.c_[p,np.ones(len(p))]@m.T)[:,:3];n=n@normal_matrix.T
        lens=np.linalg.norm(n,axis=1);normal_lengths+=lens.tolist();assert np.max(np.abs(lens-1))<2e-5
        indices=accessor(primitive["indices"]).reshape(-1).astype(int)
        assert len(indices)%3==0 and min(indices)>=0 and max(indices)<len(p)
        name=data["materials"][primitive["material"]]["name"];points+=p.tolist()
        for ids in indices.reshape(-1,3):
            tri=p[ids];cross=np.cross(tri[1]-tri[0],tri[2]-tri[0]);length=np.linalg.norm(cross)
            assert length>1e-12
            dot=float(np.dot(cross/length,np.mean(n[ids],axis=0)));assert dot>0;min_dot=min(min_dot,dot)
            triangles.append(tri);materials.append(name);content_flags.append(is_content_mesh)
            quantized=[]
            for vertex in tri:
                vertex=[round(float(c),6) for c in vertex];quantized.append(tuple(0.0 if c==0 else c for c in vertex))
            fingerprint_parts.setdefault(name,[]).append(sorted(quantized))
assert mesh_count==3 and len(triangles)==7152 and len(parts)==len(set(parts))==84
fingerprints={name:{"triangles":len(tris),"sha256":hashlib.sha256(json.dumps(sorted(tris),sort_keys=True,separators=(',',':')).encode()).hexdigest()} for name,tris in fingerprint_parts.items()}
assert fingerprints==SOURCE["material_triangle_fingerprints_1e_6_m"],"Actual BIN geometry differs from evaluated source"
low=np.min(points,axis=0);high=np.max(points,axis=0)
assert np.max(np.abs(low-[-.6,0,-.5]))<1e-6 and np.max(np.abs(high-[.6,1.35,.5]))<1e-6
anchors={};max_anchor_error=0
expected={a["anchor_id"]:a for a in PLAN["anchors"]}
for i,node in enumerate(nodes):
    aid=node.get("extras",{}).get("anchor_id")
    if not aid:continue
    assert aid not in anchors and aid in expected and parents[i]==root_index and "mesh" not in node
    p=world[i][:3,3];error=float(np.max(np.abs(p-expected[aid]["local_xyz_m"])))
    assert error<1e-6;max_anchor_error=max(max_anchor_error,error)
    assert node["extras"]["role"]==expected[aid]["role"] and node["extras"]["mass_computed_from_mesh"] is False
    anchors[aid]=p.tolist()
assert set(anchors)==set(expected)
assert root['extras']['HU_count']==1 and root['extras']['units_per_HU']==24 and root['extras']['declared_gross_mass_kg']==455
assert root['extras']['mass_computed_from_mesh'] is False and root['extras']['prototype_contents_not_stock'] is True
for key,field in [('c02_source_sha256','source_C02'),('c08_source_sha256','source_C08')]:assert root['extras'][key]==PLAN[field]['sha256']
assert root['extras']['dimension_plan_sha256']==hashlib.sha256((ROOT/'assets/v3/specs/pallet-load.dimensions.json').read_bytes()).hexdigest()

# Vectorized actual-triangle Moller-Trumbore. No Blender/BVH or declared bounds.
tris=np.array(triangles);first=tris[:,0];e1=tris[:,1]-first;e2=tris[:,2]-first
face_normal=np.cross(e1,e2);face_normal/=np.linalg.norm(face_normal,axis=1)[:,None]


def ray(origin,direction,distance,mask=None):
    origin=np.array(origin);direction=np.array(direction);cross=np.cross(direction,e2)
    det=np.einsum('ij,ij->i',e1,cross);valid=np.abs(det)>1e-12
    inv=np.divide(1,det,out=np.zeros_like(det),where=valid)
    delta=origin-first;u=np.einsum('ij,ij->i',delta,cross)*inv;q=np.cross(delta,e1)
    v=(q@direction)*inv;t=np.einsum('ij,ij->i',e2,q)*inv
    valid &= (u>=-1e-9)&(v>=-1e-9)&(u+v<=1+1e-9)&(t>=0)&(t<=distance)
    if mask is not None:valid &= mask
    ids=np.flatnonzero(valid)
    if not len(ids):return None
    i=int(ids[np.argmin(t[ids])]);return float(t[i]),origin+direction*t[i],face_normal[i],materials[i]

# All24 frames and actual body triangle envelopes are independently reconstructed.
catalog=json.loads((ROOT/PLAN['source_C02']['path']).read_text())
recipe=next(x for x in catalog['packing_recipes'] if x['archetype_id']=='PALLET_LOAD')
frames={int(n['extras']['unit_ordinal']):i for i,n in enumerate(nodes) if n.get('extras',{}).get('role')=='HU_content_unit_frame'}
assert set(frames)==set(range(1,25))
content=np.array(content_flags);wood=np.array([m=='PALLET_LOAD | wood' for m in materials])
covered=np.zeros(len(tris),dtype=bool);unit_measurements=[];support_rays=0;max_support_error=0.
for u in recipe['unit_instances']:
    ordinal=u['unit_ordinal'];lo=np.array(u['min_xyz_m'])-[.6,0,.5];hi=np.array(u['max_xyz_m'])-[.6,0,.5]
    node=nodes[frames[ordinal]];assert parents[frames[ordinal]]==root_index and 'mesh' not in node
    assert node['extras']['prototype_contents_not_stock'] is True
    assert max(abs(a-b) for a,b in zip(node['extras']['packaged_dimensions_xyz_m'],[.36,.26,.28]))<1e-6
    assert np.max(np.abs(world[frames[ordinal]][:3,3]-(lo+hi)/2))<1e-6
    mask=content & np.all(tris>=lo-1e-6,axis=(1,2)) & np.all(tris<=hi+1e-6,axis=(1,2))
    assert np.count_nonzero(mask)==188 and not np.any(covered&mask)
    covered |= mask
    vertices=tris[mask].reshape(-1,3)
    assert np.max(np.abs(np.min(vertices,axis=0)-lo))<1e-6 and np.max(np.abs(np.max(vertices,axis=0)-hi))<1e-6
    for x in np.linspace(lo[0]+.02,hi[0]-.02,3):
        for z in np.linspace(lo[2]+.02,hi[2]-.02,3):
            bottom=ray([x,lo[1]-.01,z],[0,1,0],.02,mask)
            support=ray([x,lo[1]+.01,z],[0,-1,0],.02,wood)
            assert bottom is not None and support is not None and bottom[2][1]<-.999 and support[2][1]>.999
            error=abs(float(bottom[1][1]-support[1][1]));assert error<1e-6;max_support_error=max(max_support_error,error);support_rays+=2
    unit_measurements.append({'unit_ordinal':ordinal,'actual_body_triangles':188,'actual_bounds':{'min':np.min(vertices,axis=0).tolist(),'max':np.max(vertices,axis=0).tolist()},'frame_node':node['name']})
assert np.array_equal(covered,content) and int(np.count_nonzero(content))==4512


def external_triangles(path):
    raw=path.read_bytes();offset=12;chunks={}
    while offset<len(raw):
        n,k=struct.unpack_from('<II',raw,offset);offset+=8;chunks[k]=raw[offset:offset+n];offset+=n
    doc=json.loads(chunks[0x4E4F534A]);blob=chunks[0x004E4942]
    def acc(index):
        a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
        fmt='<'+formats[a['componentType']]*sizes[a['type']];stride=v.get('byteStride',struct.calcsize(fmt));start=v.get('byteOffset',0)+a.get('byteOffset',0)
        return np.array([struct.unpack_from(fmt,blob,start+i*stride) for i in range(a['count'])])
    transforms={}
    def walk(i,parent):
        transforms[i]=parent@matrix(doc['nodes'][i])
        for c in doc['nodes'][i].get('children',[]):walk(c,transforms[i])
    for i in doc['scenes'][doc.get('scene',0)]['nodes']:walk(i,np.eye(4))
    result=[]
    for i,node in enumerate(doc['nodes']):
        if 'mesh' not in node:continue
        for primitive in doc['meshes'][node['mesh']]['primitives']:
            p=acc(primitive['attributes']['POSITION']);p=(np.c_[p,np.ones(len(p))]@transforms[i].T)[:,:3]
            ids=acc(primitive['indices']).reshape(-1,3).astype(int);result.extend(p[ids])
    return np.array(result)


def fixture_box(lo,hi):
    a,b,c=lo;d,e,f=hi
    v=np.array([[a,b,c],[d,b,c],[d,e,c],[a,e,c],[a,b,f],[d,b,f],[d,e,f],[a,e,f]])
    quads=[[0,1,5,4],[3,7,6,2],[4,5,6,7],[0,3,2,1],[0,4,7,3],[1,2,6,5]]
    return np.array([v[ids] for q in quads for ids in [[q[0],q[1],q[2]],[q[0],q[2],q[3]]]])


def external_ray(mesh,origin,direction,distance):
    start=mesh[:,0];a=mesh[:,1]-start;b=mesh[:,2]-start;direction=np.array(direction);origin=np.array(origin)
    h=np.cross(direction,b);det=np.einsum('ij,ij->i',a,h);valid=np.abs(det)>1e-12
    inv=np.divide(1,det,out=np.zeros_like(det),where=valid);delta=origin-start
    u=np.einsum('ij,ij->i',delta,h)*inv;q=np.cross(delta,a);v=(q@direction)*inv;t=np.einsum('ij,ij->i',b,q)*inv
    valid &= (u>=-1e-9)&(v>=-1e-9)&(u+v<=1+1e-9)&(t>=0)&(t<=distance)
    ids=np.flatnonzero(valid)
    if not len(ids):return None
    i=int(ids[np.argmin(t[ids])]);normal=np.cross(a[i],b[i]);normal/=np.linalg.norm(normal)
    return origin+direction*t[i],normal


heavy_path=ROOT/'frontend/public/models/v3/heavy-bay.glb';heavy_tris=external_triangles(heavy_path)
fork_tris=np.concatenate([fixture_box([x-.04,.11,-.55],[x+.04,.18,.55]) for x in [-.4,.4]])
m03_contacts=0;fork_contacts=0;max_base_error=0.
for zc in [-.4,0,.4]:
    for left,right in [(-.595,-.475),(-.165,.165),(.475,.595)]:
        for x in np.linspace(left,right,3):
            for z in np.linspace(zc-.095,zc+.095,3):
                bottom=ray([x,-.01,z],[0,1,0],.02);top=external_ray(heavy_tris,[x,.20,z+.05],[0,-1,0],.03)
                assert bottom is not None and top is not None and bottom[2][1]<-.999 and top[1][1]>.999
                error=abs(float(bottom[1][1]+.18-top[0][1]));assert error<1e-6;max_base_error=max(max_base_error,error);m03_contacts+=1
    for centre in [-.4,.4]:
        for x in np.linspace(centre-.038,centre+.038,3):
            for z in np.linspace(zc-.095,zc+.095,3):
                bottom=ray([x,-.01,z],[0,1,0],.02);top=external_ray(fork_tris,[x,.20,z+.05],[0,-1,0],.03)
                assert bottom is not None and top is not None and bottom[2][1]<-.999 and top[1][1]>.999
                error=abs(float(bottom[1][1]+.18-top[0][1]));assert error<1e-6;max_base_error=max(max_base_error,error);fork_contacts+=1
assert np.min(tris[:,:,1])+.18>=max(np.max(heavy_tris[:,:,1]),np.max(fork_tris[:,:,1]))-1e-6

def polygon_area(poly):
    return abs(sum(poly[i][0]*poly[(i+1)%len(poly)][1]-poly[(i+1)%len(poly)][0]*poly[i][1] for i in range(len(poly)))/2) if len(poly)>2 else 0.
def clip_triangle(subject,triangle):
    signed=sum(triangle[i][0]*triangle[(i+1)%3][1]-triangle[(i+1)%3][0]*triangle[i][1] for i in range(3));sign=1 if signed>0 else -1
    for a,b in zip(triangle,triangle[1:]+triangle[:1]):
        def side(p):return sign*((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))
        if not subject:return []
        out=[];prev=subject[-1];pv=side(prev)
        for cur in subject:
            cv=side(cur)
            if (cv>=0)!=(pv>=0):
                t=pv/(pv-cv);out.append((prev[0]+t*(cur[0]-prev[0]),prev[1]+t*(cur[1]-prev[1])))
            if cv>=0:out.append(cur)
            prev,pv=cur,cv
        subject=out
    return subject

cap_faces=tris[(np.max(np.abs(tris[:,:,1]-1.34),axis=1)<1e-6)&(face_normal[:,1]>.999999)&wood]
cap_y=float(np.mean(cap_faces[:,:,1]));band_cap_contacts=[]
for side in [-1,1]:
    mask=(np.max(np.abs(tris[:,:,1]-1.34),axis=1)<1e-6)&(face_normal[:,1]<-.999999)&(np.abs(np.mean(tris[:,:,0],axis=1)-side*.375)<.02)&(np.array(materials)=='PALLET_LOAD | petrol')
    band_faces=tris[mask];assert len(band_faces)>0 and len(cap_faces)>0
    area=sum(polygon_area(clip_triangle([tuple(p[[0,2]]) for p in a],[tuple(p[[0,2]]) for p in b])) for a in cap_faces for b in band_faces)
    gap=float(np.mean(band_faces[:,:,1]))-cap_y
    assert area>.018 and abs(gap)<1e-6
    top_band_mask=(np.array(materials)=='PALLET_LOAD | petrol')&(np.abs(np.mean(tris[:,:,0],axis=1)-side*.375)<.02)&(np.min(tris[:,:,1],axis=1)>1.339)
    rays=0;maximum_error=0.
    for x in np.linspace(side*.375-.015,side*.375+.015,3):
        for z in np.linspace(-.28,.28,5):
            lower=ray([x,1.33,z],[0,1,0],.02,top_band_mask);upper=ray([x,1.35,z],[0,-1,0],.02,wood)
            assert lower is not None and upper is not None and lower[2][1]<-.999 and upper[2][1]>.999
            error=abs(float(lower[1][1]-upper[1][1]));assert error<1e-6;maximum_error=max(maximum_error,error);rays+=2
    band_cap_contacts.append({'band_side':side,'finite_flat_triangle_contact_area_m2':area,'signed_band_bottom_minus_cap_top_m':gap,'opposing_surface_rays':rays,'maximum_ray_plane_error_m':maximum_error,'actual_gap':False})

report={'asset_id':'pallet-load','status':'PASS','method':'Independent actual embedded BIN accessor/TRS/index/normal/material parsing and triangle rays; no bpy.',
        'glb_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'bounds_runtime':{'min':low.tolist(),'max':high.tolist()},'dimensions_xyz_m':(high-low).tolist(),
        'runtime_meshes':mesh_count,'runtime_primitives':sum(len(m['primitives']) for m in data['meshes']),'triangles':len(tris),'editable_source_parts_matched':len(parts),'materials':sorted(expected_names),
        'normal_length_range':[min(normal_lengths),max(normal_lengths)],'minimum_face_vs_average_normal_dot':min_dot,'indices_and_winding_valid':True,
        'all_source_triangle_multisets_by_material_match_at_1e_6_m':True,'material_triangle_fingerprints':fingerprints,
        'one_HU_not_24_lots':True,'actual_unit_frames':24,'actual_unit_bodies':24,'actual_content_triangles':4512,'unit_measurements':unit_measurements,
        'carton_support_contact_rays':support_rays,'maximum_carton_support_error_m':max_support_error,'anchors':anchors,'maximum_anchor_error_m':max_anchor_error,
        'actual_M03_base_patch_points':m03_contacts,'actual_two_fork_base_patch_points':fork_contacts,'maximum_base_contact_error_m':max_base_error,
        'M03_actual_BIN_sha256':hashlib.sha256(heavy_path.read_bytes()).hexdigest(),'fork_fixture':'Actual triangle boxes .08x.07x1.10 at X+-.40; static contact only, not final M14 vehicle/actions.',
        'HU_pose_for_base_contacts':[0,.18,.05],'no_interior_HU_support_overlap':True,'mass_and_CG_declared_synthetic_not_mesh_computed':True,'top_band_cap_contact_witnesses':band_cap_contacts,
        'no_external_resources_or_required_extensions':True,'no_fixture_studio_or_vehicle_in_standalone':True,'root_browser_Khronos_gate':'pending root actual review'}
(ROOT/'assets/v3/iterations/pallet-load/candidate/binary-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','glb_bytes','sha256','dimensions_xyz_m','runtime_meshes','runtime_primitives','triangles','actual_unit_frames','carton_support_contact_rays','actual_M03_base_patch_points','actual_two_fork_base_patch_points','maximum_base_contact_error_m']},indent=2))


