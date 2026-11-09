# ADR 0086: Explicit heavy inbound additions preserve the original offered stream

Status: accepted for the N2 input-only prerequisite. Runtime and full N2 remain open.

## Requirement and source boundary

The historical V3 brief at `a54bead`, `docs/adaptive-v3/brief/02_DESIGN_V3.md:137`,
defines N2 as increased heavy/pallet receipts at a declared inlet, with compatible
storage and transport comparisons and no free equipment. Lines143–145 require the
same complete materialized physical inputs for both alternatives. C10 supplies the
legitimate fixed baseline; its expected moves are unclocked weights, not arrivals.

C11's legacy `N2_DECLARED_PORT_MIX_SHIFT` changes inbound shares of55 STANDARD
SKUs, without increasing HEAVY/PALLET intensities. Its clocks, 12/40-second proxy
allowances and eight-transfer policy are not adopted here. C12 remains a proposal
handoff. V2 swaps, rates and durations likewise provide no defaults.

Current FLEX slots accept SMALL/STANDARD only, at most15 kg. This input addition
does not modify that capability. Heavy-compatible FLEX, source physical receipt
handling, availability and paid runtime are separate unresolved tasks. A valid
input artifact must not be labelled full HEAVY/FLEX comparison or N2 execution.

## Public interface

```python
compile_heavy_inbound_inputs(
    policy: WorkloadPolicy, additions: tuple[HeavyInboundReceipt, ...],
) -> HeavyInboundInputs
load_heavy_inbound_inputs(raw: bytes) -> HeavyInboundInputs
verify_heavy_inbound_inputs(value: HeavyInboundInputs) -> HeavyInboundInputs
```

Each immutable addition explicitly supplies `job_id`, `hu_id`, `lot_id`, `sku_id`,
`port_id` and integer `arrival_tick`. The caller supplies the entire baseline
WorkloadPolicy, including horizon, inbound/outbound counts and calendar. There is
no default volume, service/handling/travel duration, graph, initial pose or grant.

Compilation reopens the canonical raw-pinned C10 package, materializes its complete
baseline and derives source inlet permissions. Only additions with source SKU
class HEAVY_BOX or PALLET_LOAD and a permitted inbound port are in scope. The source
template supplies exact quantity, dimensions, gross mass, orientation permission,
cargo/recipe hashes and SKU identity. No input overrides these values.

`orientation_id=upright_xyz` is the source template permission; it is not an actual
world yaw, staged pose, placement transform or pickup proof for the future HU.
Templates retain initial-HU references as source recipe evidence, not as a claim
that a future HU already exists or can alias an original container.

## Finite additions and identity

At least one valid additional heavy/pallet receipt is required. Every affected
class/inlet pair has explicit `before_count`, `added_count`, `after_count` and exact
added offered mass. The increase is a count of newly declared materialized offers,
not a change of weights that could round to zero. Arrivals satisfy `0 <= t < H`.

New HU and job IDs cannot collide with any original HU, existing offered HU/job,
another addition or a lot namespace. Several HUs may share one consistent lot.
Consistency binds SKU and the complete canonical source template, including per-HU
quantity and mass. A previously known lot of that same definition may be referenced;
a different SKU/template is rejected. This is input ancestry consistency only, not
permission for a later ledger to accept that receipt or to merge containers.

The baseline WorkloadPolicy, quota rows, job IDs, original arrivals and population
identity remain unchanged. No global renormalization is performed. The new
`postshift_jobs` is the sorted union of the old rows and explicit new rows, ordered
by `(arrival_tick, direction, job_id)`. Additions are normalized by unique job ID;
permuting their input tuple does not change identity. The postshift is its own
versioned offered stream, not a falsely relabelled baseline TimedWorkload with
different counts. Any future paired arms must consume these exact common bytes.

All530 original HUs,12,256 units, source slots/lots and C10 raw input/assignment
bytes remain authority. All baseline offered rows remain, including outbound B2B,
other classes, earlier scheduled receipts and future stock shortages. No class is
filtered for current runtime support, and no offer is postponed to make it feasible.

`accepted_receipt_count=0` means this input compiler has accepted or credited no
receipt; it is not an observed runtime metric. `operational_admission=False` and
`full_n2_acceptance=False` are mandatory. No StockLedger, worker, vehicle, capacity,
service schedule, receipt readiness or storage placement is created.

## Fresh authority and hand boundary

Public load accepts only the closed canonical versioned envelope. It derives all
templates, inlet permissions, baseline rows, additions and deltas again from fresh
raw source. A new outer hash does not validate altered quantity, mass, arrival or
baseline authority. Verify also compares exact recursive Python types, rejecting
equal bool/int/Fraction and mutable-container aliases.

The separate `augment_offers` helper accepts a declared analytical TimedWorkload
and explicit inlet mapping so tests can use a tiny independent oracle. It verifies
the supplied workload against its own declared source/policy and returns only an
augmentation. It does not authenticate that source as C10. Public compile accepts
neither this result nor caller WorkloadSource/port mappings; public load/verify
always reconstructs canonical C10 authority.

## Independent oracle and limits

The hand baseline contains two455 kg PALLET offers and two other offers. Two
explicit new PALLET HUs at the same inlet yield four PALLET plus the unchanged
two others: total4→6 and extra offered mass910 kg. All original job/arrival/identity
rows remain exact. A shared lot does not collapse the two physical HU identities.

Tests begin before implementation. Cases include zero increase, source-incompatible
class/port, horizon/type errors, existing HU/job identities, conflicting lot,
permuted input order, retained numerical aliases, rehashed postshift rows, raw source
mutation and attempted hand-to-source promotion. Public source examples use an
explicit policy; their counts are not source throughput or measured capacity.

This addition only prepares the common exogenous N2 stream. Physical staging and
pickup support, continuous loaded routes, target compatibility, shared resources,
credit boundaries, paid clocks and eventual comparison remain outside this ADR.
Existing source data,464 foundation files, contracts, frontend and ADR index stay
unchanged. No runtime/public API/CLI integration is added.
