"""Publish a bound public request before DES and preserve it on execution failure."""

from hashlib import sha256
from pathlib import Path

from app.errors import OutputNotEmptyError, require_empty_output
from app.storage.canonical_json import canonical_bytes
from app.v3.interface import Json
from app.v3.run_publication import publish
from app.v3.whole_profile_io import CompiledWholeProfile
from app.v3.whole_profile_io_verify import verify_compiled

REQUEST_VERSION = "qoima-whole-cli-request-0.1.0"


def reserve(out: Path) -> None:
    if out.is_symlink():
        raise OutputNotEmptyError("Whole output must not be a symbolic link")
    require_empty_output(out)


def freeze_request(compiled: CompiledWholeProfile, out: Path) -> str:
    reserve(out)
    verify_compiled(compiled)
    inputs = compiled.run_inputs
    profile = publish(out, "profile.json", compiled.choices_bytes)
    request = {
        "request_version": REQUEST_VERSION,
        "compiler_version": compiled.compiler_version,
        "choices_sha256": compiled.choices_sha256,
        "profile": profile,
        "input_hash": inputs.input_hash,
        "physical_input_hash": inputs.physical_input_hash,
        "horizon_tick": inputs.horizon_tick,
        "end_tick": inputs.end_tick,
        "inputs_path": "run/inputs.json",
    }
    raw = canonical_bytes(request)
    publish(out, "request.json", raw)
    publish(out / "run", "inputs.json", inputs.frozen_bytes)
    return sha256(raw).hexdigest()


def finish(out: Path, request_hash: str, report: Json) -> Json:
    report.update(
        request_sha256=request_hash,
        request=str(out / "request.json"),
        layout_version="qoima-144x72-v3-proposal",
        operational_admission=False,
    )
    publish(out, "result.json", canonical_bytes(report))
    return report
