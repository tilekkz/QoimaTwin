"""Normal file-driven producer chain; preserve partial evidence on any failure."""

from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any

from app.storage.canonical_json import canonical_bytes
from app.v3.forecast_placement_decision import prepare_forecast_placement_decision
from app.v3.forecast_stock_binding import bind_forecast_stock
from app.v3.offer_forecast import fit_offer_forecast
from app.v3.offer_history import compile_offer_history
from app.v3.offer_planning_cli_choices import decode_request_choices
from app.v3.offer_planning_cli_models import PlanningFiles
from app.v3.offer_planning_cli_storage import freeze_request, prepare_output, put
from app.v3.offer_planning_cli_wire import manifest_record, producer_bytes, result_record
from app.v3.offer_projection_inputs import compile_offer_projection


def _calculate(root: Path, model: str, raw: dict[str, bytes], request: bytes) -> dict[str, Any]:
    choices = decode_request_choices(raw)
    started = perf_counter()
    history = compile_offer_history(raw["history.csv"], choices.history)
    put(root, "history.json", history.frozen_bytes)
    forecast = fit_offer_forecast(history, model)
    put(root, "forecast.json", forecast.frozen_bytes)
    projection = compile_offer_projection(forecast, choices.projection)
    put(root, "projection.json", projection.frozen_bytes)
    stock = bind_forecast_stock(projection)
    put(root, "stock.json", stock.frozen_bytes)
    decision = prepare_forecast_placement_decision(stock, choices.placement)
    put(root, "decision.json", decision.frozen_bytes)
    actual = {
        "history": history.frozen_bytes,
        "forecast": forecast.frozen_bytes,
        "projection": projection.frozen_bytes,
        "stock": stock.frozen_bytes,
        "decision": decision.frozen_bytes,
    }
    if actual != producer_bytes(decision):
        raise ValueError("Producer stages do not retain the same exact chain")
    observations = canonical_bytes(
        {
            "version": "qoima-offer-planning-observations-0.1.0",
            "planning_elapsed_s": perf_counter() - started,
            "forecast_cpu": asdict(forecast.measurements),
            "benchmark_claim": False,
        }
    )
    put(root, "observations.json", observations)
    manifest = manifest_record(decision, request, observations)
    wire = canonical_bytes(manifest)
    put(root, "manifest.json", wire)
    return result_record(manifest, wire)


def plan_offer_files(paths: PlanningFiles, model: str, output: Path) -> dict[str, Any]:
    prepare_output(output)
    try:
        raw, request = freeze_request(paths, model, output)
        return _calculate(output, model, raw, request)
    except Exception as exc:
        failure = {
            "status": "failed",
            "scope": "incomplete_planning_attempt",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "valid_manifest": False,
            "operational_admission": False,
        }
        if not (output / "manifest.json").exists():
            put(output, "failure.json", canonical_bytes(failure))
        raise
