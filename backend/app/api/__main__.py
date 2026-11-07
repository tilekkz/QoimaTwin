"""Loopback-first local API server; an external bind requires an explicit --host."""

import argparse
from pathlib import Path

import uvicorn

from app.api import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--store-root", type=Path)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in [1,65535]")
    uvicorn.run(create_app(args.store_root), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
