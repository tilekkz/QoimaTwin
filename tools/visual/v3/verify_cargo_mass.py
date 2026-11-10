"""C07 mass ledger and synthetic manual handling boundary witnesses."""
import argparse
import copy
import json
import storage_eligibility as eligibility

ROOT=eligibility.ROOT
OUT=ROOT/"docs/v3/contract-proposals/cargo-mass-cases-v3.json"


def build():
    catalog,storage=[eligibility.read(p) for p in eligibility.INPUTS]
    modules={m["module_id"]:m for m in storage["modules"]}
    ledgers=[];heavy=[]
    for cargo in catalog["records"]:
        ledger=eligibility.mass_ledger(cargo)
        assert ledger["HU_gross_kg"]==cargo["handling_unit"]["gross_mass_kg"]
        ledgers.append(dict(archetype_id=cargo["archetype_id"],**ledger))
        if cargo["handling"]["modes"][0]["transport_tag"]=="forklift_assisted":
            slot=next(s for s in storage["slots"] if not s["retrieval_blocked"] and cargo["archetype_id"] in s["allowed_cargo_archetype_ids"] and s["storage_type"] in cargo["compatibility"]["storage_type_tags"])
            module=modules[slot["module_id"]]
            allowed=eligibility.evaluate(cargo,slot,module);assert allowed["design_eligible"]
            manual=eligibility.evaluate(cargo,slot,module,transport_tag="manual_hand_carry")
            unavailable=eligibility.evaluate(cargo,slot,module,handler_available=False)
            assert manual["reason"]==unavailable["reason"]=="HANDLER_UNAVAILABLE"
            shrunk=copy.deepcopy(cargo);shrunk["handling_unit"]["dimensions_xyz_m"]=[v*.1 for v in cargo["handling_unit"]["dimensions_xyz_m"]]
            assert eligibility.mass_ledger(shrunk)==ledger
            shrink_manual=eligibility.evaluate(shrunk,slot,module,transport_tag="manual_hand_carry")
            assert shrink_manual["reason"]=="HANDLER_UNAVAILABLE"
            heavy.append(dict(archetype_id=cargo["archetype_id"],forklift_design_candidate=allowed,
                forced_manual=manual,handler_absent=unavailable,shrunk_dimensions_do_not_reduce_mass_or_enable_manual=shrink_manual,
                shrink_scope="Invalid production dimension override used only as a mass-independence negative fixture; C09 must also reject the dimensions."))
    # Isolate handler mass from a slot payload limit in an explicit fixture.
    cargo=copy.deepcopy(catalog["records"][0]);slot=copy.deepcopy(next(s for s in storage["slots"] if s["storage_type"]=="FLEX" and not s["retrieval_blocked"]))
    module=copy.deepcopy(modules[slot["module_id"]]);slot["max_payload_kg"]=1000;module["max_module_payload_kg"]=1000
    def fixture_mass(value):
        c=copy.deepcopy(cargo);contents=float(eligibility.dec(value)-eligibility.dec(.1))
        c["unit"].update(contents_mass_kg=contents,packaging_tare_mass_kg=0,gross_mass_kg=contents)
        c["handling_unit"].update(units_per_handling_unit=1,contents_gross_mass_kg=contents,gross_mass_kg=value)
        return c
    boundary=[]
    for value in [15,15.0001]:
        c=fixture_mass(value);v=eligibility.evaluate(c,slot,module)
        assert v["design_eligible"]==(value==15)
        if value>15:assert v["reason"]=="OVERWEIGHT" and v["details"]["scope"]=="manual_handler"
        boundary.append(dict(HU_gross_mass_kg=value,actual=v))
    negatives=[]
    def bad(name,mutate,expected):
        c=copy.deepcopy(cargo);mutate(c)
        try:eligibility.mass_ledger(c)
        except ValueError as exc:
            assert str(exc)==expected,(name,exc);negatives.append(dict(case_id=name,reason=str(exc),passed=True));return
        raise AssertionError(name)
    bad("HU_tare_omitted",lambda c:c["handling_unit"].update(gross_mass_kg=.84),"MASS_ARITHMETIC_MISMATCH")
    bad("unit_primary_tare_omitted",lambda c:c["unit"].update(gross_mass_kg=.03),"MASS_ARITHMETIC_MISMATCH")
    bad("count_changed_without_mass",lambda c:c["handling_unit"].update(units_per_handling_unit=25),"MASS_ARITHMETIC_MISMATCH")
    bad("boolean_count",lambda c:c["handling_unit"].update(units_per_handling_unit=True),"INVALID_MASS")
    bad("fractional_count",lambda c:c["handling_unit"].update(units_per_handling_unit=1.5),"INVALID_MASS")
    bad("zero_count",lambda c:c["handling_unit"].update(units_per_handling_unit=0),"INVALID_MASS")
    bad("negative_tare",lambda c:c["handling_unit"].update(packaging_tare_mass_kg=-.1),"INVALID_MASS")
    bad("infinite_mass",lambda c:c["unit"].update(contents_mass_kg=float("inf")),"INVALID_MASS")
    bad("negative_contents",lambda c:c["unit"].update(contents_mass_kg=-.03),"INVALID_MASS")
    bad("contents_aggregate_changed",lambda c:c["handling_unit"].update(contents_gross_mass_kg=.2),"MASS_ARITHMETIC_MISMATCH")
    return dict(task_id="C07",source_kind="synthetic_design_witnesses",operational_admission=False,
        source_fingerprints=[dict(path=p.relative_to(ROOT).as_posix(),sha256=eligibility.sha(p)) for p in eligibility.INPUTS],
        production_ledgers=ledgers,heavy_handling_cases=heavy,manual_boundary_fixture=dict(
            not_a_production_template=True,synthetic_manual_limit_kg=15,not_a_legal_or_medical_limit=True,
            isolated_slot_payload_kg=1000,cases=boundary),invalid_mass_cases=negatives,
        actual_support_rating_and_source_scheduling="Required separately; eligible handler tag is not an actual physical pickup or engine operation.")


def main():
    p=argparse.ArgumentParser();p.add_argument("--check-only",action="store_true");a=p.parse_args();doc=build()
    if a.check_only:assert OUT.read_bytes()==eligibility.encoded(doc)
    else:
        OUT.write_bytes(eligibility.encoded(doc));e=dict(task_id="C07",owner="root",status="VERIFY",passed=True,
            artifact=dict(path=OUT.relative_to(ROOT).as_posix(),sha256=eligibility.sha(OUT),bytes=OUT.stat().st_size),
            exact_production_ledgers=8,heavy_handler_cases=6,invalid_mass_cases=len(doc["invalid_mass_cases"]),
            manual_boundary_cases=2,production_templates_unchanged=True)
        (ROOT/"docs/adaptive-v3/evidence/C07.json").write_bytes(eligibility.encoded(e))
    print(json.dumps(dict(passed=True,production_ledgers=8,heavy_cases=6,invalid_mass=len(doc["invalid_mass_cases"]),manual_boundary=2)))


if __name__=="__main__":main()
