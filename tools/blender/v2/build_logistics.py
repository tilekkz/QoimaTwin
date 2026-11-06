"""Reference-led v2 logistics modules; run only through task background Blender.

CLI: blender --background --factory-startup --python build_logistics.py -- [asset-id ...]
No arguments export all seven independent assets. All dimensions use runtime XYZ.
"""
from pathlib import Path
import json
import math
import sys

import bpy
import bmesh
from v2_common import reset, material, group, box, cylinder, beam, xyz, finish

ASSET_IDS = ("conveyor-high", "conveyor-low", "conveyor-corner",
             "conveyor-diverter", "order-tote", "tote-low", "sealed-parcel")


def _mesh(name, vertices, faces, mat, parent, bevel=0):
    data = bpy.data.meshes.new(name + "_mesh")
    data.from_pydata([tuple(xyz(v)) for v in vertices], [], faces)
    data.materials.append(mat)
    data.update()
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(data)
    bm.free()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    if bevel:
        modifier = obj.modifiers.new("Small moulded edge", "BEVEL")
        modifier.width = bevel
        modifier.segments = 1
        modifier.limit_method = "ANGLE"
        modifier.harden_normals = True
        obj.modifiers.new("Face normals", "WEIGHTED_NORMAL")
    return obj


def _raw_cylinder(name, loc, radius, depth, mat, parent, axis="Y", vertices=8):
    obj = cylinder(name, loc, radius, depth, mat, parent, axis=axis, vertices=vertices)
    for modifier in list(obj.modifiers):
        obj.modifiers.remove(modifier)
    return obj


def _materials():
    return {
        "steel": material("v2_conveyor_charcoal_steel", "#34434A", .72, .25),
        "metal": material("v2_conveyor_metal_fasteners", "#7A8587", .63, .40),
        "yellow": material("v2_conveyor_safety_yellow", "#E8B52E", .73),
        "belt": material("v2_conveyor_teal_belt", "#376E6C", .85),
        "teal": material("v2_order_tote_teal", "#397F7B", .78),
        "rim": material("v2_order_tote_rim", "#4C928A", .76),
        "label": material("v2_blank_cargo_label", "#E3DCCB", .86),
        "card": material("v2_parcel_cardboard", "#BC915C", .88),
        "flap": material("v2_parcel_flap", "#C79D69", .88),
        "tape": material("v2_parcel_ochre_tape", "#B88737", .75),
        "fold": material("v2_parcel_fold_seam", "#866343", .92),
    }


def _root(asset_id, role, reference):
    root = group(asset_id.replace("-", "_") + "_root")
    root["asset_id"] = asset_id
    root["role"] = role
    root["forward_axis"] = "+Z"
    root["reference"] = "assets/references/v2/" + reference + ".png"
    return root


def _port(root, name, pos, direction):
    obj = group("port_" + name)
    obj.parent = root
    obj.location = xyz(pos)
    obj.empty_display_type = "ARROWS"
    obj.empty_display_size = .08
    obj["role"] = "conveyor_port"
    obj["port_name"] = name
    obj["direction_runtime"] = list(direction)
    return obj


def _cargo_node(root, name, pos, role="cargo_attachment"):
    obj = group(name)
    obj.parent = root
    obj.location = xyz(pos)
    obj["role"] = role
    return obj


def _ports(root, branch=False, corner=False):
    _port(root, "input", (0, .9, -.5), (0, 0, 1))
    _port(root, "output", (.5, .9, 0) if corner else (0, .9, .5),
          (1, 0, 0) if corner else (0, 0, 1))
    if branch:
        _port(root, "branch", (.5, .9, 0), (1, 0, 0))
    root["belt_surface_y"] = .9
    root["cell_length_m"] = 1.0


