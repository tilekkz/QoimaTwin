"""Warm semantic summaries retain public registration, inventory and raw-byte authority."""

from pathlib import Path

import pytest

from app.storage.artifacts import ArtifactCorruption
from app.v3 import api_receipt_readers as readers
from app.v3.api_receipt_identity import public_run_id
from tests.v3.test_api_receipt_independent_fixtures import registered_hand, replace_run_index


def test_a_canonical_public_id_for_another_bundle_cannot_use_this_registration(
    tmp_path: Path,
) -> None:
    hand = registered_hand(tmp_path)
    identifier = hand.response["run_id"]
    index, _ = readers.verified_artifact(hand.store, identifier, hand.frozen)
    other = hand.store.put_json("bundles", {"scope": "different_internal_hand_registration"})
    alternate = public_run_id(index["native_run_id"], other)
    index.update(run_id=alternate, input_bundle_id=other)
    hand.store.publish_reference("runs", alternate, index)
    assert alternate != identifier
    with pytest.raises(ArtifactCorruption, match="registered profile or native identity"):
        readers.status(hand.store, alternate, hand.frozen)


@pytest.mark.parametrize("mutation", ["inventory", "registration_bytes"])
def test_warm_summary_cannot_hide_rehashed_inventory_or_source_byte_changes(
    tmp_path: Path, mutation: str
) -> None:
    hand = registered_hand(tmp_path)
    identifier = hand.response["run_id"]
    index, _ = readers.verified_artifact(hand.store, identifier, hand.frozen)
    assert readers.status(hand.store, identifier, hand.frozen) == hand.response
    if mutation == "inventory":
        index["files"] = [row for row in index["files"] if row["path"] != "catalog.json"]
        replace_run_index(hand.store, identifier, index)
    else:
        path = hand.store.path("run_files", hand.evidence_hash)
        original = path.read_bytes()
        path.write_bytes(original.replace(b"internal", b"external"))
        assert path.stat().st_size == len(original)
    with pytest.raises(ArtifactCorruption):
        readers.verify_result(hand.store, hand.response, hand.frozen)
