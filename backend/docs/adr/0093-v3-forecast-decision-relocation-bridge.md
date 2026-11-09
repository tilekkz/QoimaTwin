# ADR0093: Forecast decision to the existing paid relocation pair

Status: Implemented bounded backend bridge; source execution and release acceptance are pending.

The saved forecast placement decision previously ended at a planning artifact. Executing a manual
N1 pair required independently authored jobs, so that pair did not establish which forecast
decision selected its movement. This bridge binds that choice before actual execution. It neither
selects again using actual demand nor turns predicted offer IDs into actual customer job IDs.

`prepare_forecast_relocation(decision_bytes, common_inputs, choices)` freshly loads the complete
forecast/stock/placement authority and the separate canonical coordinator inputs. Explicit choices
contain only a job ID and arrival tick. The forecast and actual horizon must match exactly; the
existing relocation binder applies the arrival boundary and source admission rules. A 1000-second
forecast cannot use 900-second common inputs. The actual workload, arrivals, packing rules, B2B
orders and calendars are retained byte for byte. The decision retains all predicted offers,
bindings, shortages and original placements; none are projected into a replacement actual stream.

The bridge checks common source revision, layout and every planning source fingerprint, all
original HU/unit/lot/SKU/owner/mass identities, and complete original placement coverage. For a
selected movement, the actual actor ID, home, speed and gross capacity must equal the planned
actor. The existing common whole-HU configuration supplies customer port permission, buffer
geometry, pickup/place ticks and service ticks; no missing customer configuration is guessed.
Equivalent decimal spelling of the same exact buffer geometry is allowed without changing either
input byte string. Path clearance and the resulting declared relocation steps, durations and routes
must match the priced relocation. Source dimensions, role permissions, destination occupancy,
module payload, job conflicts and paid return remain the existing relocation binder's authority.
This introduces no hourly rate, alternative actor, scheduler, ledger, stock or route fallback.

Only `decision.selected` maps to a `RelocationJob`. A negative or infeasible raw candidate is not a
selection. No selected candidate yields explicit zero-job baseline and candidate arms. With the
existing same-actor/home/speed, single-consumption cost model, a legitimate no-op is expected in
many cases; this adapter does not force positive gain. It preserves the selected forecast price and
does not reprice or optimize against the subsequently supplied actual workload.

`ForecastRelocationInputs` is a new outer identity, containing canonical decision bytes, exact
common bytes, explicit choices and the complete existing prepared pair. `load` reconstructs these
authorities and compares the entire canonical envelope. `verify` also compares all retained fields
with exact recursive types; a frozen dataclass alone is not treated as immutable nested authority.
No public validated flag or cached authority bypass exists.

The native coordinator/relocation input schemas and run identities are unchanged. The fixed native
profile/provenance labels do not contain a forecast ID. Thus two forecasts selecting the same
physical no-op may legitimately have identical native pair/run identities, while their outer
experiment identities remain distinct. Consumers must retain the outer input and manifest to claim
forecast-to-execution ancestry; a native run alone does not carry that ancestry.

The standalone entry point is:

```text
python -m app.v3.forecast_relocation_cli prepare --decision DECISION.json --common-inputs COMMON.json --job-id MOVE_ID --arrival-tick T --out NEW_PREPARED_DIR
python -m app.v3.forecast_relocation_cli compare --inputs NEW_PREPARED_DIR/inputs.json --out NEW_COMPARISON_DIR
```

Both commands require an absent output directory and claim it atomically. Prepare publishes the
outer input and the normal unchanged baseline/candidate input bytes. Compare freshly verifies the
outer input, writes it before calling `execute_relocation_pair` exactly once, then binds the saved
normal comparison report in a manifest written last. The existing executor freezes its pair input,
runs both ordinary arms, performs strict native readback and preserves partial accounting. A valid
partial remains partial and exits zero. On error the bridge retains the outer input and any existing
pair outputs, writes failure evidence when storage permits, and never retries the executor.

The short tests use explicit authoritative-loader and executor doubles plus the existing pure hand
relocation plan. Their positive selected branch is an orchestration fixture, not a source claim or
proof of positive economic gain. Source compilation, HGB, DES, HTTP, full gates and source A/B are
intentionally not executed in this implementation step. Full N1 acceptance, physical N2/N3,
operational admission, UI and publication remain outside this bridge's claimed result.