def _legs(root, mats, low=False, positions=None):
    positions = positions or [(-.265, -.37), (.265, -.37), (-.265, .37), (.265, .37)]
    for i, (x, z) in enumerate(positions):
        box("leg_%d" % i, (x, .425, z), (.042, .85, .042),
            mats["steel"], root, bevel=0 if low else .004)
        if not low:
            box("bolted_foot_%d" % i, (x, .014, z), (.09, .028, .09),
                mats["steel"], root, bevel=0)
    if not low:
        for i in range(0, len(positions), 2):
            first, last = positions[i:i+2]
            beam("lower_stabilizer_%d" % i, (first[0], .27, first[1]),
                 (last[0], .27, last[1]), .032, mats["steel"], root)


def _motor(root, mats, loc=(0, .725, -.18)):
    x, y, z = loc
    box("underslung_motor_mount", (x, y+.09, z), (.30, .04, .14),
        mats["steel"], root, bevel=0)
    _raw_cylinder("drive_motor", (x-.055, y, z), .060, .17,
                  mats["steel"], root, axis="X", vertices=8)
    box("reduction_gearbox", (x+.075, y, z), (.095, .13, .13),
        mats["metal"], root, bevel=.009)
    _raw_cylinder("gearbox_round_cover", (x+.126, y, z), .042, .008,
                  mats["steel"], root, axis="X", vertices=8)


def conveyor(low=False):
    mats = _materials()
    asset_id = "conveyor-low" if low else "conveyor-high"
    root = _root(asset_id, "conveyor_straight_lod" if low else "conveyor_straight", "conveyor")
    root["lod"] = "low" if low else "high"
    root["nominal_size_m"] = [.68, .95, 1.0]
    _ports(root)
    if low:
        # Eight boxes = 96 triangles. Belt top and guide silhouette stay canonical.
        box("belt_and_deck_proxy", (0, .858, 0), (.58, .084, 1), mats["belt"], root, bevel=0)
        for side in (-1, 1):
            box("yellow_side_guide_%d" % side, (side*.315, .915, 0),
                (.05, .07, 1), mats["yellow"], root, bevel=0)
        _legs(root, mats, low=True)
        box("underframe_cross_proxy", (0, .275, -.37), (.56, .035, .035),
            mats["steel"], root, bevel=0)
        return root
    box("continuous_teal_belt", (0, .866, 0), (.575, .068, 1),
        mats["belt"], root, bevel=.008)
    for side in (-1, 1):
        box("lower_channel_%d" % side, (side*.306, .8365, 0), (.068, .121, 1),
            mats["steel"], root, bevel=.006)
        box("yellow_side_guard_%d" % side, (side*.315, .923, 0), (.05, .054, 1),
            mats["yellow"], root, bevel=.006)
        for z in (-.41, .41):
            _raw_cylinder("rail_fastener_%d_%.2f" % (side,z),
                          (side*.339, .839, z), .012, .002,
                          mats["metal"], root, axis="X", vertices=6)
    for z in (-.46, .46):
        _raw_cylinder("dimensional_end_roller_%.2f" % z, (0, .862, z),
                      .036, .583, mats["belt"], root, axis="X", vertices=10)
    _legs(root, mats)
    _motor(root, mats)
    return root


