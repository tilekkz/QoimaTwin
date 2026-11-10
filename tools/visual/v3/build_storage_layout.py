"""Deterministic numeric L09 layout; no Blender, meshes, backend or shared edits."""
from __future__ import annotations

import argparse
import collections
import hashlib
import html
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/v3/contract-proposals/storage-layout-v3.json"
EVIDENCE = ROOT / "docs/adaptive-v3/evidence/L09.json"
SVG = ROOT / "docs/adaptive-v3/evidence/L09-storage-plan.svg"

# Declared before placement. XYZ metres; +Z faces the aisle. Synthetic kg limits
# rate proposed storage only, never a forklift. Upper levels are blocked reserve.
MODULES = {
    "SMALL": dict(outer=[2.4, 1.55, 1.0], usable=[.42, .35, .42],
                  levels=[.25, 1.0], bays=[-.88, -.44, 0, .44, .88],
                  payload=15, module_payload=150, clearance=.03,
                  cargo=["SMALL_CARTON"]),
    "STANDARD": dict(outer=[2.8, 3.85, 1.4], usable=[1.25, 1.05, 1.1],
                     levels=[.2, 1.4, 2.6], bays=[-.7, .7],
                     payload=250, module_payload=1500, clearance=.05,
                     cargo=["STANDARD_CARTON", "FRAGILE_CRATE"]),
    "HEAVY": dict(outer=[1.6, .18, 1.4], operating_height=1.8,
                  usable=[1.4, 1.5, 1.2], levels=[.18], bays=[0],
                  payload=1000, module_payload=1000, clearance=.05,
                  cargo=["HEAVY_BOX", "PALLET_LOAD", "IBC", "DRUM"]),
    "LONG": dict(outer=[4.8, 2.2, 1.3], usable=[4.4, .65, .9],
                 levels=[.25, 1.3], bays=[0],
                 payload=600, module_payload=1200, clearance=.05,
                 cargo=["LONG_BUNDLE"]),
    "FLEX": dict(outer=[1.6, .85, 1.2], usable=[1.4, .6, 1.0],
                 levels=[.18], bays=[0], payload=15, module_payload=15,
                 clearance=.05, cargo=["SMALL_CARTON", "STANDARD_CARTON"]),
}
# Local structural bounds keep the declared useful cavities clear. These are
# geometric construction targets for later meshes, not structural certification.
for family, thickness, xs, zs in [
    ("SMALL", .10, [-1.15, 1.15], [-.45, .45]),
    ("STANDARD", .07, [-1.365, 0, 1.365], [-.65, .65]),
    ("LONG", .16, [-1.6, 0, 1.6], [-.55]),
    ("FLEX", .10, [-.75, .75], [-.55]),
]:
    d = MODULES[family]
    d["construction"] = dict(
        posts=[dict(min=[x-thickness/2,0,z-thickness/2],
                    max=[x+thickness/2,d["outer"][1],z+thickness/2])
               for x in xs for z in zs],
        deck_thickness_m=.10 if family in ["SMALL","STANDARD"] else .12 if family=="LONG" else .04,
        deck_top_y_m=d["levels"],
        meaning="Connected posts/decks/supports. LONG has three rear posts and cantilever arms. FLEX front stays open.")
MODULES["HEAVY"]["construction"] = dict(
    open_top=True, base_height_m=.18, deck_thickness_m=.04,
    runner_count=3, block_count=9, fork_pocket_centres_x_m=[-.4,.4],
    fork_pocket_clear_height_m=.10, fork_pocket_clear_width_m=.18,
    posts=[], meaning="Open reinforced ground support; no tall enclosing mesh. C08 still approves actual support and forks.")
SOURCES = [
    "docs/v3/contract-proposals/layout-v3.zones.json",
    "docs/v3/contract-proposals/pedestrian-graph-v3.json",
    "docs/v3/contract-proposals/vehicle-graph-v3.json",
    "docs/v3/contract-proposals/large-gate-v3.json",
    "assets/references/v3/r03-dimension-targets.json",
]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def world(local, pos, yaw):
    x, y, z = local
    c, s = math.cos(yaw), math.sin(yaw)
    return [pos[0] + x*c + z*s, pos[1] + y, pos[2] - x*s + z*c]


def box_world(lo, hi, pos, yaw):
    points = [world(q, pos, yaw) for q in itertools.product(
        [lo[0], hi[0]], [lo[1], hi[1]], [lo[2], hi[2]])]
    return dict(min=[min(q[i] for q in points) for i in range(3)],
                max=[max(q[i] for q in points) for i in range(3)])


def floor_rect(bounds):
    return [bounds["min"][0], bounds["min"][2],
            bounds["max"][0], bounds["max"][2]]


def overlap(a, b, eps=1e-8):
    return (min(a[2], b[2]) - max(a[0], b[0]) > eps and
            min(a[3], b[3]) - max(a[1], b[1]) > eps)


