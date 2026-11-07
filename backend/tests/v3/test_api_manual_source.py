"""One actual-source endpoint run with real spawn, immutable reuse and repeatable seek."""

from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import create_app
from app.api.processor import ProcessProcessor
from app.storage.artifacts import ArtifactStore


def test_actual_source_endpoint_publication_and_restart(tmp_path: Path) -> None:
    from app.v3.run_transport import read_manual_run  # frozen dependency must exist

    assert callable(read_manual_run)
    processor = ProcessProcessor()
    try:
        with TestClient(create_app(tmp_path, processor=processor)) as client:
            metadata = client.get("/api/v3/manual-profiles").json()["profiles"][0]
            body = {k: metadata[k] for k in ("profile", "layout_version", "source_revision")}
            first = client.post("/api/v3/manual-runs", json=body)
            assert first.status_code == 200, first.text
            result = first.json()
            assert result["status"] == "complete"
            assert result["source_label"] == "actual_engine_run"
            assert result["full_v3_warehouse"] is result["frontend_adapter"] is False
            base = f"/api/v3/manual-runs/{result['run_id']}"
            manifest = client.get(f"{base}/manifest").json()
            for row in manifest["files"]:
                raw = client.get(f"{base}/files/{row['sha256']}")
                assert raw.status_code == 200
                assert len(raw.content) == row["bytes"]
                assert sha256(raw.content).hexdigest() == row["sha256"]
            seek_url = f"{base}/seek?cutoff_tick=600000000"
            a, b = client.get(seek_url), client.get(seek_url)
            assert a.status_code == 200 and a.json() == b.json()
            assert client.get(f"{base}/seek?cutoff_tick=-1").status_code == 422
            assert client.get(f"{base}/seek?cutoff_tick=9999999999").status_code == 422
            assert client.get(f"{base}/files/{'f' * 64}").status_code == 404
            assert processor.last_worker_pid is not None
        with TestClient(create_app(tmp_path, processor=processor)) as restarted:
            assert restarted.post("/api/v3/manual-runs", json=body).json() == result
        store = ArtifactStore(tmp_path)
        row = manifest["files"][0]
        store.path("run_files", row["sha256"]).write_bytes(b"corrupt")
        with TestClient(
            create_app(tmp_path, processor=processor), raise_server_exceptions=False
        ) as restarted:
            assert restarted.post("/api/v3/manual-runs", json=body).status_code == 500
    finally:
        processor.pool.shutdown(wait=True)
