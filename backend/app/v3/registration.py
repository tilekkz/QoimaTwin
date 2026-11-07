"""Build the immutable packaged catalog once per API process."""

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, FastAPI

from app.v3.api import create_v3_router
from app.v3.inputs import load_v3_bundle
from app.v3.settings import default_inputs


@lru_cache(maxsize=1)
def _packaged_router() -> APIRouter:
    return create_v3_router(load_v3_bundle(default_inputs()))


def attach_v3_routes(app: FastAPI, source_path: Path | None) -> None:
    router = (
        _packaged_router() if source_path is None else create_v3_router(load_v3_bundle(source_path))
    )
    app.include_router(router)
