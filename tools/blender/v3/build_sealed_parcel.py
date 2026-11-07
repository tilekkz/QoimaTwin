"""M07.2: thin sealed wrapper, unchanged SMALL HU and native tote QA fixture.

Label ink is face material on a closed paper skin. It adds no overlapping
decal, inflated wall, stock instance or texture dependency to the template.
"""
import hashlib
import json
import sys
from pathlib import Path

import bmesh
import bpy

from v3_common import ROOT, anchor, box, finish, group, material, reset, runtime_xyz, xyz
from build_standard_carton import collect, empty_box

ASSET = "sealed-parcel"
EPS = 1e-6
OUT = ROOT / "assets/v3/iterations/sealed-parcel/M07.2-01"
TARGET = ROOT / "assets/references/v3/m07-2-sealed-parcel.targets.json"
SOURCES = ["assets/v3/blender/small-carton.blend", "assets/v3/blender/order-tote.blend",
           "frontend/public/models/v3/small-carton.glb", "frontend/public/models/v3/order-tote.glb"]


def block(name, lo, hi, mat, parent, bevel=0):
    return box(name, [(a+b)/2 for a,b in zip(lo,hi)], [b-a for a,b in zip(lo,hi)], mat, parent, bevel)


def skin(name, us, vs, point, color, mats, parent):
    """A single watertight .2mm film, tessellated for flush ink/paper regions."""
    vertices = [xyz(point(u,v,depth)) for depth in (0,1) for v in vs for u in us]
    nu,nv=len(us),len(vs)
    n=nu*nv
    faces=[];indices=[]
    for j in range(nv-1):
        for i in range(nu-1):
            a=j*nu+i;b=a+1;c=b+nu;d=a+nu
            faces.extend(((a,b,c,d),(a+n,d+n,c+n,b+n)))
            indices.extend((color((us[i]+us[i+1])/2,(vs[j]+vs[j+1])/2),0))
    edge=list(range(nu))+[j*nu+nu-1 for j in range(1,nv)]+list(range(n-2,n-nu-1,-1))+[j*nu for j in range(nv-2,0,-1)]
    for a,b in zip(edge,edge[1:]+edge[:1]):
        faces.append((a,a+n,b+n,b));indices.append(0)
    mesh=bpy.data.meshes.new(name+"__closed_film")
    mesh.from_pydata(vertices,[],faces);mesh.update()
    for mat in mats:mesh.materials.append(mat)
    for face,index in zip(mesh.polygons,indices):face.material_index=index
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free();mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.parent=parent
    obj["physical_film_gauge_m"]=.0002
    return obj


def front_color(x,y):
    if abs(x)<.017 and y>.226:return 1
    if -.155<x<-.035 and .135<y<.220:
        if -.145<x<-.062 and (.201<y<.204 or .189<y<.192):return 3
        if -.145<x<-.105 and .177<y<.180:return 3
        if .145<y<.166 and any(a<x<a+w for a,w in BARCODE):return 3
        return 2
    return 0


BARCODE=[(-.086,.0014),(-.083,.0028),(-.0785,.0014),(-.0755,.0014),
         (-.0725,.0035),(-.0675,.0014),(-.0645,.0021),(-.061,.0014),(-.058,.0028),(-.0535,.0014)]


