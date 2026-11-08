# ADR0064: source-bound concurrent coordinator inputs

Status: proposal implementation; checks deferred to final assembly by current user instruction.

## Decision

The backend-owned `qoima.coordinator-profile.v3-proposal`0.1.0 document compiles into
the ADR0063 namespace3 runtime. `compile_coordinator_profile(bundle, conveyor, document)`
returns `CompiledCoordinatorProfile(profile, horizon_tick, end_tick, frozen_bytes,
input_hash, registry_common_hash)`. `load_coordinator_inputs(raw)` reconstructs this
binding from locally verified pinned source and exact canonical choices.

All24 source worker identities and six packing stations remain present. The document
explicitly declares cart count and limits, material recipes and finite owners, all12
picker/cart eligibility records, per-order actor/cart/station/shipper/port assignments,
cross-training, common unavailability and role intents. Actor homes, speeds, handling
durations and material geometry are declared assumptions, not facts inferred from visual
clips. Arrival ticks are explicit in[0,H); no unclocked C10/C11 weights become rates.
C12 examples do not confer source authority or operational permission.

Source bindings derive baseline stock, SMALL original-HU unit addresses, actual slot
service and cart-stop anchors, six station service/WORK/spur connections, directed belt
routes, source port windows/service clocks and the common directed movement graph.
Source service facts cannot be overridden through this JSON interface. Finite local
package pools/racks and cart pools are explicit co-located assumptions. Shared material
pools cannot span different cart homes.

Inherited singleton compatibility views are generated internally from already declared
resources. There is no public default_assignment or second editable singleton
cart/station/port configuration. Runtime authority remains ADR0063's actual maps and
immutable per-order contexts. Internal C validation supports paid access between worker
home and cart home; existing old public validators remain strict and unchanged.
The inherited legacy default-view validator requires P01/K06/S01. The compiler selects
the station whose registry primary is K06, the lexicographically first declared cart
and parcel port, and their associated owners. This internal alias is not an actor/cart
eligibility grant and does not constrain actual per-order assignments:
all12 pickers, six stations and both shippers remain available through C resources.

The first public version supports source SMALL unit picking and the already supported
typed manual SMALL/STANDARD whole-HU receipts/shipping. Unsupported executed classes are
rejected. Future receipt definitions remain distinct from existing stock and are not
credited at compilation. This version retains the reviewed whole-public boundary that
unit orders reference original SMALL stock; future-HU unit demand is rejected explicitly,
not silently redirected. It does not remove any capability from the native receipt engine.

## Shared source and admission authority

Compilation reloads and verifies raw offline bundle/conveyor bytes, compares exact nested
types and canonical values of supplied records, and independently uses Registry A's raw
source verification. Caller-reported or retained hashes are not proof. Unknown fields,
duplicate identities, bool/float numeric aliases and invalid windows fail closed.

The existing source whole binding primitives preserve slot/module payload restrictions,
finite buffer connectors and their provenance. The explicit policy remains
`c09-manual-small-standard-source-mode-projection-v1`: only source pedestrian edges whose
cargo metadata is absent receive the declared manual class projection. Explicit source
denials remain intact. No vehicle/heavy operation is inferred from this projection.

Pure final admission calls the same C role/resource validation and the existing shared
prospective whole/receipt ledger with C's internal unit-view callback. It never constructs
an engine, a worker state map or a second physical runtime. The returned live initial
inventory excludes future credit. Operational actor availability, lease release and paid
return remain runtime decisions, not capability-derived compile-time grants.

## Immutable identity and future pairing

The full frozen envelope binds compiler/runtime versions, normalized explicit choices,
verified source documents and typed facts, graph/connectors, initial stock/inventory,
whole/receipt process, all C resources, Registry A and role intents. Its SHA256 is
`input_hash`. Unordered identity tables are normalized; ordered paths and placements keep
their semantic order. Runtime observations, history, caches and CPU timings are excluded.

The reader recompiles and requires exact canonical byte equality. A retained typed
compiled object must also pass `validate_compiled_coordinator` before publication;
typed profile values, graph adjacency and metadata cannot impersonate frozen inputs
through Python's bool/int equality or Fraction-shaped dictionaries.

`registry_common_hash` proves only the bounded registry sameness defined in ADR0057.
It does not prove whole-run physical A/B sameness. ADR0065/0067 must compare a complete
physical projection including H/end, world, flow, resources, assignments, graph, materials
and assumptions; only the declared role plan may differ. One safe construction is verified
recompilation with `role_intents=[]`, keeping every other choice and provenance unchanged.
No incomplete physical-common hash is returned by this compiler.

## Evidence and limitations

Tests were written before implementation, with execution intentionally deferred. The
source example declares two carts, two three-unit orders from one original HU, six
station bindings and all24 actors. Source baseline hand oracles are530 HUs and12256 units;
compiler tests must not derive expected values from engine output. No source DES, new
HTTP proof, benchmark, frontend compatibility or full N4 acceptance is claimed here.

The JSON schema is backend-owned proposal material. Shared contracts and frontend files
are unchanged. This new namespace does not reuse old codecs that omit multiple carts.
