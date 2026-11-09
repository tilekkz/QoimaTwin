"""Publish all referenced run files before an immutable manifest becomes readable."""

from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from app.exporter.identity import fingerprint
from app.exporter.run import export_run, write_run
from app.simulation.engine import Engine, RunOutcome
from app.simulation.metrics_summary import summary
from app.storage.artifacts import ArtifactCorruption, ArtifactStore


def publish_run(
    store: ArtifactStore, engine: Engine, outcome: RunOutcome, output_format: str = "2.0"
) -> str:
    exporter, writer = export_run, write_run
    if output_format == "2.1-proposal":
        proposal = import_module("app.exporter.proposal")
        exporter, writer = proposal.export_proposal, proposal.write_proposal_run
    elif output_format != "2.0":
        raise ValueError("unsupported API output_format")
    run = exporter(engine, outcome, validate=False)
    with TemporaryDirectory(prefix="qoima-api-run-") as temporary:
        directory = Path(temporary)
        manifest = writer(
            run,
            directory,
            metadata={
                "identity": run.get("identity", fingerprint(engine.ctx.inputs)),
                "ended_at_s": outcome.end_tick / engine.ctx.grid.ticks_per_second,
                "metrics": summary(engine, outcome),
                "provenance": engine.ctx.inputs.scenario.provenance.model_dump(mode="json"),
                "ticks_per_second": engine.ctx.grid.ticks_per_second,
            },
        )
        references = [
            manifest["catalog"],
            *manifest.get("chunks", []),
            *manifest.get("event_chunks", []),
            *manifest.get("snapshot_chunks", []),
        ]
        if "inline" in manifest:
            references.append(manifest["inline"])
        for reference in references:
            path = (directory / reference["path"]).resolve()
            if not path.is_relative_to(directory.resolve()):
                raise ArtifactCorruption("exported reference escapes its bundle")
            raw = path.read_bytes()
            identifier = store.put_bytes("run_files", raw)
            if identifier != reference["sha256"] or len(raw) != reference["bytes"]:
                raise ArtifactCorruption("exported reference hash or length mismatch")
        store.publish_reference("runs", run["run_id"], manifest)
    return str(run["run_id"])
