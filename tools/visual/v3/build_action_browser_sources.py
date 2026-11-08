"""Package only declared accepted visual-action source bytes for a normal browser."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = 'frontend/src/adaptive-v3/warehouseActionSourceManifest.json'
BASE = {
    'frontend/public/data/v3/warehouse-fixture-v3.json': '81d0caad4898a68a41f9c647141e7290df480900599e82b81739809cab0f9579',
    'frontend/public/data/adaptive-v3/layout-manifest.json': 'eb8afaf677864983a326af6ca47f4f41fbbd6ba162613fbce078feff0128f7db',
    'frontend/public/data/v3/worker-registry-v3.json': 'b21c2754fd2abec813adc1d9d1c24cf7f338f6a8a83efa051f70ef7982597e82',
    'frontend/public/data/v3/worker-profiles-v3.json': 'f30eb892ccc75ae5d2e6650e1a41b58acecbecd1a7c5cbcaf9b5836d8b7a8dc5',
}
SUPPORT = 'frontend/src/adaptive-v3/warehouseSupportBindings.json'
NONPUBLIC = {
    'contracts/actors.example.json',
    'docs/v3/contract-proposals/port-resource-policy-v3.json',
    'frontend/src/adaptive-v3/workerRoles.ts',
    'frontend/tools/build-worker-registry-v3.mjs',
    *['docs/adaptive-v3/evidence/' + name + '.json' for name in ['P03', 'P03.5.3.3', 'P04', 'P05', 'P06', 'P07']],
}


def read_bytes(path):
    relative = PurePosixPath(path)
    assert not relative.is_absolute() and '..' not in relative.parts and str(relative) == path
    resolved = (ROOT / path).resolve()
    assert resolved.is_relative_to(ROOT.resolve()) and resolved.is_file(), path
    return resolved.read_bytes()


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def make():
    sources = dict(BASE)
    for path, expected in BASE.items():
        assert sha(read_bytes(path)) == expected, ('Accepted base changed', path)
    registry = json.loads(read_bytes('frontend/public/data/v3/worker-registry-v3.json'))
    for path, expected in registry['source_hashes'].items():
        assert path not in sources or sources[path] == expected
        sources[path] = expected
    support = json.loads(read_bytes(SUPPORT))
    for binding in support.values():
        path = 'frontend/public/' + binding['path']
        assert path not in sources or sources[path] == binding['sha256']
        sources[path] = binding['sha256']
    rows, copies = [], {}
    for path, expected in sorted(sources.items()):
        blob = read_bytes(path)
        assert sha(blob) == expected, ('Accepted source changed', path)
        assert 0 < len(blob) <= 16 * 1024 * 1024
        if path.startswith('frontend/public/'):
            url = path.removeprefix('frontend/public/')
            assert url.startswith(('models/v3/', 'data/v3/', 'data/adaptive-v3/'))
            kind = 'existing_public_source'
        else:
            assert path in NONPUBLIC, ('Source is outside explicit publication allowlist', path)
            url = 'data/v3/action-sources/' + expected + '.bin'
            copies['frontend/public/' + url] = blob
            kind = 'exact_public_proof_copy'
        rows.append(dict(source_path=path, sha256=expected, bytes=len(blob), url=url, kind=kind))
    assert len(rows) == 30 and len(copies) == 10
    manifest = dict(schema_id='qoima.action-browser-sources.v3', source_kind='visual_fixture',
        engine_operation=False, operational_admission=False, entries=rows,
        total_source_bytes=sum(r['bytes'] for r in rows), proof_copy_bytes=sum(map(len, copies.values())),
        source_scope='Exact declared W05.1 source reader dependencies and optional W04 support sources only. No arbitrary file access or operational execution.',
        builder_sha256=sha(read_bytes('tools/visual/v3/build_action_browser_sources.py')),
        support_bindings_sha256=sha(read_bytes(SUPPORT)))
    copies[MANIFEST] = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    return manifest, copies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    manifest, outputs = make()
    for path, content in outputs.items():
        destination = ROOT / path
        if args.check_only:
            assert destination.read_bytes() == content, ('Browser source package drift', path)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + '.tmp')
            temporary.write_bytes(content)
            temporary.replace(destination)
    print(json.dumps(dict(passed=True, check_only=args.check_only, entries=len(manifest['entries']),
        existing_public=sum(e['kind'] == 'existing_public_source' for e in manifest['entries']),
        proof_copies=len(outputs) - 1, total_source_bytes=manifest['total_source_bytes'],
        proof_copy_bytes=manifest['proof_copy_bytes']), sort_keys=True))


if __name__ == '__main__':
    main()
