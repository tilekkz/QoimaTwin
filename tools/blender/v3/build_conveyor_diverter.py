"""Three open deck ports and one source-driven rigid transfer-table pivot."""
import json
import math
import bpy
import bmesh

from v3_common import ROOT, xyz, reset, group, material, box, cylinder, anchor, pivot, finish


def deck_surround(mat,parent):
    # Square outer perimeter minus an exactly facet-matched12-sided hole.
    # Include the square's45degree corners without approximating the hole by a
    # different polygon; this prevents coplanar overlap with the revolving disk.
    angles=sorted(set([math.pi/12+i*math.pi/6 for i in range(12)]+[i*math.pi/2 for i in range(4)]))
    vertices=[];faces=[];step=math.pi/6
    for t in angles:
        # Side normals align with the square axes; the hole's APOTHEM is.407.
        # Thus the whole radius.405 disk clears at every intermediate angle,
        # not merely at the neutral12-gon alignment.
        delta=t-round(t/step)*step
        ri=.407/math.cos(delta)
        ro=.41/max(abs(math.cos(t)),abs(math.sin(t)))
        for r,y in ((ri,.90),(ro,.90),(ri,.92),(ro,.92)):
            vertices.append(xyz((r*math.cos(t),y,r*math.sin(t))))
    for i in range(len(angles)):
        a,b=4*i,4*((i+1)%len(angles))
        faces.extend([(a,b,b+1,a+1),(a+2,a+3,b+3,b+2),(a,a+2,b+2,b),(a+1,b+1,b+3,a+3)])
    mesh=bpy.data.meshes.new('transfer_surround_mesh');mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new('transfer_deck_surround',mesh);bpy.context.collection.objects.link(obj)
    obj.parent=parent;mesh.materials.append(mat)
    return obj


def build():
    spec=json.loads((ROOT/'assets/v3/specs/conveyor-diverter.dimensions.json').read_text())
    root=group('conveyor_diverter_root')
    root['reference_id']='R04';root['role']='light_conveyor_module'
    root['deck_top_y_m']=.92;root['usable_width_m']=.82
    root['preserve_articulation']=True
    root['source_clock_required']=True
    teal=material('V3_Conveyor_Petrol','#2E7376')
    dark=material('V3_Conveyor_Charcoal','#293D46')
    rubber=material('V3_Conveyor_Belt','#3B474C',roughness=.95)
    tan=material('V3_Conveyor_Marker','#D3B583')
    warm=material('V3_Conveyor_Transfer','#C99A60',roughness=.9)
    frame=group('conveyor_frame',root)
    belt=group('belt_surface',root)
    # Main and branch volumes meet edge-to-edge, with no cap above deck level.
    box('main_deck_base',(0,.88,0),(1,.04,.82),rubber,belt,0)
    box('branch_deck_base',(0,.88,.455),(.82,.04,.09),rubber,belt,0)
    # Thin top strips surround the revolving disk. Below it is a genuine solid
    # backing deck rather than a hollow hole or a detached coloured decal.
    for x in (-.455,.455):
        box(f'main_end_top_{x}',(x,.91,0),(.09,.02,.82),rubber,belt,0)
    box('branch_top',(0,.91,.455),(.82,.02,.09),rubber,belt,0)
    deck_surround(rubber,belt)
    turn=pivot('joint__transfer',(0,.90,0),root,axis='Y')
    turn['stop_before_rotation']=True
    turn['source_turn_duration_s']=.8
    disk=cylinder('transfer_turntable',(0,.01,0),.405,.02,warm,turn,axis='Y',vertices=12)
    # The resting backing remains atY.90 where the round disk leaves corners.
    # Its lower height is below the supported maximal rotating footprint.
    for z in (-.385,.385):
        box(f'cross_frame_{z}',(0,.82,z),(.98,.16,.12),teal,frame,.008)
    box('rear_guard',(0,.945,-.43),(1,.11,.04),teal,frame,.006)
    for side in (-1,1):
        # Short corner stubs and branch side rails join without crossing any
        # of the three open transfer ends.
        box(f'front_corner_guard_{side}',(side*.475,.945,.43),(.05,.11,.04),teal,frame,.004)
        box(f'branch_guard_{side}',(side*.43,.945,.455),(.04,.11,.09),teal,frame,.004)
        for z in (-.30,.30):
            box(f'leg_{side}_{z}',(side*.36,.43,z),(.09,.74,.11),teal,frame,.006)
            box(f'foot_{side}_{z}',(side*.36,.035,z),(.16,.07,.22),dark,frame,.004)
        box(f'lower_brace_{side}',(side*.36,.24,0),(.07,.08,.60),dark,frame,.005)
    box('rear_marker',(0,.815,-.446),(.14,.073,.008),tan,frame,.003)
    box('drive_housing',(.20,.665,-.28),(.22,.16,.20),dark,frame,.012)
    for name,pos in spec['connection_ports'].items():
        anchor(name,pos,root,'conveyor_connection')
    anchor('anchor_floor',(0,0,0),root,'support_anchor')
    anchor('anchor_payload_centre',(0,.02,0),turn,'carrier_turntable_support')
    return root


if __name__=='__main__':
    spec=json.loads((ROOT/'assets/v3/specs/conveyor-diverter.dimensions.json').read_text())
    reset();report=finish('conveyor-diverter',build())
    for edge in ('min','max'):
        assert max(abs(a-b) for a,b in zip(report['bounds_runtime'][edge],spec['bounds_runtime'][edge]))<1e-5
    assert math.hypot(.3,.2)+.02<.405*math.cos(math.pi/12)-.0024
    for name,pos in spec['connection_ports'].items():
        assert max(abs(a-b) for a,b in zip(report['anchors'][name],pos))<1e-5
    print('V3_DIVERTER_BOUNDS_PORTS_AND_ROTATING_SUPPORT_VERIFIED')
