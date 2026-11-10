"""Restore missing ignored calibration inputs from the verified public source pack.

Existing files are never overwritten. All selected entries are validated before
any directory or file is created; --check-only performs no writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


def restore(repo: Path, check_only: bool = False) -> dict:
    repo = repo.resolve(strict=True)
    work = (repo / 'work/v3').resolve()
    pack = (repo / 'frontend/public/data/v3/motion-review').resolve(strict=True)
    if not work.is_relative_to(repo) or not pack.is_relative_to(repo):
        raise ValueError('Resolved input or pack directory escapes the repository')
    manifest_path = pack / 'manifest.json'
    if not manifest_path.resolve(strict=True).is_relative_to(pack):
        raise ValueError('Manifest escapes the source pack')
    manifest = json.loads(manifest_path.read_bytes())
    sources = manifest.get('sources')
    if (manifest.get('schema_id') != 'qoima.motion-review-sources.v1'
            or not isinstance(sources, dict)
            or type(manifest.get('source_count')) is not int
            or manifest['source_count'] != len(sources)
            or not re.fullmatch(r'[0-9a-f]{64}', str(manifest.get('source_report_sha256', '')))):
        raise ValueError('Invalid motion-review source manifest')
    validated = []
    for logical, descriptor in sorted(sources.items()):
        if not isinstance(logical, str):
            raise ValueError('Invalid logical source path')
        if not logical.startswith('work/v3/'):
            continue
        path = PurePosixPath(logical)
        if ('\\' in logical or ':' in logical or path.is_absolute()
                or '..' in path.parts or str(path) != logical):
            raise ValueError(f'Noncanonical work input: {logical}')
        if not isinstance(descriptor, dict) or descriptor.get('repo_path') != logical:
            raise ValueError(f'Invalid work descriptor: {logical}')
        digest, size = descriptor.get('sha256'), descriptor.get('bytes')
        if (not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)
                or type(size) is not int or size < 0 or descriptor.get('url') != digest + '.bin'):
            raise ValueError(f'Invalid work blob descriptor: {logical}')
        blob = (pack / descriptor['url']).resolve(strict=True)
        target = (repo / logical).resolve()
        if (not blob.is_relative_to(pack) or not blob.is_file()
                or not target.is_relative_to(work) or not target.is_relative_to(repo)):
            raise ValueError(f'Resolved work input escapes its directory: {logical}')
        raw = blob.read_bytes()
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f'Public work blob differs: {logical}')
        exists = target.exists()
        if exists and (not target.is_file() or target.read_bytes() != raw):
            raise ValueError(f'Existing work input differs; refusing overwrite: {logical}')
        if check_only and not exists:
            raise ValueError(f'Work input is missing: {logical}')
        validated.append((target, raw, exists))
    restored = 0
    if not check_only:
        for target, raw, exists in validated:
            if exists:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also refuses a concurrent writer's file.
            with target.open('xb') as stream:
                stream.write(raw)
            restored += 1
    return {'passed': True, 'check_only': check_only,
            'work_input_count': len(validated), 'restored': restored,
            'source_report_sha256': manifest['source_report_sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(restore(args.repo_root, args.check_only)))
