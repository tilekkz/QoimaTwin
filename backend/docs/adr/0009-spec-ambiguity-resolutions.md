# 0009. Resolutions of spec ambiguities

Status: accepted for implementation, 2026-11-07. Items marked (shared) need Tilek's confirmation.
Source IDs refer to `../research/2026-11-07-codex-edu-spec-audit.md` (A01-A31).

| Topic | Decision |
|---|---|
| Inventory check (A08) | In phase 3 the FIFO head order is checked against free active stock. A shortage rejects it as `unfulfilled_inventory`. An admissible head that waits for a picker or a tote is not bypassed. |
| Resource choice (A09) | Lowest free actor ID of the matching home and lowest free tote ID, reserved together with the stock in one transaction. |
| Pack target (A10) | Chosen and reserved at `handoff_ready` by minimum reserved WIP, tie by pack ID. Held until the parcel enters the outfeed. |
| Merge vs admission (A11) | Belt transfers are arbitrated first; external admissions use the inlet cells that remain free. |
| Shipping scan (A16) | The parcel leaves the shipping buffer when the scan starts. The shipper owns it and the reserved pallet slot until placement. |
| Sealed queue (A17) | A sealed pallet keeps its queue place until the forklift pickup completes. |
| Receiving (A18) | 8 physical positions shared by waiting, in-service and processed pallets. The queue KPI excludes service. |
| External receipts (A19) | Receipts that cannot enter wait in an external FIFO. They are not in the ledger and are reported separately. |
| Reserve staging (A20) | The time of the 40th putaway is measured, never hard-coded as 7200 s. |
| Drain (A04) | Useful work: admitted receipts, transfers, services, live timers, vehicle return. Idle conveyor ticks and static stock are not useful work. The deadline is `H + max_drain_s`. |
| Termination (A05) | Status per subsystem plus a reason list. Primary reason order: error, deadlock, max_drain, unfulfilled_inventory, drained. |
| Seeds (A21) | `numpy.random.SeedSequence([20261107, stream_code])` with fixed codes: history=1, orders=2, receipts=3. |
| Promotion (A22) | Labelled as a sampling-weight multiplier of 5; original and normalized weights are stored. |
| Forecast horizon (A23) | Daily visit forecasts are scaled to the run horizon; the train baseline is scaled the same way. |
| Swap costing (A24) | Each swap is priced as its own I02-to-I02 route, both orientations checked, ties broken by `(sku_a, sku_b)`. |
| Relocation (A25) | A pre-shift labor artifact. The shift starts from the post-relocation state; the cost is subtracted once. |
| Fixture (A27) | `analytical_fixture.json` is converted into a schema-valid scenario plus a separate fixture setup. |
| Exported states (A28, shared) | Visual labels are mapped from `(state, operation, reason)`; they are not engine states. |
