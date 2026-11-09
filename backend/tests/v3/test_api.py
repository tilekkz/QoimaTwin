"""Standalone V3 router must not advertise execution or leak local source paths."""

import hashlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v3.api import create_v3_router
from tests.v3.test_interface_sources import small_bundle


def test_catalog_initial_stock_and_document_endpoint_are_versioned_and_immutable() -> None:
    app = FastAPI()
    app.include_router(create_v3_router(small_bundle()))
    with TestClient(app) as client:
        catalog = client.get("/api/v3/catalog")
        assert catalog.status_code == 200
        data = catalog.json()
        assert data["capabilities"]["actual_engine_run"] is False
        assert "D:/" not in catalog.text and "C:/" not in catalog.text
        stock = client.get("/api/v3/initial-state")
        assert stock.status_code == 200
        assert stock.json()["totals"]["quantity_units"] == 4
        ref = data["source"]["documents"][0]
        response = client.get("/api/v3/documents/" + ref["canonical_sha256"])
        assert response.status_code == 200
        assert hashlib.sha256(response.content).hexdigest() == ref["canonical_sha256"]
        assert response.headers["etag"] == '"' + ref["canonical_sha256"] + '"'
        assert client.get("/api/v3/documents/" + "0" * 64).status_code == 404
        assert client.get("/api/v3/documents/not-a-hash").status_code == 422
        assert client.post("/api/v3/compare", json={}).status_code == 404
