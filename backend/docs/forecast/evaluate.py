"""One reproducible synthetic56-day evaluation; run python -m docs.forecast.evaluate."""

from __future__ import annotations

import json
from pathlib import Path

from app.data.history import history_artifact
from app.forecast import fit_forecast, read_csv


def main() -> None:
    output = Path("docs/forecast/results")
    output.mkdir(parents=True, exist_ok=True)
    history_path = Path("artifacts/forecast-history.csv")
    history_path.parent.mkdir(parents=True, exist_ok=True)
    source = history_artifact()
    history_path.write_bytes(source.csv_bytes)
    history = read_csv(history_path)
    assert history.source_sha256 == source.sha256
    for model in ("mean28", "hgb"):
        snapshot = fit_forecast(history, model)
        payload = snapshot.to_dict()
        (output / f"{model}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "model": model,
                    "wape": snapshot.validation.wape,
                    "cpu_time_s": snapshot.cpu_time_s,
                    "semantic_id": snapshot.semantic_id,
                    "source_sha256": source.sha256,
                    "history_hash": history.history_hash,
                }
            )
        )


if __name__ == "__main__":
    main()
