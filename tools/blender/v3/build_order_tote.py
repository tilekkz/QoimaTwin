"""M07.1 workflow tote: metric cavity, true handles, ribbed skin; no stock.

Pure evaluated-mesh QA is reused read-only from the accepted carton builder;
no carton geometry, Blender source or GLB is imported/scaled.
"""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import sys

import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT, anchor, box, finish, group, material, reset, runtime_xyz, xyz
from build_standard_carton import collect, empty_box

ASSET="order-tote"
ITER=ROOT/"assets/v3/iterations/order-tote/M07.1-01"
METRICS=ROOT/"assets/v3/specs/order-tote.geometry.json"
EPS=1e-6
INPUTS=["assets/references/v3/m07-1-order-tote.png","assets/references/v3/m07-1-order-tote.targets.json",
        "assets/v3/specs/order-tote.dimensions.json","assets/references/v3/provenance/r11.json",
        "docs/v3/contract-proposals/cargo-catalog-v3.json","tools/blender/v3/build_standard_carton.py"]


def bindings():
    return [{"path":p,"sha256":hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in INPUTS]


def block(name,lo,hi,mat,parent,bevel=.0008):
    return box(name,[(a+b)/2 for a,b in zip(lo,hi)],[b-a for a,b in zip(lo,hi)],mat,parent,bevel)


def build():
    root=group(ASSET);root["reference_id"]="M07.1_REF";root["role"]="workflow_container_template"
    root["not_SKU_stock_or_lot"]=True;root["tare_kg"]=3.;root["payload_limit_kg"]=12.;root["manual_loaded_gross_limit_kg"]=15.
    root["operational_admission"]=False;root["source_bindings_json"]=json.dumps(bindings(),sort_keys=True)
    teal=material("V3_TOTE_petrol","#2E7376");floor=material("V3_TOTE_floor","#3E8280")
    block("floor_skin",(-.30,.016,-.20),(.30,.02,.20),floor,root,.0005)
    # Supported ribs/perimeter set the real floor origin; inside support is .02.
    for tag,lo,hi in (("front",(-.30,0,.183),(.30,.016,.20)),("rear",(-.30,0,-.20),(.30,.016,-.183)),
                      ("left",(-.30,0,-.183),(-.283,.016,.183)),("right",(.283,0,-.183),(.30,.016,.183))):
        block("base_"+tag,lo,hi,teal,root)
    for i,x in enumerate((-.20,0,.20)):
        block(f"underside_rib_{i}",(x-.005,0,-.183),(x+.005,.016,.183),teal,root)
    # Long skin is .003 thick; upper centre is genuinely absent for the handle.
    for tag,z0,z1 in (("front",.18,.183),("rear",-.183,-.18)):
        block("skin_"+tag,(-.28,.02,z0),(.28,.26,z1),teal,root,.0004)
        for n,a,b in (("left",-.28,-.09),("right",.09,.28)):
            block(f"skin_{tag}_{n}",(a,.26,z0),(b,.32,z1),teal,root,.0004)
        block("skin_"+tag+"_bridge",(-.09,.31,z0),(.09,.32,z1),teal,root,.0004)
        # External ribs and the 3D handle perimeter all stay outside usableZ.
        out0,out1=(.183,.20) if tag=="front" else (-.20,-.183)
        for i,x in enumerate((-.26,-.12,0,.12,.26)):
            block(f"rib_{tag}_{i}",(x-.006,.02,out0),(x+.006,.26 if x==0 else .32,out1),teal,root)
        for n,lo,hi in (("lower",(-.10,.25,out0),(.10,.26,out1)),("upper",(-.10,.31,out0),(.10,.32,out1)),
                        ("left",(-.10,.26,out0),(-.09,.31,out1)),("right",(.09,.26,out0),(.10,.31,out1))):
            block(f"handle_{tag}_{n}",lo,hi,teal,root)
    for tag,x0,x1 in (("left",-.283,-.28),("right",.28,.283)):
        block("skin_"+tag,(x0,.02,-.18),(x1,.26,.18),teal,root,.0004)
        for n,a,b in (("rear",-.18,-.08),("front",.08,.18)):
            block(f"skin_{tag}_{n}",(x0,.26,a),(x1,.32,b),teal,root,.0004)
        block("skin_"+tag+"_bridge",(x0,.31,-.08),(x1,.32,.08),teal,root,.0004)
        out0,out1=(-.30,-.283) if tag=="left" else (.283,.30)
        for i,z in enumerate((-.12,.12)):
            block(f"rib_{tag}_{i}",(out0,.02,z-.006),(out1,.32,z+.006),teal,root)
        for n,lo,hi in (("lower",(out0,.25,-.09),(out1,.26,.09)),("upper",(out0,.31,-.09),(out1,.32,.09)),
                        ("rear",(out0,.26,-.09),(out1,.31,-.08)),("front",(out0,.26,.08),(out1,.31,.09))):
            block(f"handle_{tag}_{n}",lo,hi,teal,root)
    for ix,x in enumerate((-.29,.29)):
        for iz,z in enumerate((-.19,.19)):
            block(f"corner_{ix}_{iz}",(x-.01,.02,z-.01),(x+.01,.32,z+.01),teal,root)
    for tag,lo,hi in (("front",(-.30,.32,.18),(.30,.34,.20)),("rear",(-.30,.32,-.20),(.30,.34,-.18)),
                      ("left",(-.30,.32,-.18),(-.28,.34,.18)),("right",(.28,.32,-.18),(.30,.34,.18))):
        block("rim_"+tag,lo,hi,teal,root,.001)
    anchor("anchor_bottom",(0,0,0),root,"container_bottom_support")
    anchor("anchor_contents_support",(0,.02,0),root,"contents_bottom_support")
    for tag,p in (("front",(0,.31,.19)),("rear",(0,.31,-.19)),("left",(-.29,.31,0)),("right",(.29,.31,0))):
        anchor("anchor_handle_"+tag,p,root,"candidate_handle_grip")
    return root


def verify(root):
    parts,bvh=collect(root);low=[min(p["low"][i] for p in parts) for i in range(3)];high=[max(p["high"][i] for p in parts) for i in range(3)]
    assert all(abs(a-b)<EPS for a,b in zip(low+high,[-.30,0,-.20,.30,.34,.20]))
    assert all(all(abs(o.scale[i]-1)<EPS for i in range(3)) for o in [root]+list(root.children_recursive))
    empty_box(parts,[-.28,.02,-.18],[.28,.32,.18],"full usable cavity")
    empty_box(parts,[-.18,.02,-.14],[.18,.30,.14],"future .36x.28x.28 parcel envelope")
    for name,lo,hi in (("front",[-.09,.26,.179],[.09,.31,.201]),("rear",[-.09,.26,-.201],[.09,.31,-.179]),
                       ("left",[-.301,.26,-.08],[-.279,.31,.08]),("right",[.279,.26,-.08],[.301,.31,.08])):
        empty_box(parts,lo,hi,"actual open handle "+name)
    # Actual floor and underbase contacts; no hover in the parcel/tote interface.
    for x in (-.15,0,.15):
        for z in (-.12,0,.12):
            p,n,_,_=bvh.ray_cast(xyz((x,.025,z)),xyz((0,-1,0)),.015)
            assert p is not None and abs(runtime_xyz(p)[1]-.02)<EPS and n.dot(xyz((0,1,0)))>.999
    for x in (-.20,0,.20):
        p,n,_,_=bvh.ray_cast(xyz((x,-.01,0)),xyz((0,1,0)),.025)
        assert p is not None and abs(runtime_xyz(p)[1])<EPS
    # Four real 3mm skin thickness samples away from the handles/ribs.
    for origin,axis in (((.05,.15,0),(0,0,1)),((.05,.15,0),(0,0,-1)),((0,.15,.05),(1,0,0)),((0,.15,.05),(-1,0,0))):
        ray=xyz(axis);p,n,_,_=bvh.ray_cast(xyz(origin),ray,.5);assert p is not None and n.dot(ray)<-.999
        q,qn,_,_=bvh.ray_cast(p+ray*.00001,ray,.01);assert q is not None and abs((q-p).length-.003)<EPS and qn.dot(ray)>.999
    # Actual surface contact graph, not just a common parent hierarchy.
    links={p["name"]:set() for p in parts};edges=0
    for i,a in enumerate(parts):
        for b in parts[i+1:]:
            if any(a["high"][j]<b["low"][j]-EPS or b["high"][j]<a["low"][j]-EPS for j in range(3)):continue
            contact=bool(a["bvh"].overlap(b["bvh"]))
            if not contact:
                for samples,target in ((a["samples"],b["bvh"]),(b["samples"],a["bvh"])):
                    if any((n:=target.find_nearest(v))[3] is not None and n[3]<EPS for v in samples):contact=True;break
            if contact:links[a["name"]].add(b["name"]);links[b["name"]].add(a["name"]);edges+=1
    reached={"floor_skin"};frontier=list(reached)
    while frontier:
        for name in links[frontier.pop()]-reached:reached.add(name);frontier.append(name)
    assert reached==set(links),("loose wall/rib",set(links)-reached)
    return {"asset_id":ASSET,"bounds_runtime":{"min":low,"max":high},"closed_positive_outward_parts":len(parts),"actual_surface_contact_edges":edges,
            "all_parts_connected":True,"actual_cavity_clear":[.56,.30,.36],"four_handle_openings_clear":True,"four_actual_skin_thickness_m":.003,
            "parcel_fit":{"dimensions_xyz_m":[.36,.28,.28],"actual_X_each_gap":.10,"actual_Z_each_gap":.04,"top_budget":.02,"bottom_gap":0,"floor_rays_passed":9},
            "STANDARD_HU_fits":False,"STANDARD_reason":".60x.40 exceeds .56x.30 inner width/height; route direct lower tray/belt",
            "actual_source_all_scales_one":True,"tare_kg":3,"payload_limit_kg":12,"manual_gross_limit_kg":15,"sources":bindings(),"operational_admission":False}


if __name__=="__main__":
    if not bpy.app.background:raise RuntimeError("Background only")
    reset();root=build();report=verify(root);ITER.mkdir(parents=True,exist_ok=True)
    stats=finish(ASSET,root)
    # Read-back of editable source and exported PBR in this same CPU build gate.
    source=ROOT/"assets/v3/blender/order-tote.blend";sha=hashlib.sha256(source.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(source));root=bpy.data.objects[ASSET]
    meshes=[o for o in root.children_recursive if o.type=="MESH"];assert len(meshes)==report["closed_positive_outward_parts"] and all(any(m.type=="BEVEL" for m in o.modifiers) for o in meshes)
    raw=(ROOT/"frontend/public/models/v3/order-tote.glb").read_bytes();n=struct.unpack_from("<I",raw,12)[0];g=json.loads(raw[20:20+n])
    for mat in g["materials"]:
        node=next(n for n in bpy.data.materials[mat["name"]].node_tree.nodes if n.type=="BSDF_PRINCIPLED");p=mat["pbrMetallicRoughness"]
        assert max(abs(a-b) for a,b in zip(node.inputs["Base Color"].default_value,p["baseColorFactor"]))<1e-6
        assert abs(node.inputs["Roughness"].default_value-p["roughnessFactor"])<1e-6
    assert sha==hashlib.sha256(source.read_bytes()).hexdigest()
    report["saved_source_editable_bevel_parts"]=len(meshes);report["GLB_material_factors_match_source"]=len(g["materials"])
    report["glb_sha256"]=stats["sha256"];report["triangles"]=stats["triangles"]
    METRICS.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    for p in (source,source.with_suffix(".stats.json"),ROOT/"frontend/public/models/v3/order-tote.glb",METRICS,ROOT/INPUTS[2],Path(__file__)):
        shutil.copy2(p,ITER/p.name)
    print("M071_VERIFIED "+json.dumps({"parts":len(meshes),"tris":stats["triangles"],"cavity":[.56,.30,.36],"handles":4,"sha256":stats["sha256"]}))