def corner():
    mats = _materials()
    root = _root("conveyor-corner", "conveyor_corner", "conveyor")
    root["family_variant"] = "orthogonal_L_transfer"
    root["path_runtime"] = [0,.9,-.5, 0,.9,0, .5,.9,0]
    root["path_rule"] = "Two orthogonal half-metre legs; no route smoothing or timing change."
    _ports(root, corner=True)
    # Three shared, non-overlapping deck cells form an L. The central face is
    # the steel transfer plate; its top is exactly coplanar with adjacent belts.
    width = .2875
    grid = [(x,z) for z in (-.5,-width,width) for x in (-width,width,.5)]
    vertices = [(x,y,z) for y in (.834,.9) for x,z in grid]
    faces = []
    for cell in ((0,1,4,3),(3,4,7,6),(4,5,8,7)):
        faces += [tuple(reversed(cell)),tuple(i+9 for i in cell)]
    boundary = [0,1,4,5,8,7,6,3]
    for i,j in zip(boundary,boundary[1:]+boundary[:1]):
        faces.append((i,j,j+9,i+9))
    deck = _mesh("continuous_orthogonal_L_transfer_deck", vertices, faces,
                 mats["belt"], root)
    deck.data.materials.append(mats["metal"])
    deck.data.polygons[3].material_index = 1
    for name,axis,position,length in (
        ("outer_inlet","Z",(-.315,0,-.08),.84),
        ("outer_outlet","X",(.08,0,.315),.84),
        ("inner_inlet","Z",(.315,0,-.395),.21),
        ("inner_outlet","X",(.395,0,-.315),.21)):
        x,_,z = position
        guide_size = (.05,.054,length) if axis == "Z" else (length,.054,.05)
        frame_size = (.068,.121,length) if axis == "Z" else (length,.121,.068)
        frame_x = math.copysign(.306,x) if axis == "Z" else x
        frame_z = math.copysign(.306,z) if axis == "X" else z
        box(name+"_steel_channel",(frame_x,.8365,frame_z),frame_size,
            mats["steel"],root,bevel=.005)
        box(name+"_yellow_guard",(x,.923,z),guide_size,
            mats["yellow"],root,bevel=.005)
    _legs(root,mats,positions=[(-.24,-.39),(.24,-.39),(-.24,.235),(.39,.235)])
    _motor(root,mats,(.08,.725,-.10))
    return root


def diverter():
    mats = _materials()
    root = _root("conveyor-diverter", "conveyor_diverter", "conveyor")
    root["family_variant"] = "three_way_T"
    _ports(root, branch=True)
    outline = [(-.2875,-.5), (.2875,-.5), (.2875,-.2875),
               (.5,-.2875), (.5,.2875), (.2875,.2875),
               (.2875,.5), (-.2875,.5)]
    vertices = [(x,y,z) for y in (.834,.9) for x,z in outline]
    faces = [tuple(range(7,-1,-1)), tuple(range(8,16))]
    faces += [(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)]
    _mesh("single_continuous_T_belt", vertices, faces, mats["belt"], root, .004)
    box("left_continuous_channel", (-.306, .8365, 0), (.068, .121, 1),
        mats["steel"], root, bevel=.006)
    box("left_continuous_yellow_guide", (-.315, .923, 0), (.05, .054, 1),
        mats["yellow"], root, bevel=.006)
    for side in (-1, 1):
        box("right_split_channel_%d" % side, (.306, .8365, side*.414),
            (.068, .121, .172), mats["steel"], root, bevel=.005)
        box("right_split_yellow_guide_%d" % side, (.315, .923, side*.414),
            (.05, .054, .172), mats["yellow"], root, bevel=.005)
        box("branch_edge_channel_%d" % side, (.407, .8365, side*.306),
            (.186, .121, .068), mats["steel"], root, bevel=.005)
        box("branch_yellow_guide_%d" % side, (.407, .923, side*.315),
            (.186, .054, .05), mats["yellow"], root, bevel=.005)
    _legs(root, mats)
    _motor(root, mats)
    # The union deck has one top face: no coplanar belt/transfer-plate overlap.
    return root


def _box_faces():
    return [(0,1,2,3), (4,7,6,5), (0,4,5,1),
            (1,5,6,2), (2,6,7,3), (3,7,4,0)]


def _front_wall(root, name, side, mats):
    vertices = []
    for inner in (False, True):
        for y, half_x, half_z in ((.025, .228, .178), (.278, .253, .203)):
            z = side*(half_z-(.018 if inner else 0))
            vertices += [(-half_x, y, z), (half_x, y, z)]
    return _mesh(name, vertices,
                 [(0,1,3,2), (4,6,7,5), (0,4,5,1),
                  (2,3,7,6), (0,2,6,4), (1,5,7,3)],
                 mats["teal"], root, .002)


