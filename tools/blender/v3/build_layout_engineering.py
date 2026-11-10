"""L10 isolated engineering massing, from accepted numeric proposals.

Background only, two threads. No final-art assets or active worker sources.
"""
import argparse
import contextlib
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v3_common import (ROOT, ASSET_COLLECTION, anchor, beam, box, finish, group,
                       material, reset, runtime_xyz, xyz)

ASSET = "layout-engineering"
PREVIEWS = ROOT / "assets/v3/previews" / ASSET
WITNESS = ROOT / "assets/v3/iterations/worker-base/P01.2/iteration-02.blend"
INPUTS = [
    "docs/v3/contract-proposals/layout-v3.zones.json",
    "docs/v3/contract-proposals/storage-layout-v3.json",
    "docs/v3/contract-proposals/ports-v3.inbound.json",
    "docs/v3/contract-proposals/ports-v3.outbound.json",
    "docs/v3/contract-proposals/pedestrian-graph-v3.json",
    "docs/v3/contract-proposals/vehicle-graph-v3.json",
    "docs/v3/contract-proposals/conveyor-v3.json",
]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mesh(name, points, faces, mat, parent):
    data = bpy.data.meshes.new(name)
    data.from_pydata([xyz(p) for p in points], [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.data.collections[ASSET_COLLECTION].objects.link(obj)
    obj.parent = parent
    obj.data.materials.append(mat)
    return obj


def label(body, pos, size, mat, parent, upright=False):
    data = bpy.data.curves.new("LABEL__"+body, "FONT")
    data.body, data.size = body, size
    data.align_x, data.align_y = "CENTER", "CENTER"
    data.resolution_u = 2
    data.fill_mode = "BOTH"
    obj = bpy.data.objects.new("LABEL__"+body, data)
    bpy.data.collections[ASSET_COLLECTION].objects.link(obj)
    obj.parent, obj.location = parent, xyz(pos)
    if upright:
        obj.rotation_euler.x = math.pi/2
    data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    return bpy.context.object


def stroke(name, a, b, width, y, mat, parent):
    if math.dist(a, b) < 1e-5:
        return
    dx, dz = b[0]-a[0], b[1]-a[1]
    length = math.hypot(dx, dz)
    normal = [-dz/length*width/2, dx/length*width/2]
    points = [[a[0]+normal[0],y,a[1]+normal[1]],
              [b[0]+normal[0],y,b[1]+normal[1]],
              [b[0]-normal[0],y,b[1]-normal[1]],
              [a[0]-normal[0],y,a[1]-normal[1]]]
    # Paint at a boundary stays inside the declared floor; it is not a new apron.
    points = [[min(144,max(0,p[0])),p[1],min(72,max(0,p[2]))] for p in points]
    return mesh(name, points, [(0,1,2,3)], mat, parent)


def outline(name, lo, hi, y, width, mat, parent):
    points = [(lo[0],lo[1]),(hi[0],lo[1]),(hi[0],hi[1]),(lo[0],hi[1])]
    for i in range(4):
        stroke(name+f"__{i}", points[i], points[(i+1)%4], width, y, mat, parent)


def gate(port, root, mats):
    pid = port["port_id"]
    g = group("GATE__"+pid, root)
    g["port_id"], g["clear_width_m"], g["clear_height_m"] = pid, port["clear_width_m"], port["clear_height_m"]
    x, _, z = port["world_pos"]
    w, h, t = port["clear_width_m"], port["clear_height_m"], .25
    normal = port["inward_facing"]
    mat = mats["incoming"] if port["direction"]=="inbound" else mats["outgoing"]
    if normal[0]:
        frame_x = x+normal[0]*t/2
        for sign in [-1,1]:
            box(pid+"__post", [frame_x,h/2,z+sign*(w/2+t/2)], [t,h,t],mat,g,0)
        box(pid+"__header",[frame_x,h+t/2,z],[t,t,w+2*t],mat,g,0)
        label(pid,[x+6*normal[0],.018,z],.70,mats["ink"],mats["labels"])
    else:
        frame_z = z+normal[2]*t/2
        for sign in [-1,1]:
            box(pid+"__post",[x+sign*(w/2+t/2),h/2,frame_z],[t,h,t],mat,g,0)
        box(pid+"__header",[x,h+t/2,frame_z],[w+2*t,t,t],mat,g,0)
        label(pid,[x,.018,frame_z+.5*normal[2]],.55,mats["ink"],mats["labels"])
    anchor("PORT__"+pid,port["world_pos"],g,"engineering_port_boundary")
    return g


def append_witness(parent, mat):
    before = sha(WITNESS)
    with bpy.data.libraries.load(str(WITNESS), link=False) as (available, incoming):
        incoming.objects = list(available.objects)
    candidates = [o for o in incoming.objects if o and o.name=="worker_base_root"]
    if len(candidates)!=1:
        raise ValueError("Frozen P01.2 source does not contain observed worker_base_root")
    worker = candidates[0]
    if max(abs(float(v)-1) for v in worker.scale)>1e-6:
        raise ValueError("Frozen witness root must have scale1; never rescale it")
    for obj in [worker]+list(worker.children_recursive):
        if obj.name not in bpy.data.collections[ASSET_COLLECTION].objects:
            bpy.data.collections[ASSET_COLLECTION].objects.link(obj)
        obj.name = "WITNESS__P01_2__"+obj.name
        if "asset_id" in obj:
            obj["source_asset_id"] = obj["asset_id"]
            del obj["asset_id"]
    worker.parent = parent
    worker.matrix_parent_inverse = Matrix.Identity(4)
    worker.location = xyz([72,0,38])
    worker["role"] = "frozen_scale_witness"
    worker["frozen_source_sha256"] = before
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    points=[]
    for obj in worker.children_recursive:
        if obj.type!="MESH":
            continue
        evaluated=obj.evaluated_get(graph)
        data=evaluated.to_mesh()
        points.extend(runtime_xyz(evaluated.matrix_world@v.co) for v in data.vertices)
        evaluated.to_mesh_clear()
    low=[min(p[i] for p in points) for i in range(3)]
    high=[max(p[i] for p in points) for i in range(3)]
    if abs(low[1])>1e-5 or abs(high[1]-low[1]-1.7)>1e-5:
        raise AssertionError(("Frozen worker floor/height changed",low,high))
    if sha(WITNESS)!=before:
        raise AssertionError("Frozen source changed")
    box("SCALE__1_70m",[73.2,.85,38],[.04,1.7,.04],mat,parent,0)
    for y in [.02,1.68]:
        box("SCALE__tick",[73.2,y,38],[.45,.04,.04],mat,parent,0)
    label("1.70 m",[74.1,.85,38],.23,mat,parent,True)
    return dict(path=str(WITNESS.relative_to(ROOT)).replace("\\","/"),
                sha256=before,instances=1,root_scale=list(worker.scale),
                bounds_runtime=dict(min=low,max=high),height_m=high[1]-low[1])


def conveyor_envelope(data, parent, mats):
    root=group("CONVEYOR__ENGINEERING_ENVELOPES",parent)
    for m in data["physical_modules"]:
        if m["family"]!="turn":
            lo,hi=m["floor_bounds_xz"]["min"],m["floor_bounds_xz"]["max"]
            box(m["module_id"],[(lo[0]+hi[0])/2,m["deck_y"]/2,(lo[1]+hi[1])/2],
                [hi[0]-lo[0],m["deck_y"],hi[1]-lo[1]],mats["belt"],root,0)
        else:
            cx,_,cz=m["origin"];outer=m["radius_m"]+.45;inner=m["radius_m"]-.45
            points=[]
            for y in [0,m["deck_y"]]:
                for radius in [inner,outer]:
                    for i in range(m["quarter_facets"]+1):
                        t=m["theta_start_rad"]+(m["theta_end_rad"]-m["theta_start_rad"])*i/m["quarter_facets"]
                        points.append([cx+radius*math.cos(t),y,cz+radius*math.sin(t)])
            n=m["quarter_facets"]+1;faces=[]
            for i in range(n-1):
                faces.extend([(i,i+1,n+i+1,n+i),
                              (2*n+i,3*n+i,3*n+i+1,2*n+i+1),
                              (i,2*n+i,2*n+i+1,i+1),
                              (n+i,n+i+1,3*n+i+1,3*n+i)])
            faces.extend([(0,n,3*n,2*n),(n-1,3*n-1,4*n-1,2*n-1)])
            mesh(m["module_id"],points,faces,mats["belt"],root)
    for station in data["packing_stations"]:
        x,_,z=station["table_origin"];w,h,d=station["table_dimensions_m"];opening=station["central_clear_opening_width_m"]
        side=(w-opening)/2
        for sign in [-1,1]:
            box(station["pack_id"]+"__side",[x+sign*(opening/2+side/2),h/2,z],
                [side,h,d],mats["pack"],root,0)
        cut=station["worktop_cutout_local_z"][1]
        box(station["pack_id"]+"__bridge",[x,h/2,z+(cut+d/2)/2],
            [opening,h,d/2-cut],mats["pack"],root,0)


def build():
    sources={p:read(p) for p in INPUTS}
    layout=sources[INPUTS[1]]
    root=group("LAYOUT_ENGINEERING_ROOT")
    root["role"],root["engineering_preview"],root["final_art"]= "engineering_layout_preview",True,False
    root["inventory_units_created"],root["module_count"],root["address_count"]=0,len(layout["modules"]),len(layout["slots"])
    root["floor_dimensions_m"]=[144,72]
    root["building_height_m"]=8
    root["floor_origin_meaning"]="Minimum floor corner; not a centred asset wrapper."
    root["source_fingerprints_json"]=json.dumps({p:sha(ROOT/p) for p in INPUTS})
    mats={k:material("ENG__"+k,c,.95) for k,c in {
        "floor":"#E3E4DF","ink":"#263E48","SMALL":"#7EC8B7",
        "STANDARD":"#8DB7D8","HEAVY":"#AF9CC8","LONG":"#D3AD68",
        "FLEX":"#D0A0B5","reserve":"#A8B7C2","clear":"#D4DAD9",
        "incoming":"#9B59D0","outgoing":"#2AA56A","belt":"#2E7376",
        "pack":"#C99A60","ped":"#39769C","vehicle":"#CA9235",
        "buffer":"#BC8A53","scale":"#F4C542"}.items()}
    mats["labels"]=group("ENGINEERING_LABELS",root)
    mesh("FLOOR__144x72m",[[0,0,0],[144,0,0],[144,0,72],[0,0,72]],[(0,3,2,1)],mats["floor"],root)
    zones=group("ZONES__EXACT_FOOTPRINTS",root)
    for z in sources[INPUTS[0]]["zones"]:
        if z["kind"]=="circulation":
            continue
        lo,hi=z["floor_bounds_xz_m"]["min"],z["floor_bounds_xz_m"]["max"]
        color=mats.get(z.get("storage_type"),mats["reserve"] if z["kind"]=="reserve" else mats["buffer"])
        # Colour is engineering floor paint, not cargo or an extra storage slab.
        mesh("ZONE__"+z["zone_id"],[[lo[0],.001,lo[1]],[hi[0],.001,lo[1]],[hi[0],.001,hi[1]],[lo[0],.001,hi[1]]],[(0,3,2,1)],color,zones)
    modules=group("MODULES__132_BOUNDING_VOLUMES",root)
    for m in layout["modules"]:
        g=group("MODULE__"+m["module_id"],modules)
        g["module_id"],g["zone_id"],g["family"]=m["module_id"],m["zone_id"],m["family"]
        g["engineering_volume_not_final_rack"]=True
        b=m["outer_bounds_world"];lo,hi=b["min"],b["max"]
        g["expected_bounds_runtime_json"]=json.dumps(b)
        color=mats["reserve"] if m["zone_id"].startswith("RESERVE") else mats[m["family"]]
        box("VOLUME__"+m["module_id"],[(lo[i]+hi[i])/2 for i in range(3)],
            [hi[i]-lo[i] for i in range(3)],color,g,0)
    # Mark the actual building height without adding enclosing walls or a roof.
    for x,z in [(.15,.15),(143.85,.15),(143.85,71.85),(.15,71.85)]:
        box("HEIGHT__8m",[x,4,z],[.12,8,.12],mats["ink"],root,0)
    for a,b in [([.15,8,.15],[143.85,8,.15]),([143.85,8,.15],[143.85,8,71.85]),
                ([143.85,8,71.85],[.15,8,71.85]),([.15,8,71.85],[.15,8,.15])]:
        # Thin roof-height line stays below/equalY8 and within the floor bounds.
        stroke("HEIGHT__upper_outline",a[::2],b[::2],.04,8,mats["ink"],root)
    gates=group("PORTS__SIX_CLEAR_APERTURES",root)
    ports=[p for path in INPUTS[2:4] for p in sources[path]["ports"]]
    for p in ports:
        gate(p,gates,mats)
    buffers=group("BUFFERS__FINITE_MARKED_AREAS",root)
    for p in ports:
        for allocation in p["finite_buffer_capacity"]["allocations"]:
            z=next(z for z in sources[INPUTS[0]]["zones"] if z["zone_id"]==allocation["zone_id"])
            lo,hi=z["floor_bounds_xz_m"]["min"],z["floor_bounds_xz_m"]["max"]
            outline("BUFFER__"+z["zone_id"],lo,hi,.012,.08,mats["buffer"],buffers)
        for cell in p["finite_buffer_capacity"].get("buffer_cells",[]):
            b=cell["floor_bounds_xz_m"];outline("CELL__"+cell["cell_id"],b["min"],b["max"],.015,.035,mats["ink"],buffers)
    paths=group("ROUTES__ENGINEERING_FLOOR_OVERLAYS",root)
    seen=set()
    def path_line(a,b,color,width,y):
        key=tuple(sorted((tuple(round(v,5) for v in a),tuple(round(v,5) for v in b))))+(color.name,)
        if key not in seen:
            seen.add(key);stroke("ROUTE",a,b,width,y,color,paths)
    ped=sources[INPUTS[4]];pn={n["node_id"]:n["world_pos"] for n in ped["nodes"]}
    for e in ped["edges"]:
        path_line(pn[e["from_node_id"]][::2],pn[e["to_node_id"]][::2],mats["ped"],.07,.02)
    vehicle=sources[INPUTS[5]]
    for e in vehicle["edges"]:
        if e.get("reverse_of_edge_id"):continue
        points=[[p[5],p[6]] for p in e["pose_samples"]]
        for a,b in zip(points,points[1:]):path_line(a,b,mats["vehicle"],.055,.022)
    for p in layout["local_access_paths"]:
        if p["mode"]=="manual_cart":
            for a,b in zip(p["points_world_xz_m"],p["points_world_xz_m"][1:]):
                path_line(a,b,mats["ped"],.025,.024)
        elif p["mode"]=="forklift":
            for segment in p["segments"]:
                count=18 if segment["kind"]!="line" else 1;points=[]
                for i in range(count+1):
                    u=i/count;theta=segment["start_yaw_rad"]+(segment["end_yaw_rad"]-segment["start_yaw_rad"])*u
                    if segment["kind"]=="line":
                        a,b=segment["front_axle_start_xz_m"],segment["front_axle_end_xz_m"]
                        points.append([a[k]+u*(b[k]-a[k]) for k in [0,1]])
                    else:
                        c=segment["icr_world_xz_m"];q=segment["icr_vehicle_local_x_m"]
                        points.append([c[0]-q*math.cos(theta),c[1]+q*math.sin(theta)])
                for a,b in zip(points,points[1:]):path_line(a,b,mats["vehicle"],.025,.026)
    conveyor_envelope(sources[INPUTS[6]],root,mats)
    counts={}
    for s in layout["slots"]:counts[s["zone_id"]]=counts.get(s["zone_id"],0)+1
    for zid,count in counts.items():
        zone=next(z for z in sources[INPUTS[0]]["zones"] if z["zone_id"]==zid);lo,hi=zone["floor_bounds_xz_m"].values()
        x,z=(lo[0]+hi[0])/2,(lo[1]+hi[1])/2
        if zid.startswith("SMALL"):z=49
        elif zid.startswith("STANDARD"):z=50.5
        elif zid.startswith("HEAVY"):z=25.7
        elif zid.startswith("LONG"):z=30.5
        elif zid.startswith("FLEX"):z=13.6
        elif zid.startswith("RESERVE"):z=59.7
        size = .65 if zid.startswith("FLEX") else .80 if zid.startswith("RESERVE") else 1.20
        label(zid+f" / {count}",[x,.03,z],size,mats["ink"],mats["labels"])
    label("ENGINEERING / 132 MODULES / ZERO INVENTORY",[72,.03,69],1.6,mats["ink"],mats["labels"])
    label("144 m x 72 m / HEIGHT 8 m",[72,.03,71.1],.7,mats["ink"],mats["labels"])
    witness=append_witness(root,mats["scale"])
    root["frozen_worker_witness_json"]=json.dumps(witness)
    return root,witness,sources


def main():
    if not bpy.app.background:
        raise RuntimeError("Never run engineering build in live Blender")
    PREVIEWS.mkdir(parents=True,exist_ok=True)
    reset()
    root,witness,sources=build()
    with (PREVIEWS/"build.log").open("w",encoding="utf-8") as log, contextlib.redirect_stdout(log):
        report=finish(ASSET,root)
    evidence=dict(task_id="L10",status="ACTIVE",root_review="pending",preview_kind="engineering_volumes_not_final_art",
                  asset_stats={k:report[k] for k in ["asset_id","namespace","layout_version","generated_at",
                      "glb","source","glb_bytes","sha256","source_meshes","runtime_meshes","triangles",
                      "bounds_runtime","runtime_size","root_matrix_blender"]},
                  full_stats_path="assets/v3/blender/layout-engineering.stats.json",worker_witness=witness,
                  counts=dict(module_volumes=len(sources[INPUTS[1]]["modules"]),addresses=len(sources[INPUTS[1]]["slots"]),
                              ports=sum(len(sources[p]["ports"]) for p in INPUTS[2:4]),
                              conveyor_modules=len(sources[INPUTS[6]]["physical_modules"]),
                              packing_stations=len(sources[INPUTS[6]]["packing_stations"]),inventory_units=0),
                  read_only_input_fingerprints=[dict(path=p,sha256=sha(ROOT/p)) for p in INPUTS],
                  source_worker_unchanged=sha(WITNESS)==witness["sha256"],
                  render_review="pending queued renders and root actual browser review",
                  scope="New engineering BLEND/GLB only; no main graph/frontend/backend/active-worker mutation.")
    (ROOT/"docs/adaptive-v3/evidence/L10.json").write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8")
    print("L10_ENGINEERING_EXPORTED "+json.dumps({k:report[k] for k in ["glb","glb_bytes","sha256","triangles","bounds_runtime","runtime_size"]}))


if __name__=="__main__":
    main()
