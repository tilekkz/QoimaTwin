"""P09.4 R07/R08 surface paint. No physical routing/storage changes."""
import json,math,hashlib,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,group,box,material,anchor,xyz,runtime_xyz,finish
from build_sealed_parcel import append_source
from build_standard_carton import collect

H=.001
OUT=ROOT/'assets/v3/iterations/environment-shell/P09.4'
INPUTS=['assets/references/v3/r07-ports-zones.png','assets/references/v3/r08-composition.png','assets/v3/specs/environment-shell.dimensions.json','assets/v3/blender/environment-shell.blend','docs/v3/contract-proposals/layout-v3.zones.json','docs/v3/contract-proposals/layout-links-v3.json']
LABELS={'SMALL':'SMALL','STANDARD':'STANDARD','HEAVY':'HEAVY','LONG':'LONG','FLEX':'FLEX','RESERVE':'RESERVE'}

def paint(obj,kind,semantic):
    obj['surface_paint']=True;obj['cast_shadow']=False;obj['collision_enabled']=False
    obj['paint_kind']=kind;obj['semantic_id']=semantic
    return obj

def strip(name,a,b,width,mat,parent,semantic):
    dx,dz=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dz)
    assert length>0
    obj=box(name,((a[0]+b[0])/2,H/2,(a[1]+b[1])/2),(width,H,length),mat,parent,0)
    obj.rotation_euler.z=math.atan2(dx,dz)
    return paint(obj,'line',semantic)

def dashed(name,a,b,width,mat,parent,semantic,dash=1.2,gap=.6):
    dx,dz=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dz);n=max(1,math.ceil(length/(dash+gap)))
    for i in range(n):
        start=i*(dash+gap);end=min(length,start+dash)
        if end<=start:continue
        strip(name+'_'+str(i),(a[0]+dx*start/length,a[1]+dz*start/length),(a[0]+dx*end/length,a[1]+dz*end/length),width,mat,parent,semantic)

GLYPHS={
 'A':[14,17,17,31,17,17,17],'B':[30,17,17,30,17,17,30],'C':[14,17,16,16,16,17,14],
 'D':[30,17,17,17,17,17,30],'E':[31,16,16,30,16,16,31],'F':[31,16,16,30,16,16,16],
 'G':[14,17,16,23,17,17,15],'H':[17,17,17,31,17,17,17],'I':[14,4,4,4,4,4,14],
 'J':[7,2,2,2,18,18,12],'K':[17,18,20,24,20,18,17],'L':[16,16,16,16,16,16,31],
 'M':[17,27,21,21,17,17,17],'N':[17,25,21,19,17,17,17],'O':[14,17,17,17,17,17,14],
 'P':[30,17,17,30,16,16,16],'Q':[14,17,17,17,21,18,13],'R':[30,17,17,30,20,18,17],
 'S':[15,16,16,14,1,1,30],'T':[31,4,4,4,4,4,4],'U':[17,17,17,17,17,17,14],
 'V':[17,17,17,17,17,10,4],'W':[17,17,17,21,21,21,10],'X':[17,17,10,4,10,17,17],
 'Y':[17,17,10,4,4,4,4],'Z':[31,1,2,4,8,16,31],'2':[14,17,1,2,4,8,31],
 '/':[1,1,2,4,8,16,16],' ':[0]*7}

def text(name,value,x,z,size,mat,parent,semantic):
    # Original block-stencil lettering: closed rectangular runs, no external
    # font or degenerate font cap tessellation at a1mm paint thickness.
    cell=size/7;start=-(len(value)*6-1)*cell/2;verts=[];faces=[]
    for index,char in enumerate(value):
        for row,bits in enumerate(GLYPHS[char]):
            col=0
            while col<5:
                if not bits&(1<<(4-col)):col+=1;continue
                end=col+1
                while end<5 and bits&(1<<(4-end)):end+=1
                x0=start+(index*6+col)*cell;x1=start+(index*6+end)*cell;z0=(row-3.5)*cell;z1=z0+cell;n=len(verts)
                verts.extend(xyz(p) for p in [(x0,0,z0),(x1,0,z0),(x1,0,z1),(x0,0,z1),(x0,H,z0),(x1,H,z0),(x1,H,z1),(x0,H,z1)])
                faces.extend(tuple(n+i for i in f) for f in [(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)])
                col=end
    mesh=bpy.data.meshes.new(name+'_stencil');mesh.from_pydata(verts,[],faces);mesh.update();mesh.materials.append(mat)
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.parent=parent;obj.location=xyz((x,0,z))
    obj['label_text']=value;obj['font_source']='Original5x7 block stencil, no external font asset'
    return paint(obj,'label',semantic)

