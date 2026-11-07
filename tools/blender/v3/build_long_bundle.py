"""M10:24 real hollow C02 profiles, integral packaging and native rack pairing."""
import hashlib
import json
from pathlib import Path

import bmesh
import bpy

from v3_common import ROOT, anchor, box, finish, group, material, reset, runtime_xyz, xyz
from build_standard_carton import collect, empty_box
from build_long_rack import build as build_rack, transfer_gauge

EPS=2e-6
OUT=ROOT/'assets/v3/iterations/long-bundle/M10-01'
CATALOG=ROOT/'docs/v3/contract-proposals/cargo-catalog-v3.json'


def block(name,lo,hi,mat,parent,bevel=.001):
    return box(name,[(a+b)/2 for a,b in zip(lo,hi)],[b-a for a,b in zip(lo,hi)],mat,parent,bevel)


def tube_x(name,xs,ys,zs,wall,mats,parent,bevel=.001):
    y0,y1=ys;z0,z1=zs
    outer=[(y0,z0),(y1,z0),(y1,z1),(y0,z1)]
    inner=[(y0+wall,z0+wall),(y1-wall,z0+wall),(y1-wall,z1-wall),(y0+wall,z1-wall)]
    vertices=[xyz((x,y,z)) for x in xs for ring in (outer,inner) for y,z in ring]
    faces=[];indices=[]
    for i in range(4):
        j=(i+1)%4
        faces.extend(((i,j,j+8,i+8),(i+4,i+12,j+12,j+4),(i,i+4,j+4,j),(i+8,j+8,j+12,i+12)))
        indices.extend((0,1 if len(mats)>1 else 0,0,0))
    mesh=bpy.data.meshes.new(name+'__editable_hollow');mesh.from_pydata(vertices,[],faces);mesh.update()
    for mat in mats:mesh.materials.append(mat)
    for face,index in zip(mesh.polygons,indices):face.material_index=index
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free();mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.parent=parent
    mod=obj.modifiers.new('Small profile edge relief','BEVEL');mod.width=bevel;mod.segments=1;mod.harden_normals=True
    obj.modifiers.new('Weighted flat faces','WEIGHTED_NORMAL').keep_sharp=True
    return obj


def inputs():
    catalog=json.loads(CATALOG.read_text(encoding='utf-8'))
    record=next(v for v in catalog['records'] if v['archetype_id']=='LONG_BUNDLE')
    recipe=next(v for v in catalog['packing_recipes'] if v['archetype_id']=='LONG_BUNDLE')
    assert record['handling_unit']['dimensions_xyz_m']==[4.2,.52,.65]
    assert record['handling_unit']['gross_mass_kg']==200 and record['unit']['gross_mass_kg']==8
    assert record['handling_unit']['units_per_handling_unit']==len(recipe['unit_instances'])==24
    return record,recipe


