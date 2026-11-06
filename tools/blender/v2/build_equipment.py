"""Adapt reviewed v1 equipment into v2 with functional runtime attachment nodes.

The v1 builders are imported only for geometry; their __main__/finish never run.
Named joints use runtime Y-up axes. Neutral-pose sources retain individual parts.
"""
from pathlib import Path
import json
import math
import sys

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from v2_common import reset, group, box, cylinder, beam, material, xyz, finish

sys.path.insert(0, str(HERE.parent))
import build_forklift as source_forklift
import build_packing_station as source_packing
import build_buffer_pallet as source_pallet
import build_crate as source_crate

ASSET_IDS = ("forklift", "packing-station", "buffer-pallet", "pallet", "crate")
AXIS_CONVERSION = Matrix(((1,0,0,0), (0,0,1,0), (0,-1,0,0), (0,0,0,1)))


def _children(root, prefix):
    return [obj for obj in root.children_recursive if obj.type == "MESH"
            and obj.name.startswith(prefix)]


def _reparent(parts, parent):
    bpy.context.view_layer.update()
    for obj in parts:
        world = obj.matrix_world.copy()
        obj.parent = parent
        obj.matrix_world = world
    bpy.context.view_layer.update()


def _node(root, name, pos, role="attachment", parent=None, normal=None):
    node = group(name)
    node.parent = parent or root
    world = Matrix.Translation(xyz(pos))
    if normal is not None:
        rotation = xyz(normal).normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
        world = world @ rotation
    bpy.context.view_layer.update()
    node.matrix_world = world
    node.empty_display_type = "ARROWS"
    node.empty_display_size = .08
    node["role"] = role
    node["coordinate_system"] = "runtime_Y_up_m"
    bpy.context.view_layer.update()
    return node


def _joint(root, name, pos, motion, axis, minimum, maximum, parent=None, normal=None):
    node = _node(root, name, pos, "functional_pivot", parent, normal)
    node["motion"] = motion
    node["axis_local_runtime"] = list(axis)
    node["minimum"] = minimum
    node["maximum"] = maximum
    node["units"] = "m" if motion == "translation" else "radians"
    return node


def _metadata(root, asset_id, reference, origin):
    root["asset_id"] = asset_id
    root["layout_version"] = "qoima-72x48-v2"
    root["reference"] = reference
    root["forward_axis"] = "+Z"
    root["origin"] = origin
    root["animation_api_version"] = "1.0"
    return root


def _fork_blade(obj, side):
    # A flat 30mm heel section fits below the pallet's 53mm deck underside;
    # only the last 120mm tapers. The original 51mm tall wedge could not enter.
    vertices = []
    x = side*.225
    for z, half_width, top in ((.49,.057,.045), (1.18,.057,.045), (1.30,.047,.025)):
        vertices += [(x-half_width,.015,z), (x+half_width,.015,z),
                     (x+half_width,top,z), (x-half_width,top,z)]
    faces = [(0,3,2,1), (8,9,10,11)]
    for section in range(2):
        offset = section*4
        for i in range(4):
            j = (i+1)%4
            faces.append((offset+i,offset+j,offset+j+4,offset+i+4))
    obj.data.clear_geometry()
    obj.data.from_pydata([tuple(xyz(v)) for v in vertices], [], faces)
    obj.data.update()
    # Consistent outward normals, including the new flat support surface.
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    for modifier in obj.modifiers:
        if modifier.type == "BEVEL":
            modifier.width = .002


