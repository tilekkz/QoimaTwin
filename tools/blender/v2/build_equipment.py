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


def _mesh_part(name, vertices, faces, mat, root, bevel=0, segments=2):
    import bmesh
    mesh = bpy.data.meshes.new(name+"_mesh")
    mesh.from_pydata([tuple(xyz(v)) for v in vertices], [], faces)
    mesh.materials.append(mat)
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free(); mesh.update()
    obj = bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj); obj.parent = root
    if bevel:
        mod=obj.modifiers.new("Manufactured edge radius","BEVEL")
        mod.width=bevel; mod.segments=segments; mod.harden_normals=True
        normal=obj.modifiers.new("Broad weighted face normals","WEIGHTED_NORMAL")
        normal.keep_sharp=True
    return obj


def _soft_box(name, loc, size, mat, root, bevel=.01, segments=3):
    obj=box(name,loc,size,mat,root,bevel=bevel)
    for mod in obj.modifiers:
        if mod.type=="BEVEL": mod.segments=segments
    return obj


def _remove_parts(root, prefixes):
    for obj in list(root.children_recursive):
        if obj.type=="MESH" and any(obj.name.startswith(p) for p in prefixes):
            bpy.data.objects.remove(obj,do_unlink=True)


def _profile_yz(name, profile, x0, x1, mat, root, bevel=.008):
    n=len(profile)
    vertices=[(x,y,z) for x in (x0,x1) for y,z in profile]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return _mesh_part(name,vertices,faces,mat,root,bevel)


def _round_plan(width,depth,radius):
    points=[]
    for cx,cz,start in ((width/2-radius,depth/2-radius,0),
                        (-width/2+radius,depth/2-radius,90),
                        (-width/2+radius,-depth/2+radius,180),
                        (width/2-radius,-depth/2+radius,270)):
        for j in range(4):
            a=math.radians(start+j*30)
            points.append((cx+radius*math.cos(a),cz+radius*math.sin(a)))
    return points


def _counterweight(root,mat):
    # A single lofted casting: softened rear plan, broad shoulder and taper.
    rings=((.19,.77,.40,.085),(.28,.94,.47,.11),
           (.76,.96,.47,.11),(.89,.88,.43,.105),(.97,.74,.35,.085))
    vertices=[]
    for y,w,d,r in rings:
        vertices += [(x,y,z-1.065) for x,z in _round_plan(w,d,r)]
    n=16; faces=[tuple(reversed(range(n))),tuple(range((len(rings)-1)*n,len(rings)*n))]
    faces += [(k*n+i,k*n+(i+1)%n,(k+1)*n+(i+1)%n,(k+1)*n+i)
              for k in range(len(rings)-1) for i in range(n)]
    return _mesh_part("cast_counterweight",vertices,faces,mat,root,.008,2)


def _lathe_x(name,centre,profile,mat,root,segments=24,smooth=True):
    x,y,z=centre; n=segments
    vertices=[(x+offset,y+r*math.cos(i*math.tau/n),z+r*math.sin(i*math.tau/n))
              for offset,r in profile for i in range(n)]
    faces=[(k*n+i,k*n+(i+1)%n,((k+1)%len(profile))*n+(i+1)%n,
            ((k+1)%len(profile))*n+i) for k in range(len(profile)) for i in range(n)]
    obj=_mesh_part(name,vertices,faces,mat,root)
    for p in obj.data.polygons:p.use_smooth=smooth
    return obj


