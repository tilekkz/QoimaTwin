"""Small independent subprocess entry point for hash-seed and python -O checks."""

from __future__ import annotations

import argparse
import json
from typing import Any

from app.contracts.assignment import Assignment
from app.contracts.loader import load_contract_bundle
from app.data.scenario_materializer import Profile, materialize
from app.exporter.run import export_run
from app.settings import default_contracts_dir
from app.simulation.context import RunInputs
from app.simulation.engine import Engine, RunStatus
from app.simulation.fixtures import fixture_inputs, load_fixture
from app.storage.canonical_json import sha256_hex


def probe(profile: Profile | None = None, horizon_s: int = 600) -> dict[str, Any]:
    contracts = default_contracts_dir()
    bundle = load_contract_bundle(contracts)
    if profile is None:
        inputs = fixture_inputs(bundle, load_fixture(contracts))
    else:
        assignment = Assignment.from_json_text((contracts / "assignment.example.json").read_bytes())
        inputs = RunInputs(
            bundle.layout,
            bundle.config,
            bundle.actors,
            assignment,
            materialize(profile, horizon_s, bundle.config).scenario,
        )
    engine = Engine(inputs, check_invariants=True)
    outcome = engine.run()
    if outcome.status is not RunStatus.COMPLETE or engine.ctx.ledger.check_conservation():
        raise RuntimeError("subprocess smoke did not drain with conserved inventory")
    if profile is None and engine.ctx.grid.seconds(outcome.end_tick) != 474:
        raise RuntimeError("analytical fixture return differs from hand-derived 474 seconds")
    run = export_run(engine, outcome)
    return {"run_id": run["run_id"], "events_sha256": sha256_hex(run["events"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture", action="store_true")
    mode.add_argument("--profile", choices=("large-normal", "large-peak", "promotion"))
    parser.add_argument("--horizon-s", type=int, default=600)
    args = parser.parse_args()
    print(json.dumps(probe(args.profile, args.horizon_s), sort_keys=True))


if __name__ == "__main__":
    main()
