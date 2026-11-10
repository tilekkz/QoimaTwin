"""P04 isolated seam-press workcell, accepted source templates stay immutable."""
import hashlib,json,sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from v3_common import ROOT,reset,group,finish,xyz,runtime_xyz
from build_sealed_parcel import append_source
from build_standard_carton import collect

OUT=ROOT/'assets/v3/iterations/packer/P04.1'
SOURCES=['assets/v3/blender/'+n+'.blend' for n in ['packing-station','conveyor-straight','sealed-parcel','worker-manual']]

def workcell():
    root=group('packer_workcell_root');root['role']='visual_QA_fixture';root['source_kind']='visual_fixture';root['engine_operation']=False
    root['reference_id']='R04';root['contains_worker']=False
    root['scope']='Final seam press/inspection on one existing closed taped parcel. No folding, content packing, label creation, transport or engine result.'
    station=append_source(SOURCES[0],'packing-station__MODULE',root)
    belts=[]
    for i,z in enumerate([-1.2,-.2]):
        # Name suffix is scoped to this source append; avoid finding the first copy.
        existing=set(bpy.data.objects)
        with bpy.data.libraries.load(str(ROOT/SOURCES[1]),link=False) as (data,loaded):loaded.objects=list(data.objects)
        for o in loaded.objects:
            if o is not None and o.name not in bpy.context.scene.objects:bpy.context.collection.objects.link(o)
        belt=next(o for o in loaded.objects if o and o not in existing and o.get('asset_id')=='conveyor-straight')
        belt.parent=root;belt.location=xyz((0,0,z));belt.name='packer_spur_'+str(i);belts.append(belt)
    parcel=append_source(SOURCES[2],'sealed-parcel',root,(0,.92,.1));parcel.name='packer_existing_parcel'
    parcel['fixture_package_id']='v3:fixture:package:SMALL001';parcel['fixture_contents_HU_ref']='v3:fixture:HU:SMALL001'
    root['package_identity_policy']='One existing package ref; no stock/SKU/lot/quantity creation.'
    return root,station,belts,parcel

if __name__=='__main__':
    assert bpy.app.background
    frozen={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}
    reset();root,station,belts,parcel=workcell();sp,_=collect(station);bp=[collect(b)[0] for b in belts];pp,_=collect(parcel)
    lo=[min(p['low'][i] for p in pp) for i in range(3)];hi=[max(p['high'][i] for p in pp) for i in range(3)]
    assert max(abs(a-b) for a,b in zip(lo+hi,[-.18,.92,-.04,.18,1.2,.24]))<2e-6
    contacts=[]
    for x in [-.15,0,.15]:
        for z in [-.02,.1,.22]:
            hits=[p['bvh'].ray_cast(xyz((x,.93,z)),xyz((0,-1,0)),.02)[0] for ps in bp for p in ps]
            assert any(h is not None and abs(runtime_xyz(h)[1]-.92)<2e-6 for h in hits)
            contacts.append([x,.92,z])
    OUT.mkdir(parents=True,exist_ok=True);stats=finish('packer-workcell-fixture',root)
    assert frozen=={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}
    report=dict(task_id='P04.1',source_hashes=frozen,parcel_bounds_m=dict(min=lo,max=hi),actual_package_deck_supports=contacts,scale=1,package_instances=1,worker_instances=0,glb_sha256=stats['sha256'],scope='Source workcell only; worker contact/action is a subsequent gate.')
    (OUT/'actual-workcell.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('PACKER_WORKCELL_VERIFIED '+json.dumps({'supports':len(contacts),'package_instances':1,'triangles':stats['triangles']}))