def _polished_wheel(root,name,x,y,z,radius,tire,steel,dark):
    # Continuous rounded sidewalls and a wide crown replace gear-like tread cubes.
    r=radius
    profile=[(-.105,r*.57),(-.105,r*.74),(-.093,r*.91),(-.067,r*.985),
             (-.043,r),(.043,r),(.067,r*.985),(.093,r*.91),
             (.105,r*.74),(.105,r*.57)]
    _lathe_x(name+"_tire",(x,y,z),profile,tire,root)
    side=1 if x>0 else -1
    cylinder(name+"_pressed_rim",(x+side*.090,y,z),r*.575,.018,
             steel,root,axis="X",vertices=20)
    _lathe_x(name+"_rim_bead",(x+side*.099,y,z),
             [(-.004,r*.55),(-.004,r*.59),(.003,r*.59),(.003,r*.55)],steel,root,20)
    cylinder(name+"_hub_recess",(x+side*.095,y,z),r*.40,.008,dark,root,axis="X",vertices=16)
    cylinder(name+"_axle_cap",(x+side*.096,y,z),r*.245,.018,steel,root,axis="X",vertices=16)
    for i in range(6):
        a=i*math.tau/6
        lug=cylinder(name+"_lug_%d"%i,(x+side*.101,y+r*.465*math.cos(a),z+r*.465*math.sin(a)),
                     .009,.008,steel,root,axis="X",vertices=6)
        for mod in list(lug.modifiers):lug.modifiers.remove(mod)
    # Twelve shallow continuous shoulder grooves; no protruding tyre teeth.
    groove=material("rubber_tread_recess","#171D20",.94)
    for i in range(12):
        a=i*math.tau/12+.055
        vertices=[]
        for offset,angle in ((-.082,a-.012),(-.044,a+.055),(.044,a+.055),(.082,a-.012)):
            rr=r*(.957 if abs(offset)>.07 else 1.0001)
            vertices.append((x+offset,y+rr*math.cos(angle),z+rr*math.sin(angle)))
        _mesh_part(name+"_tread_sipe_%02d"%i,vertices,[(0,1,2,3)],groove,root)


def _cab_frame(root,side,mat):
    path=[(.84,-1.015),(1.89,-.965),(2.045,-.91),(2.102,-.82),
          (2.102,-.17),(2.055,-.075),(1.92,-.025),(.60,.08)]
    outer=[];inner=[];half=.039
    for i,p in enumerate(path):
        a=Vector(path[max(0,i-1)]); b=Vector(p); c=Vector(path[min(len(path)-1,i+1)])
        t0=(b-a).normalized() if i else (c-b).normalized()
        t1=(c-b).normalized() if i<len(path)-1 else t0
        n0=Vector((-t0.y,t0.x));n1=Vector((-t1.y,t1.x))
        m=(n0+n1).normalized();offset=m*(half/max(.5,m.dot(n0)))
        outer.append(tuple(b+offset));inner.append(tuple(b-offset))
    _profile_yz("formed_cab_side_%d"%side,outer+list(reversed(inner)),
                side*.40-.041,side*.40+.041,mat,root,.009)


