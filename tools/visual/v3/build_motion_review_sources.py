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


def build(check_only: bool) -> dict:
    repo = Path(__file__).resolve().parents[3]
    public = repo / "frontend/public"
    output = public / "data/v3/motion-review"
    report_path = repo / "docs/adaptive-v3/evidence/W05.3.7-checks.json"
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    pins = report["input_hashes"]
    if not (
        report.get("passed") is True
        and report.get("task_id") == "W05.3.7"
        and report.get("motion_style") == "grounded_carry"
        and report.get("source_kind") == "visual_fixture"
        and report.get("engine_operation") is False
        and report.get("runtime_scene_joined") is False
        and len(pins) == 85
        and abs(report["route"]["duration_s"] - 28.47) < 1e-9
    ):
        raise ValueError("The accepted 85-source grounded-carry report is required")

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
        "source_report": "docs/adaptive-v3/evidence/W05.3.7-checks.json",
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
    args = parser.parse_args()
    print(json.dumps(build(args.check_only), ensure_ascii=False))
