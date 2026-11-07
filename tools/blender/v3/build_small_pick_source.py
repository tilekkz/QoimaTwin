"""P03.5.2 C02primary packages and already-prepared partial-case source scene."""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,anchor,finish,group,material,pivot,reset,runtime_xyz,xyz
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_long_rack import block
from build_picking_cart import connected
from build_sealed_parcel import append_source
from build_standard_carton import collect,empty_box
from build_picker_figure import physical_body

OUT=ROOT/'assets/v3/iterations/small-carton/P03.5.2';EPS=2e-6
C=Matrix(((1,0,0),(0,0,-1),(0,1,0)))
SOURCES=['assets/v3/blender/small-carton.blend','assets/v3/blender/rack-small.blend','assets/v3/blender/picking-cart.blend','assets/v3/blender/order-tote.blend','assets/v3/blender/worker-manual.blend','docs/v3/contract-proposals/cargo-catalog-v3.json']

def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True);reset()

def rotate(obj,angles):
    a,b,c=angles;m=Matrix.Rotation(a,3,'X')@Matrix.Rotation(b,3,'Y')@Matrix.Rotation(c,3,'Z')
    obj.rotation_mode='QUATERNION';obj.rotation_quaternion=(C@m@C.transposed()).to_quaternion()

def parent_at_rest(obj,parent):
    bpy.context.view_layer.update();world=obj.matrix_world.copy();obj.parent=parent;obj.matrix_world=world;bpy.context.view_layer.update()
    assert max(abs(obj.matrix_world[i][j]-world[i][j]) for i in range(4) for j in range(4))<EPS,('reparent moved source part',obj.name)

def make_unit():
    root=group('small-unit');root['role']='primary_package_prototype';root['archetype_id']='SMALL_CARTON'
    root['gross_mass_kg']=.035;root['dimensions_xyz_m']=[.06,.04,.04]
    root['is_handling_unit']=False;root['prototype_contents_not_stock']=True;root['reference_id']='M06.1_REF'
    root['source_label']='C02 individually packaged small accessory, not a scaled HU or a new lot'
    tan=material('V3_PRIMARY_SMALL_cardboard','#C99A60');tape=material('V3_PRIMARY_SMALL_tape','#DEC08A')
    paper=material('V3_PRIMARY_SMALL_paper','#E8E3D9');ink=material('V3_PRIMARY_SMALL_ink','#293D46')
    for m in (tan,tape,paper,ink):m.use_backface_culling=True
    block('unit_package_body',[-.03,0,-.0198],[.03,.0398,.0198],tan,root,.0006)
    block('unit_tape_top',[-.004,.0398,-.0198],[.004,.04,.0198],tape,root,.000015)
    block('unit_tape_front',[-.004,.026,.0198],[.004,.04,.02],tape,root,.000015)
    block('unit_tape_rear',[-.004,.026,-.02],[.004,.04,-.0198],tape,root,.000015)
    block('unit_label',[-.026,.023,.0198],[-.012,.032,.01995],paper,root,.000015)
    for i,(y,w) in enumerate([(.029,.009),(.026,.006)]):block('unit_ink_'+str(i),[-.024,y,.01995],[-.024+w,y+.0006,.01997],ink,root,.000003)
    anchor('anchor_primary_bottom',(0,0,0),root,'actual_primary_package_support')
    anchor('anchor_primary_centre',(0,.02,0),root,'primary_package_centre')
    parts,_=collect(root);lo=[min(p['low'][i] for p in parts) for i in range(3)];hi=[max(p['high'][i] for p in parts) for i in range(3)]
    assert max(abs(a-b) for a,b in zip(lo+hi,[-.03,0,-.02,.03,.04,.02]))<EPS
    links=connected(parts);stats=finish('small-unit',root)
    return {'closed_parts':len(parts),'bounds_m':{'min':lo,'max':hi},'connection_links':links,'glb_sha256':stats['sha256'],'gross_mass_kg':.035,'not_a_HU_or_stock_instance':True}

