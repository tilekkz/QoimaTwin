"""Isolated L12 semantic/graph/proposal-package compiler; no engine execution."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
import hashlib
import heapq
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/"docs/v3/contract-proposals/layout-semantic-index-v3.json"
EVIDENCE=ROOT/"docs/adaptive-v3/evidence/L12.1.json"
NAMES=["layout-v3.envelope","layout-v3.zones","ports-v3.inbound","ports-v3.outbound",
       "port-resource-policy-v3","large-gate-v3","pedestrian-graph-v3","vehicle-graph-v3",
       "conveyor-v3","storage-layout-v3","layout-conflicts-v3"]
PATHS=["docs/v3/contract-proposals/"+n+".json" for n in NAMES]+[
    "assets/references/v3/r03-dimension-targets.json","contracts/actors.example.json",
    "assets/v3/blender/layout-engineering.stats.json","frontend/public/models/v3/layout-engineering.glb"]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def escape(key):return str(key).replace("~","~0").replace("/","~1")


def resolve(doc,pointer):
    value=doc
    for part in pointer.split("/")[1:]:
        part=part.replace("~1","/").replace("~0","~")
        value=value[int(part)] if isinstance(value,list) else value[part]
    return value


class Registry:
    def __init__(self,docs):
        self.docs=docs;self.definitions={};self.references=[];self.locations=set()

    def define(self,kind,sid,source,pointer,origin="value",status="source_declared"):
        key=(kind,sid)
        if key in self.definitions:
            raise ValueError(f"DUPLICATE_DEFINITION {key} at {source}{pointer}; first={self.definitions[key]}")
        assert isinstance(sid,str) and sid
        self.definitions[key]=dict(kind=kind,id=sid,source_id=source,pointer=pointer,
                                  identity_origin=origin,definition_status=status)
        self.locations.add((kind,source,pointer))

    def ref(self,kind,sid,source,pointer):
        if sid is None:return
        assert isinstance(sid,str),(kind,source,pointer,sid)
        if (kind,source,pointer) not in self.locations:
            self.references.append(dict(kind=kind,id=sid,source_id=source,pointer=pointer))

    def validate(self):
        missing=[r for r in self.references if (r["kind"],r["id"]) not in self.definitions]
        if missing:raise ValueError("MISSING_REFERENCE "+json.dumps(missing[:8]))
        for d in self.definitions.values():
            if d["identity_origin"]=="object_key":
                actual=d["pointer"].split("/")[-1].replace("~1","/").replace("~0","~")
                resolve(self.docs[d["source_id"]],d["pointer"])
            else:actual=resolve(self.docs[d["source_id"]],d["pointer"])
            assert actual==d["id"],("DEFINITION_PROVENANCE_MISMATCH",d,actual)
        for r in self.references:
            assert resolve(self.docs[r["source_id"]],r["pointer"])==r["id"],("REFERENCE_PROVENANCE_MISMATCH",r)


def identities(policy,actors,ped):
    canonical=[a["actor_id"] for a in actors["actors"]]
    if len(canonical)!=len(set(canonical)) or len(canonical)!=24:
        raise ValueError("CANONICAL_ACTOR_IDENTITIES_INVALID")
    if policy["actor_count"]!=24 or sorted(policy["actor_ids"])!=sorted(canonical) or sorted(ped["actors"]["actor_ids"])!=sorted(canonical):
        raise ValueError("ACTOR_IDENTITY_MISMATCH")
    if {(p["actor_id"],p["vehicle_id"]) for p in policy["forklift_pairs"]}!={("F01","FL01"),("F02","FL02")}:
        raise ValueError("FORKLIFT_PAIR_IDENTITY_MISMATCH")
    return canonical


def service_aliases(ports,ped,vehicle):
    pn={n["node_id"]:n for n in ped["nodes"]};vn={n["node_id"]:n for n in vehicle["nodes"]};result=[]
    for p in ports:
        sid=p["service_node_id"];point=p["service_node_world_pos"]
        if pn[sid]["world_pos"]!=point or vn[sid]["world_pos"]!=point:
            raise ValueError("SHARED_SERVICE_POSITION_MISMATCH "+sid)
        result.append(dict(service_place_id=sid,port_id=p["port_id"],world_pos=point,
                           node_keys=[dict(kind="ped_node",id=sid),dict(kind="vehicle_node",id=sid)],
                           rule="Shared place only; graph mode/yaw/edge identities remain separate."))
    return sorted(result,key=lambda r:r["port_id"])


def walk_refs(reg,source,mapping,skip=(),special=None):
    def walk(value,path=""):
        if isinstance(value,dict):
            for key,child in value.items():
                p=path+"/"+escape(key)
                if key in skip:continue
                if special and special(key,child,p):continue
                if key in mapping:
                    kind=mapping[key]
                    values=list(enumerate(child)) if isinstance(child,list) else [(None,child)]
                    for i,item in values:
                        if item is None:continue
                        target=kind(item) if callable(kind) else kind
                        reg.ref(target,item,source,p+("/"+str(i) if i is not None else ""))
                walk(child,p)
        elif isinstance(value,list):
            for i,item in enumerate(value):walk(item,path+"/"+str(i))
    walk(reg.docs[source])


def compile_semantics(docs,sources):
    E,Z,IN,OUTP,POL,GATE,PED,VEH,CONV,STORE,AUDIT,TARGET,ACTORS,STATS,GLB=[s["source_id"] for s in sources]
    env,zones,inp,outp,policy,l05,ped,vehicle,conv,store,audit,targets,actors=[docs[s] for s in [E,Z,IN,OUTP,POL,GATE,PED,VEH,CONV,STORE,AUDIT,TARGET,ACTORS]]
    assert env["bounds"]==dict(min=[0,0,0],max=[144,8,72]) and env["units"]["length"]=="m" and env["units"]["time"]=="s"
    canonical=identities(policy,actors,ped);ports=inp["ports"]+outp["ports"]
    aliases=service_aliases(ports,ped,vehicle);r=Registry(docs)
    def table(source,name,key,kind):
        for i,item in enumerate(docs[source][name]):r.define(kind,item[key],source,f"/{name}/{i}/{key}")
    table(ACTORS,"actors","actor_id","actor")
    table(POL,"pools","pool_id","actor_pool");table(POL,"forklift_pairs","pair_id","equipment_pair");table(POL,"forklift_pairs","vehicle_id","vehicle")
    table(Z,"zones","zone_id","zone")
    for source in [IN,OUTP]:
        table(source,"ports","port_id","port");table(source,"ports","service_node_id","service_place")
        for i,p in enumerate(docs[source]["ports"]):
            for j,c in enumerate(p["finite_buffer_capacity"].get("buffer_cells",[])):
                r.define("buffer_cell",c["cell_id"],source,f"/ports/{i}/finite_buffer_capacity/buffer_cells/{j}/cell_id")
    table(TARGET,"archetypes","archetype_id","cargo_reference_target")
    for kind,path in [("vehicle_blueprint","/vehicle_blueprint/blueprint_id"),("load_orientation","/load_profile/orientation_id"),("attachment","/cradle_assumption/attachment_id")]:
        r.define(kind,resolve(l05,path),GATE,path)
    table(GATE,"gates","gate_id","large_gate")
    for name,key,kind in [("nodes","node_id","ped_node"),("edges","edge_id","ped_edge"),("modes","mode_id","transport_mode"),("packing_clear_reservations","reservation_id","clear_floor_reservation")]:table(PED,name,key,kind)
    for name,key,kind in [("profiles","profile_id","vehicle_profile"),("junctions","junction_id","vehicle_junction"),("nodes","node_id","vehicle_node"),("edges","edge_id","vehicle_edge"),("reservation_groups","reservation_group_id","vehicle_reservation")]:table(VEH,name,key,kind)
    for name,key,kind in [("nodes","node_id","conveyor_node"),("edges","edge_id","conveyor_edge"),("physical_modules","module_id","conveyor_module"),("cells","cell_id","conveyor_cell"),("resources","resource_id","conveyor_resource"),("packing_stations","pack_id","packing_station")]:table(CONV,name,key,kind)
    for i,h in enumerate(conv["manual_handoffs"]):
        r.define("manual_handoff",h["node_id"],CONV,f"/manual_handoffs/{i}/node_id")
        r.define("ped_node",h["node_id"],CONV,f"/manual_handoffs/{i}/node_id")
        r.define("ped_node",h["junction_node_id"],CONV,f"/manual_handoffs/{i}/junction_node_id")
    for family in store["module_definitions"]:r.define("storage_family",family,STORE,"/module_definitions/"+escape(family),"object_key")
    for name,key,kind in [("modules","module_id","storage_module"),("slots","slot_id","storage_slot"),("service_nodes","node_id","local_service"),("local_access_paths","path_id","local_path")]:table(STORE,name,key,kind)
    for pid in store["access_profiles"]:r.define("local_profile",pid,STORE,"/access_profiles/"+escape(pid),"object_key")
    r.define("storage_orientation",store["slots"][0]["allowed_orientation_ids"][0],STORE,"/slots/0/allowed_orientation_ids/0",status="derived_shared_enum_from_L09")
    firstfork=next(i for i,p in enumerate(store["local_access_paths"]) if p["mode"]=="forklift")
    r.define("transport_mode","forklift",STORE,f"/local_access_paths/{firstfork}/mode",status="derived_declared_mode_enum")
    for i,resource in enumerate(audit["mixed_traffic"]["resources"]):r.define("traffic_resource",resource["resource_id"],AUDIT,f"/mixed_traffic/resources/{i}/resource_id")
    table(AUDIT,"route_ref_index","route_ref","audit_route_ref")
    common=dict(allowed_cargo_archetype_ids="cargo_reference_target",cargo_archetype_ids="cargo_reference_target",archetype_id="cargo_reference_target",
                equipment_pair_refs="equipment_pair",forklift_pair_ref="equipment_pair",actor_ids="actor",actor_id="actor",vehicle_id="vehicle")
    skip=("read_only_input_fingerprints","source_of_assumption","source_assumptions","assumptions","verification_cases","negative_cases","deferred")
    walk_refs(r,POL,dict(actor_ids="actor",actor_id="actor",vehicle_id="vehicle"),skip)
    walk_refs(r,Z,dict(storage_type="storage_family",required_class_pairs="storage_family",port_id_context="port",related_staging_zone_ids="zone"),skip)
    for source in [IN,OUTP]:
        walk_refs(r,source,dict(common,port_id="port",service_node_id="service_place",available_equipment_refs="equipment_pair",
                               receiver_pool_ref="actor_pool",shipper_pool_ref="actor_pool",zone_id="zone",cell_id="buffer_cell"),skip)
    walk_refs(r,GATE,dict(common,port_id="port",service_node_id="service_place",pair_ref="equipment_pair"),skip)
    walk_refs(r,PED,dict(port_id="port",zone_id="zone",pack_id="packing_station",from_node_id="ped_node",to_node_id="ped_node",allowed_modes="transport_mode",
                         approach_node_id="ped_node",gateway_edge_ids="ped_edge",cart_stop_node_id="ped_node",service_node_id="ped_node",actor_ids="actor"),skip)
    for i,s in enumerate(ped["port_services"]):r.ref("ped_node",s["node_id"],PED,f"/port_services/{i}/node_id")
    walk_refs(r,VEH,dict(common,blueprint_id="vehicle_blueprint",relative_load_orientation_ref="load_orientation",junction_id="vehicle_junction",port_id="port",zone_id="zone",
                         allowed_profile_ids="vehicle_profile",reservation_group_ids="vehicle_reservation",reservation_group_id="vehicle_reservation",reverse_of_edge_id="vehicle_edge"),skip)
    for i,edge in enumerate(vehicle["edges"]):
        for field in ["from","to"]:r.ref("vehicle_node",edge[field],VEH,f"/edges/{i}/{field}")
    walk_refs(r,CONV,dict(from_node_id="conveyor_node",to_node_id="conveyor_node",turn_at_node_id="conveyor_node",resource_id="conveyor_resource",member_cell_ids="conveyor_cell",
                          pack_id="packing_station",work_node_id="conveyor_node",spur_resource_id="conveyor_resource",split_existing_edge_id="ped_edge",allowed_modes="transport_mode"),skip)
    def storage_special(key,value,path):
        if key!="start_reference":return False
        if value["graph"] not in ["L06","L07"]:raise ValueError("UNKNOWN_GRAPH_SELECTOR "+value["graph"])
        kinds=dict(node_id="ped_node" if value["graph"]=="L06" else "vehicle_node",edge_id="ped_edge" if value["graph"]=="L06" else "vehicle_edge")
        for field in ["node_id","edge_id"]:
            if field in value:r.ref(kinds[field],value[field],STORE,path+"/"+field)
        return True
    walk_refs(r,STORE,dict(module_id="storage_module",zone_id="zone",storage_type="storage_family",family="storage_family",allowed_cargo_archetype_ids="cargo_reference_target",
        allowed_orientation_ids="storage_orientation",service_node_id="local_service",cart_stop_id="local_service",worker_node_id="local_service",worker="local_service",vehicle="local_service",
        vehicle_approach_id="local_path",end_node_id="local_service",profile_id="local_profile",allowed_storage_regions="zone",mode="transport_mode"),skip,storage_special)
    def audit_profile(sid):return "vehicle_profile" if ("vehicle_profile",sid) in r.definitions else "local_profile"
    walk_refs(r,AUDIT,dict(human_route_refs="audit_route_ref",vehicle_route_refs="audit_route_ref",human_modes="transport_mode",vehicle_profile_ids=audit_profile,
                           existing_vehicle_reservation_refs="vehicle_reservation",actor_ids="actor",actor_id="actor",vehicle_id="vehicle"),skip+("source_geometry_checks","protected_space_checks"))
    for i,item in enumerate(audit["route_ref_index"]):
        kind={"L06":"ped_edge","L07":"vehicle_edge","L08":"manual_handoff","L09":"local_path"}[item["source"]]
        r.ref(kind,item["source_id"],AUDIT,f"/route_ref_index/{i}/source_id")
    r.validate()
    counts=dict(Counter(d["kind"] for d in r.definitions.values()))
    assert counts["actor"]==24 and counts["storage_module"]==132 and counts["storage_slot"]==776 and counts["port"]==6
    assert len({s["slot_id"] for s in store["slots"]})==776 and len(aliases)==6
    record=dict(schema_id="qoima.layout-semantic-index.v3-proposal",schema_version="0.1.0",layout_version=env["layout_version"],
        status="proposal",compilation_stage="semantic_index_only",operational_admission=False,
        units=dict(length="m",time="s",mass="kg",angle="radian",up_axis="Y",handedness="right"),
        envelope=dict(bounds=env["bounds"],origin=env["origin"],entity_dimension_scale_factor=1),
        sources=sources,identity_policy=dict(key=["kind","id"],original_ids_renamed=False,
            duplicates="Reject duplicate definitions within the same typed namespace, even equal payloads.",
            shared_service_rule="Six pedestrian/vehicle node IDs intentionally share canonical service-place IDs; coordinates must agree, modes/yaw never collapse.",
            derived_enums="Only existing L09 upright storage orientation and declared forklift mode are indexed as derived shared enums; not a canonical engine/cargo schema adoption."),
        definition_counts_by_kind=dict(sorted(counts.items())),definition_count=len(r.definitions),reference_count=len(r.references),
        definitions=[r.definitions[k] for k in sorted(r.definitions)],references=sorted(r.references,key=lambda x:(x["source_id"],x["pointer"],x["kind"],x["id"])),
        shared_service_places=aliases,graph_selectors=dict(L06="pedestrian-graph-v3.json; existing source only",L07="vehicle-graph-v3.json; existing source only"),
        validation=dict(duplicate_definitions=0,missing_references=0,source_pointer_mismatches=0,actor_identities_preserved=canonical,
                        storage_modules=132,storage_slots=776,ports=6,shared_service_aliases=6),
        bounded_scope=dict(indexed="Declared live entity tables and material relationship fields in accepted L01-L11 numeric proposals; exact definition/ref JSON Pointer provenance.",
            excluded=["negative/injected fixture IDs, assumption/case labels and free-text reason/mode guards",
                      "V2 actor positions/home nodes/roles: canonical actor file supplies identity only",
                      "L10 mesh-node names, route paint and diagnostic anchors are not layout semantic entities",
                      "R03 reference dimensions are targets pending C02 adoption, not SKU/lot inventory"],
            not_compiled=["L08/L09 edge splits and new adjacency","L07 vehicle fractional local graph connections",
                          "runtime public manifest or frontend integration","source traffic scheduling or simulation results"]),
        open_visual_findings="Root SCENE_COMPOSITION_FINDINGS.md density/lighting gates remain open.")
    return record,r


def negative_checks(reg,docs,sources):
    results=[]
    def reject(name,call,code):
        try:call()
        except (ValueError,AssertionError) as exc:
            assert code in str(exc),(name,str(exc));results.append(dict(case=name,passed=True,result=code));return
        raise AssertionError("NEGATIVE_WAS_ACCEPTED "+name)
    store_id=sources[9]["source_id"]
    clone=copy.deepcopy(docs);clone[store_id]["slots"].append(copy.deepcopy(clone[store_id]["slots"][0]))
    reject("duplicate_slot_definition_in_source",lambda:compile_semantics(clone,sources),"DUPLICATE_DEFINITION")
    clone=copy.deepcopy(docs);clone[store_id]["slots"][0]["module_id"]="v3:module:MISSING:999"
    reject("missing_module_reference_in_source",lambda:compile_semantics(clone,sources),"MISSING_REFERENCE")
    pol,ped,veh,actors=[docs[sources[i]["source_id"]] for i in [4,6,7,12]]
    wrong=copy.deepcopy(pol);wrong["actor_ids"][0]="P99"
    reject("substituted_actor_without_headcount_change",lambda:identities(wrong,actors,ped),"ACTOR_IDENTITY_MISMATCH")
    ports=docs[sources[2]["source_id"]]["ports"]+docs[sources[3]["source_id"]]["ports"]
    wrong=copy.deepcopy(veh);next(n for n in wrong["nodes"] if n["node_id"]==ports[0]["service_node_id"])["world_pos"][0]+=.1
    reject("same_service_id_different_graph_position",lambda:service_aliases(ports,ped,wrong),"SHARED_SERVICE_POSITION_MISMATCH")
    return results


def close(a,b,tol=1e-8):return math.dist(a,b)<=tol
def angle_delta(a,b):return (a-b+math.pi)%(2*math.pi)-math.pi


def add_node(nodes,sid,point,**meta):
    if sid in nodes:
        if not close(nodes[sid]["world_pos"],point):raise ValueError("NODE_POSITION_MISMATCH "+sid)
        return
    nodes[sid]=dict(node_id=sid,world_pos=list(point),**meta)


def add_walk_arcs(arcs,mapping,nodes,points,ids,source_id,mode_list,width,origin):
    compact=[]
    for p,sid in zip(points,ids):
        if compact and close(compact[-1][0],p):
            compact[-1]=(p,sid)  # The declared final semantic endpoint wins.
        else:compact.append((p,sid))
    for p,sid in compact:add_node(nodes,sid,p,source=origin)
    for i,((a,na),(b,nb)) in enumerate(zip(compact,compact[1:])):
        length=math.dist(a,b);assert length>1e-8 and width+1e-8>=max(.7 if m=="pedestrian" else 1.9 for m in mode_list)
        for rev in [False,True]:
            aid=source_id+f":segment:{i:03d}:"+("r" if rev else "f")
            arcs.append(dict(arc_id=aid,from_node_id=nb if rev else na,to_node_id=na if rev else nb,
                length_m=length,cost_m=length,width_m=width,clear_height_m=8,allowed_modes=list(mode_list),
                source=origin,source_route_id=source_id,direction="reverse" if rev else "forward"))
            mapping[source_id].append(aid)


def walk_split_intents(ped,conv,store):
    nodes={n["node_id"]:n for n in ped["nodes"]};edges={e["edge_id"]:e for e in ped["edges"]};result=[]
    for i,h in enumerate(conv["manual_handoffs"]):
        e=edges[h["split_existing_edge_id"]];a=nodes[e["from_node_id"]]["world_pos"];b=nodes[e["to_node_id"]]["world_pos"];p=h["junction_world_pos"]
        delta=[b[j]-a[j] for j in range(3)];u=sum((p[j]-a[j])*delta[j] for j in range(3))/sum(v*v for v in delta)
        result.append(dict(edge_id=e["edge_id"],u=u,node_id=h["junction_node_id"],world_pos=p,source=f"L08/manual_handoffs/{i}"))
    for i,p in enumerate(store["local_access_paths"]):
        ref=p["start_reference"]
        if p["mode"]!="forklift" and "edge_id" in ref:
            result.append(dict(edge_id=ref["edge_id"],u=ref["edge_u"],node_id=p["path_id"]+":attachment",
                               world_pos=[p["points_world_xz_m"][0][0],0,p["points_world_xz_m"][0][1]],source=f"L09/local_access_paths/{i}"))
    return result


def split_walk_base(ped,intents):
    nodes={n["node_id"]:dict(n) for n in ped["nodes"]};arcs=[];mapping=defaultdict(list);aliases={};groups=[];by_edge=defaultdict(list)
    for intent in intents:by_edge[intent["edge_id"]].append(intent)
    known={e["edge_id"] for e in ped["edges"]};assert set(by_edge)<=known
    for e in ped["edges"]:
        a,b=nodes[e["from_node_id"]]["world_pos"],nodes[e["to_node_id"]]["world_pos"];buckets=defaultdict(list)
        for intent in by_edge[e["edge_id"]]:
            u=intent["u"];expected=[a[j]+u*(b[j]-a[j]) for j in range(3)]
            if not -1e-10<=u<=1+1e-10 or not close(intent["world_pos"],expected):
                raise ValueError("INVALID_SPLIT_POSITION "+str(intent))
            buckets[round(max(0,min(1,u)),12)].append(intent)
        knots=[(0.,e["from_node_id"]), (1.,e["to_node_id"])]
        entries=[]
        for u,items in sorted(buckets.items()):
            sid=e["from_node_id"] if u==0 else e["to_node_id"] if u==1 else min(i["node_id"] for i in items)
            point=[a[j]+u*(b[j]-a[j]) for j in range(3)];add_node(nodes,sid,point,source="collected_split")
            for item in items:
                if item["node_id"]!=sid:aliases[item["node_id"]]=sid
            if 0<u<1:knots.append((u,sid))
            entries.append(dict(u=u,compiled_node_id=sid,intents=sorted(items,key=lambda q:(q["source"],q["node_id"]))))
        knots.sort()
        if entries:groups.append(dict(original_edge_id=e["edge_id"],ordered_splits=entries))
        for part,((u0,n0),(u1,n1)) in enumerate(zip(knots,knots[1:])):
            assert u1-u0>1e-10
            piece=e["edge_id"] if len(knots)==2 else e["edge_id"]+f":part:{part:03d}"
            for reverse in [False,True]:
                assert e["direction"]=="both" or not reverse
                aid=piece+(":r" if reverse else ":f");metadata={k:v for k,v in e.items() if k not in ["edge_id","from_node_id","to_node_id","length_m","cost_m","travel_time_s_by_mode","direction"]}
                arcs.append(dict(metadata,arc_id=aid,from_node_id=n1 if reverse else n0,to_node_id=n0 if reverse else n1,
                    length_m=e["length_m"]*(u1-u0),cost_m=e["cost_m"]*(u1-u0),
                    travel_time_s_by_mode={m:t*(u1-u0) for m,t in e["travel_time_s_by_mode"].items()},
                    source="L06",source_edge_id=e["edge_id"],source_u_range=[u1,u0] if reverse else [u0,u1],
                    direction="reverse" if reverse else "forward",clear_height_m=8))
                mapping[e["edge_id"]].append(aid)
    return nodes,arcs,mapping,aliases,groups


def compile_walk(ped,conv,store):
    intents=walk_split_intents(ped,conv,store)
    nodes,arcs,base_map,aliases,groups=split_walk_base(ped,intents);handoffs=defaultdict(list);local=defaultdict(list)
    local_nodes={n["node_id"]:n for n in store["service_nodes"]}
    for n in local_nodes.values():
        if n["kind"]!="forklift_pre_handle_stop":add_node(nodes,n["node_id"],n["world_pos"],source="L09",source_kind=n["kind"])
    for h in conv["manual_handoffs"]:
        start=aliases.get(h["junction_node_id"],h["junction_node_id"])
        add_walk_arcs(arcs,handoffs,nodes,h["connector_path"],[start,h["node_id"]],h["node_id"],h["allowed_modes"],h["width_m"],"L08")
    worker_cart={}
    for s in store["slots"]:
        a=s["access"];wid,cid=a["worker_node_id"],a["cart_stop_id"]
        assert wid not in worker_cart or worker_cart[wid]==cid;worker_cart[wid]=cid
    for path in store["local_access_paths"]:
        if path["mode"]=="forklift":continue
        points=[]
        for q in path["points_world_xz_m"]:
            point=[q[0],0,q[1]]
            if not points or not close(points[-1],point):points.append(point)
        ref=path["start_reference"];start=ref.get("node_id",path["path_id"]+":attachment")
        start=aliases.get(start,start);assert close(nodes[start]["world_pos"],points[0])
        ids=[path["path_id"]+f":point:{i:03d}" for i in range(len(points))];ids[0]=start;ids[-1]=path["end_node_id"]
        cart=worker_cart.get(path["end_node_id"])
        if cart and len(points)>2 and close(points[-2],local_nodes[cart]["world_pos"]):ids[-2]=cart
        add_walk_arcs(arcs,local,nodes,points,ids,path["path_id"],[path["mode"]],2*path["clearance_radius_m"],"L09")
    return dict(nodes=sorted(nodes.values(),key=lambda n:n["node_id"]),arcs=sorted(arcs,key=lambda a:a["arc_id"]),
                source_edge_arc_map=dict(sorted(base_map.items())),source_handoff_arc_map=dict(sorted(handoffs.items())),
                source_path_arc_map=dict(sorted(local.items())),source_edge_ids=[e["edge_id"] for e in ped["edges"]],
                split_groups=groups,node_aliases=aliases)


def vehicle_pose(g,u):
    yaw=g["start_yaw_rad"]+u*(g["end_yaw_rad"]-g["start_yaw_rad"])
    if g["kind"]=="line":
        a,b=g["front_axle_start_xz_m"],g["front_axle_end_xz_m"];f=[a[i]+u*(b[i]-a[i]) for i in [0,1]]
    else:
        c,q=g["icr_world_xz_m"],g["icr_vehicle_local_x_m"];f=[c[0]-q*math.cos(yaw),c[1]+q*math.sin(yaw)]
    return [f[0]-.4*math.sin(yaw),0,f[1]-.4*math.cos(yaw)],yaw,[f[0],0,f[1]]


def geometry_part(g,u0,u1):
    out=copy.deepcopy(g);out["start_yaw_rad"]=g["start_yaw_rad"]+u0*(g["end_yaw_rad"]-g["start_yaw_rad"]);out["end_yaw_rad"]=g["start_yaw_rad"]+u1*(g["end_yaw_rad"]-g["start_yaw_rad"])
    if g["kind"]=="line":
        out["front_axle_start_xz_m"]=vehicle_pose(g,u0)[2][::2];out["front_axle_end_xz_m"]=vehicle_pose(g,u1)[2][::2]
    return out


def geometry_lengths(g):
    if g["kind"]=="line":
        length=math.dist(g["front_axle_start_xz_m"],g["front_axle_end_xz_m"]);return length,length
    turn=abs(g["end_yaw_rad"]-g["start_yaw_rad"]);r=abs(g["icr_vehicle_local_x_m"])
    return r*turn,math.hypot(r,.4)*turn


def add_vehicle_node(nodes,sid,g,u,source):
    point,yaw,f=vehicle_pose(g,u)
    if sid in nodes:
        n=nodes[sid]
        if not close(n["world_pos"],point) or abs(angle_delta(n["yaw_rad"],yaw))>1e-8:raise ValueError("VEHICLE_POSE_MISMATCH "+sid)
    else:nodes[sid]=dict(node_id=sid,world_pos=point,yaw_rad=yaw%(2*math.pi),front_axle_world_pos=f,source=source)


def compile_vehicle(vehicle,store):
    original={e["edge_id"]:e for e in vehicle["edges"]};reverse={e["reverse_of_edge_id"]:e["edge_id"] for e in vehicle["edges"] if "reverse_of_edge_id" in e}
    nodes={n["node_id"]:dict(n) for n in vehicle["nodes"]};arcs=[];source_map=defaultdict(list);local_map=defaultdict(list);groups=defaultdict(dict)
    attachments={}
    for i,path in enumerate(store["local_access_paths"]):
        if path["mode"]!="forklift":continue
        ref=path["start_reference"]
        if "node_id" in ref:attachments[path["path_id"]]=ref["node_id"];continue
        e=original[ref["edge_id"]];base=e.get("reverse_of_edge_id",e["edge_id"]);u=1-ref["edge_u"] if "reverse_of_edge_id" in e else ref["edge_u"];u=max(0,min(1,u))
        assert 0<=ref["edge_u"]<=1
        key=round(u,12);base_edge=original[base]
        sid=base_edge["from"] if key==0 else base_edge["to"] if key==1 else base+f":split:{key:.12f}"
        add_vehicle_node(nodes,sid,base_edge["geometry"],u,"L09_fraction_on_L07")
        attachments[path["path_id"]]=sid
        bucket=groups[base].setdefault(key,dict(u=u,node_id=sid,source_refs=[]))
        bucket["source_refs"].append(dict(path_id=path["path_id"],edge_id=e["edge_id"],edge_u=ref["edge_u"],source_pointer=f"/local_access_paths/{i}/start_reference"))
    profile_alias={"long_loaded":"loaded_max","nonlong_forklift":"nonlong_forklift"}
    profiles={p["profile_id"]:p for p in vehicle["profiles"]}
    bare=profiles["unloaded_bare"]["component_bounds_local_m"][0]
    nonlong=store["access_profiles"]["nonlong_forklift"]["component_bounds_local_m"]
    assert all(all(bare["min"][j]-1e-8<=b["min"][j]<b["max"][j]<=bare["max"][j]+1e-8 for j in range(3)) for b in nonlong)
    assert store["access_profiles"]["long_loaded"]["component_bounds_local_m"]==profiles["loaded_max"]["component_bounds_local_m"]
    for e in vehicle["edges"]:
        base=e.get("reverse_of_edge_id",e["edge_id"]);rev="reverse_of_edge_id" in e
        split=[(1-b["u"] if rev else b["u"],b["node_id"]) for b in groups.get(base,{}).values() if 0<b["u"]<1]
        knots=sorted([(0.,e["from"]),(1.,e["to"])]+split)
        for i,((u0,n0),(u1,n1)) in enumerate(zip(knots,knots[1:])):
            g=geometry_part(e["geometry"],u0,u1);add_vehicle_node(nodes,n0,g,0,"L07");add_vehicle_node(nodes,n1,g,1,"L07")
            front,root=geometry_lengths(g);aid=e["edge_id"] if len(knots)==2 else e["edge_id"]+f":part:{i:03d}"
            allowed=list(e["allowed_profile_ids"])
            if "loaded_max" in allowed:allowed.append("nonlong_forklift")
            arcs.append(dict(arc_id=aid,from_node_id=n0,to_node_id=n1,geometry=g,motion_direction=e["motion_direction"],
                front_axle_path_length_m=front,length_m=root,cost_m=root,clear_width_m=e["clear_width_m"],clear_height_m=e["clear_height_m"],
                allowed_geometry_profile_ids=allowed,source_allowed_profile_ids=e["allowed_profile_ids"],
                allowed_cargo_archetype_ids=e["allowed_cargo_archetype_ids"],equipment_pair_refs=e["equipment_pair_refs"],
                source_reservation_group_ids=e["reservation_group_ids"],rear_virtual_steer_deg=e["rear_virtual_steer_deg"],
                curvature_transition=e["curvature_transition"],
                source="L07",source_edge_id=e["edge_id"],source_u_range=[u0,u1],source_role=e["role"]))
            source_map[e["edge_id"]].append(aid)
    slot_by_path=defaultdict(list)
    for slot in store["slots"]:
        if "vehicle_approach_id" in slot["access"]:slot_by_path[slot["access"]["vehicle_approach_id"]].append(slot)
    main_cargo=set(c for e in vehicle["edges"] for c in e["allowed_cargo_archetype_ids"])
    for path in store["local_access_paths"]:
        if path["mode"]!="forklift":continue
        source=path["path_id"];segments=path["segments"];ids=[attachments[source]]+[source+f":pose:{i:03d}" for i in range(1,len(segments))]+[path["end_node_id"]]
        cargo=sorted(set(c for s in slot_by_path[source] for c in s["allowed_cargo_archetype_ids"])&main_cargo)
        for i,g in enumerate(segments):
            add_vehicle_node(nodes,ids[i],g,0,"L09");add_vehicle_node(nodes,ids[i+1],g,1,"L09")
            front,root=geometry_lengths(g)
            for rev in [False,True]:
                geom=geometry_part(g,1,0) if rev else copy.deepcopy(g);aid=source+f":segment:{i:03d}:"+("r" if rev else "f")
                arcs.append(dict(arc_id=aid,from_node_id=ids[i+1] if rev else ids[i],to_node_id=ids[i] if rev else ids[i+1],
                    geometry=geom,motion_direction=-1 if rev else 1,front_axle_path_length_m=front,length_m=root,cost_m=root,
                    allowed_geometry_profile_ids=[profile_alias[path["profile_id"]]],source_profile_id=path["profile_id"],
                    allowed_cargo_archetype_ids=cargo,cargo_transport_supported=bool(cargo),equipment_pair_refs=vehicle["equipment_pair_refs"],source_reservation_group_ids=[],
                    clear_height_m=8,clearance_padding_m=.25,clearance_ref="L09/L11 complete component sweep; no uniform local corridor width invented",
                    source="L09",source_path_id=source,source_segment_index=i,direction="reverse_exit" if rev else "approach",
                    curvature_transition="Stop and set steering before changing curvature or reversing; preserve physical yaw. No source durations invented.",
                    rear_virtual_steer_deg=g["rear_virtual_steer_deg"],operational_admission=False))
                local_map[source].append(aid)
        end=next(n for n in store["service_nodes"] if n["node_id"]==path["end_node_id"])
        assert close(nodes[end["node_id"]]["world_pos"],end["world_pos"]) and abs(angle_delta(nodes[end["node_id"]]["yaw_rad"],end["yaw_rad"]))<1e-8
    return dict(nodes=sorted(nodes.values(),key=lambda n:n["node_id"]),arcs=sorted(arcs,key=lambda a:a["arc_id"]),
        source_edge_arc_map=dict(sorted(source_map.items())),source_path_arc_map=dict(sorted(local_map.items())),
        source_edge_ids=[e["edge_id"] for e in vehicle["edges"]],
        fractional_split_groups=[dict(original_forward_edge_id=k,reverse_edge_id=reverse.get(k),ordered_splits=[groups[k][u] for u in sorted(groups[k])]) for k in sorted(groups)],
        front_axle_root_offset_m=.4,pose_rule="Evaluate analytic geometry theta independently; root=F-.4*[sin(theta),0,cos(theta)]. Reverse changes motion sign, not facing by pi.",
        profile_aliases=profile_alias,profile_adapter=dict(nonlong_forklift="Main edges only when conservative loaded_max is already admitted; component containment verified. No bare-only loaded access or attachment change.",
            long_loaded="Exact component alias of L07 loaded_max.",cargo_rule="Local cargo permissions intersect unchanged L07 forklift classes; STANDARD_CARTON is excluded. C08 remains mandatory."))


def shortest(graph,start,mode=None,profile=None,cargo=None,reverse=False):
    adjacency=defaultdict(list);admissible=set()
    for a in graph["arcs"]:
        if mode and mode not in a.get("allowed_modes",[]):continue
        if profile and profile not in a.get("allowed_geometry_profile_ids",[]):continue
        if cargo and cargo not in a.get("allowed_cargo_archetype_ids",[]):continue
        x,y=(a["to_node_id"],a["from_node_id"]) if reverse else (a["from_node_id"],a["to_node_id"])
        adjacency[x].append((y,a["cost_m"],a["arc_id"]));admissible.update([x,y])
    if start not in admissible:return {},{}
    dist={start:0.};via={};heap=[(0.,start)]
    while heap:
        cost,node=heapq.heappop(heap)
        if cost>dist[node]+1e-10:continue
        for nxt,length,aid in adjacency[node]:
            new=cost+length
            if new<dist.get(nxt,math.inf)-1e-10:
                dist[nxt]=new;via[nxt]=(node,aid);heapq.heappush(heap,(new,nxt))
    return dist,via


def route_result(graph,start,end,**query):
    dist,via=shortest(graph,start,**query)
    if end not in dist:return dict(status="no_path",path_arc_ids=[],distance_m=None)
    path=[];n=end
    while n!=start:n,aid=via[n];path.append(aid)
    return dict(status="geometry_path",path_arc_ids=list(reversed(path)),distance_m=dist[end],operational_admission=False)


def validate_links(walk,veh,ped,vehicle,conv,store,ports):
    checks=[]
    def check(name,condition,actual=None):
        assert condition,(name,actual);checks.append(dict(name=name,passed=True,actual=actual))
    for graph in [walk,veh]:
        nd={n["node_id"]:n for n in graph["nodes"]};aa={a["arc_id"]:a for a in graph["arcs"]}
        check("unique_compiled_nodes_arcs",len(nd)==len(graph["nodes"]) and len(aa)==len(graph["arcs"]),dict(nodes=len(nd),arcs=len(aa)))
        check("positive_known_endpoint_arcs",all(a["from_node_id"] in nd and a["to_node_id"] in nd and a["cost_m"]>0 for a in aa.values()))
    wa={a["arc_id"]:a for a in walk["arcs"]};wn={n["node_id"]:n for n in walk["nodes"]}
    for e in ped["edges"]:
        arcs=[wa[aid] for aid in walk["source_edge_arc_map"][e["edge_id"]]]
        for direction in ["forward","reverse"]:
            parts=[a for a in arcs if a["direction"]==direction]
            assert abs(sum(a["cost_m"] for a in parts)-e["cost_m"])<1e-8
            assert all(a["allowed_modes"]==e["allowed_modes"] and a["width_m"]==e["width_m"] and a["access_restrictions"]==e["access_restrictions"] for a in parts)
    check("all54_original_walk_edges_preserve_cost_both_modes_directions",len(walk["source_edge_arc_map"])==54)
    check("walk_arc_lengths_equal_actual_endpoints",all(abs(math.dist(wn[a["from_node_id"]]["world_pos"],wn[a["to_node_id"]]["world_pos"])-a["length_m"])<1e-8 for a in wa.values()))
    edge46=[a for a in wa.values() if a.get("source_edge_id")=="v3:ped-edge:0046"]
    check("edge0046_three_pieces_six_arcs",len(edge46)==6,len(edge46))
    vn={n["node_id"]:n for n in veh["nodes"]};va={a["arc_id"]:a for a in veh["arcs"]}
    for a in va.values():
        for field,u in [("from_node_id",0),("to_node_id",1)]:
            p,yaw,f=vehicle_pose(a["geometry"],u);node=vn[a[field]]
            assert close(p,node["world_pos"]) and abs(angle_delta(yaw,node["yaw_rad"]))<1e-8 and close(f,node["front_axle_world_pos"])
        if a["geometry"]["kind"]=="line":assert abs(a["geometry"]["end_yaw_rad"]-a["geometry"]["start_yaw_rad"])<1e-8
    for e in vehicle["edges"]:
        arcs=[va[aid] for aid in veh["source_edge_arc_map"][e["edge_id"]]]
        assert abs(sum(a["length_m"] for a in arcs)-e["root_path_length_m"])<1e-8
        assert all(a["source_allowed_profile_ids"]==e["allowed_profile_ids"] and a["allowed_cargo_archetype_ids"]==e["allowed_cargo_archetype_ids"] and a["equipment_pair_refs"]==e["equipment_pair_refs"] and a["source_reservation_group_ids"]==e["reservation_group_ids"] for a in arcs)
    check("all284_original_vehicle_edges_preserve_geometry_cost_permissions",len(veh["source_edge_arc_map"])==284)
    reverse_pairs=0
    for path in store["local_access_paths"]:
        if path["mode"]!="forklift":continue
        for i in range(len(path["segments"])):
            a,b=va[path["path_id"]+f":segment:{i:03d}:f"],va[path["path_id"]+f":segment:{i:03d}:r"]
            assert a["rear_virtual_steer_deg"]==b["rear_virtual_steer_deg"] and a["motion_direction"]==-b["motion_direction"]
            for u in [0,.25,.5,.75,1]:
                ap,ay,_=vehicle_pose(a["geometry"],u);bp,by,_=vehicle_pose(b["geometry"],1-u)
                assert close(ap,bp) and abs(angle_delta(ay,by))<1e-8
            reverse_pairs+=1
    check("reverse_exits_preserve_physical_pose_and_steer",reverse_pairs==484,reverse_pairs)
    start=ports[0]["service_node_id"];manual_start=next(p["service_node_id"] for p in ports if p["port_id"]=="IN_E_PARCEL")
    pd,_=shortest(walk,manual_start,mode="pedestrian");cd,_=shortest(walk,manual_start,mode="manual_cart")
    check("all_six_ports_reachable_both_human_modes",all(p["service_node_id"] in pd and p["service_node_id"] in cd for p in ports),6)
    human=[n for n in store["service_nodes"] if n["kind"]!="forklift_pre_handle_stop"]
    carts=[n for n in human if n["kind"]=="manual_cart"]
    check("all728_local_human_floor_services_reachable",all(n["node_id"] in pd for n in human),len(human))
    check("all364_local_cart_stops_reachable_by_cart",all(n["node_id"] in cd for n in carts),len(carts))
    candidates=[s for s in store["slots"] if s["active_pick_candidate"]];manual=[s for s in candidates if s["manual_pick_allowed"]]
    check("all552_active_manual_primary_services_and_cart_stops",len(manual)==552 and all(s["service_node_id"] in pd and s["access"]["cart_stop_id"] in cd for s in manual),len(manual))
    vehicle_dist={};vehicle_back={}
    for profile,cargo in [("nonlong_forklift","HEAVY_BOX"),("nonlong_forklift","FRAGILE_CRATE"),("loaded_max","LONG_BUNDLE"),("nonlong_forklift",None)]:
        vehicle_dist[profile,cargo]=shortest(veh,start,profile=profile,cargo=cargo)[0]
        vehicle_back[profile,cargo]=shortest(veh,start,profile=profile,cargo=cargo,reverse=True)[0]
    reached=0
    for path in store["local_access_paths"]:
        if path["mode"]!="forklift":continue
        profile=veh["profile_aliases"][path["profile_id"]]
        cargo="LONG_BUNDLE" if profile=="loaded_max" else "HEAVY_BOX" if ":HEAVY_" in path["path_id"] else None if ":RESERVE_" in path["path_id"] else "FRAGILE_CRATE"
        key=(profile,cargo);assert path["end_node_id"] in vehicle_dist[key] and path["end_node_id"] in vehicle_back[key];reached+=1
    check("all116_prehandle_floor_poses_and_reverse_exits",reached==116,reached)
    for s in candidates:
        if s["manual_pick_allowed"]:continue
        key=("loaded_max","LONG_BUNDLE") if s["storage_type"]=="LONG" else ("nonlong_forklift","HEAVY_BOX")
        assert s["service_node_id"] in vehicle_dist[key]
    check("all588_active_primary_geometry_candidates",len(candidates)==588,len(candidates))
    check("all188_reserve_retrievals_still_blocked",all(s["retrieval_blocked"] and not s["active_pick_candidate"] for s in store["slots"] if s["reserve_only"]),sum(s["reserve_only"] for s in store["slots"]))
    bridge=route_result(walk,"v3:service:CART_PARK","v3:service:CONVEYOR_IN",mode="pedestrian")
    check("two0046_splits_connected_with_actual8_6m_bridge",bridge["status"]=="geometry_path" and abs(bridge["distance_m"]-8.6)<1e-8,bridge["distance_m"])
    check("cart_cannot_reach_pedestrian_only_handoff",route_result(walk,manual_start,"v3:service:CONVEYOR_IN",mode="manual_cart")["status"]=="no_path")
    worker=next(s["service_node_id"] for s in candidates if s["storage_type"]=="SMALL")
    check("cart_cannot_enter_worker_terminal",route_result(walk,manual_start,worker,mode="manual_cart")["status"]=="no_path")
    check("loaded_south_remains_no_path",route_result(veh,start,"v3:service:OUT_S_EXPRESS",profile="loaded_max",cargo="LONG_BUNDLE")["status"]=="no_path")
    reserve=next(p["end_node_id"] for p in store["local_access_paths"] if p["mode"]=="forklift" and ":RESERVE_" in p["path_id"])
    check("reserve_STANDARD_CARTON_forklift_transport_no_path",route_result(veh,start,reserve,profile="nonlong_forklift",cargo="STANDARD_CARTON")["status"]=="no_path")
    check("unknown_node_or_unsupported_mode_never_zero_distance_success",
        route_result(walk,"v3:missing","v3:missing",mode="pedestrian")["status"]=="no_path" and
        route_result(walk,worker,worker,mode="manual_cart")["status"]=="no_path")
    return checks,dict(human_ports=6,local_human_services=len(human),local_cart_stops=len(carts),active_manual_candidates=len(manual),
        active_primary_candidates=len(candidates),vehicle_prehandle_floor_poses=reached,conditional_vehicle_cargo_approaches=100,
        reserve_geometry_only_floor_links=16,blocked_reserve_addresses=188,
        source_floor_references=dict(manual=manual_start,vehicle=start,meaning="Geometric reachability references only; no port operation or C08 admission."),
        example_distances_m=dict(cartpark_to_intake_pedestrian=bridge["distance_m"]))


def link_robustness(ped,conv,store,walk,veh):
    intents=walk_split_intents(ped,conv,store);extra=copy.deepcopy(intents[-1]);extra["source"]="negative_duplicate_request"
    _,arcs,_,_,groups=split_walk_base(ped,intents+[extra])
    base_count=sum(len(ids) for ids in walk["source_edge_arc_map"].values())
    assert len(arcs)==base_count and all(a["cost_m"]>0 for a in arcs)
    assert sum(len(s["intents"]) for g in groups for s in g["ordered_splits"])==len(intents)+1
    results=[dict(case="duplicate_same_fraction_request",passed=True,result="COALESCED_WITHOUT_ZERO_EDGES_OR_LOST_PROVENANCE")]
    bad=copy.deepcopy(extra);bad["world_pos"][0]+=.2
    try:split_walk_base(ped,intents+[bad])
    except ValueError as exc:
        assert "INVALID_SPLIT_POSITION" in str(exc);results.append(dict(case="same_fraction_wrong_coordinate",passed=True,result="INVALID_SPLIT_POSITION"))
    else:raise AssertionError("Bad split accepted")
    arc=next(a for a in veh["arcs"] if a["source"]=="L09" and a["geometry"]["kind"]=="rear_steer_arc" and a["motion_direction"]==1)
    g=arc["geometry"];p,yaw,_=vehicle_pose(g,.5);p0=vehicle_pose(g,.49999)[0];p1=vehicle_pose(g,.50001)[0]
    tangent=math.atan2(p1[0]-p0[0],p1[2]-p0[2]);gap=abs(angle_delta(tangent,yaw))
    assert gap>math.radians(20)
    wrong={arc["from_node_id"]:dict(node_id=arc["from_node_id"],world_pos=p,yaw_rad=tangent)}
    try:add_vehicle_node(wrong,arc["from_node_id"],g,.5,"negative_tangent")
    except ValueError as exc:
        assert "VEHICLE_POSE_MISMATCH" in str(exc);results.append(dict(case="root_tangent_as_vehicle_yaw",passed=True,result="VEHICLE_POSE_MISMATCH",yaw_error_deg=math.degrees(gap)))
    else:raise AssertionError("Tangent yaw accepted")
    return results


def compile_links(docs,sources):
    ped,vehicle,conv,store,audit=[docs[sources[i]["source_id"]] for i in [6,7,8,9,10]]
    ports=docs[sources[2]["source_id"]]["ports"]+docs[sources[3]["source_id"]]["ports"]
    assert docs[sources[5]["source_id"]]["vehicle_blueprint"]["steering"]["front_axle_z_m"]==.4,"Accepted axle blueprint changed; revalidate analytic adapter"
    walk=compile_walk(ped,conv,store);veh=compile_vehicle(vehicle,store)
    checks,reach=validate_links(walk,veh,ped,vehicle,conv,store,ports);robust=link_robustness(ped,conv,store,walk,veh)
    wa={a["arc_id"]:a for a in walk["arcs"]};va={a["arc_id"]:a for a in veh["arcs"]};bindings=[]
    for r in audit["route_ref_index"]:
        source,sid,mode=r["source"],r["source_id"],r["mode"]
        if source=="L06":ids=walk["source_edge_arc_map"][sid]
        elif source=="L07":ids=veh["source_edge_arc_map"][sid]
        elif source=="L08":ids=walk["source_handoff_arc_map"][sid]
        else:ids=(veh if mode=="forklift" else walk)["source_path_arc_map"][sid]
        ids=sorted(a for a in ids if mode=="forklift" or mode in wa[a]["allowed_modes"])
        assert ids
        bindings.append(dict(route_ref=r["route_ref"],source=source,source_id=sid,mode=mode,
                             compiled_graph="vehicle" if mode=="forklift" else "walk",compiled_arc_ids=ids))
    assert len({b["route_ref"] for b in bindings})==1234
    known={b["route_ref"] for b in bindings}
    assert all(set(r["human_route_refs"]+r["vehicle_route_refs"])<=known for r in audit["mixed_traffic"]["resources"])
    result=dict(schema_id="qoima.layout-links.v3-proposal",schema_version="0.1.0",layout_version="qoima-144x72-v3-proposal",
        status="proposal",compilation_stage="graph_links_only",units=dict(length="m",time="s",angle="radian",up_axis="Y"),
        operational_admission=False,semantic_index=dict(path=str(OUT.relative_to(ROOT)).replace("\\","/"),sha256=sha(OUT)),
        accepted_source_fingerprints=sources,walk_graph=walk,vehicle_graph=veh,traffic_route_bindings=bindings,
        traffic_source=dict(path="docs/v3/contract-proposals/layout-conflicts-v3.json",resources=282,resolved_route_refs=len(bindings),
                            scheduling_implemented=False,rule="Resolve original resource route refs through traffic_route_bindings. No actual scheduler/grants/waits are created."),
        checks=checks,robustness_cases=robust,geometric_reachability=reach,
        limitations=["Geometry paths are not handler/cargo/attachment/lift admission or an actual engine run.",
                     "Reserve retrieval remains blocked; reachable floor pose does not approve upper lift.",
                     "Main nonlong adapter uses existing conservative loaded_max permission only; no bare-only loaded shortcut.",
                     "Travel time fields inherited from L06 are synthetic assumptions, not measured engine timings.",
                     "L12.3 public package not produced; density/lighting and final visual completeness remain root gates."])
    return result


def run_links(docs,sources,check_only):
    result=compile_links(docs,sources);path=ROOT/"docs/v3/contract-proposals/layout-links-v3.json";payload=(json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode()
    assert all(sha(ROOT/s["path"])==s["sha256"] for s in sources),"Source changed during link compilation"
    if check_only:assert path.read_bytes()==payload,"Link artifact differs from deterministic compilation"
    else:
        path.write_bytes(payload)
        evidence=dict(task_id="L12.2",status="ACTIVE",root_review="pending",checked_utc=datetime.now(timezone.utc).isoformat(),passed=True,
            output=dict(path=str(path.relative_to(ROOT)).replace("\\","/"),bytes=len(payload),sha256=sha(path)),
            compiler=dict(path=str(Path(__file__).relative_to(ROOT)).replace("\\","/"),sha256=sha(Path(__file__))),
            semantic_index_sha256=sha(OUT),counts=dict(walk_nodes=len(result["walk_graph"]["nodes"]),walk_arcs=len(result["walk_graph"]["arcs"]),
                vehicle_nodes=len(result["vehicle_graph"]["nodes"]),vehicle_arcs=len(result["vehicle_graph"]["arcs"]),traffic_route_bindings=len(result["traffic_route_bindings"])),
            geometric_reachability=result["geometric_reachability"],checks=result["checks"],robustness_cases=result["robustness_cases"],
            sources_unchanged=True,scheduling_implemented=False,operational_admission=False,public_package_created=False)
        (ROOT/"docs/adaptive-v3/evidence/L12.2.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(passed=True,walk_nodes=len(result["walk_graph"]["nodes"]),walk_arcs=len(result["walk_graph"]["arcs"]),
        vehicle_nodes=len(result["vehicle_graph"]["nodes"]),vehicle_arcs=len(result["vehicle_graph"]["arcs"]),
        reachability=result["geometric_reachability"],checks=len(result["checks"]),robustness_cases=len(result["robustness_cases"]),sha256=hashlib.sha256(payload).hexdigest()),indent=2))


def canonical_bytes(value,pretty=False):
    options=dict(ensure_ascii=False,sort_keys=True)
    options.update(dict(indent=2) if pretty else dict(separators=(",",":")))
    return (json.dumps(value,**options)+"\n").encode("utf-8")


def table_data(columns,records):
    return dict(columns=columns,rows=[[r.get(c) for c in columns] for r in records])


def unpack_table(table):
    columns=table["columns"]
    if len(set(columns))!=len(columns) or any(len(row)!=len(columns) for row in table["rows"]):
        raise ValueError("TABLE_SCHEMA_MISMATCH")
    return [dict(zip(columns,row)) for row in table["rows"]]


def compact_graph(graph,vehicle=False):
    nodes=graph["nodes"];node_index={n["node_id"]:i for i,n in enumerate(nodes)}
    node_columns=["node_id","world_pos"]+(["yaw_rad","front_axle_world_pos"] if vehicle else [])+["attributes"]
    node_rows=[]
    for n in nodes:
        row={k:n[k] for k in node_columns if k in n}
        row["attributes"]={k:v for k,v in n.items() if k not in node_columns}
        node_rows.append(row)
    transitions=sorted({a["curvature_transition"] for a in graph["arcs"]}) if vehicle else []
    arc_rows=[]
    for a in graph["arcs"]:
        row=dict(arc_id=a["arc_id"],from_node_index=node_index[a["from_node_id"]],to_node_index=node_index[a["to_node_id"]],
                 length_m=a["length_m"],cost_m=a["cost_m"])
        row["source_ref"]=dict(source=a["source"],source_id=a.get("source_edge_id",a.get("source_path_id",a.get("source_route_id"))))
        if "source_u_range" in a:row["source_ref"]["u_range"]=a["source_u_range"]
        if "source_segment_index" in a:row["source_ref"]["segment_index"]=a["source_segment_index"]
        if vehicle:
            row.update({k:a.get(k) for k in ["geometry","motion_direction","front_axle_path_length_m","clear_width_m","clear_height_m",
                "allowed_geometry_profile_ids","source_allowed_profile_ids","source_profile_id","allowed_cargo_archetype_ids",
                "cargo_transport_supported","equipment_pair_refs","source_reservation_group_ids","rear_virtual_steer_deg","clearance_padding_m"]})
            row["transition_rule_index"]=transitions.index(a["curvature_transition"])
        else:
            row.update({k:a.get(k) for k in ["width_m","clear_height_m","allowed_modes","forbidden_modes","state","access_restrictions"]})
        arc_rows.append(row)
    fields=["arc_id","from_node_index","to_node_index","length_m","cost_m"]+(
        ["geometry","motion_direction","front_axle_path_length_m","clear_width_m","clear_height_m","allowed_geometry_profile_ids",
         "source_allowed_profile_ids","source_profile_id","allowed_cargo_archetype_ids","cargo_transport_supported","equipment_pair_refs",
         "source_reservation_group_ids","rear_virtual_steer_deg","clearance_padding_m","transition_rule_index"] if vehicle else
        ["width_m","clear_height_m","allowed_modes","forbidden_modes","state","access_restrictions"])+["source_ref"]
    result=dict(nodes=table_data(node_columns,node_rows),arcs=table_data(fields,arc_rows))
    if vehicle:
        result.update(transition_rules=transitions,profile_aliases=graph["profile_aliases"],profile_adapter=graph["profile_adapter"],
                      front_axle_root_offset_m=graph["front_axle_root_offset_m"],pose_rule=graph["pose_rule"])
    return result,node_index,{a["arc_id"]:i for i,a in enumerate(graph["arcs"])}


def runtime_projection(docs,sources,links):
    env,zones,inp,outp,policy,l05,ped,vehicle,conv,store,audit,targets=[docs[sources[i]["source_id"]] for i in range(12)]
    walk,wn,wa=compact_graph(links["walk_graph"]);veh,vn,va=compact_graph(links["vehicle_graph"],True)
    zi={z["zone_id"]:i for i,z in enumerate(zones["zones"])};mi={m["module_id"]:i for i,m in enumerate(store["modules"])}
    module_rows=[dict(m,zone_index=zi[m["zone_id"]]) for m in store["modules"]]
    modules=table_data(["module_id","zone_index","family","world_pos","yaw_rad","outer_bounds_world","operating_bounds_world","row","aisle"],module_rows)
    slot_rows=[]
    for s in store["slots"]:
        sid=s["service_node_id"];access=s["access"]
        row=dict(s,module_index=mi[s["module_id"]],service_ref=["vehicle",vn[sid]] if sid in vn else ["walk",wn[sid]],
                 cart_stop_node_index=wn[access["cart_stop_id"]],worker_node_index=wn[access["worker_node_id"]],
                 vehicle_node_index=vn.get(access.get("vehicle")))
        slot_rows.append(row)
    slot_columns=["slot_id","module_index","level","bay","usable_dimensions_xyz_m","usable_bounds_world","usable_volume_m3","service_height_m",
        "bin_anchor","allowed_orientation_ids","allowed_cargo_archetype_ids","clearance_each_side_m","max_payload_kg","max_handling_units",
        "stacking_allowed","active_pick_candidate","reserve_only","retrieval_blocked","retrieval_block_reason","manual_gross_mass_limit_kg",
        "manual_pick_allowed","required_handler","service_ref","cart_stop_node_index","worker_node_index","vehicle_node_index"]
    binding_rows=[]
    for b in links["traffic_route_bindings"]:
        indices=va if b["compiled_graph"]=="vehicle" else wa
        binding_rows.append(dict(b,compiled_arc_indices=[indices[aid] for aid in b["compiled_arc_ids"]]))
    bi={b["route_ref"]:i for i,b in enumerate(binding_rows)}
    resource_rows=[dict(r,route_binding_indices=sorted({bi[x] for x in r["human_route_refs"]+r["vehicle_route_refs"]})) for r in audit["mixed_traffic"]["resources"]]
    return dict(envelope=dict(bounds=env["bounds"],origin=env["origin"],floor_area_m2=env["floor_area_m2"],entity_dimension_scale_factor=1),
        zones=zones["zones"],ports=inp["ports"]+outp["ports"],port_approach_context=zones["port_approach_context"],
        actor_resource_policy=policy,cargo_reference_targets=dict(status=targets["status"],archetypes=targets["archetypes"],catalog_adopted=False),
        storage=dict(module_definitions=store["module_definitions"],modules=modules,slots=table_data(slot_columns,slot_rows),
            access_profiles=store["access_profiles"],manual_access=store["manual_access"],reserve_policy=store["reserve_policy"],operational_admission=False),
        graphs=dict(walk=walk,vehicle=veh,human_modes=ped["modes"],vehicle_profiles=vehicle["profiles"]),
        vehicle_geometry=dict(blueprint=l05["vehicle_blueprint"],load_profile=l05["load_profile"],cradle_assumption=l05["cradle_assumption"],
                              nonlong_access_profile=store["access_profiles"]["nonlong_forklift"]),
        conveyor={k:conv[k] for k in ["geometry","nodes","edges","physical_modules","cells","resources","packing_stations","manual_handoffs",
                                    "source_assumptions","payload_admission","direction_policy","queue_policy","output_policy"]},
        traffic=dict(resources=table_data(["resource_id","floor_bounds_xz_m","capacity_occupants","route_binding_indices","human_modes","vehicle_profile_ids"],resource_rows),
            route_bindings=table_data(["route_ref","source","source_id","mode","compiled_graph","compiled_arc_indices"],binding_rows),
            vehicle_reservations=vehicle["reservation_groups"],clear_floor_reservations=ped["packing_clear_reservations"],
            reservation_rule=audit["mixed_traffic"]["reservation_rule"],scheduling_implemented=False))


def runtime_ids(data):
    result=dict(actor=list(data["actor_resource_policy"]["actor_ids"]),vehicle=[p["vehicle_id"] for p in data["actor_resource_policy"]["forklift_pairs"]],
        zone=[z["zone_id"] for z in data["zones"]],port=[p["port_id"] for p in data["ports"]],
        equipment_pair=[p["pair_id"] for p in data["actor_resource_policy"]["forklift_pairs"]],
        actor_pool=[p["pool_id"] for p in data["actor_resource_policy"]["pools"]],
        cargo_reference_target=[a["archetype_id"] for a in data["cargo_reference_targets"]["archetypes"]])
    for table_name,table,key in [
        ("storage_module",data["storage"]["modules"],"module_id"),("storage_slot",data["storage"]["slots"],"slot_id"),
        ("walk_node",data["graphs"]["walk"]["nodes"],"node_id"),("walk_arc",data["graphs"]["walk"]["arcs"],"arc_id"),
        ("vehicle_node",data["graphs"]["vehicle"]["nodes"],"node_id"),("vehicle_arc",data["graphs"]["vehicle"]["arcs"],"arc_id"),
        ("traffic_resource",data["traffic"]["resources"],"resource_id"),("traffic_route_ref",data["traffic"]["route_bindings"],"route_ref")]:
        result[table_name]=[r[key] for r in unpack_table(table)]
    for name,key,kind in [("nodes","node_id","conveyor_node"),("edges","edge_id","conveyor_edge"),("physical_modules","module_id","conveyor_module"),
                          ("cells","cell_id","conveyor_cell"),("resources","resource_id","conveyor_resource"),("packing_stations","pack_id","packing_station")]:
        result[kind]=[r[key] for r in data["conveyor"][name]]
    for kind,ids in result.items():
        if len(ids)!=len(set(ids)):raise ValueError("DUPLICATE_RUNTIME_ID "+kind)
    return result


def id_expectations(data):
    return {kind:dict(count=len(ids),sorted_ids_sha256=hashlib.sha256(canonical_bytes(sorted(ids))).hexdigest()) for kind,ids in sorted(runtime_ids(data).items())}


def valid_index(index,length):
    return isinstance(index,int) and not isinstance(index,bool) and 0<=index<length


def validate_runtime(manifest,raw,file_reader=None):
    if manifest.get("schema_id")!="qoima.layout-manifest.v3-proposal" or manifest.get("schema_version")!="0.1.0":raise ValueError("SCHEMA_VERSION_MISMATCH")
    if hashlib.sha256(raw).hexdigest()!=manifest["public_runtime"]["sha256"]:raise ValueError("PUBLIC_CHECKSUM_MISMATCH")
    runtime=json.loads(raw)
    if runtime.get("schema_id")!="qoima.layout-runtime.v3-proposal" or runtime.get("schema_version")!="0.1.0":raise ValueError("SCHEMA_VERSION_MISMATCH")
    if runtime.get("layout_version")!=manifest["layout_version"]:raise ValueError("LAYOUT_VERSION_MISMATCH")
    if runtime.get("layout_content_hash")!=manifest["layout_content_hash"] or runtime.get("upstream_fingerprints")!=manifest["inputs"][:-1]:raise ValueError("SOURCE_SNAPSHOT_MISMATCH")
    if runtime.get("units")!=manifest["units"]:raise ValueError("UNITS_OR_ENVELOPE_MISMATCH")
    if runtime.get("status")!="proposal" or runtime.get("data_kind")!="geometry_proposal" or any(runtime.get(k) is not False for k in ["operational_admission","scheduling_implemented","backend_integration_complete","visual_complete"]):
        raise ValueError("UNAPPROVED_OPERATIONAL_LABEL")
    data=runtime["data"];ids=runtime_ids(data)
    if id_expectations(data)!=manifest["id_expectations"]:raise ValueError("ID_SET_MISMATCH")
    if hashlib.sha256(canonical_bytes(data)).hexdigest()!=manifest["data_projection_sha256"]:raise ValueError("DATA_PROJECTION_MISMATCH")
    reader=file_reader or (lambda path:(ROOT/path).read_bytes())
    for source in manifest["inputs"]:
        try:body=reader(source["path"])
        except FileNotFoundError:raise ValueError("SOURCE_MISSING "+source["path"])
        if hashlib.sha256(body).hexdigest()!=source["sha256"]:raise ValueError("SOURCE_HASH_MISMATCH "+source["path"])
    graphs={}
    for name in ["walk","vehicle"]:
        graph=data["graphs"][name];nodes=unpack_table(graph["nodes"]);arcs=unpack_table(graph["arcs"]);graphs[name]=(nodes,arcs)
        for a in arcs:
            if not valid_index(a["from_node_index"],len(nodes)) or not valid_index(a["to_node_index"],len(nodes)) or a["cost_m"]<=0:raise ValueError("GRAPH_REFERENCE_MISMATCH")
            if name=="vehicle" and not valid_index(a["transition_rule_index"],len(graph["transition_rules"])):raise ValueError("TRANSITION_REFERENCE_MISMATCH")
    modules=unpack_table(data["storage"]["modules"]);slots=unpack_table(data["storage"]["slots"])
    for m in modules:
        if not valid_index(m["zone_index"],len(data["zones"])) or m["family"] not in data["storage"]["module_definitions"]:raise ValueError("MODULE_REFERENCE_MISMATCH")
    for s in slots:
        if not valid_index(s["module_index"],len(modules)):raise ValueError("SLOT_MODULE_REFERENCE_MISMATCH")
        graph,index=s["service_ref"]
        if graph not in graphs or not valid_index(index,len(graphs[graph][0])):raise ValueError("SERVICE_REFERENCE_MISMATCH")
        if not all(valid_index(s[k],len(graphs["walk"][0])) for k in ["cart_stop_node_index","worker_node_index"]):raise ValueError("HUMAN_SERVICE_REFERENCE_MISMATCH")
        if s["vehicle_node_index"] is not None and not valid_index(s["vehicle_node_index"],len(graphs["vehicle"][0])):raise ValueError("VEHICLE_SERVICE_REFERENCE_MISMATCH")
        if not set(s["allowed_cargo_archetype_ids"])<=set(ids["cargo_reference_target"]):raise ValueError("CARGO_REFERENCE_MISMATCH")
        if s["reserve_only"] and (not s["retrieval_blocked"] or s["active_pick_candidate"]):raise ValueError("RESERVE_ACCESS_CHANGED")
        if abs(math.prod(s["usable_dimensions_xyz_m"])-s["usable_volume_m3"])>1e-8:raise ValueError("USABLE_VOLUME_MISMATCH")
    bindings=unpack_table(data["traffic"]["route_bindings"]);resources=unpack_table(data["traffic"]["resources"])
    for b in bindings:
        if b["compiled_graph"] not in graphs:raise ValueError("TRAFFIC_GRAPH_REFERENCE_MISMATCH")
        aa=graphs[b["compiled_graph"]][1]
        for i in b["compiled_arc_indices"]:
            if not valid_index(i,len(aa)):raise ValueError("TRAFFIC_ARC_REFERENCE_MISMATCH")
            if b["compiled_graph"]=="walk" and b["mode"] not in aa[i]["allowed_modes"]:raise ValueError("TRAFFIC_MODE_MISMATCH")
    for r in resources:
        if r["capacity_occupants"]!=1 or not all(valid_index(i,len(bindings)) for i in r["route_binding_indices"]):raise ValueError("TRAFFIC_RESOURCE_REFERENCE_MISMATCH")
    expected=dict(actor=24,vehicle=2,port=6,zone=40,storage_module=132,storage_slot=776,walk_node=1633,walk_arc=4000,
                  vehicle_node=620,vehicle_arc=1316,traffic_resource=282,traffic_route_ref=1234)
    if any(len(ids[k])!=n for k,n in expected.items()):raise ValueError("EXPECTED_COUNT_MISMATCH")
    if data["envelope"]!=manifest["envelope"] or data["envelope"]["bounds"]!=dict(min=[0,0,0],max=[144,8,72]) or data["traffic"]["scheduling_implemented"] is not False:raise ValueError("ENVELOPE_OR_TRAFFIC_LABEL_MISMATCH")
    return dict(validated_files=len(manifest["inputs"]),validated_tables=8,counts={k:len(v) for k,v in ids.items()},
                active_geometry_candidates=sum(s["active_pick_candidate"] for s in slots),blocked_reserve=sum(s["reserve_only"] and s["retrieval_blocked"] for s in slots))


def package_objects(docs,sources,links):
    links_path=ROOT/"docs/v3/contract-proposals/layout-links-v3.json"
    dependencies=[dict(path=s["path"],sha256=s["sha256"],bytes=s["bytes"]) for s in sources]
    dependencies += [dict(path=str(p.relative_to(ROOT)).replace("\\","/"),sha256=sha(p),bytes=p.stat().st_size) for p in [OUT,links_path]]
    snapshot=hashlib.sha256(canonical_bytes(dependencies)).hexdigest()
    data=runtime_projection(docs,sources,links)
    runtime=dict(schema_id="qoima.layout-runtime.v3-proposal",schema_version="0.1.0",layout_version="qoima-144x72-v3-proposal",
        status="proposal",data_kind="geometry_proposal",layout_content_hash=snapshot,operational_admission=False,
        scheduling_implemented=False,backend_integration_complete=False,visual_complete=False,
        units=dict(length="m",time="s",mass="kg",angle="radian",up_axis="Y",handedness="right"),
        table_format="Table columns name each cell; rows use zero-based indices into same-package tables. Original semantic IDs remain in ID columns. Never reuse numeric indices across layout_content_hash.",
        upstream_fingerprints=dependencies,data=data,
        inventory_state="not_initialized; no SKU/lot/stock or engine work events are fabricated",
        open_gates=["C02/C04/C08 actual cargo/mass/support/lift and handler admission","W actual scheduling and source replay","root density/lighting/final visual completeness"])
    raw=canonical_bytes(runtime)
    assert len(raw)<2500000,("Compact public package exceeds2.5MB",len(raw))
    dependencies=dependencies+[dict(path=str(Path(__file__).relative_to(ROOT)).replace("\\","/"),sha256=sha(Path(__file__)),bytes=Path(__file__).stat().st_size)]
    manifest=dict(schema_id="qoima.layout-manifest.v3-proposal",schema_version="0.1.0",layout_version=runtime["layout_version"],
        status="proposal",data_kind="geometry_proposal",layout_content_hash=snapshot,operational_admission=False,scheduling_implemented=False,
        units=runtime["units"],envelope=data["envelope"],
        inputs=dependencies,id_expectations=id_expectations(data),data_projection_sha256=hashlib.sha256(canonical_bytes(data)).hexdigest(),
        public_runtime=dict(path="frontend/public/data/adaptive-v3/layout-manifest.json",url="/data/adaptive-v3/layout-manifest.json",
            schema_id=runtime["schema_id"],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),
        compatibility=dict(shared_v2_contracts_modified=False,backend_adapter_implemented=False,
            semantic_index_sha256=sha(OUT),compiled_links_sha256=sha(links_path),numeric_references_bound_to_layout_content_hash=True),
        scope="Final isolated L12 geometry/data proposal. Not actual engine integration, cargo admission, inventory, scheduling or final-art approval.")
    return manifest,runtime,raw


def package_mutations(manifest,runtime,raw):
    cases=[]
    def reject(name,m,body,code,reader=None):
        try:validate_runtime(m,body,reader)
        except ValueError as exc:
            assert code in str(exc),(name,str(exc));cases.append(dict(case=name,passed=True,result=code));return
        raise AssertionError("MUTATION_ACCEPTED "+name)
    reject("public_bytes_changed",manifest,raw+b" ","PUBLIC_CHECKSUM_MISMATCH")
    target=manifest["inputs"][0]["path"]
    reject("accepted_source_bytes_changed",manifest,raw,"SOURCE_HASH_MISMATCH",lambda p:(ROOT/p).read_bytes()+(b"\n" if p==target else b""))
    def missing_reader(path):
        if path==target:raise FileNotFoundError(path)
        return (ROOT/path).read_bytes()
    reject("referenced_file_missing",manifest,raw,"SOURCE_MISSING",missing_reader)
    changed=copy.deepcopy(runtime);rows=changed["data"]["storage"]["slots"];col=rows["columns"].index("slot_id");rows["rows"][1][col]=rows["rows"][0][col]
    body=canonical_bytes(changed);m=copy.deepcopy(manifest);m["public_runtime"]["sha256"]=hashlib.sha256(body).hexdigest()
    reject("duplicate_slot_even_if_outer_checksum_recomputed",m,body,"DUPLICATE_RUNTIME_ID")
    changed=copy.deepcopy(runtime);changed["layout_version"]="qoima-72x48-v2";body=canonical_bytes(changed);m=copy.deepcopy(manifest);m["public_runtime"]["sha256"]=hashlib.sha256(body).hexdigest()
    reject("wrong_layout_version_even_if_rehashed",m,body,"LAYOUT_VERSION_MISMATCH")
    changed=copy.deepcopy(runtime);changed["operational_admission"]=True;body=canonical_bytes(changed);m=copy.deepcopy(manifest);m["public_runtime"]["sha256"]=hashlib.sha256(body).hexdigest()
    reject("unapproved_operational_claim_even_if_rehashed",m,body,"UNAPPROVED_OPERATIONAL_LABEL")
    changed=copy.deepcopy(runtime);changed["units"]["length"]="ft";body=canonical_bytes(changed);m=copy.deepcopy(manifest);m["public_runtime"]["sha256"]=hashlib.sha256(body).hexdigest()
    reject("wrong_units_even_if_rehashed",m,body,"UNITS_OR_ENVELOPE_MISMATCH")
    changed=copy.deepcopy(runtime);changed["layout_content_hash"]="0"*64;body=canonical_bytes(changed);m=copy.deepcopy(manifest);m["public_runtime"]["sha256"]=hashlib.sha256(body).hexdigest()
    reject("source_snapshot_mismatch_even_if_rehashed",m,body,"SOURCE_SNAPSHOT_MISMATCH")
    return cases


def run_package(docs,sources,check_only):
    links=compile_links(docs,sources);links_path=ROOT/"docs/v3/contract-proposals/layout-links-v3.json"
    assert links_path.read_bytes()==(json.dumps(links,ensure_ascii=False,indent=2)+"\n").encode(),"Accepted links differ; do not silently rewrite"
    old_evidence=[ROOT/f"docs/adaptive-v3/evidence/L12.{i}.json" for i in [1,2]];before={str(p.relative_to(ROOT)):sha(p) for p in old_evidence}
    manifest,runtime,raw=package_objects(docs,sources,links);validation=validate_runtime(manifest,raw);negatives=package_mutations(manifest,runtime,raw)
    target=ROOT/manifest["public_runtime"]["path"];private=ROOT/"docs/v3/contract-proposals/layout-manifest-v3.json";private_bytes=canonical_bytes(manifest,True)
    if check_only:
        assert target.read_bytes()==raw,"Public runtime differs from canonical current package"
        assert private.read_bytes()==private_bytes,"Private manifest differs from canonical current package"
    else:
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);private.write_bytes(private_bytes)
        evidence=dict(task_id="L12.3",status="ACTIVE",root_review="pending",checked_utc=datetime.now(timezone.utc).isoformat(),passed=True,
            private_manifest=dict(path=str(private.relative_to(ROOT)).replace("\\","/"),sha256=sha(private),bytes=len(private_bytes)),
            public_runtime=manifest["public_runtime"],layout_content_hash=manifest["layout_content_hash"],validation=validation,negative_cases=negatives,
            semantic_index_sha256=sha(OUT),links_sha256=sha(links_path),previous_evidence_preserved=before,
            compiler=dict(path=str(Path(__file__).relative_to(ROOT)).replace("\\","/"),sha256=sha(Path(__file__))),
            root_http_browser_check="pending",operational_admission=False,scheduling_implemented=False)
        (ROOT/"docs/adaptive-v3/evidence/L12.3.json").write_bytes(canonical_bytes(evidence,True))
    assert before=={str(p.relative_to(ROOT)):sha(p) for p in old_evidence},"Previous child evidence changed during packaging"
    print(json.dumps(dict(passed=True,public_bytes=len(raw),public_sha256=hashlib.sha256(raw).hexdigest(),
        private_sha256=hashlib.sha256(private_bytes).hexdigest(),layout_content_hash=manifest["layout_content_hash"],
        validated_files=validation["validated_files"],counts=validation["counts"],negative_cases=len(negatives)),indent=2))


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--check-only",action="store_true");parser.add_argument("--stage",choices=["semantic","links","package"],default="semantic");args=parser.parse_args()
    sources=[];docs={}
    for i,path in enumerate(PATHS):
        sid=f"S{i+1:02d}";p=ROOT/path
        sources.append(dict(source_id=sid,path=path,bytes=p.stat().st_size,sha256=sha(p),
                            role="diagnostic_engineering_asset_not_semantic_authority" if i>=13 else "identity_only_no_v2_geometry_import" if i==12 else "accepted_proposal_or_reference_target"))
        if path.endswith(".json"):docs[sid]=json.loads(p.read_text(encoding="utf-8-sig"))
    result,reg=compile_semantics(docs,sources);negatives=negative_checks(reg,docs,sources)
    assert all(sha(ROOT/s["path"])==s["sha256"] for s in sources),"Source changed during compile"
    payload=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if args.stage in ["links","package"]:
        assert OUT.read_bytes()==payload.encode("utf-8"),"Accepted semantic index is not current; do not silently rewrite it"
        (run_package if args.stage=="package" else run_links)(docs,sources,args.check_only);return
    if args.check_only:assert OUT.read_bytes()==payload.encode("utf-8"),"Semantic index differs from deterministic current compilation"
    else:
        OUT.write_text(payload,encoding="utf-8",newline="\n")
        evidence=dict(task_id="L12.1",status="ACTIVE",root_review="pending",checked_utc=datetime.now(timezone.utc).isoformat(),
            passed=True,stage="semantic_index_only",definition_count=result["definition_count"],reference_count=result["reference_count"],
            counts_by_kind=result["definition_counts_by_kind"],validation=result["validation"],negative_cases=negatives,
            output=dict(path=str(OUT.relative_to(ROOT)).replace("\\","/"),bytes=OUT.stat().st_size,sha256=sha(OUT)),
            compiler=dict(path=str(Path(__file__).relative_to(ROOT)).replace("\\","/"),sha256=sha(Path(__file__))),
            source_count=len(sources),source_hashes_verified_unchanged=True,
            graph_evidence=dict(tier=2,project="qoima-twin",generation="2026-11-06T22:22:36Z",
                                coverage="New paths missing; current accepted paths not_tracked. Exact current source/JSON fallback; no index completeness claim."),
            next_stage_not_implemented="L12.2 split collection/graph links and L12.3 public manifest are gated separately.")
        EVIDENCE.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(passed=True,definition_count=result["definition_count"],reference_count=result["reference_count"],
                         counts=result["definition_counts_by_kind"],negative_cases=len(negatives),sha256=hashlib.sha256(payload.encode()).hexdigest()),indent=2))


if __name__=="__main__":main()
