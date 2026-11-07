"""The application serves the pinned V3 proposal alongside the existing V2 API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app


def test_api_exposes_v3_without_switching_v2(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    response = client.get("/api/v3/catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert catalog["schema_id"] == "qoima.catalog.v3-proposal"
    assert not catalog["capabilities"]["actual_engine_run"]
    assert client.get("/api/v3/initial-state").status_code == 200
    v2 = client.get("/api/catalog")
    assert v2.status_code == 200
    assert "qoima-72x48-v2" in v2.text


def test_api_rejects_missing_explicit_v3_package(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        create_app(tmp_path / "store", v3_inputs=tmp_path / "missing")
