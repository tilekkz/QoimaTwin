"""Normal CLI argument dispatch with tiny pinned files; no external execution."""

from pathlib import Path

import pytest

from app.storage.canonical_json import parse_json
from app.v3 import physical_handoff_cli as cli
from app.v3 import physical_handoff_source as source
from tests.v3.test_physical_handoff_source import Packet
from tests.v3.test_physical_handoff_source import packet as packet


def test_cli_writes_only_small_report_and_manifest(packet: Packet, tmp_path: Path) -> None:
    out = tmp_path / "result"
    assert cli.main(["validate", "--assets-root", str(packet.root), "--out", str(out)]) == 0
    assert {p.name for p in out.iterdir()} == {"report.json", "manifest.json"}
    report = parse_json((out / "report.json").read_bytes())
    manifest = parse_json((out / "manifest.json").read_bytes())
    assert report["operational_admission"] is False
    assert manifest["input_hash"] == source.load_physical_handoff(packet.root).input_hash
    assert manifest["validation_scope"] == "reference_only"


def test_existing_output_even_empty_is_never_claimed(packet: Packet, tmp_path: Path) -> None:
    out = tmp_path / "existing"
    out.mkdir()
    assert cli.main(["validate", "--assets-root", str(packet.root), "--out", str(out)]) == 1
    assert list(out.iterdir()) == []


@pytest.mark.parametrize("location", ["inside", "same", "parent"])
def test_output_cannot_overlap_input_tree(packet: Packet, location: str) -> None:
    out = {"inside": packet.root / "new", "same": packet.root, "parent": packet.root.parent}[
        location
    ]
    before = {
        p.relative_to(packet.root): p.read_bytes() for p in packet.root.rglob("*") if p.is_file()
    }
    assert cli.main(["validate", "--assets-root", str(packet.root), "--out", str(out)]) == 1
    assert before == {
        p.relative_to(packet.root): p.read_bytes() for p in packet.root.rglob("*") if p.is_file()
    }


def test_failed_validation_keeps_error_without_success_manifest(
    packet: Packet, tmp_path: Path
) -> None:
    (packet.root / "source.json").write_bytes(b"wrong")
    out = tmp_path / "failed"
    assert cli.main(["validate", "--assets-root", str(packet.root), "--out", str(out)]) == 1
    assert {p.name for p in out.iterdir()} == {"failure.json"}
    assert parse_json((out / "failure.json").read_bytes())["status"] == "failed"


def test_atomic_output_claim_precedes_loader(
    packet: Packet, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "claimed"
    out.mkdir()
    monkeypatch.setattr(cli, "load_physical_handoff", lambda root: pytest.fail("loader called"))
    assert cli.main(["validate", "--assets-root", str(packet.root), "--out", str(out)]) == 1


def test_repeat_publish_does_not_clobber(packet: Packet, tmp_path: Path) -> None:
    out = tmp_path / "once"
    argv = ["validate", "--assets-root", str(packet.root), "--out", str(out)]
    assert cli.main(argv) == 0
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    assert cli.main(argv) == 1
    assert before == {p.name: p.read_bytes() for p in out.iterdir()}
