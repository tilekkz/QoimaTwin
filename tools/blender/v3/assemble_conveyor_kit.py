"""Actual nine-module seam fixture; no warehouse or autonomous timing claim."""
import json
import math

from v3_common import ROOT, reset, group, xyz, anchor, finish
from build_conveyor_straight import build as straight
from build_conveyor_turn import build as turn
from build_conveyor_diverter import build as diverter


DECLARED=[
    ('CURVE',turn,(3,0,2.25),0),
    ('FEED',straight,(4.25,0,2.75),0),
    ('MAIN_E2',straight,(2.5,0,1),math.pi/2),
    ('MAIN_E1',straight,(1.5,0,1),math.pi/2),
    ('TRANSFER',diverter,(.5,0,1),0),
    ('MAIN_W1',straight,(-.5,0,1),math.pi/2),
    ('MAIN_W2',straight,(-1.5,0,1),math.pi/2),
    ('SPUR_1',straight,(.5,0,2),0),
    ('SPUR_2',straight,(.5,0,3),0),
]
PAIRS=[
    ('FEED','anchor_port_minus','CURVE','anchor_port_start'),
    ('CURVE','anchor_port_end','MAIN_E2','anchor_port_plus'),
    ('MAIN_E2','anchor_port_minus','MAIN_E1','anchor_port_plus'),
    ('MAIN_E1','anchor_port_minus','TRANSFER','anchor_port_east'),
    ('TRANSFER','anchor_port_west','MAIN_W1','anchor_port_plus'),
    ('MAIN_W1','anchor_port_minus','MAIN_W2','anchor_port_plus'),
    ('TRANSFER','anchor_port_branch','SPUR_1','anchor_port_minus'),
    ('SPUR_1','anchor_port_plus','SPUR_2','anchor_port_minus'),
]


if __name__=='__main__':
    reset();root=group('conveyor_kit_root')
    root['role']='engineering_module_seam_fixture'
    root['preserve_articulation']=True
    root['reference_id']='R04'
    root['not_an_operational_engine_run']=True
    units={};ports={}
    for name,builder,pos,yaw in DECLARED:
        unit=builder();unit.parent=root
        unit.location=xyz(pos);unit.rotation_euler.z=yaw
        nodes=[unit]+list(unit.children_recursive)
        for obj in nodes:
            obj.name=name+'__'+obj.name
            if obj.get('anchor_id'):ports[(name,obj['anchor_id'])]=obj
        unit['fixture_instance_id']=name
        units[name]=unit
    import bpy
    bpy.context.view_layer.update()
    actual=[]
    for a,pa,b,pb in PAIRS:
        left,right=ports[(a,pa)],ports[(b,pb)]
        gap=(left.matrix_world.translation-right.matrix_world.translation).length
        assert gap<1e-5,(a,b,gap)
        actual.append({'from':[a,pa],'to':[b,pb],'gap_m':gap})
    anchor('anchor_fixture_intake',(4.25,.92,3.05),root,'payload_stop')
    anchor('anchor_fixture_work',(.5,.92,3.3),root,'payload_stop')
    anchor('anchor_fixture_output',(-1.7,.92,1),root,'payload_stop')
    report=finish('conveyor-kit',root)
    path=ROOT/'docs/adaptive-v3/evidence/M13-assembly-numeric.json'
    path.write_text(json.dumps({'status':'VERIFY','scope':'actual source ports before GLB; runtime footprint/browsers remaining','modules':len(DECLARED),'connections':actual,'glb_sha256':report['sha256'],'dimensions_m':report['dimensions_m']},indent=2)+'\n')
    print('V3_KIT_EIGHT_PORT_PAIRS_VERIFIED')
