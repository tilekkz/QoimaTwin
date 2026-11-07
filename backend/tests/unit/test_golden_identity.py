"""Identity oracles use source contracts and literal canonical bytes, never engine output."""

import hashlib
from dataclasses import replace
from pathlib import Path

from app.contracts.loader import ContractBundle
from app.contracts.scenario import Provenance
from app.exporter.identity import fingerprint
from app.simulation.fixtures import fixture_inputs, load_fixture
from tests.golden_identity_oracle import build_fingerprint


def test_complete_fixture_identity_matches_input_only_oracle(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    assert fingerprint(inputs) == build_fingerprint(contracts_dir)


def test_provenance_hash_has_a_hand_written_canonical_preimage(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    provenance = Provenance(
        kind="synthetic_fixture",
        generator_version="manual-oracle",
        seed=7,
        source_notes="manual",
        orders_sha256="0" * 64,
        receipts_sha256="1" * 64,
    )
    changed = replace(
        inputs, scenario=inputs.scenario.model_copy(update={"provenance": provenance})
    )
    expected = (
        b'{"generator_version":"manual-oracle","kind":"synthetic_fixture","orders_sha256":"'
        + b"0" * 64
        + b'","receipts_sha256":"'
        + b"1" * 64
        + b'","seed":7,"source_notes":"manual"}'
    )
    assert fingerprint(changed)["provenance_sha256"] == hashlib.sha256(expected).hexdigest()


def test_absent_plan_and_forecast_are_hashes_of_literal_null(
    bundle: ContractBundle, contracts_dir: Path
) -> None:
    inputs = fixture_inputs(bundle, load_fixture(contracts_dir))
    hashes = fingerprint(inputs)["hashes"]
    expected = hashlib.sha256(b"null").hexdigest()
    assert hashes["relocation_plan"] == hashes["forecast_snapshot"] == expected