def build():
    record,recipe=inputs();root=group('long-bundle')
    root['reference_id']='M10_REF';root['role']='handling_unit_template';root['archetype_id']='LONG_BUNDLE'
    root['units_per_handling_unit']=24;root['gross_mass_kg']=200.;root['HU_packaging_tare_kg']=8.
    root['prototype_contents_not_stock']=True;root['operational_admission']=False
    root['contents_semantics']='24 unchanged C02 unit templates inside one HU; not24new lots or stock records; detachable cradle excluded'
    root['source_catalog_sha256']=hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    root['content_envelopes_HU_min_frame_json']=json.dumps(recipe['unit_instances'])
    tan=material('V3_LONG_profiles_tan','#C99A60');dark=material('V3_LONG_packaging_charcoal','#293D46')
    wood=material('V3_LONG_dunnage','#AC7E48');inside=material('V3_LONG_profile_inner','#1C2C31')
    for unit in recipe['unit_instances']:
        lo=[unit['min_xyz_m'][i]-[2.1,0,.325][i] for i in range(3)]
        hi=[unit['max_xyz_m'][i]-[2.1,0,.325][i] for i in range(3)]
        obj=tube_x(f'content_profile_{unit["unit_ordinal"]:02d}',[lo[0],hi[0]],[lo[1],hi[1]],[lo[2],hi[2]],.006,[tan,inside],root,.0008)
        obj['content_unit_ordinal']=unit['unit_ordinal'];obj['prototype_contents_not_stock']=True
    # Two narrow continuous integral skids let the same HU rest on either
    # rackX±1.6/0 or separate cradleX±1.4, without changing its support origin.
    for side,z in (('front',.2),('rear',-.2)):
        block('integral_skid_'+side,[-2.04,0,z-.03],[2.04,.06,z+.03],dark,root,.002)
    for i,x in enumerate((-1.6,0,1.6)):
        block(f'base_dunnage_{i}',[x-.06,0,-.325],[x+.06,.098,.325],wood,root,.001)
        for level,y in enumerate((.178,.266,.354),1):
            block(f'layer_separator_{level}_{i}',[x-.06,y,-.26],[x+.06,y+.008,.26],wood,root,.0003)
    for side,xs in (('L',[-2.10,-2.0]),('R',[2.0,2.10])):
        tube_x('end_protection_'+side,xs,[.04,.52],[-.325,.325],.04,[dark],root,.003)
        x0,x1=(-2.03,-1.95) if side=='L' else (1.95,2.03)
        block('end_support_'+side,[x0,.06,-.285],[x1,.098,.285],wood,root,.0005)
        block('end_top_lining_'+side,[x0,.442,-.285],[x1,.48,.285],wood,root,.0005)
        for label,z0,z1 in (('front',.26,.285),('rear',-.285,-.26)):
            block('end_side_lining_'+side+'_'+label,[x0,.098,z0],[x1,.442,z1],wood,root,.0004)
    for side,x in (('L',-1.5),('R',1.5)):
        tube_x('retaining_band_'+side,[x-.025,x+.025],[.055,.465],[-.278,.278],.014,[dark],root,.001)
        block('top_band_pad_'+side,[x-.03,.442,-.264],[x+.03,.451,.264],wood,root,.0003)
    anchor('anchor_support_bottom',(0,0,0),root,'HU_bottom_support')
    anchor('anchor_centre_of_load',(0,.26,0),root,'declared_symmetric_load_centre')
    for i,x in enumerate((-1.6,0,1.6)):
        anchor(f'anchor_rack_support_{i}',(x,0,0),root,'three_arm_support')
    for side,x in (('L',-1.4),('R',1.4)):
        anchor('anchor_cradle_support_'+side,(x,0,0),root,'detachable_cradle_pad_support')
    return root


def verify(root):
    record,recipe=inputs();parts,bvh=collect(root);byname={p['name']:p for p in parts}
    low=[min(p['low'][i] for p in parts) for i in range(3)];high=[max(p['high'][i] for p in parts) for i in range(3)]
    assert max(abs(a-b) for a,b in zip(low+high,[-2.1,0,-.325,2.1,.52,.325]))<EPS
    profile_checks=[]
    for unit in recipe['unit_instances']:
        p=byname[f'content_profile_{unit["unit_ordinal"]:02d}']
        lo=[unit['min_xyz_m'][i]-[2.1,0,.325][i] for i in range(3)]
        hi=[unit['max_xyz_m'][i]-[2.1,0,.325][i] for i in range(3)]
        assert max(abs(a-b) for a,b in zip(p['low']+p['high'],lo+hi))<EPS
        centre=[(lo[i]+hi[i])/2 for i in range(3)]
        # A ray crosses the real4m hollow bore and both protective end frames.
        hit,_,_,_=bvh.ray_cast(xyz((-2.2,centre[1],centre[2])),xyz((1,0,0)),4.4)
        assert hit is None,('profile bore obstructed',unit['unit_ordinal'],runtime_xyz(hit) if hit else None)
        profile_checks.append({'unit_ordinal':unit['unit_ordinal'],'min':p['low'],'max':p['high'],'open_bore_through_actual_geometry':True})
    support_rays=[]
    for x in (-1.6,0,1.6,-1.4,1.4):
        for z in (-.2,.2):
            p,normal,_,_=bvh.ray_cast(xyz((x,-.01,z)),xyz((0,1,0)),.03)
            assert p is not None and abs(runtime_xyz(p)[1])<EPS
            support_rays.append([x,0,z])
    assert sum(n.startswith('content_profile_') for n in byname)==24
    assert all(all(abs(v-1)<EPS for v in obj.scale) for obj in [root]+list(root.children_recursive))
    return {'dimensions_m':[high[i]-low[i] for i in range(3)],'closed_positive_outward_parts':len(parts),
            'actual24_profile_envelopes':profile_checks,'profile_wall_m':.006,'actual_bottom_support_rays':support_rays,
            'gross_mass_kg':200,'contents_unit_gross_kg':8,'HU_packaging_tare_kg':8,'total_units':24,
            'canonical_catalog_sha256':hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
            'quantity_semantics':'One HU,24 prototype contents; no added SKU/lot/stock','cradle_excluded_from_HU':True,'operational_admission':False}


