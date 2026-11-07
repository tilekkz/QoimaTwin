# ADR 0028: Freeze a scoped V3 proposal package before execution adaptation

Status: implemented for isolated input ingestion; operational admission remains false.

## Context

The V3 brief proposes a distinct 144 x 72 x 8 m warehouse with heterogeneous cargo,
776 storage slots, six ports and a synthetic 530-HU initial baseline. The old 474-second
V2 fixture and its stock/process assumptions remain authoritative for V2. V3 geometry
artifacts and planning scores do not establish an operational execution contract.

## Decision

Pin upstream revision `22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec` and vendor only the
14 JSON files required for typed static catalogs, compiled graph links and baseline
conservation. Preserve raw bytes and source-relative paths. Record upstream Git blob,
raw SHA-256, byte length and URL in a scoped provenance manifest. Anchor that manifest
by its own SHA-256 in code, so changing both a source and its local inventory entry does
not bypass the pin. Updating the revision requires an explicit reviewed code/data change.

Expose `load_v3_bundle(path: Path) -> V3Bundle`. Verify hashes before strict parsing and
validate the actual upstream Draft 2020-12 schemas at their correct roots. Reject missing
sources rather than fetching moving heads. Validate cross-record identities, counts,
quantities, mass, slot/module payload and links, independently of supplied summary values.
Return frozen typed tuples and a mapping of immutable canonical-byte JSON documents;
decoding creates a fresh tree. This prevents mutation through shallow frozen dictionaries.

Use exact identity/count/hash comparisons. Following upstream C04/C05, evaluate local
`HU dimension + 2 * clearance <= usable dimension` with `Fraction(str(number))` on
each operand, before arithmetic. There is no geometry epsilon: height .95000000001
rejects against usable 1.05 and per-side clearance .05; .95 fits exactly. Decimal's
global precision cannot affect these checks. Never substitute module outer bounds,
weaken source frame capacity, scale cargo or infer cargo rotation from module world yaw.

Use the same exact source-decimal arithmetic for unit/HU mass identities, per-slot
payload, aggregated module payload and port-mix normalization. Enforce integer buffer
allocations and exact count conservation. Static assignment validation intersects cargo
storage types and slot archetypes and requires the source identity local XYZ orientation
and its explicit mapping to a slot-permitted orientation.

Keep absolute tolerance 1e-8 (zero relative tolerance) only when comparing serialized
derived volume or mass summaries, whose upstream generation uses float arithmetic.
Such comparisons never authorize geometry or capacity. Compare exact module mass to
the source capacity independently of the serialized module summary. No source rewriting
or public frozen-model changes are needed for this correction.

## Consequences

The stable seam permits downstream static API/bridge work without coupling to runtime,
API, exporter, shared-contract or V2 engine changes. `static_geometry_proposal` and
`operational_admission=false` must remain visible in downstream representations.

The minimal package is about 10.5 MB and explicitly excludes visuals, original graph/model
sources and the full semantic/public projection. Runtime verifies only the scoped source
inventory and internal relationships; it does not certify excluded dependencies, recompute
the whole upstream layout content hash, prove physical operation or produce an engine run.
A frozen scenario, finite resource execution semantics, handling/support/loaded routes and
operational admission need separate work. See `../v3-inputs.md` for the public field contract,
source scope, corruption tests and commands.
