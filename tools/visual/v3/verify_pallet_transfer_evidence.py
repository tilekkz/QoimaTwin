"""Validate current W05.4.4 evidence bytes without rendering or refreshing old proofs."""
import argparse
import collections
import hashlib
import json
import math
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'assets/v3/iterations/warehouse/W05.4.4'
OUT = ROOT / 'docs/adaptive-v3/evidence/W05.4.4-checks.json'
EPS = 2e-6
HU = 'v3:HU:initial:DEMO_172:01'
SOURCE_SLOT = 'slot:v3:slot:HEAVY_E:011:L1:B1'
TARGET_SLOT = 'slot:v3:slot:HEAVY_E:009:L1:B1'


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def number(value):
    assert type(value) in (int, float) and math.isfinite(value), ('Invalid numeric primitive', value)
    return value


def exact(value, expected):
    assert number(value) == expected, (value, expected)


def scoped(path):
    target = (ROOT / path).resolve()
    assert target.is_relative_to(ROOT.resolve()) and target.is_file(), path
    return target


def validate_native(report):
    assert report['executed'] is True and report['passed'] is True and not report['defects']
    assert report['complete_collision_certificate'] is False and report['coverage']['continuous_certificate'] is False
    exact(len(report['results']), 81)
    assert report['controls']['overlap']['found'] is True and report['controls']['boundary_only']['found'] is False
    assert all(number(d) > EPS for d in report['controls']['overlap']['surface_depths_m'])
    lost = report['controls']['native_lost_contact']
    assert number(lost['before_area']) > 0 and number(lost['after_area']) == 0
    assert abs(number(lost['restored_area']) - lost['before_area']) < 1e-12
    assert len(report['invalid_input_controls']) == 8 and all(x['rejected'] is True for x in report['invalid_input_controls'])
    unresolved = sum(len(s['unresolved_pairs']) for r in report['results'] for s in r['scans'])
    exact(unresolved, 12409)
    exact(report['statistics']['unresolved_component_pairs'], unresolved)
    assert all(not s['witnesses'] for r in report['results'] for s in r['scans'])
    assert report['native_capture']['scale'] == [1, 1, 1]
    q = report['native_capture']['quaternion']
    assert abs(abs(number(q[1])) - 1) < 1e-12 and abs(number(q[3])) < 1e-12
    assert all(number(c['max_matrix_delta']) < EPS for c in report['capture_continuity'])
    exact(report['counts']['HU'], 530)
    exact(report['counts']['actors'], 24)
    exact(report['counts']['trucks'], 2)
    for row in report['conservation']:
        for key, expected in [('HU_count', 530), ('worker_count', 24), ('vehicle_count', 2), ('quantity_units', 12256)]:
            exact(row[key], expected)
        assert row['HU_records_unchanged'] is True and row['all_actual_other_world_matrices_unchanged'] is True
        assert abs(number(row['gross_mass_kg']) - 9403.85) < 1e-8
    assert len(report['supports']) == 2 and len(report['fork_contacts']) == 14
    for support in report['supports']:
        assert support['handling_unit_id'] == HU and number(support['native_contact_area_sum_m2']) > 0
        assert abs(number(support['actual_bottom_gap_m'])) < EPS and number(support['maximum_contact_gap_m']) < EPS
    for frame in report['fork_contacts']:
        assert {r['side'] for r in frame['rows']} == {'L', 'R'}
        for row in frame['rows']:
            assert number(row['triangle_contact']['native_contact_area_sum_m2']) > 0
            assert number(row['triangle_contact']['maximum_contact_gap_m']) < EPS
            # Match the native gate: rays over pallet voids can hit the upper deck.
            # Each fork needs actual triangle area plus a matched surface ray, not every void ray.
            assert row['dual_surface_rays'] and any(r['gap_m'] is not None and number(r['gap_m']) <= EPS for r in row['dual_surface_rays'])
    driver_error = max(number(c['gap_m']) for r in report['results'] for c in r['driver']['worldContact'].values())
    assert driver_error < EPS
    return unresolved, driver_error