def fixture():
    reset();root=group('long-rack-loaded-fixture');root['role']='visual_QA_fixture'
    root['source_label']='One canonical LONG HU on native rack; separate C08 interface gauge below, not inventory or accepted attachment'
    rack=build_rack();rack.parent=root
    cargo=build();cargo.parent=root;cargo.location=xyz((0,.25,.225))
    gauge=transfer_gauge(root)
    bpy.context.view_layer.update()
    rackparts,rackbvh=collect(rack);cargoparts,cargobvh=collect(cargo)
    # The unchanged C09 front-aligned placement is tested against actual meshes.
    for p in cargoparts:
        empty_box(rackparts,p['low'],p['high'],('actual LONG vs rack',p['name']))
    contact_pairs=[]
    for x in (-1.6,0,1.6):
        for z in (-.2,.2):
            worldz=.225+z
            lower,_,_,_=rackbvh.ray_cast(xyz((x,.255,worldz)),xyz((0,-1,0)),.02)
            upper,_,_,_=cargobvh.ray_cast(xyz((x,.245,worldz)),xyz((0,1,0)),.02)
            assert lower is not None and upper is not None and abs(runtime_xyz(lower)[1]-.25)<EPS and abs(runtime_xyz(upper)[1]-.25)<EPS
            contact_pairs.append([x,.25,worldz])
    # Gauge is2cm disengaged below cargo; raise it2cm for actual pad contacts.
    gauge.location=xyz((0,.10,.225));bpy.context.view_layer.update();_,gaugebvh=collect(gauge)
    pad_contacts=[]
    for x in (-1.4,1.4):
        for z in (-.2,.2):
            worldz=.225+z
            lower,_,_,_=gaugebvh.ray_cast(xyz((x,.255,worldz)),xyz((0,-1,0)),.02)
            upper,_,_,_=cargobvh.ray_cast(xyz((x,.245,worldz)),xyz((0,1,0)),.02)
            assert lower is not None and upper is not None and abs(runtime_xyz(lower)[1]-.25)<EPS and abs(runtime_xyz(upper)[1]-.25)<EPS
            pad_contacts.append([x,.25,worldz])
    gauge.location=xyz((0,.08,.225));bpy.context.view_layer.update()
    return root,{'actual_rack_HU_zero_gap_contacts':contact_pairs,'actual_cradle_pad_HU_zero_gap_contacts':pad_contacts,
                 'HU_native_placement_bottom_xyz_m':[0,.25,.225],'HU_scale':[1,1,1],
                 'fixture_gauge_disengagement_gap_m':.02,'upper_LONG_reserve_retrieval_remains_blocked':True}


if __name__=='__main__':
    if not bpy.app.background:raise RuntimeError('Background Blender only')
    OUT.mkdir(parents=True,exist_ok=True);before=hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    reset();root=build();checks=verify(root);stats=finish('long-bundle',root)
    checks['glb_sha256']=stats['sha256'];checks['triangles']=stats['triangles']
    pair,paired=fixture();pair_stats=finish('long-rack-loaded-fixture',pair)
    assert before==hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    checks['native_pair']=paired;checks['fixture_sha256']=pair_stats['sha256']
    (OUT/'mesh-checks.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    (ROOT/'assets/v3/specs/long-bundle.geometry.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    print('M10_SOURCE_VERIFIED '+json.dumps({'profiles':24,'closed_parts':checks['closed_positive_outward_parts'],
           'rack_contacts':6,'cradle_contacts':4,'triangles':stats['triangles'],'catalog_unchanged':True}))
