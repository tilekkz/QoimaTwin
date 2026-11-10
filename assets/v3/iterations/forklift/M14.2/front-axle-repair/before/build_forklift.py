"""Separate accepted body/wheels and M14.3 cab checkpoints.

Background only, via v3/run_build.py. Every location below is parent-local
runtime XYZ metres. The complete vehicle floor-centre origin is retained even
though this partial stage contains no forks or roof.
"""
import json
import math
from pathlib import Path
import argparse
import sys

import bpy
import bmesh

from v3_common import ROOT, anchor, box, cylinder, finish, group, material, pivot, reset, xyz

ASSET_ID = "forklift-body-wheels"
SPEC = ROOT / "assets/v3/specs/forklift.dimensions.json"


def _tag(obj, part, kind):
    obj["source_part_id"] = part
    obj["forklift_component_class"] = kind
    return obj


def _box_bounds(name, lo, hi, mat, parent, bevel=.008, kind="body"):
    return _tag(box(name, [(a+b)/2 for a,b in zip(lo,hi)],
                    [b-a for a,b in zip(lo,hi)], mat, parent, bevel), name, kind)


def _tyre(name, radius, width, inner_radius, mat, parent, segments=24):
    """Closed annular tyre with actual rounded shoulders and a contained hub.

    Six fixed axial/radial profile stations form the bevel; no tread texture or
    floating torus. Theta includes pi, so the authored circular footprint has
    exact floor contact at bind pose. All vertices lie inside L05's cylinder.
    """
    h=width/2
    edge=.025 if radius==.30 else .020
    profile=[(-h,inner_radius),(-h,radius-edge),(-h+edge,radius),
             (h-edge,radius),(h,radius-edge),(h,inner_radius)]
    vertices=[]
    for x,r in profile:
        for j in range(segments):
            angle=2*math.pi*j/segments
            vertices.append(xyz((x,r*math.cos(angle),r*math.sin(angle))))
    faces=[]
    for k in range(len(profile)):
        following=(k+1)%len(profile)
        for j in range(segments):
            next_j=(j+1)%segments
            faces.append((k*segments+j,k*segments+next_j,
                          following*segments+next_j,following*segments+j))
    mesh=bpy.data.meshes.new(name+"__editable_annular_mesh")
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent=parent
    mesh.materials.append(mat)
    _tag(obj,name,"tyre")
    obj["radius_m"]=radius
    obj["tyre_width_m"]=width
    obj["inner_radius_m"]=inner_radius
    obj["radial_segments"]=segments
    obj["continuous_cylinder_bound"]=True
    return obj


