"""Location of the reviewed V3 source package shipped with this backend."""

from pathlib import Path


def default_inputs() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "v3-proposal"