def _polish_forklift(root):
    _remove_parts(root,("tapered_main_chassis","rear_counterweight","rear_hood", "side_panel_",
                       "front_fender_","access_step_","step_grip_","rear_light_","rear_red_",
                       "rear_amber_","left_front_","right_front_","left_rear_","right_rear_",
                       "seat_","driver_floorboard","angled_steering_column","control_lever_",
                       "roll_cage_","roof_","overhead_guard_","steering_wheel_"))
    saffron=bpy.data.materials["industrial_saffron"]; edge=bpy.data.materials["saffron_edge"]
    dark=bpy.data.materials["charcoal_steel"];steel=bpy.data.materials["lift_steel"]
    tire=bpy.data.materials["rubber_tire"];seat=bpy.data.materials["seat_cushion"]
    _counterweight(root,saffron)
    _soft_box("underbody_casting",(0,.265,-.46),(.79,.23,1.29),saffron,root,.045)
    _soft_box("driver_floorboard",(0,.515,-.31),(.72,.05,.72),dark,root,.016)
    profile=[(.28,-.91),(.81,-.91),(.85,-.70),(.80,-.57),(.53,-.43),(.53,-.23),
             (.635,-.13),(.66,.09),(.62,.30),(.50,.32),(.47,.275),(.59,.205),
             (.645,.06),(.59,-.105),(.45,-.25),(.32,-.29),(.28,-.49)]
    for side in (-1,1):
        label="left" if side<0 else "right"
        _profile_yz("sculpted_side_body_%d"%side,profile,min(side*.37,side*.505),
                    max(side*.37,side*.505),saffron,root,.014)
        _soft_box("recessed_access_step_%d"%side,(side*.452,.402,-.385),(.176,.055,.27),dark,root,.012)
        for j in range(3):
            _soft_box("step_anti_slip_%d_%d"%(side,j),(side*.45,.432,-.46+j*.074),
                      (.14,.004,.014),steel,root,.001,1)
        for axle,y,z,r in (("front",.30,.06,.30),("rear",.225,-1.02,.225)):
            _polished_wheel(root,label+"_"+axle,side*.45,y,z,r,tire,steel,dark)
        _cab_frame(root,side,dark)
        _soft_box("cab_mount_boot_%d"%side,(side*.40,.845,-1.015),(.13,.11,.15),saffron,root,.012)
        _soft_box("rear_light_housing_%d"%side,(side*.32,.785,-1.307),(.16,.095,.024),dark,root,.012)
        _soft_box("rear_light_lens_%d"%side,(side*.32,.785,-1.316),(.126,.059,.006),
                  bpy.data.materials["rear_lamp"],root,.009)
        cylinder("beacon_base_%d"%side,(side*.33,.969,-1.05),.045,.022,dark,root,vertices=12)
        cylinder("beacon_lens_%d"%side,(side*.33,1.007,-1.05),.037,.055,
                 bpy.data.materials["amber_lamp"],root,vertices=12)
    # A padded seat with a coherent shell, bolster and pivots at the cushion.
    _soft_box("seat_suspension_base",(0,.745,-.68),(.42,.27,.40),dark,root,.025)
    _soft_box("seat_lower_shell",(0,.885,-.65),(.54,.055,.46),dark,root,.025)
    _soft_box("seat_lower_cushion",(0,.938,-.65),(.51,.104,.43),seat,root,.045,3)
    back=_soft_box("seat_back_shell",(0,1.20,-.875),(.53,.51,.115),dark,root,.044,3)
    back.rotation_euler.x=math.radians(-8)
    cushion=_soft_box("seat_back_cushion",(0,1.20,-.812),(.435,.415,.067),seat,root,.030,3)
    cushion.rotation_euler.x=math.radians(-8)
    for side in (-1,1):
        cylinder("seat_hinge_%d"%side,(side*.264,.97,-.77),.052,.026,dark,root,axis="X",vertices=12)
        _soft_box("seat_arm_mount_%d"%side,(side*.265,.961,-.75),(.046,.11,.09),dark,root,.014)
        _soft_box("seat_arm_pad_%d"%side,(side*.265,1.025,-.65),(.066,.044,.29),seat,root,.018)
    _profile_yz("steering_console",[(.54,.015),(.56,-.18),(.92,-.215),(1.035,-.205),
                                   (1.06,-.13),(.83,-.015)],-.115,.115,dark,root,.018)
    beam("steering_column_shaft",(0,.90,-.16),(0,1.13,-.27),.055,dark,root)
    source_forklift._steering_ring(root,dark,(0,1.13,-.27),(0,.8,-.6))
    for side in (-1,1):
        _soft_box("floor_pedal_%d"%side,(side*.12,.558,-.115),(.095,.025,.115),tire,root,.008)
    _soft_box("hydraulic_lever_console",(.295,.79,-.325),(.16,.24,.24),dark,root,.025)
    for i in range(2):
        beam("hydraulic_lever_%d"%i,(.265+.065*i,.90,-.29),(.265+.065*i,1.015,-.235),.022,steel,root)
        _soft_box("hydraulic_lever_grip_%d"%i,(.265+.065*i,1.019,-.235),(.041,.044,.048),tire,root,.012)
    for z in (-.91,-.035):
        _soft_box("guard_crossmember_%.2f"%z,(0,2.104,z),(.88,.075,.085),dark,root,.017,2)
    for i in range(6):
        _soft_box("guard_roof_slat_%d"%i,(0,2.107,-.78+i*.125),(.725,.032,.038),steel,root,.006,2)
    # Hydraulic rod now reaches a connected top clevis instead of ending in air.
    piston=_children(root,"hydraulic_ram_piston")[0]
    piston.location=xyz((0,1.69,.32));piston.dimensions=(.054,.054,.73)
    cylinder("hydraulic_upper_clevis",(0,2.04,.32),.052,.105,steel,root,axis="Z",vertices=12)
    root["art_revision"]="equipment-polish-2"
    root["geometry_revision_note"]="Lofted counterweight, sculpted wheel arches, formed cab frame, continuous tyre shoulders and cushioned seat; original functional anchors retained."


def forklift():
    root = source_forklift.build()
    _polish_forklift(root)
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


