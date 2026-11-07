"""C01 one-record structure/identity validation, never cargo admission/packing."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[3]
SCHEMA=ROOT/"docs/v3/contract-proposals/cargo-archetype-v3.schema.json"
EXAMPLE=ROOT/"docs/v3/contract-proposals/cargo-archetype-v3.example.json"
MANIFEST=ROOT/"docs/v3/contract-proposals/layout-manifest-v3.json"
TARGETS=ROOT/"assets/references/v3/r03-dimension-targets.json"
STORAGE=ROOT/"docs/v3/contract-proposals/storage-layout-v3.json"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    def reject(value):raise ValueError("NONFINITE_JSON_NUMBER "+value)
    return json.loads(path.read_text(encoding="utf-8-sig"),parse_constant=reject)


def finite(value):
    if isinstance(value,float) and not math.isfinite(value):raise ValueError("NONFINITE_NUMBER")
    if isinstance(value,dict):
        for v in value.values():finite(v)
    elif isinstance(value,list):
        for v in value:finite(v)


def equal(actual,expected,reason):
    if not math.isclose(actual,expected,rel_tol=1e-9,abs_tol=1e-12):
        raise ValueError(reason+f" actual={actual},expected={expected}")


def context():
    schema=read(SCHEMA);Draft202012Validator.check_schema(schema)
    return dict(schema=schema,validator=Draft202012Validator(schema),manifest=read(MANIFEST),
        targets={x["archetype_id"]:x for x in read(TARGETS)["archetypes"]},
        slot_orientation_ids={o for s in read(STORAGE)["slots"] for o in s["allowed_orientation_ids"]})


def proper_orientation(axes):
    if len({x[1] for x in axes})!=3:raise ValueError("ORIENTATION_AXES_NOT_PERMUTATION")
    m=[[0]*3 for _ in range(3)]
    for col,axis in enumerate(axes):m["XYZ".index(axis[1])][col]=1 if axis[0]=="+" else -1
    det=m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])-m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])+m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0])
    if det!=1:raise ValueError("ORIENTATION_REFLECTION")


def validate_record(record,ctx):
    finite(record)
    errors=list(ctx["validator"].iter_errors(record))
    if errors:
        e=errors[0];raise ValueError("SCHEMA_FIELD_ERROR "+"/".join(str(p) for p in e.absolute_path)+": "+e.message)
    layout=record["layout_binding"];manifest=ctx["manifest"]
    expected=dict(manifest_path="docs/v3/contract-proposals/layout-manifest-v3.json",manifest_sha256=sha(MANIFEST),
                  layout_version=manifest["layout_version"],layout_content_hash=manifest["layout_content_hash"],
                  public_runtime_sha256=manifest["public_runtime"]["sha256"])
    if layout!=expected:raise ValueError("LAYOUT_BINDING_MISMATCH")
    ref=record["reference_binding"];target=ctx["targets"][record["archetype_id"]]
    if ref["archetype_id"]!=record["archetype_id"] or ref["sha256"]!=sha(TARGETS):raise ValueError("REFERENCE_BINDING_MISMATCH")
    unit,hu=record["unit"],record["handling_unit"]
    for name,item in [("unit",unit),("handling_unit",hu)]:
        equal(item["bounding_volume_m3"],math.prod(item["dimensions_xyz_m"]),"VOLUME_MISMATCH "+name)
    if any(not math.isclose(a,b,rel_tol=0,abs_tol=1e-10) for a,b in zip(hu["dimensions_xyz_m"],target["dimensions_m"])):
        raise ValueError("REFERENCE_TARGET_MISMATCH")
    equal(unit["gross_mass_kg"],unit["contents_mass_kg"]+unit["packaging_tare_mass_kg"],"UNIT_GROSS_MASS_MISMATCH")
    equal(hu["contents_gross_mass_kg"],hu["units_per_handling_unit"]*unit["gross_mass_kg"],"HU_CONTENTS_MASS_MISMATCH")
    equal(hu["gross_mass_kg"],hu["contents_gross_mass_kg"]+hu["packaging_tare_mass_kg"],"HU_GROSS_MASS_MISMATCH")
    orientation=record["orientation"];permitted={}
    for o in orientation["permitted_orientations"]:
        oid=o["orientation_id"]
        if oid in permitted:raise ValueError("DUPLICATE_ORIENTATION_ID")
        axes=o["local_axes_in_destination"];proper_orientation(axes)
        if orientation["upright_only"] and axes[1]!="+Y":raise ValueError("UPRIGHT_ORIENTATION_CONFLICT")
        permitted[oid]=axes
    pairs=set()
    for mapping in orientation["slot_orientation_mappings"]:
        sid,cid=mapping["slot_orientation_id"],mapping["cargo_orientation_id"]
        if sid not in ctx["slot_orientation_ids"] or cid not in permitted:raise ValueError("ORIENTATION_MAPPING_REFERENCE_MISMATCH")
        if (sid,cid) in pairs:raise ValueError("DUPLICATE_ORIENTATION_MAPPING")
        pairs.add((sid,cid))
        if sid=="upright_xyz_in_module" and permitted[cid]!=["+X","+Y","+Z"]:raise ValueError("SLOT_ORIENTATION_MAPPING_CONFLICT")
    stacking=record["stacking"]
    if (not stacking["stackable"] and stacking["max_stack"]!=1) or (stacking["stackable"] and stacking["max_stack"]<2):
        raise ValueError("STACK_POLICY_CONFLICT")
    modes=set()
    for mode in record["handling"]["modes"]:
        tag=mode["transport_tag"]
        if tag in modes:raise ValueError("DUPLICATE_HANDLING_MODE")
        modes.add(tag)
        required={"manual_hand_carry":set(),"manual_cart":{"manual_cart"},"light_conveyor":{"light_conveyor"},
                  "forklift_assisted":{"forklift","approved_load_support"}}[tag]
        if not required<=set(mode["required_equipment_tags"]):raise ValueError("HANDLING_MODE_REQUIREMENT_CONFLICT")
        if tag=="forklift_assisted" and mode["required_handler_tag"]!="forklift_operator":raise ValueError("HANDLER_TAG_CONFLICT")
    assumptions=[a["assumption_id"] for a in record["source_of_assumptions"]]
    if len(assumptions)!=len(set(assumptions)):raise ValueError("DUPLICATE_ASSUMPTION_ID")
    return dict(archetype_id=record["archetype_id"],unit_volume_m3=unit["bounding_volume_m3"],HU_volume_m3=hu["bounding_volume_m3"],
        unit_gross_mass_kg=unit["gross_mass_kg"],units_per_HU=hu["units_per_handling_unit"],HU_contents_gross_mass_kg=hu["contents_gross_mass_kg"],
        HU_packaging_tare_kg=hu["packaging_tare_mass_kg"],HU_gross_mass_kg=hu["gross_mass_kg"],
        proper_orientations=len(permitted),operational_admission=False,catalogue_created=False)


def negative_cases(example,ctx):
    cases=[]
    def reject(name,mutate,reason):
        bad=copy.deepcopy(example);mutate(bad)
        try:validate_record(bad,ctx)
        except ValueError as exc:
            if reason not in str(exc):raise AssertionError((name,str(exc)))
            cases.append(dict(case=name,passed=True,result=reason));return
        raise AssertionError("INVALID_RECORD_ACCEPTED "+name)
    reject("missing_physical_unit",lambda r:r.pop("unit"),"SCHEMA_FIELD_ERROR")
    reject("zero_dimension",lambda r:r["unit"]["dimensions_xyz_m"].__setitem__(0,0),"SCHEMA_FIELD_ERROR")
    reject("negative_packaging_mass",lambda r:r["handling_unit"].__setitem__("packaging_tare_mass_kg",-.1),"SCHEMA_FIELD_ERROR")
    reject("zero_gross_mass",lambda r:r["unit"].__setitem__("gross_mass_kg",0),"SCHEMA_FIELD_ERROR")
    reject("nonfinite_mass",lambda r:r["unit"].__setitem__("contents_mass_kg",float("nan")),"NONFINITE_NUMBER")
    reject("infinite_dimension",lambda r:r["unit"]["dimensions_xyz_m"].__setitem__(0,float("inf")),"NONFINITE_NUMBER")
    reject("wrong_bounding_volume",lambda r:r["unit"].__setitem__("bounding_volume_m3",1),"VOLUME_MISMATCH")
    reject("wrong_unit_gross_mass",lambda r:r["unit"].__setitem__("gross_mass_kg",.5),"UNIT_GROSS_MASS_MISMATCH")
    reject("wrong_HU_gross_mass",lambda r:r["handling_unit"].__setitem__("gross_mass_kg",6),"HU_GROSS_MASS_MISMATCH")
    reject("wrong_units_to_HU_mass_identity",lambda r:r["handling_unit"].__setitem__("units_per_handling_unit",25),"HU_CONTENTS_MASS_MISMATCH")
    reject("zero_units_per_HU",lambda r:r["handling_unit"].__setitem__("units_per_handling_unit",0),"SCHEMA_FIELD_ERROR")
    reject("upright_axis_tipped",lambda r:r["orientation"]["permitted_orientations"][0].__setitem__("local_axes_in_destination",["-Y","+X","+Z"]),"UPRIGHT_ORIENTATION_CONFLICT")
    reject("reflected_axes",lambda r:r["orientation"]["permitted_orientations"][0].__setitem__("local_axes_in_destination",["+X","+Y","-Z"]),"ORIENTATION_REFLECTION")
    reject("stackable_false_but_two_high",lambda r:r["stacking"].__setitem__("max_stack",2),"STACK_POLICY_CONFLICT")
    reject("wrong_layout_snapshot",lambda r:r["layout_binding"].__setitem__("layout_content_hash","0"*64),"LAYOUT_BINDING_MISMATCH")
    def wrong_target(r):
        r["handling_unit"]["dimensions_xyz_m"]=[.61,.4,.3];r["handling_unit"]["bounding_volume_m3"]=.61*.4*.3
    reject("changed_R03_HU_target",wrong_target,"REFERENCE_TARGET_MISMATCH")
    reject("yaw90_hidden_under_L09_identity",lambda r:r["orientation"]["permitted_orientations"][0].__setitem__("local_axes_in_destination",["+Z","+Y","-X"]),"SLOT_ORIENTATION_MAPPING_CONFLICT")
    reject("cart_mode_without_cart_requirement",lambda r:r["handling"]["modes"][1].__setitem__("required_equipment_tags",[]),"HANDLING_MODE_REQUIREMENT_CONFLICT")
    reject("inventory_field_smuggled_into_archetype",lambda r:r.__setitem__("lot_id","NOT_AN_ARCHETYPE_FIELD"),"SCHEMA_FIELD_ERROR")
    return cases


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--check-only",action="store_true");args=parser.parse_args()
    ctx=context();record=read(EXAMPLE);inputs=[SCHEMA,EXAMPLE,MANIFEST,TARGETS,STORAGE]
    before={str(p):sha(p) for p in inputs};result=validate_record(record,ctx);negative=negative_cases(record,ctx)
    assert before=={str(p):sha(p) for p in inputs},"Read-only cargo/layout input changed"
    if not args.check_only:
        evidence=dict(task_id="C01",status="ACTIVE",root_review="pending",checked_utc=datetime.now(timezone.utc).isoformat(),passed=True,
            schema_validator=f"installed jsonschema{importlib.metadata.version('jsonschema')} Draft202012Validator; local schema/meta validation, no network/install",
            example_result=result,negative_cases=negative,
            input_fingerprints=[dict(path=str(p.relative_to(ROOT)).replace("\\","/"),sha256=sha(p)) for p in inputs],
            validator=dict(path=str(Path(__file__).relative_to(ROOT)).replace("\\","/"),sha256=sha(Path(__file__))),
            scope="One record schema/example; no8catalogue,SKU,inventory,packing/admission solver or frontend change.")
        (ROOT/"docs/adaptive-v3/evidence/C01.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(dict(passed=True,example=result,negative_cases=len(negative),schema_sha256=sha(SCHEMA),example_sha256=sha(EXAMPLE)),indent=2))


if __name__=="__main__":main()
