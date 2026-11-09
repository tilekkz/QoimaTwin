"""Project C09 manual mode intent only where source walk cargo metadata is absent."""

from typing import Any

ROUTE_POLICY = "c09-manual-small-source-mode-projection-v1"


def project_manual_cargo(links: dict[str, Any]) -> None:
    """Only use on a fresh decode of the compiler's independently verified pinned source."""
    for arc in links["walk_graph"]["arcs"]:
        if (
            "pedestrian" in arc.get("allowed_modes", [])
            and "allowed_cargo_archetype_ids" not in arc
            and "cargo_transport_supported" not in arc
        ):
            arc["allowed_cargo_archetype_ids"] = ["SMALL_CARTON"]
            arc["cargo_transport_supported"] = True