class Layout:
    def __init__(self):
        self.zones = {q["zone_id"]: q for q in read(SOURCES[0])["zones"]}
        self.ped = read(SOURCES[1])
        self.vehicle = read(SOURCES[2])
        self.l05 = read(SOURCES[3])
        self.targets = {q["archetype_id"]: q["dimensions_m"]
                        for q in read(SOURCES[4])["archetypes"]}
        self.ped_nodes = {q["node_id"]: q for q in self.ped["nodes"]}
        self.vehicle_nodes = {q["node_id"]: q for q in self.vehicle["nodes"]}
        self.radius = self.l05["vehicle_blueprint"]["steering"]["icr_local_xz_m"][0]
        self.modules, self.slots, self.paths, self.nodes = [], [], [], []
        self.counts = collections.Counter()

    def add_module(self, zone, family, x, z, yaw, row=0, aisle=None):
        self.counts[zone] += 1
        mid = f"v3:module:{zone}:{self.counts[zone]:03d}"
        d = MODULES[family]
        w, h, depth = d["outer"]
        pos = [x, 0, z]
        bounds = box_world([-w/2, 0, -depth/2], [w/2, h, depth/2], pos, yaw)
        op = box_world([-w/2, 0, -depth/2],
                       [w/2, d.get("operating_height", h), depth/2], pos, yaw)
        m = dict(module_id=mid, zone_id=zone, family=family, world_pos=pos,
                 yaw_rad=yaw % (2*math.pi), outer_bounds_world=bounds,
                 operating_bounds_world=op, row=row, aisle=aisle)
        self.modules.append(m)
        for bi, bx in enumerate(d["bays"], 1):
            services = self.services(m, bi, bx)
            front = depth/2 - .05
            ux, uy, uz = d["usable"]
            for li, height in enumerate(d["levels"], 1):
                reserve = zone.startswith("RESERVE") or (
                    family in ["STANDARD", "LONG"] and li > 1)
                sid = f"v3:slot:{zone}:{self.counts[zone]:03d}:L{li}:B{bi}"
                local_min = [bx-ux/2, height, front-uz]
                local_max = [bx+ux/2, height+uy, front]
                primary = services.get("vehicle") if family in ["HEAVY", "LONG"] or (
                    reserve and family == "STANDARD") else services["worker"]
                allowed = ["STANDARD_CARTON"] if zone.startswith("RESERVE") else d["cargo"]
                self.slots.append(dict(
                    slot_id=sid, module_id=mid, zone_id=zone, storage_type=family,
                    level=li, bay=bi, usable_dimensions_xyz_m=d["usable"],
                    usable_bounds_world=box_world(local_min, local_max, pos, yaw),
                    usable_volume_m3=ux*uy*uz, service_height_m=height,
                    bin_anchor=world([bx, height, front-uz/2], pos, yaw),
                    bin_anchor_meaning="Bottom centre of usable envelope, not an asset-origin substitution.",
                    placement_rule="Upright local XYZ, lateral centred and front aligned with stated per-side clearance; actual unit centre derived from dimensions.",
                    allowed_orientation_ids=["upright_xyz_in_module"],
                    module_world_yaw_rad=m["yaw_rad"],
                    allowed_cargo_archetype_ids=allowed,
                    clearance_each_side_m=d["clearance"],
                    max_payload_kg=d["payload"], max_handling_units=1,
                    stacking_allowed=False, active_pick_candidate=not reserve,
                    reserve_only=reserve, retrieval_blocked=reserve,
                    retrieval_block_reason="HEIGHT_ACCESS_UNAVAILABLE_PENDING_C08" if reserve else None,
                    manual_gross_mass_limit_kg=15,
                    manual_pick_allowed=not reserve and family in ["SMALL", "STANDARD", "FLEX"],
                    required_handler=("approved_lift_process_pending_C08" if reserve else
                                      "forklift_with_approved_support" if family in ["HEAVY", "LONG"]
                                      else "manual_up_to_15kg_or_ground_fragile_forklift" if family=="STANDARD"
                                      else "manual_up_to_15kg_only"),
                    service_node_id=primary, access=services,
                    operational_admission=False,
                    cargo_mass_packing_and_compatibility_status="C02/C04/C08 required; geometric candidate only"))

    def node(self, nid, point, yaw, kind):
        self.nodes.append(dict(node_id=nid, world_pos=point,
                               yaw_rad=yaw % (2*math.pi), kind=kind))

    def human_path(self, pid, mode, gateway, points, allowed_regions, end_yaw):
        radius = .95 if mode == "manual_cart" else .35
        node_id = pid + ":node"
        self.node(node_id, [points[-1][0], 0, points[-1][1]], end_yaw, mode)
        self.paths.append(dict(
            path_id=pid, mode=mode, start_reference=dict(graph="L06", node_id=gateway),
            points_world_xz_m=points, clearance_radius_m=radius,
            clear_height_m=8, allowed_storage_regions=allowed_regions,
            end_node_id=node_id, direction="both",
            restriction="Cart access is not heavy/LONG manual handling; payload and height rules apply."))
        return node_id

    def services(self, m, bi, bx):
        family, zone = m["family"], m["zone_id"]
        pos, theta = m["world_pos"], m["yaw_rad"]
        depth = MODULES[family]["outer"][2]
        prefix = m["module_id"] + f":B{bi}"
        cw = 1.5 if family == "SMALL" else 3 if family == "HEAVY" else (
            1.25 if family == "FLEX" else 1.4 if zone.startswith("RESERVE") else 1.2)
        cart = world([bx, 0, depth/2+cw], pos, theta)
        worker = world([bx, 0, depth/2+.36], pos, theta)
        p = lambda q: [q[0], q[2]]
        allowed = [zone]
        if family == "SMALL":
            gateway = "v3:gateway:" + zone
            start = self.ped_nodes[gateway]["world_pos"]
            points = [p(start), [cart[0], 49], p(cart)]
        elif family == "HEAVY":
            gateway = "v3:gateway:" + zone
            start = self.ped_nodes[gateway]["world_pos"]
            center = 22 if zone.endswith("_W") else 122
            points = [p(start), [center, 25], [center, cart[2]], p(cart)]
        elif family == "LONG":
            gateway = "v3:gateway:" + zone
            start = self.ped_nodes[gateway]["world_pos"]
            center = 52 if zone.endswith("_W") else 92
            points = [p(start), [center, 27], [cart[0], 27], p(cart)]
        elif family == "FLEX":
            gateway = "v3:gateway:" + zone
            start = self.ped_nodes[gateway]["world_pos"]
            points = [p(start), [start[0], cart[2]], p(cart)]
        else:
            std_zone = "STANDARD_W" if zone.endswith("_W") else "STANDARD_E"
            gateway = "v3:gateway:" + std_zone
            start = self.ped_nodes[gateway]["world_pos"]
            center = 52 if zone.endswith("_W") else 92
            if zone.startswith("RESERVE"):
                allowed.append(std_zone)
                points = [p(start), [center, 56], [cart[0], 56], p(cart)]
            elif m["row"] == 0:
                points = [p(start), [center, cart[2]], p(cart)]
            else:
                points = [p(start), [center, 49], [cart[0], 49], p(cart)]
        facing = (theta + math.pi) % (2*math.pi)
        cart_id = self.human_path(prefix+":cart", "manual_cart", gateway, points,
                                  allowed, facing)
        worker_id = self.human_path(prefix+":worker", "pedestrian", gateway,
                                    points + [p(worker)], allowed, facing)
        result = dict(cart_stop_id=cart_id, worker_node_id=worker_id, worker=worker_id,
                      cart_transport_requires_gross_mass_at_most_15kg=True)
        if family in ["STANDARD", "HEAVY", "LONG"]:
            target = world([bx, 0, depth/2+1.80], pos, theta)
            result["vehicle"] = self.vehicle_path(m, bi, target, facing, allowed)
            result["vehicle_approach_id"] = prefix+":vehicle"
        return result

    def source_cross(self, fx):
        for e in self.vehicle["edges"]:
            g = e["geometry"]
            if g["kind"] != "line" or e["motion_direction"] != 1:
                continue
            a, b = g["front_axle_start_xz_m"], g["front_axle_end_xz_m"]
            if abs(a[1]-38)<1e-8 and abs(b[1]-38)<1e-8 and b[0]>a[0] and a[0]-1e-8<=fx<=b[0]+1e-8:
                return dict(graph="L07", edge_id=e["edge_id"],
                            edge_u=(fx-a[0])/(b[0]-a[0])), (fx, 38), math.pi/2
        raise ValueError(("no existing eastward cross attachment", fx))

    def vehicle_path(self, m, bi, target, target_yaw, allowed):
        family, zone = m["family"], m["zone_id"]
        prefix = m["module_id"] + f":B{bi}:vehicle"
        segments, radius = [], self.radius
        if family in ["HEAVY", "LONG"]:
            nid = "v3:vehicle:gateway:" + zone
            n = self.vehicle_nodes[nid]
            start = dict(graph="L07", node_id=nid)
            F = [n["front_axle_world_pos"][0], n["front_axle_world_pos"][2]]
            heading = n["yaw_rad"]
        else:
            center = 52 if zone.endswith("_W") else 92
            attach_x = target[0] if m["row"] == 0 and not zone.startswith("RESERVE") else center
            start, F, heading = self.source_cross(attach_x-radius)
        def line_to(B):
            nonlocal F
            if math.dist(F, B) < 1e-9:
                return
            h = [math.sin(heading), math.cos(heading)]
            assert (B[0]-F[0])*h[0]+(B[1]-F[1])*h[1] > -1e-8
            segments.append(dict(kind="line", front_axle_start_xz_m=list(F),
                                 front_axle_end_xz_m=list(B), start_yaw_rad=heading,
                                 end_yaw_rad=heading, rear_virtual_steer_deg=0))
            F = list(B)
        def turn(J, out):
            nonlocal F, heading
            incoming = [round(math.sin(heading)), round(math.cos(heading))]
            A = [J[i]-radius*incoming[i] for i in [0, 1]]
            line_to(A)
            end_yaw = math.atan2(out[0], out[1]) % (2*math.pi)
            delta = wrap(end_yaw-heading)
            assert abs(abs(delta)-math.pi/2)<1e-8
            I = [J[i]+radius*(-incoming[i]+out[i]) for i in [0, 1]]
            segments.append(dict(kind="rear_steer_arc", icr_world_xz_m=I,
                                 icr_vehicle_local_x_m=math.copysign(radius, delta),
                                 front_axle_radius_m=radius, start_yaw_rad=heading,
                                 end_yaw_rad=heading+delta,
                                 rear_virtual_steer_deg=-math.copysign(60, delta)))
            F = [J[i]+radius*out[i] for i in [0, 1]]
            heading = end_yaw
        if family == "HEAVY":
            center = 22 if zone.endswith("_W") else 122
            out = [round(math.sin(target_yaw)), round(math.cos(target_yaw))]
            turn([center, target[2]], out)
        elif family == "LONG":
            center = 52 if zone.endswith("_W") else 92
            out = [1 if target[0]>center else -1, 0]
            turn([center, 27], out)
            turn([target[0], 27], [0, -1])
        else:
            center = 52 if zone.endswith("_W") else 92
            attach_x = target[0] if m["row"] == 0 and not zone.startswith("RESERVE") else center
            turn([attach_x, 38], [0, 1])
            if m["row"] != 0 or zone.startswith("RESERVE"):
                cross_z = 57 if zone.startswith("RESERVE") else 49
                out = [1 if target[0]>center else -1, 0]
                turn([center, cross_z], out)
                turn([target[0], cross_z], [0, 1])
        line_to([target[0]+.4*math.sin(target_yaw),
                 target[2]+.4*math.cos(target_yaw)])
        assert abs(wrap(heading-target_yaw))<1e-8
        node_id = prefix + ":node"
        self.node(node_id, target, target_yaw, "forklift_pre_handle_stop")
        self.paths.append(dict(
            path_id=prefix, mode="forklift", start_reference=start,
            segments=segments, end_node_id=node_id,
            profile_id="long_loaded" if family=="LONG" else "nonlong_forklift",
            allowed_storage_regions=allowed, reverse_exit="Traverse reversed segments backwards with unchanged yaw/steer; no spin.",
            handling_admission="C08 support/payload/lift and exact handling-unit eligibility required; floor approach is not a fork insertion/contact path.",
            nonlong_attachment_rule="No LONG cradle on nonlong profile; actual support must fit this envelope and be approved. No implicit attachment change.",
            semantic_restriction="STANDARD_CARTON forklift transport/retrieval is not authorized by L07; reserve upper levels stay blocked pending an approved process." if family=="STANDARD" else None))
        return node_id

    def place(self):
        for bank, shift in [("W", 0), ("E", 100)]:
            for aisle in [16+shift, 22+shift, 28+shift]:
                for side in [-1, 1]:
                    x = aisle + side*2
                    yaw = math.pi/2 if side<0 else 3*math.pi/2
                    for z in [43.5, 46, 51.4, 53.9]:
                        self.add_module("SMALL_"+bank, "SMALL", x, z, yaw, aisle=aisle)
        for bank, shift in [("W", 0), ("E", 40)]:
            for row, front in enumerate([44, 52.3]):
                for x in [38.2, 41.2, 44.2, 47.2, 56.8, 59.8, 62.8, 65.8]:
                    self.add_module("STANDARD_"+bank, "STANDARD", x+shift, front+.7, math.pi, row=row)
        for bank, center in [("W", 22), ("E", 122)]:
            for side in [-1, 1]:
                front = center + side*3
                x = front + side*.7
                yaw = math.pi/2 if side<0 else 3*math.pi/2
                for z in [17.5, 19.5, 21.5, 27.5, 29.5, 31.5]:
                    self.add_module("HEAVY_"+bank, "HEAVY", x, z, yaw)
        for bank, shift in [("W", 0), ("E", 40)]:
            for x in [38.5, 43.5, 48.5, 55.5, 60.5, 65.5]:
                self.add_module("LONG_"+bank, "LONG", x+shift, 17.65, 0)
        for bank, shift in [("W", 0), ("E", 60)]:
            for x in [37.6, 40.4, 43.2, 46]:
                self.add_module("FLEX_"+bank, "FLEX", x+shift, 15.1, math.pi)
        for bank, shift in [("W", 0), ("E", 58)]:
            for x in [38, 41.2, 44.4, 47.6]:
                self.add_module("RESERVE_"+bank, "STANDARD", x+shift, 61.2, math.pi, row=2)
        return dict(
            document_kind="deterministic_storage_layout_proposal", proposal_id="L09",
            proposal_version="0.1.0", status="proposal",
            layout_version="qoima-144x72-v3-proposal",
            units=dict(length="m", mass="kg", time="s", angle="radian", up_axis="Y"),
            assumptions="Synthetic module geometry/storage payloads and access. No SKU/lot inventory, backend KPI, structural certification or C08 eligibility is generated.",
            module_definitions=MODULES, modules=self.modules, slots=self.slots,
            service_nodes=self.nodes, local_access_paths=self.paths,
            access_profiles=dict(
                pedestrian=dict(radius_m=.35, height_m=1.7),
                manual_cart=dict(radius_m=.95, meaning="L06 combined cart+operator envelope"),
                long_loaded=dict(component_bounds_local_m=[
                    self.l05["vehicle_blueprint"]["bounds_local_m"],
                    self.l05["cradle_assumption"]["bounds_local_m"],
                    self.l05["load_profile"]["bounds_local_m"]], padding_m=.25),
                nonlong_forklift=dict(component_bounds_local_m=[
                    self.l05["vehicle_blueprint"]["bounds_local_m"],
                    dict(min=[-.6,.45,.5], max=[.6,1.8,1.5])], padding_m=.25,
                    meaning="Actual R03 heavy/pallet/IBC/drum/fragile sizes are enclosed without resizing. No LONG cradle; actual support/C08 approval still required.")),
            manual_access=dict(max_gross_mass_kg=15, max_grasp_height_m=1.25,
                               horizontal_grasp_reach_m=.4712),
            reserve_policy="Reserve-only addresses reject retrieval with HEIGHT_ACCESS_UNAVAILABLE_PENDING_C08 until a real lift/handling process is approved. Never active inaccessible inventory.",
            operational_admission=False,
            read_only_input_fingerprints=[dict(path=f, sha256=sha(ROOT/f)) for f in SOURCES],
            generator=dict(path=str(Path(__file__).relative_to(ROOT)).replace("\\","/"),
                           sha256=sha(Path(__file__))),
            deferred=["C02 exact catalog/mass and 200-SKU binding", "C04 final compatibility",
                      "C08 fork insertion, lift, support/rating, attachment and pickup/retrieval",
                      "Source mixed pedestrian/vehicle scheduling", "Meshes"])


