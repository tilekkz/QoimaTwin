"""Input and version identity is separate from the bounded common registry fingerprint."""

from app.storage.canonical_json import sha256_hex
from app.v3 import coordinator_metrics
from app.v3.coordinator_models import COORDINATOR_VERSION
from app.v3.coordinator_run_schema import PUBLICATION_VERSION


def run_identity(input_hash: str) -> str:
    if type(input_hash) is not str or len(input_hash) != 64:
        raise ValueError("Coordinator input identity requires an exact SHA256")
    if any(c not in "0123456789abcdef" for c in input_hash):
        raise ValueError("Coordinator input identity requires lowercase hexadecimal")
    return sha256_hex(
        {
            "engine_version": COORDINATOR_VERSION,
            "publication_version": PUBLICATION_VERSION,
            "metrics_version": coordinator_metrics.METRICS_VERSION,
            "input_hash": input_hash,
        }
    )