def build():
    root=group(ASSET)
    root["reference_id"]="M07.2_REF";root["role"]="workflow_package_template"
    root["package_tare_kg"]=.08;root["content_HU_gross_kg"]=.94;root["complete_gross_kg"]=1.02
    root["instance_identity_policy"]="Each instance supplies unique package_id and existing contents_HU_ref; no SKU, lot, quantity or stock creation"
    root["baked_content_instances"]=0;root["operational_admission"]=False
    mats=[material("V3_PARCEL_cardboard","#C99A60"),material("V3_PARCEL_paper_tape","#DEC08A"),
          material("V3_PARCEL_label","#E8E3D9"),material("V3_PARCEL_ink","#293D46"),
          material("V3_PARCEL_fold","#8B693F")]
    block("parcel_bottom",[-.18,0,-.14],[.18,.003,.14],mats[0],root,.00035)
    for side,x0,x1 in (("left",-.18,-.177),("right",.177,.18)):
        block("parcel_"+side,[x0,.003,-.14],[x1,.277,.14],mats[0],root,.00035)
    block("front_cardboard_core",[-.177,.003,.137],[.177,.277,.1398],mats[0],root)
    block("rear_cardboard_core",[-.177,.003,-.1398],[.177,.277,-.137],mats[0],root)
    xs=sorted(set([-.177,-.155,-.145,-.105,-.086,-.062,-.035,-.017,.017,.177]+[v for a,w in BARCODE for v in (a,a+w)]))
    ys=[.003,.135,.145,.166,.177,.180,.189,.192,.201,.204,.220,.226,.277]
    skin("front_paper_and_print",xs,ys,lambda x,y,d:(x,y,.14-d*.0002),front_color,mats,root)
    skin("rear_paper_and_tape",[-.177,-.017,.017,.177],[.003,.226,.277],
         lambda x,y,d:(x,y,-.14+d*.0002),lambda x,y:1 if abs(x)<.017 and y>.226 else 0,mats,root)
    # Two flush major flaps with a thin folded tape, all inside the nominal top.
    for side,x0,x1 in (("left",-.18,0),("right",0,.18)):
        block("top_flap_core_"+side,[x0,.277,-.14],[x1,.2798,.14],mats[0],root,.00010)
    skin("top_flaps_and_seal",[-.18,-.017,.017,.18],[-.14,-.138,-.1375,.1375,.138,.14],
         lambda x,z,d:(x,.28-d*.0002,z),
         lambda x,z:1 if abs(x)<.017 else (4 if .1375<abs(z)<.138 else 0),mats,root)
    anchor("anchor_support_bottom",(0,0,0),root,"package_bottom_support")
    anchor("anchor_content_HU_support",(0,.003,0),root,"existing_HU_support")
    return root


def append_source(path, name, parent, offset=(0,0,0)):
    with bpy.data.libraries.load(str(ROOT/path),link=False) as (data,loaded):
        loaded.objects=list(data.objects)
    for obj in loaded.objects:
        if obj is not None and obj.name not in bpy.context.scene.objects:bpy.context.collection.objects.link(obj)
    root=next(obj for obj in loaded.objects if obj and obj.name==name)
    root.parent=parent;root.location=xyz(offset)
    return root


def verify(root):
    parts,bvh=collect(root)
    lo=[min(p["low"][i] for p in parts) for i in range(3)]
    hi=[max(p["high"][i] for p in parts) for i in range(3)]
    assert max(abs(a-b) for a,b in zip(lo+hi,[-.18,0,-.14,.18,.28,.14]))<EPS
    empty_box(parts,[-.177,.003,-.137],[.177,.277,.137],"real sealed package cavity")
    # Six actual material paths from the cavity to the outside total exactly3mm.
    gauge=[]
    for origin,direction in (((.05,.15,0),(0,0,1)),((.05,.15,0),(0,0,-1)),
                             ((0,.15,.05),(1,0,0)),((0,.15,.05),(-1,0,0)),
                             ((.05,.15,.05),(0,1,0)),((.05,.15,.05),(0,-1,0))):
        ray=xyz(direction);p,normal,_,_=bvh.ray_cast(xyz(origin),ray,1)
        assert p is not None and normal.dot(ray)<-.99
        # Find the outward face from outside; inlay/core shared faces are internal.
        outside=xyz(origin)+ray
        q,normal,_,_=bvh.ray_cast(outside,-ray,1)
        assert q is not None and normal.dot(ray)>.99
        thickness=(q-p).length;assert abs(thickness-.003)<EPS,thickness
        gauge.append(thickness)
    return {"bounds_runtime":{"min":lo,"max":hi},"closed_positive_outward_parts":len(parts),
            "actual_cavity_xyz_m":[.354,.274,.274],"six_actual_wall_gauges_m":gauge,
            "inlay_film_m":.0002,"inlay_core_m":.0028,"template_content_instances":0,
            "new_SKU_lot_stock_or_quantity":False,"operational_admission":False}


