"""M11 sealed faceted primary drum, integral support and native fork pairing."""
import hashlib
import json
import math
from pathlib import Path

import bmesh
import bpy

from v3_common import ROOT, anchor, box, cylinder, finish, group, material, reset, runtime_xyz, xyz
from build_standard_carton import collect, empty_box
from build_sealed_parcel import append_source

OUT=ROOT/'assets/v3/iterations/drum/M11-01'
EPS=2e-6
CATALOG=ROOT/'docs/v3/contract-proposals/cargo-catalog-v3.json'


def ring(name,y0,y1,outer,inner,mat,parent,bevel=.001):
    count=16
    verts=[xyz((r*math.cos(2*math.pi*i/count),y,r*math.sin(2*math.pi*i/count)))
           for y in (y0,y1) for r in (outer,inner) for i in range(count)]
    faces=[]
    for i in range(count):
        j=(i+1)%count
        faces.extend(((i,j,j+32,i+32),(i+16,i+48,j+48,j+16),
                      (i,i+16,j+16,j),(i+32,j+32,j+48,i+48)))
    mesh=bpy.data.meshes.new(name+'__closed_ring');mesh.from_pydata(verts,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free();mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.parent=parent;mesh.materials.append(mat)
    if bevel:
        mod=obj.modifiers.new('Small formed rim bevel','BEVEL');mod.width=bevel;mod.segments=1;mod.harden_normals=True
        obj.modifiers.new('Weighted flat ring faces','WEIGHTED_NORMAL').keep_sharp=True
    return obj


def build():
    c=json.loads(CATALOG.read_text(encoding='utf-8'));record=next(r for r in c['records'] if r['archetype_id']=='DRUM')
    recipe=next(r for r in c['packing_recipes'] if r['archetype_id']=='DRUM')
    assert record['handling_unit']['dimensions_xyz_m']==[.68,.95,.68] and record['handling_unit']['gross_mass_kg']==180
    assert record['unit']['dimensions_xyz_m']==[.6,.82,.6] and len(recipe['unit_instances'])==1
    root=group('drum');root['reference_id']='M11_REF';root['role']='handling_unit_template';root['archetype_id']='DRUM'
    root['gross_mass_kg']=180.;root['unit_gross_kg']=172.;root['HU_packaging_tare_kg']=8.;root['units_per_handling_unit']=1
    root['prototype_contents_not_stock']=True;root['operational_admission']=False
    root['symbolic_liquid_json']=json.dumps(recipe['symbolic_liquid']);root['liquid_volume_is_not_unit_count']=True
    root['source_catalog_sha256']=hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    tan=material('V3_DRUM_carrier_tan','#C99A60');teal=material('V3_DRUM_shell','#2E7376')
    rim=material('V3_DRUM_rims','#2A6468');lid=material('V3_DRUM_lid','#327B7C')
    for i,x in enumerate((-.24,0,.24)):
        box(f'carrier_runner_{i}',(x,.0375,0),(.14,.075,.68),tan,root,.003)
    box('carrier_deck',(0,.08,0),(.68,.02,.68),tan,root,.002)
    unit=group('primary_drum_unit',root);unit['prototype_contents_not_stock']=True;unit['unit_ordinal']=1
    unit['gross_mass_kg']=172.;unit['declared_contents_mass_kg']=160.
    ring('formed_drum_wall',.105,.895,.287,.281,teal,unit,.0006)
    for i,(a,b) in enumerate(((.09,.13),(.31,.35),(.55,.59),(.875,.91))):
        ring(f'reinforcing_hoop_{i}',a,b,.30,.281,rim,unit,.0012)
    cylinder('sealed_bottom',(0,.100,0),.285,.020,teal,unit,vertices=16)
    cylinder('recessed_sealed_lid',(0,.884,0),.285,.008,lid,unit,vertices=16)
    cylinder('sealed_bung',(0,.899,0),.045,.022,tan,unit,vertices=12)
    # A separate protective cover belongs to HU packaging; the exact primary
    # unit remains.60x.82x.60 atY.09 and is not resized to the outerHU height.
    cylinder('bung_protective_cover',(0,.93,0),.065,.040,tan,root,vertices=12)
    anchor('anchor_support_bottom',(0,0,0),root,'HU_bottom_support')
    anchor('anchor_primary_unit_bottom',(0,.09,0),root,'primary_drum_bottom')
    for side,x in (('L',-.24),('R',.24)):
        anchor('anchor_fork_support_'+side,(x,0,0),root,'two_forks_below_unchanged_HU_base')
    return root,unit


def bounds(parts):
    return {'min':[min(p['low'][i] for p in parts) for i in range(3)],'max':[max(p['high'][i] for p in parts) for i in range(3)]}


def verify(root,unit):
    parts,bvh=collect(root);unitparts,_=collect(unit);outer=bounds(parts);primary=bounds(unitparts)
    assert max(abs(a-b) for a,b in zip(outer['min']+outer['max'],[-.34,0,-.34,.34,.95,.34]))<EPS
    assert max(abs(a-b) for a,b in zip(primary['min']+primary['max'],[-.30,.09,-.30,.30,.91,.30]))<EPS
    # Sealed thin wall, real inner free space and recessed lid, not a flat solid glyph.
    empty_box(unitparts,[-.195,.112,-.195],[.195,.875,.195],'actual interior of sealed primary drum')
    supports=[]
    for x in (-.24,.24):
        for z in (-.20,.20):
            p,normal,_,_=bvh.ray_cast(xyz((x,-.01,z)),xyz((0,1,0)),.025)
            assert p is not None and abs(runtime_xyz(p)[1])<EPS and normal.dot(xyz((0,-1,0)))>.999
            supports.append([x,0,z])
    assert all(all(abs(v-1)<EPS for v in o.scale) for o in [root]+list(root.children_recursive))
    return {'outer_bounds':outer,'primary_unit_bounds':primary,'closed_positive_outward_parts':len(parts),
            'primary_wall_gauge_m':.006,'actual_closed_drum_inner_box_clear':True,'actual_fork_support_rays':supports,
            'gross_mass_kg':180,'mass_components_kg':{'contents':160,'primary_packaging':12,'HU_packaging':8},
            'unit_count':1,'fill_volume_m3':.16,'declared_usable_capacity_m3':.18,'volume_is_not_count':True,
            'capacity_is_design_not_mesh_certification':True,'operational_admission':False}


def paired_fixture():
    reset();fixture=group('drum-forklift-fixture');fixture['role']='visual_QA_fixture'
    fixture['source_label']='One DRUM HU in declared C08 travel pose; fork contacts only, not complete action'
    forklift=append_source('assets/v3/blender/forklift-mast-stage.blend','forklift_root',fixture)
    for side,x in (('L',-.24),('R',.24)):
        obj=next(o for o in forklift.children_recursive if o.name=='joint__fork_'+side);obj.location=xyz((x,0,0))
    cargo,_=build();cargo.parent=fixture;cargo.location=xyz((0,.7,1.16));bpy.context.view_layer.update()
    forkparts,forkbvh=collect(forklift);cargoparts,cargobvh=collect(cargo)
    for p in cargoparts:empty_box(forkparts,p['low'],p['high'],('actual DRUM loaded clearance',p['name']))
    contacts=[]
    for x in (-.24,.24):
        for z in (1.01,1.31):
            lower,_,_,_=forkbvh.ray_cast(xyz((x,.705,z)),xyz((0,-1,0)),.02)
            upper,_,_,_=cargobvh.ray_cast(xyz((x,.695,z)),xyz((0,1,0)),.02)
            assert lower is not None and upper is not None and abs(runtime_xyz(lower)[1]-.7)<EPS and abs(runtime_xyz(upper)[1]-.7)<EPS
            contacts.append([x,.7,z])
    return fixture,{'travel_HU_bottom_xyz_m':[0,.7,1.16],'fork_halfspacing_m':.24,'actual_zero_gap_contacts':contacts,'actual_cargo_vehicle_meshes_clear':True,'full_action_accepted':False}


if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Background Blender only')
    OUT.mkdir(parents=True,exist_ok=True);frozen=hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    reset();root,unit=build();checks=verify(root,unit);stats=finish('drum',root)
    checks['glb_sha256']=stats['sha256'];checks['triangles']=stats['triangles']
    pair,contacts=paired_fixture();pair_stats=finish('drum-forklift-fixture',pair)
    assert frozen==hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    checks['paired_forklift']=contacts;checks['fixture_sha256']=pair_stats['sha256'];checks['canonical_catalog_sha256']=frozen
    (OUT/'mesh-checks.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    (ROOT/'assets/v3/specs/drum.geometry.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    print('M11_SOURCE_VERIFIED '+json.dumps({'closed_parts':checks['closed_positive_outward_parts'],'actual_primary_bounds':checks['primary_unit_bounds'],
            'fork_contacts':len(contacts['actual_zero_gap_contacts']),'triangles':stats['triangles'],'catalog_unchanged':True}))
