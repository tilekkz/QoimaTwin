"""Refresh only the owned repair evidence; retain previous accepted history."""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
HERE = Path(__file__).resolve().parent
REL = HERE.relative_to(ROOT).as_posix()

def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))

def save(path, data):
    (ROOT / path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def fingerprint(path):
    data = (ROOT / path).read_bytes()
    return {'path': path, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

def archive(path, target):
    dest = HERE / 'before' / target
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(ROOT / path, dest)

now = datetime.now(timezone.utc).isoformat()
qa = load(f'{REL}/actual-repair-checks.json')
glb_reports = {r['asset_id']: r for r in load(f'{REL}/actual-repair-glb-checks.json')['reports']}
views = ['front', 'side', 'rear', 'three-quarter']
for view in views:
    dst = f'assets/v3/previews/forklift-cab-stage/{view}.png'
    archive(dst, f'cab-previews/{view}.png')
    shutil.copy2(HERE / 'after' / f'{view}.png', ROOT / dst)
shutil.copy2(HERE / 'after' / 'render-provenance.json', ROOT / 'assets/v3/previews/forklift-cab-stage/render-provenance.json')

repair = {
    'recorded_at': now,
    'reason': 'User observed detached-looking front wheels; root authorized bounded structural repair before mast.',
    'changes': ['closed cast central ramp', 'larger axle saddle and 90mm-radius shaft', 'two bearing collars', 'low crossmember and two connected tapered outboard frame cheeks'],
    'fixed_hull_xyz_m': [1.2, 2.1, 3.0],
    'tyres_pivots_cab_driver_C08_unchanged': True,
    'before_stub_m': .084,
    'after_stub_m': qa['front_exposed_stub_m'],
    'actual_source_checks': f'{REL}/actual-repair-checks.json',
    'actual_GLTFLoader_checks': f'{REL}/actual-repair-glb-checks.json',
    'source_closed_positive_parts': 45,
    'source_interior_contact_witnesses': 52,
    'old_parts_unchanged_except_three_authorized_frame_parts': 37,
    'new_body_cab_identical_parts': 30,
    'actual_tyre_triangle_intersections': 0,
    'continuous_declared_interface_clearances': qa['continuous_interface_clearances'],
    'clearance_scope': 'Actual fixed repair solids against frozen declared moving interfaces; production mast/actions are not yet built or accepted.',
    'negative_cases': qa['negative_cases'],
    'actual_source_images_opened': [f'{REL}/before/wheel-close.png'] + [f'{REL}/after/{v}.png' for v in views] + [f'{REL}/after/wheel-close.png', f'{REL}/paired-after/three-quarter.png'],
    'visual_findings': 'Substantial centre housing and side frame connect wheel assembly to body. No detached axle reading in side/quarter. Four grounded tyres, unchanged cab/driver fit. No new visible defect in the seven opened PNGs.',
    'mechanical_closeup_visibility': 'Cab/control meshes hidden only in the identical before/after wheel-close camera; all full views and paired-quarter retain complete source hierarchy.',
    'previous_previews': 'Body-only four views and three older paired views are historical pre-repair images; current four cab views include the complete repaired body. Current driver witness is paired-after/three-quarter.png.',
    'no_whole_route_or_unchanged_worker_pipeline_repeat': True,
    'full_forklift_accepted': False,
}

for stage, asset_id in [('M14.2', 'forklift-body-wheels'), ('M14.3', 'forklift-cab-stage')]:
    evidence_path = f'docs/adaptive-v3/evidence/{stage}.json'
    doc_path = f'docs/adaptive-v3/specs/{stage}.md'
    spec_path = f'assets/v3/specs/{asset_id}.json'
    for path in [evidence_path, doc_path, spec_path]:
        archive(path, f'{stage}/{Path(path).name}')
    stats = load(f'assets/v3/blender/{asset_id}.stats.json')
    runtime = glb_reports[asset_id]
    spec = load(spec_path)
    spec['status'] = 'VERIFY'
    spec['front_attachment_repair'] = repair
    if stage == 'M14.2':
        names = {c['name'] for c in stats['components']}
        spec['actual_source_parts'] = [{'name': c['name'], 'parent': c['parent'], 'bounds': c['bounds_runtime']} for c in stats['components']]
        spec['actual_source_bounds'] = stats['bounds_runtime']
        spec['actual_runtime_bounds'] = runtime['bounds']
        spec['actual_contact_tree_edges'] = [c for c in qa['actual_contacts'] if set(c['parts']) <= names]
        spec['metrics'] = {'source_meshes': 30, 'runtime_meshes': runtime['meshes'], 'nodes': runtime['nodes'], 'triangles': runtime['triangles'], 'vertices_exported': runtime['vertices'], 'materials': runtime['materials'], 'bytes': runtime['bytes'], 'glb_sha256': runtime['sha256']}
        spec['shape_decisions'].append('User repair: cast central ramp, substantial front housing/collars and outboard cheek frame; 9mm exposed shaft, original hull/tyres retained.')
    else:
        body = fingerprint('assets/v3/blender/forklift-body-wheels.blend')
        spec['accepted_body_source_sha256'] = body['sha256']
        spec['accepted_body_glb_sha256'] = glb_reports['forklift-body-wheels']['sha256']
        spec['accepted_body_revision_state'] = 'Updated body repair under root review; previous acceptance archived.'
        spec['actual'].update(source_meshes=45, closed_positive_vehicle_parts=45, contact_witnesses=52, unchanged_body_parts=30, source_sha256=qa['source_sha256'])
        spec['actual']['GLB'].update(sha256=runtime['sha256'], bytes=runtime['bytes'], triangles=runtime['triangles'], vertices=runtime['vertices'], nodeCount=runtime['nodes'], meshes=runtime['meshes'], bounds=runtime['bounds'], maxNormalError=runtime['maxNormalError'], maxBatchBoundError=runtime['maxBatchBoundError'])
    save(spec_path, spec)
    evidence = {
        'task_id': stage, 'owner': 'people_packing', 'status': 'VERIFY', 'recorded_at': now,
        'scope': 'Bounded user-requested front attachment repair; body/cab stages only, no mast/actions.',
        'previous_root_acceptance': f'{REL}/before/{stage}/{stage}.json',
        'reference_id': 'M14.2-REACH',
        'repair': repair,
        'current_source': fingerprint(f'assets/v3/blender/{asset_id}.blend'),
        'actual_runtime': runtime,
        'execution': {'source_checker_exit': 0, 'repair_GLTFLoader_exit': 0, 'lean_Workbench_render_exit': 0, 'threads': 2, 'all_Blender_processes_closed': True, 'browser_and_Khronos': 'Root owns final changed-artifact acceptance; not claimed here.'},
        'remaining': ['Root actual final body/cab browser + changed GLB Khronos gate', 'Separate mast/reach/forks/actions children'],
        'shared_helpers_contracts_P01_modified': False,
        'graph_evidence': {'tier': 2, 'project': 'qoima-twin', 'generation': '2026-11-07T15:43:42Z', 'coverage': 'No recorded issue but metadata_changed/not_tracked; exact source/artifacts read. No reindex.'},
    }
    artifact_paths = [
        'tools/blender/v3/build_forklift.py', f'assets/v3/blender/{asset_id}.blend', f'assets/v3/blender/{asset_id}.stats.json',
        f'frontend/public/models/v3/{asset_id}.glb', spec_path,
        f'{REL}/check_repair.py', f'{REL}/actual-repair-checks.json', f'{REL}/verify_repair_glb.mjs', f'{REL}/actual-repair-glb-checks.json',
        f'{REL}/before/wheel-close.png', f'{REL}/after/wheel-close.png', f'{REL}/paired-after/three-quarter.png',
    ] + [f'{REL}/after/{v}.png' for v in views]
    evidence['artifacts'] = [fingerprint(p) for p in artifact_paths]
    save(evidence_path, evidence)
    text = f'''# {stage} — front wheel/body attachment repair

**VERIFY.** Пользователь заметил отделённую переднюю ось. В принятом hull 1.20×2.10×3.00 м добавлены связные литые массы: ramp, увеличенный axle housing/shaft, bearing collars, нижняя поперечина и две боковые tapered cheeks. Шины, pivots, кабина, P01 и C08 не изменены. Предыдущий принятый результат сохранён в `{REL}/before/{stage}` и Git checkpoint `195323c`.

Текущий `{asset_id}`: {runtime['triangles']} tri, {runtime['bytes']} байт, {runtime['source_parts']} source parts/{runtime['meshes']} runtime meshes, {runtime['pivots']} pivots/{runtime['anchors']} anchors. GLB SHA256 `{runtime['sha256']}`. Actual stage bbox прежний; общий 3м travel hull не выдаётся за bbox незавершённой модели.

Actual source:45 замкнутых положительных solids/52 внутренних contact witnesses;37 исходных деталей неизменны (кроме трёх явно исправленных frame parts),30 body parts идентичны в обоих source. Участок вала между collar и hub сокращён с84 до9мм. Actual triangle tyre intersections=0. Реальный срез ramp в Z0… .08 имеет maxY.095 и15мм до minY.11 moving plate. Щёки имеют10мм до declared guides; остальные continuous clearance values и2negative cases сохранены в `{REL}/actual-repair-checks.json`. Это проверка actual fixed mesh против принятых **declared** moving interfaces: мачта/actions ещё не построены.

Независимый GLTFLoader декодировал оба новых GLB: finite/unit normals, actual bounds, source provenance, original root identity; все wheel batches и pivot/anchor matrices точно совпадают с frozen before GLB. Ненужные повторные route/worker-role проверки не запускались.

Фактически открыты7PNG: одинаковый mechanical close до/после, final cab front/side/rear/quarter и paired quarter. Кузов теперь имеет выраженную непрерывную опору передней оси; новых видимых дефектов не найдено. Close-camera скрывает только cab/control meshes для показа рамы; полные виды ничего не скрывают. Current cab previews включают исправленный кузов. Старые body-only4views и прежние paired views — **исторические до ремонта**, не свидетельства текущей геометрии. Актуальный driver witness: `{REL}/paired-after/three-quarter.png`.

Source/GLB/checks и hashes перечислены в evidence. Blender background factory-startup/2threads закрыт; source не менялся при render. Root выполняет final browser/Khronos gate; полный forklift, mast/reach/actions здесь не принимаются.
'''
    (ROOT / doc_path).write_text(text, encoding='utf-8')
    card_path = ROOT / f'docs/adaptive-v3/tasks/{stage}.md'
    card = card_path.read_text(encoding='utf-8-sig').replace('- Status: FIX', '- Status: VERIFY').replace('- Status: ACTIVE', '- Status: VERIFY')
    card += f'\n## Front attachment repair — VERIFY ({now})\n\nUser correction implemented inside unchanged hull: cast ramp, substantial saddle/axle/collars and connected side frame. {runtime["source_parts"]} source parts/{runtime["triangles"]}tri, GLB SHA`{runtime["sha256"]}`. Actual45parts/52contacts,37unchanged parts,30body/cab matches, tyre/BVH and continuous declared-interface checks plus2negatives; bounded GLTF decode passed. Final cab4+close+pairedquarter actually opened; no new visible defect. Prior source/GLB/history retained; old body-only previews are historical. Compact repair evidence/spec current; root browser/Khronos acceptance pending. No mast/action geometry.\n'
    card_path.write_text(card, encoding='utf-8')

print(json.dumps({'status': 'VERIFY', 'updated': ['M14.2', 'M14.3'], 'sources_and_GLBs_frozen': True, 'cab_previews_current': True}))
