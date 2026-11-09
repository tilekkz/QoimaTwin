# Storage fullness read model

Backend proposal, ADR0080. No shared contract or frontend migration is implied.

Use `app.v3.storage_fullness_publication.build_fullness_report(run, inputs=raw_inputs)`
with a native coordinator run and its exact frozen inputs. It validates the complete native
evidence first and returns an independent JSON object containing:

- `version`, `report_id`, `source_run_id`, `input_hash`, `native_run_sha256`;
- `at_horizon` and `at_end`, each at the native settled boundary;
- `total`, `zones`, `modules`, `slots` for a source-bound profile;
- `available=false` for an analytical profile without source warehouse capacity.

`validate_fullness_report(report, run, inputs=raw_inputs)` recomputes and checks the entire
report. The report does not modify the native run, create events or advance its clock.

Each aggregate distinguishes physical occupied/empty, active occupied/empty, reserve-only,
blocked, reserved and unreserved active empty slots. Occupied and reserved can overlap.
Every occupied wrapper counts even when it has no remaining product units. Inventory in
transit is outside storage, while its cargo remains in the native ledger.

The physical occupancy ratio divides occupied slots by physical slots. Active occupancy
uses active slots. Mass and outer bounding volume use separately named payload and usable
volume denominators. Module ceilings are checked independently of summed slot limits.
Fractions use `{numerator, denominator}`; an absent denominator is null. No percent is an
admission decision. In particular, `unreserved_active_empty_slots` does not promise that a
particular cargo, handler or route can use those places.

At the unchanged initial source, the hand oracle is 530 occupied of 776 physical slots,
530 occupied of 588 active slots, 246 physically empty, 58 active empty and 188 blocked
reserve. Initial storage cargo is 12,256 units and 9,403.85 kg; explicitly declared material
pools are separate. Actual later values must come from the chosen native observation.
