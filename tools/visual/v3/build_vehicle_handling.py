"""C08: frozen synthetic handling design and loaded route eligibility.

Design acceptance is deliberately separate from M/P actual mesh/action evidence.
No inventory, durations, score, or operating resource is created here.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "docs/v3/contract-proposals"
OUT = BASE / "vehicle-handling-v3.json"
INPUTS = [BASE / n for n in ["cargo-catalog-v3.json", "large-gate-v3.json",
    "vehicle-graph-v3.json", "storage-layout-v3.json", "layout-links-v3.json",
    "ports-v3.inbound.json", "ports-v3.outbound.json", "port-resource-policy-v3.json"]]
INPUTS += [ROOT / "assets/references/v3/r12-dimension-targets.json"]
FORKLIFT_CARGO = ["HEAVY_BOX", "PALLET_LOAD", "IBC", "LONG_BUNDLE", "DRUM", "FRAGILE_CRATE"]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def contained(inner, outer):
    return all(outer["min"][i] - 1e-9 <= inner["min"][i] <= inner["max"][i] <= outer["max"][i] + 1e-9 for i in range(3))


def bounds(dims, base_y, centre_z):
    w, h, d = dims
    return {"min": [-w / 2, base_y, centre_z - d / 2],
            "max": [w / 2, base_y + h, centre_z + d / 2]}


def make():
    catalog, blueprint, graph, storage, links = [read(p) for p in INPUTS[:5]]
    records = {r["archetype_id"]: r for r in catalog["records"]}
    profiles = {p["profile_id"]: p for p in graph["profiles"]}
    bare = blueprint["vehicle_blueprint"]["bounds_local_m"]
    effective_long=copy.deepcopy(profiles["loaded_max"]["component_bounds_local_m"])
    # Explicit vertical extension of the same XZ sweeps, all below unchanged2.10m.
    effective_long[1]["min"][1],effective_long[1]["max"][1]=.65,.80
    effective_long[2]["min"][1],effective_long[2]["max"][1]=.80,1.32
    for old,new in zip(profiles["loaded_max"]["component_bounds_local_m"],effective_long):
        assert all(old[end][axis]==new[end][axis] for end in ["min","max"] for axis in [0,2])
        assert 0<=new["min"][1]<=new["max"][1]<=bare["max"][1]
    loads = []
    for aid in FORKLIFT_CARGO:
        hu = records[aid]["handling_unit"]
        is_long = aid == "LONG_BUNDLE"
        # Fixed fork tip at1.50; nonlong far HU face ends at the tip. No telescoping.
        centre_z = 1.0 if is_long else 1.5 - hu["dimensions_xyz_m"][2] / 2
        bottom = .80 if is_long else .70
        cargo_bounds = bounds(hu["dimensions_xyz_m"], bottom, centre_z)
        attachment_mass = 40 if is_long else 0
        mass = hu["gross_mass_kg"] + attachment_mass
        cog_y = (hu["gross_mass_kg"] * (bottom + hu["dimensions_xyz_m"][1] / 2) + attachment_mass * .715) / mass
        centre = centre_z - .4
        capacity = min(1000.0, 800.0 / centre)
        components = [copy.deepcopy(bare), cargo_bounds]
        if is_long:
            components.insert(1, copy.deepcopy(effective_long[1]))
        main_profile = effective_long
        local_profile = effective_long if is_long else storage["access_profiles"]["nonlong_forklift"]["component_bounds_local_m"]
        assert all(any(contained(b, q) for q in main_profile) for b in components), aid
        assert all(any(contained(b, q) for q in local_profile) for b in components), aid
        loads.append(dict(archetype_id=aid, handling_unit_dimensions_xyz_m=hu["dimensions_xyz_m"],
            HU_gross_mass_kg=hu["gross_mass_kg"], attachment_mass_kg=attachment_mass,
            total_lifted_mass_kg=mass, cog_local_xyz_m=[0, cog_y, centre_z],
            load_centre_from_fork_heel_m=centre, declared_capacity_at_this_centre_kg=capacity,
            extended_handling_rating_arm_from_fixed_Z04_m=centre+.40,
            extended_handling_capacity_kg=min(1000,800/(centre+.40)),
            orientation_id="upright_xyz", scale_factor=1, cargo_bounds_local_m=cargo_bounds,
            component_bounds_local_m=components, local_geometry_profile_id="long_loaded" if is_long else "nonlong_forklift",
            main_geometry_profile_id="loaded_max", fork_top_travel_y_m=.75 if is_long else .70,
            fork_centres_x_m=[-.4, .4] if is_long or aid in ["PALLET_LOAD", "IBC", "FRAGILE_CRATE"] else [-.24, .24],
            support_design="positive_locked_long_cradle" if is_long else "two_forks_under_unchanged_HU_base",
            support_assumption_scope="Synthetic design target; actual mesh/contacts/retention/transfer need bound M/P evidence.",
            component_containment_verified=True))
    arcs = links["vehicle_graph"]["arcs"]
    port_profiles=[]
    for source in INPUTS[5:7]:
        for port in read(source)["ports"]:
            forklift_requirements=[r for r in port["resource_requirements"] if r.get("forklift_pair_ref")]
            port_profiles.append(dict(port_id=port["port_id"],direction=port["direction"],
                allowed_cargo_archetype_ids=port["allowed_cargo_archetype_ids"],
                forklift_cargo_archetype_ids=sorted({c for r in forklift_requirements for c in r["cargo_archetype_ids"]}),
                equipment_pair_ref=next((r["forklift_pair_ref"] for r in forklift_requirements),None),
                clear_width_m=port["clear_width_m"],clear_height_m=port["clear_height_m"],
                straight_crossing_only=True, source_path=source.relative_to(ROOT).as_posix()))
    eligibility = []
    for load in loads:
        allowed, rejected = [], []
        for arc in arcs:
            why = arc_reason(load, arc)
            (rejected if why else allowed).append({"arc_id": arc["arc_id"], "reason": why} if why else arc["arc_id"])
        eligibility.append(dict(archetype_id=load["archetype_id"], allowed_arc_ids=allowed, rejected_arcs=rejected))
    return dict(schema_id="qoima.vehicle-handling.v3-design", schema_version="0.2.0", source_kind="synthetic_design",
        status="design_contract", operational_admission=False, actual_model_actions_verified=False,
        layout_content_hash=catalog["layout_binding"]["layout_content_hash"],
        source_fingerprints=[dict(path=p.relative_to(ROOT).as_posix(), sha256=sha(p)) for p in INPUTS],
        invariants=dict(unit_scale=1, up_axis="Y", vehicle_forward="+Z", people=24, vehicles=2,
            reserve_retrieval_blocked=188, no_relative_load_yaw_or_tilt=True,
            no_in_place_rotation=True, reverse_preserves_chassis_yaw=True,
            eligibility_before_cost=True, shared_contracts_changed=False),
        rating_design=dict(source_kind="synthetic_design", certification=False, nominal_capacity_kg=1000,
            nominal_load_centre_m=.8, capacity_rule="min(1000,800/rating_arm_about_fixed_chassis_Z04_m)",
            moment_budget_kg_m=800, rating_reference_z_m=.40,
            maximum_fork_top_handling_y_m=1.5, maximum_single_fork_share_kg=500,
            restricted_to_symmetrical_centre_of_gravity=True,
            frozen_selection="Replaces v0.1 600kgm before stock/optimization: extended654kg IBC at1.0m needs explicit larger declared design. Same rating in both A/B cases; not a measured improvement.",
            reach_rule="Reach shifts load AND fork heel forward. Physical fork load-centre is unchanged, but moment arm about fixed chassis reference increases by .40m; capacity must use that increased arm.",
            meaning="Declared simulation equipment rating, not calculated structural stability or a real manufacturer's capacity plate."),
        fork_design=dict(width_each_m=.08, thickness_m=.07, heel_z_m=.4, tip_z_m=1.5,
            adjustable_abs_centre_x_range_m=[.24, .40], bare_and_direct_load_travel_top_y_m=.70,
            LONG_closed_pocket_travel_top_y_m=.75,
            stopped_handling_reach_stroke_m=.40, extended_handling_heel_z_m=.80, extended_handling_tip_z_m=1.90,
            travel_reach_extension_m=0,
            L05_extension="Historical .30m fork top collides with front tyres. All travel forks are high(.70/.75), unchanged heel.40/tip1.50. Low handling extends a real carriage+.40 only while stopped; its enlarged footprint needs actual M14.8 action proof and never enters travel edges."),
        geometry_profile_extensions=dict(loaded_max=effective_long,long_loaded=effective_long,empty_cradle=effective_long[:2],
            authority="C08v0.2 vertical operating extension, unchanged accepted source files.",
            proof="Same per-component XZ bounds as L05/L07/L09, nonnegativeY and maxwholeheight2.10 unchanged. L07/L09/L11 ground-obstacle swept polygons, continuous yaw inflation, clear widths and maximum-height proofs are unchanged; this is NOT old3D component containment. M/P physical collision proof is separate."),
        long_cradle_design=dict(attachment_id="v3:attachment:long-cradle:01", own_dimensions_xyz_m=[3.2,.15,.85],
            mount_origin_in_vehicle_m=[0,.65,1], mass_kg=40, own_cog_xyz_m=[0,.065,0],
            pocket_centres_x_m=[-.4,.4], pocket_inner_width_m=.14, pocket_inner_y_range_own_m=[.02,.10],
            blade_y_range_own_m=[.03,.10], free_floor_gap_m=.01,
            positive_lock="Two retained rear pins/ears plus independent visible load restraint; missing lock or restraint rejects.",
            positive_pin_design=dict(bore_radius_m=.010,pin_radius_m=.008,centres_x_m=[-.40,.40],
                own_z_m=-.38,vehicle_travel_z_m=.62,vehicle_extended_z_m=1.02,
                pin_closed_y_own_m=[.005,.15],open_retraction_m=.11,
                open_allowed_only_stopped=True,actual_mesh_and_strength_approval=False),
            support_pad_centres_x_m=[-1.4,1.4], pad_width_m=.20, support_span_m=2.8,
            HU_end_distance_from_pad_centre_m=.7, HU_frame_end_overhang_m=.5,
            declared_payload_limit_kg=600, allowed_HU="LONG_BUNDLE",
            support_approval="Synthetic rigid restrained bundle with fixed symmetric CoG; no general beam stress certification.",
            transfer_interface="Actual M04/M14 must provide arm/pad/pocket relief and verify lower rack plane .25m before any transfer. No continuous deck through cradle pads; upper12 LONG addresses stay blocked."),
        direct_support_design=dict(required_contacts=2, fork_tip_equals_HU_far_face=True,
            HU_base_must_be_supported_without_scale=True,
            pickup_rule="Fixed support/buffer must leave actual open fork approach channels below HU support plane. Solid full deck or ground-resting solid HU without fork access rejects transfer.",
            slot_bottom_rule="HU bottom remains exact C04 supportY; no extra carrier silently inserted underneath stored HU.",
            model_requirements="M03 low base may use three deck ribs and two open top fork lanes, preserving outer/support/usable bounds. Actual M/P triangles must prove fork clearance and contacts; reference broad deck is not solid geometry authority."),
        stopped_reach_handling_design=dict(not_a_transit_profile=True,extension_m=.40,
            minimum_fork_top_y_m=.18,maximum_fork_top_y_m=1.50,
            allowed_sequence=["stop_and_reserve_action_space","extend_high","lower_extended","engage_or_release","lift_extended_to_travel_height","retract_high"],
            release_sequence="After setdown, reverse withdraw with carriage extended; lift empty forks before full retraction.",
            prohibitions=["low_retracted_forks","extended_or_low_transit","lowering_before_extension","retraction_before_lift"],
            required_actual_proof="M14.8 continuous actual fork/carriage/tyre/HU/rack/traffic contacts and state timestamps, plus exclusive operator/vehicle/action space. A declared sequence is not an implemented action.",
            mechanism="Connected twin mast/side reach guides and carriage. Low side guides outside front tyres; rear crossplate behind tyres and front plate ahead when low; actual model must prove all intermediate poses."),
        loads=loads, ports=port_profiles, per_cargo_arc_eligibility=eligibility,
        route_policy=dict(empty_bare="unloaded_bare", attached_empty="empty_cradle",
            loaded_main="loaded_max", conservative_policy="Never admit cargo onto bare-only edges even if its projected AABB fits.",
            analytic_pose_rule=graph["geometry_evaluation"],
            reservations="Existing L12 traffic groups and actual pair/operator availability must be held by source scheduler.",
            action_evidence_requirement="Matching actual M/P mesh hashes and contact/lock/support proofs; a design verdict alone cannot start an operation."),
        deferred=["M/P actual meshes, cavity/contact/lock/transfer tests", "W source scheduling/traffic and actual jobs", "Backend integration and throughput"])


def arc_reason(load, arc):
    if load["archetype_id"] not in arc["allowed_cargo_archetype_ids"]:
        return "CARGO_TYPE_MISMATCH"
    permitted = arc["allowed_geometry_profile_ids"]
    if load["main_geometry_profile_id"] not in permitted and load["local_geometry_profile_id"] not in permitted:
        return "PATH_CLEARANCE"
    top = max(b["max"][1] for b in load["component_bounds_local_m"])
    if top + .25 > arc["clear_height_m"] + 1e-9:
        return "PATH_CLEARANCE"
    width=max(b["max"][0] for b in load["component_bounds_local_m"])-min(b["min"][0] for b in load["component_bounds_local_m"])
    if "clear_width_m" in arc and width+.5>arc["clear_width_m"]+1e-9:
        return "PATH_CLEARANCE"
    return None


def rated_mass_eligible(design, mass, arm):
    rating=design["rating_design"]
    if type(mass) not in (int,float) or type(arm) not in (int,float) or not math.isfinite(mass) or not math.isfinite(arm) or mass<=0 or arm<=0:
        return False
    capacity=min(rating["nominal_capacity_kg"],rating["moment_budget_kg_m"]/arm)
    return mass<=capacity and mass/2<=rating["maximum_single_fork_share_kg"]


def candidate(design, job, arc, port=None):
    """Analytical design eligibility only. No score or operational admission."""
    def reject(reason):
        return dict(design_eligible=False, reason=reason, operational_admission=False, cost_evaluated=False)
    load = next((l for l in design["loads"] if l["archetype_id"] == job.get("archetype_id")), None)
    if load is None:
        return reject("HANDLER_UNAVAILABLE")
    if type(job.get("scale_factor")) not in (int,float) or job.get("scale_factor") != 1 or job.get("dimensions_xyz_m") != load["handling_unit_dimensions_xyz_m"]:
        return reject("DIMENSION_MISMATCH")
    if job.get("orientation_id") != "upright_xyz" or job.get("relative_yaw_rad") != 0 or job.get("relative_tilt_rad") != 0:
        return reject("ORIENTATION_FORBIDDEN")
    if job.get("HU_mass_kg") != load["HU_gross_mass_kg"]:
        return reject("MASS_MISMATCH")
    if job.get("motion_state")!="travel" or job.get("reach_extension_z_m")!=0:
        return reject("HANDLING_STATE_NOT_TRANSIT")
    centre = job.get("load_centre_m")
    if not isinstance(centre, (int,float)) or not math.isfinite(centre) or centre <= 0 or centre != load["load_centre_from_fork_heel_m"]:
        return reject("LOAD_CENTRE_MISMATCH")
    lifted = job["HU_mass_kg"] + load["attachment_mass_kg"]
    if not rated_mass_eligible(design,lifted,centre):
        return reject("OVERWEIGHT")
    if not job.get("support_verified") or not job.get("retention_verified"):
        return reject("SUPPORT_UNAVAILABLE")
    if load["archetype_id"] == "LONG_BUNDLE" and not job.get("attachment_locked"):
        return reject("ATTACHMENT_UNLOCKED")
    if job.get("fork_top_y_m") != load["fork_top_travel_y_m"]:
        return reject("FORK_ENGAGEMENT_MISMATCH")
    pair = job.get("equipment_pair_ref")
    if pair not in arc["equipment_pair_refs"]:
        return reject("HANDLER_UNAVAILABLE")
    why = arc_reason(load,arc)
    if why:
        return reject(why)
    if port is not None:
        if load["archetype_id"] not in port["allowed_cargo_archetype_ids"]:
            return reject("PORT_CARGO_FORBIDDEN")
        if load["archetype_id"] not in port["forklift_cargo_archetype_ids"]:
            return reject("HANDLER_UNAVAILABLE")
        if pair != port["equipment_pair_ref"]:
            return reject("HANDLER_UNAVAILABLE")
        # Cross gate straight, centre-aligned, chassis+load yaw together.
        w = max(b["max"][0] for b in load["component_bounds_local_m"]) - min(b["min"][0] for b in load["component_bounds_local_m"])
        h = max(b["max"][1] for b in load["component_bounds_local_m"])
        if w+.5 > port["clear_width_m"]+1e-9 or h+.25 > port["clear_height_m"]+1e-9 or not job.get("gate_aligned"):
            return reject("PATH_CLEARANCE")
    return dict(design_eligible=True, reason="DESIGN_GEOMETRY_ELIGIBLE", operational_admission=False,
        actual_mesh_actions_verified=False, cost_evaluated=False)


def mechanical_blueprint_checks(design):
    """Exact front-tyre cylinder vs box witnesses, not actual M14 mesh proof."""
    def hits_front_tyres(box):
        for centre_x in [-.35,.35]:
            if box["max"][0]<=centre_x-.12 or box["min"][0]>=centre_x+.12:continue
            dy=max(box["min"][1]-.30,0,.30-box["max"][1])
            dz=max(box["min"][2]-.40,0,.40-box["max"][2])
            if dy*dy+dz*dz<.30**2:return True
        return False
    old_fork=dict(min=[.36,.23,.40],max=[.44,.30,1.50])
    assert hits_front_tyres(old_fork)
    old_HU= bounds([1.2,1.35,1.0],.30,1.0)
    assert hits_front_tyres(old_HU)
    # Entire continuous spacing/reach interval is enclosed; high Y or forward Z
    # separation proves all intermediate states, without sparse sampling.
    high_sweep=dict(min=[-.44,.63,.40],max=[.44,.75,1.90])
    low_extended_sweep=dict(min=[-.44,.03,.80],max=[.44,1.50,1.90])
    assert not hits_front_tyres(high_sweep) and not hits_front_tyres(low_extended_sweep)
    for load in design["loads"]:
        for component in load["component_bounds_local_m"][1:]:
            assert not hits_front_tyres(component),(load["archetype_id"],component)
            extended=copy.deepcopy(component)
            extended["min"][1]=0;extended["max"][1]=2.10
            extended["min"][2]+=.40;extended["max"][2]+=.40
            assert not hits_front_tyres(extended)
        assert load["total_lifted_mass_kg"]<=load["extended_handling_capacity_kg"]
    # The old declared moment budget really rejected the unchanged extended IBC.
    ibc=next(l for l in design["loads"] if l["archetype_id"]=="IBC")
    assert 600/ibc["extended_handling_rating_arm_from_fixed_Z04_m"]<ibc["total_lifted_mass_kg"]<=ibc["extended_handling_capacity_kg"]
    assert not rated_mass_eligible(design,801,1.0)
    assert not rated_mass_eligible(design,1001,.20)
    assert rated_mass_eligible(design,654,1.0)
    return dict(method="Analytic front tyre finite-X cylinder vs complete rectangular sweeps",
        historical_low_fork_collision_detected=True,historical_low_PALLET_IBC_collision_detected=True,
        whole_spacing_high_reach_sweep_clear=True,whole_low_extended_height_sweep_clear=True,
        all_travel_cargo_and_cradle_clear=True,all_low_extended_cargo_XZ_clear=True,
        old_600kgm_extended_IBC_rejected=True,new_800kgm_all_extended_loads_fit=True,
        actual_reach_rails_driver_mesh_and_action_verified=False)


def checks(design):
    graph=read(INPUTS[4])["vehicle_graph"]
    all_arcs=graph["arcs"]
    load=next(l for l in design["loads"] if l["archetype_id"]=="LONG_BUNDLE")
    arc=next(a for a in all_arcs if a["source"]=="L07" and not arc_reason(load,a))
    job=dict(archetype_id="LONG_BUNDLE",scale_factor=1,dimensions_xyz_m=[4.2,.52,.65],
        orientation_id="upright_xyz",relative_yaw_rad=0,relative_tilt_rad=0,HU_mass_kg=200,
        load_centre_m=.6,support_verified=True,retention_verified=True,attachment_locked=True,
        fork_top_y_m=.75,equipment_pair_ref="INBOUND_FORKLIFT_PAIR",gate_aligned=True,
        motion_state="travel",reach_extension_z_m=0)
    gate=next(p for p in design["ports"] if p["port_id"]=="IN_W_BULK")
    assert candidate(design,job,arc,gate)["design_eligible"]
    cases=[]
    def negative(name, expected, change_job=None, change_arc=None, change_port=None):
        j,a,p=copy.deepcopy(job),copy.deepcopy(arc),copy.deepcopy(gate)
        if change_job:change_job(j)
        if change_arc:change_arc(a)
        if change_port:change_port(p)
        result=candidate(design,j,a,p)
        assert result["reason"]==expected and not result["design_eligible"] and not result["cost_evaluated"], (name,result)
        cases.append(dict(case_id=name,reason=expected,passed=True))
    negative("scale","DIMENSION_MISMATCH",lambda j:j.update(scale_factor=.5))
    negative("boolean_scale","DIMENSION_MISMATCH",lambda j:j.update(scale_factor=True))
    negative("dimension","DIMENSION_MISMATCH",lambda j:j.update(dimensions_xyz_m=[2.1,.52,.65]))
    negative("relative_yaw","ORIENTATION_FORBIDDEN",lambda j:j.update(relative_yaw_rad=math.pi/2))
    negative("tilt","ORIENTATION_FORBIDDEN",lambda j:j.update(relative_tilt_rad=.1))
    negative("orientation","ORIENTATION_FORBIDDEN",lambda j:j.update(orientation_id="sideways"))
    negative("mass_changed","MASS_MISMATCH",lambda j:j.update(HU_mass_kg=2))
    negative("centre_nan","LOAD_CENTRE_MISMATCH",lambda j:j.update(load_centre_m=float("nan")))
    negative("centre_shift","LOAD_CENTRE_MISMATCH",lambda j:j.update(load_centre_m=.5))
    negative("missing_support","SUPPORT_UNAVAILABLE",lambda j:j.update(support_verified=False))
    negative("missing_retention","SUPPORT_UNAVAILABLE",lambda j:j.update(retention_verified=False))
    negative("unlocked","ATTACHMENT_UNLOCKED",lambda j:j.update(attachment_locked=False))
    negative("nominal_fork_not_in_pocket","FORK_ENGAGEMENT_MISMATCH",lambda j:j.update(fork_top_y_m=.3))
    negative("extended_carriage_not_transit","HANDLING_STATE_NOT_TRANSIT",lambda j:j.update(reach_extension_z_m=.4))
    negative("stopped_handling_not_transit","HANDLING_STATE_NOT_TRANSIT",lambda j:j.update(motion_state="handling"))
    negative("missing_pair","HANDLER_UNAVAILABLE",lambda j:j.update(equipment_pair_ref=None))
    negative("bare_only_edge","PATH_CLEARANCE",change_arc=lambda a:a.update(allowed_geometry_profile_ids=["unloaded_bare"]))
    negative("edge_cargo","CARGO_TYPE_MISMATCH",change_arc=lambda a:a.update(allowed_cargo_archetype_ids=[]))
    negative("edge_height","PATH_CLEARANCE",change_arc=lambda a:a.update(clear_height_m=2.2))
    negative("edge_width","PATH_CLEARANCE",change_arc=lambda a:a.update(clear_width_m=4.4))
    negative("narrow_gate","PATH_CLEARANCE",change_port=lambda p:p.update(clear_width_m=4.4))
    negative("low_gate","PATH_CLEARANCE",change_port=lambda p:p.update(clear_height_m=2.2))
    negative("gate_forbidden_despite_width","PORT_CARGO_FORBIDDEN",change_port=lambda p:p.update(allowed_cargo_archetype_ids=["PALLET_LOAD"],clear_width_m=6))
    negative("wrong_direction_pair","HANDLER_UNAVAILABLE",change_port=lambda p:p.update(equipment_pair_ref="OUTBOUND_FORKLIFT_PAIR"))
    negative("turn_in_aperture","PATH_CLEARANCE",lambda j:j.update(gate_aligned=False))
    # Same catalog HU/cradle, deliberately insufficient equipment rating.
    mutated=copy.deepcopy(design);mutated["rating_design"]["nominal_capacity_kg"]=100
    assert candidate(mutated,job,arc,gate)["reason"]=="OVERWEIGHT"
    cases.append(dict(case_id="overweight_at_actual_load_centre",reason="OVERWEIGHT",passed=True))
    port_matrix=[]
    for p in design["ports"]:
        for l in design["loads"]:
            j=copy.deepcopy(job);j.update(archetype_id=l["archetype_id"],dimensions_xyz_m=l["handling_unit_dimensions_xyz_m"],
                HU_mass_kg=l["HU_gross_mass_kg"],load_centre_m=l["load_centre_from_fork_heel_m"],
                fork_top_y_m=l["fork_top_travel_y_m"],equipment_pair_ref=p["equipment_pair_ref"] or "INBOUND_FORKLIFT_PAIR")
            result=candidate(design,j,arc,p)
            expected=l["archetype_id"] in p["forklift_cargo_archetype_ids"]
            assert result["design_eligible"]==expected,(p["port_id"],l["archetype_id"],result)
            port_matrix.append(dict(port_id=p["port_id"],archetype_id=l["archetype_id"],**result))
    counts=[]
    for item in design["per_cargo_arc_eligibility"]:
        assert len(item["allowed_arc_ids"])+len(item["rejected_arcs"])==len(all_arcs)
        assert item["allowed_arc_ids"]
        counts.append(dict(archetype_id=item["archetype_id"],allowed=len(item["allowed_arc_ids"]),rejected=len(item["rejected_arcs"])))
    # All reverse geometry keeps explicit analytic start/end yaw from source.
    assert design["route_policy"]["analytic_pose_rule"]["no_in_place_rotation"] is True
    assert design["fork_design"]["thickness_m"]==read(INPUTS[1])["vehicle_blueprint"]["fork_thickness_m"]
    assert all(l["total_lifted_mass_kg"]<=l["declared_capacity_at_this_centre_kg"] for l in design["loads"])
    assert .75-.07 >= .65+.02 and math.isclose(.65+.10,.75)
    return dict(passed=True,negative_cases=cases,compiled_arcs=len(all_arcs),per_cargo=counts,port_matrix=port_matrix,
        exact_catalog_dimensions_and_masses=True,effective_profile_component_containment=True,
        source_component_XZ_and_whole_height_equivalence=True,mechanical_blueprint_checks=mechanical_blueprint_checks(design),
        actual_model_action_acceptance=False,operational_admission=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--check-only",action="store_true");args=parser.parse_args()
    design=make();result=checks(design)
    if args.check_only:
        assert OUT.read_bytes()==encoded(design), "Frozen contract differs from deterministic sources/design"
    else:
        OUT.write_bytes(encoded(design))
        evidence=dict(task_id="C08",owner="root",status="VERIFY",contract=dict(path=OUT.relative_to(ROOT).as_posix(),sha256=sha(OUT),bytes=OUT.stat().st_size),
            builder_sha256=sha(Path(__file__)),checks=result,limits="Synthetic analytical design, not M/P physical action or W engine acceptance.")
        (ROOT/"docs/adaptive-v3/evidence/C08.json").write_bytes(encoded(evidence))
    print(json.dumps(result,separators=(",",":")))


if __name__=="__main__":main()