def _polish_packing(root):
    steel=bpy.data.materials["Steel_Charcoal"]; casing=bpy.data.materials["Equipment_Charcoal"]
    wood=bpy.data.materials["Birch_Warm"]; edge=bpy.data.materials["Birch_Edge"]
    hardware=bpy.data.materials["Hardware_Grey"];paper=bpy.data.materials["Label_Paper"]
    _remove_parts(root,("tabletop_","printer_body","printer_top_lid","monitor_body",
                        "tape_roll","tape_roll_core"))
    top=_soft_box("laminated_worktop",(0,.8225,0),(2.2,.055,1),edge,root,.014,3)
    top.data.materials.append(wood)
    for face in top.data.polygons:
        if face.normal.z>.9:face.material_index=1
    # A sloping moulded printer housing replaces two piled rectangular bricks.
    px,pz=.805,-.245
    profile=[(.878,pz-.15),(.878,pz+.15),(1.04,pz+.15),
             (1.095,pz+.105),(1.125,pz-.025),(1.113,pz-.15)]
    _profile_yz("printer_body",profile,px-.16,px+.16,casing,root,.012)
    for obj in _children(root,"printer_button"):
        obj.location=xyz((px+.103,1.027,pz+.154))
    _soft_box("printer_lid_release",(px+.166,1.015,pz-.045),(.012,.025,.04),
              steel,root,.004,2)
    # The monitor is thin at its perimeter and fuller only behind the display.
    _profile_yz("monitor_body",[(1.06,-.329),(1.06,-.266),(1.42,-.266),
                                (1.42,-.312),(1.38,-.335)],-.965,-.475,casing,root,.010)
    ink=material("equipment_label_ink","#788080",.9)
    for i in range(9):
        box("label_on_tray_bar_%d"%i,(px-.064+i*.014,.89015,pz+.285),
            (.002 if i%3 else .004,.0003,.046),ink,root,bevel=0)
    _lathe_x("tape_roll",(-.325,.956,.30),
             [(-.0295,.026),(-.0295,.060),(-.025,.066),(.025,.066),
              (.0295,.060),(.0295,.026)],bpy.data.materials["Carton_Tape"],root,20)
    for side in (-1,1):
        x=-.325+side*.04
        _profile_yz("tape_spindle_support_%d"%side,
                    [(.896,.268),(.896,.332),(.953,.326),(.971,.30),(.953,.274)],
                    x-.006,x+.006,casing,root,.003)
    cylinder("tape_spindle",(-.325,.956,.30),.010,.09,hardware,root,axis="X",vertices=10)
    # Thin corrugated walls/flaps read as folded packaging rather than a box bin.
    for obj in _children(root,"carton_bottom"):
        obj.location=xyz((.23,.853,.005));obj.dimensions=(.48,.43,.006)
    for obj in _children(root,"carton_side_wall"):
        side=-1 if obj.location.x<.23 else 1
        obj.location=xyz((.23+side*.237,1.0,.005));obj.dimensions=(.006,.43,.30)
    for obj in _children(root,"carton_end_wall"):
        side=-1 if -obj.location.y<.005 else 1
        obj.location=xyz((.23,1.0,.005+side*.212));obj.dimensions=(.468,.006,.30)
    for obj in _children(root,"carton_end_flap")+_children(root,"carton_side_flap"):
        for vertex in obj.data.vertices:vertex.co.z*=.5
        for modifier in obj.modifiers:
            if modifier.type=="BEVEL":modifier.width=.001;modifier.segments=1
    for obj in root.children_recursive:
        if obj.type=="MESH" and obj.name.startswith(("scanner_","monitor_base","printer_foot", "table_foot")):
            for modifier in obj.modifiers:
                if modifier.type=="BEVEL":modifier.segments=3
    root["art_revision"]="equipment-polish-2"
    root["geometry_revision_note"]="Single laminated worktop, moulded sloping printer, tapered monitor shell, hollow tape roll and thin corrugated carton. Service and transfer anchors unchanged."


