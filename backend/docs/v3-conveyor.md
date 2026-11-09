# V3 finite conveyor component

The pinned L08 source now has an executable conveyor component: individual
physical-cell reservations, the shared curve, reversible station spurs, stopped
pivots and finite H/end observations. It preserves an explicitly offered carrier's
HU identity and dimensions. The source supplement and all raw hashes are vendored
under `data/v3-conveyor-proposal`; the original warehouse input pin is unchanged.

From `backend`, run the declared SMALL catalogue fixture:

```powershell
uv run python -m app.cli v3 simulate-conveyor `
  --profile docs/proposals/adaptive-v3/conveyor-source-demo-v1.json `
  --out D:/QoimaTwin-runs/conveyor-source-demo-v1
```

The output directory must be empty. `inputs.json` is written before engine
creation. `trace.json` contains actual events and separate settled state at H
and the end; `manifest.json` binds their raw hashes and sizes. A changed profile
produces a different run identity. A capped unfinished run returns exit code 1
and `partial`, retaining its actual open motion and never fabricating completion.

The example offers `v3:HU:initial:DEMO_001:01` at the intake, traverses PK06 and
exits at the west output. The catalogue supplies .32 x .24 x .24m and .94kg.
The profile explicitly supplies 2 seconds of stationary work, H100 and end200.
Manual source-edge arithmetic gives a final tick of 149170000 microseconds.
That dwell is a component fixture choice, not a packing-duration claim.

This is an `actual_engine_component_run`. It does not remove the offered HU
from warehouse stock, execute a picker/cart handoff, transform its units or
package, reserve a human packer, or confirm an outbound shipment. The trace
declares `full_v3_warehouse`, `inventory_integration` and `frontend_adapter` false.
Its experimental schema is separate from the shared Run2.0 and manual-run
transport. There is no existing Tilek reader or general snapshot-seek contract
for this trace. See [ADR0040](adr/0040-bounded-v3-conveyor-execution.md) and
[ADR0044](adr/0044-v3-conveyor-component-publication.md).

Vehicle prerequisite checks are separately available through
`app.v3.vehicle_package.load_repository_vehicle_adapter`. They bind the six
reviewed graph/traffic/handling documents, exact cargo geometry and evidence
requirements. Even a statically admissible candidate remains
`operational_admission=false`; it is not a timed forklift run or a mesh proof.