def make_case(catalog):
    root=group('small_case_open_partial_root');frame=group('case_stock_frame',root)
    root['role']='visual_partial_case';root['source_kind']='visual_fixture';root['engine_operation']=False
    root['reference_id']='M06.1_REF';root['operational_admission']=False;root['preserve_articulation']=True
    root['nominal_closed_HU_xyz_m']=[.32,.24,.24];root['full_HU_template_gross_mass_kg']=.94
    root['full_HU_template_unit_count']=24;root['fixture_remaining_primary_packages']=4;root['fixture_current_case_gross_mass_kg']=.24
    root['preparation_state']='Already opened partial case; preparation is outside this action. Open panels use separately checked handling bounds.'
    shell=append_source(SOURCES[0],'small-carton',frame);shell['role']='opened_packaging_component';shell['contains_inventory']=False
    originals={o.name:o for o in shell.children_recursive if o.type=='MESH'}
    raw={name:[tuple(v.co) for v in obj.data.vertices] for name,obj in originals.items()}
    cp,_=collect(shell);closed_bounds={'min':[min(p['low'][i] for p in cp) for i in range(3)],'max':[max(p['high'][i] for p in cp) for i in range(3)]}
    # Same closed source solids and colours; front-face culling reveals the
    # real3mm inward/outward wall faces without drawing opposite contact faces.
    copies={}
    for obj in originals.values():
        for i,m in enumerate(obj.data.materials):
            if m.name not in copies:copy=m.copy();copy.name=m.name+'_open_case';copy.use_backface_culling=True;copies[m.name]=copy
            obj.data.materials[i]=copies[m.name]
    for side,x,angle in [('left',-.16,math.pi/2),('right',.16,-math.pi/2)]:
        node=pivot('joint__case_major_'+side,(x,.2365,0),shell,'Z')
        parent_at_rest(originals['lid_major_'+side],node);rotate(node,(0,0,angle));node['prepared_angle_rad']=angle
    front=pivot('joint__case_front_display',(0,.2365,.118),shell,'X')
    for name,obj in originals.items():
        if name in ('shell_front','lid_under_front','tape_front','label_paper','arrow_baseline','up_arrow_left','up_arrow_right') or name.startswith('label_line_'):parent_at_rest(obj,front)
    rotate(front,(math.pi,0,0));front['prepared_angle_rad']=math.pi
    rear=pivot('joint__case_minor_rear',(0,.2365,-.1165),shell,'X');parent_at_rest(originals['lid_under_rear'],rear);rotate(rear,(-math.pi/2,0,0))
    # Real integral crease material bridges the tiny chamfered edge gaps.
    # These are cardboard folds in the prepared handling state, not hardware
    # or a change to the original closed-HU body mesh coordinates.
    foldmat=originals['shell_bottom'].data.materials[0]
    for side,x in [('left',-.16),('right',.16)]:block('integral_open_crease_'+side,[x-.0005,.2355,-.115],[x+.0005,.2375,.115],foldmat,shell,.00005)
    for side,z in [('front',.1165),('rear',-.1165)]:block('integral_open_crease_'+side,[-.1605,.2355,z-.0005],[.1605,.2375,z+.0005],foldmat,shell,.00005)
    peel=group('peeled_tape_piece',root);top=originals['tape_top'];world=top.matrix_world.copy();top.parent=peel;top.matrix_world=Matrix.Translation(xyz((0,-.2395,-.57)))@world
    peel['role']='pre_existing_packaging_piece_not_stock';peel['support_role']='rear_structural_deck_not_an_address'
    bpy.context.view_layer.update();assert all(raw[n]==[tuple(v.co) for v in o.data.vertices] for n,o in originals.items())
    recipe=next(p for p in catalog['packing_recipes'] if p['archetype_id']=='SMALL_CARTON');selected=[];unit_nodes=[]
    packaging=group('case_integral_supports',frame);padmat=material('V3_CASE_localized_cardboard_support','#A97C45');padmat.use_backface_culling=True;shared_unit_materials={}
    for item in recipe['unit_instances']:
        lo=[a-b for a,b in zip(item['min_xyz_m'],[.16,0,.12])];hi=[a-b for a,b in zip(item['max_xyz_m'],[.16,0,.12])]
        if lo[0]<-.001 or abs((lo[2]+hi[2])/2)>1e-6:continue
        ident='primary_unit__'+str(item['unit_ordinal']).zfill(2)
        node=append_source('assets/v3/blender/small-unit.blend','small-unit',frame,((lo[0]+hi[0])/2,lo[1],(lo[2]+hi[2])/2))
        node.name=ident;node['role']='visual_primary_package_instance';node['unit_ordinal']=item['unit_ordinal'];node['not_a_handling_unit']=True
        node['is_pick_target']=lo[1]>.12
        for child in node.children_recursive:
            child.name=ident+'__'+child.name.split('.')[0]
            if child.type=='MESH':
                for i,m in enumerate(child.data.materials):
                    key=m.name.split('.')[0]
                    if key not in shared_unit_materials:shared_unit_materials[key]=m
                    child.data.materials[i]=shared_unit_materials[key]
        unit_nodes.append(node);selected.append({'id':ident,'unit_ordinal':item['unit_ordinal'],'min_case_m':lo,'max_case_m':hi,'pick_target':lo[1]>.12})
        if lo[1]<.1:
            # Folded3mm U-riser: real void below the support face, not a solid
            # block that could be mistaken for extra inventory or a dense slab.
            for side,a,b in [('L',lo[0],lo[0]+.003),('R',hi[0]-.003,hi[0])]:block('integral_bottom_leg_'+side+'_'+ident,[a,.003,lo[2]],[b,lo[1]-.003,hi[2]],padmat,packaging,.00015)
            block('integral_bottom_bridge_'+ident,[lo[0],lo[1]-.003,lo[2]],[hi[0],lo[1],hi[2]],padmat,packaging,.00015)
        else:block('integral_separator_'+ident,[lo[0],lo[1]-.005,lo[2]],[hi[0],lo[1],hi[2]],padmat,packaging,.0001)
    assert len(selected)==4 and sum(p['pick_target'] for p in selected)==2
    bpy.context.view_layer.update();parts,union=collect(root);pp,_=collect(packaging)
    supports=[]
    for node,item in zip(unit_nodes,selected):
        up,ubvh=collect(node);x=(item['min_case_m'][0]+item['max_case_m'][0])/2;z=0;y=item['min_case_m'][1]
        point=xyz((x,y,z));unit_faces=[];pack_faces=[]
        for p in up:
            h,n,_,dist=p['bvh'].find_nearest(point)
            if dist<EPS and n.dot(xyz((0,-1,0)))>.9:unit_faces.append(p['name'])
        for p in pp:
            h,n,_,dist=p['bvh'].find_nearest(point)
            if dist<EPS and n.dot(xyz((0,1,0)))>.9:pack_faces.append(p['name'])
        assert unit_faces and pack_faces,(node.name,y,unit_faces,pack_faces)
        supports.append({'unit':node.name,'point':[x,y,z],'actual_unit_bottom_faces':unit_faces,'actual_packaging_top_faces':pack_faces,'method':'coincident nearest native faces with opposed normals'})
    structure,_=collect(shell);links=connected(structure)
    packaging_chain=[]
    riser_bridge_contacts=[]
    for node,item in zip(unit_nodes,selected):
        xs=[item['min_case_m'][0]+.0015,item['max_case_m'][0]-.0015] if not item['pick_target'] else [(item['min_case_m'][0]+item['max_case_m'][0])/2]
        y=.003 if not item['pick_target'] else item['min_case_m'][1]-.005
        for x in xs:
            expected=xyz((x,y,0));below=[];above=[]
            for p in pp:
                hit,normal,_,distance=p['bvh'].find_nearest(expected)
                if distance<EPS and normal.dot(xyz((0,-1,0)))>.9:above.append(p['name'])
            candidates=structure if not item['pick_target'] else [p for other in unit_nodes if other['unit_ordinal']!=node['unit_ordinal'] for p in collect(other)[0]]
            for p in candidates:
                hit,normal,_,distance=p['bvh'].find_nearest(expected)
                if distance<EPS and normal.dot(xyz((0,1,0)))>.9:below.append(p['name'])
            assert above and below,('unsupported packaging',node.name,y,above,below)
            packaging_chain.append({'point':[x,y,0],'actual_packaging_bottom':above,'actual_support_top':below})
            if not item['pick_target']:
                bridge_point=xyz((x,item['min_case_m'][1]-.003,0));bottom=[];top=[]
                for p in pp:
                    hit,normal,_,distance=p['bvh'].find_nearest(bridge_point)
                    if distance<EPS and normal.dot(xyz((0,-1,0)))>.9:bottom.append(p['name'])
                    if distance<EPS and normal.dot(xyz((0,1,0)))>.9:top.append(p['name'])
                assert bottom and top,('riser bridge not on real legs',node.name,x,bottom,top)
                riser_bridge_contacts.append({'point':runtime_xyz(bridge_point),'bridge_bottom':bottom,'leg_top':top})
    for item in selected:
        if item['pick_target']:continue
        empty_box(pp,[item['min_case_m'][0]+.003,.003,item['min_case_m'][2]],[item['max_case_m'][0]-.003,item['min_case_m'][1]-.003,item['max_case_m'][2]],'real hollow3mm cardboard U-riser')
    # All original case solids are retained, including the peeled tape.
    assert len(originals)==19;assert all(raw[n]==[tuple(v.co) for v in o.data.vertices] for n,o in originals.items())
    root['partial_units_json']=json.dumps(selected);root['pick_target_count']=2
    stats=finish('small-case-open-partial',root)
    return {'closed_source_nominal_bounds_m':closed_bounds,'original_case_mesh_count':19,'original_raw_meshes_unchanged':True,'integral_open_crease_parts':4,'shell_connection_links':links,'closed_parts_in_open_model':len(parts),'primary_units':selected,'actual_unit_packaging_supports':supports,'actual_packaging_support_chain_contacts':packaging_chain,'actual_U_riser_bridge_leg_contacts':riser_bridge_contacts,'U_riser_wall_thickness_m':.003,'shared_primary_unit_materials':len(shared_unit_materials),'prepared_front_hinge_y_m':.2365,'peeled_tape_bottom_y_m':min(p['low'][1] for p in parts if p['name']=='tape_top'),'open_handling_bounds_m':stats['bounds_runtime'],'glb_sha256':stats['sha256'],'unit_count':4,'pick_target_count':2,'is_visual_fixture_not_inventory':True}

