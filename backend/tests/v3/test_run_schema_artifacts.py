"""Published schemas and source-demo fixture are reproducible review artifacts."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from app.v3.run_schema import schema
from app.v3.run_transport_schema import manifest_schema


def test_published_manual_schemas_match_executable_definitions() -> None:
    root = Path(__file__).parents[2] / "docs/proposals/adaptive-v3"
    for name, expected in (
        ("manual-run.schema.json", schema()),
        ("manual-manifest.schema.json", manifest_schema()),
    ):
        value = json.loads((root / name).read_text(encoding="utf-8"))
        assert value == expected
        Draft202012Validator.check_schema(value)
