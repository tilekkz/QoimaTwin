"""C02 fixed synthetic eight-HU templates and explicit packing witnesses."""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import validate_cargo_contract as c01

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/"docs/v3/contract-proposals/cargo-catalog-v3.json"
EPS=1e-9
INPUTS=[c01.SCHEMA,Path(c01.__file__),c01.EXAMPLE,c01.TARGETS,c01.MANIFEST,c01.STORAGE]

# Fixed before any optimization. XYZ metres; kg; minimum-HU-corner packing frame.
# unit contents/primary tare, HU count/outer tare, grid and free inner bounds.
PARAMS={
 "SMALL_CARTON":dict(unit=[.06,.04,.04],contents=.03,primary=.005,count=24,outer=.10,pack="carton",grid=[4,2,3],gap=[.005]*3,lo=[.015]*3,hi=[.305,.225,.225],storage=["SMALL","FLEX"],meaning="Individually packed small accessories"),
 "STANDARD_CARTON":dict(unit=[.10,.08,.06],contents=.20,primary=.05,count=24,outer=.35,pack="carton",grid=[4,3,2],gap=[.01]*3,lo=[.02]*3,hi=[.58,.38,.28],storage=["STANDARD","FLEX"],meaning="Individually packed standard goods; same mass/design as C01"),
 "HEAVY_BOX":dict(unit=[.30,.20,.20],contents=22,primary=1,count=8,outer=16,pack="protective_crate",grid=[2,2,2],gap=[.02]*3,lo=[.05,.06,.05],hi=[.75,.60,.55],storage=["HEAVY"],meaning="Dense packaged machinery parts in a reinforced supported box"),
 "PALLET_LOAD":dict(unit=[.36,.26,.28],contents=17.2,primary=.8,count=24,outer=23,pack="palletized",grid=[3,4,2],gap=[.02]*3,lo=[.02,.16,.02],hi=[1.18,1.31,.98],storage=["HEAVY"],meaning="24sealed cartons above an integral pallet and restraints"),
 "IBC":dict(unit=[1.08,1.02,.88],contents=600,primary=14,count=1,outer=40,pack="caged_tank",grid=[1,1,1],gap=[0]*3,lo=[.05,.10,.05],hi=[1.15,1.13,.95],storage=["HEAVY"],meaning="One sealed filled inner bottle; fluid kg/litres are not unit counts",fluid=dict(density_kg_m3=1000,fill_volume_m3=.6,declared_usable_capacity_m3=.65,shape_convention="Synthetic sealed tank fill indicator; no mesh/internal-volume certification")),
 "LONG_BUNDLE":dict(unit=[4,.08,.08],contents=7.8,primary=.2,count=24,outer=8,pack="bundled",grid=[1,4,6],gap=[0,.008,.008],lo=[.08,.06,.05],hi=[4.12,.48,.60],storage=["LONG"],meaning="24rigid hollow profiles, end protection/bands; detachable vehicle cradle excluded"),
 "DRUM":dict(unit=[.60,.82,.60],contents=160,primary=12,count=1,outer=8,pack="drum_on_support",grid=[1,1,1],gap=[0]*3,lo=[.03,.08,.03],hi=[.65,.92,.65],storage=["HEAVY"],meaning="One sealed primary drum on integral restraint/support; not160unit boxes",fluid=dict(density_kg_m3=1000,fill_volume_m3=.16,declared_usable_capacity_m3=.18,shape_convention="Synthetic sealed drum fill indicator; no mesh/internal-volume certification")),
 "FRAGILE_CRATE":dict(unit=[.90,.70,.65],contents=68,primary=5,count=1,outer=15,pack="protective_crate",grid=[1,1,1],gap=[0]*3,lo=[.08,.10,.08],hi=[1.02,.86,.77],storage=["STANDARD"],meaning="One primary-packaged instrument inside a cushioned outer crate",fragile=True),
}