def validate_browser(report):
    assert report['passed'] is True and report['runtime_status'] == 'passed' and report['preflight_current'] is True
    assert report['mode'] == 'actual_browser_integration' and report['served_mode'] == 'production_vite_preview'
    assert report['visible'] is False and report['lifecycle']['terminated'] is True
    assert not report['preflight_problems'] and not report['fatal'] and not report['unexpected']
    assert all(r['injected'] is True for r in report['failed_requests'])
    assert len(report['checks']) == 18 and all(v is True for v in report['checks'].values())
    assert len(report['input_hashes']) == 156 and len(report['captures']) == 9
    assert len({c['file'] for c in report['captures']}) == 9
    for negative in report['negative_cases']:
        assert negative.get('refused') is True or bool(negative.get('error'))
    assert len(report['negative_cases']) == 4
    owners = {'01-paused-source.png': SOURCE_SLOT, 'stage-attach.png': 'vehicle:FL02',
              'stage-loaded.png': 'vehicle:FL02', 'stage-release.png': TARGET_SLOT,
              'stage-end.png': TARGET_SLOT, '06-live-reduced-manual.png': 'vehicle:FL02',
              '07-mobile-setdown.png': TARGET_SLOT}
    for capture in report['captures']:
        s = capture['snapshot']
        assert s['selection'] == dict(kind='HU', id=HU)
        for key, expected in [('stock_HUs', 530), ('workers', 24), ('completed_jobs', 0)]:
            exact(s['scene'][key], expected)
        assert len(s['scene']['vehicle_ids']) == 2
        preview = s['pallet']
        assert preview['playing'] is False and preview['engine_operation'] is False and preview['physical_join'] is False
        exact(preview['completed_jobs'], 0)
        if capture['file'].startswith('error-'):
            assert preview['phase'] == 'error' and preview['frame'] is None and preview['error']
        else:
            assert preview['phase'] == 'ready' and preview['frame']['logical_owner'] == owners[capture['file']]
        assert HU in capture['selected_card'] and '455' in capture['selected_card']
    identities = None
    for observation in report['observations']:
        cargo = observation['native']
        assert cargo['handling_unit_id'] == HU and cargo['model_scale_factor'] == 1
        exact(cargo['gross_mass_kg'], 455)
        exact(cargo['quantity_units'], 24)
        current = [(x['uuid'], x['index']) for x in cargo['mesh_instances']]
        identities = current if identities is None else identities
        assert current == identities and len(current) == 5


