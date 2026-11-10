"""Freeze the accepted calibration's exact source bytes into a portable public pack.

Public files keep their existing URLs. Only the accepted non-public inputs are
copied, by content hash; the browser never needs a repository or filesystem URL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


def build(check_only: bool, report_name: str = 'docs/adaptive-v3/evidence/W05.3.7-checks.json') -> dict:
    repo = Path(__file__).resolve().parents[3]
    public = repo / "frontend/public"
    output = public / "data/v3/motion-review"
    report_path = (repo / report_name).resolve(strict=True)
    if not report_path.is_relative_to(repo):
        raise ValueError('Report must be inside the repository')
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    pins = report["input_hashes"]
    if not (
        report.get("passed") is True
        and report.get("task_id") in ("W05.3.7", "W05.3.10", "W05.3.11", "W05.3.12", "W05.3.13")
        and report.get("motion_style") == "grounded_carry"
        and report.get("source_kind") == "visual_fixture"
        and report.get("engine_operation") is False
        and report.get("runtime_scene_joined") is False
        and len(pins) >= 85
        and abs(report["route"]["duration_s"] - 28.47) < 1e-9
    ):
        raise ValueError("An accepted grounded-carry native report is required")
    original_hold = report.get('review_task_id') == 'W05.3.13-original-pose-only-hold'
    if original_hold and not (
        report['task_id'] == 'W05.3.13'
        and report.get('carry_pose') == 'original_hold'
        and report.get('breathing') is False
        and report.get('worker_model_path') == 'frontend/public/models/v3/worker-base.glb'
        and report.get('sample_scope') == 'full_source_sweep'
        and pins.get('frontend/public/models/v3/worker-base.glb') == '542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163'
        and 'frontend/src/adaptive-v3/warehouseForearmPronationPose.ts' in pins
        and 'frontend/public/data/v3/worker-base-original-hold-pose.json' in pins
        and len(report.get('frames', [])) >= 2000
        and report.get('native_foreign_and_full_body_gate', {}).get('material_witness_count') == 0
    ):
        raise ValueError('Original hold requires its full native sweep and original geometry pins')
    if not original_hold and report['task_id'] != 'W05.3.7' and (
        report.get('carry_pose') != ({'W05.3.12': 'vertical_90', 'W05.3.13': 'close_hold'}.get(report['task_id'], 'low_close'))
        or report.get('breathing') is not (report['task_id'] in ('W05.3.11', 'W05.3.12', 'W05.3.13'))
    ):
        raise ValueError('Low carry evidence must name its actual preset and breathing state')

    sources, copies = {}, {}
    # Validate the whole set before creating or changing any output.
    for logical_path, expected_sha in sorted(pins.items()):
        source = (repo / logical_path).resolve(strict=True)
        if not source.is_relative_to(repo) or not source.is_file():
            raise ValueError(f"Source escapes the repository: {logical_path}")
        if logical_path != source.relative_to(repo).as_posix():
            raise ValueError(f"Source must have a canonical repository path: {logical_path}")
        raw = source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected_sha:
            raise ValueError(f"Accepted input changed: {logical_path} ({digest})")
        if source.is_relative_to(public):
            url = os.path.relpath(source, output).replace("\\", "/")
        else:
            url = digest + ".bin"
            copies[url] = raw
        sources[logical_path] = {
            "repo_path": logical_path, "sha256": digest, "bytes": len(raw), "url": url,
        }

    manifest = {
        "schema_id": "qoima.motion-review-sources.v1",
        "source_kind": "visual_fixture",
        "engine_operation": False,
        "runtime_scene_joined": False,
        "source_pickup_executed": False,
        "motion_style": "grounded_carry",
        "duration_s": report["route"]["duration_s"],
        "carry_pose": report.get("carry_pose", "source"),
        "worker_model_path": report.get("worker_model_path", "frontend/public/models/v3/worker-base.glb"),
        "breathing": report.get("breathing", False),
        "source_report": report_path.relative_to(repo).as_posix(),
        "source_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "source_count": len(sources),
        "sources": sources,
    }
    copies["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if check_only:
        for name, expected in copies.items():
            target = output / name
            if not target.is_file() or target.read_bytes() != expected:
                raise ValueError(f"Frozen output differs or is missing: {target.relative_to(repo)}")
    else:
        output.mkdir(parents=True, exist_ok=True)
        for name, expected in copies.items():
            target = output / name
            if not target.is_file() or target.read_bytes() != expected:
                target.write_bytes(expected)
    return {
        "passed": True, "check_only": check_only, "sources": len(sources),
        "reused_public_sources": sum(s["url"].startswith("../") for s in sources.values()),
        "copied_nonpublic_blobs": len(copies) - 1,
        "copied_bytes": sum(len(raw) for name, raw in copies.items() if name != "manifest.json"),
        "manifest": str((output / "manifest.json").relative_to(repo)).replace("\\", "/"),
        "source_report_sha256": manifest["source_report_sha256"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Compare frozen outputs without writing")
    parser.add_argument("--report", default='docs/adaptive-v3/evidence/W05.3.7-checks.json', help='Current accepted native evidence report')
    args = parser.parse_args()
    print(json.dumps(build(args.check_only, args.report), ensure_ascii=False))