def arrow(name,parent,mat,semantic,outbound):
    points=[(-.18,-1.1),(.18,-1.1),(.18,.25),(.52,.25),(0,1.15),(-.52,.25),(-.18,.25)]
    vertices=[xyz((x,y,z)) for y in (0,H) for x,z in points];n=len(points)
    # The floor polygon is clockwise as seen from above in Blender XY.
    faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=bpy.data.meshes.new(name+'_solid');mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.parent=parent;obj.location=xyz((0,0,3.8));mesh.materials.append(mat)
    if outbound:obj.rotation_euler.z=math.pi
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    obj['direction_local_runtime']=[0,0,-1 if outbound else 1]
    return paint(obj,'port_direction_arrow',semantic)

def build():
    spec=json.loads((ROOT/INPUTS[2]).read_text(encoding='utf8'));zones=json.loads((ROOT/INPUTS[4]).read_text(encoding='utf8'))['zones']
    root=group('floor_markings_root');root['role']='noncollidable_floor_wayfinding';root['reference_id']='R07';root['reference_context']='R07/R08'
    root['surface_paint']=True;root['collision_enabled']=False;root['engine_operation']=False;root['source_kind']='visual_fixture';root['paint_height_m']=H
    root['scope']='Surface coating and semantic wayfinding only; unchanged physical routing, floor, slots, stock and architecture. Not final scene composition.'
    white=material('V3_PAINT_warm_white','#F2EAD9',.9);tan=material('V3_PAINT_safety_tan','#DEB256',.9);ink=material('V3_PAINT_lettering','#50656A',.95)
    incoming=material('V3_PAINT_incoming','#8F6BB2',.9);outgoing=material('V3_PAINT_outgoing','#D28D4B',.9)
    for m in (white,tan,ink,incoming,outgoing):m.use_backface_culling=True
    tagged=[]
    for zone in zones:
        if zone['kind']=='circulation':continue
        ident=zone['zone_id'];node=group('zone__'+ident,root);node['zone_id']=ident;node['surface_paint']=True;node['collision_enabled']=False
        lo,hi=zone['floor_bounds_xz_m']['min'],zone['floor_bounds_xz_m']['max'];x0,z0=lo[0]+.22,lo[1]+.22;x1,z1=hi[0]-.22,hi[1]-.22
        points=[(x0,z0),(x1,z0),(x1,z1),(x0,z1)]
        for i,(a,b) in enumerate(zip(points,points[1:]+points[:1])):
            if zone['kind']=='staging':dashed('stage_boundary_'+str(i),a,b,.12,tan,node,ident)
            else:strip('zone_boundary_'+str(i),a,b,.12,white,node,ident)
        if zone['kind'] in ('storage','reserve'):label=ident.replace('_',' ')
        elif zone['kind']=='packing':label='PACK / SCAN'
        else:label=ident.removeprefix('STAGE_').replace('IN_','IN ').replace('OUT_','OUT ').replace('_',' ')
        width=x1-x0;size=min(.95,width/(max(4,len(label))*.9))
        text('zone_label',label,(x0+x1)/2,z0+max(.65,size*.7),size,ink,node,ident)
        anchor('anchor_marking_'+ident,((x0+x1)/2,0,(z0+z1)/2),node,'zone_floor_wayfinding')
        bpy.context.view_layer.update();zp,_=collect(node)
        actual_lo=[min(p['low'][i] for p in zp) for i in range(3)];actual_hi=[max(p['high'][i] for p in zp) for i in range(3)]
        assert actual_lo[0]>=lo[0]-2e-5 and actual_hi[0]<=hi[0]+2e-5 and actual_lo[2]>=lo[1]-2e-5 and actual_hi[2]<=hi[1]+2e-5,('zone paint escaped source bounds',ident)
        tagged.append(dict(zone_id=ident,label=label,bounds_xz_m=dict(min=lo,max=hi),actual_paint_bounds_m=dict(min=actual_lo,max=actual_hi)))
    routes=[]
    for ident in ('CLEAR_CENTRAL_SPINE','CLEAR_CROSS_W','CLEAR_CROSS_E'):
        zone=next(z for z in zones if z['zone_id']==ident);lo,hi=zone['floor_bounds_xz_m']['min'],zone['floor_bounds_xz_m']['max'];node=group('route__'+ident,root);node['source_zone_id']=ident;node['surface_paint']=True;node['collision_enabled']=False
        if ident=='CLEAR_CENTRAL_SPINE':a,b=((lo[0]+hi[0])/2,lo[1]+1),((lo[0]+hi[0])/2,hi[1]-1)
        else:a,b=(lo[0]+1,(lo[1]+hi[1])/2),(hi[0]-1,(lo[1]+hi[1])/2)
        dashed('circulation_guide',a,b,.10,white,node,ident,dash=2,gap=1.5);routes.append(dict(source_zone_id=ident,start=a,end=b,direction_rule='none; actual directed graph unchanged'))
    ports=[]
    for gate in spec['gates']:
        pid=gate['port_id'];node=group('port__'+pid,root,gate['position']);node.rotation_euler.z=gate['yaw_rad'];node['port_id']=pid;node['surface_paint']=True;node['collision_enabled']=False
        half=gate['clear_width_m']/2-.2
        for sign in (-1,1):dashed('port_side_'+str(sign),(sign*half,1),(sign*half,6),.15,tan,node,pid,dash=.75,gap=.5)
        dashed('port_threshold',(-half,1),(half,1),.15,tan,node,pid,dash=.6,gap=.4)
        outbound=pid.startswith('OUT_');obj=arrow('port_arrow',node,outgoing if outbound else incoming,pid,outbound)
        label=pid.replace('IN_','IN ').replace('OUT_','OUT ').replace('_',' ')
        size=min(.65,(2*half)/(len(label)*.9));text('port_label',label,0,6.7,size,ink,node,pid)
        anchor('anchor_marking_'+pid,(0,0,3.8),node,'port_direction_floor_marking')
        bpy.context.view_layer.update();direction=runtime_xyz(node.matrix_world.to_3x3()@xyz((0,0,-1 if outbound else 1)))
        local=[(runtime_xyz(v.co),v.co) for v in obj.data.vertices];tip_z=max(p[0][2] for p in local);tail_z=min(p[0][2] for p in local)
        tip=sum((p[1] for p in local if abs(p[0][2]-tip_z)<1e-7),Vector())/sum(abs(p[0][2]-tip_z)<1e-7 for p in local)
        tail=sum((p[1] for p in local if abs(p[0][2]-tail_z)<1e-7),Vector())/sum(abs(p[0][2]-tail_z)<1e-7 for p in local)
        actual_direction=runtime_xyz((obj.matrix_world@tip-obj.matrix_world@tail).normalized())
        assert max(abs(a-b) for a,b in zip(actual_direction,direction))<2e-5,('arrow mesh direction',pid)
        inverse=node.matrix_world.inverted();points=[runtime_xyz(inverse@o.matrix_world@v.co) for o in node.children_recursive if o.type=='MESH' for v in o.data.vertices]
        assert max(abs(v[0]) for v in points)<=gate['clear_width_m']/2+2e-5 and min(v[2] for v in points)>.5,('paint beyond declared port width',pid)
        ports.append(dict(port_id=pid,inbound=not outbound,arrow_world_direction=direction,actual_arrow_mesh_direction=actual_direction,gate_clear_width_m=gate['clear_width_m'],all_port_paint_inside_clear_width=True))
    root['zone_ids_json']=json.dumps([r['zone_id'] for r in tagged]);root['port_ids_json']=json.dumps([r['port_id'] for r in ports])
    return root,tagged,routes,ports