def segment_pose(g, u):
    theta = g["start_yaw_rad"] + u*(g["end_yaw_rad"]-g["start_yaw_rad"])
    if g["kind"] == "line":
        a, b = g["front_axle_start_xz_m"], g["front_axle_end_xz_m"]
        f = [a[i]+u*(b[i]-a[i]) for i in [0, 1]]
    else:
        q, centre = g["icr_vehicle_local_x_m"], g["icr_world_xz_m"]
        f = [centre[0]-q*math.cos(theta), centre[1]+q*math.sin(theta)]
    return [f[0]-.4*math.sin(theta), 0, f[1]-.4*math.cos(theta)], theta, f


def polygon(box, pos, theta, padding):
    return [world([x, 0, z], pos, theta)[::2] for x, z in [
        (box["min"][0]-padding, box["min"][2]-padding),
        (box["max"][0]+padding, box["min"][2]-padding),
        (box["max"][0]+padding, box["max"][2]+padding),
        (box["min"][0]-padding, box["max"][2]+padding)]]


def polygon_hit(points, rect, theta):
    xs, zs = [q[0] for q in points], [q[1] for q in points]
    if not overlap([min(xs), min(zs), max(xs), max(zs)], rect):
        return False
    for ax, az in [(math.cos(theta), -math.sin(theta)),
                   (math.sin(theta), math.cos(theta))]:
        projections = [x*ax+z*az for x, z in points]
        centre = (rect[0]+rect[2])/2*ax+(rect[1]+rect[3])/2*az
        extent = (rect[2]-rect[0])/2*abs(ax)+(rect[3]-rect[1])/2*abs(az)
        if min(max(projections), centre+extent)-max(min(projections), centre-extent)<=1e-8:
            return False
    return True


