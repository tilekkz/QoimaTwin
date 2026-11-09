# E011 pickup to loaded prehandle

This finite geometry proposal binds original `DEMO_172:01`, source owner
`HEAVY_E:011:L1:B1` and outbound F02/FL02 to one proposed pickup sequence.
It does not enable an outbound runtime job. See ADR0079 for exact authority,
numerical policy and retained failure cases.

```python
from pathlib import Path

from app.v3.pallet_outbound_pickup_plan import compile_pickup_plan
from app.v3.pallet_outbound_pickup_source import load_pickup_source
from app.v3.pallet_outbound_pickup_verify import (
    certify_pickup,
    verify_pickup_certificate,
)

source = load_pickup_source(Path("data"))
plan = compile_pickup_plan(source)
certificate = certify_pickup(source, plan)
verify_pickup_certificate(source, plan, certificate)
assert certificate.operational_admission is False
assert certificate.positive_fore_aft_clearance is False
```

Only these source/plan/certificate entry points confer the bounded evidence.
Geometry helpers expose intermediate pure calculations for independent hand
tests; passing a modified scene to such a helper does not create a source
certificate. No public function accepts a caller's geometry PASS flag.

| Item | Source fact or proposed result |
|---|---|
| Original HU centre | Source-derived `[125.6,.855,29.5]`, yaw `3*pi/2` |
| Initial vehicle root | Source prehandle `[123.2,0,29.5]`, yaw `pi/2` |
| Empty/high/retracted initial vehicle | Proposed precondition; availability/seating not proved |
| Intermediate motion and attachment | Proposed six-step policy; no durations |
| Final loaded root | `[123.2,0,29.5]`, source prehandle matched |
| Final axle | `[123.6,0,29.5]`, first reverse arc start matched |
| Final HU bottom centre | `[124.2,.70,29.5]`, source yaw retained |
| Fore-aft clearance during lowering | Nominal zero; inward1mm rejects |
| Known obstacles | Other module/initial-HU bounds checked; transient occupancy absent |
| Route, traffic, runtime, B2B handoff | Not granted |

The certificate also exposes geometric `relative_hu_yaw_rad=pi` and
`travel_orientation_status="not_admitted_pending_C08_relative_yaw_frame_binding"`.
The pinned C08 builder requires zero job-relative yaw/tilt. Its nominal job
load frame is not yet bound to this source-preserving mesh orientation, so
there is no travel admission and no silent yaw normalization.

The original unit identifiers in the plan preserve ancestry only. There is no
slot-to-vehicle ledger mutation, worker admission, claim, reservation, event,
or cost. Existing source/runtime models and old F01/FL01 certificates remain
unchanged. A later runtime or route extension must retain these limits and
provide its own causal and physical evidence.
