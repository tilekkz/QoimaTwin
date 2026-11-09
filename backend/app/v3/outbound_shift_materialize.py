"""One postshift offered stream, frozen before either future comparison arm."""

from hashlib import sha256

from app.storage.canonical_json import canonical_bytes
from app.v3.outbound_shift_models import INPUT_SCOPE, INPUT_VERSION, N1Scenario, OutboundShiftInputs
from app.v3.outbound_shift_wire import scenario_dict
from app.v3.workload_materialize import materialize_workload
from app.v3.workload_models import WorkloadPolicy
from app.v3.workload_wire import policy_dict, workload_dict


def _materialize(scenario: N1Scenario, policy: WorkloadPolicy) -> OutboundShiftInputs:
    """Internal only: the public compiler supplies freshly authenticated source facts."""
    workload = materialize_workload(scenario.postshift, policy)
    scenario_value, choices, offered = (
        scenario_dict(scenario),
        policy_dict(policy),
        workload_dict(workload),
    )
    frozen = canonical_bytes(
        {
            "schema_version": INPUT_VERSION,
            "scope": INPUT_SCOPE,
            "scenario": scenario_value,
            "choices": choices,
            "workload": offered,
            "operational_admission": False,
            "full_n1_acceptance": False,
        }
    )
    return OutboundShiftInputs(
        scenario,
        policy,
        workload,
        canonical_bytes(scenario_value),
        canonical_bytes(choices),
        canonical_bytes(offered),
        frozen,
        sha256(frozen).hexdigest(),
    )