def _end_wall(root, side, mats):
    # One welded wall mesh with a real hand opening. Shared coplanar grid edges
    # create no artificial seams between the lower panel and handle jambs.
    vertices = []
    for inner in (False, True):
        for y in (.025, .205, .25, .278):
            amount = (y-.025)/.253
            half_x = .228+.025*amount
            half_z = .178+.025*amount
            x = side*(half_x-(.018 if inner else 0))
            vertices += [(x,y,z) for z in (-half_z,-.075,.075,half_z)]
    faces = []
    for row in range(3):
        for col in range(3):
            if row == 1 and col == 1:
                continue
            i = row*4+col
            faces += [(i,i+1,i+5,i+4), (i+16,i+20,i+21,i+17)]
    for loop in ([0,1,2,3,7,11,15,14,13,12,8,4], [5,6,10,9]):
        for i,j in zip(loop,loop[1:]+loop[:1]):
            faces.append((i,i+16,j+16,j))
    return _mesh("unified_handhold_end_%d" % side, vertices, faces,
                 mats["teal"], root, .002)


def _tote_rim(root, mat):
    def loop(half_x, half_z, chamfer):
        return [(-half_x+chamfer,-half_z), (half_x-chamfer,-half_z),
                (half_x,-half_z+chamfer), (half_x,half_z-chamfer),
                (half_x-chamfer,half_z), (-half_x+chamfer,half_z),
                (-half_x,half_z-chamfer), (-half_x,-half_z+chamfer)]
    vertices = []
    for y, shape in ((.272,loop(.26,.21,.009)), (.30,loop(.26,.21,.009)),
                     (.272,loop(.234,.184,.007)), (.30,loop(.234,.184,.007))):
        vertices += [(x,y,z) for x,z in shape]
    faces = []
    for i in range(8):
        j = (i+1)%8
        faces += [(i,j,j+8,i+8), (i+16,i+24,j+24,j+16),
                  (i+8,j+8,j+24,i+24), (i,j,j+16,i+16)]
    return _mesh("continuous_thick_chamfered_rim", vertices, faces, mat, root)


def tote(low=False):
    mats = _materials()
    asset_id = "tote-low" if low else "order-tote"
    root = _root(asset_id, "order_tote", "order-tote")
    root["lod"] = "low" if low else "high"
    root["size_m"] = [.52, .30, .42]
    root["cargo_kind"] = "tote"
    root["hollow"] = True
    root["origin"] = "bottom_centre"
    _cargo_node(root, "anchor_cargo", (0,0,0))
    _cargo_node(root, "anchor_contents", (0,.033,0), "contents_attachment")
    _cargo_node(root, "anchor_grip_left", (-.25,.26,0), "hand_contact")
    _cargo_node(root, "anchor_grip_right", (.25,.26,0), "hand_contact")
    if low:
        vertices = []
        for y, half_x, half_z in ((0,.228,.178), (.30,.26,.21),
                                  (.025,.210,.160), (.30,.242,.192)):
            vertices += [(-half_x,y,-half_z), (half_x,y,-half_z),
                         (half_x,y,half_z), (-half_x,y,half_z)]
        faces = [(0,3,2,1), (8,9,10,11)]
        for i in range(4):
            j = (i+1)%4
            faces += [(i,j,j+4,i+4), (i+8,i+12,j+12,j+8),
                      (i+4,j+4,j+12,i+12)]
        _mesh("hollow_tapered_tote_proxy", vertices, faces, mats["teal"], root)
        return root
    box("tote_floor", (0, .021, 0), (.456, .024, .356),
        mats["teal"], root, bevel=.004)
    _tote_rim(root, mats["rim"])
    for side in (-1, 1):
        _front_wall(root, "long_thick_wall_%d" % side, side, mats)
        _end_wall(root, side, mats)
        for i, y in enumerate((.095,.207)):
            z = side*(.178+.025*(y-.025)/.253+.004)
            box("front_reinforcement_%d_%d" % (side,i), (0,y,z),
                (.426,.012,.012), mats["rim"], root, bevel=.003)
    for sx in (-1,1):
        for sz in (-1,1):
            beam("moulded_corner_rib_%d_%d" % (sx,sz),
                 (sx*.228,.035,sz*.178), (sx*.251,.277,sz*.201),
                 .012, mats["rim"], root)
            box("moulded_foot_%d_%d" % (sx,sz), (sx*.18,.005,sz*.13),
                (.05,.010,.04), mats["teal"], root, bevel=0)
    label_z = .178+.025*(.151-.025)/.253+.001
    label = box("blank_recessed_tote_label", (0,.151,label_z), (.12,.052,.003),
                mats["label"], root, bevel=.003)
    label.rotation_euler.x = math.atan(.025/.253)
    return root


