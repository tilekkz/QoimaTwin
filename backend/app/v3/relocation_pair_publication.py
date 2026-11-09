"""Host-only publication of already saved N1 pairs, without engine execution."""

import argparse
from pathlib import Path

from app.storage.artifacts import ArtifactStore
from app.storage.canonical_json import canonical_bytes
from app.v3.interface import Json
from app.v3.relocation_pair_publication_source import capture, validate
from app.v3.relocation_pair_publication_storage import publish


def publish_pair(pair_root: Path, store_root: Path) -> Json:
    source, target = pair_root.resolve(), store_root.resolve()
    if source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError("Saved relocation pair source and publication store must not overlap")
    saved = validate(capture(pair_root))
    return publish(ArtifactStore(store_root), saved)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("publish")
    command.add_argument("--pair", type=Path, required=True)
    command.add_argument("--store-root", type=Path, required=True)
    args = parser.parse_args()
    print(canonical_bytes(publish_pair(args.pair, args.store_root)).decode())


if __name__ == "__main__":
    main()
