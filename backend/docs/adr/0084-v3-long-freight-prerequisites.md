# ADR 0084: Source-bound LONG freight prerequisites without operation admission

Status: accepted for the bounded backend prerequisite; operational N3 remains open.

## Requirement and scope

The historical V3 brief at `a54bead`, `docs/adaptive-v3/brief/02_DESIGN_V3.md`,
section7 requires N3 LONG FREIGHT to respect orientation, gate and zone constraints,
and to explain an incompatible choice. Sections6–7 preserve complete physical
inputs and paid moves. C10 supplies a legitimate immutable baseline; C11's legacy
`N2_DECLARED_PORT_MIX_SHIFT` and C12 examples are unclocked proposals, not N3
operation authority. Neither V2 swap limits nor old proxy clocks are adopted.

This addition checks one original `v3:HU:initial:DEMO_180:01` at
`v3:slot:LONG_W:002:L1:B1`, with proposed target
`v3:slot:LONG_W:001:L1:B1`, declared `upright_xyz`, `OUT_E_B2B`,
`OUTBOUND_FORKLIFT_PAIR`, `F02` and `FL02`. The source target is initially free.
Other known target choices remain visible static rejections, including other free
LONG places; they do not expand the approved finite slice. No search, relocation
job, customer allocation or beneficial plan is created.

## Explicit public boundary

```python
compile_long_freight_requirements(
    request: LongFreightRequest, policy: WorkloadPolicy,
) -> LongFreightRequirements
load_long_freight_requirements(raw: bytes) -> LongFreightRequirements
verify_long_freight_requirements(
    value: LongFreightRequirements,
) -> LongFreightRequirements
```

The request contains only eight explicit semantic IDs: HU, original source slot,
proposed target, orientation, port, pair, actor and vehicle. It accepts no graph,
pose, arbitrary yaw, dimensions, cost, route, proof hashes or capability grant.
Unknown original identity/source, unknown slot/port, malformed types and extra wire
fields fail closed. Known incompatible physical choices produce deterministic
reason codes and `static_rejected`, rather than disappearing.

`WorkloadPolicy` is mandatory. Fresh C10 source templates and weights are passed
to the existing exact whole-HU materializer with the caller's explicit count and
arrival policy. Every offered row, including all B2B and inbound rows, is retained;
no admission filtering or adjustment to make this HU appear in a customer offer
occurs. The request is a static proposed movement, not an allocated timed customer
job. Consequently a zero-count policy is valid prerequisite input and proves no
operational scenario coverage. No source rate, volume or operation clock is inferred.

The authority retains exact raw C10 input/assignment bytes, all530 original HUs,
their original slots/lot/orientation/quantities, complete materialized workload
and bytes, source revision/layout hash and the union of17 pinned physical source
fingerprints. Existing baseline assignment bytes and workload population identity
remain unchanged. This is C10 common workload, not an N1/C11 projection.

Every public compile/load/verify reopens the canonical local base and vehicle
packages through their existing hash-pinned loaders. Source paths are locators,
not caller-controlled identity. Load reconstructs all derived values from the
request and policy and requires exact canonical byte equality. Verify also checks
exact recursive Python types, so equal `bool`/integer/Fraction substitutions do
not gain authority. Retained hashes do not replace raw source verification.

## What is checked

Existing `SourceAdmissionCatalog` performs cargo family, source upright mapping,
dimensions plus clearance, slot/module payload, occupancy and conditional handler
checks. Source C08 rules check both original pickup and target place design,
including support/fork height, payload with attachment, rating moments and the
named port/pair. The static capability descriptor means the required source
`forklift_operator`/`approved_load_support` conditions; it does not assert that
an attachment is mounted or that F02 is available, seated, trained or reserved.

The original HU is200 kg. C08 declares a40 kg LONG cradle, so lifted mass is240 kg.
The stored HU remains200 kg, with unchanged24 units and original lot. Required
dimensions are `(4.3,.62,.75)` after applying source clearance `.05` on each side,
within target `(4.4,.65,.9)` and600 kg payload. This does not infer a rigid transform
between source/target/vehicle frames or normalize any signed axis. Exact original
placement evidence stays in the raw assignment.

The source B2B gate is6 m wide and4.5 m high; declared LONG port service is210 s.
These are source design facts, not a swept-route result, timed schedule or total
customer duration. The standalone `straight_gate_fits` helper checks only an
explicit, already aligned analytical width/height envelope with exact Fraction
clearance. It does not use or certify the source route and never clears a blocker.

## Permanently unresolved physical and process prerequisites

Every result retains seven structured obligations with explicit required fields:

1. Actual pickup meshes, signed source orientation, support and two-fork contact.
2. Actual cradle inventory/mount, both positive pins, restraint, retention and strength.
3. Actual target support, relief, continuous setdown and release.
4. Directed loaded routes and return, actual model containment, signed poses,
   gate/turn sweeps, stop/steering/reverse obligations.
5. Actual F02/FL02 initial pose and seating; driver/shipper/vehicle availability,
   traffic/action/target/staging leases and one custody clock.
6. Explicit paid approach, pickup, carry, place, return and transition clocks,
   complete service scope without double charging, rounding and H/end.
7. Exact customer allocation and one-use original HU, finite staging support,
   actual port handoff and release.

No caller certificate clears these obligations in this version. Even the valid
source candidate returns `prerequisites_only`, `operational_admission=False` and
`full_n3_acceptance=False`. This is not a stock transaction, ledger credit, engine
run, route admission or runtime improvement. PALLET geometry/F02 seating proofs
cannot be renamed as LONG action proofs. Future physical work needs a new explicit
proof-bound interface and independent tests before scheduling or publication.

## Independent checks

Tests start with absent-module RED, then check exact source arithmetic, complete
stock/offers, missing-proof preservation, SMALL/FLEX/occupied target, forbidden
orientation, EXPRESS port and wrong fixed-pair members. A separate actual RED
exposed another free LONG target being accepted outside the bounded choice;
the guard now preserves that request as an explained static rejection.

Analytical gate boundaries4.19/4.20 m and clearance `.05` are exact test choices,
not modified source gates. Public roundtrip, rehashed flags/mass/arrival, nested
type aliases, shortened stock and fresh raw source mutation controls require
authoritative reconstruction. The declared example H60,000,000 ticks with40
inbound and60 outbound offers is test policy only; no performance claim follows.

Only new namespaced modules/tests and this proposal are added. Protected452 files,
canonical contracts, frontend, source packages and ADR index remain unchanged.
