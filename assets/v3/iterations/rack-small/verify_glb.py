"""Independent actual BIN inspection. Run with bundled Python/NumPy, no bpy."""
from pathlib import Path
import hashlib
import json
import math
import struct

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
PATH = ROOT / "frontend/public/models/v3/rack-small.glb"
PLAN = json.loads((ROOT / "assets/v3/specs/rack-small.dimensions.json").read_text())
SOURCE = json.loads((ROOT / "assets/v3/iterations/rack-small/candidate/geometry-checks.json").read_text())
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
assert root["name"]=="rack-small__MODULE" and np.max(np.abs(matrix(root)-np.eye(4)))<1e-7
for k,v in {"asset_id":"rack-small","namespace":"v3","layout_version":"qoima-144x72-v3","up_axis":"Y","units":"m","forward_axis":"+Z","contains_inventory":False,"operational_admission":False}.items():assert root["extras"][k]==v
world={};parents={}


def visit(index,parent):
    assert index not in world
    world[index]=parent@matrix(nodes[index])
    for child in nodes[index].get("children",[]):
        assert child not in parents;parents[child]=index;visit(child,world[index])


visit(root_index,np.eye(4));assert len(world)==len(nodes)==14
expected_names={"SMALL | "+name for name in PLAN["palette"]}
assert {m["name"] for m in data["materials"]}==expected_names
for mat in data["materials"]:
    name=mat["name"].split(" | ")[1];color=PLAN["palette"][name].lstrip("#")
    srgb=[int(color[i:i+2],16)/255 for i in (0,2,4)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in srgb]+[1]
    pbr=mat["pbrMetallicRoughness"]
    assert max(abs(a-b) for a,b in zip(pbr["baseColorFactor"],linear))<1e-6
    assert abs(pbr["roughnessFactor"]-.86)<1e-6 and pbr["metallicFactor"]==0

triangles=[];materials=[];points=[];normal_lengths=[];parts=[];fingerprint_parts={};mesh_count=0;min_dot=1
for ni,node in enumerate(nodes):
    if "mesh" not in node:continue
    mesh_count+=1;assert parents[ni]==root_index
    parts+=json.loads(node["extras"]["source_parts_json"])
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
            triangles.append(tri);materials.append(name)
            quantized=[]
            for vertex in tri:
                vertex=[round(float(c),6) for c in vertex];quantized.append(tuple(0.0 if c==0 else c for c in vertex))
            fingerprint_parts.setdefault(name,[]).append(sorted(quantized))
assert mesh_count==3 and len(triangles)==2676 and len(parts)==len(set(parts))==59
fingerprints={name:{"triangles":len(tris),"sha256":hashlib.sha256(json.dumps(sorted(tris),sort_keys=True,separators=(',',':')).encode()).hexdigest()} for name,tris in fingerprint_parts.items()}
assert fingerprints==SOURCE["material_triangle_fingerprints_1e_6_m"],"Actual BIN geometry differs from evaluated source"
low=np.min(points,axis=0);high=np.max(points,axis=0)
assert np.max(np.abs(low-[-1.2,0,-.5]))<1e-6 and np.max(np.abs(high-[1.2,1.55,.5]))<1e-6
anchors={};max_anchor_error=0
expected={a["anchor_id"]:a for a in PLAN["anchors"]}
for i,node in enumerate(nodes):
    aid=node.get("extras",{}).get("anchor_id")
    if not aid:continue
    assert aid not in anchors and aid in expected and parents[i]==root_index and "mesh" not in node
    p=world[i][:3,3];error=float(np.max(np.abs(p-expected[aid]["local_xyz_m"])))
    assert error<1e-6;max_anchor_error=max(max_anchor_error,error)
    assert node["extras"]["role"]=="storage_slot_bottom_centre" and node["extras"]["not_inventory_instance_id"]
    anchors[aid]=p.tolist()
assert set(anchors)==set(expected)

# Vectorized actual-triangle Moller-Trumbore. No Blender/BVH or declared bounds.
tris=np.array(triangles);first=tris[:,0];e1=tris[:,1]-first;e2=tris[:,2]-first
face_normal=np.cross(e1,e2);face_normal/=np.linalg.norm(face_normal,axis=1)[:,None]