def _counterweight(mat,parent):
    # A tapered cast mass, rather than a cuboid that reads as a shipping box.
    # Every ring stays inside the accepted counterweight envelope.
    rings=[(.50,.35,-1.44,-.99),(.58,.46,-1.50,-.93),
           (.82,.46,-1.50,-.93),(.86,.44,-1.48,-.95)]
    points=[]
    for y,half,z0,z1 in rings:
        c=.04
        outline=[(-half+c,z0),(half-c,z0),(half,z0+c),(half,z1-c),
                 (half-c,z1),(-half+c,z1),(-half,z1-c),(-half,z0+c)]
        points.extend(xyz((x,y,z)) for x,z in outline)
    faces=[tuple(range(8))]
    for k in range(len(rings)-1):
        for j in range(8):
            n=(j+1)%8
            faces.append((k*8+j,(k+1)*8+j,(k+1)*8+n,k*8+n))
    faces.append(tuple(reversed(range(24,32))))
    mesh=bpy.data.meshes.new("counterweight_body__editable_tapered_mesh")
    mesh.from_pydata(points,[],faces)
    mesh.update()
    obj=bpy.data.objects.new("counterweight_body",mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent=parent
    mesh.materials.append(mat)
    _tag(obj,obj.name,"body")
    return obj


def _wheel(data, root, mats):
    name=data["id"]
    centre=data["centre"]
    if name.startswith("rear"):
        side=name[-1]
        steering=pivot("joint__rear_steer_"+side,centre,root,"Y")
        steering["max_abs_steer_deg"]=75
        steering["bind_world_runtime"]=centre
        spin=pivot("joint__wheel_"+name,(0,0,0),steering,"X")
    else:
        spin=pivot("joint__wheel_"+name,centre,root,"X")
    spin["bind_world_runtime"]=centre
    spin["wheel_radius_m"]=data["radius"]
    spin["positive_spin_rule"]="runtime X; signed rolling follows physical forward/reverse motion"
    radius,width=data["radius"],data["width"]
    inner=.135 if name.startswith("front") else .095
    _tyre("tyre_"+name,radius,width,inner,mats["rubber"],spin)
    hub_radius=inner+.015
    hub=cylinder("hub_"+name,(0,0,0),hub_radius,width-.008,
                 mats["tan"],spin,axis="X",vertices=24)
    _tag(hub,"hub_"+name,"hub")
    sign=-1 if name.endswith("L") else 1
    cap=cylinder("hub_centre_"+name,(sign*(width/2-.0025),0,0),
                 .055 if name.startswith("front") else .040,.004,
                 mats["steel"],spin,axis="X",vertices=16)
    _tag(cap,"hub_centre_"+name,"hub_cap")
    return spin


def build_body_wheels():
    plan=json.loads(SPEC.read_text(encoding="utf-8"))
    root=group("forklift_root")
    root["asset_id"]=ASSET_ID
    root["stage"]="M14.2_body_wheels_only"
    root["complete_forklift"]=False
    root["preserve_articulation"]=True
    root["reference_id"]="M14.2-REACH"
    root["numeric_authority"]="M14.1 / C08v0.2"
    root["complete_vehicle_dimensions_xyz_m"]=[1.2,2.1,3.0]
    root["staged_expected_dimensions_xyz_m"]=[1.2,.92,2.2]
    root["origin_description"]="floor centre of FULL travel footprint, unchanged for partial stage"
    root["future_children"]="cab/seat/guard; mast/reach/forks; complete GLB; pickup/setdown action"
    mats={k:material(v["name"],v["color"],.85,0) for k,v in plan["materials"].items()}
    selected={"chassis_rear_spine","chassis_front_spine","driver_floorboard",
              "entry_step_L","entry_step_R","petrol_nose"}
    for part in plan["blueprint_boxes"]:
        if part["name"] in selected:
            _box_bounds(part["name"],part["min"],part["max"],mats[part["material"]],root,
                        .006 if "spine" in part["name"] else .010)
    # A stepped substantial counterweight stays inside the accepted envelope.
    # The two volumes overlap by20mm; no coplanar overlay, detached cap or decal.
    _counterweight(mats["tan"],root)
    _box_bounds("counterweight_upper_step",[-.42,.84,-1.425],[.42,.92,-.935],mats["tan"],root,.010)
    # Approved fixed front-axle support chain, below the moving plate or behind
    # it. These parts do not occupy the high/extended-low reach sweep.
    _box_bounds("low_forward_spine",[-.10,.04,-.10],[.10,.09,.45],mats["steel"],root,.003,"axle_support")
    _box_bounds("rear_drop_connection",[-.10,.08,-.15],[.10,.20,-.07],mats["petrol"],root,.004,"axle_support")
    _box_bounds("front_axle_saddle",[-.15,.08,.32],[.15,.36,.48],mats["steel"],root,.007,"axle_support")
    for axle,y,z,r in (("front",.30,.40,.050),("rear",.225,-1.00,.035)):
        obj=cylinder("axle_"+axle,(0,y,z),r,.70,mats["steel"],root,axis="X",vertices=16)
        _tag(obj,"axle_"+axle,"axle")
    for data in plan["wheels"]:
        _wheel(data,root,mats)
    return root


def _tube(name,start,end,radius,mat,parent,kind="control"):
    delta=xyz([b-a for a,b in zip(start,end)])
    obj=cylinder(name,[(a+b)/2 for a,b in zip(start,end)],radius,
                 delta.length,mat,parent,axis="Y",vertices=24)
    obj.rotation_mode="QUATERNION"
    obj.rotation_quaternion=delta.to_track_quat("Z","Y")
    return _tag(obj,name,kind)


def _conceal_column_base(obj,max_z=-.045):
    # Only remove material inside the declared capsule. Its nominal lower
    # axis point lies ahead of the nose; a closed oblique cut conceals that
    # protrusion and leaves the future rear lift-plate corridor empty.
    bpy.context.view_layer.update()
    transform=obj.matrix_local.copy()
    plane=transform.inverted()@xyz((0,0,max_z))
    normal=(transform.to_3x3().transposed()@xyz((0,0,1))).normalized()
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                          plane_co=plane,plane_no=normal,dist=1e-7,clear_outer=True)
    bmesh.ops.holes_fill(bm,edges=[e for e in bm.edges if e.is_boundary],sides=0)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(obj.data);bm.free();obj.data.update()
    obj["concealed_base_max_runtime_z"]=max_z


