"""Independent actual BIN inspection. Run with bundled Python/NumPy, no bpy."""
from pathlib import Path
import hashlib
import json
import math
import struct

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
PATH = ROOT / "frontend/public/models/v3/heavy-bay.glb"
PLAN = json.loads((ROOT / "assets/v3/specs/heavy-bay.dimensions.json").read_text())
SOURCE = json.loads((ROOT / "assets/v3/iterations/heavy-bay/candidate/geometry-checks.json").read_text())
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
assert root["name"]=="heavy-bay__MODULE" and np.max(np.abs(matrix(root)-np.eye(4)))<1e-7
for k,v in {"asset_id":"heavy-bay","namespace":"v3","layout_version":"qoima-144x72-v3","up_axis":"Y","units":"m","forward_axis":"+Z","contains_inventory":False,"operational_admission":False}.items():assert root["extras"][k]==v
world={};parents={}


def visit(index,parent):
    assert index not in world
    world[index]=parent@matrix(nodes[index])
    for child in nodes[index].get("children",[]):
        assert child not in parents;parents[child]=index;visit(child,world[index])


visit(root_index,np.eye(4));assert len(world)==len(nodes)==5
expected_names={"HEAVY | "+name for name in PLAN["palette"]}
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
assert mesh_count==3 and len(triangles)==748 and len(parts)==len(set(parts))==17
fingerprints={name:{"triangles":len(tris),"sha256":hashlib.sha256(json.dumps(sorted(tris),sort_keys=True,separators=(',',':')).encode()).hexdigest()} for name,tris in fingerprint_parts.items()}
assert fingerprints==SOURCE["material_triangle_fingerprints_1e_6_m"],"Actual BIN geometry differs from evaluated source"
low=np.min(points,axis=0);high=np.max(points,axis=0)
assert np.max(np.abs(low-[-.8,0,-.7]))<1e-6 and np.max(np.abs(high-[.8,.18,.7]))<1e-6
anchors={};max_anchor_error=0
expected={a["anchor_id"]:a for a in PLAN["anchors"]}
for i,node in enumerate(nodes):
    aid=node.get("extras",{}).get("anchor_id")
    if not aid:continue
    assert aid not in anchors and aid in expected and parents[i]==root_index and "mesh" not in node
    p=world[i][:3,3];error=float(np.max(np.abs(p-expected[aid]["local_xyz_m"])))
    assert error<1e-6;max_anchor_error=max(max_anchor_error,error)
    assert node["extras"]["role"]=="storage_slot_bottom_centre" and node["extras"]["not_inventory_instance_id"]
    assert node['extras']['prototype_source_slot_id']==expected[aid]['prototype_source_slot_id']
    assert max(abs(x-y) for x,y in zip(node['extras']['usable_dimensions_xyz_m'],expected[aid]['usable_dimensions_xyz_m']))<1e-6
    assert json.loads(node['extras']['usable_bounds_module_json'])==expected[aid]['usable_bounds_module_local']
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
    for axis in range(3):
        other=[k for k in range(3) if k!=axis]
        for i in range(11):
            for j in range(11):
                start=np.zeros(3);start[axis]=lo[axis]+1e-5
                for k,t in zip(other,[i,j]):start[k]=lo[k]+1e-5+(hi[k]-lo[k]-2e-5)*t/10
                direction=np.zeros(3);direction[axis]=1
                assert ray(start,direction,hi[axis]-lo[axis]-2e-5) is None;clear+=1
    centre=p+[0,.30,0]
    for direction in [[-1,0,0],[1,0,0],[0,0,1],[0,1,0]]:
        assert ray(centre,direction,1.0) is None
    measurements.append({'anchor_id':aid,'clear_dimensions_tested_xyz_m':a['usable_dimensions_xyz_m'],'support_y_m':float(p[1]),'front_sides_top_open':True})

# Real support patches, not a full usable-floor claim.
for patch in PLAN["support_patches"]:
    for x in np.linspace(*patch["x_range_m"],11):
        for z in np.linspace(*patch["z_range_m"],21):
            hit=ray([x,.38,z],[0,-1,0],.21)
            assert hit is not None and hit[2][1]>.999 and hit[3]=='HEAVY | tan'
            error=abs(float(hit[1][1])-.18);assert error<1e-6
            max_floor_error=max(max_floor_error,error);floors+=1
hole_rays=0;hole_hit_ys=[]
for left,right in PLAN["open_top_channels"]["x_bands_m"]:
    for x in np.linspace(left+.01,right-.01,5):
        for z in np.linspace(-.69,.69,11):
            hit=ray([x,.38,z],[0,-1,0],.5)
            assert hit is None or hit[1][1]<.081
            if hit is not None:hole_hit_ys.append(float(hit[1][1]))
            hole_rays+=1

