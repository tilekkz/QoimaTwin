"""Freeze reviewed, source-pinned N2/N3 physical interface sections for API work."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PACKAGE = REPO / 'docs/v3/contract-proposals/n2-n3-physical-interfaces-v1'
NAMES = {'staging': 'n2-staging.json', 'retention': 'n3-retention.json', 'routes': 'route-terminal-interfaces.json'}
EXTENSIONS = {'n2_relative_pi':'n2-relative-pi-endpoints.json', 'n3_relative_pi':'n3-relative-pi-addon.json', 'current_n3_input':'n3-current-input.json', 'current_n3_migration':'n3-input-migration.json'}
VERIFIERS = ['freeze_n2_n3_interfaces_v3.py', 'verify_n2_n3_interfaces_v3.py', 'n2_n3_native_geometry.py', 'n2_n3_route_geometry.py']


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict:
    def reject(value: str):
        raise ValueError(f'Non-finite JSON number: {value}')
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=reject)


def inside(path: str) -> Path:
    result = (REPO / path).resolve(strict=True)
    if not result.is_relative_to(REPO) or result.relative_to(REPO).as_posix() != path:
        raise ValueError(f'Noncanonical source path: {path}')
    return result


def freeze(inputs: dict[str, Path], check_only: bool) -> dict:
    sections, sources, copies = {}, {}, {}
    for name, path in inputs.items():
        raw = path.read_bytes()
        data = load(path)
        if data.get('source_kind') != 'visual_fixture' or data.get('ready') is False:
            raise ValueError(f'{name} is not a reviewed physical interface section')
        if not data.get('schema_id') or not data.get('source_hashes'):
            raise ValueError(f'{name} lacks its schema or source pins')
        for source_path, expected in data['source_hashes'].items():
            if source_path.startswith(('work/', '/')):
                raise ValueError(f'Published interface depends on scratch work: {source_path}')
            actual = digest(inside(source_path).read_bytes())
            if actual != expected or source_path in sources and sources[source_path] != expected:
                raise ValueError(f'Source drift or conflicting section epochs: {source_path}')
            sources[source_path] = expected
        copies[NAMES[name]] = raw
        sections[name] = {'path': NAMES[name], 'sha256': digest(raw), 'schema_id': data['schema_id']}
    extensions={}
    for name, filename in EXTENSIONS.items():
        path=PACKAGE/filename
        if not path.exists():
            continue
        raw=path.read_bytes();data=load(path)
        if data.get('source_kind')!='visual_fixture' or not data.get('schema_id'):
            raise ValueError(f'Invalid extension: {filename}')
        for source_path, expected in data.get('source_hashes',{}).items():
            if source_path.startswith('work/') or digest(inside(source_path).read_bytes())!=expected:
                raise ValueError(f'Extension source drift: {source_path}')
            if source_path in sources and sources[source_path]!=expected:
                raise ValueError(f'Extension source epoch conflict: {source_path}')
            sources[source_path]=expected
        extensions[name]={'path':filename,'sha256':digest(raw),'schema_id':data['schema_id']}
    for filename in VERIFIERS:
        name='tools/visual/v3/'+filename
        sources[name]=digest(inside(name).read_bytes())
    artifacts={}
    for path in PACKAGE.rglob('*'):
        if path.is_file() and path.name!='bundle.json' and '__pycache__' not in path.parts and path.suffix!='.pyc':
            name=path.relative_to(PACKAGE).as_posix();raw=copies.get(name,path.read_bytes())
            artifacts[name]={'sha256':digest(raw),'bytes':len(raw)}
    for name,raw in copies.items():
        artifacts[name]={'sha256':digest(raw),'bytes':len(raw)}
    bundle = {
        'schema_id': 'qoima.n2-n3-physical-handoff.v1',
        'schema_version': '1.0.0',
        'source_kind': 'visual_fixture',
        'units': 'm_s_kg',
        'coordinate_system': {'handedness': 'right', 'up_axis': '+Y', 'scale_factor': 1},
        'engine_operation': False,
        'operational_workflow_admitted': False,
        'backend_adoption_recorded': False,
        'sections': sections,
        'extensions': extensions,
        'artifacts': dict(sorted(artifacts.items())),
        'source_hashes': dict(sorted(sources.items())),
        'scope': 'Physical frames, supports, retention controls and guarded terminal connections for API integration; full operational scheduling and source workflow execution remain separate.',
    }
    copies['bundle.json'] = (json.dumps(bundle, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    # Validate all bytes and all source epochs before making any output changes.
    if check_only:
        for name, raw in copies.items():
            if (PACKAGE / name).read_bytes() != raw:
                raise ValueError(f'Frozen packet differs: {name}')
    else:
        PACKAGE.mkdir(parents=True, exist_ok=True)
        for name, raw in copies.items():
            target = PACKAGE / name
            if not target.exists() or target.read_bytes() != raw:
                target.write_bytes(raw)
    return {'frozen': True, 'check_only': check_only, 'sections': len(sections), 'source_count': len(sources), 'bundle_sha256': digest(copies['bundle.json'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name, filename in NAMES.items():
        parser.add_argument('--' + name, type=Path, default=PACKAGE / filename)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(freeze({name: getattr(args, name) for name in NAMES}, args.check_only)))