def forklift():
    root = source_forklift.build()
    _metadata(root, "forklift", "assets/references/forklift.png", "floor_centre")
    root["role"] = "forklift"
    root["preserve_articulation"] = True
    root["fork_top_height_m"] = .045
    root["pallet_deck_underside_m"] = .116
    root["pickup_contact_lift_m"] = .071
    root["pallet_attach_minimum_lift_m"] = .071
    root["buffer_pickup_contact_lift_m"] = .008
    root["carriage_lift_maximum_m"] = 1.0
    for side, name in ((-1,"left"), (1,"right")):
        for axle, y, z in (("front",.30,.06), ("rear",.225,-1.02)):
            parent = root
            if axle == "rear":
                parent = _joint(root, "pivot_wheel_rear_%s_steer" % name,
                                (side*.45,y,z), "rotation", (0,1,0),
                                -math.radians(35), math.radians(35))
            spin = _joint(root, "pivot_wheel_%s_%s_spin" % (axle,name),
                          (side*.45,y,z), "rotation", (1,0,0),
                          -1e9, 1e9, parent=parent)
            spin["radius_m"] = .30 if axle == "front" else .225
            _reparent(_children(root, "%s_%s_" % (name,axle)), spin)

    steering = _joint(root, "pivot_steering_wheel", (0,1.13,-.27),
                      "rotation", (0,1,0), -math.tau, math.tau,
                      normal=(0,.8,-.6))
    _reparent(_children(root, "steering_wheel_"), steering)
    carriage = _joint(root, "pivot_carriage", (0,.24,.475),
                      "translation", (0,1,0), 0, 1.0)
    for side in (-1,1):
        blade = _children(root, "tapered_flat_fork_%d" % side)[0]
        _fork_blade(blade, side)
        heel = _children(root, "fork_heel_%d" % side)[0]
        # Retain its upper connection while bringing the heel down to the blade.
        heel.location = xyz((side*.225,.2525,.53))
        heel.dimensions = (.115,.068,.475)
        bpy.context.view_layer.update()
    carriage_parts = []
    for prefix in ("fork_carriage_", "load_backrest_", "fork_heel_", "tapered_flat_fork_"):
        carriage_parts += _children(root, prefix)
    _reparent(carriage_parts, carriage)
    _node(root, "anchor_pallet", (0,-.071,1.08), parent=carriage)
    _node(root, "anchor_cargo", (0,.069,1.08), parent=carriage)
    _node(root, "anchor_buffer_pallet", (0,-.008,1.08), parent=carriage)
    _node(root, "anchor_fork_left_tip", (-.225,.025,1.30), parent=carriage)
    _node(root, "anchor_fork_right_tip", (.225,.025,1.30), parent=carriage)
    _node(root, "anchor_driver_seat", (0,.99,-.65))
    _node(root, "anchor_driver_footwell", (0,.54,-.20))
    _node(root, "anchor_hand_left", (-.11,1.13,-.27))
    _node(root, "anchor_hand_right", (.11,1.13,-.27))
    return root


def _passive_grid(root, name, xs, zs, cells, surface_y, mat):
    used = sorted({(row,col) for cell_row,cell_col in cells
                   for row,col in ((cell_row,cell_col),(cell_row,cell_col+1),
                                   (cell_row+1,cell_col+1),(cell_row+1,cell_col))})
    lookup = {pair:index for index,pair in enumerate(used)}
    vertices = [(xs[col],surface_y(zs[row])-offset,zs[row])
                for offset in (.06,.018) for row,col in used]
    count = len(used)
    faces, edges = [], {}
    for row,col in cells:
        ring = [lookup[pair] for pair in ((row,col),(row,col+1),(row+1,col+1),(row+1,col))]
        faces += [tuple(reversed(ring)),tuple(index+count for index in ring)]
        for a,b in zip(ring,ring[1:]+ring[:1]):
            key = tuple(sorted((a,b)))
            edges[key] = None if key in edges else (a,b)
    for edge in edges.values():
        if edge:
            a,b = edge
            faces.append((a,b,b+count,a+count))
    mesh = bpy.data.meshes.new(name+"_mesh")
    mesh.from_pydata([tuple(xyz(point)) for point in vertices],[],faces)
    mesh.materials.append(mat)
    import bmesh
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj); obj.parent = root
    return obj


def _raw_part(obj):
    for modifier in list(obj.modifiers):
        obj.modifiers.remove(modifier)
    return obj