def number(value):return Decimal(str(value))
def total(*values):return float(sum(number(v) for v in values))
def volume(dims):return float(math.prod(number(v) for v in dims))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def encoded(value):return (json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode()


def make_record(aid,target,layout):
    p=PARAMS[aid];ug=total(p["contents"],p["primary"]);contents=float(number(ug)*p["count"])
    light=aid in ["SMALL_CARTON","STANDARD_CARTON"]
    modes=[dict(transport_tag="manual_hand_carry",required_handler_tag="manual_operator",required_equipment_tags=[]),
           dict(transport_tag="manual_cart",required_handler_tag="manual_operator",required_equipment_tags=["manual_cart"]),
           dict(transport_tag="light_conveyor",required_handler_tag="handoff_operator",required_equipment_tags=["light_conveyor"])] if light else [
           dict(transport_tag="forklift_assisted",required_handler_tag="forklift_operator",required_equipment_tags=["forklift","approved_load_support"])]
    return dict(schema_id="qoima.cargo-archetype.v3-proposal",schema_version="0.1.0",record_type="CargoArchetype",status="proposal",
        source_kind="synthetic_design",operational_admission=False,archetype_id=aid,label="C02 synthetic "+aid,
        layout_binding=dict(manifest_path="docs/v3/contract-proposals/layout-manifest-v3.json",manifest_sha256=sha(c01.MANIFEST),
            layout_version=layout["layout_version"],layout_content_hash=layout["layout_content_hash"],public_runtime_sha256=layout["public_runtime"]["sha256"]),
        reference_binding=dict(path="assets/references/v3/r03-dimension-targets.json",sha256=sha(c01.TARGETS),archetype_id=aid,dimensions_role="handling_unit_outer_target"),
        unit=dict(dimensions_xyz_m=p["unit"],bounding_volume_m3=volume(p["unit"]),contents_mass_kg=p["contents"],packaging_tare_mass_kg=p["primary"],
                  gross_mass_kg=ug,mass_scope="contents_plus_primary_unit_packaging"),
        handling_unit=dict(dimensions_xyz_m=target["dimensions_m"],bounding_volume_m3=volume(target["dimensions_m"]),
            units_per_handling_unit=p["count"],packaging_type=p["pack"],packaging_tare_mass_kg=p["outer"],contents_gross_mass_kg=contents,
            gross_mass_kg=total(contents,p["outer"]),mass_scope="packaged_units_plus_HU_packaging_and_integral_support_excludes_vehicle_attachments"),
        orientation=dict(upright_only=True,permitted_orientations=[dict(orientation_id="upright_xyz",local_axes_in_destination=["+X","+Y","+Z"])],
            slot_orientation_mappings=[dict(slot_orientation_id="upright_xyz_in_module",cargo_orientation_id="upright_xyz")]),
        fragile=p.get("fragile",False),stacking=dict(stackable=False,max_stack=1),
        handling=dict(candidate_only=True,modes=modes),
        compatibility=dict(storage_type_tags=p["storage"],property_tags=["upright","sealed"]+(["fragile"] if p.get("fragile") else []),candidate_only=True),
        source_of_assumptions=[
            dict(assumption_id="C02_"+aid+"_HU_TARGET",kind="synthetic_design",fields=["handling_unit.dimensions_xyz_m"],
                 statement="Explicit unchanged adoption of accepted R03outerHU target, not unit contents or SKU dimensions."),
            dict(assumption_id="C02_"+aid+"_FIXED_PACK",kind="synthetic_design",fields=["unit","handling_unit","orientation","fragile","stacking","handling","compatibility"],
                 statement=p["meaning"]+". All masses/counts/packing/handling assumptions fixed before optimization; eligibility/support/rating/contacts remain C04-C09/P/W.")])


def make_recipe(aid):
    p=PARAMS[aid];u=p["unit"];grid=p["grid"];gap=p["gap"]
    extent=[grid[i]*u[i]+(grid[i]-1)*gap[i] for i in range(3)]
    start=[p["lo"][i]+(p["hi"][i]-p["lo"][i]-extent[i])/2 for i in range(3)];instances=[]
    for ordinal,cell in enumerate(itertools.product(*(range(n) for n in grid)),1):
        lo=[round(start[i]+cell[i]*(u[i]+gap[i]),9) for i in range(3)]
        instances.append(dict(unit_ordinal=ordinal,min_xyz_m=lo,max_xyz_m=[round(lo[i]+u[i],9) for i in range(3)]))
    recipe=dict(archetype_id=aid,method="explicit_axis_aligned_unit_envelopes",packing_frame="HU_minimum_outer_XYZ_corner",
        unit_axes_in_HU=["+X","+Y","+Z"],inner_bounds_xyz_m=dict(min=p["lo"],max=p["hi"]),grid_counts_xyz=grid,unit_gap_xyz_m=gap,
        physical_unit_meaning=p["meaning"],unit_instances=instances,prototype_contents_not_stock=True,
        support_convention=dict(kind="localized_integral_packaging_dunnage_and_separators",mass_included_in="handling_unit.packaging_tare_mass_kg",
            lowest_unit_bottom_y_m=min(v["min_xyz_m"][1] for v in instances),inter_layer_separator_thickness_m=gap[1],
            rule="Lowest units rest on packaging/support pads at statedY; upper aligned columns bear through units and gap-thickness separators. Not a solid full-volume slab or support/rating approval."),
        display_semantics="One HU glyph contains its stated unit templates. Interior glyphs are contents, never extra lots; no scaling or units-as-litres.",
        scope="Geometric envelope witness/symbolic sealed contents convention; no manufacturing, support/rating, admission or warehouse inventory.")
    if "fluid" in p:recipe["symbolic_liquid"]=p["fluid"]
    return recipe


def candidate_families(records,storage):
    result=[]
    for record in records:
        aid=record["archetype_id"];hu=record["handling_unit"];families={};margins={}
        for slot in storage["slots"]:
            if not slot["active_pick_candidate"] or slot["retrieval_blocked"] or slot["storage_type"] not in record["compatibility"]["storage_type_tags"] or aid not in slot["allowed_cargo_archetype_ids"]:continue
            spare=[slot["usable_dimensions_xyz_m"][i]-hu["dimensions_xyz_m"][i]-2*slot["clearance_each_side_m"] for i in range(3)]
            if min(spare)<-EPS or hu["gross_mass_kg"]>slot["max_payload_kg"]+EPS or slot["max_handling_units"]<1:continue
            family=slot["storage_type"];families[family]=families.get(family,0)+1
            margins[family]=[min(a,b) for a,b in zip(margins.get(family,[math.inf]*3),spare)]
        if not families:raise ValueError("NO_PLAUSIBLE_ACTIVE_FAMILY "+aid)
        result.append(dict(archetype_id=aid,active_geometry_candidates_by_family=families,
            minimum_extra_allowance_after_declared_clearance_m={f:[0 if abs(x)<EPS else round(x,9) for x in v] for f,v in margins.items()},
            capacity_is_shared_not_dedicated=True,operational_admission=False,
            scope="Only active type/upright d+2c dimension budget/per-HU payload/capacity witness, not placement. Never infer base+c hover; support/vertical clearance allocation is C04. Handler/routes/lift/assignment remain later gates."))
    return result


def validate_packing(record,recipe):
    aid=record["archetype_id"];u=record["unit"]["dimensions_xyz_m"];hu=record["handling_unit"];inner=recipe["inner_bounds_xyz_m"]
    if recipe["prototype_contents_not_stock"] is not True:raise ValueError("PACKING_SCOPE_MISMATCH")
    if recipe["packing_frame"]!="HU_minimum_outer_XYZ_corner":raise ValueError("PACKING_FRAME_MISMATCH")
    if recipe["unit_axes_in_HU"]!=["+X","+Y","+Z"]:raise ValueError("UNDECLARED_UNIT_PACKING_ORIENTATION")
    if len(recipe["grid_counts_xyz"])!=3 or any(not isinstance(n,int) or isinstance(n,bool) or n<1 for n in recipe["grid_counts_xyz"]):raise ValueError("PACKING_GRID_MISMATCH")
    if len(recipe["unit_gap_xyz_m"])!=3 or min(recipe["unit_gap_xyz_m"])<0:raise ValueError("PACKING_GAP_MISMATCH")
    if len(recipe["unit_instances"])!=hu["units_per_handling_unit"] or math.prod(recipe["grid_counts_xyz"])!=hu["units_per_handling_unit"]:raise ValueError("PACKING_COUNT_MISMATCH")
    if not all(0<=inner["min"][i]<inner["max"][i]<=hu["dimensions_xyz_m"][i]+EPS for i in range(3)):raise ValueError("PACKING_INNER_OUTSIDE_HU")
    if {v["unit_ordinal"] for v in recipe["unit_instances"]}!=set(range(1,hu["units_per_handling_unit"]+1)):raise ValueError("INVALID_PACKING_ORDINALS")
    support=recipe["support_convention"]
    if support["mass_included_in"]!="handling_unit.packaging_tare_mass_kg" or abs(support["lowest_unit_bottom_y_m"]-min(v["min_xyz_m"][1] for v in recipe["unit_instances"]))>EPS or support["inter_layer_separator_thickness_m"]!=recipe["unit_gap_xyz_m"][1]:raise ValueError("PACKING_SUPPORT_CONVENTION_MISMATCH")
    for v in recipe["unit_instances"]:
        lo,hi=v["min_xyz_m"],v["max_xyz_m"]
        if not all(abs(hi[i]-lo[i]-u[i])<=EPS for i in range(3)):raise ValueError("PACKING_UNIT_DIMENSION_MISMATCH")
        if not all(inner["min"][i]-EPS<=lo[i]<hi[i]<=inner["max"][i]+EPS for i in range(3)):raise ValueError("PACKING_UNIT_OUTSIDE_INNER "+aid)
    for a,b in itertools.combinations(recipe["unit_instances"],2):
        if all(min(a["max_xyz_m"][i],b["max_xyz_m"][i])-max(a["min_xyz_m"][i],b["min_xyz_m"][i])>EPS for i in range(3)):raise ValueError("PACKING_UNIT_OVERLAP")
    if aid in ["IBC","DRUM"]:
        fluid=recipe["symbolic_liquid"]
        if hu["units_per_handling_unit"]!=1:raise ValueError("LIQUID_UNIT_MEANS_ONE_SEALED_CONTAINER")
        c01.equal(fluid["density_kg_m3"]*fluid["fill_volume_m3"],record["unit"]["contents_mass_kg"],"SYMBOLIC_FLUID_MASS_MISMATCH")
        if not 0<fluid["fill_volume_m3"]<=fluid["declared_usable_capacity_m3"]<=record["unit"]["bounding_volume_m3"]+EPS:raise ValueError("SYMBOLIC_CAPACITY_EXCEEDED")
    elif "symbolic_liquid" in recipe:raise ValueError("UNEXPECTED_FLUID_CONVENTION")


def build():
    layout=c01.read(c01.MANIFEST);targets=c01.read(c01.TARGETS)["archetypes"]
    records=[make_record(t["archetype_id"],t,layout) for t in targets]
    return dict(schema_id="qoima.cargo-catalog.v3-proposal",schema_version="0.1.0",status="proposal",source_kind="synthetic_design",
        operational_admission=False,assumption_freeze="All8unit/pack dimensions/masses/counts/tags fixed before any optimization or assignment.",
        layout_binding=records[0]["layout_binding"],reference_adoption=dict(path="assets/references/v3/r03-dimension-targets.json",sha256=sha(c01.TARGETS),
            status="C02explicit_R03_HU_target_adoption_proposal",targets_changed=False,archetype_ids=[r["archetype_id"] for r in records]),
        source_fingerprints=[dict(path=str(p.relative_to(ROOT)).replace("\\","/"),sha256=sha(p)) for p in INPUTS],
        geometry_policy=dict(HU_model_scale_factor=1,unit_instance_scale_factor=1,HU_model_origin="floor_centre_XZ_Y0",
            recipe_origin="HU_minimum_outer_XYZ_corner",recipe_to_HU_model="(x-HUwidth/2,y,z-HUdepth/2)"),
        records=records,packing_recipes=[make_recipe(r["archetype_id"]) for r in records],
        candidate_family_witnesses=candidate_families(records,c01.read(c01.STORAGE)),
        candidate_witness_tolerance_m=EPS,
        capacity_note="Per-archetype witness counts share the same physical slots; never sum them as independent capacity or an assignment.",
        deferred=["200SKU binding,stock,lots and assignments","C04-C09 actual compatibility,handler/route/support/rating/height/clearance","actual cargo meshes and P/W contacts/source scheduling"])


def validate_catalog(data):
    c01.finite(data);ctx=c01.context();records=data["records"];expected=set(ctx["targets"]);ids=[r["archetype_id"] for r in records]
    if len(records)!=8:raise ValueError("EXPECTED_EIGHT_ARCHETYPES")
    if len(set(ids))!=8:raise ValueError("DUPLICATE_ARCHETYPE_ID")
    if set(ids)!=expected:raise ValueError("ARCHETYPE_SET_MISMATCH")
    if data["schema_id"]!="qoima.cargo-catalog.v3-proposal" or data["schema_version"]!="0.1.0":raise ValueError("CATALOG_SCHEMA_MISMATCH")
    adoption=data["reference_adoption"]
    if adoption["sha256"]!=sha(c01.TARGETS) or adoption["targets_changed"] is not False or adoption["archetype_ids"]!=[t["archetype_id"] for t in c01.read(c01.TARGETS)["archetypes"]]:raise ValueError("TARGET_ADOPTION_MISMATCH")
    if data["candidate_witness_tolerance_m"]!=EPS:raise ValueError("CANDIDATE_TOLERANCE_CHANGED")
    if data["geometry_policy"]["HU_model_scale_factor"]!=1 or data["geometry_policy"]["unit_instance_scale_factor"]!=1:raise ValueError("SCALE_OVERRIDE_FORBIDDEN")
    if data["operational_admission"] is not False or data["status"]!="proposal":raise ValueError("UNAPPROVED_ADMISSION")
    actual={f["path"]:f["sha256"] for f in data["source_fingerprints"]}
    wanted={str(p.relative_to(ROOT)).replace("\\","/"):sha(p) for p in INPUTS}
    if actual!=wanted or len(data["source_fingerprints"])!=len(INPUTS):raise ValueError("SOURCE_HASH_MISMATCH")
    results=[c01.validate_record(r,ctx) for r in records]
    if any(r["layout_binding"]!=data["layout_binding"] for r in records):raise ValueError("CATALOG_LAYOUT_BINDING_MISMATCH")
    witnesses=candidate_families(records,c01.read(c01.STORAGE))
    if witnesses!=data["candidate_family_witnesses"]:raise ValueError("CANDIDATE_WITNESS_MISMATCH")
    recipes={r["archetype_id"]:r for r in data["packing_recipes"]}
    if len(recipes)!=8 or len(data["packing_recipes"])!=8 or set(recipes)!=expected:raise ValueError("PACKING_RECIPE_SET_MISMATCH")
    for r in records:validate_packing(r,recipes[r["archetype_id"]])
    return dict(records_validated=8,prototype_unit_instances=sum(len(r["unit_instances"]) for r in recipes.values()),
        HU_gross_mass_kg={r["archetype_id"]:r["handling_unit"]["gross_mass_kg"] for r in records},candidate_family_witnesses=witnesses,
        operational_admission=False,SKU_inventory_or_assignments_created=False)


def negative_cases(data):
    result=[]
    def reject(name,mutate,reason):
        bad=copy.deepcopy(data);mutate(bad)
        try:validate_catalog(bad)
        except (ValueError,AssertionError) as e:
            assert reason in str(e),(name,str(e));result.append(dict(case=name,passed=True,result=reason));return
        raise AssertionError("BAD_CATALOG_ACCEPTED "+name)
    reject("duplicate_archetype",lambda d:d["records"].__setitem__(1,copy.deepcopy(d["records"][0])),"DUPLICATE_ARCHETYPE_ID")
    reject("missing_archetype",lambda d:d["records"].pop(),"EXPECTED_EIGHT_ARCHETYPES")
    reject("stale_layout",lambda d:d["records"][0]["layout_binding"].__setitem__("layout_content_hash","0"*64),"LAYOUT_BINDING_MISMATCH")
    reject("stale_source_fingerprint",lambda d:d["source_fingerprints"][0].__setitem__("sha256","0"*64),"SOURCE_HASH_MISMATCH")
    def changed_target(d):
        h=d["records"][0]["handling_unit"];h["dimensions_xyz_m"]=[.33,.24,.24];h["bounding_volume_m3"]=volume(h["dimensions_xyz_m"])
    reject("changed_R03_HU_target_even_with_correct_volume",changed_target,"REFERENCE_TARGET_MISMATCH")
    reject("HU_mass_identity",lambda d:d["records"][0]["handling_unit"].__setitem__("gross_mass_kg",2),"HU_GROSS_MASS_MISMATCH")
    def outside(d):
        v=d["packing_recipes"][0]["unit_instances"][0]
        v["min_xyz_m"][0]-=.5;v["max_xyz_m"][0]-=.5
    reject("outside_inner_pack",outside,"PACKING_UNIT_OUTSIDE_INNER")
    def overlap(d):
        a,b=d["packing_recipes"][0]["unit_instances"][:2];b["min_xyz_m"]=list(a["min_xyz_m"]);b["max_xyz_m"]=list(a["max_xyz_m"])
    reject("overlapping_contents_despite_sufficient_total_volume",overlap,"PACKING_UNIT_OVERLAP")
    reject("wrong_pack_count",lambda d:d["packing_recipes"][0]["unit_instances"].pop(),"PACKING_COUNT_MISMATCH")
    def overweight(d):
        r=next(r for r in d["records"] if r["archetype_id"]=="IBC")
        r["unit"].update(contents_mass_kg=1200,gross_mass_kg=1214);r["handling_unit"].update(contents_gross_mass_kg=1214,gross_mass_kg=1254)
    reject("IBC_exceeds_all_active_ground_payloads",overweight,"NO_PLAUSIBLE_ACTIVE_FAMILY")
    def fluid_overfill(d):
        r=next(r for r in d["records"] if r["archetype_id"]=="IBC")
        r["unit"].update(contents_mass_kg=700,gross_mass_kg=714);r["handling_unit"].update(contents_gross_mass_kg=714,gross_mass_kg=754)
        p=next(p for p in d["packing_recipes"] if p["archetype_id"]=="IBC");p["symbolic_liquid"]["fill_volume_m3"]=.7
    reject("symbolic_tank_overfill",fluid_overfill,"SYMBOLIC_CAPACITY_EXCEEDED")
    reject("conflate_unit_with_HU",lambda d:d["records"][0]["unit"].update(dimensions_xyz_m=d["records"][0]["handling_unit"]["dimensions_xyz_m"],bounding_volume_m3=d["records"][0]["handling_unit"]["bounding_volume_m3"]),"PACKING_UNIT_DIMENSION_MISMATCH")
    reject("shrink_HU_to_force_fit",lambda d:d["geometry_policy"].__setitem__("HU_model_scale_factor",.9),"SCALE_OVERRIDE_FORBIDDEN")
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--check-only",action="store_true");args=parser.parse_args()
    before={str(p):sha(p) for p in INPUTS};data=build();summary=validate_catalog(data);negative=negative_cases(data);payload=encoded(data)
    if args.check_only:assert OUT.read_bytes()==payload,"Catalogue differs from fixed deterministic proposal"
    else:
        OUT.write_bytes(payload)
        evidence=dict(task_id="C02",status="ACTIVE",root_review="pending",checked_utc=datetime.now(timezone.utc).isoformat(),passed=True,
            summary=summary,negative_cases=negative,output=dict(path=str(OUT.relative_to(ROOT)).replace("\\","/"),sha256=sha(OUT),bytes=len(payload)),
            builder=dict(path=str(Path(__file__).relative_to(ROOT)).replace("\\","/"),sha256=sha(Path(__file__))),
            source_fingerprints=data["source_fingerprints"],source_inputs_preserved=True)
        (ROOT/"docs/adaptive-v3/evidence/C02.json").write_bytes(encoded(evidence))
    assert before=={str(p):sha(p) for p in INPUTS},"Read-only source changed"
    print(json.dumps(dict(passed=True,records=8,prototype_units=summary["prototype_unit_instances"],HU_gross_mass_kg=summary["HU_gross_mass_kg"],
                         negative_cases=len(negative),sha256=hashlib.sha256(payload).hexdigest()),indent=2))


if __name__=="__main__":main()
