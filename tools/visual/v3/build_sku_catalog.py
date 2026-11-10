"""C03 canonical synthetic SKU identities -> fixed archetype templates only."""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/"contracts/assignment.example.json"
CARGO=ROOT/"docs/v3/contract-proposals/cargo-catalog-v3.json"
TARGETS=ROOT/"assets/references/v3/r03-dimension-targets.json"
LAYOUT=ROOT/"docs/v3/contract-proposals/layout-manifest-v3.json"
OUT=ROOT/"docs/v3/contract-proposals/sku-catalog-v3.json"
EXPECTED_SOURCE_SHA="b4c3ef62aff9ee2f7774fcaa13e4e563a626c512cfff9dab8655cff0db55f8cc"
EXPECTED_CARGO_SHA="1d873698e090604a80ef305be020230b04abe160fd2188735fc42fb95d4056b9"
MIX=[("SMALL_CARTON",110),("STANDARD_CARTON",55),("HEAVY_BOX",6),("PALLET_LOAD",5),
     ("IBC",3),("LONG_BUNDLE",8),("DRUM",5),("FRAGILE_CRATE",8)]
INHERITED=["unit","handling_unit","orientation","fragile","stacking","handling","compatibility"]
ROW_FIELDS={"sku_id","archetype_id","cargo_template_pointer","model_scale_factor"}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding="utf-8-sig"))
def encode(data):return (json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")


def inputs():
    if sha(SOURCE)!=EXPECTED_SOURCE_SHA:raise ValueError("PROTECTED_IDENTITY_SOURCE_CHANGED")
    if sha(CARGO)!=EXPECTED_CARGO_SHA:raise ValueError("ACCEPTED_C02_TEMPLATE_CHANGED")
    source=read(SOURCE)
    # Read this field only. No legacy quantity/lot/position or assignment copies.
    ids=sorted({row["sku_id"] for row in source["initial_lots"]})
    if ids!=[f"DEMO_{i:03d}" for i in range(1,201)]:raise ValueError("SOURCE_IDENTITY_SET_MISMATCH")
    cargo=read(CARGO);targets=read(TARGETS)
    if {r["archetype_id"] for r in cargo["records"]}!={a for a,_ in MIX}:raise ValueError("C02_ARCHETYPE_SET_MISMATCH")
    if cargo["reference_adoption"]["sha256"]!=sha(TARGETS):raise ValueError("R03_SOURCE_MISMATCH")
    layout=read(LAYOUT);binding=cargo["layout_binding"]
    if binding["manifest_sha256"]!=sha(LAYOUT) or binding["layout_content_hash"]!=layout["layout_content_hash"]:raise ValueError("LAYOUT_SOURCE_MISMATCH")
    return ids,cargo,targets


def fixed_recipe(ids,cargo):
    indices={r["archetype_id"]:i for i,r in enumerate(cargo["records"])};rows=[];blocks=[];start=0
    for aid,count in MIX:
        block=ids[start:start+count]
        blocks.append(dict(archetype_id=aid,count=count,first_sku_id=block[0],last_sku_id=block[-1]))
        rows.extend(dict(sku_id=sid,archetype_id=aid,cargo_template_pointer=f"/records/{indices[aid]}",model_scale_factor=1) for sid in block)
        start+=count
    assert start==200
    return rows,blocks


def build():
    ids,cargo,_=inputs();rows,blocks=fixed_recipe(ids,cargo)
    return dict(schema_id="qoima.sku-catalog.v3-proposal",schema_version="0.1.0",status="proposal",
        data_kind="synthetic_identity_mapping",operational_admission=False,identity_only_import=True,
        identity_source=dict(path="contracts/assignment.example.json",sha256=sha(SOURCE),field_selector="/initial_lots/*/sku_id",unique_identity_count=200),
        cargo_catalog_binding=dict(path="docs/v3/contract-proposals/cargo-catalog-v3.json",sha256=sha(CARGO),
            schema_id=cargo["schema_id"],schema_version=cargo["schema_version"],parameters_are_immutable=True,inherited_fields=INHERITED),
        reference_target_binding=dict(path="assets/references/v3/r03-dimension-targets.json",sha256=sha(TARGETS)),
        layout_binding=cargo["layout_binding"],
        mapping_policy=dict(method="sorted_canonical_ids_contiguous_fixed_blocks",fixed_before_optimization=True,
            class_mix=dict(MIX),blocks=blocks,randomness_used=False),
        skus=rows,
        scope="Identity/template mapping only. No legacy quantities/lots/slot positions/assignment,stock,demand/orders/events or real historical/forecast merge.",
        admission_note="Class counts are assortment composition, not HU stock or proof of shared capacity/slot/route/handler admission. C10 creates actual load separately.")


def validate_catalog(data):
    ids,cargo,_=inputs();expected,blocks=fixed_recipe(ids,cargo);rows=data["skus"]
    if set(data)!=set(build()):raise ValueError("CATALOG_FIELDS_NOT_IDENTITY_ONLY")
    if data["schema_id"]!="qoima.sku-catalog.v3-proposal" or data["schema_version"]!="0.1.0":raise ValueError("SCHEMA_VERSION_MISMATCH")
    if len(rows)!=200:raise ValueError("EXPECTED_200_SKUS")
    found=[r["sku_id"] for r in rows]
    if len(set(found))!=200:raise ValueError("DUPLICATE_SKU_ID")
    if sorted(found)!=ids:raise ValueError("SKU_ID_SET_MISMATCH")
    if data["identity_source"]!=dict(path="contracts/assignment.example.json",sha256=sha(SOURCE),field_selector="/initial_lots/*/sku_id",unique_identity_count=200):raise ValueError("IDENTITY_SOURCE_MISMATCH")
    cb=data["cargo_catalog_binding"]
    if cb["path"]!="docs/v3/contract-proposals/cargo-catalog-v3.json" or cb["sha256"]!=sha(CARGO) or cb["schema_id"]!=cargo["schema_id"] or cb["schema_version"]!=cargo["schema_version"]:raise ValueError("TEMPLATE_SOURCE_MISMATCH")
    if cb["parameters_are_immutable"] is not True or cb["inherited_fields"]!=INHERITED:raise ValueError("TEMPLATE_INHERITANCE_CHANGED")
    if data["reference_target_binding"]!=dict(path="assets/references/v3/r03-dimension-targets.json",sha256=sha(TARGETS)):raise ValueError("REFERENCE_SOURCE_MISMATCH")
    if data["layout_binding"]!=cargo["layout_binding"]:raise ValueError("LAYOUT_BINDING_MISMATCH")
    if data["operational_admission"] is not False or data["identity_only_import"] is not True or data["status"]!="proposal" or data["data_kind"]!="synthetic_identity_mapping":raise ValueError("IDENTITY_ONLY_BOUNDARY_CHANGED")
    known={r["archetype_id"] for r in cargo["records"]}
    for r in rows:
        if set(r)!=ROW_FIELDS:raise ValueError("ROW_FIELDS_NOT_IDENTITY_ONLY")
        if r["archetype_id"] not in known:raise ValueError("UNKNOWN_ARCHETYPE")
        if type(r["model_scale_factor"]) not in [int,float] or r["model_scale_factor"]!=1:raise ValueError("SCALE_OVERRIDE_FORBIDDEN")
        try:
            pointer=r["cargo_template_pointer"].split("/")
            assert pointer[:2]==["","records"] and len(pointer)==3
            record=cargo["records"][int(pointer[2])]
            assert int(pointer[2])>=0 and record["archetype_id"]==r["archetype_id"]
        except (AssertionError,IndexError,ValueError):raise ValueError("TEMPLATE_REFERENCE_MISMATCH")
    if dict(Counter(r["archetype_id"] for r in rows))!=dict(MIX):raise ValueError("FIXED_CLASS_MIX_MISMATCH")
    if rows!=expected or data["mapping_policy"]!=dict(method="sorted_canonical_ids_contiguous_fixed_blocks",fixed_before_optimization=True,class_mix=dict(MIX),blocks=blocks,randomness_used=False):
        raise ValueError("FIXED_CLASS_RECIPE_MISMATCH")
    return dict(unique_skus=200,class_mix=dict(MIX),immutable_templates=8,source_identity_only=True,
                quantities_lots_assignments_created=False,historical_forecast_merged=False,operational_admission=False)


def negative_cases(data):
    cases=[]
    def reject(name,mutate,reason):
        bad=copy.deepcopy(data);mutate(bad)
        try:validate_catalog(bad)
        except ValueError as e:
            assert reason in str(e),(name,str(e));cases.append(dict(case=name,passed=True,result=reason));return
        raise AssertionError("INVALID_MAPPING_ACCEPTED "+name)
    reject("duplicate_SKU",lambda d:d["skus"].__setitem__(1,copy.deepcopy(d["skus"][0])),"DUPLICATE_SKU_ID")
    reject("missing_SKU",lambda d:d["skus"].pop(),"EXPECTED_200_SKUS")
    reject("foreign_SKU_identity",lambda d:d["skus"][0].__setitem__("sku_id","DEMO_999"),"SKU_ID_SET_MISMATCH")
    reject("unknown_archetype",lambda d:d["skus"][0].__setitem__("archetype_id","UNKNOWN"),"UNKNOWN_ARCHETYPE")
    reject("wrong_template_pointer",lambda d:d["skus"][0].__setitem__("cargo_template_pointer","/records/1"),"TEMPLATE_REFERENCE_MISMATCH")
    reject("stale_identity_source",lambda d:d["identity_source"].__setitem__("sha256","0"*64),"IDENTITY_SOURCE_MISMATCH")
    reject("stale_C02_snapshot",lambda d:d["cargo_catalog_binding"].__setitem__("sha256","0"*64),"TEMPLATE_SOURCE_MISMATCH")
    reject("stale_reference_snapshot",lambda d:d["reference_target_binding"].__setitem__("sha256","0"*64),"REFERENCE_SOURCE_MISMATCH")
    reject("visual_scale_override",lambda d:d["skus"][0].__setitem__("model_scale_factor",.9),"SCALE_OVERRIDE_FORBIDDEN")
    reject("boolean_is_not_numeric_scale",lambda d:d["skus"][0].__setitem__("model_scale_factor",True),"SCALE_OVERRIDE_FORBIDDEN")
    reject("legacy_quantity_field_injected",lambda d:d["skus"][0].__setitem__("quantity_units",123),"ROW_FIELDS_NOT_IDENTITY_ONLY")
    reject("legacy_lot_rows_injected",lambda d:d.__setitem__("initial_lots",[]),"CATALOG_FIELDS_NOT_IDENTITY_ONLY")
    def swap_classes(d):
        for key in ["archetype_id","cargo_template_pointer"]:
            d["skus"][0][key],d["skus"][110][key]=d["skus"][110][key],d["skus"][0][key]
    reject("same_counts_but_changed_fixed_mapping",swap_classes,"FIXED_CLASS_RECIPE_MISMATCH")
    return cases


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--check-only",action="store_true");args=parser.parse_args()
    source_paths=[SOURCE,CARGO,TARGETS,LAYOUT];before={str(p):sha(p) for p in source_paths}
    data=build();summary=validate_catalog(data);negative=negative_cases(data);payload=encode(data)
    if args.check_only:assert OUT.read_bytes()==payload,"SKU mapping differs from deterministic frozen recipe"
    else:
        OUT.write_bytes(payload)
        evidence=dict(task_id="C03",status="ACTIVE",root_review="pending",checked_utc=datetime.now(timezone.utc).isoformat(),passed=True,
            summary=summary,negative_cases=negative,output=dict(path=str(OUT.relative_to(ROOT)).replace("\\","/"),sha256=sha(OUT),bytes=len(payload)),
            builder=dict(path=str(Path(__file__).relative_to(ROOT)).replace("\\","/"),sha256=sha(Path(__file__))),
            inputs=[dict(path=str(p.relative_to(ROOT)).replace("\\","/"),sha256=sha(p)) for p in source_paths],source_inputs_preserved=True)
        (ROOT/"docs/adaptive-v3/evidence/C03.json").write_bytes(encode(evidence))
    assert before=={str(p):sha(p) for p in source_paths},"Read-only source changed"
    print(json.dumps(dict(passed=True,summary=summary,negative_cases=len(negative),sha256=hashlib.sha256(payload).hexdigest()),indent=2))


if __name__=="__main__":main()
