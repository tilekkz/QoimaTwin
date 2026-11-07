"""Standalone read-only V3 router, explicitly separate from the V2 experiment API."""

from hashlib import sha256
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response

from app.storage.canonical_json import canonical_bytes
from app.v3.export import build_static_export
from app.v3.interface import CatalogSource, canonical_documents


def create_v3_router(bundle: CatalogSource) -> APIRouter:
    value = build_static_export(bundle)
    catalog, stock = canonical_bytes(value["catalog"]), canonical_bytes(value["initial_state"])
    documents = canonical_documents(bundle)
    router = APIRouter(prefix="/api/v3", tags=["V3 static proposal"])

    @router.get("/catalog")
    async def catalog_endpoint() -> Response:
        return _json(catalog)

    @router.get("/initial-state")
    async def initial_state_endpoint() -> Response:
        return _json(stock)

    @router.get("/documents/{artifact_id}")
    async def source_document(
        artifact_id: Annotated[str, Path(pattern=r"^[0-9a-f]{64}$")],
    ) -> Response:
        if artifact_id not in documents:
            raise HTTPException(status_code=404, detail="Unknown source document")
        return _json(documents[artifact_id])

    return router


def _json(raw: bytes) -> Response:
    return Response(
        raw,
        media_type="application/json",
        headers={
            "ETag": f'"{sha256(raw).hexdigest()}"',
            "Cache-Control": "public, max-age=0, must-revalidate",
        },
    )