def _packing_transfers(root):
    steel = bpy.data.materials["Steel_Charcoal"]
    deck = bpy.data.materials["Equipment_Charcoal"]
    hardware = bpy.data.materials["Hardware_Grey"]
    input_y = lambda z: .85+.05*min(1,max(0,(z-.5)/.75))
    output_y = lambda z: .85+.05*min(1,max(0,(-.5-z)/.7))
    _passive_grid(root,"passive_input_L_deck",[-1.02,-.42,.3],[.5,1,1.25,1.5],
                  [(0,0),(1,0),(1,1),(2,0),(2,1)],input_y,deck)
    _passive_grid(root,"passive_output_L_deck",[-.3,.3,.42,1.02],[-1.5,-1.45,-1.2,-.95,-.5],
                  [(0,0),(1,0),(1,1),(1,2),(2,0),(2,1),(2,2),(3,2)],output_y,deck)
    for name,x,zs,cross_z,cross_xs,height in (
        ("input",-.72,(.56,.79,1.02,1.25),1.25,(-.15,-.45),input_y),
        ("output",.72,(-.56,-.78,-1,-1.22),-1.2,(.15,.45),output_y)):
        for i,z in enumerate(zs):
            _raw_part(cylinder("passive_%s_roller_%d" % (name,i),(x,height(z)-.018,z),
                               .018,.54,hardware,root,axis="X",vertices=8))
        for i,cross_x in enumerate(cross_xs):
            _raw_part(cylinder("passive_%s_cross_roller_%d" % (name,i),
                               (cross_x,.882,cross_z),.018,.46,hardware,root,axis="Z",vertices=8))
        for i,z in enumerate((cross_z,.65 if name=="input" else -.65)):
            leg_height = height(z)-.06-.025
            box("passive_%s_leg_%d" % (name,i),(x,.025+leg_height/2,z),
                (.045,leg_height,.045),steel,root,bevel=0)
            box("passive_%s_foot_%d" % (name,i),(x,.0125,z),(.10,.025,.10),steel,root,bevel=0)
        tip_x = .04 if name=="input" else -.04
        _raw_part(beam("passive_%s_cantilever_brace" % name,(x,.38,cross_z),
                       (tip_x,.85,cross_z),.035,steel,root))
        _raw_part(cylinder("passive_%s_hex_bolt" % name,(x+.025,.77,cross_z),
                           .011,.004,hardware,root,axis="X",vertices=6))
    for name,pos in (
        ("input_branch",(0,.9,1.5)),("input_cross",(0,.9,1.25)),
        ("input_turn",(-.72,.9,1.25)),("input_table",(-.72,.85,.5)),
        ("output_table",(.72,.85,-.5)),("output_turn",(.72,.9,-1.2)),
        ("output_cross",(0,.9,-1.2)),("output_outfeed",(0,.9,-1.5))):
        _node(root,"anchor_transfer_"+name,pos,"passive_transfer_surface")
    root["passive_transfer_supports"] = True
    root["passive_transfer_note"] = "Passive roller counters only; no motors, cells or transport timing. Surface paths are transfer anchors."
    root["dimensions_m"] = [2.2,1.42,3.0]


def _component_bounds(parts):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in parts:
        evaluated = obj.evaluated_get(depsgraph)
        for vertex in evaluated.data.vertices:
            point = evaluated.matrix_world@vertex.co
            points.append((point.x,point.z,-point.y))
    return {"min":[min(point[axis] for point in points) for axis in range(3)],
            "max":[max(point[axis] for point in points) for axis in range(3)]}


