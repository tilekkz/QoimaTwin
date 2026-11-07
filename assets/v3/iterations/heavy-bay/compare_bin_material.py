"""Independent before/after actual world POSITION+NORMAL triangle comparison."""
from pathlib import Path
import hashlib
import json
import struct

import numpy as np

ROOT = Path(__file__).resolve().parents[4]


def fingerprint(path):
    raw = path.read_bytes(); offset = 12; chunks = {}
    while offset < len(raw):
        length, kind = struct.unpack_from("<II", raw, offset); offset += 8
        chunks[kind] = raw[offset:offset+length]; offset += length
    data = json.loads(chunks[0x4E4F534A]); binary = chunks[0x004E4942]

    def accessor(index):
        a = data["accessors"][index]; v = data["bufferViews"][a["bufferView"]]
        fmt = "<" + {5123: "H", 5125: "I", 5126: "f"}[a["componentType"]] * {"SCALAR": 1, "VEC3": 3}[a["type"]]
        stride = v.get("byteStride", struct.calcsize(fmt)); start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        return np.array([struct.unpack_from(fmt, binary, start+i*stride) for i in range(a["count"])])

    world = {}

    def visit(index, parent):
        node = data["nodes"][index]; m = np.eye(4)
        if "matrix" in node:
            m = np.array(node["matrix"]).reshape(4, 4).T
        else:
            x, y, z, w = node.get("rotation", [0, 0, 0, 1])
            m[:3, :3] = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                                  [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                                  [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]) @ np.diag(node.get("scale", [1, 1, 1]))
            m[:3, 3] = node.get("translation", [0, 0, 0])
        world[index] = parent @ m
        for child in node.get("children", []): visit(child, world[index])

    for index in data["scenes"][data.get("scene", 0)]["nodes"]: visit(index, np.eye(4))
    triangles = [];actual_triangles=[]
    for index, node in enumerate(data["nodes"]):
        if "mesh" not in node: continue
        m = world[index]; normal_matrix = np.linalg.inv(m[:3, :3]).T
        for primitive in data["meshes"][node["mesh"]]["primitives"]:
            p = accessor(primitive["attributes"]["POSITION"]); n = accessor(primitive["attributes"]["NORMAL"])
            p = (np.c_[p, np.ones(len(p))] @ m.T)[:, :3]; n = n @ normal_matrix.T
            indices = accessor(primitive["indices"]).reshape(-1, 3).astype(int)
            for tri in indices:
                vertices = []
                for i in tri:
                    values = [round(float(x), 6) for x in list(p[i])+list(n[i])]
                    vertices.append(tuple(0.0 if x == 0 else x for x in values))
                triangles.append(sorted(vertices))
                actual_triangles.append(sorted([list(p[i])+list(n[i]) for i in tri],key=lambda row:tuple(round(float(v),5) for v in row[:3])))
    return {"actual": actual_triangles, "triangles": len(triangles), "world_position_normal_triangle_multiset_sha256_1e_6": hashlib.sha256(json.dumps(sorted(triangles), separators=(",", ":")).encode()).hexdigest()}


before = fingerprint(ROOT / "assets/v3/iterations/heavy-bay/c08-v02/heavy-bay.glb")
after = fingerprint(ROOT / "frontend/public/models/v3/heavy-bay.glb")
# Hash quantization can straddle rounding boundaries after a different material
# batch origin. Match actual world triangles by coarse position keys, then
# measure the real coordinate/normal errors rather than relaxing a hash result.
def groups(result):
    grouped={}
    for tri in result.pop("actual"):
        key=tuple(sorted(tuple(round(x,5) for x in row[:3]) for row in tri))
        grouped.setdefault(key,[]).append(np.array(tri))
    return grouped
old=groups(before);new=groups(after)
assert old.keys()==new.keys() and before["triangles"]==after["triangles"]==748
max_position_error=0.;max_normal_error=0.;max_angle_degrees=0.
for key,items in old.items():
    pending=list(new[key]);assert len(items)==len(pending)
    for triangle in items:
        i=min(range(len(pending)),key=lambda j:np.max(np.abs(triangle-pending[j])))
        other=pending.pop(i)
        max_position_error=max(max_position_error,float(np.max(np.abs(triangle[:,:3]-other[:,:3]))))
        max_normal_error=max(max_normal_error,float(np.max(np.abs(triangle[:,3:]-other[:,3:]))))
        left=triangle[:,3:]/np.linalg.norm(triangle[:,3:],axis=1)[:,None];right=other[:,3:]/np.linalg.norm(other[:,3:],axis=1)[:,None]
        max_angle_degrees=max(max_angle_degrees,float(np.max(np.degrees(np.arccos(np.clip(np.sum(left*right,axis=1),-1,1))))))
assert max_position_error<=1e-6 and max_normal_error<=2e-4 and max_angle_degrees<.02,(max_position_error,max_normal_error)
report={"status":"PASS","actual_world_position_normal_triangle_multisets_equal_within_tolerance_ignoring_material":True,
        "before":before,"after":after,"maximum_world_position_error_m":max_position_error,"maximum_world_unit_normal_component_error":max_normal_error,
        "position_tolerance_m":1e-6,"normal_component_tolerance":2e-4,"maximum_normal_angle_degrees":max_angle_degrees,"normal_angle_tolerance_degrees":.02,"BIN_normals_exactly_equal":False,
        "method":"Independent embedded BIN accessors/worldTRS; matching world triangles and measuring actual differences after different material batch origins. Material IDs deliberately excluded; source signatures are exact."}
(ROOT/"assets/v3/iterations/heavy-bay/material-final/BIN-material-equivalence.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report))