def ray(origin,direction,distance):
    origin=np.array(origin);direction=np.array(direction);cross=np.cross(direction,e2)
    det=np.einsum('ij,ij->i',e1,cross);valid=np.abs(det)>1e-12
    inv=np.divide(1,det,out=np.zeros_like(det),where=valid)
    delta=origin-first;u=np.einsum('ij,ij->i',delta,cross)*inv;q=np.cross(delta,e1)
    v=(q@direction)*inv;t=np.einsum('ij,ij->i',e2,q)*inv
    valid &= (u>=-1e-9)&(v>=-1e-9)&(u+v<=1+1e-9)&(t>=0)&(t<=distance)
    ids=np.flatnonzero(valid)
    if not len(ids):return None
    i=int(ids[np.argmin(t[ids])]);return float(t[i]),origin+direction*t[i],face_normal[i],materials[i]


floors=0;clear=0;measurements=[];max_floor_error=0
for aid,a in expected.items():
    b=a["usable_bounds_module_local"];lo,hi=np.array(b["min"]),np.array(b["max"]);p=np.array(a["local_xyz_m"])
    for x in np.linspace(lo[0]+1e-5,hi[0]-1e-5,9):
        for z in np.linspace(lo[2]+1e-5,hi[2]-1e-5,9):
            hit=ray([x,p[1]+.2,z],[0,-1,0],.21)
            assert hit is not None and hit[2][1]>.999 and hit[3]=='SMALL | petrol'
            error=abs(float(hit[1][1])-p[1]);assert error<1e-6;max_floor_error=max(max_floor_error,error);floors+=1
    for axis in range(3):
        other=[k for k in range(3) if k!=axis]
        for i in range(7):
            for j in range(7):
                start=np.zeros(3);start[axis]=lo[axis]+1e-5
                for k,t in zip(other,[i,j]):start[k]=lo[k]+1e-5+(hi[k]-lo[k]-2e-5)*t/6
                direction=np.zeros(3);direction[axis]=1
                assert ray(start,direction,hi[axis]-lo[axis]-2e-5) is None;clear+=1
    centre=p+[0,.175,0];distances=[]
    for direction in [[-1,0,0],[1,0,0],[0,0,-1]]:
        hit=ray(centre,direction,.3);assert hit is not None and abs(hit[0]-.21)<1e-6;distances.append(hit[0])
    hit=ray(p+[0,.04,0],[0,0,1],.3);assert hit is not None and abs(hit[0]-.21)<1e-6;distances.append(hit[0])
    assert ray(centre,[0,0,1],.3) is None
    measurements.append({'anchor_id':aid,'actual_width_m':distances[0]+distances[1],'actual_depth_between_back_and_low_lip_m':distances[2]+distances[3],'support_y_m':p[1]})

report={'asset_id':'rack-small','status':'PASS','method':'Independent actual embedded BIN accessor/TRS/index/normal/material parser and vectorized triangle rays; no bpy and no declared-bounds geometry shortcut.',
        'glb_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'bounds_runtime':{'min':low.tolist(),'max':high.tolist()},'dimensions_xyz_m':(high-low).tolist(),
        'runtime_meshes':mesh_count,'triangles':len(triangles),'source_part_names':len(parts),'materials':sorted(expected_names),
        'finite_positions_and_normals':True,'normal_length_range':[min(normal_lengths),max(normal_lengths)],'minimum_face_vs_average_normal_dot':min_dot,
        'indices_valid_and_no_degenerate_or_inverted_faces':True,'single_root_and_no_external_resources_or_required_extensions':True,
        'all_source_triangle_multisets_by_material_match_at_1e_6_m':True,'material_triangle_fingerprints':fingerprints,
        'anchors':anchors,'maximum_anchor_error_m':max_anchor_error,'clear_interior_axis_segments':clear,'exact_floor_support_rays':floors,
        'maximum_floor_error_m':max_floor_error,'actual_inner_measurements':measurements,'no_cargo_worker_or_studio_hierarchy':True,
        'root_Khronos_browser_review':'pending; not claimed by numeric checks'}
(ROOT/'assets/v3/iterations/rack-small/candidate/binary-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','glb_bytes','sha256','dimensions_xyz_m','runtime_meshes','triangles','maximum_anchor_error_m','clear_interior_axis_segments','exact_floor_support_rays','maximum_floor_error_m']},indent=2))