if __name__=='__main__':
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in INPUTS};OUT.mkdir(parents=True,exist_ok=True);reset();root,zones,routes,ports=build()
    parts,_=collect(root);lo=[min(p['low'][i] for p in parts) for i in range(3)];hi=[max(p['high'][i] for p in parts) for i in range(3)]
    assert lo[0]>=-2e-5 and hi[0]<=144+2e-5 and lo[2]>=-2e-5 and hi[2]<=72+2e-5
    assert abs(lo[1])<2e-7 and abs(hi[1]-H)<2e-7,(lo,hi)
    assert len(zones)==20 and len(ports)==6 and len(routes)==3
    assert all(o.get('surface_paint') and o.get('collision_enabled') is False for o in root.children_recursive if o.type=='MESH')
    stats=finish('floor-markings',root)
    bpy.ops.wm.read_factory_settings(use_empty=True);reset();fixture=group('environment_markings_fixture_root');fixture['role']='architectural_paint_QA_fixture';fixture['source_kind']='visual_fixture';fixture['engine_operation']=False;fixture['reference_id']='R07'
    shell=append_source('assets/v3/blender/environment-shell.blend','environment_shell_root',fixture)
    # This assembled inspection uses a quieter concrete tone so white paint
    # remains legible under the scene light. The accepted shell file stays intact.
    floor_tone=material('V3_Wayfinding_concrete','#AFB6AF',.95)
    for obj in shell.children_recursive:
        if obj.type=='MESH' and obj.get('shell_component_class')=='floor_support':
            for i,m in enumerate(obj.data.materials):
                if m and m.name.startswith('V3_Shell_floor'):obj.data.materials[i]=floor_tone
    append_source('assets/v3/blender/floor-markings.blend','floor_markings_root',fixture)
    assembly=finish('environment-markings-fixture',fixture)
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    report=dict(task_id='P09.4',source_hashes=hashes,reference_ids=['R07','R08'],zone_markings=zones,route_guides=routes,port_arrows=ports,paint_closed_positive_volume_parts=len(parts),paint_bounds_m=dict(min=lo,max=hi),paint_height_m=H,fixture_concrete_tone='#AFB6AF',collision_objects_added=0,source_shell_and_layout_unchanged=True,glb_sha256=stats['sha256'],fixture_sha256=assembly['sha256'],scope='Noncollidable surface wayfinding; no route, inventory, physical-floor or final scene-composition admission.')
    (OUT/'actual-floor-markings.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');(ROOT/'assets/v3/specs/floor-markings.geometry.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('FLOOR_MARKINGS_VERIFIED '+json.dumps(dict(zones=len(zones),routes=len(routes),ports=len(ports),closed_paint_parts=len(parts),physical_colliders_added=0)))