def _steering_rim(mat,parent,axis,radius=.14,tube=.012):
    # A readable circular wheel around the accepted hub. The diametric yoke
    # acts as connected spokes while unchanged outer grip shafts retain fit.
    from mathutils import Vector
    normal=Vector(axis).normalized()
    u=Vector((1,0,0));v=normal.cross(u).normalized()
    vertices=[]
    major,minor=20,8
    for i in range(major):
        theta=2*math.pi*i/major
        radial=u*math.cos(theta)+v*math.sin(theta)
        centre=radial*radius
        for j in range(minor):
            phi=2*math.pi*j/minor
            vertices.append(xyz(centre+radial*(tube*math.cos(phi))+normal*(tube*math.sin(phi))))
    faces=[]
    for i in range(major):
        for j in range(minor):
            ni,nj=(i+1)%major,(j+1)%minor
            faces.append((i*minor+j,ni*minor+j,ni*minor+nj,i*minor+nj))
    mesh=bpy.data.meshes.new("steering_rim__editable_closed_tube")
    mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new("steering_rim",mesh)
    bpy.context.collection.objects.link(obj);obj.parent=parent;mesh.materials.append(mat)
    _tag(obj,obj.name,"control")
    obj["major_radius_m"]=radius;obj["tube_radius_m"]=tube
    return obj


def build_cab():
    plan=json.loads(SPEC.read_text(encoding="utf-8"))
    frozen=json.loads((ROOT/"assets/v3/iterations/forklift/M14.1/actual-blueprint-checks.json").read_text(encoding="utf-8"))
    root=build_body_wheels()
    root["asset_id"]="forklift-cab-stage"
    root["stage"]="M14.3_body_and_cab_no_mast"
    root["staged_expected_dimensions_xyz_m"]=[1.2,2.1,2.2]
    root["future_children"]="mast/reach/forks; complete GLB; pickup/setdown action"
    mats={k:material(v["name"],v["color"],.85,0) for k,v in plan["materials"].items()}
    for part in plan["blueprint_boxes"]:
        name=part["name"]
        if not name.startswith(("seat_","guard_","roof_")):
            continue
        mat=mats["petrol"] if name.startswith(("guard_","roof_")) else mats[part["material"]]
        bevel=.003 if name.startswith("guard_") or name=="seat_cushion_nose" else .006
        _box_bounds(name,part["min"],part["max"],mat,root,bevel,"cab")
    column=plan["driver"]["steering_column"]
    column_obj=_tube("steering_column",column["start"],column["end"],column["radius_m"],mats["steel"],root)
    _conceal_column_base(column_obj)
    centre=column["end"]
    steering=pivot("joint__steering_wheel",centre,root,"Y")
    axis=[b-a for a,b in zip(column["start"],column["end"])]
    length=math.sqrt(sum(v*v for v in axis));axis=[v/length for v in axis]
    steering["mechanical_axis_runtime"]=axis
    steering["control_shape"]="connected yoke fitting frozen hand-channel axes"
    _tube("steering_hub",[-v*.020 for v in axis],[v*.020 for v in axis],.045,mats["steel"],steering)
    y=1.285783894374534-centre[1]
    z=-.2582260170000707-centre[2]
    _tube("steering_yoke_crossbar",[-.215,y,z],[.215,y,z],.014,mats["steel"],steering)
    _steering_rim(mats["steel"],steering,axis)
    for grip in frozen["actualDriver"]["grips"]:
        local=[a-b for a,b in zip(grip["centre"],centre)]
        start=[p-a*.040 for p,a in zip(local,grip["axis"])]
        end=[p+a*.040 for p,a in zip(local,grip["axis"])]
        _tube("steering_grip_"+grip["side"],start,end,.018,mats["rubber"],steering)
    current={"forklift_root":root,"joint__steering_wheel":steering}
    for name in ("anchor_floor_origin","anchor_front_axle","anchor_rear_axle","anchor_driver_seat",
                 "anchor_footrest_L","anchor_footrest_R","anchor_steering_grip_L","anchor_steering_grip_R"):
        parent=current[plan["anchor_parents"][name]]
        parent_world=centre if parent==steering else [0,0,0]
        local=[a-b for a,b in zip(plan["anchors"][name],parent_world)]
        anchor(name,local,parent,"driver_contact" if "driver" in name or "grip" in name or "footrest" in name else "vehicle_reference")
    return root


def build(stage="body-wheels"):
    if stage=="body-wheels":
        return build_body_wheels()
    if stage=="cab":
        return build_cab()
    raise ValueError("Only body-wheels and cab stages are implemented")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--stage",choices=["body-wheels","cab"],default="body-wheels")
    arguments=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    args=parser.parse_args(arguments)
    reset()
    finish(ASSET_ID if args.stage=="body-wheels" else "forklift-cab-stage",build(args.stage),batch_runtime=True)