def document():
    hashes = {}
    def data(path):
        blob = scoped(path).read_bytes()
        assert path not in hashes or hashes[path] == sha(blob), ('Concurrent input disagreement', path)
        hashes[path] = sha(blob)
        return blob
    def load(path):
        return json.loads(data(path))
    def current(mapping):
        for path, expected in mapping.items():
            assert sha(data(path)) == expected, ('Stale material evidence', path)
    report_path = 'assets/v3/iterations/warehouse/W05.4.4/browser/browser-checks.json'
    review_path = 'assets/v3/iterations/warehouse/W05.4.4/visual-review.json'
    browser, review = load(report_path), load(review_path)
    validate_browser(browser)
    current(browser['input_hashes'])
    assert review['passed'] is True and review['reviewer'] == 'root' and review['root_visual_go'] is True
    assert review['root_artifact_review_pending'] is True
    assert review['browser_report_sha256'] == hashes[report_path]
    assert len(review['images']) == 9 and {i['file'] for i in review['images']} == {c['file'] for c in browser['captures']}
    for capture in browser['captures']:
        path = 'assets/v3/iterations/warehouse/W05.4.4/browser/' + capture['file']
        assert sha(data(path)) == capture['sha256']
        observed = next(x for x in review['images'] if x['file'] == capture['file'])
        assert observed['sha256'] == capture['sha256'] and observed['observation'].strip()
    assert sha(data('assets/v3/iterations/warehouse/W05.4.4/browser/sheet.png')) == review['auxiliary_sheet']['sha256']
    manifest = load('frontend/src/adaptive-v3/warehouseActionSourceManifest.json')
    assert len(manifest['entries']) == len(browser['public_sources']) == len(browser['http_preflight']) == 30
    for entry in manifest['entries']:
        original = data(entry['source_path'])
        assert sha(original) == entry['sha256'] and len(original) == entry['bytes']
        assert data('frontend/public/' + entry['url']) == data('frontend/dist/' + entry['url']) == original
        public = next(r for r in browser['public_sources'] if r['source_path'] == entry['source_path'])
        http = next(r for r in browser['http_preflight'] if r['source_path'] == entry['source_path'])
        assert public['expected_sha256'] == public['source_sha256'] == public['served_sha256'] == entry['sha256']
        assert http['status'] == 200 and http['sha256'] == http['expected_sha256'] == entry['sha256']
        assert http['bytes'] == http['expected_bytes'] == public['source_bytes'] == public['served_bytes'] == entry['bytes']
    assert len(browser['compiled_HTTP']) == 10
    for asset in browser['compiled_HTTP']:
        relative = urlsplit(asset['url']).path.lstrip('/')
        assert '..' not in Path(relative).parts
        blob = data('frontend/dist/' + relative)
        assert sha(blob) == asset['sha256'] and len(blob) == asset['bytes']
    paths = {name: f'docs/adaptive-v3/evidence/{file}.json' for name, file in
             [('plan', 'W05.4.1-checks'), ('plan_acceptance', 'W05.4.1'), ('native', 'W05.4.2-native-checks'), ('scene', 'W05.4.3-checks')]}
    reports = {k: load(p) for k, p in paths.items()}
    for report in [browser, *reports.values()]:
        assert report['engine_operation'] is False and report['physical_join'] is False
        exact(report['completed_jobs'], 0)
        current(report.get('input_hashes', report.get('source_hashes', {})))
    plan, native, scene = reports['plan'], reports['native'], reports['scene']
    assert reports['plan_acceptance']['passed'] is True and plan['cpu_gate_passed'] is True
    assert len(plan['negative_cases']) == 111 and plan['handling_raw_heading_checks'] >= 4112
    assert plan['maximum_handling_angular_velocity_rad_s'] == 0
    assert len(plan['routes']['empty']['arcs']) == 10 and len(plan['routes']['loaded']['arcs']) == 6
    unresolved, driver_error = validate_native(native)
    assert scene['cpu_gate_passed'] is True and scene['native_geometry_admission_required'] is True
    assert scene['population'] == dict(handling_units=530, workers=24, vehicles=2, created_by_applicator=0)
    assert scene['selected_native_parts'] == 5 and scene['actual_fork_support_parts'] == 2 and scene['seek_samples'] == 143
    assert scene['reverse_repeat_samples'] == 286 and scene['nondefault_representation_samples'] == 38
    assert number(scene['maximum_native_root_position_error_m']) < EPS and number(scene['maximum_driver_contact_error_m']) < EPS
    assert number(scene['maximum_attach_release_translation_error_m']) < EPS and number(scene['maximum_attach_release_matrix_error']) < EPS
    assert scene['foreign_resource_disposals'] == 0
    archive = {x['file']: x for x in review['component_archives']}
    for name, row in archive.items():
        assert sha(data('assets/v3/iterations/warehouse/W05.4.4/browser/' + name)) == row['sha256']
    component_base = 'assets/v3/iterations/warehouse/W05.4.4/browser/'
    audit = load(component_base + 'component-audit-findings.json')
    fixed = load(component_base + 'component-fix-verification.json')
    before = load(component_base + 'component-results-before.json')
    after = load(component_base + 'component-results-after.json')
    assert audit['counts']['total'] == 3 and len(audit['findings']) == 3
    assert before['counts'] == dict(cases=11, passed=8, harnessFailures=3)
    assert after['counts'] == fixed['green'] == dict(cases=11, passed=11, harnessFailures=0)
    assert after['label'] == fixed['label'] == 'WHITE_BOX / COMPONENT_ONLY'
    # These immutable before/after archives describe the original repair epoch.
    # Only the portable report below is evidence for today's exact Preview source.
    assert after['source_sha256'] == fixed['source_after_sha256'] == fixed['source_current_sha256']
    assert before['source_sha256'] == fixed['source_before_sha256']
    for source, copied in [('component-results-red.json', 'component-results-before.json'),
                           ('component-results-green.json', 'component-results-after.json'),
                           ('component-regressions.cjs', 'component-regressions.cjs.txt')]:
        assert hashes[component_base + copied] == fixed['files'][source]
    assert {x['id'] for x in after['results'] if x.get('classification') == 'regression_green'} == set(fixed['targeted_cases'])
    lifecycle_path = 'docs/adaptive-v3/evidence/W05.4.4-lifecycle-checks.json'
    lifecycle = load(lifecycle_path)
    current(lifecycle['input_hashes'])
    assert lifecycle['passed'] is True and lifecycle['label'] == 'COMPONENT_ONLY'
    assert lifecycle['counts'] == dict(cases=11, passed=11, failed=0, behavior_cases=10, conditional_limitations=1)
    for flag in ['public_bootstrap', 'private_source_issuance', 'native_physical_admission', 'native_530_HU_scene', 'rendered_appearance', 'operational_admission', 'continuous_deadline_certificate']:
        assert lifecycle[flag] is False
    assert len(lifecycle['results']) == 11 and all(x['outcome'] == 'PASS' for x in lifecycle['results'])
    assert {x['id'] for x in lifecycle['results'] if x.get('classification') == 'regression_green'} == set(fixed['targeted_cases'])
    deadline = next(x for x in lifecycle['results'] if x['id'] == 'C11_NONCOOPERATIVE_PREPARE_DEADLINE')
    assert deadline['classification'] == 'conditional_limitation' and deadline['settledAfterDeadline'] is False
    assert deadline['observedAfterDeadline']['phase'] == 'loading'
    retention = next(x for x in lifecycle['results'] if x['id'] == 'C02_ERROR_PERSISTENCE')
    assert retention['afterStop']['error'] == 'CHANGED_NATIVE_BINDING' and retention['legacyCancellationRetainsDiagnostic'] is True
    assert lifecycle['historical_red_reference']['sha256'] == hashes[component_base + 'component-results-before.json']
    rerun = subprocess.run(['node', 'tools/check-warehouse-pallet-preview-lifecycle-v3.cjs', '--check-only'],
                           cwd=ROOT/'frontend', capture_output=True, text=True, timeout=60)
    assert rerun.returncode == 0, ('Current portable lifecycle regression failed', (rerun.stdout+rerun.stderr)[-2000:])
    for path in ['docs/adaptive-v3/specs/W05.4.4.md', 'tools/visual/v3/verify_pallet_transfer_evidence.py']:
        data(path)
    current(hashes.copy())
    return dict(task_id='W05.4.4', passed=True, verification_kind='current_report_and_exact_byte_agreement',
        source_kind='visual_fixture', engine_operation=False, operational_admission=False,
        physical_join=False, completed_jobs=0, root_artifact_acceptance_pending=True,
        recorded_at_utc=review['recorded_at_utc'], browser_report_sha256=hashes[report_path],
        checks=dict(browser_checks=18, actual_primary_captures=9, browser_input_hashes=156,
            exact_HTTP_sources=30, exact_current_compiled_HTTP_assets=10, native_poses=81,
            Scene_seek_samples=143, reverse_repeat_samples=286, source_target_supports=2,
            fork_contact_frames=14, maximum_driver_contact_error_m=driver_error,
            same_HU_parts=5, handling_units=530, workers=24, vehicles=2,
            component_stub_regressions_before=8, component_stub_regressions_after=11,
            current_portable_component_cases=11, portable_component_behavior_cases=10,
            portable_component_conditional_limitations=1, independent_findings_fixed=3),
        native_unresolved_component_observations=unresolved, complete_collision_certificate=False,
        representation_diagnostics=dict(maximum_native_root_position_error_m=scene['maximum_native_root_position_error_m'],
            maximum_ideal_plan_position_drift_m=scene['maximum_ideal_plan_position_drift_m'],
            maximum_native_part_root_spread_m=scene['maximum_native_part_root_spread_m'],
            maximum_nondefault_part_root_spread_m=scene['maximum_nondefault_part_root_spread_m']),
        input_hashes=dict(sorted(hashes.items())),
        limitations=['12409 native no-witness component observations remain unresolved; no complete continuous collision certificate.',
            'Native horizontal support/centre hull is not strength or stability certification.',
            'Component11/11 uses dependency/DOM stubs; actual production browser is a separate18check report.',
            'Abort-only30second deadline cannot force a noncooperative awaited dependency to settle.',
            'Current exact-byte/report and authorized root visual-review agreement only; no new rendering or operational admission.',
            'Root reviews this persisted artifact/spec packet before task acceptance; no parent or task status is changed.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--write-checks', action='store_true')
    group.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    report = document()
    blob = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    if args.write_checks:
        temporary = OUT.with_suffix('.json.tmp')
        temporary.write_bytes(blob)
        temporary.replace(OUT)
    elif args.check_only:
        before = OUT.stat()
        assert OUT.read_bytes() == blob, 'Current pallet evidence differs; old proofs are never rewritten'
        assert OUT.stat().st_mtime_ns == before.st_mtime_ns
    print(json.dumps(dict(passed=True, check_only=args.check_only, proof_written=args.write_checks,
        captures=9, browser_checks=18, unresolved_native_observations=12409,
        verified_source_files=len(report['input_hashes']), checks_sha256=sha(blob), root_artifact_acceptance_pending=True)))


if __name__ == '__main__':
    main()
