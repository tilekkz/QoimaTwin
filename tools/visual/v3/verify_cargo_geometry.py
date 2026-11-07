"""C06 actual evaluator witnesses, including a hypothetical rotation-only fit."""
import argparse
import copy
import json
from pathlib import Path
import storage_eligibility as eligibility

ROOT=eligibility.ROOT
OUT=ROOT/"docs/v3/contract-proposals/cargo-geometry-cases-v3.json"


def build():
    catalog,storage=[eligibility.read(p) for p in eligibility.INPUTS]
    modules={m["module_id"]:m for m in storage["modules"]}
    production=[]
    for cargo in catalog["records"]:
        aid=cargo["archetype_id"]
        assert cargo["orientation"]["permitted_orientations"]==[{"local_axes_in_destination":["+X","+Y","+Z"],"orientation_id":"upright_xyz"}]
        slot=next(s for s in storage["slots"] if not s["retrieval_blocked"] and s["storage_type"] in cargo["compatibility"]["storage_type_tags"] and aid in s["allowed_cargo_archetype_ids"])
        verdict=eligibility.evaluate(cargo,slot,modules[slot["module_id"]]);assert verdict["design_eligible"]
        denied=eligibility.evaluate(cargo,slot,modules[slot["module_id"]],orientation_id="unlisted_yaw90")
        assert denied["reason"]=="ORIENTATION_FORBIDDEN"
        placement=verdict["details"]["placement"]
        assert placement["support_gap_m"]==0 and placement["bottom_y_m"]==slot["bin_anchor_module_local"][1]
        production.append(dict(archetype_id=aid,slot_id=slot["slot_id"],positive=verdict,unlisted_rotation=denied))
    cargo=copy.deepcopy(catalog["records"][0]);cargo["handling_unit"]["dimensions_xyz_m"]=[.40,.30,.60]
    cargo["orientation"]["permitted_orientations"].append(dict(orientation_id="fixture_upright_yaw90",local_axes_in_destination=["+Z","+Y","-X"]))
    cargo["orientation"]["slot_orientation_mappings"].append(dict(cargo_orientation_id="fixture_upright_yaw90",slot_orientation_id="upright_xyz_in_module"))
    slot=copy.deepcopy(next(s for s in storage["slots"] if s["storage_type"]=="FLEX" and not s["retrieval_blocked"]))
    slot.update(usable_dimensions_xyz_m=[.70,.50,.50],bin_anchor_module_local=[0,.18,0],clearance_each_side_m=.05,
        usable_bounds_module_local=dict(min=[-.35,.18,-.25],max=[.35,.68,.25]))
    module=modules[slot["module_id"]]
    identity=eligibility.evaluate(cargo,slot,module);rotated=eligibility.evaluate(cargo,slot,module,orientation_id="fixture_upright_yaw90")
    assert identity["reason"]=="DIMENSION_MISMATCH" and rotated["design_eligible"]
    assert rotated["details"]["oriented_dimensions_xyz_m"]==[.60,.30,.40]
    cases=[]
    def check(name,c,s,expected,orientation="fixture_upright_yaw90"):
        verdict=eligibility.evaluate(c,s,module,orientation_id=orientation)
        assert verdict["reason"]==expected,(name,verdict)
        cases.append(dict(case_id=name,expected=expected,actual=verdict))
    c=copy.deepcopy(cargo);c["orientation"]["permitted_orientations"].pop()
    check("unlisted_even_when_it_would_fit",c,slot,"ORIENTATION_FORBIDDEN")
    c=copy.deepcopy(cargo);c["orientation"]["permitted_orientations"][-1]["local_axes_in_destination"]=["+X","+Y","-Z"]
    check("reflection_not_rotation",c,slot,"ORIENTATION_FORBIDDEN")
    c=copy.deepcopy(cargo);c["orientation"]["permitted_orientations"][-1]["local_axes_in_destination"]=["+X","+Z","-Y"]
    check("proper_rotation_but_upright_forbidden",c,slot,"ORIENTATION_FORBIDDEN")
    for source_axis in range(3):
        c=copy.deepcopy(cargo)
        # Rotated destinationX=sourceZ, destinationY=sourceY, destinationZ=sourceX.
        destination=[2,1,0][source_axis]
        c["handling_unit"]["dimensions_xyz_m"][source_axis]=slot["usable_dimensions_xyz_m"][destination]-.10+1e-10
        check("tiny_excess_source_axis_"+str(source_axis),c,slot,"DIMENSION_MISMATCH")
    return dict(task_id="C06",source_kind="synthetic_design_witnesses",operational_admission=False,
        source_fingerprints=[dict(path=p.relative_to(ROOT).as_posix(),sha256=eligibility.sha(p)) for p in eligibility.INPUTS],
        production_cases=production,hypothetical_fixture=dict(not_a_production_template=True,dimensions_xyz_m=[.40,.30,.60],
            usable_xyz_m=[.70,.50,.50],clearance_each_side_m=.05,identity=identity,explicitly_permitted_yaw90=rotated,
            orientation_axes=["+Z","+Y","-X"],negative_cases=cases),production_permissions_changed=False)


def main():
    p=argparse.ArgumentParser();p.add_argument("--check-only",action="store_true");args=p.parse_args();doc=build()
    if args.check_only:assert OUT.read_bytes()==eligibility.encoded(doc)
    else:
        OUT.write_bytes(eligibility.encoded(doc))
        evidence=dict(task_id="C06",owner="root",status="VERIFY",passed=True,
            artifact=dict(path=OUT.relative_to(ROOT).as_posix(),sha256=eligibility.sha(OUT),bytes=OUT.stat().st_size),
            production_fit_cases=8,production_forbidden_yaw_cases=8,hypothetical_rotation_only_fit=True,fixture_negative_cases=6)
        (ROOT/"docs/adaptive-v3/evidence/C06.json").write_bytes(eligibility.encoded(evidence))
    print(json.dumps(dict(passed=True,production_fit=8,production_forbidden_yaw=8,fixture_negatives=6,rotation_only_fixture=True)))


if __name__=="__main__":main()