def clear_box(lo,hi,samples):
    total=0
    for axis in range(3):
        other=[k for k in range(3) if k!=axis]
        for i in range(samples):
            for j in range(samples):
                start=np.zeros(3);start[axis]=lo[axis]+1e-5
                for k,t in zip(other,[i,j]):start[k]=lo[k]+1e-5+(hi[k]-lo[k]-2e-5)*t/(samples-1)
                direction=np.zeros(3);direction[axis]=1
                assert ray(start,direction,hi[axis]-lo[axis]-2e-5) is None;total+=1
    return total
channels=0;blades=0
for left,right in PLAN["open_top_channels"]["x_bands_m"]:
    channels+=clear_box([left,.08001,-.8],[right,.18001,.8],11)
for spacing in [.24,.28,.32,.36,.40]:
    for side in [-1,1]:blades+=clear_box([side*spacing-.04,.11,-.8],[side*spacing+.04,.18,.8],7)

# Independent SAT (box axes, triangle normal, 9 edge cross-axes), rather than
# source inspector's polygon clipping, checks every actual BIN triangle over
# the union of every legal continuous half-spacing .24.. .40 m.
def triangle_box_intersects(tri,lo,hi):
    lo=np.array(lo);hi=np.array(hi);centre=(lo+hi)/2;half=(hi-lo)/2;v=tri-centre
    edges=[v[1]-v[0],v[2]-v[1],v[0]-v[2]]
    axes=list(np.eye(3))+[np.cross(edges[0],edges[1])]+[np.cross(e,a) for e in edges for a in np.eye(3)]
    for axis in axes:
        if np.dot(axis,axis)<1e-20:continue
        projection=v@axis;radius=half@np.abs(axis)
        if np.min(projection)>radius+1e-10 or np.max(projection)<-radius-1e-10:return False
    return True
sat_tests=0
for lo,hi in [([-.44,.11,-.8],[-.20,.18,.8]),([.20,.11,-.8],[.44,.18,.8])]:
    for tri in tris:
        assert not triangle_box_intersects(tri,lo,hi),'Actual BIN triangle blocks legal blade union';sat_tests+=1
flat_top_area=float(sum(np.linalg.norm(np.cross(t[1]-t[0],t[2]-t[0]))/2 for t in tris if np.max(np.abs(t[:,1]-.18))<1e-6))
assert root['extras']['full_floor_support'] is False
assert root['extras']['support_pattern']=='three_ribs_two_open_top_channels'
assert root['extras']['c04_source_sha256']==PLAN['source_contract']['sha256']
assert root['extras']['c08_source_sha256']==PLAN['C08_interface']['sha256']
assert root['extras']['dimension_plan_sha256']==hashlib.sha256((ROOT/'assets/v3/specs/heavy-bay.dimensions.json').read_bytes()).hexdigest()

report={'asset_id':'heavy-bay','status':'PASS','method':'Independent actual embedded BIN accessor/TRS/index/normal/material parser and vectorized triangle rays; no bpy and no declared-bounds geometry shortcut.',
        'glb_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'bounds_runtime':{'min':low.tolist(),'max':high.tolist()},'dimensions_xyz_m':(high-low).tolist(),
        'runtime_meshes':mesh_count,'triangles':len(triangles),'source_part_names':len(parts),'materials':sorted(expected_names),
        'finite_positions_and_normals':True,'normal_length_range':[min(normal_lengths),max(normal_lengths)],'minimum_face_vs_average_normal_dot':min_dot,
        'indices_valid_and_no_degenerate_or_inverted_faces':True,'single_root_and_no_external_resources_or_required_extensions':True,
        'all_source_triangle_multisets_by_material_match_at_1e_6_m':True,'material_triangle_fingerprints':fingerprints,
        'support_patches':PLAN['support_patches'],'actual_flat_top_area_m2':flat_top_area,'full_floor_support':False,
        'negative_hole_floor_rays':hole_rays,'negative_hole_hit_y_range_m':[min(hole_hit_ys),max(hole_hit_ys)] if hole_hit_ys else None,
        'clear_channel_segments':channels,'clear_blade_envelope_segments':blades,'continuous_blade_union_SAT_triangle_box_tests':sat_tests,'continuous_blade_union_triangle_intersections':0,
        'anchors':anchors,'maximum_anchor_error_m':max_anchor_error,'clear_interior_axis_segments':clear,'exact_floor_support_rays':floors,
        'maximum_floor_error_m':max_floor_error,'actual_open_space_checks':measurements,'no_cargo_worker_or_studio_hierarchy':True,
        'root_Khronos_browser_review':'pending; not claimed by numeric checks'}
(ROOT/'assets/v3/iterations/heavy-bay/candidate/binary-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','glb_bytes','sha256','dimensions_xyz_m','runtime_meshes','triangles','maximum_anchor_error_m','clear_interior_axis_segments','exact_floor_support_rays','maximum_floor_error_m']},indent=2))