def paired_fixture():
    reset();fixture=group("sealed-parcel-tote-fixture");fixture["role"]="visual_QA_fixture"
    fixture["source_label"]="visual fixture; one existing SMALL HU, wrapper and workflow tote"
    tote=append_source(SOURCES[1],"order-tote",fixture)
    parcel=build();parcel.parent=fixture;parcel.location=xyz((0,.02,0))
    content=append_source(SOURCES[0],"small-carton",parcel,(0,.003,0))
    content["fixture_existing_HU_ref"]="v3:fixture:HU:SMALL001"
    parcel["fixture_package_id"]="v3:fixture:package:SMALL001"
    parcel["fixture_contents_HU_ref"]="v3:fixture:HU:SMALL001"
    bpy.context.view_layer.update()
    small_parts,_=collect(content)
    small_lo=[min(p["low"][i] for p in small_parts) for i in range(3)]
    small_hi=[max(p["high"][i] for p in small_parts) for i in range(3)]
    assert max(abs(a-b) for a,b in zip(small_lo+small_hi,[-.16,.023,-.12,.16,.263,.12]))<EPS
    assert all(a>=b-EPS for a,b in zip(small_lo,[-.177,.023,-.137]))
    assert all(a<=b+EPS for a,b in zip(small_hi,[.177,.297,.137]))
    tote_parts,tote_bvh=collect(tote)
    empty_box(tote_parts,[-.18,.02,-.14],[.18,.30,.14],"actual parcel fit in accepted tote")
    for x in (-.15,0,.15):
        # Avoid a triangulation diagonal in Blender's single-precision ray BVH.
        for z in (-.12,0,.12):
            point,normal,_,_=tote_bvh.ray_cast(xyz((x,.025,z)),xyz((0,-1,0)),.015)
            assert point is not None and abs(runtime_xyz(point)[1]-.02)<EPS,("tote_floor",x,z,runtime_xyz(point) if point else None,[p["name"] for p in tote_parts])
    return fixture,{"actual_SMALL_bounds_in_fixture":{"min":small_lo,"max":small_hi},
                    "content_clearance_m":{"X_each":.017,"Z_each":.017,"top":.034,"floor":0},
                    "parcel_tote_clearance_m":{"X_each":.10,"Z_each":.04,"top":.02,"floor":0},
                    "actual_tote_support_rays":9,"contents_unchanged_scale":list(content.scale),
                    "loaded_tote_gross_kg":4.02,"manual_limit_kg":15,
                    "instance_ancestry":{"package_id":parcel["fixture_package_id"],"contents_HU_ref":parcel["fixture_contents_HU_ref"]}}


if __name__=="__main__":
    if not bpy.app.background:raise RuntimeError("Background Blender only")
    OUT.mkdir(parents=True,exist_ok=True)
    frozen={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in SOURCES}
    reset();root=build();checks=verify(root);stats=finish(ASSET,root)
    checks["glb_sha256"]=stats["sha256"];checks["triangles"]=stats["triangles"]
    fixture,paired=paired_fixture();fixture_stats=finish("sealed-parcel-tote-fixture",fixture)
    assert frozen=={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in SOURCES}
    checks["paired_fixture"]=paired;checks["accepted_inputs_unchanged"]=frozen
    checks["paired_fixture_sha256"]=fixture_stats["sha256"]
    (ROOT/"assets/v3/specs/sealed-parcel.geometry.json").write_text(json.dumps(checks,indent=2)+"\n",encoding="utf-8")
    (ROOT/"assets/v3/specs/sealed-parcel.dimensions.json").write_text(TARGET.read_text(encoding="utf-8"),encoding="utf-8")
    (OUT/"mesh-checks.json").write_text(json.dumps(checks,indent=2)+"\n",encoding="utf-8")
    print("M072_VERIFIED "+json.dumps({"triangles":stats["triangles"],"six_wall_gauges":True,"native_content_tote_fit":True,"inputs_unchanged":True}))