def _arrange_packing_equipment(root):
    printer = _children(root,"printer_")+_children(root,"emerging_label")+_children(root,"label_on_tray")
    old = xyz((.805,0,-.245)); target = xyz((-.805,0,-.245))
    transform = Matrix.Translation(target)@Matrix.Rotation(math.pi/2,4,"Z")@Matrix.Translation(-old)
    bpy.context.view_layer.update()
    for obj in printer:
        obj.matrix_world = transform@obj.matrix_world
    # The original monitor would occupy the new printer location. Its rear-centre
    # position clears both flow lanes, the scanner and the carton flap sweep.
    monitor = _children(root,"monitor_")
    shift = Matrix.Translation(xyz((.72,0,-.14)))
    for obj in monitor:
        obj.matrix_world = shift@obj.matrix_world
    bounds = {"printer":_component_bounds(printer),"monitor":_component_bounds(monitor),
              "scanner":_component_bounds(_children(root,"scanner_"))}
    def overlaps(a,b):
        return all(a["min"][axis]<b["max"][axis]-1e-6 and b["min"][axis]<a["max"][axis]-1e-6
                   for axis in range(3))
    if overlaps(bounds["printer"],bounds["monitor"]) or overlaps(bounds["printer"],bounds["scanner"]):
        raise RuntimeError("Packing equipment intersects after lane clearance placement")
    if bounds["printer"]["max"][2]>.02:
        raise RuntimeError("Printer/tray enters the incoming tote footprint")
    if max(item["max"][0] for item in bounds.values())>.47:
        raise RuntimeError("Packing equipment enters the output parcel lane")
    root["equipment_bounds_runtime_json"] = json.dumps(bounds)
    root["printer_to_scanner_clearance_x_m"] = bounds["scanner"]["min"][0]-bounds["printer"]["max"][0]
    root["input_tote_to_printer_clearance_z_m"] = .02-bounds["printer"]["max"][2]
    print("PACKING_EQUIPMENT_BOUNDS "+json.dumps(bounds))


def packing():
    root = source_packing.build()
    _metadata(root, "packing-station", "assets/references/packing-station-reference.png",
              "floor_centre")
    root["preserve_articulation"] = True
    # The reviewed v1 bundle floated 4.5mm above its shelf, with gaps between
    # its flat cartons. In v2 the six folded cartons and band actually touch.
    bundle = sorted(_children(root,"flat_carton_bundle"), key=lambda obj: obj.location.z)
    for index,obj in enumerate(bundle):
        obj.location.z = .25125+index*.0125
        obj.dimensions.z = .0125
    for obj in _children(root,"bundle_strap_top"):
        obj.location.z = .324
    for prefix in ("bundle_strap_front","bundle_strap_rear"):
        for obj in _children(root,prefix):
            obj.location.z = .2825
            obj.dimensions.z = .075
    _arrange_packing_equipment(root)
    scanner = _joint(root, "pivot_scanner", (-.315,.894,-.27),
                     "rotation", (1,0,0), -math.pi/2, math.pi/2)
    scanner_parts = []
    for prefix in ("scanner_handle", "scanner_yellow_grip", "scanner_head", "scanner_lens"):
        scanner_parts += _children(root, prefix)
    _reparent(scanner_parts, scanner)
    _node(root, "anchor_scanner_grip", (-.315,.982,-.256), parent=scanner)
    _node(root, "anchor_scanner_lens", (-.315,1.081,-.1765), parent=scanner)
    carton = _node(root, "pivot_packing_carton", (.23,.85,.005), "cargo_fixture")
    carton["runtime_default_visible"] = False
    carton["visibility_rule"] = "show only while representing the current authoritative packing cargo"
    _reparent(_children(root, "carton_"), carton)
    for side, label in ((-1,"rear"), (1,"front")):
        hinge = _joint(root, "pivot_carton_flap_%s" % label,
                       (.23,1.15,.005+side*.215), "rotation", (1,0,0),
                       min(0,-side*math.radians(145)), max(0,-side*math.radians(145)),
                       parent=carton)
        hinge["closed_delta_radians"] = -side*math.radians(145)
        candidates = _children(root, "carton_end_flap")
        target = min(candidates, key=lambda obj: abs(-obj.matrix_world.translation.y-(.005+side*(.215+math.cos(math.radians(35))*.135/2))))
        _reparent([target], hinge)
    for side, label in ((-1,"left"), (1,"right")):
        hinge = _joint(root, "pivot_carton_flap_%s" % label,
                       (.23+side*.24,1.15,.005), "rotation", (0,0,1),
                       min(0,side*math.radians(145)), max(0,side*math.radians(145)),
                       parent=carton)
        hinge["closed_delta_radians"] = side*math.radians(145)
        candidates = _children(root, "carton_side_flap")
        target = min(candidates, key=lambda obj: abs(obj.matrix_world.translation.x-(.23+side*(.24+math.cos(math.radians(35))*.135/2))))
        _reparent([target], hinge)
    _node(root, "anchor_input_tote", (-.72,.85,.23))
    _node(root, "anchor_output_parcel", (.72,.85,.29))
    _node(root, "anchor_work_parcel", (.23,.85,.005))
    _node(root, "anchor_worker", (.05,0,.85))
    _node(root, "anchor_hand_left", (-.03,1.05,.22))
    _node(root, "anchor_hand_right", (.43,1.05,.22))
    label_output = _node(root, "anchor_label_output", (-.52,.89,-.245))
    label_output["normal_runtime"] = [1,0,0]
    _packing_transfers(root)
    return root