def packing():
    root = source_packing.build()
    _polish_packing(root)
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
    nail = material("pallet_recessed_fastener", "#786F5F", .85, .15)
    for i,x in enumerate((-.57,0,.57)):
        _soft_box("pallet_bottom_runner_%d" % i, (x,.011,0), (.13,.022,1.0),
                  endgrain, root, bevel=.004,segments=2)
        for j,z in enumerate((-.40,0,.40)):
            _soft_box("pallet_block_%d_%d" % (i,j), (x,.061,z), (.13,.078,.16),
                      wood, root, bevel=.008,segments=2)
        _soft_box("pallet_upper_stringer_%d" % i, (x,.108,0), (.13,.016,1.0),
                  endgrain, root, bevel=.002,segments=2)
    for i in range(8):
        z=-.434+i*.124
        plank=_soft_box("pallet_deck_slat_%d" % i, (0,.12785,z), (1.4,.0237,.112),
                        wood if i%2 else alternate, root, bevel=.003,segments=2)
        plank.data.materials.append(endgrain)
        for face in plank.data.polygons:
            if abs(face.normal.x)>.9:face.material_index=1
        for j,x in enumerate((-.57,0,.57)):
            fastener=cylinder("pallet_flush_nail_%d_%d"%(i,j),(x,.13985,z),.0045,.0003,
                              nail,root,vertices=8)
            _raw_part(fastener)
    root["art_revision"]="equipment-polish-2"
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
    root = group("crate_root")
    _metadata(root, "crate", "assets/references/crate-reference.png", "geometric_center")
    root["cargo_kind"] = "storage_carton"
    root["nominal_size_m"] = [.55,.45,.65]
    root["art_revision"] = "equipment-polish-2"
    root["construction"] = "Folded corrugated carton; no lid slab or raised edge frame."
    kraft=material("carton_kraft_natural","#B99360",.91)
    flap=material("carton_flap_face","#C6A575",.91)
    tape=material("carton_paper_tape","#C1A16D",.83)
    fold=material("carton_fold_shadow","#97794F",.94)
    paper=material("carton_shipping_paper","#E2DECD",.95)
    ink=material("carton_print_warm_grey","#746F61",.96)
    # Flush, thin panels. The flap and tape fit inside the canonical envelope.
    _soft_box("corrugated_carton_body",(0,-.001,0),(.55,.448,.6488),kraft,root,.0025,2)
    for side in (-1,1):
        _soft_box("closed_major_flap_%d"%side,(side*.1385,.223,0),(.273,.004,.6488),
                  flap,root,.0009,1)
    box("major_flap_meeting_seam",(0,.2239,0),(.002,.0002,.648),fold,root,bevel=0)
    # One continuous paper-tape strip bends over both upper edges into short tabs.
    path=[(-.325,.151),(-.325,.2228),(-.3244,.225),(.3244,.225),(.325,.2228),(.325,.151)]
    inner=[(-.3244,.151),(-.3244,.2228),(-.3241,.2244),(.3241,.2244),(.3244,.2228),(.3244,.151)]
    _profile_yz("folded_sealing_tape",[(y,z) for z,y in path]+[(y,z) for z,y in reversed(inner)],
                -.032,.032,tape,root,0)
    # Paper lies on the face; ink has physical but sub-millimetre thickness.
    box("shipping_label_paper",(-.143,.045,.3246),(.150,.092,.0004),paper,root,bevel=.0001)
    for i,(x,w) in enumerate(((-.198,.003),(-.191,.002),(-.185,.004),(-.176,.002),
                               (-.169,.003),(-.161,.005),(-.151,.002),(-.145,.003),
                               (-.137,.002),(-.130,.004),(-.121,.002),(-.115,.003))):
        box("label_bar_%02d"%i,(x,.027,.3249),(w,.025,.0002),ink,root,bevel=0)
    for i,w in enumerate((.092,.066,.036)):
        box("label_address_line_%d"%i,(-.154,.073-i*.009,.3249),(w,.002,.0002),ink,root,bevel=0)
    # Two small up arrows, not large ornamental borders or pseudo-text.
    for i,x in enumerate((.125,.158)):
        box("handling_arrow_stem_%d"%i,(x,-.125,.3249),(.003,.028,.0002),ink,root,bevel=0)
        _mesh_part("handling_arrow_head_%d"%i,[(x-.009,-.115,.325),(x+.009,-.115,.325),
                                               (x,-.102,.325)],[(0,1,2)],ink,root)
    box("handling_arrow_baseline",(.1415,-.145,.3249),(.063,.002,.0002),ink,root,bevel=0)
    # A small flat conversion/box stamp on the side makes the long panel readable.
    for i,y in enumerate((-.112,-.135)):
        box("side_print_rule_%d"%i,(.2749,y,-.16),(.0002,.002,.078),ink,root,bevel=0)
    for i,z in enumerate((-.198,-.122)):
        box("side_print_edge_%d"%i,(.2749,-.1235,z),(.0002,.023,.002),ink,root,bevel=0)
    box("glued_panel_overlap",(-.2749,-.004,-.272),(.0002,.414,.001),fold,root,bevel=0)
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
