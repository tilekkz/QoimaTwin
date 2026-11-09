# Conditional F02/FL02 body fit

This opt-in pure geometry seam verifies the original outbound pair against the
actual source worker and vehicle meshes. It grants no operation or initial state.

```python
from pathlib import Path

from app.v3.pallet_operator_fit_source import load_operator_fit_source
from app.v3.pallet_operator_fit_verify import certify_operator_fit, verify_operator_fit_certificate
from app.v3.pallet_outbound_pickup_plan import compile_pickup_plan

backend = Path("backend")
source = load_operator_fit_source(
    backend / "data", backend / "docs/proposals/pallet-operator-fit-v1"
)
plan = compile_pickup_plan(source.pickup)
result = certify_operator_fit(source, plan)
fresh = verify_operator_fit_certificate(source, plan, result)
```

Both roots locate exact pinned raw bytes. Source identity does not depend on the
host path, and a changed file cannot be admitted by changing its supplied hash.
The result binds all original source documents, raw worker mesh/provenance, exact
F02/FL02 IDs, pickup plan, five actual anchors, finite seat/boot contact patches,
body/vehicle clearance, source headroom, seated portal projection and all six
relative component-motion intervals. Certificate verification recomputes every
check, then compares types as well as values.

The conditional root world position is a rigid derivation, not evidence that F02
has approached, boarded or occupied FL02. Full-body static clearance and continuous
carriage/reach/fork plus wheel envelope checks do not certify cargo/body clearance,
driving/steering, dynamic restraint or the full pickup/route. The result's four
admission/initial-state/boarding/travel flags stay false. See ADR0082 for exact
source and policy boundaries; earlier pickup limitations remain in force.
