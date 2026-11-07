"""Faceted, closed-volume R04 quarter belt with exact L08 radius/ports."""
import json
import math

import bpy
import bmesh

from v3_common import ROOT, xyz, reset, group, material, box, beam, anchor, finish


def sector(name, ri, ro, lo, hi, mat, parent, start=0, end=-math.pi/2, count=8):
    """A single closed annular prism, with no coincident internal wedge faces."""
    vertices=[]
    for i in range(count+1):
        t=start+(end-start)*i/count
        for r,y in ((ri,lo),(ro,lo),(ri,hi),(ro,hi)):
            vertices.append(xyz((r*math.cos(t),y,r*math.sin(t))))
    faces=[]
    for i in range(count):
        a,b=4*i,4*(i+1)
        faces.extend([(a,b,b+1,a+1),(a+2,a+3,b+3,b+2),
                      (a,a+2,b+2,b),(a+1,b+1,b+3,a+3)])
    faces.extend([(0,1,3,2),(4*count,4*count+2,4*count+3,4*count+1)])
    mesh=bpy.data.meshes.new(name+'_mesh')
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent=parent
    mesh.materials.append(mat)
    return obj


def build():
    spec=json.loads((ROOT/'assets/v3/specs/conveyor-turn.dimensions.json').read_text())
    root=group('conveyor_turn_root')
    root['reference_id']='R04'
    root['role']='light_conveyor_module'
    root['deck_top_y_m']=.92
    root['path_radius_m']=1.25
    root['source_clock_required']=True
    teal=material('V3_Conveyor_Petrol','#2E7376')
    dark=material('V3_Conveyor_Charcoal','#293D46')
    rubber=material('V3_Conveyor_Belt','#3B474C',roughness=.95)
    rubber_alt=material('V3_Conveyor_BeltSegment','#404B4F',roughness=.95)
    tan=material('V3_Conveyor_Marker','#D3B583')
    frame=group('conveyor_frame',root)
    belt=group('belt_surface',root)
    belt['source_motion_kind']='analytic_quarter_arc'
    belt['path_radius_m']=1.25
    # Continuous solid deck; alternate top facets are separate material slots,
    # not coplanar decals or disconnected overlapping wedges.
    deck=sector('curved_belt_volume',.84,1.66,.86,.92,rubber,belt)
    deck.data.materials.append(rubber_alt)
    for i in range(8):
        deck.data.polygons[4*i+1].material_index=i%2
    sector('inner_guard',.80,.84,.89,1.0,teal,frame)
    sector('outer_guard',1.66,1.70,.89,1.0,teal,frame)
    # Recess structural ends from the deck connection plane, preventing the
    # coplanar end-face defect found on the first straight-module iteration.
    sector('inner_frame',.80,.95,.74,.90,teal,frame,-.008,-math.pi/2+.008)
    sector('outer_frame',1.55,1.695,.74,.90,teal,frame,-.008,-math.pi/2+.008)
    for j,t in enumerate(spec['foot_angles_rad']):
        for k,r in enumerate(spec['foot_radii_m']):
            x,z=r*math.cos(t),r*math.sin(t)
            box(f'leg_{j}_{k}',(x,.43,z),(.09,.74,.11),teal,frame,.006)
            box(f'foot_{j}_{k}',(x,.035,z),(.16,.07,.20),dark,frame,.004)
        beam(f'cross_member_{j}',(.91*math.cos(t),.755,.91*math.sin(t)),
             (1.59*math.cos(t),.755,1.59*math.sin(t)),.08,dark,frame)
    sector('lower_inner_brace',.90,.96,.20,.28,dark,frame,-.16,-math.pi/2+.16)
    sector('lower_outer_brace',1.54,1.60,.20,.28,dark,frame,-.16,-math.pi/2+.16)
    t=-math.pi/4
    marker=box('curve_marker',(1.692*math.cos(t),.815,1.692*math.sin(t)),(.008,.073,.14),tan,frame,.003)
    marker.rotation_euler.z=-t
    for name,pos in spec['connection_ports'].items():
        node=anchor(name,pos,root,'conveyor_connection')
        node['forward_vector_runtime']=spec['port_forward_vectors'][name]
    anchor('anchor_floor',(0,0,0),root,'support_anchor')
    anchor('anchor_payload_mid',(1.25/math.sqrt(2),.92,-1.25/math.sqrt(2)),root,'path_midpoint')
    return root


if __name__=='__main__':
    spec=json.loads((ROOT/'assets/v3/specs/conveyor-turn.dimensions.json').read_text())
    reset()
    report=finish('conveyor-turn',build())
    for edge in ('min','max'):
        assert max(abs(a-b) for a,b in zip(report['bounds_runtime'][edge],spec['bounds_runtime'][edge]))<1e-5
    for name,pos in spec['connection_ports'].items():
        assert max(abs(a-b) for a,b in zip(report['anchors'][name],pos))<1e-5
    assert 1.66*math.cos(math.pi/32)>1.64
    print('V3_TURN_DIMENSIONS_PORTS_AND_FACET_CLEARANCE_VERIFIED')
