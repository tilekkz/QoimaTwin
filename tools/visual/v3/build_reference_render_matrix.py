"""Inventory existing V3 reference/model/view evidence; never render or approve it.

Run with the repository Python. --check-only compares bytes and writes nothing.
Only Q01-model-matrix.json and Q01_MODEL_MATRIX.md are generated.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[3]
OUTPUT_JSON = "docs/adaptive-v3/evidence/Q01-model-matrix.json"
OUTPUT_MD = "docs/adaptive-v3/Q01_MODEL_MATRIX.md"
VIEWS = ("front", "side", "rear", "three-quarter")
HASH = re.compile(r"^[0-9a-fA-F]{64}$")
PATH = re.compile(r"(?:assets/|frontend/|docs/|tools/)[^\s\"'<>;,()\[\]{}]+?\.(?:json|png|jpg|blend|glb|md|py|ts|mjs|txt|svg)\b")
GROUPS = {
    "storage": "rack-small rack-standard heavy-bay long-rack flex-bay",
    "cargo": "small-carton standard-carton heavy-box pallet-load ibc long-bundle drum fragile-crate",
    "containers": "order-tote sealed-parcel pallet small-unit small-case-open-partial",
    "workers": "worker-base worker-manual worker-small-pick picker-figure picker-worker driver",
    "equipment": "picking-cart forklift long-cradle small-package-gripper",
    "conveyors": "conveyor-straight conveyor-turn conveyor-diverter conveyor-kit",
    "packing": "packing-station",
    "environment": "dock-module large-gate large-gate-b2b environment-shell floor-markings environment-markings-fixture",
}
TASKS = dict(zip(
    "rack-small rack-standard heavy-bay long-rack flex-bay small-carton standard-carton heavy-box order-tote sealed-parcel pallet-load ibc long-bundle drum fragile-crate".split(),
    "M01 M02 M03 M04 M05 M06.1 M06.2 M06.3 M07.1 M07.2 M08 M09 M10 M11 M12".split()))
TASKS.update({"worker-base": "P01", "worker-manual": "P03.5.3.3.1", "worker-small-pick": "P03.5.3.3.1", "picking-cart": "P03", "forklift": "M14.9", "long-cradle": "M14.6", "packing-station": "P08", "conveyor-kit": "P08", "dock-module": "P09.1", "large-gate": "P09.2", "large-gate-b2b": "P09.2", "environment-shell": "P09.3", "floor-markings": "P09.4", "environment-markings-fixture": "P09.4", "packer-workcell-fixture": "P04", "receiver-workcell-fixture": "P05", "shipper-workcell-fixture": "P06"})
REFINEMENTS = {
    "rack-small": "Shallow front bins/rear strip and exact C04 metrics override raster proportions; see M01 approved_engineering_adaptations.",
    "rack-standard": "Accepted open-top ground fork lanes/ribs replace the closed concept deck; columns stay within .07 m envelopes. C08 metadata refresh is distinct from original geometry review.",
    "heavy-bay": "C08 functional open fork lanes/support patches override continuous raster deck; narrow-HU/support limitations remain. Petrol ribs/charcoal runners supersede earlier tan material mismatch.",
    "long-rack": "M04_TRANSFER_REF supersedes original R13.4 topology; paired rack/transfer supports are engineering refinements, not shrink-to-fit.",
    "long-bundle": "M10_METAL_REF is the bound metal bundle concept; original wood-like concept is historical.",
    "forklift": "M14.2-REACH and final M14.9 evidence govern current vehicle, not latest stage filename. Historical axle/cab/mast stages are separate models.",
    "worker-base": "Original base identity retained. Current requested rest palms face inward; historical neutral/pose acceptance does not establish this correction in current runtime.",
    "worker-manual": "Additive articulated derivative preserves original body identity; current requested rest palms face inward. Historical thumb/rig checks are bounded fixtures.",
    "picking-cart": "Current requested grip is overhand, top-down. Historical push/action captures alone do not establish the current correction or a four-view sheet.",
    "small-case-open-partial": "Current requested opening has four outward upper carton flaps and fixed walls; current geometry/action must be reviewed against that correction.",
    "dock-module": "Connected stepped U frame adapted to accepted .25 m wall band; no threshold/panel in clear opening.",
    "large-gate": "Accepted .25 m wall band and clear passage govern frame dimensions; no scale stretching.",
    "large-gate-b2b": "Separate gate variant; accepted .25 m wall band and B2B clear passage govern geometry.",
    "environment-shell": "Accepted cutaway walls/returns, columns and six apertures; architectural exceptions/precision budget remain qualified in P09.3.",
}


# Runtime compositions reuse native models and do not create new worker identities.
PRESENTATIONS = {
    "forklift-driver": ("worker-base", "forklift-driver", None, "P07", "R05", ["forklift", "worker-base"]),
    "picker-cart-grip": ("picker-figure", "picker-cart-grip", None, "P03.3", "R11", ["picker-figure", "picking-cart"]),
    "picker-cart-walk": ("picker-figure", "picker-cart-walk", None, "P03.4", "R11", ["picker-figure", "picking-cart"]),
    "manual-cart-walk": ("worker-manual", "manual-cart-walk", None, "P03.4", "R11", ["worker-manual", "picking-cart"]),
    "forklift-pickup-cycle": ("forklift", "forklift-pickup-cycle", None, "M14.8", "M14.2-REACH", ["forklift", "worker-base"]),
    **{f"worker-role-{role}": ("worker-base", "worker-roles", role, "P02", "R05", ["worker-base"]) for role in ("P01", "K01", "R01", "S01", "F01")},
}


def canonical(value):
    """Normalize only repository paths; never follow an external evidence path."""
    s = str(value).replace("\\", "/")
    root = ROOT.as_posix() + "/"
    if s.lower().startswith(root.lower()):
        s = s[len(root):]
    while s.startswith("../"):
        s = s[3:]
    if not s.startswith(("assets/", "frontend/", "docs/", "tools/")):
        return None
    if ".." in Path(s).parts or ":" in s:
        return None
    return s


def walk(value, pointer=""):
    yield pointer, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk(item, pointer + "/" + str(key).replace("~", "~0").replace("/", "~1"))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from walk(item, pointer + "/" + str(i))


class Inventory:
    def __init__(self):
        self.files = {}
        self.documents = {}
        self.links = defaultdict(list)
        self.frames = defaultdict(list)

    def file(self, path):
        path = canonical(path)
        if path is None:
            return None
        if path not in self.files:
            p = ROOT / path
            if p.is_file():
                raw = p.read_bytes()
                row = {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "status": "present"}
                if raw[:8] == b"\x89PNG\r\n\x1a\n":
                    row["dimensions_px"] = list(struct.unpack(">II", raw[16:24]))
                self.files[path] = row
            else:
                self.files[path] = {"path": path, "bytes": None, "sha256": None, "status": "missing"}
        return self.files[path]

    def read(self, path):
        path = canonical(path)
        self.file(path)
        if path not in self.documents:
            data = json.loads((ROOT / path).read_text(encoding="utf-8-sig"))
            records = []
            for ptr, value in walk(data):
                if isinstance(value, dict):
                    screenshot = canonical(value.get("screenshot", ""))
                    if screenshot:
                        state = value.get("state", {})
                        identity = {k: v for k, v in state.items() if k in ("modelId", "phase", "view", "fixture", "roles", "time", "time_s", "action", "pose", "actorId", "driver", "grip")} if isinstance(state, dict) else state
                        self.frames[screenshot].append({"document": path, "pointer": ptr, "view": value.get("view"), "state_identity": identity})
                    if isinstance(value.get("path"), str):
                        p = canonical(value["path"])
                        if p:
                            records.append((p, value.get("sha256"), ptr))
                    for key, item in value.items():
                        p = canonical(key)
                        if p and isinstance(item, str) and HASH.fullmatch(item):
                            records.append((p, item, ptr))
                elif isinstance(value, str):
                    for match in PATH.finditer(value.replace("\\", "/")):
                        p = canonical(match.group())
                        if p:
                            records.append((p, None, ptr))
            records = sorted(set(records), key=lambda x: (x[0], x[1] or "", x[2]))
            self.documents[path] = (data, records)
            for p, expected, ptr in records:
                self.links[p].append({"document": path, "pointer": ptr, "recorded_sha256": expected})
        return self.documents[path][0]

    def claims(self, path):
        actual = self.file(path)
        result = []
        for rec in self.links.get(path, []):
            expected = rec["recorded_sha256"]
            result.append({**rec, "hash_status": "missing" if actual["status"] == "missing" else "unbound" if not expected else "current" if expected == actual["sha256"] else "stale"})
        return result


def review_records(data):
    """Preserve historical assertions verbatim, with pointers; grant no new review."""
    out = []
    for ptr, value in walk(data):
        key = ptr.rsplit("/", 1)[-1].lower()
        if key in {"root_review", "root_acceptance", "visual_review", "model_review", "approved_engineering_adaptations", "reference_adaptation", "interpretation", "root_plan_approval", "pregeometry_plan_root_response", "final_actual_visual_review", "explicitly_reviewed_current_view", "limits", "scope"}:
            out.append({"pointer": ptr, "assertion": value})
    return out


def build():
    inv = Inventory()
    manifest = inv.read("assets/references/v3/manifest.json")
    bindings = inv.read("frontend/src/adaptive-v3/warehouseAssetBindings.json")
    # Scoped metadata only. No code discovery, execution, graph mutation or rendering.
    doc_paths = set()
    for folder in ("assets/v3/previews", "assets/v3/qa-browser", "assets/v3/iterations", "assets/v3/specs"):
        doc_paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / folder).rglob("*.json"))
    evidence = ROOT / "docs/adaptive-v3/evidence"
    doc_paths.update(p.relative_to(ROOT).as_posix() for p in evidence.glob("*.json") if re.match(r"^(M\d|P\d|W04\.|C02|R\d)", p.stem))
    for path in sorted(doc_paths):
        inv.read(path)
    stats_paths = sorted((ROOT / "assets/v3/blender").glob("*.stats.json"))
    stats = {p.name.removesuffix(".stats.json"): inv.read(p.relative_to(ROOT).as_posix()) for p in stats_paths}
    # Manifest aliases without actual stats are explicit unresolved rows, not invented models.
    assets = sorted(set(stats) | set(manifest["asset_reference_bindings"]) | set(PRESENTATIONS))
    all_images = sorted({p.relative_to(ROOT).as_posix() for folder in ("assets/v3/previews", "assets/v3/qa-browser", "assets/v3/iterations") for p in (ROOT / folder).rglob("*.png")})
    references = {}
    for ref in manifest["references"]:
        rid = ref["reference_id"]
        references[rid] = {"manifest_record": ref, "files": []}
        for ptr, value in walk(ref):
            if isinstance(value, dict) and isinstance(value.get("path"), str) and canonical(value["path"]):
                record = inv.file(value["path"])
                references[rid]["files"].append({**record, "manifest_pointer": ptr, "recorded_sha256": value.get("sha256"), "hash_status": "current" if record["sha256"] == value.get("sha256") else "missing" if record["status"] == "missing" else "stale"})
                if record["status"] == "present" and record["path"].endswith(".json"):
                    inv.read(record["path"])
    rows = []
    for asset in assets:
        presentation = PRESENTATIONS.get(asset)
        base, image_dir, prefix, presentation_task, presentation_ref, members = presentation or (asset, asset, None, None, None, [])
        st = stats.get(base, {})
        source = canonical(st.get("source", "")) or f"assets/v3/blender/{asset}.blend"
        model = canonical(st.get("glb", "")) or f"frontend/public/models/v3/{asset}.glb"
        source_file, model_file = inv.file(source), inv.file(model)
        related = set()
        for target in (source, model, f"assets/v3/blender/{base}.stats.json"):
            related.update(x["document"] for x in inv.links.get(target, []))
        task = presentation_task or TASKS.get(asset)
        if task and (evidence / (task + ".json")).is_file():
            related.add(f"docs/adaptive-v3/evidence/{task}.json")
        # Directory identity is exact, never a substring or latest-filename rule.
        images = {p for p in all_images if image_dir in Path(p).parts and (not prefix or Path(p).name.startswith(prefix + "-"))}
        related.update(p for p in inv.documents if image_dir in Path(p).parts)
        for document in sorted(related):
            for p, _, _ in inv.documents[document][1]:
                if p.endswith(".png") and not p.startswith("assets/references/"):
                    # Multi-model records can supply images only in this asset's directory.
                    if image_dir in Path(p).parts and (not prefix or Path(p).name.startswith(prefix + "-")):
                        images.add(p)
        image_rows = []
        for p in sorted(images):
            info = inv.file(p)
            claims = inv.claims(p)
            links = []
            for claim in claims:
                records = inv.documents[claim["document"]][1]
                source_hashes = sorted({h for q, h, _ in records if q == source and h})
                model_hashes = sorted({h for q, h, _ in records if q == model and h})
                if source_hashes or model_hashes:
                    # Mixed historical/current hashes in one document are ambiguous.
                    exact = (source_hashes == [source_file["sha256"]] or model_hashes == [model_file["sha256"]])
                    conflict = (source_hashes and source_hashes != [source_file["sha256"]]) or (model_hashes and model_hashes != [model_file["sha256"]])
                    status = "current-source-bound" if exact and not conflict and claim["hash_status"] == "current" else "stale" if not exact or claim["hash_status"] == "stale" else "unbound"
                    links.append({"document": claim["document"], "image_pointer": claim["pointer"], "image_hash_status": claim["hash_status"], "source_sha256_claims": source_hashes, "model_sha256_claims": model_hashes, "status": status})
            status = "missing" if info["status"] == "missing" else "current-source-bound" if any(x["status"] == "current-source-bound" for x in links) else "stale" if links and all(x["status"] == "stale" for x in links) else "unbound"
            stem = Path(p).stem
            if presentation and status == "current-source-bound":
                status = "unbound"  # A component hash cannot bind the composed runtime state.
            if prefix and stem.startswith(prefix + "-"):
                stem = stem[len(prefix) + 1:]
            view = "three-quarter" if stem in ("quarter", "three-quarter") else stem if stem in VIEWS else None
            image_rows.append({**info, "view": view, "kind": "runtime-capture" if "/qa-browser/" in p or "/browser/" in p else "native-source-render", "binding_status": status, "binding_evidence": links, "visual_review_status": "unreviewed", "frame_identity_records": [{"document": c["document"], "pointer": c["pointer"]} for c in claims], "static_sheet_eligible": view is not None and not any(t in Path(p).parts for t in ("action", "actions", "walk", "pick", "deposit"))})
        views = {}
        for view in VIEWS:
            candidates = [x for x in image_rows if x["view"] == view and x["static_sheet_eligible"]]
            status = next((s for s in ("current-source-bound", "unbound", "stale") if any(x["binding_status"] == s for x in candidates)), "missing")
            views[view] = {"binding_status": status, "visual_review_status": "unreviewed", "candidate_paths": [x["path"] for x in candidates], "selection": None, "reason": "All candidates retained; source hash/evidence matching precedes root image selection. Action frames/contact sheets do not establish static views."}
        historical = []
        for document in sorted(related):
            if not document.startswith("docs/adaptive-v3/evidence/"):
                continue
            data = inv.documents[document][0]
            historical.append({"document": document, "recorded_status": data.get("status", data.get("passed")), "assertions": review_records(data), "current_source_claims": [x for x in inv.claims(source) if x["document"] == document], "current_model_claims": [x for x in inv.claims(model) if x["document"] == document]})
        group = "runtime-presentations" if presentation else next((g for g, names in GROUPS.items() if asset in names.split()), "supporting-fixtures")
        ref_id = presentation_ref or manifest["asset_reference_bindings"].get(asset)
        rows.append({"asset_id": asset, "family": group, "primary_task": task, "reference_id": ref_id, "reference_status": "manifest-bound" if ref_id in references else "unresolved", "current": {"source": source_file, "model": model_file, "stats": inv.file(f"assets/v3/blender/{asset}.stats.json"), "stats_asset_id": st.get("asset_id"), "stats_model_sha256": st.get("sha256"), "stats_model_binding": "current" if st.get("sha256") and st["sha256"] == model_file["sha256"] else "missing" if not st else "stale", "units": st.get("units"), "up_axis": st.get("up_axis"), "forward_axis": st.get("forward_axis"), "dimensions_m": st.get("dimensions_m"), "root_matrix_blender": st.get("root_matrix_blender"), "warehouse_binding": bindings.get(asset), "warehouse_binding_status": "absent" if asset not in bindings else "current" if bindings[asset].get("sha256") == model_file["sha256"] else "stale"}, "source_hash_claims": inv.claims(source), "model_hash_claims": inv.claims(model), "historical_acceptance_evidence": historical, "engineering_refinement": REFINEMENTS.get(asset, "See exact task/spec assertions; no geometry judgement inferred from filenames or source renders."), "spec_paths": sorted(p for p in doc_paths if p.startswith("assets/v3/specs/") and (Path(p).name.startswith(asset + ".") or Path(p).name.startswith(asset + "-"))), "views": views, "images": image_rows, "native_runtime_evidence": sorted(related), "current_visual_review": "unreviewed", "acceptance": "unresolved; historical evidence retained separately; Q01 root review open"})
        row = rows[-1]
        for item in historical:
            data = inv.documents[item["document"]][0]
            review = data.get("root_review", {})
            root_pass = isinstance(review, dict) and review.get("status") == "PASS"
            root_pass = root_pass or (data.get("reviewer") == "root" and (data.get("passed") is True or data.get("status") == "PASS"))
            item["historical_root_pass_asserted"] = root_pass
            item["source_and_model_hashes_match_current"] = all(any(c["hash_status"] == "current" for c in item[key]) and not any(c["hash_status"] == "stale" for c in item[key]) for key in ("current_source_claims", "current_model_claims"))
        row["record_kind"] = "runtime-composition" if presentation else "native-model" if st else "unresolved-manifest-alias"
        row["reference_binding_basis"] = "explicit presentation mapping; component authority, not a new independent concept" if presentation else "manifest asset_reference_bindings"
        for image in image_rows:
            image["evidence_pointers"] = image.pop("frame_identity_records")
            image["frame_identity_records"] = inv.frames.get(image["path"], [])
            image["medium_classification_basis"] = "path convention; consult provenance/frame records, no new visual inspection"
            if presentation and asset in ("picker-cart-walk", "manual-cart-walk", "forklift-pickup-cycle"):
                image["static_sheet_eligible"] = False
        if presentation:
            row["current"]["stats"] = inv.file(f"assets/v3/blender/{base}.stats.json")
            row["composition_members"] = [{"asset_id": member, "source": inv.file(f"assets/v3/blender/{member}.blend"), "model": inv.file(f"frontend/public/models/v3/{member}.glb")} for member in members]
            row["engineering_refinement"] = "Composed existing models/actor, not a separate GLB or new person. Component model hashes do not bind action/controller/pose state. See task scope and exact runtime frame pointers."
            if asset in ("picker-cart-walk", "manual-cart-walk", "forklift-pickup-cycle"):
                for view in row["views"].values():
                    view.update(binding_status="missing", candidate_paths=[], reason="Action observation retained in images; not a four-view static model sheet.")
        for view_name, cell in row["views"].items():
            cell["by_medium"] = {}
            for medium in ("native-source-render", "runtime-capture"):
                candidates = [i for i in image_rows if i["kind"] == medium and i["path"] in cell["candidate_paths"]]
                state = next((s for s in ("current-source-bound", "unbound", "stale") if any(i["binding_status"] == s for i in candidates)), "missing")
                cell["by_medium"][medium] = {"binding_status": state, "visual_review_status": "unreviewed", "candidate_paths": [i["path"] for i in candidates]}
    # Bind recorded task inputs/outputs too, including C02 proposals and pose/controller files.
    # Hashing source bytes does not inspect code structure or execute it.
    for path in sorted(inv.links):
        inv.file(path)
    # Read/hash applicable briefs/cards and supporting model reports as authoritative inputs.
    inputs = ["tools/visual/v3/build_reference_render_matrix.py", "docs/adaptive-v3/tasks/Q01.md"] + [f"docs/adaptive-v3/brief/{n}" for n in ("02_DESIGN_V3.md", "03_MICROTASKS.md", "04_TASK_CARD_EXAMPLES.md")]
    inputs += [p.relative_to(ROOT).as_posix() for p in (ROOT / "docs/adaptive-v3/tasks").glob("*.md") if re.match(r"^[MP]\d", p.stem)]
    inputs += [p.relative_to(ROOT).as_posix() for p in (ROOT / "docs/adaptive-v3/models").glob("*.md")]
    for p in inputs:
        inv.file(p)
    # Bind every indexed metadata document and every image, including action/non-sheet frames.
    for p in all_images:
        inv.file(p)
    counts = Counter(v["binding_status"] for row in rows for v in row["views"].values())
    summary = {"asset_rows": len(rows), "families": dict(sorted(Counter(r["family"] for r in rows).items())), "required_view_cells": len(rows) * 4, "view_binding_status": dict(sorted(counts.items())), "unreviewed_view_cells": len(rows) * 4, "images": sum(len(r["images"]) for r in rows), "stats_model_binding": dict(sorted(Counter(r["current"]["stats_model_binding"] for r in rows).items()))}
    result = {"schema_version": 1, "task_id": "Q01", "status": "MATRIX_BUILT_REVIEW_OPEN", "method": {"graph": "No structural code graph tools exposed; exact scoped source/metadata fallback; no reindex.", "selection": "Current canonical Blender stats/source/GLB first; manifest reference and task evidence next; all image candidates matched by hashes. Never latest filename selection.", "binding": "current-source-bound means exact image hash plus an unambiguous current source or model path/hash in the same evidence document. It is a documentary association, not an independently repeated render or proof of model correctness. Mixed historical/current hashes remain unbound or stale. Missing hashes remain unbound.", "review": "All current visual-review cells remain unreviewed. Historical assertions are quoted evidence only, including PASS/FIX scope and limitations; no new root visual review.", "views": "Exact front/side/rear/quarter/three-quarter filenames only; quarter aliases three-quarter. Contact sheets/pose sequences/action frames are retained but never fill four static view cells. Runtime and native candidates remain separately typed.", "scope": "Input-only models/references/evidence; no new render/browser/backend run, strength/retention/performance claim or full visual completion.", "invariants": "Original 24 worker identities, 530 HUs, C02 units/masses/dimensions and 1:1 scale preserved; this inventory does not execute or certify those invariants.", "corrections": "Inward rest palms; overhand top-down cart grip; four outward upper carton flaps with fixed walls. Historical acceptance does not waive current correction review."}, "summary": summary, "references": references, "assets": rows, "input_files": [inv.files[k] for k in sorted(inv.files)]}
    return result


def markdown(data):
    s = data["summary"]
    lines = ["# Q01 reference / model / view matrix", "", "Status: **MATRIX BUILT; CURRENT VISUAL REVIEW OPEN**. No new renders or acceptance.", "", f"{s['asset_rows']} explicit model/alias rows; {s['required_view_cells']} required four-view cells; {s['unreviewed_view_cells']} unreviewed. Binding counts: " + json.dumps(s["view_binding_status"], sort_keys=True) + ".", "", "Family counts: " + json.dumps(s["families"], sort_keys=True) + ".", "", "The companion [JSON](evidence/Q01-model-matrix.json) contains full source/model/image SHA256, reference provenance, frame/evidence pointers, historical review assertions and input fingerprints. Current canonical stats live in assets/v3/blender. Alias rows without stats remain unresolved.", "", "## Interpretation", ""]
    lines.extend(f"- **{key}**: {value}" for key, value in data["method"].items())
    lines += ["", "## Coverage", "", "F/S/R/Q = front/side/rear/three-quarter. C=current-source-bound, S=stale, U=unbound, M=missing. All are visually unreviewed; C is a hash-backed documentary association, never an acceptance verdict.", "", "| Family / asset | Reference | Stats→GLB | F/S/R/Q | Historical task |", "|---|---|---|---|---|"]
    short = {"current-source-bound": "C", "stale": "S", "unbound": "U", "missing": "M"}
    for row in data["assets"]:
        states = "/".join(short[row["views"][v]["binding_status"]] for v in VIEWS)
        lines.append(f"| {row['family']} / {row['asset_id']} | {row['reference_id'] or 'unresolved'} | {row['current']['stats_model_binding']} | {states} | {row['primary_task'] or 'see evidence index'} |")
    lines += ["", "## Per-model evidence", ""]
    for row in data["assets"]:
        lines += [f"### {row['asset_id']}", "", f"Reference: {row['reference_id'] or 'unresolved; no independent concept binding established'}. Current review: **unreviewed**.", ""]
        for label in ("source", "model", "stats"):
            f = row["current"][label]
            lines.append(f"- {label}: `{f['path']}` — {f['bytes']} bytes; SHA256 `{f['sha256']}` ({f['status']}).")
        lines += [f"- Engineering qualification: {row['engineering_refinement']}", f"- Warehouse binding: {row['current']['warehouse_binding_status']}; historical acceptance is separate from source binding."]
        for view in VIEWS:
            v = row["views"][view]
            lines.append(f"- {view}: **{v['binding_status']} / unreviewed**; " + ("; ".join(f"`{p}`" for p in v["candidate_paths"]) or "no explicit static-view candidate"))
        lines.append("- Native/runtime/task evidence: " + ("; ".join(f"`{p}`" for p in row["native_runtime_evidence"]) or "missing explicit evidence association"))
        lines.append("")
    lines += ["## Reproduce", "", "```powershell", ".venv/Scripts/python.exe tools/visual/v3/build_reference_render_matrix.py", ".venv/Scripts/python.exe tools/visual/v3/build_reference_render_matrix.py --check-only", "```", "", "Normal mode writes only this Markdown and its companion JSON. Check-only recomputes bytes without writes and fails on input/artifact drift. Stable paths/order/LF; no volatile build timestamp. Concurrent source/evidence changes can legitimately require regeneration. Root selects and visually reviews the current candidates; contact-sheet presence and historical PASS do not close Q01.", ""]
    return "\n".join(lines).encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    data = build()
    outputs = {OUTPUT_JSON: (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"), OUTPUT_MD: markdown(data)}
    drift = []
    for name, content in outputs.items():
        p = ROOT / name
        if args.check_only:
            if not p.is_file() or p.read_bytes() != content:
                drift.append(name)
        else:
            p.write_bytes(content)
    print(json.dumps({"mode": "check-only" if args.check_only else "write", "drift": drift, "outputs": {k: len(v) for k, v in outputs.items()}, "coverage": data["summary"]}, sort_keys=True))
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
