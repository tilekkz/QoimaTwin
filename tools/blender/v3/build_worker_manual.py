"""P03.5.1 rigid manual controls on unchanged R05body mesh pieces."""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,finish,material,pivot,reset,runtime_xyz,xyz
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_picker_figure import physical_body
from build_picking_cart import connected
from build_sealed_parcel import append_source
from build_standard_carton import collect
from build_long_rack import block

OUT=ROOT/'assets/v3/iterations/worker-base/P03.5.1';EPS=2e-6

if __name__=='__main__':
    paths=['assets/v3/blender/worker-base.blend','frontend/public/models/v3/worker-base.glb','docs/v3/contract-proposals/cargo-catalog-v3.json']
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths};reset()
    worker=append_source(paths[0],'worker_base_root',None)
    before,_=physical_body(worker);raw={o.name:[tuple(v.co) for v in o.data.vertices] for o in worker.children_recursive if o.type=='MESH'}
    controls={}
    for side in ('L','R'):
        hand=bpy.data.objects['joint__hand_'+side];basis=hand.matrix_basis.copy()
        roll=pivot('joint__palm_roll_'+side,(0,0,0),hand.parent,'Y');roll.matrix_basis=basis
        roll['joint_mode']='manual_forearm_axial_roll';roll['rotation_range_radians']=[-math.pi,math.pi]
        roll['meaning']='Explicit added manual forearm/pronation control; does not relax original hand Euler limits.'
        hand.parent=roll;hand.matrix_basis=Matrix.Identity(4)
        controls[side]={'roll':roll}
        for label,part,axis,limit in [('upper','upper_pad','Y',.014),('lower','lower_pad','Y',.014),('thumb','thumb','Z',.005)]:
            node=pivot('joint__finger_'+label+'_'+side,(0,0,0),hand,axis)
            node['joint_mode']='rigid_finger_pad_translation';node['translation_axis_runtime']=axis
            node['signed_travel_m']=[-limit,0] if label in ('upper','thumb') else [0,limit]
            node['meaning']='Same rigid closed mitten part; no geometry scaling or deformation.'
            obj=bpy.data.objects['mitten_'+side+'_'+part];obj.parent=node
            controls[side][label]=node
    bpy.context.view_layer.update();after,_=physical_body(worker)
    assert all(raw[o.name]==[tuple(v.co) for v in o.data.vertices] for o in worker.children_recursive if o.type=='MESH')
    by_name={p['name']:p for p in before}
    neutral_error=max(abs(a-b) for p in after for v,w in zip(p['verts'],by_name[p['name']]['verts']) for a,b in zip(v,w));assert neutral_error<EPS
    assert len(after)==50
    connections=[]
    for side in ('L','R'):
        c=controls[side];hand=bpy.data.objects['joint__hand_'+side]
        for roll,close,retract in [(0,0,0),(0,.0025,.005),(0,.014,.005),(math.pi,.0025,.005),(-math.pi,.014,0)]:
            c['roll'].rotation_euler=(0,0,roll);c['upper'].location=xyz((0,-close,0));c['lower'].location=xyz((0,close,0));c['thumb'].location=xyz((0,0,-retract))
            parts,_=collect(hand);links=connected(parts);assert len(parts)==4
            connections.append({'side':side,'roll_rad':roll,'closing_travel_m':close,'thumb_retraction_m':retract,'closed_parts':4,'actual_connection_links':links})
        c['roll'].rotation_euler=(0,0,0);c['upper'].location=c['lower'].location=c['thumb'].location=xyz((0,0,0))
    # Pure C02envelope witnesses: no unit stock is baked into this template.
    c=controls['L'];c['roll'].rotation_euler=(0,0,math.pi);c['upper'].location=xyz((0,-.0025,0));c['lower'].location=xyz((0,.0025,0));c['thumb'].location=xyz((0,0,-.005))
    hand=bpy.data.objects['joint__hand_L'];grip=bpy.data.objects['anchor_hand_grip_L'];centre=runtime_xyz(grip.location);gp,_=collect(hand)
    mat=material('QA_ONLY_C02_unit_envelopes','#C99A60');units=[];witnesses=[]
    for i,offset in enumerate((-.0325,.0325)):
        p=[centre[0]+offset,centre[1],centre[2]-.0025]
        obj=block('QA_ONLY_unit_'+str(i),[p[0]-.03,p[1]-.02,p[2]-.02],[p[0]+.03,p[1]+.02,p[2]+.02],mat,hand,.0002);units.append(obj)
        bpy.context.view_layer.update()
        origin=hand.matrix_world@xyz(p)
        for direction in [(0,1,0),(0,-1,0),(0,0,-1)]:
            d=hand.matrix_world.to_3x3()@xyz(direction);hits=[]
            for part in gp:
                hit,_,_,_=part['bvh'].ray_cast(origin,d,.03)
                if hit is not None:hits.append((hit,part['name']))
            assert hits,('missing actual mitten witness',i,direction)
            point,name=min(hits,key=lambda pair:(pair[0]-origin).length);gap=abs((point-origin).length-.02);assert gap<EPS
            witnesses.append({'unit_envelope':i,'direction':direction,'actual_part':name,'gap_m':gap})
    # Actual envelope/skin intersections may only be exact opposed boundaries.
    for obj in units:
        bpy.context.view_layer.update();evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
        for v in mesh.vertices:
            point=evaluated.matrix_world@v.co
            for part in gp:
                hit,n,_,dist=part['bvh'].find_nearest(point);assert dist<EPS or n.dot(point-hit)>=-EPS,('envelope inside skin',obj.name,part['name'])
        evaluated.to_mesh_clear();bpy.data.objects.remove(obj,do_unlink=True)
    for c in controls.values():
        c['roll'].rotation_euler=(0,0,0)
        for name in ('upper','lower','thumb'):c[name].location=xyz((0,0,0))
    worker['reference_id']='R05';worker['role']='manual_worker_template';worker['preserve_articulation']=True
    worker['body_mesh_geometry_unchanged']=True;worker['manual_control_spec']='docs/adaptive-v3/specs/P03.5.1.md'
    worker['manual_controls_json']=json.dumps({'roll':'forearm-localY[-pi,+pi]','finger_closing_travel_m':[0,.014],'thumb_retraction_m':[0,.005]})
    OUT.mkdir(parents=True,exist_ok=True);stats=finish('worker-manual',worker)
    assert len(stats['pivots'])==23 and len(stats['anchors'])==7
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    report={'task_id':'P03.5.1','source_hashes':hashes,'body_parts':50,'raw_body_mesh_coordinates_unchanged':True,'neutral_world_vertex_error_m':neutral_error,'pivots':23,'anchors':7,'original15joint_limits_retained':True,'rigid_mitten_connection_poses':connections,'C02_two_unit_envelope_contacts':witnesses,'QA_envelopes_excluded_from_export':True,'glb_sha256':stats['sha256'],'scope':'Manual rig interface only. Two C02unit envelopes are temporary contact witnesses, not stock/model/action acceptance. Actual source/carry comes next.'}
    (OUT/'actual-manual-rig-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('P0351_MANUAL_RIG_VERIFIED '+json.dumps({'body_parts':50,'neutral_vertex_error_m':neutral_error,'pivots':23,'anchors':7,'grip_envelope_contacts':len(witnesses)}))
