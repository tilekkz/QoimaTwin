"""Declare a CPU-only blueprint; this script does not create a Blender mesh."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / "assets/v3/specs/forklift.dimensions.json"
INPUTS = [
    "docs/v3/contract-proposals/large-gate-v3.json",
    "docs/v3/contract-proposals/vehicle-handling-v3.json",
    "docs/v3/contract-proposals/cargo-catalog-v3.json",
    "assets/v3/specs/worker-base.dimensions.json",
    "assets/v3/specs/worker-rig-qa.json",
    "frontend/public/models/v3/worker-base.glb",
    "assets/references/v3/r06-forklift.png",
    "assets/references/v3/manifest.json",
    "assets/v3/iterations/forklift/M14.1/C08-before-physical-correction.json",
    "docs/v3/contract-proposals/storage-layout-v3.json",
    "assets/references/v3/r12-c08-interface-targets-v2.json",
]
read = lambda p: json.loads((ROOT / p).read_text(encoding="utf-8-sig"))
l05 = read(INPUTS[0])["vehicle_blueprint"]
c08 = read(INPUTS[1])
worker = read(INPUTS[3])
pose = {name: [0, 0, 0] for name in worker["joints"]}
for side, sign in (("L", 1), ("R", -1)):
    pose[f"joint__thigh_{side}"][0] = -math.pi / 2
    pose[f"joint__shin_{side}"][0] = math.pi / 2
    pose[f"joint__upper_arm_{side}"] = [-.55, 0, sign * .23]
    pose[f"joint__forearm_{side}"][0] = -1

boxes = []
def box(name, lo, hi, material, purpose, parent="forklift_root"):
    boxes.append(dict(name=name, min=lo, max=hi, material=material,
                      purpose=purpose, parent=parent))

box("chassis_rear_spine", [-.08, .16, -1.42], [.08, .52, -.69], "steel", "clear rear steered tyres")
box("chassis_front_spine", [-.19, .15, -.70], [.19, .53, -.05], "petrol", "central frame behind lift crossplate")
box("counterweight", [-.46, .50, -1.50], [.46, .92, -.93], "tan", "above rear tyre swept volume")
box("driver_floorboard", [-.30, .45, -.82], [.30, .53, -.02], "steel", "actual boot support top .53")
box("seat_pedestal", [-.20, .50, -.81], [.20, .77, -.64], "petrol", "seat joins floorboard and overlaps rear cushion10mm")
box("seat_cushion_rear", [-.22, .76, -.81], [.22, .84, -.65], "rubber", "pelvis rear underside bears on top .84")
box("seat_cushion_nose", [-.22, .74, -.655], [.22, .775, -.53], "rubber", "lowered shortened nose clears folded thighs and vertical shins")
box("seat_back", [-.215, .83, -.85], [.215, 1.40, -.760], "rubber", "back cushion with clothing clearance")
for sign, side in ((-1, "L"), (1, "R")):
    xr = sorted([sign * .29, sign * .60])
    box("entry_step_"+side, [xr[0], .30, -.68], [xr[1], .53, -.10], "petrol", "connected lateral foot step")
    xr = sorted([sign * .45, sign * .50])
    for end, zr in (("rear", [-1.05, -.96]), ("front", [-.10, -.04])):
        box(f"guard_{end}_{side}", [xr[0], .53, zr[0]], [xr[1], 2.05, zr[1]], "steel", "grounded guard joins frame and overlaps roof10mm")
    xr = sorted([sign * .20, sign * .28])
    box("mast_rail_"+side, [xr[0], .08, -.02], [xr[1], 2.10, .06], "steel", "twin connected fixed mast behind front tyres")
box("roof_guard", [-.50, 2.04, -1.15], [.50, 2.10, .15], "steel", "open-sided head guard, 50mm actual helmet clearance")
box("mast_top_crossmember", [-.28, 2.01, -.02], [.28, 2.10, .06], "steel", "connect twin rails")
box("mast_foot_rear_connection", [-.28, .08, -.10], [.28, .22, -.02], "steel", "join central chassis behind moving crossplate")
box("mast_foot_low_crossmember", [-.28, .08, -.025], [.28, .10, .06], "steel", "connect both mast rails below lowest carriage stop .11")
box("petrol_nose", [-.49, .50, -.15], [.49, .75, -.04], "petrol", "chunky fixed body ends behind moving lift crossplate")

wheels = []
for axle, z, radius, width in (("front", .40, .30, .24), ("rear", -1., .225, .20)):
    for sign, side in ((-1, "L"), (1, "R")):
        wheels.append(dict(id=f"{axle}_{side}", centre=[sign*.35, radius, z],
                           radius=radius, width=width, spin_axis="X",
                           steer_axis="Y" if axle == "rear" else None,
                           max_abs_steer_deg=75 if axle == "rear" else 0,
                           tyre_is_continuous_circular_cylinder=True,
                           parent=f"joint__rear_steer_{side}" if axle == "rear" else "forklift_root"))

joints = []
for w in wheels:
    if w["steer_axis"]:
        joints.append(dict(name=w["parent"], parent="forklift_root", position=w["centre"], axis="Y", limits=[-75,75], units="degrees"))
    joints.append(dict(name="joint__wheel_"+w["id"], parent=w["parent"], position=w["centre"], axis="X", limits=None, units="radians", position_space="vehicle_bind_world"))
joints.append(dict(name="joint__carriage", parent="forklift_root", position=[0,.70,.04], axis="Y", translation_range_m=[-.52,.80], meaning="fork top=.70+lift; stops .18..1.50"))
joints.append(dict(name="joint__reach", parent="joint__carriage", position=[0,.70,.40], axis="Z", translation_range_m=[0,.40], meaning="stopped handling only; travel at0. Fork heel=.40+reach; tips=1.50+reach"))
for sign, side in ((-1,"L"),(1,"R")):
    joints.append(dict(name="joint__fork_"+side, parent="joint__reach", position=[sign*.40,.70,.40], axis="X", translation_abs_centre_range_m=[.24,.40], meaning="no yaw/tilt or telescoping blade"))
joints.append(dict(name="joint__steering_wheel",parent="forklift_root",position=[0,1.2780096372028482,-.2534595793976674],axis="declared steering column axis",units="radians",purpose="visual control rotation; chassis follows L12 analytic path"))

plan = dict(
    schema="qoima-forklift-dimensions-v3.1", stage="M14.1", status="VERIFY",
    geometry_created=False, asset_id="forklift", namespace="v3", root_name="forklift_root",
    units="m", up_axis="Y", forward_axis="+Z", scale=[1,1,1],
    origin="floor centre of complete unloaded operating footprint, including forks and steered tyres",
    dimensions_xyz_m=[1.2,2.1,3], bounds={"min":[-.6,0,-1.5],"max":[.6,2.1,1.5]},
    reference={"reference_id":"R06","path":INPUTS[6],"actually_viewed":True,
               "authority":"blocky petrol body, tan counterweight/forks, charcoal guard/tyres; numeric L05/C08 overrides image proportions"},
    input_fingerprints=[dict(path=p,sha256=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()) for p in INPUTS],
    historical_blueprint={"fork_heel_z_m":l05["fork_heel_z_m"],"nominal_fork_top_y_m":.30,
        "front_axle_z_m":.40,"rear_axle_z_m":-1.,
        "contradiction":"historical .40 heel blade passes through both front tyre solids at every .24..40 half spacing"},
    approved_root_extension={"source":"published canonical C08v0.2.0, read after root final direction2026-11-07",
        "travel_physical_fork_heel_z_m":.40,"handling_physical_fork_heel_z_m":.80,
        "travel_direct_fork_top_y_m":.70,"LONG_travel_fork_top_y_m":.75,"LONG_travel_cradle_bottom_y_m":.65,
        "superseded_proposal":{"physical_heel_z_m":.75,"reason":"advancing blade alone does not clear low PALLET/IBC HU boxes; never canonical"},
        "rating_moment_reference_z_m":.40,"observed_or_certified_capacity_improvement_claimed":False,
        "unchanged":["axles","wheelbase","Ackermann steering","tyres","track","travel operating bounds","cargo dimensions/orientation","cradle own dimensions","rating values","travel fork heel/tip/blade length"],
        "canonical_C08_adoption":"v0.2.0 adopted; original v0.1 byte-exact snapshot retained in stage"},
    wheels=wheels, steering=l05["steering"],
    forks={"width_each_m":.08,"thickness_m":.07,"heel_z_m":.40,"tip_z_m":1.50,
        "blade_length_m":1.10,"half_spacing_range_m":[.24,.40],"nominal_direct_top_y_m":.70,
        "LONG_closed_pocket_top_y_m":.75,"max_handling_top_y_m":1.50,"min_handling_top_y_m":.18,
        "handling_reach_stroke_m":.40,"handling_heel_z_m":.80,"handling_tip_z_m":1.90,
        "physical_heel_to_PALLET_CoG_m":.60,"rating_moment_reference_z_m":.40,
        "minimum_supported_depth_fraction":2/3,"fork_tip_equals_HU_far_face":True,
        "future_vertical_stem_bounds":{"z_relative_heel":[-.025,0],"y_relative_top":[-.07,.30]},
        "collision_scope":"actual future rounded tips/blades/stems must fit these rectangular envelopes"},
    blueprint_boxes=boxes, joint_position_space="vehicle bind-world; derive local translation by subtracting parent bind-world position", joints=joints,
    dynamic_reach_frame={"rear_plate":{"x":[-.56,.56],"z":[0,.08],"y_relative_fork_top":[-.07,.16]},
        "side_guides":{"outer_x_abs":[.50,.56],"outer_z_fixed":[-.02,.62],"outer_y_relative_fork_top":[-.07,-.015],
            "outer_wall_thickness_m":.008,"inner_x_abs":[.512,.548],
            "inner_z_retracted":[-.02,.62],"inner_y_relative_fork_top":[-.0575,-.0275],
            "inner_translation_z_range_m":[0,.40],"minimum_full_extension_engagement_m":.24,
            "cross_section_air_each_side_x_m":.004,"cross_section_air_each_side_y_m":.0045,
            "outer_parent":"joint__carriage","inner_parent":"joint__reach",
            "all_rail_lengths_fixed_no_scale_animation":True},
        "forward_plate":{"x":[-.56,.56],"z_relative_heel":[-.04,0],"y_relative_fork_top":[-.07,.04]},
        "fixed_connection":"rear crossplate slides between fixed twin mast rails; two outboard side guides connect rear to forward crossplate; heel stems attach forward plate",
        "allowed_sequence":["travel: reach0/top.70 or LONG.75", "stop; extend at high top", "lower only at full reach.40", "engage/release load", "lift at full reach to high travel top", "retract only at high top"],
        "low_retracted_state_forbidden":True,"travel_graph_reach_must_equal_zero":True,
        "handling_envelope":{"bare_min":[-.60,0,-1.50],"bare_max":[.60,2.10,1.90],"loaded_height_rule":"fork top+HU height; may exceed travel2.10 only in separately cleared stopped handling volume"}},
    driver={"asset":INPUTS[5],"worker_height_m":1.70,"worker_geometry_unchanged":True,
        "worker_scale":[1,1,1],"seat_anchor_vehicle":[0,.84,-.65],
        "seat_contact_worker_bind":[0,.55,-.035],"worker_root_translation":[0,.29,-.615],
        "rotation_order":"native Three.js intrinsic Euler XYZ, radians",
        "jointEulerXYZ":pose,"pelvisShift":[0,0,0],
        "expected_grips":{"L":[-.24188875983010355,1.2780096372028482,-.2534595793976674],"R":[.24188875983010355,1.2780096372028482,-.2534595793976674]},
        "expected_soles":{"L":[-.11499999463558197,.53000003375113,-.39499998070299625],"R":[.11499999463558197,.53000003375113,-.39499998070299625]},
        "grip_bar_radius_m":.018,"grip_bar_length_m":.080,
        "grip_bar_axis":"actual posed hand local X; connected through rim to steering column",
        "steering_column":{"start":[0,.53,-.02],"end":[0,1.2780096372028482,-.2534595793976674],"radius_m":.035},
        "entry_clear_portal":{"x_plane_abs_m":.45,"y":[.53,2.04],"z":[-.96,-.10]},
        "entry_check_scope":"seated-pose lateral portal clearance only; walking/climbing sequence not yet accepted",
        "required_pose_tolerance_m":.00002,"minimum_helmet_roof_gap_m":.045},
    anchor_position_space="vehicle bind world, local translations derived by subtracting named parent bind world; preserve unit frames",
    anchor_parents={"anchor_floor_origin":"forklift_root","anchor_front_axle":"forklift_root","anchor_rear_axle":"forklift_root",
        "anchor_driver_seat":"forklift_root","anchor_footrest_L":"forklift_root","anchor_footrest_R":"forklift_root",
        "anchor_steering_grip_L":"joint__steering_wheel","anchor_steering_grip_R":"joint__steering_wheel",
        "anchor_fork_top_L":"joint__fork_L","anchor_fork_top_R":"joint__fork_R",
        "anchor_LONG_cradle":"joint__reach","anchor_LONG_load":"joint__reach"},
    anchors={"anchor_floor_origin":[0,0,0],"anchor_front_axle":[0,.30,.40],"anchor_rear_axle":[0,.225,-1.],
        "anchor_driver_seat":[0,.84,-.65],"anchor_footrest_L":[-.115,.53,-.395],"anchor_footrest_R":[.115,.53,-.395],
        "anchor_steering_grip_L":[-.24188875983010355,1.2780096372028482,-.2534595793976674],
        "anchor_steering_grip_R":[.24188875983010355,1.2780096372028482,-.2534595793976674],
        "anchor_fork_top_L":[-.40,.70,.95],"anchor_fork_top_R":[.40,.70,.95],
        "anchor_LONG_cradle":[0,.60,1.0],"anchor_LONG_load":[0,.75,1.0]},
    anchor_pose_targets={"LONG_travel":{"carriage_lift_m":.05,"reach_m":0,"cradle_vehicle":[0,.65,1],"HU_vehicle":[0,.80,1]},
        "LONG_lower_rack":{"carriage_lift_m":-.50,"reach_m":.40,"fork_top_y_m":.20,"cradle_vehicle":[0,.10,1.40],"HU_vehicle":[0,.25,1.40]}},
    long_attachment={**c08["long_cradle_design"],"separate_attachment_not_cargo":True,
        "travel_mount_origin_in_vehicle_m":[0,.65,1],"travel_HU_bottom_y_m":.80,
        "pocket_roof_contact_z_vehicle_m":[.575,1.425],"pocket_engagement_m":.85,
        "low_handling_pose":{"reach_m":.40,"fork_top_y_m":.40,"cradle_bottom_y_m":.30,"cradle_origin_z_m":1.40},
        "rear_wheel_clearance":"travel attachment bottom.65 clears tyremax.60; low handling requires Ztranslation+.40 before lowering",
        "positive_lock_plan":"two captive vertical pins through matching blade/roof/floor bores positively arrest fore-aft slide; independent upper bundle restraints",
        "lock_dimensions":{"pin_centres_own_xz_m":[[-.40,-.38],[.40,-.38]],
            "pin_shaft_radius_m":.008,"matching_bore_radius_m":.010,
            "pin_shaft_closed_y_own_m":[.005,.145],"recessed_cap_radius_m":.016,
            "recessed_cap_closed_y_own_m":[.125,.15],
            "fork_bore_centre_z_from_heel_m":.22,"fork_bore_axis":"Y",
            "lock_joint_names":["joint__cradle_lock_L","joint__cradle_lock_R"],
            "open_pin_translation_y_m":.11,
            "open_pin_enlarged_handling_height_own_m":.26,
            "pin_ear_outer_z_own_m":[-.402,-.358],"open_pin_lowest_y_own_m":.115,
            "HU_rear_z_own_m":-.325,"ear_to_HU_fore_aft_gap_m":.033,
            "travel_requires_both_pins_closed_and_bundle_restraints_closed":True,
            "source_scope":"dimension declaration; actual boolean bores, captive ears, pin sweeps/contact and strength remain later M14 attachment gate"},
        "pins_clamp_actual_geometry_and_retention":"pending M14 attachment child, no stress certificate",
        "M04_support_relief":"must consume actual M04 arm/pad channels; unresolved until paired mesh/contact proof"},
    ratings={**c08["rating_design"],"rating_reference_z_m":.40,"physical_travel_fork_heel_z_m":.40,
        "capacity_rule":c08["rating_design"]["capacity_rule"],"moment_budget_kg_m":800,"nominal_load_centre_m":.8,
        "one_frozen_rating_for_travel_and_stopped_reach":True,"same_frozen_rating_and_timings_for_later_AB":True,
        "no_outrigger_or_resource_increase":True,"certification":False,
        "approved_revision_source":"published C08v0.2.0",
        "historical_extended_IBC_conflict":{"mass_kg":654,"extended_reference_arm_m":1.0,"old_capacity_kg":600,"old_moment_budget_kg_m":600,"new_capacity_kg":800}},
    materials={"petrol":{"name":"V3_Forklift_Petrol","color":"#2E7376"},"tan":{"name":"V3_Forklift_Tan","color":"#C99A60"},
        "steel":{"name":"V3_Forklift_Charcoal","color":"#293D46"},"rubber":{"name":"V3_Forklift_Rubber","color":"#263238"}},
    renderer_or_runtime_used=False,
    staffing="F01/F02 existing typed driver actors are seated clones of unchanged worker-base at vehicle seat; not two additional people",
    storage_contact_height_scope={"HEAVY_min":.18,"STANDARD_active_levels":[.20,1.40],"LONG_HU_bottom":.25,
        "LONG_fork_top_when_cradle_roof_at_HU_bottom":.20,"unsupported_floor_HU_pickup_admitted":False,
        "proof_scope":"height reach only; lanes, rack arms, clamps, HU base contacts and approach footprint require actual paired M/P proof"},
    deferred=["extended pickup/setdown swept action and actual contact proof",
        "actual forklift mesh silhouette/material/source/GLB gates", "all body/wheel/mast actual joins and swept steer tests",
        "cradle through-pockets/clamps/straps/rack relief actual contact/transfer", "seated-driver actual paired views and controls",
        "walking/climbing entry animation", "source scheduling, business simulation, real equipment certification"])
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(OUT.relative_to(ROOT))
