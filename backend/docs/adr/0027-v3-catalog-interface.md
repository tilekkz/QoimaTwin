# ADR 0027: Separate static V3 catalog and source-bound stock interface

Status: accepted for the backend proposal; shared frontend contract agreement pending.

## Context

The user selected Tilek's adaptive V3 warehouse. Pinned source revision
`22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec` describes 144 x 72 metres, 776
storage slots, 200 SKU, eight cargo archetypes, 530 initial handling units and
six ports. Its static manifest explicitly does not claim operational admission
or scheduling. Existing V2 layout, execution and Run 2.0 remain separate.

## Decision

Publish a backend-owned proposal with schema identifiers
`qoima.catalog.v3-proposal`, `qoima.initial-state.v3-proposal`,
`qoima.static-export.v3-proposal` and `qoima.static-manifest.v3-proposal`.
Their schema version is `0.1.0`; the source layout version remains
`qoima-144x72-v3-proposal`. These names express independent model and wire
versions, not an agreed replacement of the shared Run 2.0 schema.

The immutable ingestion seam is `CatalogSource`: source revision, layout hash,
source inventory and immutable canonical JSON documents. Production callers
use `load_v3_bundle`; the interface does not perform network access or re-create
the ingestion gate. Raw source SHA-256 and byte counts are provenance. A separate
canonical SHA-256 addresses the exact canonical source document returned by
the API and exported under `sources/`. Catalog, initial-state and export IDs
hash their complete canonical content with their own ID field excluded.

The catalog preserves actual V3 dimensions, module poses, slot bounds, SKU to
archetype links, unit versus HU dimensions and masses, six ports and declared
actor pools/equipment pairs. Actors have `profile_status=not_defined`; no V2
home or role is invented. Asset archetypes have `binding_status=not_bound` and
scale one; there is no invented model URI or asset readiness assertion.

Initial inventory uses stable HU and lot IDs, quantities in units, one typed
storage-slot owner per HU and floor-centre world poses. The four source module
rotations are exact signed-axis quarter turns. Source-decimal arithmetic is
exact before JSON-number serialization; arbitrary yaw and any excess over
exported usable bounds are rejected without geometry tolerance. Source-derived
serialization checks in ingestion remain a distinct concern (ADR 0028).
The export validates schema, identities, references, owner uniqueness, actual
full-HU quantities/dimensions/mass, SKU inventory and total mass. This is a
static consistency check, not loaded-route or operational admission.

Expose only GET `/api/v3/catalog`, `/api/v3/initial-state` and
`/api/v3/documents/{canonical_sha256}`. Responses are canonical bytes with their
raw-byte SHA-256 as ETag. Router construction validates once and fails closed.
No comparison, scheduling or simulation endpoint is implied by this slice.

Publication requires an empty directory, writes validated canonical artifacts
with exclusive atomic hard-link publication and writes the manifest last.
Concurrent destination files are never replaced. Failed publication may leave
its completed artifacts, but cannot publish a success manifest. A filesystem
without hard-link support fails rather than silently using an overwrite path.

## Consequences and evidence

All static envelopes say `data_kind=static_geometry_proposal`,
`contract_status=proposal`, `operational_admission=false`. Operational replay,
actual engine run, timed materialization and comparison capabilities are false.
There is no run ID, event journal, simulated timestamp or fabricated throughput.

Hand-authored tests establish a two-HU/four-unit/five-kg rotated example.
Rehashed corruptions exercise references, ownership, counts, quantities,
dimensions, totals, support height and yaw; hashes alone are not validation.
The real pinned package verifies all 530 HU, 12,256 units and 9,403.85 kg, plus
the first source-derived world pose `[126.3, 0.25, 50.52]`. The published schema
and initial example are under `docs/proposals/adaptive-v3/`.

Operational runs require a separately declared execution profile, clock,
resource leases, typed ownership transitions and actual runtime evidence.
Neither V2 geometry nor V2 replay events are a valid implementation shortcut.