def buffer_pallet():
    root = source_pallet.build()
    _metadata(root, "buffer-pallet", "assets/references/buffer-pallet.png", "floor_centre")
    root["pocket_clear_height_m"] = .053
    root["pocket_width_m"] = .45
    root["compatible_fork_centres_x_m"] = [-.225,.225]
    _node(root, "anchor_pallet_base", (0,0,0))
    _node(root, "anchor_cargo", (0,.075,0))
    for side, label in ((-1,"left"), (1,"right")):
        for z, end in ((-.5,"rear"), (.5,"front")):
            entry = _node(root, "anchor_fork_entry_%s_%s" % (end,label), (side*.225,.0265,z))
            entry["approach_runtime"] = [0,0,1 if z < 0 else -1]
            entry["clear_height_m"] = .053
            entry["clear_width_m"] = .45
    return root


def pallet():
    root = group("pallet_root")
    _metadata(root, "pallet", "assets/references/buffer-pallet.png", "floor_centre")
    root["role"] = "empty_shipping_pallet"
    root["size_m"] = [1.4,.14,1.0]
    root["top_height_m"] = .14
    root["deck_underside_m"] = .116
    root["contains_cargo"] = False
    root["fork_direction_runtime"] = [0,0,1]
    root["fork_contact_lift_m"] = .071
    root["reference_adaptation"] = "Same warm slatted wood language; v2 has a full 140mm pallet with nine blocks and three bottom runners."
    wood = material("buffer_warm_tan_wood", "#B88A56", .88)
    alternate = material("buffer_alternate_wood", "#C89C64", .88)
    endgrain = material("buffer_runner_endgrain", "#A97C47", .90)
    for i,x in enumerate((-.57,0,.57)):
        box("pallet_bottom_runner_%d" % i, (x,.011,0), (.13,.022,1.0),
            endgrain, root, bevel=.003)
        for j,z in enumerate((-.40,0,.40)):
            box("pallet_block_%d_%d" % (i,j), (x,.061,z), (.13,.078,.16),
                wood, root, bevel=.004)
        box("pallet_upper_stringer_%d" % i, (x,.108,0), (.13,.016,1.0),
            endgrain, root, bevel=.002)
    for i in range(8):
        box("pallet_deck_slat_%d" % i, (0,.128,-.434+i*.124), (1.4,.024,.112),
            wood if i%2 else alternate, root, bevel=.003)
    _node(root,"anchor_pallet_base",(0,0,0))
    _node(root,"anchor_cargo",(0,.14,0))
    for side,label in ((-1,"left"),(1,"right")):
        for z,end in ((-.5,"rear"),(.5,"front")):
            entry = _node(root,"anchor_fork_entry_%s_%s" % (end,label),
                          (side*.225,.058,z))
            entry["approach_runtime"] = [0,0,1 if z<0 else -1]
            entry["clear_height_m"] = .116
            entry["clear_width_m"] = .44
    return root


