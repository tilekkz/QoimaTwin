"""C05-C07 isolated design compatibility; no assignment or route scoring."""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_storage_contract import supported_placement

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/"docs/v3/contract-proposals"
INPUTS=[BASE/"cargo-catalog-v3.json",BASE/"storage-slots-v3.json"]
OUT=BASE/"storage-compatibility-v3.json"
FAMILIES=["SMALL","STANDARD","HEAVY","LONG","FLEX"]
EXPECTED={"SMALL_CARTON":488,"STANDARD_CARTON":72,"HEAVY_BOX":24,"PALLET_LOAD":24,"IBC":24,"LONG_BUNDLE":12,"DRUM":24,"FRAGILE_CRATE":64}


def read(p):return json.loads(p.read_text(encoding="utf-8"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encoded(d):return (json.dumps(d,indent=2,sort_keys=True)+"\n").encode()
def dec(n):return Decimal(str(n))
def valid_number(n):return type(n) in (int,float) and math.isfinite(n)


def mass_ledger(cargo):
    unit,hu=cargo["unit"],cargo["handling_unit"]
    keys=[(unit,"contents_mass_kg"),(unit,"packaging_tare_mass_kg"),(unit,"gross_mass_kg"),
        (hu,"packaging_tare_mass_kg"),(hu,"contents_gross_mass_kg"),(hu,"gross_mass_kg")]
    if any(not valid_number(obj[key]) or obj[key]<0 for obj,key in keys):raise ValueError("INVALID_MASS")
    count=hu["units_per_handling_unit"]
    if type(count) is not int or count<=0 or unit["gross_mass_kg"]<=0 or hu["gross_mass_kg"]<=0:raise ValueError("INVALID_MASS")
    ug=dec(unit["contents_mass_kg"])+dec(unit["packaging_tare_mass_kg"])
    contents=ug*count;gross=contents+dec(hu["packaging_tare_mass_kg"])
    if ug!=dec(unit["gross_mass_kg"]) or contents!=dec(hu["contents_gross_mass_kg"]) or gross!=dec(hu["gross_mass_kg"]):raise ValueError("MASS_ARITHMETIC_MISMATCH")
    return dict(unit_gross_kg=float(ug),unit_count=count,contents_gross_kg=float(contents),
        HU_tare_kg=hu["packaging_tare_mass_kg"],HU_gross_kg=float(gross))


def orientation_dimensions(cargo, orientation_id, slot):
    """Signed proper XYZ permutation; never choose an unlisted rotation."""
    orientation=next((o for o in cargo["orientation"]["permitted_orientations"] if o["orientation_id"]==orientation_id),None)
    if orientation is None:return None
    axes=orientation["local_axes_in_destination"]
    if len(axes)!=3 or any(a not in [s+x for s in ["+","-"] for x in "XYZ"] for a in axes):return None
    indices=["XYZ".index(a[1]) for a in axes]
    if len(set(indices))!=3:return None
    inversions=sum(indices[i]>indices[j] for i in range(3) for j in range(i+1,3))
    determinant=(-1)**inversions*math.prod(1 if a[0]=="+" else -1 for a in axes)
    if determinant!=1 or cargo["orientation"]["upright_only"] and axes[1]!="+Y":return None
    if not any(m["cargo_orientation_id"]==orientation_id and m["slot_orientation_id"] in slot["allowed_orientation_ids"] for m in cargo["orientation"]["slot_orientation_mappings"]):return None
    dims=cargo["handling_unit"]["dimensions_xyz_m"]
    if len(dims)!=3 or any(not valid_number(d) or d<=0 for d in dims):return None
    out=[0,0,0]
    for source,destination in enumerate(indices):out[destination]=dims[source]
    return out


def evaluate(cargo,slot,module,*,orientation_id="upright_xyz",transport_tag=None,occupied_units=0,module_mass_kg=0,handler_available=True):
    """Return design eligibility. Source inventory and actual M/P admission are separate."""
    def result(ok,reason,**details):return dict(design_eligible=ok,reason=reason,details=details,
        operational_admission=False,cost_evaluated=False)
    aid=cargo["archetype_id"]
    if slot["retrieval_blocked"] or slot["reserve_only"]:
        return result(False,"HEIGHT_ACCESS_UNAVAILABLE",source_reason=slot["retrieval_block_reason"])
    if slot["storage_type"] not in cargo["compatibility"]["storage_type_tags"] or aid not in slot["allowed_cargo_archetype_ids"]:
        return result(False,"CARGO_TYPE_MISMATCH")
    dims=orientation_dimensions(cargo,orientation_id,slot)
    if dims is None:return result(False,"ORIENTATION_FORBIDDEN")
    clearance=slot["clearance_each_side_m"]
    if any(dec(d)+2*dec(clearance)>dec(u) for d,u in zip(dims,slot["usable_dimensions_xyz_m"])):
        return result(False,"DIMENSION_MISMATCH",oriented_dimensions_xyz_m=dims)
    mass=cargo["handling_unit"]["gross_mass_kg"]
    if not valid_number(mass) or mass<=0:return result(False,"INVALID_MASS")
    try:mass_ledger(cargo)
    except ValueError as exc:return result(False,str(exc))
    if mass>slot["max_payload_kg"]:return result(False,"OVERWEIGHT",scope="slot")
    if type(occupied_units) is not int or occupied_units<0 or not valid_number(module_mass_kg) or module_mass_kg<0:
        return result(False,"INVALID_OCCUPANCY")
    if occupied_units>=slot["max_handling_units"]:return result(False,"SLOT_CAPACITY")
    if dec(mass)+dec(module_mass_kg)>dec(module["max_module_payload_kg"]):
        return result(False,"OVERWEIGHT",scope="module")
    modes=cargo["handling"]["modes"]
    tag=transport_tag or modes[0]["transport_tag"]
    if not any(m["transport_tag"]==tag for m in modes):return result(False,"HANDLER_UNAVAILABLE")
    option=next((o for o in slot["conditional_handler_options"] if o["transport_tag"]==tag and aid in o["allowed_cargo_archetype_ids"]),None)
    if not option or not handler_available:return result(False,"HANDLER_UNAVAILABLE")
    if option["manual_gross_mass_limit_kg"] is not None and mass>option["manual_gross_mass_limit_kg"]:
        return result(False,"OVERWEIGHT",scope="manual_handler")
    placement=supported_placement(slot,dims)
    assert placement["support_gap_m"]==0
    return result(True,"DESIGN_COMPATIBLE",transport_tag=tag,oriented_dimensions_xyz_m=dims,placement=placement)


def make():
    catalog,storage=[read(p) for p in INPUTS]
    modules={m["module_id"]:m for m in storage["modules"]}
    rows=[];summaries=[]
    for cargo in catalog["records"]:
        accepted=[];rejections=Counter()
        for slot in storage["slots"]:
            verdict=evaluate(cargo,slot,modules[slot["module_id"]])
            if verdict["design_eligible"]:accepted.append(slot["slot_id"])
            else:rejections[verdict["reason"]]+=1
        assert len(accepted)==EXPECTED[cargo["archetype_id"]],(cargo["archetype_id"],len(accepted))
        summaries.append(dict(archetype_id=cargo["archetype_id"],accepted_slot_ids=accepted,accepted_count=len(accepted),rejection_counts=dict(rejections)))
        for family in FAMILIES:
            slot=next(s for s in storage["slots"] if s["storage_type"]==family and not s["retrieval_blocked"] and not s["reserve_only"])
            rows.append(dict(archetype_id=cargo["archetype_id"],storage_type=family,representative_slot_id=slot["slot_id"],
                **evaluate(cargo,slot,modules[slot["module_id"]])))
    assert sum(r["design_eligible"] for r in rows)==10
    return dict(schema_id="qoima.storage-compatibility.v3-design",schema_version="0.1.0",source_kind="synthetic_design",
        operational_admission=False,source_fingerprints=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in INPUTS],
        layout_content_hash=catalog["layout_binding"]["layout_content_hash"],
        scope="Design compatibility, no stock/assignment/actual contacts/availability/source scheduling. Candidate sets share slots; never sum as independent capacity.",
        decision_order=["reserve_access","cargo_type","permitted_orientation","exact_dimensions_plus_clearance","HU_slot_mass","slot_capacity","module_mass","allowed_available_handler"],
        dimension_rule="Oriented dimensions+2c <= usable on all axes, exact Decimal; C04 support plane with zero bottom gap.",
        family_matrix=rows,per_cargo_slot_candidates=summaries,
        counters=dict(archetypes=8,families=5,family_cases=40,family_positive=10,physical_slots=776,blocked_reserve_slots=188,slot_cases=6208))


def checks():
    cargo=read(INPUTS[0])["records"][0];storage=read(INPUTS[1]);slot=next(s for s in storage["slots"] if s["storage_type"]=="SMALL" and not s["retrieval_blocked"])
    module=next(m for m in storage["modules"] if m["module_id"]==slot["module_id"])
    assert evaluate(cargo,slot,module)["design_eligible"]
    tests=[]
    def bad(name,reason,change_cargo=None,change_slot=None,kwargs=None):
        c,s=copy.deepcopy(cargo),copy.deepcopy(slot)
        if change_cargo:change_cargo(c)
        if change_slot:change_slot(s)
        v=evaluate(c,s,module,**(kwargs or {}));assert not v["design_eligible"] and v["reason"]==reason,(name,v)
        assert v["cost_evaluated"] is False
        tests.append(dict(case_id=name,reason=reason,passed=True))
    bad("wrong_type","CARGO_TYPE_MISMATCH",lambda c:c["compatibility"].update(storage_type_tags=["LONG"]))
    bad("forbidden_yaw","ORIENTATION_FORBIDDEN",kwargs=dict(orientation_id="unlisted_90deg"))
    bad("oversize","DIMENSION_MISMATCH",lambda c:c["handling_unit"].update(dimensions_xyz_m=[.50,.24,.24]))
    def overweight(c):
        c["unit"].update(contents_mass_kg=15.9,packaging_tare_mass_kg=0,gross_mass_kg=15.9)
        c["handling_unit"].update(units_per_handling_unit=1,contents_gross_mass_kg=15.9,gross_mass_kg=16)
    bad("slot_overweight","OVERWEIGHT",overweight)
    bad("unknown_mass","INVALID_MASS",lambda c:c["handling_unit"].update(gross_mass_kg=float("nan")))
    bad("full_slot","SLOT_CAPACITY",kwargs=dict(occupied_units=1))
    bad("module_overweight","OVERWEIGHT",kwargs=dict(module_mass_kg=150))
    bad("negative_occupancy","INVALID_OCCUPANCY",kwargs=dict(occupied_units=-1))
    bad("manual_to_forklift","HANDLER_UNAVAILABLE",kwargs=dict(transport_tag="forklift_assisted"))
    bad("handler_absent","HANDLER_UNAVAILABLE",kwargs=dict(handler_available=False))
    bad("reserve_access","HEIGHT_ACCESS_UNAVAILABLE",change_slot=lambda s:s.update(retrieval_blocked=True))
    bad("reflected_orientation","ORIENTATION_FORBIDDEN",lambda c:c["orientation"]["permitted_orientations"][0].update(local_axes_in_destination=["-X","+Y","+Z"]))
    # Any tiny height excess over the exact d+2c budget rejects; no epsilon halo.
    h=float(dec(slot["usable_dimensions_xyz_m"][1])-2*dec(slot["clearance_each_side_m"]))
    c=copy.deepcopy(cargo);c["handling_unit"]["dimensions_xyz_m"][1]=h
    assert evaluate(c,slot,module)["design_eligible"]
    c["handling_unit"]["dimensions_xyz_m"][1]=h+1e-10
    assert evaluate(c,slot,module)["reason"]=="DIMENSION_MISMATCH"
    tests.append(dict(case_id="strict_height_budget",reason="DIMENSION_MISMATCH",passed=True))
    return dict(passed=True,negative_cases=tests)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--check-only",action="store_true");args=parser.parse_args()
    document=make();verification=checks()
    if args.check_only:assert OUT.read_bytes()==encoded(document),"Saved compatibility differs from current frozen sources"
    else:
        OUT.write_bytes(encoded(document));evidence=dict(task_id="C05",owner="root",status="VERIFY",artifact=dict(path=OUT.relative_to(ROOT).as_posix(),sha256=sha(OUT),bytes=OUT.stat().st_size),builder_sha256=sha(Path(__file__)),checks=verification,counters=document["counters"])
        (ROOT/"docs/adaptive-v3/evidence/C05.json").write_bytes(encoded(evidence))
    print(json.dumps(dict(**verification,**document["counters"]),separators=(",",":")))


if __name__=="__main__":main()
