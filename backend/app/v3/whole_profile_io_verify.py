"""A request receipt proves choices-to-input binding, not two independently supplied hashes."""

from hashlib import sha256

from app.v3.whole_profile_io import COMPILER_VERSION, CompiledWholeProfile, _compile_source_bytes
from app.v3.whole_run_inputs import WholeRunInputs, verify_inputs


def verify_compiled(compiled: CompiledWholeProfile) -> None:
    _types(compiled)
    if (
        compiled.compiler_version != COMPILER_VERSION
        or sha256(compiled.choices_bytes).hexdigest() != compiled.choices_sha256
    ):
        raise ValueError("Public whole compiler identity differs")
    inputs = compiled.run_inputs
    verify_inputs(inputs)
    if _compile_source_bytes(compiled.choices_bytes) != inputs.frozen_bytes:
        raise ValueError("Public whole choices differ from the actual compiled source inputs")


def _types(compiled: CompiledWholeProfile) -> None:
    if type(compiled) is not CompiledWholeProfile:
        raise ValueError("Exact public whole compiled record type required")
    if (
        type(compiled.choices_bytes) is not bytes
        or type(compiled.choices_sha256) is not str
        or type(compiled.compiler_version) is not str
    ):
        raise ValueError("Exact public whole identity scalar types required")
    inputs = compiled.run_inputs
    if type(inputs) is not WholeRunInputs or (
        type(inputs.frozen_bytes) is not bytes
        or type(inputs.input_hash) is not str
        or type(inputs.physical_input_hash) is not str
        or type(inputs.horizon_tick) is not int
        or type(inputs.end_tick) is not int
    ):
        raise ValueError("Exact whole input envelope scalar types required")
