"""M12 protective crate: real frame/cavity/grip recesses and unchanged C02 unit."""
import hashlib
import json
from pathlib import Path

import bmesh
import bpy

from v3_common import ROOT, anchor, box, cylinder, finish, group, material, reset, runtime_xyz, xyz
from build_standard_carton import collect, empty_box
from build_sealed_parcel import append_source

OUT=ROOT/'assets/v3/iterations/fragile-crate/M12-01'
EPS=2e-6
CATALOG=ROOT/'docs/v3/contract-proposals/cargo-catalog-v3.json'


def block(name,lo,hi,mat,parent,bevel=.004):
    return box(name,[(a+b)/2 for a,b in zip(lo,hi)],[b-a for a,b in zip(lo,hi)],mat,parent,bevel)


def ink_shape(name,outline,parent,mat):
    n=len(outline);vertices=[xyz((x,y,z)) for z in (.395,.39515) for x,y in outline]
    faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=bpy.data.meshes.new(name+'__printed_film');mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free();mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.parent=parent;mesh.materials.append(mat)
    obj['cast_shadow']=False;return obj


def grip_panel(sign,parent,mat,ink,tan):
    side='R' if sign>0 else 'L'
    x0,x1=sorted((sign*.47,sign*.52))
    panel=block('side_panel_'+side,[x0,.16,-.345],[x1,.86,.345],mat,parent,0)
    panel.data.materials.append(ink)
    cutter=box('temporary_grip_cutter',(sign*.525,.61,0),(.07,.08,.20),mat,None,0)
    cutter.data.materials.append(ink)
    for face in cutter.data.polygons:face.material_index=1
    modifier=panel.modifiers.new('Backed30mm grip recess','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
    bpy.context.view_layer.objects.active=panel
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    bevel=panel.modifiers.new('Panel and recess edge relief','BEVEL');bevel.width=.0015;bevel.segments=1;bevel.harden_normals=True
    panel.modifiers.new('Weighted panel faces','WEIGHTED_NORMAL').keep_sharp=True
    a,b=sorted((sign*.518,sign*.532))
    for tag,lo,hi in [('lower',[a,.558,-.112],[b,.570,.112]),('upper',[a,.650,-.112],[b,.662,.112]),
                       ('front',[a,.570,.100],[b,.650,.112]),('rear',[a,.570,-.112],[b,.650,-.100])]:
        block('grip_trim_'+side+'_'+tag,lo,hi,tan,parent,.001)
    return panel


def hardware_recess(rail,front,mat):
    for x in (-.30,.30):
        zs=[.393,.44] if front else [-.44,-.390]
        cutter=block('temporary_hardware_pocket',[x-.045,.845,zs[0]],[x+.045,.930,zs[1]],mat,None,0)
        mod=rail.modifiers.new('Recessed hardware mounting pocket','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
        bpy.context.view_layer.objects.active=rail;bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter,do_unlink=True)
    bevel=rail.modifiers.new('Timber and mounting pocket relief','BEVEL');bevel.width=.003;bevel.segments=1;bevel.harden_normals=True
    rail.modifiers.new('Weighted timber faces','WEIGHTED_NORMAL').keep_sharp=True


def build():
    c=json.loads(CATALOG.read_text(encoding='utf-8'));record=next(r for r in c['records'] if r['archetype_id']=='FRAGILE_CRATE')
    recipe=next(r for r in c['packing_recipes'] if r['archetype_id']=='FRAGILE_CRATE')
    assert record['handling_unit']['dimensions_xyz_m']==[1.1,.95,.85] and record['handling_unit']['gross_mass_kg']==88
    assert record['unit']['dimensions_xyz_m']==[.9,.7,.65] and len(recipe['unit_instances'])==1
    root=group('fragile-crate');root['reference_id']='M12_REF';root['role']='handling_unit_template';root['archetype_id']='FRAGILE_CRATE'
    root['gross_mass_kg']=88.;root['unit_gross_kg']=73.;root['HU_packaging_tare_kg']=15.;root['units_per_handling_unit']=1
    root['prototype_contents_not_stock']=True;root['operational_admission']=False
    root['source_catalog_sha256']=hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    root['contents_semantics']='One primary-packaged instrument in a cushioned protective crate; no new SKU/lot/stock'
    shell=group('crate_shell',root)
    tan=material('V3_FRAGILE_frame','#C99A60');paper=material('V3_FRAGILE_panels','#E8E3D9')
    ink=material('V3_FRAGILE_hardware_ink','#293D46');foam=material('V3_FRAGILE_cushion','#567675')
    printing=material('V3_FRAGILE_print','#293D46')
    inner=material('V3_FRAGILE_primary_case','#3D6268')
    for i,x in enumerate((-.4,0,.4)):
        block(f'base_runner_{i}',[x-.08,0,-.425],[x+.08,.075,.425],tan,shell,.003)
    block('base_floor',[-.47,.07,-.345],[.47,.10,.345],tan,shell,.002)
    for ix,xs in enumerate(([-.55,-.47],[.47,.55])):
        for iz,zs in enumerate(([-.425,-.345],[.345,.425])):
            block(f'corner_post_{ix}_{iz}',[xs[0],.16,zs[0]],[xs[1],.86,zs[1]],tan,shell,.006)
    for level,ys in (('bottom',[.07,.16]),('top',[.86,.95])):
        for face,zs in (('front',[.345,.425]),('rear',[-.425,-.345])):
            rail=block(f'{level}_rail_{face}',[-.55,ys[0],zs[0]],[.55,ys[1],zs[1]],tan,shell,0 if level=='top' else .005)
            if level=='top':hardware_recess(rail,face=='front',tan)
        for side,xs in (('L',[-.55,-.47]),('R',[.47,.55])):
            block(f'{level}_rail_{side}',[xs[0],ys[0],-.345],[xs[1],ys[1],.345],tan,shell,.005)
    block('front_inset_panel',[-.47,.16,.345],[.47,.86,.395],paper,shell,.002)
    block('rear_inset_panel',[-.47,.16,-.395],[.47,.86,-.345],paper,shell,.002)
    grip_panel(-1,shell,paper,ink,tan);grip_panel(1,shell,paper,ink,tan)
    block('inset_lid',[-.47,.86,-.345],[.47,.925,.345],paper,shell,.003)
    # Hinges sit at the actual lid seam, correcting the schematic mid-panel
    # hinge placement in the rear art without changing shape or envelope.
    for side,x in (('L',-.30),('R',.30)):
        block('front_latch_mount_'+side,[x-.035,.855,.390],[x+.035,.915,.423],ink,shell,.003)
        block('front_latch_socket_'+side,[x-.025,.772,.392],[x+.025,.820,.411],ink,shell,.002)
        block('front_latch_lever_'+side,[x-.018,.785,.405],[x+.018,.885,.425],ink,shell,.002)
        cylinder('latch_pin_'+side,(x,.867,.413),.008,.078,ink,shell,axis='X',vertices=12)
        block('rear_hinge_leaf_'+side,[x-.043,.836,-.412],[x+.043,.923,-.388],ink,shell,.003)
        cylinder('rear_hinge_barrel_'+side,(x,.875,-.413),.012,.092,ink,shell,axis='X',vertices=12)
    # Physical thin print stays below the outer frame plane and casts no shadow.
    for cx in (-.18,.18):
        for label,lo,hi in [('left',[cx-.12,.38,.395],[cx-.116,.62,.39515]),('right',[cx+.116,.38,.395],[cx+.12,.62,.39515]),
                            ('lower',[cx-.116,.38,.395],[cx+.116,.384,.39515]),('upper',[cx-.116,.616,.395],[cx+.116,.62,.39515])]:
            obj=block('printed_border_'+str(cx)+'_'+label,lo,hi,printing,shell,0);obj['cast_shadow']=False
    bowl=[(-.050,.080),(.050,.080),(.048,.040),(.035,.005),(.008,-.012),(.008,-.075),(.045,-.080),
          (.045,-.090),(-.045,-.090),(-.045,-.080),(-.008,-.075),(-.008,-.012),(-.035,.005),(-.048,.040)]
    ink_shape('printed_fragile_glass',[(x-.18,y+.50) for x,y in bowl],shell,printing)
    arrow=[(-.010,0),(.010,0),(.010,.100),(.035,.100),(0,.145),(-.035,.100),(-.010,.100)]
    for i,x in enumerate((.135,.225)):
        ink_shape(f'printed_up_arrow_{i}',[(x+a,.435+b) for a,b in arrow],shell,printing)
    base=block('printed_arrow_baseline',[.09,.412,.395],[.27,.417,.39515],printing,shell,0);base['cast_shadow']=False
    for ix,x in enumerate((-.32,.32)):
        for iz,z in enumerate((-.23,.23)):
            block(f'cushion_pad_{ix}_{iz}',[x-.06,.10,z-.05],[x+.06,.13,z+.05],foam,root,.001)
    unit=group('primary_packaged_instrument',root);unit['unit_ordinal']=1;unit['prototype_contents_not_stock']=True;unit['gross_mass_kg']=73.
    block('primary_instrument_case',[-.45,.13,-.325],[.45,.83,.325],inner,unit,.012)
    anchor('anchor_support_bottom',(0,0,0),root,'HU_bottom_support')
    anchor('anchor_primary_unit_bottom',(0,.13,0),root,'cushioned_primary_support')
    for side,x in (('L',-.4),('R',.4)):
        anchor('anchor_fork_support_'+side,(x,0,0),root,'two_forks_below_unchanged_HU_base')
    return root,shell,unit


def bounds(parts):
    return {'min':[min(p['low'][i] for p in parts) for i in range(3)],'max':[max(p['high'][i] for p in parts) for i in range(3)]}


def verify(root,shell,unit):
    parts,bvh=collect(root);shellparts,shellbvh=collect(shell);unitparts,unitbvh=collect(unit)
    outer=bounds(parts);primary=bounds(unitparts)
    assert max(abs(a-b) for a,b in zip(outer['min']+outer['max'],[-.55,0,-.425,.55,.95,.425]))<EPS
    assert max(abs(a-b) for a,b in zip(primary['min']+primary['max'],[-.45,.13,-.325,.45,.83,.325]))<EPS
    empty_box(shellparts,[-.47,.10,-.345],[.47,.86,.345],'real shell inner clear box excluding declared cushioning')
    for p in unitparts:empty_box(shellparts,p['low'],p['high'],'unchanged C02 primary unit fit')
    grips=[]
    for sign in (-1,1):
        hit,_,_,_=shellbvh.ray_cast(xyz((sign*.60,.61,0)),xyz((-sign,0,0)),.20)
        assert hit is not None and abs(abs(runtime_xyz(hit)[0])-.49)<EPS
        grips.append({'side':sign,'actual_back_x_m':runtime_xyz(hit)[0],'recess_depth_m':.03,'backing_wall_m':.02})
    pads=[]
    for ix,x in enumerate((-.32,.32)):
        for iz,z in enumerate((-.23,.23)):
            pad=next(p for p in parts if p['name']==f'cushion_pad_{ix}_{iz}')
            lower,_,_,_=pad['bvh'].ray_cast(xyz((x,.135,z)),xyz((0,-1,0)),.02)
            upper,_,_,_=unitbvh.ray_cast(xyz((x,.125,z)),xyz((0,1,0)),.02)
            assert lower is not None and upper is not None and abs(runtime_xyz(lower)[1]-.13)<EPS and abs(runtime_xyz(upper)[1]-.13)<EPS
            pads.append([x,.13,z])
    supports=[]
    for x in (-.4,.4):
        for z in (-.20,.20):
            p,_,_,_=bvh.ray_cast(xyz((x,-.01,z)),xyz((0,1,0)),.025)
            assert p is not None and abs(runtime_xyz(p)[1])<EPS;supports.append([x,0,z])
    return {'outer_bounds':outer,'primary_unit_bounds':primary,'closed_positive_outward_parts':len(parts),
            'shell_inner_clear_box_m':[.94,.76,.69],'primary_clearances_m':{'X_each':.02,'Z_each':.02,'top':.03,'support_gap':0},
            'actual_backed_grips':grips,'actual_cushion_contacts':pads,'actual_fork_support_rays':supports,
            'gross_mass_kg':88,'mass_components_kg':{'primary_unit':73,'HU_packaging':15},'unit_count':1,
            'rear_hinges_at_actual_lid_seam':True,'operational_admission':False}


def paired_fixture():
    reset();root=group('fragile-forklift-fixture');root['role']='visual_QA_fixture'
    root['source_label']='One FRAGILE HU in declared C08 travel pose; native contacts, not complete action'
    forklift=append_source('assets/v3/blender/forklift-mast-stage.blend','forklift_root',root)
    cargo,_,_=build();cargo.parent=root;cargo.location=xyz((0,.7,1.075));bpy.context.view_layer.update()
    forkparts,forkbvh=collect(forklift);cargoparts,cargobvh=collect(cargo)
    for p in cargoparts:empty_box(forkparts,p['low'],p['high'],('FRAGILE vehicle clearance',p['name']))
    contacts=[]
    for x in (-.4,.4):
        for z in (.875,1.275):
            lower,_,_,_=forkbvh.ray_cast(xyz((x,.705,z)),xyz((0,-1,0)),.02)
            upper,_,_,_=cargobvh.ray_cast(xyz((x,.695,z)),xyz((0,1,0)),.02)
            assert lower is not None and upper is not None and abs(runtime_xyz(lower)[1]-.7)<EPS and abs(runtime_xyz(upper)[1]-.7)<EPS
            contacts.append([x,.7,z])
    return root,{'travel_HU_bottom_xyz_m':[0,.7,1.075],'fork_halfspacing_m':.4,'actual_zero_gap_contacts':contacts,'actual_cargo_vehicle_meshes_clear':True,'full_action_accepted':False}


if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Background Blender only')
    OUT.mkdir(parents=True,exist_ok=True);frozen=hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    reset();root,shell,unit=build();checks=verify(root,shell,unit);stats=finish('fragile-crate',root)
    checks['glb_sha256']=stats['sha256'];checks['triangles']=stats['triangles']
    pair,paired=paired_fixture();pair_stats=finish('fragile-forklift-fixture',pair)
    assert frozen==hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    checks['paired_forklift']=paired;checks['fixture_sha256']=pair_stats['sha256'];checks['canonical_catalog_sha256']=frozen
    (OUT/'mesh-checks.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    (ROOT/'assets/v3/specs/fragile-crate.geometry.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    print('M12_SOURCE_VERIFIED '+json.dumps({'closed_parts':checks['closed_positive_outward_parts'],'actual_grips':2,'cushion_contacts':4,'fork_contacts':4,'triangles':stats['triangles'],'catalog_unchanged':True}))
