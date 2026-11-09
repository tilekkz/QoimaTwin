"""A public bind is always an explicit launch choice."""

import sys
from typing import Any

import pytest

from app.api.__main__ import main


def test_default_launch_binds_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, Any] = {}
    application = object()
    monkeypatch.setattr("app.api.__main__.create_app", lambda _: application)

    def run(app: object, *, host: str, port: int) -> None:
        called.update(app=app, host=host, port=port)

    monkeypatch.setattr("app.api.__main__.uvicorn.run", run)
    monkeypatch.setattr(sys, "argv", ["app.api"])
    main()
    assert called == {"app": application, "host": "127.0.0.1", "port": 8000}
