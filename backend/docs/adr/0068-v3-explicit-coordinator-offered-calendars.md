# ADR 0068: Explicit calendars for a finite coordinator job population

Status: proposed; implementation draft, execution deferred by user instruction.

## Context

V3 defines separate workload settings, but supplies no hourly normal/peak arrival rate.
C10 movement weights describe a planning period, not an hourly rate. Existing
`workload_*` code correctly materializes a declared whole-HU population without granting
operational admission. A source-bound coordinator profile instead contains explicit unit
orders, manual receipts and whole-HU jobs. It needs reproducible clocks for paired and
longer observations without silently cloning units, wrappers, carts or stock.

## Decision

An additive calendar proposal changes only `horizon_tick`, `end_tick` and each existing
job's `arrival_tick`. A calendar lane identifies its stream, a unique lane ID, an ordered
nonempty list of existing job IDs, and an explicit half-open window `[a,b)` within `[0,H)`.
For `n` jobs the integer microsecond arrival is `a + floor(i*(b-a)/n)`, `i=0..n-1`.
The last arrival is strictly below `b`, even if several jobs share a tick. Job order is
meaningful; the lane table is unordered and canonicalized by lane ID. Concurrent lanes
may overlap. Every declared job must appear exactly once, with its correct stream.

All clocks are exact integers; Boolean and floating aliases are rejected. `0 < H <= end`
is required. An empty population requires an explicit empty lane table. Missing, duplicate
or unsupported jobs are errors, never filtered. No implicit rate, seed, material generation,
source-slot reassignment or rate derived from a previous run exists.

Source port clocks, staffing windows, assignments, materials and operation durations are
preserved. Extending the observation does not extend a port or staffing window. Source
compilation after materialization performs all physical, stock, route and role checks.
The pure materializer always declares `operational_admission=False`; its successful
return alone cannot authorize an engine run. Unsupported classes remain unsupported.

`offered_workload_hash` covers the resulting three job tables, declared H/end and source
revision/layout identifiers. It is deliberately bounded: different carts or role plans
may share it. It is neither `physical_common_input_hash` nor raw-source authority. Native
compilation produces its own complete input identity. The calendar document records
the scheduling recipe and its stated provenance; two recipes producing the same jobs and
clocks describe the same offered workload. ADR0067 must still verify full physical common
inputs before pairing.

## Hand arithmetic and verification plan

- Two jobs on `[2,10)` arrive at `2,6`.
- Three jobs on `[0,10)` arrive at `0,3,6`; on `[0,1)` all arrive at `0`.
- Two existing jobs over one hour arrive at `0,1800 s`; over eight hours at `0,14400 s`.
  These are sparse illustrative populations, not normal/peak acceptance budgets.
- Reordering lanes leaves materialization unchanged; reordering jobs within a lane changes
  their clocks. Original inputs must not mutate.
- Tests cover complete stream membership, duplicate/global identities, bounds, exact types,
  preserved resources, bounded hash semantics and required source recompilation.

Tests were authored before implementation. They have not been executed: new validation
runs are reserved for final integration under the latest user instruction. No V3 hourly
throughput, N0/N4 success, source C10 mix execution, or performance result is claimed here.

## Consequences

This provides deterministic timing for an already explicit executable subset. It does not
create the missing full eight-class workload or implement paid relocation. Future demand
generation must explicitly select volumes and bind unique units/materials/receipt slots;
it cannot inherit V2's 240/600 orders per hour or call this two-job example a benchmark.
