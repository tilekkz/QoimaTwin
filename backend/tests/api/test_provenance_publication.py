"""Public provenance revisions cannot collide in immutable run storage."""

import dataclasses
from pathlib import Path

from app.api.publication import publish_run
from app.contracts.loader import ContractBundle
from app.simulation.engine import Engine
from app.storage.artifacts import ArtifactStore
from tests.builders import run_inputs, scenario


def test_changed_provenance_publishes_distinct_immutable_manifests(
    tmp_path: Path,
    bundle: ContractBundle,
    contracts_dir: Path,
) -> None:
    inputs = run_inputs(bundle, contracts_dir, scenario([], horizon_s=1))
    updated = inputs.scenario.model_copy(
        update={
            "provenance": inputs.scenario.provenance.model_copy(
                update={"source_notes": "independent revised provenance"}
            )
        }
    )
    store, identifiers = ArtifactStore(tmp_path), []
    for current in (inputs, dataclasses.replace(inputs, scenario=updated)):
        engine = Engine(current, check_invariants=True)
        identifiers.append(publish_run(store, engine, engine.run()))
    assert len(set(identifiers)) == 2
    notes = [
        store.read_reference("runs", identifier)["provenance"]["source_notes"]
        for identifier in identifiers
    ]
    assert notes == [inputs.scenario.provenance.source_notes, "independent revised provenance"]