def validate(data, model):
    import datetime
    checks = []
    def check(name, condition, actual=None):
        assert condition, (name, actual)
        checks.append(dict(name=name, status="PASS", actual=actual))
    modules = {m["module_id"]: m for m in data["modules"]}
    slots = {s["slot_id"]: s for s in data["slots"]}
    nodes = {n["node_id"]: n for n in data["service_nodes"]}
    paths = {p["path_id"]: p for p in data["local_access_paths"]}
    check("unique_modules", len(modules)==len(data["modules"]), len(modules))
    check("unique_slots", len(slots)==len(data["slots"]), len(slots))
    check("unique_service_nodes", len(nodes)==len(data["service_nodes"]), len(nodes))
    check("unique_local_paths", len(paths)==len(data["local_access_paths"]), len(paths))
    obstacles = [(m["module_id"], floor_rect(m["operating_bounds_world"]))
                 for m in modules.values()]
    for m in modules.values():
        rect = floor_rect(m["outer_bounds_world"])
        lo, hi = model.zones[m["zone_id"]]["floor_bounds_xz_m"].values()
        check("module_in_region:"+m["module_id"],
              lo[0]-1e-8<=rect[0]<rect[2]<=hi[0]+1e-8 and
              lo[1]-1e-8<=rect[1]<rect[3]<=hi[1]+1e-8)
    collisions = [(a[0], b[0]) for a, b in itertools.combinations(obstacles, 2)
                  if overlap(a[1], b[1])]
    check("module_floor_overlaps", not collisions, collisions)
    per_module = collections.Counter(s["module_id"] for s in slots.values())
    for mid, m in modules.items():
        d = MODULES[m["family"]]
        check("derived_addresses:"+mid, per_module[mid]==len(d["levels"])*len(d["bays"]))
        own = [s for s in slots.values() if s["module_id"] == mid]
        check("aggregate_storage_payload:"+mid,
              sum(s["max_payload_kg"] for s in own)<=d["module_payload"])
        overlaps = [(a["slot_id"],b["slot_id"])
                    for a,b in itertools.combinations(own,2)
                    if all(min(a["usable_bounds_world"]["max"][i],b["usable_bounds_world"]["max"][i])-
                           max(a["usable_bounds_world"]["min"][i],b["usable_bounds_world"]["min"][i])>1e-8
                           for i in range(3))]
        check("usable_slot_overlaps:"+mid,not overlaps,overlaps)
        posts = [box_world(b["min"],b["max"],m["world_pos"],m["yaw_rad"])
                 for b in d["construction"]["posts"]]
        intrusion = [(s["slot_id"],i) for s in own for i,b in enumerate(posts)
                     if all(min(s["usable_bounds_world"]["max"][axis],b["max"][axis])-
                            max(s["usable_bounds_world"]["min"][axis],b["min"][axis])>1e-8
                            for axis in range(3))]
        check("posts_outside_usable_cavity:"+mid,not intrusion,intrusion)
    for s in slots.values():
        m = modules[s["module_id"]]
        op, usable = m["operating_bounds_world"], s["usable_bounds_world"]
        check("usable_within_operating_bounds:"+s["slot_id"],
              all(op["min"][i]-1e-8<=usable["min"][i]<usable["max"][i]<=op["max"][i]+1e-8 for i in range(3)))
        check("known_primary_service:"+s["slot_id"], s["service_node_id"] in nodes)
        check("usable_world_volume:"+s["slot_id"],
              math.isclose(math.prod(usable["max"][i]-usable["min"][i] for i in range(3)),
                           s["usable_volume_m3"],rel_tol=1e-9,abs_tol=1e-9))
        check("reserve_retrieval_rejected:"+s["slot_id"],
              not s["reserve_only"] or (not s["active_pick_candidate"] and s["retrieval_blocked"]))
        dims = s["usable_dimensions_xyz_m"]
        for cargo in s["allowed_cargo_archetype_ids"]:
            target = model.targets[cargo]
            check("cargo_fit:"+s["slot_id"]+":"+cargo,
                  all(target[i]+2*s["clearance_each_side_m"]<=dims[i]+1e-8 for i in range(3)))
        if s["manual_pick_allowed"]:
            max_grasp = s["service_height_m"]+max(model.targets[c][1]/2 for c in s["allowed_cargo_archetype_ids"])
            check("manual_height:"+s["slot_id"], max_grasp<=1.25+1e-8)
            reach = .36+.05+s["clearance_each_side_m"]
            check("actual_manual_horizontal_reach:"+s["slot_id"],reach<=.4712+1e-8,reach)
    human_segments, vehicle_component_poses, vehicle_segments = 0, 0, 0
    mode_counts = collections.Counter()
    for path in paths.values():
        mode_counts[path["mode"]] += 1
        foreign = [(zid, z["floor_bounds_xz_m"]["min"]+z["floor_bounds_xz_m"]["max"])
                   for zid, z in model.zones.items() if z["kind"]!="circulation" and zid not in path["allowed_storage_regions"]]
        blockers = obstacles + foreign
        if path["mode"] != "forklift":
            reference = model.ped_nodes[path["start_reference"]["node_id"]]["world_pos"][::2]
            points = path["points_world_xz_m"]
            check("human_attachment:"+path["path_id"], math.dist(points[0], reference)<1e-8)
            radius = path["clearance_radius_m"]
            for a, b in zip(points, points[1:]):
                sweep = [min(a[0],b[0])-radius, min(a[1],b[1])-radius,
                         max(a[0],b[0])+radius, max(a[1],b[1])+radius]
                assert sweep[0]>=-1e-8 and sweep[1]>=-1e-8 and sweep[2]<=144+1e-8 and sweep[3]<=72+1e-8
                hit = next((bid for bid, bounds in blockers if overlap(sweep, bounds)), None)
                assert hit is None, (path["path_id"], "human collision", hit, sweep)
                human_segments += 1
            continue
        components = data["access_profiles"][path["profile_id"]]["component_bounds_local_m"]
        source = path["start_reference"]
        first, first_yaw, _ = segment_pose(path["segments"][0], 0)
        if "node_id" in source:
            n = model.vehicle_nodes[source["node_id"]]
            check("vehicle_node_attachment:"+path["path_id"],
                  math.dist(first,n["world_pos"])<1e-8 and abs(wrap(first_yaw-n["yaw_rad"]))<1e-8)
        else:
            edge = next(e for e in model.vehicle["edges"] if e["edge_id"]==source["edge_id"])
            expected, eyaw, _ = segment_pose(edge["geometry"], source["edge_u"])
            check("vehicle_edge_attachment:"+path["path_id"],
                  0<=source["edge_u"]<=1 and math.dist(first,expected)<1e-8 and abs(wrap(first_yaw-eyaw))<1e-8)
        for index, g in enumerate(path["segments"]):
            vehicle_segments += 1
            if index:
                prev, prev_yaw, _ = segment_pose(path["segments"][index-1], 1)
                here, here_yaw, _ = segment_pose(g, 0)
                check("vehicle_continuity:"+path["path_id"]+":"+str(index),
                      math.dist(prev,here)<1e-8 and abs(wrap(prev_yaw-here_yaw))<1e-8)
            if g["kind"] == "line":
                for box in components:
                    points=[]
                    for u in [0,1]:
                        pos, theta, _ = segment_pose(g,u)
                        points += polygon(box,pos,theta,.25)
                    sweep=[min(q[0] for q in points),min(q[1] for q in points),
                           max(q[0] for q in points),max(q[1] for q in points)]
                    assert sweep[0]>=-1e-8 and sweep[1]>=-1e-8 and sweep[2]<=144+1e-8 and sweep[3]<=72+1e-8
                    hit=next((bid for bid,bounds in blockers if overlap(sweep,bounds)),None)
                    assert hit is None,(path["path_id"],"vehicle line collision",hit,sweep)
                    vehicle_component_poses+=2
            else:
                delta=abs(g["end_yaw_rad"]-g["start_yaw_rad"])
                count=math.ceil(delta/math.radians(.5))
                q=g["icr_vehicle_local_x_m"]
                rho=max(math.hypot(x-q,z-.4) for b in components for x in [b["min"][0],b["max"][0]] for z in [b["min"][2],b["max"][2]])
                extra=2*rho*math.sin(delta/(4*count))
                for step in range(count+1):
                    pos,theta,_=segment_pose(g,step/count)
                    for box in components:
                        points=polygon(box,pos,theta,.25+extra)
                        assert all(-1e-8<=x<=144+1e-8 and -1e-8<=z<=72+1e-8 for x,z in points)
                        hit=next((bid for bid,bounds in blockers if polygon_hit(points,bounds,theta)),None)
                        assert hit is None,(path["path_id"],"vehicle arc collision",hit,step/count)
                        vehicle_component_poses+=1
        end,theta,_=segment_pose(path["segments"][-1],1)
        node=nodes[path["end_node_id"]]
        check("vehicle_service_endpoint:"+path["path_id"],
              math.dist(end,node["world_pos"])<1e-8 and abs(wrap(theta-node["yaw_rad"]))<1e-8)
    check("unchanged_LONG_components",
          data["access_profiles"]["long_loaded"]["component_bounds_local_m"]==[
              model.l05["vehicle_blueprint"]["bounds_local_m"],
              model.l05["cradle_assumption"]["bounds_local_m"],
              model.l05["load_profile"]["bounds_local_m"]])
    for fingerprint in data["read_only_input_fingerprints"]:
        check("unchanged_source:"+fingerprint["path"],
              sha(ROOT/fingerprint["path"])==fingerprint["sha256"])
    counts=dict(modules=len(modules),addresses=len(slots),
                active_pick_candidates=sum(s["active_pick_candidate"] for s in slots.values()),
                reserve_addresses=sum(s["reserve_only"] for s in slots.values()),
                modules_by_region=dict(collections.Counter(m["zone_id"] for m in modules.values())),
                addresses_by_region=dict(collections.Counter(s["zone_id"] for s in slots.values())),
                paths_by_mode=dict(mode_counts))
    # Explicit negative outcomes, based on the same dimensions/metadata.
    negatives=[
        dict(case="standard_carton_in_SMALL",result="DIMENSION_MISMATCH",
             passed=model.targets["STANDARD_CARTON"][0]+.06>MODULES["SMALL"]["usable"][0]),
        dict(case="payload_above_limit",result="OVERWEIGHT",passed=16>MODULES["FLEX"]["payload"]),
        dict(case="manual_upper_STANDARD",result="HEIGHT_ACCESS_UNAVAILABLE",
             passed=all(s["retrieval_blocked"] and not s["manual_pick_allowed"] for s in slots.values() if s["storage_type"]=="STANDARD" and s["level"]>1)),
        dict(case="manual_LONG",result="HANDLER_UNAVAILABLE",
             passed=all(not s["manual_pick_allowed"] for s in slots.values() if s["storage_type"]=="LONG")),
        dict(case="second_handling_unit",result="SLOT_CAPACITY",
             passed=all(s["max_handling_units"]==1 for s in slots.values())),
        dict(case="tilt_to_force_fit",result="ORIENTATION_FORBIDDEN",
             passed=all("tip_on_side" not in s["allowed_orientation_ids"] for s in slots.values())),
        dict(case="reserve_ground_not_active_inventory",result="RETRIEVAL_BLOCKED",
             passed=all(s["retrieval_blocked"] and not s["active_pick_candidate"]
                        for s in slots.values() if s["zone_id"].startswith("RESERVE")))]
    check("negative_cases",all(n["passed"] for n in negatives))
    return dict(task_id="L09",status="ACTIVE",root_review="pending",
                checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                counts=counts,checks=dict(passed=len(checks),failures=0,results=checks),
                validation_summary=dict(module_overlaps=0,human_capsule_segments=human_segments,
                                        vehicle_segments=vehicle_segments,
                                        oriented_vehicle_component_poses=vehicle_component_poses,
                                        clearance_failures=0,
                                        arc_continuous_method="<=.5degree samples +2*rho*sin(delta/4) inflation; exact line component sweeps"),
                negative_cases=negatives,operational_admission=False,
                source_fingerprints=data["read_only_input_fingerprints"],
                limitations=["C02 SKU/mass mix must respect shared physical capacity; no inventory is instantiated.",
                             "Upper/reserve retrieval remains blocked pending actual handling/lift access.",
                             "Floor pre-handle stops are not approved fork insertion, load support or lift trajectories.",
                             "Local edges extend L06/L07 through references; original graph files unchanged."])


