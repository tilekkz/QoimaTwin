"""Every N1 input and behavior policy participates in its separate native identity."""

from hashlib import sha256

from app.storage.canonical_json import canonical_bytes
from app.v3.relocation_metrics import METRICS_VERSION
from app.v3.relocation_models import RELOCATION_VERSION
from app.v3.relocation_run_schema import PUBLICATION_VERSION


def run_identity(input_hash: str) -> str:
    return sha256(
        canonical_bytes(
            {
                "engine_version": RELOCATION_VERSION,
                "publication_version": PUBLICATION_VERSION,
                "metrics_version": METRICS_VERSION,
                "input_hash": input_hash,
            }
        )
    ).hexdigest()
