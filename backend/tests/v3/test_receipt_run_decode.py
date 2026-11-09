"""Native JSON reuse never executes objects or coerces booleans into physical integers."""

from copy import deepcopy

import pytest

from app.storage.canonical_json import canonical_bytes
from app.v3.flow_profile_wire import record
from app.v3.receipt_run import build_receipt_run
from app.v3.receipt_run_decode import decode_outcome
from tests.v3.test_receipt_run_fixtures import sample


def test_native_record_roundtrip_retains_receipt_delta_subtypes() -> None:
    inputs, outcome = sample()
    decoded = decode_outcome(record(outcome))
    assert canonical_bytes(record(decoded)) == canonical_bytes(record(outcome))
    assert build_receipt_run(inputs, decoded) == build_receipt_run(inputs, outcome)


@pytest.mark.parametrize("field", ["tick", "extra", "rational"])
def test_native_decoder_rejects_type_aliases_and_unknown_fields(field: str) -> None:
    value = deepcopy(record(sample()[1]))
    if field == "tick":
        value["checkpoints"][0]["tick"] = False
    elif field == "extra":
        value["events"][0]["untrusted_type"] = "execute"
    else:
        value["at_end"]["balance"]["onsite_mass_kg"]["denominator"] = True
    with pytest.raises(ValueError):
        decode_outcome(value)
