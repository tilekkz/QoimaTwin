# Bounded paired coordinator comparison

`app.v3.coordinator_pair.compare_coordinator_profiles(bundle, conveyor, baseline_document,
candidate_document, scenario="N0" | "N4")` validates two source-bound ADR 0064 inputs, executes
two independent namespace3 worlds, and builds strict native runs before returning a comparison.

The result exposes immutable `report_bytes`, `baseline_run_bytes`, `candidate_run_bytes`,
`baseline_inputs` and `candidate_inputs`. The `report`, `baseline_run`, and `candidate_run`
properties decode fresh objects. `prepare_coordinator_pair` performs source and comparability
validation without executing a simulation. It does not grant permission to bypass validation
through an externally supplied prepared object; execution uses the complete public entry point.

Only `role_intents` may differ for N4. Both role-neutral inputs must successfully recompile
to identical full bytes, and all other materialized profile fields must match. Registry
identity alone is insufficient. N0 additionally requires identical full inputs.

The report returns `demonstrated` or `not_demonstrated` for this bounded scenario. Partial
business flow, unfinished paid return, and staffing violations remain visible in the native
statuses and evidence. N4 requires actual completed helper work and actual return by the
declared deadline. The result does not claim full V3 acceptance or frontend compatibility.

Metrics are retained separately for baseline/candidate and at-horizon/at-end. In particular,
assignment exposure is not busy utilization, and runs ending at different ticks use different
at-end time denominators. N1/N2/N3 raise an explicit unsupported-scenario error.

The analytical hand seam is for internal manual arithmetic tests only. Its outputs retain
that scope; neither public source CLI nor API accepts hand profiles through this module.

Implementation and prewritten tests are currently awaiting the user-requested final checks.

The mixed-source N4 examples (both original P11/P12 and Tilek P01/P02 helper families)
explicitly declare shipped-owner capacity3: two parcels plus one intact received HU.
Both sides retain exactly the same capacity. This corrects the earlier capacity2
example, which necessarily leaves at least one shipment unfinished without terminal
clearing. It does not add clearing or change runtime/source capacity rules. Completion
remains conditional on actual execution before the end cap; no successful run is claimed.
