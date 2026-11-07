"""Exclusive raw-byte publication and bounded half-open manual timeline chunks."""

from collections.abc import Iterator
from hashlib import sha256
from os import link
from pathlib import Path
from uuid import uuid4

from app.storage.canonical_json import canonical_bytes
from app.v3.interface import Json


def publish(root: Path, relative: str, raw: bytes) -> Json:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(raw)
        link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return {"path": relative, "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def _batches(rows: list[Json], interval: int, maximum: int) -> Iterator[tuple[int, list[Json]]]:
    bucket, size = -1, 12
    batch: list[Json] = []
    for row in rows:
        number = row["tick"] // interval
        length = len(canonical_bytes(row))
        if length + 12 > maximum:
            raise ValueError("one manual timeline item exceeds the raw chunk byte limit")
        if batch and (number != bucket or size + length + 1 > maximum):
            yield bucket, batch
            size, batch = 12, []
        size += length + int(bool(batch))
        bucket = number
        batch.append(row)
    if batch:
        yield bucket, batch


def chunks(root: Path, kind: str, rows: list[Json], interval: int, maximum: int) -> list[Json]:
    result = []
    for ordinal, (bucket, batch) in enumerate(_batches(rows, interval, maximum)):
        raw = canonical_bytes({"items": batch})
        descriptor = publish(root, f"{kind}/{ordinal:06}.json", raw)
        descriptor.update(
            {
                "start_tick": bucket * interval,
                "end_tick": (bucket + 1) * interval,
                "first_tick": batch[0]["tick"],
                "last_tick": batch[-1]["tick"],
            }
        )
        result.append(descriptor)
    return result
