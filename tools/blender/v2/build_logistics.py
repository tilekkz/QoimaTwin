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


def _mesh(name, vertices, faces, mat, parent, bevel=0, upward=False):
    data = bpy.data.meshes.new(name + "_mesh")
    data.from_pydata([tuple(xyz(v)) for v in vertices], [], faces)
    data.materials.append(mat)
    data.update()
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if upward:
        # Recalc cannot infer an outside for disconnected single-sided strips.
        for face in bm.faces:
            if face.normal.z < 0:
                face.normal_flip()
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
        "yellow": material("v2_conveyor_safety_yellow", "#CBA548", .8),
        "belt": material("v2_conveyor_rubber_belt_surface", "#2D4A4D", .88),
        "tread": material("v2_conveyor_belt_tread_bands", "#486766", .87),
        "teal": material("v2_order_tote_teal", "#3C7977", .82),
        "rim": material("v2_order_tote_moulded_rim", "#568C86", .8),
        "label": material("v2_blank_cargo_label", "#E3DCCB", .86),
        "card": material("v2_parcel_cardboard", "#B99566", .92),
        "flap": material("v2_parcel_folded_flap", "#C3A477", .92),
        "tape": material("v2_parcel_kraft_tape", "#C3A16E", .84),
        "fold": material("v2_parcel_fold_seam", "#9C7D56", .95),
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
    root["port_clear_width_m"] = .632


