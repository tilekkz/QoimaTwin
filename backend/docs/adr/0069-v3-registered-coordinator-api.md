# ADR 0069: Registered namespace3 coordinator runs through the shared API worker

Status: proposed backend implementation. Tests and static checks are deferred by the user's
current instruction. No shared frontend contract adoption or full V3 acceptance is implied.

## Decision

Add a separate `/api/v3/coordinator-profiles` and `/api/v3/coordinator-runs` family. The sole
server-owned profile is `explicit-two-cart-six-station-source-proposal` from ADR0064's proposal
example. A request selects that name and must match the registered source revision and layout.
It cannot supply a filesystem path, arbitrary raw source, stock, clocks, material recipes,
worker plan, resource override or analytical hand profile.

Registration compiles the actual pinned source, verifies its retained typed/materialized input,
and freezes the exact raw source files, conveyor files, normalized public choices, source-only
CLI request and native frozen inputs in immutable storage. Metadata is derived from that
compilation. It includes all existing actors and explicit resource counts, but registry identity
is explicitly not advertised as a full physical A/B identity. No engine executes at registration.

The routes submit `coordinator-v3` jobs through the existing `JobService`; root owns the shared
dispatch and application hooks. This is the same owned calculation slot as the other API
families, not a second background engine pool. The immutable request key binds API domain,
registered bundle, complete input identity, request evidence and compiler/engine/export versions.

The worker restores raw registered evidence, recompiles it and compares full frozen input bytes
before execution. It calls the source-only `simulate_compiled_coordinator` entry point once.
Only a strict namespace3 read plus exact registered/native/request binding can publish a public
run reference. A failed attempt keeps its private source/output/failure evidence and raises;
it never publishes a successful run or reusable JobService response. Slot release/cancellation
continues to belong to the common worker lifecycle.

## Native and public identity

`qoima-v3-coordinator-api-1` is a distinct API identity domain. Public run IDs bind the native
ADR0065 run ID, immutable registered bundle and versions. Native IDs and bytes retain their own
contract; no whole, receipt or light codec is reused to drop coordinator-specific state.

The run index contains the exact native manifest inventory plus exactly `profile.json`,
`request.json` and `result.json` outer evidence. Every raw descriptor has a path, positive exact
byte length and content hash. Known path membership and confinement precede restoration, and
native publication is rejected if undeclared files or symbolic links appear in the output.
The semantic public reference is published last after full strict validation.

Every read rehashes the complete registered evidence and every authorized native/outer file.
Only then may a bounded cache reuse immutable canonical validation results. The cache key includes
the full index and registration snapshot; it never caches mutable run objects. Cold validation
restores the bundle and calls ADR0065's strict reader, then compares outer CLI evidence and result
to the actual native observations. Cached POST responses must equal the freshly verified response.

## Reads and terminal meaning

Status includes native `complete`/`partial`, distinct business completion, resource drainage,
observation end, staffing status, violations and native metrics. It does not infer completion from
one worker's current order ID, business shipment alone, or a future planned return. Actual open
operations, multiple carts, unit contexts, role bindings and packing state stay in the native
captured checkpoints. A full warehouse/N4/mesh-proof claim is not synthesized from these fields.

Checkpoint reads require an exactly captured integer tick; no arbitrary seek, interpolation or
Engine.restore is claimed. Events use a half-open `[start_tick,end_tick)` window of at most
60 seconds, entirely within the observed interval including an event at the final tick through
the exclusive endpoint `observed_until_tick + 1`. Public query ticks are strict decimal strings
to avoid JSON number precision ambiguity.

Raw file reads authorize only hashes listed in that run's verified inventory and return exact
bytes with hash ETags. Unknown public runs or unauthorized file IDs are 404. Missing/corrupt
server-owned dependencies of a known registered run, malformed indices, or contradictions in
cached responses are 500 `artifact_corruption`; they are not client `invalid_input` errors.
Malformed client requests and invalid checkpoint/event bounds remain 422. A forged cached
response pointing at an unknown run is server corruption, distinct from an unknown public GET.

The reader validates the whole bundle before selecting a checkpoint/event window. No streaming,
bounded-memory, arbitrary replay or performance guarantee is claimed.

## Verification plan and limits

Prewritten cases cover strict request fields, namespace/bundle identity, no hand public profile,
real source registration preserving530HU/12256units/24actors/six stations/two explicit carts,
missing known registration evidence even after cache warm-up, exact raw bytes, immutable repeat
responses, a captured two-helper paid return at158s with planned restoration160s, half-open event
selection, corrupt cached completion, and failed worker attempts without success publication.

Hand storage/HTTP fixtures explicitly patch registration for tests. They do not demonstrate that
public production accepts hand profiles or certify source-scale physical execution. Expected
158/160s boundaries come from the declared hand routes, not new engine output. Source registration
tests forbid engine execution. All new tests are currently unexecuted; final integration must
include coherent ADR0064/0065 and root CLI/shared dispatch dependencies before running gates.
