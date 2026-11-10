"""L11 read-only spatial audit and proposed mixed-traffic resource register.

Stdlib only. No Blender/browser/backend, and no accepted input is rewritten.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/v3/contract-proposals/layout-conflicts-v3.json"
EVIDENCE = ROOT / "docs/adaptive-v3/evidence/L11.json"
EPS = 1e-8
GRID = 4.0
INPUTS = [
    "docs/v3/contract-proposals/layout-v3.zones.json",
    "docs/v3/contract-proposals/ports-v3.inbound.json",
    "docs/v3/contract-proposals/ports-v3.outbound.json",
    "docs/v3/contract-proposals/large-gate-v3.json",
    "docs/v3/contract-proposals/pedestrian-graph-v3.json",
    "docs/v3/contract-proposals/vehicle-graph-v3.json",
    "docs/v3/contract-proposals/conveyor-v3.json",
    "docs/v3/contract-proposals/storage-layout-v3.json",
    "assets/v3/blender/layout-engineering.stats.json",
    "tools/blender/v3/build_layout_engineering.py",
    "docs/v3/contract-proposals/port-resource-policy-v3.json",
]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def rect(lo, hi):
    return [(lo[0], lo[1]), (hi[0], lo[1]), (hi[0], hi[1]), (lo[0], hi[1])]


def aabb(poly):
    return [min(q[0] for q in poly), min(q[1] for q in poly),
            max(q[0] for q in poly), max(q[1] for q in poly)]


def box_poly(b):
    return rect(b["min"][::2], b["max"][::2])


def overlap(a, b):
    return min(a[2], b[2])-max(a[0], b[0]) > EPS and min(a[3], b[3])-max(a[1], b[1]) > EPS


def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def hull(points):
    points = sorted(set(tuple(q) for q in points))
    sides = []
    for order in [points, list(reversed(points))]:
        result = []
        for p in order:
            while len(result) >= 2 and cross(result[-2], result[-1], p) <= EPS:
                result.pop()
            result.append(p)
        sides.append(result[:-1])
    return sides[0]+sides[1]


def poly_hit(a, b):
    if not overlap(aabb(a), aabb(b)):
        return False
    for polygon in [a, b]:
        for p, q in zip(polygon, polygon[1:]+polygon[:1]):
            axis = (q[1]-p[1], p[0]-q[0])
            ap = [v[0]*axis[0]+v[1]*axis[1] for v in a]
            bp = [v[0]*axis[0]+v[1]*axis[1] for v in b]
            if min(max(ap), max(bp))-max(min(ap), min(bp)) <= EPS:
                return False
    return True


def point_segment_sq(p, a, b):
    v = [b[i]-a[i] for i in [0, 1]]
    length = sum(q*q for q in v)
    u = max(0, min(1, sum((p[i]-a[i])*v[i] for i in [0, 1])/length)) if length else 0
    return sum((p[i]-a[i]-u*v[i])**2 for i in [0, 1])


def segment_intersects(a, b, c, d):
    o = [cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)]
    if o[0]*o[1] < -EPS and o[2]*o[3] < -EPS:
        return True
    return min(point_segment_sq(a,c,d), point_segment_sq(b,c,d),
               point_segment_sq(c,a,b), point_segment_sq(d,a,b)) < EPS*EPS


def inside(p, poly):
    signs = [cross(a,b,p) for a,b in zip(poly, poly[1:]+poly[:1])]
    return all(x >= -EPS for x in signs) or all(x <= EPS for x in signs)


def capsule_hit(a, b, radius, poly):
    if inside(a,poly) or inside(b,poly):
        return True
    best = math.inf
    for c,d in zip(poly, poly[1:]+poly[:1]):
        if segment_intersects(a,b,c,d):
            return True
        best = min(best,point_segment_sq(a,c,d),point_segment_sq(b,c,d),
                   point_segment_sq(c,a,b),point_segment_sq(d,a,b))
    return best < (radius-1e-8)**2


def capsule_bounds(a, b, r):
    return [min(a[0],b[0])-r,min(a[1],b[1])-r,max(a[0],b[0])+r,max(a[1],b[1])+r]


def cells(bounds):
    for x in range(max(0,math.floor(bounds[0]/GRID)), min(35,math.floor(bounds[2]/GRID))+1):
        for z in range(max(0,math.floor(bounds[1]/GRID)), min(17,math.floor(bounds[3]/GRID))+1):
            yield x,z


class Index:
    def __init__(self, shapes):
        self.shapes = shapes
        self.grid = defaultdict(set)
        for i,s in enumerate(shapes):
            for c in cells(s["bounds"]):
                self.grid[c].add(i)

    def query(self, bounds):
        ids = set()
        for c in cells(bounds):
            ids.update(self.grid[c])
        return (self.shapes[i] for i in sorted(ids) if overlap(bounds,self.shapes[i]["bounds"]))


def solid(sid, category, poly, y0, y1):
    return dict(id=sid, category=category, poly=poly, bounds=aabb(poly), y_min=y0, y_max=y1)


def physical(data):
    zones, inbound, outbound, l05, ped, vehicle, conveyor, storage, stats = data[:9]
    result = []
    source_components = {c["name"]:c for c in stats["components"]}
    matches = []
    def add_box(sid, category, b, source_name=None):
        if source_name:
            actual = source_components[source_name]["bounds_runtime"]
            err = max(abs(actual[k][i]-b[k][i]) for k in ["min","max"] for i in range(3))
            assert err < 1e-5,(source_name,"L10/source numeric mismatch",err)
            matches.append(err)
        result.append(solid(sid,category,box_poly(b),b["min"][1],b["max"][1]))
    for m in storage["modules"]:
        add_box(m["module_id"],"storage",m["outer_bounds_world"],"VOLUME__"+m["module_id"])
    for m in conveyor["physical_modules"]:
        lo,hi=m["floor_bounds_xz"]["min"],m["floor_bounds_xz"]["max"]
        b=dict(min=[lo[0],0,lo[1]],max=[hi[0],m["deck_y"],hi[1]])
        if m["family"] != "turn":
            add_box(m["module_id"],"conveyor",b,m["module_id"])
            continue
        actual=source_components[m["module_id"]]["bounds_runtime"]
        err=max(abs(actual[k][i]-b[k][i]) for k in ["min","max"] for i in range(3));assert err<1e-5;matches.append(err)
        cx,_,cz=m["origin"];w=conveyor["geometry"]["total_width_m"];r0,r1=m["radius_m"]-w/2,m["radius_m"]+w/2
        for i in range(m["quarter_facets"]):
            angles=[m["theta_start_rad"]+(m["theta_end_rad"]-m["theta_start_rad"])*j/m["quarter_facets"] for j in [i,i+1]]
            p=hull([(cx+r*math.cos(t),cz+r*math.sin(t)) for r in [r0,r1] for t in angles])
            result.append(solid(m["module_id"]+f":facet:{i}","conveyor",p,0,m["deck_y"]))
    for station in conveyor["packing_stations"]:
        name=station["pack_id"];x,_,z=station["table_origin"]
        w,h,d=station["table_dimensions_m"];opening=station["central_clear_opening_width_m"];side=(w-opening)/2
        for sign in [-1,1]:
            cx=x+sign*(opening/2+side/2);sid=name+"__side"+(".001" if sign==1 else "")
            add_box(sid,"packing",dict(min=[cx-side/2,0,z-d/2],max=[cx+side/2,h,z+d/2]),sid)
        cut=station["worktop_cutout_local_z"][1];sid=name+"__bridge"
        add_box(sid,"packing",dict(min=[x-opening/2,0,z+cut],max=[x+opening/2,h,z+d/2]),sid)
    for port in inbound["ports"]+outbound["ports"]:
        x,_,z=port["world_pos"];w,h,t=port["clear_width_m"],port["clear_height_m"],.25;n=port["inward_facing"]
        for sign in [-1,1]:
            sid=port["port_id"]+"__post"+(".001" if sign==1 else "")
            if n[0]:
                cx,cz=x+n[0]*t/2,z+sign*(w/2+t/2)
            else:
                cx,cz=x+sign*(w/2+t/2),z+n[2]*t/2
            add_box(sid,"gate_frame",dict(min=[cx-t/2,0,cz-t/2],max=[cx+t/2,h,cz+t/2]),sid)
        sid=port["port_id"]+"__header"
        if n[0]:
            b=dict(min=[min(x,x+n[0]*t),h,z-w/2-t],max=[max(x,x+n[0]*t),h+t,z+w/2+t])
        else:
            b=dict(min=[x-w/2-t,h,min(z,z+n[2]*t)],max=[x+w/2+t,h+t,max(z,z+n[2]*t)])
        add_box(sid,"gate_frame",b,sid)
    return result,dict(source_components_checked=len(matches),max_source_bound_error_m=max(matches),
                       physical_solids=len(result),by_category=dict(Counter(x["category"] for x in result)),
                       excluded_source_meshes=stats["source_meshes"]-132-87-18-18)


def pose(g, u):
    yaw=g["start_yaw_rad"]+u*(g["end_yaw_rad"]-g["start_yaw_rad"])
    if g["kind"]=="line":
        a,b=g["front_axle_start_xz_m"],g["front_axle_end_xz_m"]
        f=[a[i]+u*(b[i]-a[i]) for i in [0,1]]
    else:
        q,c=g["icr_vehicle_local_x_m"],g["icr_world_xz_m"]
        f=[c[0]-q*math.cos(yaw),c[1]+q*math.sin(yaw)]
    return [f[0]-.4*math.sin(yaw),f[1]-.4*math.cos(yaw)],yaw


def oriented(box, point, yaw, padding):
    c,s=math.cos(yaw),math.sin(yaw)
    return [(point[0]+x*c+z*s,point[1]-x*s+z*c) for x,z in [
        (box["min"][0]-padding,box["min"][2]-padding),
        (box["max"][0]+padding,box["min"][2]-padding),
        (box["max"][0]+padding,box["max"][2]+padding),
        (box["min"][0]-padding,box["max"][2]+padding)]]


def human_routes(ped, conveyor, storage):
    nodes={n["node_id"]:n["world_pos"][::2] for n in ped["nodes"]}
    modes={m["mode_id"]:m["clearance_radius_m"] for m in ped["modes"]}
    result=[]
    for edge in ped["edges"]:
        for mode in edge["allowed_modes"]:
            if mode not in modes:continue
            assert edge["width_m"]+EPS>=2*modes[mode]
            result.append(dict(id=edge["edge_id"]+":"+mode,source="L06",source_id=edge["edge_id"],mode=mode,radius=modes[mode],allowed_regions=[],
                               points=[nodes[edge["from_node_id"]],nodes[edge["to_node_id"]]]))
    for h in conveyor["manual_handoffs"]:
        for mode in h["allowed_modes"]:
            assert h["width_m"]+EPS>=2*modes[mode]
            result.append(dict(id=h["node_id"]+":connector:"+mode,source="L08",source_id=h["node_id"],mode=mode,radius=modes[mode],allowed_regions=["PACKING_LIGHT_LINE"],
                               points=[q[::2] for q in h["connector_path"]]))
    for path in storage["local_access_paths"]:
        if path["mode"]!="forklift":
            result.append(dict(id=path["path_id"],source="L09",source_id=path["path_id"],mode=path["mode"],radius=path["clearance_radius_m"],allowed_regions=path["allowed_storage_regions"],points=path["points_world_xz_m"]))
    return result


def vehicle_routes(vehicle, storage):
    profiles={p["profile_id"]:p for p in vehicle["profiles"]}
    result=[]
    for edge in vehicle["edges"]:
        # Largest admitted profile includes all smaller profiles on that edge.
        pid=next(p for p in ["loaded_max","empty_cradle","unloaded_bare"] if p in edge["allowed_profile_ids"])
        profile=profiles[pid]
        result.append(dict(id=edge["edge_id"],source="L07",source_id=edge["edge_id"],profile_id=pid,allowed_regions=[],
                           components=profile["component_bounds_local_m"],padding=profile["clearance_padding_m"],
                           top_padding=profile["top_padding_m"],segments=[edge["geometry"]],
                           allowed_profile_ids=edge["allowed_profile_ids"],clear_width_m=edge["clear_width_m"],clear_height_m=edge["clear_height_m"],
                           reservation_refs=edge["reservation_group_ids"]))
    for path in storage["local_access_paths"]:
        if path["mode"]=="forklift":
            profile=storage["access_profiles"][path["profile_id"]]
            result.append(dict(id=path["path_id"],source="L09",source_id=path["path_id"],profile_id=path["profile_id"],allowed_regions=path["allowed_storage_regions"],
                               components=profile["component_bounds_local_m"],padding=profile["padding_m"],top_padding=.25,
                               segments=path["segments"],reservation_refs=[]))
    return result


def profile_clearance(route):
    reasons=[]
    if "allowed_profile_ids" in route and route["profile_id"] not in route["allowed_profile_ids"]:
        reasons.append("PROFILE_FORBIDDEN")
    width=max(b["max"][0] for b in route["components"])-min(b["min"][0] for b in route["components"])+2*route["padding"]
    height=max(b["max"][1] for b in route["components"])+route["top_padding"]
    if width>route.get("clear_width_m",math.inf)+EPS:reasons.append("PROTECTED_WIDTH_TOO_NARROW")
    if height>route.get("clear_height_m",math.inf)+EPS:reasons.append("CLEAR_HEIGHT_TOO_LOW")
    return reasons,width,height


def region_blockers(route,zones,ped):
    """Protected allocated floor is not silently made drivable because empty."""
    result=[]
    for zone in zones["zones"]:
        if zone["kind"]=="circulation" or zone["zone_id"] in route["allowed_regions"]:continue
        lo,hi=zone["floor_bounds_xz_m"]["min"],zone["floor_bounds_xz_m"]["max"]
        cuts=[]
        if route["source"]=="L06":
            cuts=[r["floor_bounds_xz_m"] for r in ped["packing_clear_reservations"] if route["mode"] in r["allowed_modes"]]
        xs=sorted({lo[0],hi[0]}|{v for c in cuts for v in [c["min"][0],c["max"][0]] if lo[0]<v<hi[0]})
        zs=sorted({lo[1],hi[1]}|{v for c in cuts for v in [c["min"][1],c["max"][1]] if lo[1]<v<hi[1]})
        for xi,(x0,x1) in enumerate(zip(xs,xs[1:])):
            for zi,(z0,z1) in enumerate(zip(zs,zs[1:])):
                cx,cz=(x0+x1)/2,(z0+z1)/2
                if any(c["min"][0]<=cx<=c["max"][0] and c["min"][1]<=cz<=c["max"][1] for c in cuts):continue
                result.append(solid("RESERVED__"+zone["zone_id"]+f":{xi}:{zi}","allocated_floor_keepout",rect([x0,z0],[x1,z1]),0,8))
    return result


def swept_shapes(route, g):
    delta=abs(g["end_yaw_rad"]-g["start_yaw_rad"])
    arc=g["kind"]!="line"
    count=max(1,math.ceil(delta/math.radians(.5))) if arc else 1
    q=g.get("icr_vehicle_local_x_m",0)
    pad=route["padding"]
    rho=max(math.hypot(x-q,z-.4) for box in route["components"] for x in [box["min"][0]-pad,box["max"][0]+pad] for z in [box["min"][2]-pad,box["max"][2]+pad])
    extra=2*rho*math.sin(delta/(4*count)) if arc else 0
    for ci,box in enumerate(route["components"]):
        samples=[]
        for j in range(count+1):
            point,yaw=pose(g,j/count)
            samples.append(oriented(box,point,yaw,pad+extra))
        checked=samples if arc else [hull(samples[0]+samples[1])]
        # This hull may reserve extra inside corners; it never underbounds the arc.
        traffic=hull([q for sample in samples for q in sample])
        yield ci,box,checked,traffic,extra


def check_static(solids):
    index=Index(solids);findings=[]
    for a in solids:
        for b in index.query(a["bounds"]):
            if a["id"]>=b["id"]:continue
            if min(a["y_max"],b["y_max"])-max(a["y_min"],b["y_min"])<=1e-5:continue
            if poly_hit(a["poly"],b["poly"]):
                findings.append(dict(kind="physical_solid_overlap",a=a["id"],b=b["id"],
                                     overlap_aabb_xz=[max(a["bounds"][0],b["bounds"][0]),max(a["bounds"][1],b["bounds"][1]),min(a["bounds"][2],b["bounds"][2]),min(a["bounds"][3],b["bounds"][3])]))
    return findings


def protected_spaces(solids,zones,ports,stats):
    findings=[];gates=[];approaches=[]
    for s in solids:
        b=s["bounds"]
        if b[0]<-1e-5 or b[1]<-1e-5 or b[2]>144+1e-5 or b[3]>72+1e-5 or s["y_min"]<-1e-5 or s["y_max"]>8+1e-5:
            findings.append(dict(kind="static_outside_building",solid_id=s["id"],bounds_xz=b))
    for p in ports:
        x,_,z=p["world_pos"];w,h=p["clear_width_m"],p["clear_height_m"];n=p["inward_facing"]
        if n[0]:
            poly=rect([min(x,x+n[0]*.25),z-w/2],[max(x,x+n[0]*.25),z+w/2])
        else:
            poly=rect([x-w/2,min(z,z+n[2]*.25)],[x+w/2,max(z,z+n[2]*.25)])
        hits=[s["id"] for s in solids if s["y_min"]<h-EPS and s["y_max"]>EPS and poly_hit(poly,s["poly"])]
        findings += [dict(kind="blocked_gate_aperture",port_id=p["port_id"],blocker_id=s) for s in hits]
        parts=[c["bounds_runtime"] for c in stats["components"] if c["parent"]=="GATE__"+p["port_id"]]
        header=next(c for c in parts if c["min"][1]>.1);posts=sorted([c for c in parts if c!=header],key=lambda b:b["min"][2 if n[0] else 0])
        axis=2 if n[0] else 0;actualw=posts[1]["min"][axis]-posts[0]["max"][axis]
        assert abs(actualw-w)<1e-5 and abs(header["min"][1]-h)<1e-5
        gates.append(dict(port_id=p["port_id"],actual_clear_width_m=actualw,actual_clear_height_m=header["min"][1],blocked=bool(hits)))
        approach=next(c for c in zones["port_approach_context"] if c["port_id_context"]==p["port_id"])["keep_clear_overlay_xz_m"]
        ap=rect(approach["min"],approach["max"])
        # Own gate posts/frame intentionally bound this approach, not obstacles in it.
        blockers=[s["id"] for s in solids if s["category"]!="gate_frame" and poly_hit(ap,s["poly"])]
        findings += [dict(kind="blocked_port_approach",port_id=p["port_id"],blocker_id=s) for s in blockers]
        approaches.append(dict(port_id=p["port_id"],bounds_xz=approach,blocking_fixed_solids=len(blockers)))
    return findings,dict(actual_gate_apertures=gates,port_keep_clear_approaches=approaches)


def audit(solids, humans, vehicles,zones,ped):
    findings=[];counts=Counter();human_unique={};traffic={};cache=set();indices={}
    def blockers(route):
        key=(route["source"],route.get("mode"),tuple(route["allowed_regions"]))
        if key not in indices:indices[key]=Index(solids+region_blockers(route,zones,ped))
        return indices[key]
    for route in humans:
        index=blockers(route)
        for si,(a,b) in enumerate(zip(route["points"],route["points"][1:])):
            if math.dist(a,b)<EPS:continue
            counts["human_segments_including_shared_references"]+=1
            bounds=capsule_bounds(a,b,route["radius"])
            key=(tuple(sorted((tuple(a),tuple(b)))),route["radius"],route["mode"],tuple(route["allowed_regions"]),route["source"])
            if key in human_unique:
                human_unique[key]["route_refs"].add(route["id"]);continue
            h=dict(a=a,b=b,radius=route["radius"],mode=route["mode"],bounds=bounds,route_refs={route["id"]})
            human_unique[key]=h
            if bounds[0]<-EPS or bounds[1]<-EPS or bounds[2]>144+EPS or bounds[3]>72+EPS:
                findings.append(dict(kind="human_floor_boundary",route_id=route["id"],segment=si,bounds_xz=bounds))
            for obstacle in index.query(bounds):
                if obstacle["y_min"]>=1.7:continue
                if capsule_hit(a,b,route["radius"],obstacle["poly"]):
                    findings.append(dict(kind="human_static_collision",route_id=route["id"],segment=si,blocker_id=obstacle["id"],sweep_bounds_xz=bounds))
    for route in vehicles:
        index=blockers(route)
        reasons,width,height=profile_clearance(route)
        if reasons:
            findings.append(dict(kind="vehicle_profile_or_declared_clearance",route_id=route["id"],
                                 reason_codes=reasons,required_width_m=width,required_height_m=height))
        counts["vehicle_segments_including_shared_references"]+=len(route["segments"])
        for si,g in enumerate(route["segments"]):
            key=json.dumps([g,route["components"],route["padding"],route["allowed_regions"],route["source"]],sort_keys=True)
            if key in cache:
                counts["reused_vehicle_segment_proofs"]+=1
            cache.add(key)
            for ci,box,polygons,tpoly,extra in swept_shapes(route,g):
                tkey=tuple(sorted((round(x,7),round(z,7)) for x,z in tpoly))
                tkey=(tkey,round(box["min"][1],6),round(box["max"][1]+route["top_padding"],6))
                if tkey not in traffic:
                    traffic[tkey]=solid("sweep", "vehicle_sweep",tpoly,box["min"][1],box["max"][1]+route["top_padding"])
                    traffic[tkey]["route_refs"]=set();traffic[tkey]["profile_ids"]=set()
                traffic[tkey]["route_refs"].add(route["id"]);traffic[tkey]["profile_ids"].add(route["profile_id"])
                # Cache static proof per geometry/components; preserve all traffic refs.
                proof_key=(key,ci)
                if proof_key in cache:continue
                cache.add(proof_key)
                counts["unique_vehicle_component_sweeps"]+=1
                for poly in polygons:
                    counts["oriented_component_polygons_checked"]+=1
                    bounds=aabb(poly)
                    if bounds[0]<-EPS or bounds[1]<-EPS or bounds[2]>144+EPS or bounds[3]>72+EPS:
                        findings.append(dict(kind="vehicle_floor_boundary",route_id=route["id"],segment=si,component=ci,bounds_xz=bounds))
                    for obstacle in index.query(bounds):
                        if min(box["max"][1]+route["top_padding"],obstacle["y_max"])-max(box["min"][1],obstacle["y_min"])<=EPS:continue
                        if poly_hit(poly,obstacle["poly"]):
                            finding=dict(kind="vehicle_static_collision",route_id=route["id"],segment=si,component=ci,
                                         blocker_id=obstacle["id"],sweep_bounds_xz=bounds,arc_interval_inflation_m=extra)
                            if not findings or finding!=findings[-1]:findings.append(finding)
    counts["unique_human_capsules"]=len(human_unique);counts["traffic_sweep_hulls"]=len(traffic)
    return findings,dict(counts),list(human_unique.values()),list(traffic.values())


def crossings(humans, vehicles):
    index=Index(vehicles);resources={};candidate_pairs=0
    for h in humans:
        for v in index.query(h["bounds"]):
            if v["y_min"]>=1.7 or not capsule_hit(h["a"],h["b"],h["radius"],v["poly"]):continue
            candidate_pairs+=1
            intersection=[max(h["bounds"][0],v["bounds"][0]),max(h["bounds"][1],v["bounds"][1]),min(h["bounds"][2],v["bounds"][2]),min(h["bounds"][3],v["bounds"][3])]
            for x,z in cells(intersection):
                if (x,z) not in resources:
                    resources[x,z]=dict(resource_id=f"v3:traffic:cell:{x:02d}:{z:02d}",
                        floor_bounds_xz_m=dict(min=[x*GRID,z*GRID],max=[(x+1)*GRID,(z+1)*GRID]),
                        capacity_occupants=1,human_route_refs=set(),vehicle_route_refs=set(),human_modes=set(),vehicle_profile_ids=set())
                cell=resources[x,z]
                cell["human_route_refs"].update(h["route_refs"]);cell["vehicle_route_refs"].update(v["route_refs"])
                cell["human_modes"].add(h["mode"]);cell["vehicle_profile_ids"].update(v["profile_ids"])
    result=[]
    for key in sorted(resources):
        r=resources[key]
        for k in ["human_route_refs","vehicle_route_refs","human_modes","vehicle_profile_ids"]:r[k]=sorted(r[k])
        result.append(r)
    return result,candidate_pairs


def negative_cases(solids, humans, vehicles, vehicle_graph,zones,ports,stats):
    rack=solid("INJECTED_RACK_ON_BELT","storage",rect([80,2.8],[81,3.2]),0,2)
    rack_hits=[x for x in check_static(solids+[rack]) if rack["id"] in [x["a"],x["b"]]]
    assert rack_hits
    block=solid("INJECTED_BLOCKED_IN_W_GATE","storage",rect([0,17.5],[.25,18.5]),0,2)
    gate_findings,_=protected_spaces(solids+[block],zones,ports,stats)
    gate_hit=[f for f in gate_findings if f["kind"]=="blocked_gate_aperture" and f["port_id"]=="IN_W_BULK" and f["blocker_id"]==block["id"]]
    assert gate_hit
    edge=next(e for e in vehicle_graph["edges"] if e["allowed_profile_ids"]==["unloaded_bare"]
              and e["geometry"]["kind"]=="line" and not e.get("reverse_of_edge_id")
              and abs(e["geometry"]["front_axle_start_xz_m"][1]-10)<1e-8
              and abs(e["geometry"]["front_axle_end_xz_m"][1]-10)<1e-8)
    loaded=next(r for r in vehicles if r["profile_id"]=="loaded_max")
    denied=dict(loaded,allowed_profile_ids=edge["allowed_profile_ids"],clear_width_m=edge["clear_width_m"],clear_height_m=edge["clear_height_m"])
    reasons,required_width,_=profile_clearance(denied)
    assert reasons==["PROFILE_FORBIDDEN","PROTECTED_WIDTH_TOO_NARROW"]
    # Separate, explicitly injected physical shortcut, not an accepted graph edge.
    shortcut=dict(kind="line",front_axle_start_xz_m=[72,6],front_axle_end_xz_m=[72,4.8],start_yaw_rad=math.pi,end_yaw_rad=math.pi)
    forced=dict(loaded,id="negative_forced_loaded_into_packing",segments=[shortcut])
    collision=[]
    for _,_,polys,_,_ in swept_shapes(forced,shortcut):
        for poly in polys:
            collision += [s["id"] for s in solids if poly_hit(poly,s["poly"]) and s["y_min"]<2.1]
    assert collision,"Injected continuation into packing must hit actual geometry"
    return [dict(case="rack_on_belt",passed=True,result="PHYSICAL_SOLID_OVERLAP",injected_bounds_xz=rack["bounds"],hits=rack_hits),
            dict(case="blocked_gate",passed=True,result="PATH_CLEARANCE",injected_bounds_xz=block["bounds"],gate_id="IN_W_BULK",hits=gate_hit),
            dict(case="loaded_south_shortcut",passed=True,result=reasons,edge_id=edge["edge_id"],forced_profile="loaded_max",required_width_m=required_width,clear_width_m=edge["clear_width_m"]),
            dict(case="injected_loaded_continuation_into_packing",passed=True,result="PHYSICAL_COLLISION",injected_front_axle_points=[[72,6],[72,4.8]],blocker_ids=sorted(set(collision)))]


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--check-only",action="store_true");args=parser.parse_args()
    fingerprints=[dict(path=p,sha256=sha(ROOT/p)) for p in INPUTS]
    data=[read(p) for p in INPUTS if p.endswith(".json")]
    zones,inbound,outbound,l05,ped,vehicle,conveyor,storage,stats,policy=data
    assert policy["actor_count"]==len(set(policy["actor_ids"]))==24
    assert {(p["actor_id"],p["vehicle_id"]) for p in policy["forklift_pairs"]}=={("F01","FL01"),("F02","FL02")}
    solids,source_checks=physical(data)
    humans=human_routes(ped,conveyor,storage);vehicles=vehicle_routes(vehicle,storage)
    findings=check_static(solids)
    protected_findings,protected_checks=protected_spaces(solids,zones,inbound["ports"]+outbound["ports"],stats);findings+=protected_findings
    route_findings,counts,human_sweeps,vehicle_sweeps=audit(solids,humans,vehicles,zones,ped);findings+=route_findings
    resources,pairs=crossings(human_sweeps,vehicle_sweeps)
    negatives=negative_cases(solids,humans,vehicles,vehicle,zones,inbound["ports"]+outbound["ports"],stats)
    # Content is deterministic; execution time/provenance lives only in evidence.
    report=dict(document_kind="bounded_layout_spatial_audit_proposal",proposal_id="L11",proposal_version="0.1.0",
        layout_version="qoima-144x72-v3-proposal",units=dict(length="m",angle="radian",up_axis="Y"),
        audit_scope=dict(physical="L09 storage bounding volumes; L08 exact physical module footprints/turn facets and U packing envelopes; L10 actual frame mesh bounds.",
            excluded=["floor paint, labels, route overlay meshes, scale witness/height markers and asset-studio geometry","uninstantiated buffer cargo and future typed inventory","external truck paths, buffer-unit handling/insertion/lift/contact trajectories pending C08","final-art geometry not yet adopted into layout"],
            continuous_route_method="Exact human/cart capsules; constant-yaw vehicle convex swept rectangles; arcs <=0.5deg with 2*rho*sin(delta/4) displacement inflation using padded corner radii.",
            profile_reduction="Largest admitted L07 component profile encloses smaller profiles. L09 uses each declared exact access profile. No yaw from root tangent; no in-place turn.",
            allocated_floor="Non-circulation zones remain keep-outs except each L09 path's declared storage regions, L06 explicit mode-specific packing clear strips, and L08 manual connector permission in the packing zone. Empty allocated floor is not a new vehicle shortcut.",
            numerical_tolerance_m=1e-8,source_mesh_bound_tolerance_m=1e-5),
        source_geometry_checks=source_checks,protected_space_checks=protected_checks,
        counts=dict(human_routes=len(humans),vehicle_routes=len(vehicles),**counts),
        static_findings=findings,blocking_static_conflicts=len(findings),
        mixed_traffic=dict(scheduling_implemented=False,status="required_W_source_scheduler_input_not_runtime_behavior",
            method="Human capsules intersect conservative full vehicle-component sweep hulls; all intersected4m cells are reserved. Arc hulls/cell quantization may overreserve, never grant clearance.",
            grid_cell_size_m=GRID,conservative_sweep_pairs=pairs,resources=resources,
            reservation_rule="Before entering any listed sweep, reserve every associated shared traffic cell atomically in sorted resource_id order, together with existing vehicle/port/work resources; release only after the entire assembly clears. Deterministic grant/wait/deadlock policy remains W/backend work.",
            no_extra_agents="Existing24people and two F01/FL01,F02/FL02 pairs only. Cell resources are spatial exclusivity, never duplicated workers/vehicles.",
            existing_vehicle_reservation_refs=[r["reservation_group_id"] for r in vehicle["reservation_groups"]]),
        route_ref_index=[dict(route_ref=r["id"],source=r["source"],source_id=r["source_id"],mode=r.get("mode","forklift")) for r in humans+vehicles],
        shared_resources_preserved=dict(actor_count=policy["actor_count"],actor_ids=policy["actor_ids"],forklift_pairs=policy["forklift_pairs"],pools=policy["pools"]),
        negative_cases=negatives,operational_admission=False,
        read_only_input_fingerprints=fingerprints,
        limitations=["Numeric spatial audit does not close root-owned4.01% density or144m shadow-band composition findings.",
            "C02/C04/C08 cargo/mass/support/attachment and upper/reserve access remain required.",
            "No transit timing, traffic controller, backpressure execution, active inventory or backend KPI is implemented.",
            "Buffer floor allocation/count is not a proved pickup route. New final mesh bounds or changed layout require re-audit."])
    assert all(sha(ROOT/f["path"])==f["sha256"] for f in fingerprints),"Read-only source changed during audit"
    if args.check_only:
        assert json.loads(OUT.read_text())==report,"Saved audit differs from deterministic current audit"
    else:
        dump(OUT,report)
        evidence=dict(task_id="L11",status="ACTIVE",root_review="pending",checked_at_utc=datetime.now(timezone.utc).isoformat(),
            passed=not findings,blocking_static_conflicts=len(findings),counts=report["counts"],
            source_geometry_checks=source_checks,mixed_traffic_resources=len(resources),mixed_traffic_implemented=False,
            negative_cases=negatives,proposal=dict(path=str(OUT.relative_to(ROOT)).replace("\\","/"),sha256=sha(OUT)),
            generator=dict(path=str(Path(__file__).relative_to(ROOT)).replace("\\","/"),sha256=sha(Path(__file__))),
            source_fingerprints=fingerprints,
            graph_evidence=dict(tier=2,project="qoima-twin",generation="2026-11-06T22:22:36Z",coverage="Task-specific coverage call: new paths missing, accepted inputs not_tracked; no recorded parse issue is not completeness.",fallback="Exact current accepted JSON, L10 source/stats and L09 generator read directly. No extra index refresh."),
            composition_findings="Root SCENE_COMPOSITION_FINDINGS.md remains open; not closed by this numerical audit.")
        dump(EVIDENCE,evidence)
    print(json.dumps(dict(passed=not findings,blocking_static_conflicts=len(findings),source_geometry_checks=source_checks,
                          counts=report["counts"],mixed_traffic_resources=len(resources),negative_cases=len(negatives)),indent=2))
    if findings:
        print(json.dumps(findings[:12],indent=2));raise SystemExit(1)


if __name__=="__main__":
    main()