def draw_svg(data):
    ox,oy,scale=100,150,7
    px=lambda x:ox+x*scale
    py=lambda z:oy+(72-z)*scale
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1700" height="1050" viewBox="0 0 1700 1050">',
         '<rect width="1700" height="1050" fill="#fafbfc"/>',
         '<g font-family="Arial,sans-serif" fill="#20333e">',
         '<text x="100" y="42" font-size="28" font-weight="700">L09 / METRIC STORAGE ADDRESSES</text>',
         f'<text x="100" y="73" font-size="16">{len(data["modules"])} modules; {len(data["slots"])} derived addresses — no target count / no inventory instantiated</text>',
         '<text x="100" y="100" font-size="14">144 × 72 m · ordinary metre scale · local aisles and full vehicle turns checked · conditional C02/C08</text>']
    palette={"SMALL":"#8ac8ba","STANDARD":"#90b4d7","HEAVY":"#b7a9cd","LONG":"#d4b77a","FLEX":"#dcb0c1"}
    layout=read(SOURCES[0])
    for z in layout["zones"]:
        (x0,z0),(x1,z1)=z["floor_bounds_xz_m"]["min"],z["floor_bounds_xz_m"]["max"]
        fill="#edf0f2" if z["kind"]=="circulation" else "#f7f5ef"
        svg.append(f'<rect x="{px(x0):g}" y="{py(z1):g}" width="{(x1-x0)*scale:g}" height="{(z1-z0)*scale:g}" fill="{fill}" stroke="#dfe4e7"/>')
    for path in data["local_access_paths"]:
        if path["mode"]=="pedestrian":
            continue
        if path["mode"]=="manual_cart":
            points=path["points_world_xz_m"];color="#438b92";width=.7
        else:
            points=[]
            for g in path["segments"]:
                for i in range(19 if g["kind"]!="line" else 2):
                    count=18 if g["kind"]!="line" else 1
                    pos,_,_=segment_pose(g,i/count);points.append(pos[::2])
            color="#c3903c";width=.7
        pts=" ".join(f"{px(x):.2f},{py(z):.2f}" for x,z in points)
        svg.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-opacity=".5" stroke-width="{width}"/>')
    for m in data["modules"]:
        x0,z0,x1,z1=floor_rect(m["outer_bounds_world"])
        fill=palette[m["family"]] if not m["zone_id"].startswith("RESERVE") else "#aebdc7"
        svg.append(f'<rect data-module-id="{m["module_id"]}" x="{px(x0):g}" y="{py(z1):g}" width="{(x1-x0)*scale:g}" height="{(z1-z0)*scale:g}" fill="{fill}" stroke="#314b58" stroke-width=".55"/>')
    per=collections.Counter(s["zone_id"] for s in data["slots"])
    for z in layout["zones"]:
        if z["zone_id"] not in per:
            continue
        (x0,z0),(x1,z1)=z["floor_bounds_xz_m"]["min"],z["floor_bounds_xz_m"]["max"]
        # Region count labels sit just inside the top edge; exact slot geometry is in JSON.
        label_y = py(z0)-4 if z["zone_id"].startswith("FLEX") else py(z1)-5
        svg.append(f'<text x="{px((x0+x1)/2):g}" y="{label_y:g}" text-anchor="middle" font-size="10" font-weight="700">{z["zone_id"]}: {per[z["zone_id"]]} addresses</text>')
    svg+=['<rect x="100" y="150" width="1008" height="504" fill="none" stroke="#20333e" stroke-width="2"/>',
          '<text x="1080" y="705" font-size="13">X (m) →</text>',
          '<text x="66" y="140" font-size="13">Z ↑</text>']
    for x in range(0,145,24):
        svg.append(f'<text x="{px(x):g}" y="676" font-size="12" text-anchor="middle">{x}</text>')
    for z in range(0,73,12):
        svg.append(f'<text x="93" y="{py(z)+4:g}" font-size="11" text-anchor="end">{z}</text>')
    svg+=['<text x="1180" y="154" font-size="20" font-weight="700">Module / level rules</text>']
    for i,(family,d) in enumerate(MODULES.items()):
        y=194+i*63
        svg.append(f'<rect x="1180" y="{y-15}" width="18" height="18" fill="{palette[family]}"/>')
        svg.append(f'<text x="1210" y="{y}" font-size="15" font-weight="700">{family}: {html.escape(str(d["outer"]))} m</text>')
        svg.append(f'<text x="1210" y="{y+24}" font-size="13">usable {html.escape(str(d["usable"]))}; levels {d["levels"]}</text>')
    active=sum(s["active_pick_candidate"] for s in data["slots"])
    reserve=sum(s["reserve_only"] for s in data["slots"])
    svg += [f'<text x="1180" y="548" font-size="17" font-weight="700">{active} active-pick geometry candidates</text>',
            f'<text x="1180" y="578" font-size="17" font-weight="700">{reserve} reserve-only / retrieval blocked</text>',
            '<text x="1180" y="618" font-size="14">Upper STANDARD/LONG require approved lift.</text>',
            '<text x="1180" y="644" font-size="14">No inaccessible active inventory is created.</text>',
            '<text x="1180" y="684" font-size="14">HEAVY is a .18 m open support platform;</text>',
            '<text x="1180" y="710" font-size="14">usable vertical headroom is separate.</text>',
            '<text x="1180" y="750" font-size="14">LONG/cradle/vehicle sizes match L05.</text>',
            '<text x="1180" y="776" font-size="14">Nonlong paths use actual enclosed loads,</text>',
            '<text x="1180" y="802" font-size="14">without the wide LONG cradle attached.</text>',
            '<text x="1180" y="842" font-size="14">Manual reach .44–.46 m ≤ .4712 m.</text>',
            '<line x1="100" x2="145" y1="726" y2="726" stroke="#438b92" stroke-width="3"/><text x="158" y="731" font-size="15">L06-connected cart paths (radius .95 m); worker-only terminal branches in JSON</text>',
            '<line x1="100" x2="145" y1="763" y2="763" stroke="#c3903c" stroke-width="3"/><text x="158" y="768" font-size="15">Real L07-connected rear-steer vehicle approaches; full component clearance</text>',
            '<text x="100" y="818" font-size="15">Three cart aisles per SMALL region; STANDARD central aisle 6.8 m / between rows 6.9 m.</text>',
            '<text x="100" y="851" font-size="15">HEAVY central aisle 6 m and pedestrian cross at Z25; LONG retains a broad turning apron.</text>',
            '<text x="100" y="884" font-size="15">FLEX has four finite manual bays per region. Separate RESERVE regions reuse STANDARD geometry.</text>',
            '<text x="100" y="936" font-size="14">All cargo/mass/packing eligibility remains C02/C04/C08. Address counts are not units, stock or backend KPI.</text>',
            '<text x="100" y="970" font-size="14">Outer geometry, operating envelope and useful cavity are distinct; no mesh, rig or fork-contact acceptance here.</text>',
            '<text x="100" y="1005" font-size="13" fill="#637680">Synthetic deterministic numeric proposal; generator and source fingerprints retained. Root actual plan review required.</text>',
            '</g></svg>']
    SVG.write_text("\n".join(svg)+"\n",encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    model = Layout()
    data = read(str(OUT.relative_to(ROOT))) if args.check_only else model.place()
    result = validate(data, model)
    if not args.check_only:
        dump(OUT, data)
        draw_svg(data)
        result["artifacts"] = {
            "layout": dict(path=str(OUT.relative_to(ROOT)).replace("\\","/"), sha256=sha(OUT)),
            "plan": dict(path=str(SVG.relative_to(ROOT)).replace("\\","/"), sha256=sha(SVG)),
            "generator": dict(path=str(Path(__file__).relative_to(ROOT)).replace("\\","/"), sha256=sha(Path(__file__)))}
        dump(EVIDENCE, result)
    print(json.dumps({k: result[k] for k in ["status", "counts", "validation_summary"]}, indent=2))


if __name__ == "__main__":
    main()