def make_scene(case_checks):
    root=group('picker_pick_source_fixture_root');root['role']='visual_QA_fixture';root['source_kind']='visual_fixture';root['engine_operation']=False;root['reference_ids_json']=json.dumps(['R13.1','M06.1_REF','R11']);root['source_label']='Prepared partial case4primary packages,2later targets, one cart/empty tote. No warehouse ledger or employee baked.'
    rack=append_source(SOURCES[1],'rack-small__MODULE',root)
    case=append_source('assets/v3/blender/small-case-open-partial.blend','small_case_open_partial_root',root,(.88,1,.32))
    cart=append_source(SOURCES[2],'picking-cart',root,(1.75,0,-.10));tote=append_source(SOURCES[3],'order-tote',cart,(0,.62,.12))
    rp,rbvh=collect(rack);hp,hbvh=collect(case);cp,cbvh=collect(cart);tp,tbvh=collect(tote)
    tote_names={p['name'] for p in tp};cp=[p for p in cp if p['name'] not in tote_names]
    slot=next(o for o in rack.children_recursive if o.name=='anchor_bin_L2_B5');bounds=json.loads(slot['usable_bounds_module_json'])
    closed_lo=[.72,1,.20];closed_hi=[1.04,1.24,.44]
    assert all(closed_lo[i]>=bounds['min'][i]-EPS and closed_hi[i]<=bounds['max'][i]+EPS for i in range(3)),('closed source envelope not in actual slot',bounds)
    for p in hp:empty_box(rp,p['low'],p['high'],('actual open case/primary packaging versus native rack',p['name']))
    rack_support=[]
    for label,x,y,z in [('case',.88,1,.32),('peeled_tape',.88,1,-.25)]:
        a,_,_,_=rbvh.ray_cast(xyz((x,y+.001,z)),xyz((0,-1,0)),.01)
        b,_,_,_=hbvh.ray_cast(xyz((x,y-.001,z)),xyz((0,1,0)),.01)
        assert a is not None and b is not None and abs(runtime_xyz(a)[1]-y)<EPS and abs(runtime_xyz(b)[1]-y)<EPS,(label,runtime_xyz(a) if a else None,runtime_xyz(b) if b else None)
        rack_support.append({'part':label,'point':[x,y,z]})
    for p in tp:empty_box(cp,p['low'],p['high'],('unchanged native tote versus cart',p['name']))
    tote_support=[]
    for x in (1.55,1.95):
        for z in (-.10,.14):
            # Tote is shifted+.12along the upper tray; actual rib centres move
            # with it and still rest on the real wooden deck.
            a,_,_,_=tbvh.ray_cast(xyz((x,.615,z)),xyz((0,1,0)),.02)
            hits=[p['bvh'].ray_cast(xyz((x,.625,z)),xyz((0,-1,0)),.02)[0] for p in cp]
            assert a is not None and abs(runtime_xyz(a)[1]-.62)<EPS and any(h is not None and abs(runtime_xyz(h)[1]-.62)<EPS for h in hits)
            tote_support.append([x,.62,z])
    # Check the actual neutral employee working envelope before exporting a
    # source-only scene. A former cartZ+.30 put its rim through the idle left
    # mitten. Retain the actual failed pairs and prove the moved cart is clear.
    worker=append_source(SOURCES[4],'worker_base_root',None,(1.20,0,.74));rotate(worker,(0,math.pi,0));bpy.context.view_layer.update();wp,_=physical_body(worker)
    old=[];cart.location=xyz((1.75,0,.30));old_parts,_=collect(cart)
    for w in wp:
        for p in old_parts:
            if any(w['high'][i]<=p['low'][i]+EPS or w['low'][i]>=p['high'][i]-EPS for i in range(3)):continue
            if w['bvh'].overlap(p['bvh']):old.append([w['name'],p['name']])
    assert old,'Expected old idle-mitten/cart interference was not reproduced'
    cart.location=xyz((1.75,0,-.10));new_parts,_=collect(cart)
    for w in wp:empty_box(rp+hp+new_parts,w['low'],w['high'],('actual initial employee versus native source/cart',w['name']))
    worker_parts=len(wp)
    for obj in list(worker.children_recursive)+[worker]:bpy.data.objects.remove(obj,do_unlink=True)
    stats=finish('picker-pick-source-fixture',root)
    return {'native_closed_slot_bounds':bounds,'closed_case_inside_slot':True,'actual_rack_case_and_tape_supports':rack_support,'actual_tote_rib_supports':tote_support,'rack_cart_lateral_gap_m':.19,'case_position_m':[.88,1,.32],'cart_position_m':[1.75,0,-.1],'tote_world_position_m':[1.75,.62,.02],'old_cart_Z_plus30cm_actual_intersections':old,'initial_native_worker_closed_parts_checked':worker_parts,'initial_worker_clear_of_source_and_cart':True,'primary_contents':4,'pick_targets':2,'employee_instances':0,'glb_sha256':stats['sha256']}

if __name__=='__main__':
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES};catalog=json.loads((ROOT/SOURCES[-1]).read_text(encoding='utf8'));OUT.mkdir(parents=True,exist_ok=True)
    fresh();unit=make_unit();fresh();case=make_case(catalog);fresh();scene=make_scene(case)
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    report={'task_id':'P03.5.2','source_hashes':hashes,'primary_unit':unit,'prepared_partial_case':case,'native_scene':scene,'original_files_unchanged':True,'scope':'Prepared source geometry only;4primary contents are visual fixture quantities, not extra HUs or an engine stock run. Actual reaching/picking/release remains P03.5.3.'}
    (OUT/'actual-small-pick-source-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    (ROOT/'assets/v3/specs/small-pick-source.geometry.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('P0352_SOURCE_VERIFIED '+json.dumps({'primary_package_parts':unit['closed_parts'],'case_parts':case['closed_parts_in_open_model'],'primary_units':4,'pick_targets':2,'rack_supports':2,'tote_supports':4}))
