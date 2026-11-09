# ADR 0048: Compile explicit public choices for the connected SMALL flow

Status: backend proposal; the bounded ADR 0045 connected flow only.

## Decision

`compile_light_profile(bundle, conveyor, document)` returns an immutable
`CompiledLightProfile(profile, horizon_tick, end_tick, frozen_bytes, input_hash)`.
Compilation runs the existing source binder and physical stock/route validator
before publication or engine construction. It neither executes jobs nor records
future results. The default source authority remains the pinned offline base
bundle and conveyor supplement, not the public profile.

The JSON schema is `qoima.light-flow-profile.v3-proposal`, version `0.1.0`.
Every object rejects unknown properties and every field is required. Explicit
choices include all 24 actor IDs, homes, available times, speeds and capacities;
the three active roles; cart identity/home/owner/speed/width/capacity; owners and
finite capacities; all physical carrier/package recipes and initial containers;
station/port selection; pool, bench, empty-carrier and shipped owners; every
positive handling service time; and each order's original HU, arrival, carrier,
package, original unit IDs and exact placements in both physical containers.
Unallocated stock remains the complete source stock, including inactive classes.

Each rational quantity uses `{ "numerator": integer, "denominator": positive
integer }`. Boolean and floating JSON values are rejected, including integral
floats such as 1.0. Fractions are reduced before canonicalization. A recipe's
allowed archetypes is an unordered unique set; duplicate recipe IDs, containers,
owners or source-unit promises are rejected. Initial material containers must
be explicitly unsealed. Every declared recipe binds at least one declared
initial physical container; there is no implicit material inventory.

The clock uses ADR 0026 integer microseconds. Require `0 < horizon_tick <=
end_tick`, and every offered order arrives strictly before H, matching ADR 0045's
actual runtime. Actor availability may be after H; that honestly leaves waiting
work. Port service duration/windows come from source and cannot be overwritten.
No rate, pool size, carrier shape or service time receives a product default.

## Authority and derivation

Public source revision and layout content hash must match the pinned source.
The supplied bundle and conveyor are also compared, including their exact nested
runtime types, typed facts and full documents, to a cached independently loaded
offline reference. A Fraction and a plain numerator/denominator dictionary can
share a public JSON projection but are not interchangeable source values. The
original canonical document bytes must also match; decoding and normalizing an
edited document cannot silently preserve an old digest. Merely
preserving an old raw digest while changing a typed speed, port or geometry field
does not establish authority. Existing ingestion performs raw pin verification.
The reference cache is keyed by the fixed installed compiler/source version; it
does not turn mutable caller data into a trusted reference.

`bind_source_profile` derives the actual directed pedestrian/cart graph, complete
source stock, selected slot's separate worker and cart approach nodes, L08 cart
park/intake/output/station anchors, source port endpoint/service/window and
directed belt route. The public schema forbids all these derived fields. Internal
empty placeholders exist only to satisfy the binder's typed template seam and
are replaced before validation; they are neither user defaults nor runnable data.

The existing stock ledger validates recipes, tare/gross mass, finite owners,
original-unit ancestry, geometric containment and nonoverlap. The existing flow
validator checks source routing, capacity and conveyor admission. This compiler
does not duplicate or relax those physical checks.

## Reproducible immutable inputs

SHA256 of canonical frozen JSON is the input hash. It covers compiler version,
normalized explicit choices, full source documents/catalogs/recipes and raw
fingerprints, the verified conveyor document and typed facts, actual public graph
nodes/arcs, materialized profile, initial containers/unit locations/balance and
original unit recipes. Mutable transaction history and private graph adjacency
or caches are excluded. The immutable input package is separate from subsequent
run snapshots and events.

Actors, owners, materials, recipes and orders are sorted by their unique IDs;
source graph arcs/nodes expose their stable public order. Rational 2/4 and 1/2
have the same normalized identity. Directed route order and each explicit unit
placement list are preserved; reordering a placement list remains a distinct
declared input even if a particular physical calculation is commutative. Changing
a synthetic handling tick or source-bound fact changes identity or is rejected.

## Explicit source example and limits

`docs/proposals/adaptive-v3/light-flow-profile.example.json` declares three original
units of `v3:HU:initial:DEMO_001:01`, one carrier and one package. The carrier is a
synthetic 0.32 x 0.24 x 0.24 m container with 0.20 kg tare; the parcel has 0.05 kg
tare. Every home, timing, capacity and placement is visible in the file.
This is not the M07 asset and does not claim a hand/contact mesh proof. The actual
selected worker connector is 0.7 m wide: no claim is made that shrinking was
required. The independent whole-stock mass arithmetic is 9403.85 + 0.20 + 0.05
= 9404.10 kg, and the three-unit shipped parcel is 0.105 + 0.05 = 0.155 kg.

This does not add CLI/API publication, role reassignment, all-class order support,
physical human hand contacts, warehouse-wide collision proof, generated timing
defaults, or a full N0-N4 acceptance claim. No frontend/shared contract or source
input bytes are changed.
