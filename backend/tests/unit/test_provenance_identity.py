"""Public provenance participates in immutable publication identity."""

from dataclasses import replace
from pathlib import Path

from app.contracts.loader import ContractBundle
from app.exporter.identity import fingerprint
from app.simulation.fixtures import fixture_inputs, load_fixture
from app.storage.canonical_json import sha256_hex


def test_provenance_revision_changes_identity(bundle: ContractBundle, contracts_dir: Path) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    revised = inputs.scenario.provenance.model_copy(update={"source_notes": "Reviewed provenance"})
    changed = replace(inputs, scenario=inputs.scenario.model_copy(update={"provenance": revised}))
    first, second = fingerprint(inputs), fingerprint(changed)
    assert first != second
    assert first["hashes"] == second["hashes"]
    assert first["identity_version"] == "qoima-run-v2"
    assert second["provenance_sha256"] == sha256_hex(revised.model_dump(mode="json"))


def test_identical_provenance_remains_stable(bundle: ContractBundle, contracts_dir: Path) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    same = replace(inputs, scenario=inputs.scenario.model_copy(deep=True))
    assert fingerprint(inputs) == fingerprint(same)