def parcel():
    mats = _materials()
    root = _root("sealed-parcel", "sealed_parcel", "sealed-parcel")
    root["cargo_kind"] = "parcel"
    root["size_m"] = [.50,.32,.38]
    root["origin"] = "bottom_centre"
    root["sealed"] = True
    _cargo_node(root, "anchor_cargo", (0,0,0))
    _cargo_node(root, "anchor_grip_left", (-.20,.04,0), "hand_contact")
    _cargo_node(root, "anchor_grip_right", (.20,.04,0), "hand_contact")
    box("closed_corrugated_body", (0,.159,0), (.50,.318,.378),
        mats["card"], root, bevel=.007)
    for side in (-1,1):
        box("top_flap_%d" % side, (side*.125,.31825,0), (.248,.0005,.376),
            mats["flap"], root, bevel=0)
        box("front_rear_tape_wrap_%d" % side, (0,.16,side*.1895),
            (.052,.32,.001), mats["tape"], root, bevel=0)
        box("top_end_sealing_strip_%d" % side, (side*.231,.319,0),
            (.020,.002,.376), mats["tape"], root, bevel=0)
        for z in (-.17,.17):
            box("folded_corner_vertical_%d_%.2f" % (side,z),
                (side*.246,.159,z), (.003,.288,.003), mats["fold"], root, bevel=0)
    box("centre_top_sealing_tape", (0,.319,0), (.052,.002,.38),
        mats["tape"], root, bevel=0)
    box("blank_shipping_label", (.123,.214,.1895), (.12,.065,.001),
        mats["label"], root, bevel=.0002)
    # Small crease marks meet the body's bevels, representing folded carton corners.
    for sx in (-1,1):
        for sz in (-1,1):
            for top in (False,True):
                y0, y1 = ((.008,.024) if not top else (.294,.310))
                beam("diagonal_fold_%d_%d_%d" % (sx,sz,top),
                     (sx*.246,y0,sz*.180), (sx*.232,y1,sz*.187),
                     .002, mats["fold"], root)
    return root


def build(asset_id):
    builders = {"conveyor-high": lambda: conveyor(False),
                "conveyor-low": lambda: conveyor(True),
                "conveyor-corner": corner, "conveyor-diverter": diverter,
                "order-tote": lambda: tote(False), "tote-low": lambda: tote(True),
                "sealed-parcel": parcel}
    return builders[asset_id]()


def write_anchor_manifest(asset_id, root):
    from mathutils import Matrix
    conversion = Matrix(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)))
    bpy.context.view_layer.update()
    nodes = []
    for obj in root.children_recursive:
        if obj.type != "EMPTY":
            continue
        local = conversion @ obj.matrix_local @ conversion.inverted()
        nodes.append({"name":obj.name, "parent":obj.parent.name,
                      "position_local_runtime":list(local.translation),
                      "properties":{key:obj[key].to_list() if hasattr(obj[key],"to_list") else obj[key]
                                    for key in obj.keys()}})
    report = {"asset_id":asset_id,"layout_version":"qoima-72x48-v2",
              "coordinate_system":"right_handed_Y_up_metres","root_name":root.name,
              "reference":root["reference"],
              "root_properties":{key:root[key].to_list() if hasattr(root[key],"to_list") else root[key]
                                 for key in root.keys()},"nodes":nodes}
    output = Path(__file__).resolve().parents[3]/"assets"/"v2"/"blender"/(asset_id+".anchors.json")
    output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    selected = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else list(ASSET_IDS)
    if not selected:
        selected = list(ASSET_IDS)
    for asset_id in selected:
        if asset_id not in ASSET_IDS:
            raise ValueError("Unknown logistics asset: " + asset_id)
        reset()
        root = build(asset_id)
        finish(asset_id, root)
        write_anchor_manifest(asset_id, root)