def _legs(root, mats, low=False, positions=None):
    positions = positions or [(-.265, -.37), (.265, -.37), (-.265, .37), (.265, .37)]
    for i, (x, z) in enumerate(positions):
        box("leg_%d" % i, (x, .425, z), (.05, .85, .05),
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


def _treads(root, mats, axis='Z', center=(0, 0), length=.88, width=.606, count=9, low=False):
    for index in range(count):
        along = -length*.5 + (index+.5)*length/count
        half = .006 if not low else .008
        if axis == 'Z':
            x, z = center[0], center[1]+along
            points = [(x-width/2,.9,z-half),(x+width/2,.9,z-half),
                      (x+width/2,.9,z+half),(x-width/2,.9,z+half)]
        else:
            x, z = center[0]+along, center[1]
            points = [(x-half,.9,z-width/2),(x+half,.9,z-width/2),
                      (x+half,.9,z+width/2),(x-half,.9,z+width/2)]
        obj = _mesh('belt_tread_band_%s_%02d' % (axis,index), points,
                    [(3,2,1,0)], mats['tread'], root, upward=True)
        obj['visual_flow_surface'] = True


def _end_rollers(root, mats, low=False):
    for end in (-1,1):
        _raw_cylinder('belt_end_idler_%d' % end, (0,.856,end*.456),
                      .044,.62,mats['belt'],root,axis='X',vertices=8 if low else 12)
        if not low:
            for side in (-1,1):
                box('idler_tension_carrier_%d_%d' % (end,side),
                    (side*.319,.825,end*.435),(.04,.095,.11),mats['metal'],root,.003)
                box('idler_tension_slot_%d_%d' % (end,side),
                    (side*.339,.833,end*.435),(.002,.016,.058),mats['steel'],root,0)
                _raw_cylinder('idler_axle_%d_%d' % (end,side),
                              (side*.337,.856,end*.456),.015,.006,
                              mats['metal'],root,axis='X',vertices=8)


def _flow_metadata(root, mats):
    root['belt_materials_json'] = json.dumps([mats['belt'].name,mats['tread'].name])
    root['belt_visual_top_y'] = .9
    root['tread_bands_are_visual_only'] = True


def _guide_segment(root, mats, name, start, end):
    dx,dz = end[0]-start[0],end[1]-start[1]
    length = math.hypot(dx,dz)
    for suffix, y, height, width, mat in (
        ('channel',.833,.115,.04,mats['steel']),
        ('guard',.925,.05,.024,mats['yellow'])):
        obj = box(name+'_'+suffix,((start[0]+end[0])/2,y,(start[1]+end[1])/2),
                  (length,height,width),mat,root,.003)
        obj.rotation_euler.z = math.atan2(-dz,dx)


def _transfer_platform(root, mats, branch=False):
    # A real wide central deck accommodates the 0.721m diagonal of a turning
    # .60x.40 tote. Its open arms still meet the exact canonical +/-0.5m ports.
    w,n = .43,.31
    outline=[(-w,-w),(-n,-w),(-n,-.5),(n,-.5),(n,-w),
             (w,-w),(w,-n),(.5,-n),(.5,n),(w,n)]
    if branch:
        outline += [(w,w),(n,w),(n,.5),(-n,.5),(-n,w),(-w,w)]
    else:
        outline += [(w,w),(-w,w)]
    vertices=[(x,y,z) for y in (.805,.892) for x,z in outline]
    count=len(outline)
    faces=[tuple(range(count-1,-1,-1)),tuple(range(count,count*2))]
    faces += [(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
    _mesh('wide_open_transfer_platform',vertices,faces,mats['steel'],root,.003)
    for end in (-1,1) if branch else (-1,):
        box('short_in_out_belt_%d' % end,(0,.866,end*.4),(.62,.067,.2),mats['belt'],root,.002)
        _treads(root,mats,center=(0,end*.4),length=.18,width=.606,count=3)
    box('short_branch_belt',(.4,.866,0),(.2,.067,.62),mats['belt'],root,.002)
    _treads(root,mats,axis='X',center=(.4,0),length=.18,width=.606,count=3)
    # Flush roller crowns at Y=.9; the supporting plate is only 8mm below.
    for row,z in enumerate((-.24,-.08,.08,.24)):
        for col,x in enumerate((-.24,-.08,.08,.24)):
            _raw_cylinder('central_transfer_roller_%s_%s' % (row,col),
                          (x,.872,z),.028,.13,mats['metal'],root,axis='X',vertices=12)
    root['central_clearance_m'] = [.78,.78]
    root['central_platform_m'] = [.86,.86]
    root['nominal_size_m'] = [1,.95,1]
    _flow_metadata(root,mats)


def conveyor(low=False):
    mats = _materials()
    asset_id = "conveyor-low" if low else "conveyor-high"
    root = _root(asset_id, "conveyor_straight_lod" if low else "conveyor_straight", "conveyor")
    root["lod"] = "low" if low else "high"
    root["nominal_size_m"] = [.68, .95, 1.0]
    _ports(root)
    _flow_metadata(root,mats)
    if low:
        box("belt_and_deck_proxy", (0, .858, 0), (.62, .083, .912), mats["belt"], root, bevel=0)
        for side in (-1, 1):
            box("yellow_side_guide_%d" % side, (side*.328, .925, 0),
                (.024, .05, 1), mats["yellow"], root, bevel=0)
            box('steel_side_channel_%d' % side,(side*.319,.833,0),
                (.042,.115,1),mats['steel'],root,0)
        _legs(root, mats, low=True)
        box("underframe_cross_proxy", (0, .275, -.37), (.56, .035, .035),
            mats["steel"], root, bevel=0)
        _end_rollers(root,mats,low=True)
        _treads(root,mats,count=5,low=True)
        return root
    belt=box("continuous_rubber_belt", (0, .866, 0), (.62, .067, .912),
             mats["belt"], root, bevel=.004)
    belt['visual_flow_surface'] = True
    for side in (-1, 1):
        box("lower_channel_%d" % side, (side*.319, .833, 0), (.042, .115, 1),
            mats["steel"], root, bevel=.004)
        box("yellow_side_guard_%d" % side, (side*.328, .925, 0), (.024, .05, 1),
            mats["yellow"], root, bevel=.003)
        for z in (-.30, .30):
            _raw_cylinder("rail_fastener_%d_%.2f" % (side,z),
                          (side*.339, .839, z), .012, .002,
                          mats["metal"], root, axis="X", vertices=6)
    _end_rollers(root,mats)
    _treads(root,mats)
    _legs(root, mats)
    _motor(root, mats)
    box('photoelectric_sensor',( .331,.864,.18),(.016,.035,.045),mats['metal'],root,.002)
    box('sensor_dark_lens',( .321,.864,.18),(.003,.019,.024),mats['steel'],root,0)
    return root


def corner():
    mats = _materials()
    root = _root("conveyor-corner", "conveyor_corner", "conveyor")
    root["family_variant"] = "orthogonal_L_transfer"
    root["path_runtime"] = [0,.9,-.5, 0,.9,0, .5,.9,0]
    root["path_rule"] = "Two orthogonal half-metre legs; no route smoothing or timing change."
    _ports(root, corner=True)
    _transfer_platform(root,mats)
    for name,a,b in (
        ('outer_left',(-.447,-.36),(-.447,.447)),
        ('outer_back',(-.447,.447),(.36,.447)),
        ('inlet_left_transition',(-.328,-.482),(-.447,-.36)),
        ('outlet_back_transition',(.36,.447),(.482,.328)),
        ('inlet_right_cap',(.328,-.482),(.395,-.447)),
        ('outlet_front_cap',(.447,-.395),(.482,-.328))):
        _guide_segment(root,mats,name,a,b)
    _legs(root,mats,positions=[(-.33,-.33),(.33,-.33),(-.33,.33),(.33,.33)])
    _motor(root,mats,(-.07,.725,.10))
    return root


def diverter():
    mats = _materials()
    root = _root("conveyor-diverter", "conveyor_diverter", "conveyor")
    root["family_variant"] = "three_way_T"
    _ports(root, branch=True)
    _transfer_platform(root,mats,branch=True)
    _guide_segment(root,mats,'closed_left',(-.447,-.36),(-.447,.36))
    for side in (-1,1):
        _guide_segment(root,mats,'left_port_transition_'+str(side),
                       (-.328,side*.482),(-.447,side*.36))
        _guide_segment(root,mats,'right_port_cap_'+str(side),
                       (.328,side*.482),(.395,side*.447))
        _guide_segment(root,mats,'branch_cap_'+str(side),
                       (.447,side*.395),(.482,side*.328))
    _legs(root,mats,positions=[(-.33,-.33),(.33,-.33),(-.33,.33),(.33,.33)])
    _motor(root, mats)
    return root


def _box_faces():
    return [(0,1,2,3), (4,7,6,5), (0,4,5,1),
            (1,5,6,2), (2,6,7,3), (3,7,4,0)]


def _rounded_loop(half_x, half_z, radius, segments=3):
    result=[]
    for cx,cz,start in ((half_x-radius,half_z-radius,0),
                        (-half_x+radius,half_z-radius,90),
                        (-half_x+radius,-half_z+radius,180),
                        (half_x-radius,-half_z+radius,270)):
        for index in range(segments+1):
            angle=math.radians(start+90*index/segments)
            result.append((cx+radius*math.cos(angle),cz+radius*math.sin(angle)))
    return result


def _tote_shell(root,mats,low=False):
    segments=1 if low else 3
    shapes=((0 if low else .012,.27,.17,.018),
            (.30 if low else .278,.30 if low else .291,.20 if low else .191,.028),
            (.035,.251,.151,.014),
            (.30 if low else .278,.276 if low else .273,.176 if low else .173,.017))
    loops=[[(x,y,z) for x,z in _rounded_loop(hx,hz,r,segments)] for y,hx,hz,r in shapes]
    count=len(loops[0]);vertices=sum(loops,[])
    faces=[tuple(range(count-1,-1,-1)),tuple(range(2*count,3*count))]
    for index in range(count):
        nxt=(index+1)%count
        faces += [(index,nxt,nxt+count,index+count),
                  (index+2*count,index+3*count,nxt+3*count,nxt+2*count),
                  (index+count,nxt+count,nxt+3*count,index+3*count)]
    body=_mesh('rounded_tapered_hollow_tote',vertices,faces,mats['teal'],root)
    if low:
        body.data.materials.append(mats['rim'])
        for index in range(count):body.data.polygons[4+3*index].material_index=1
        return body
    # Rounded apertures are actual through-holes in the 18mm side walls.
    hole=_rounded_loop(.085,.0225,.015,3)
    for side in (-1,1):
        cutter_vertices=[(side*x,.238+y,z) for x in (.245,.325) for z,y in hole]
        n=len(hole)
        cutter_faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
        cutter_faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        cutter=_mesh('temporary_rounded_handhold_cutter',cutter_vertices,cutter_faces,mats['teal'],root)
        bpy.ops.object.select_all(action='DESELECT')
        body.select_set(True)
        bpy.context.view_layer.objects.active=body
        modifier=body.modifiers.new('Real rounded hand opening','BOOLEAN')
        modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.data.objects.remove(cutter,do_unlink=True)
    bevel=body.modifiers.new('Soft moulded wall edges','BEVEL')
    bevel.width=.0015;bevel.segments=2;bevel.harden_normals=True
    body.modifiers.new('Moulded wall normals','WEIGHTED_NORMAL')
    return body


def _rounded_tote_rim(root,mats):
    vertices=[]
    for y,hx,hz,r in ((.274,.30,.20,.028),(.30,.30,.20,.028),
                       (.274,.276,.176,.017),(.30,.276,.176,.017)):
        vertices += [(x,y,z) for x,z in _rounded_loop(hx,hz,r)]
    n=16;faces=[]
    for i in range(n):
        j=(i+1)%n
        faces += [(i,j,j+n,i+n),(i+2*n,i+3*n,j+3*n,j+2*n),
                  (i+n,j+n,j+3*n,i+3*n),(i,j,j+2*n,i+2*n)]
    _mesh('continuous_rounded_double_wall_rim',vertices,faces,mats['rim'],root,.001)


def _handhold_bezel(root,mats,side):
    outer=_rounded_loop(.096,.033,.022)
    inner=_rounded_loop(.0855,.023,.0155)
    vertices=[]
    for offset,shape in ((.001,outer),(.007,outer),(.001,inner),(.007,inner)):
        for z,dy in shape:
            y=.238+dy
            x=side*(.27+.021*(y-.012)/.266+offset)
            vertices.append((x,y,z))
    n=16;faces=[]
    for i in range(n):
        j=(i+1)%n
        faces += [(i,j,j+n,i+n),(i+2*n,i+3*n,j+3*n,j+2*n),
                  (i+n,j+n,j+3*n,i+3*n),(i,j,j+2*n,i+2*n)]
    _mesh('thick_rounded_handhold_surround_'+str(side),vertices,faces,mats['rim'],root)


def tote(low=False):
    mats=_materials()
    asset_id='tote-low' if low else 'order-tote'
    root=_root(asset_id,'order_tote','order-tote')
    root['lod']='low' if low else 'high'
    root['size_m']=[.60,.30,.40]
    root['interior_minimum_m']=[.502,.265,.302]
    root['recommended_contents_envelope_m']=[.48,.22,.28]
    root['cargo_kind']='tote';root['hollow']=True;root['origin']='bottom_centre'
    root['handhold_shape']='rounded_real_aperture' if not low else 'omitted_at_distance'
    _cargo_node(root,'anchor_cargo',(0,0,0))
    _cargo_node(root,'anchor_contents',(0,.035,0),'contents_attachment')
    _cargo_node(root,'anchor_grip_left',(-.292,.263,0),'hand_contact')
    _cargo_node(root,'anchor_grip_right',(.292,.263,0),'hand_contact')
    _tote_shell(root,mats,low)
    if low:return root
    _rounded_tote_rim(root,mats)
    for side in (-1,1):
        _handhold_bezel(root,mats,side)
        for index,y in enumerate((.094,.183)):
            z=side*(.17+.021*(y-.012)/.266+.004)
            box('moulded_long_wall_rib_%s_%s'%(side,index),(0,y,z),
                (.475,.015,.014),mats['rim'],root,.003)
    for sx in (-1,1):
        for sz in (-1,1):
            beam('rounded_corner_reinforcement_%s_%s'%(sx,sz),
                 (sx*.253,.035,sz*.153),(sx*.277,.266,sz*.177),.013,mats['rim'],root)
            box('moulded_bottom_foot_%s_%s'%(sx,sz),(sx*.21,.006,sz*.12),
                (.08,.012,.045),mats['teal'],root,.002)
    label_z=.17+.021*(.145-.012)/.266+.0015
    frame=box('recessed_label_surround',(0,.145,label_z),(.142,.066,.002),mats['rim'],root,.0004)
    label=box('blank_recessed_tote_label',(0,.145,label_z+.0013),(.122,.048,.001),mats['label'],root,.0002)
    frame.rotation_euler.x=label.rotation_euler.x=math.atan(.021/.266)
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
    box("closed_corrugated_body", (0,.159,0), (.50,.318,.377),
        mats["card"], root, bevel=.0025)
    for side in (-1,1):
        box("flush_folded_top_flap_%d" % side, (side*.124,.3186,0), (.246,.0008,.376),
            mats["flap"], root, bevel=0)
        box("front_rear_kraft_tape_%d" % side, (0,.159,side*.1895),
            (.048,.318,.001), mats["tape"], root, bevel=0)
        for z in (-.17,.17):
            box("folded_corner_vertical_%d_%.2f" % (side,z),
                (side*.247,.159,z), (.0012,.288,.0012), mats["fold"], root, bevel=0)
    box("centre_top_sealing_tape", (0,.3196,0), (.048,.0008,.379),
        mats["tape"], root, bevel=0)
    box("blank_shipping_label", (.13,.214,.1895), (.115,.065,.001),
        mats["label"], root, bevel=.0002)
    box('flat_top_shipping_label',(.13,.3196,-.037),(.13,.0008,.105),mats['label'],root,0)
    # Small crease marks meet the body's bevels, representing folded carton corners.
    for sx in (-1,1):
        for sz in (-1,1):
            for top in (False,True):
                y0, y1 = ((.008,.024) if not top else (.294,.310))
                beam("diagonal_fold_%d_%d_%d" % (sx,sz,top),
                     (sx*.246,y0,sz*.180), (sx*.232,y1,sz*.187),
                     .0012, mats["fold"], root)
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
