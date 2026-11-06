"""Load and schema-validate the shared contract files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
from pydantic import ValidationError

from app.contracts.actors import ActorRegistry
from app.contracts.config import SimulationConfig
from app.contracts.layout import Layout

LAYOUT_FILE = "layout.example.json"
ACTORS_FILE = "actors.example.json"
CONFIG_FILE = "simulation_defaults.json"

SCHEMA_PAIRS: tuple[tuple[str, str], ...] = (
    (LAYOUT_FILE, "layout.schema.json"),
    (ACTORS_FILE, "actors.schema.json"),
)
SCHEMA_ONLY: tuple[str, ...] = ("run.schema.json", "scenario.schema.json")


class ContractError(Exception):
    """A contract file is missing, unreadable, or violates its schema or model."""


@dataclass(frozen=True, slots=True)
class ContractBundle:
    directory: Path
    layout: Layout
    config: SimulationConfig
    actors: ActorRegistry


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"{path.name}: file not found in {path.parent}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"{path.name}: invalid JSON at line {exc.lineno}: {exc.msg}") from exc


def _check_schemas(directory: Path) -> None:
    for data_name, schema_name in SCHEMA_PAIRS:
        schema = _read_json(directory / schema_name)
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(_read_json(directory / data_name)), key=str)
        if errors:
            first = errors[0]
            location = "/".join(str(part) for part in first.absolute_path)
            raise ContractError(f"{data_name}: schema violation at '{location}': {first.message}")
    for schema_name in SCHEMA_ONLY:
        try:
            jsonschema.Draft202012Validator.check_schema(_read_json(directory / schema_name))
        except jsonschema.SchemaError as exc:
            raise ContractError(f"{schema_name}: invalid JSON Schema: {exc.message}") from exc


def _parse[ModelT: (Layout, SimulationConfig, ActorRegistry)](
    model: type[ModelT], path: Path
) -> ModelT:
    try:
        return model.from_json_text(path.read_bytes())
    except ValidationError as exc:
        raise ContractError(
            f"{path.name}: {exc.error_count()} model errors; first: {exc.errors()[0]}"
        ) from exc


def load_contract_bundle(directory: Path) -> ContractBundle:
    """Load layout, config and actors; validate them against JSON Schema and typed models."""
    if not directory.is_dir():
        raise ContractError(f"contracts directory not found: {directory}")
    _check_schemas(directory)
    return ContractBundle(
        directory=directory,
        layout=_parse(Layout, directory / LAYOUT_FILE),
        config=_parse(SimulationConfig, directory / CONFIG_FILE),
        actors=_parse(ActorRegistry, directory / ACTORS_FILE),
    )