def crate():
    root = source_crate.build()
    _metadata(root, "crate", "assets/references/crate-reference.png", "geometric_center")
    root["cargo_kind"] = "storage_carton"
    _node(root, "anchor_cargo", (0,0,0))
    _node(root, "anchor_bottom", (0,-.225,0))
    _node(root, "anchor_grip_left", (-.20,-.19,0))
    _node(root, "anchor_grip_right", (.20,-.19,0))
    _node(root, "cargo_contents_root", (0,0,0), "contents_attachment")
    return root


def build(asset_id):
    return {"forklift":forklift, "packing-station":packing,
            "buffer-pallet":buffer_pallet, "pallet":pallet, "crate":crate}[asset_id]()


def _batch_by_parent(root):
    meshes = [obj for obj in root.children_recursive if obj.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.convert(target="MESH")
    batches = {}
    for obj in root.children_recursive:
        if obj.type == "MESH":
            key = (obj.parent,tuple(mat.name for mat in obj.data.materials))
            batches.setdefault(key,[]).append(obj)
    for index, ((parent,_),parts) in enumerate(batches.items()):
        bpy.ops.object.select_all(action="DESELECT")
        for obj in parts:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        if len(parts) > 1:
            bpy.ops.object.join()
        bpy.context.object.name = "%s__material_%02d" % (parent.name,index)
    bpy.context.view_layer.update()


def _manifest(asset_id, root):
    bpy.context.view_layer.update()
    nodes = []
    for obj in root.children_recursive:
        if obj.type != "EMPTY":
            continue
        local = AXIS_CONVERSION @ obj.matrix_local @ AXIS_CONVERSION.inverted()
        world = AXIS_CONVERSION @ obj.matrix_world @ AXIS_CONVERSION.inverted()
        position,rotation,scale = local.decompose()
        nodes.append({"name":obj.name, "parent":obj.parent.name if obj.parent else None,
                      "position_local_runtime":list(position),
                      "rotation_local_xyzw":[rotation.x,rotation.y,rotation.z,rotation.w],
                      "scale_local":list(scale), "position_asset_runtime":list(world.translation),
                      "properties":{key:obj[key].to_list() if hasattr(obj[key],"to_list") else obj[key]
                                    for key in obj.keys()}})
    report = {"asset_id":asset_id, "layout_version":"qoima-72x48-v2",
              "root_name":root.name, "units":"metres_radians",
              "coordinate_system":"right_handed_Y_up", "forward_axis":"+Z",
              "reference":root["reference"], "origin":root["origin"],
              "root_properties":{key:root[key].to_list() if hasattr(root[key],"to_list") else root[key]
                                 for key in root.keys()},
              "animation":"Apply deltas relative to each stored rest transform; never overwrite the tilted steering rest quaternion.",
              "nodes":nodes}
    output = ROOT/"assets"/"v2"/"blender"/(asset_id+".anchors.json")
    output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")


def export(asset_id):
    reset()
    root = build(asset_id)
    editable_bytes = None
    source_path = ROOT/"assets"/"v2"/"blender"/(asset_id+".blend")
    if root.get("preserve_articulation",False):
        source_path.parent.mkdir(parents=True,exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(source_path))
        editable_bytes = source_path.read_bytes()
        _batch_by_parent(root)
    finish(asset_id,root)
    # finish saves before export. Restore the individually editable source scene
    # while retaining the small per-articulation/material runtime GLB batches.
    if editable_bytes is not None:
        source_path.write_bytes(editable_bytes)
    _manifest(asset_id,root)


if __name__ == "__main__":
    selected = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else list(ASSET_IDS)
    for asset_id in selected or ASSET_IDS:
        if asset_id not in ASSET_IDS:
            raise ValueError("Unknown equipment asset: "+asset_id)
        export(asset_id)
