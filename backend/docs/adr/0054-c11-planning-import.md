# ADR 0054: Import C11 as a separately pinned planning comparison

Status: accepted backend implementation decision; planning proposal only.

## Decision

The six C11 documents at upstream `be9b4da9b93b2c99aacfd048b8cd3846c91efc82`
form a separate backend source package. Their bytes are unchanged at the later
audited `c661a726eede7bd1a38999a311228cb5c279463e`. The package records raw SHA256,
byte counts and Git blob IDs, and its provenance bytes have their own fixed hash.
It binds the existing baseline and declared source fingerprints without replacing
the original V3 baseline package or weakening its loader.

Adapted documents are not baseline-assignment documents: their summary, score
units and route records have different semantics. A dedicated typed decoder
preserves these differences. No conversion fabricates missing baseline fields.
Malformed numeric values, duplicate identities, unknown document identity,
changed source bytes, period mismatch and unsupported admission claims are rejected.
Requested period counts require exact integers; `true`, `1.0` and `Fraction(1)`
cannot alias the one-period identity. Verified baseline documents are frozen as
canonical bytes, and accessors return fresh parses rather than mutable shared views.

Public planning also compares reconstructed package objects against an independently
loaded pinned reference, including exact nested types and bytes. Retained digest
fields alone are insufficient. A supplied reusable context must match freshly
derived source facts; evaluation uses that fresh context, so modifying its cargo
mass cannot inherit source authority. Every adapted row's module must match its
actual source slot. The production loader evaluates only the pinned documents;
explicit document overrides remain a review seam and do not change package identity.

## Exact comparison and sequence

Periods 1, 2, 4 and 8 are unclocked repetitions of the declared planning flow.
They are not hours, measured demand or DES schedules. The declared 1.4/1.8 m/s
speeds and 12/40-second handling allowances remain proxy assumptions, distinct
from runtime actor rates and paid relocation durations.

Route lengths are recomputed from exact decimal arc facts and directed arc IDs.
The adapter preserves graph mode and loaded-profile restrictions, endpoints and
separate reverse arcs. Reported floating lengths and costs remain separate
diagnostics; they do not supply exact result values. Comparison terms use common
flow weights, periods, source inventory and cost assumptions for both alternatives.

A disposable planning projection applies transfers strictly in source order.
Destinations must be free at the time of that step, and source family, geometry,
orientation, slot/module payload and transport restrictions remain required.
Some accepted destinations are freed by earlier transfers, so evaluating every
move against initial occupancy would change the proposal's meaning. Each HU may
move at most once. Inventory identities, quantities and mass remain conserved.

The one-period no-op is valid. Positive sensitivity results remain planning
comparisons, with exact recomputed gross, one-off relocation and net proxy terms.
No projection mutation is applied to the live stock ledger, calendar or workers.

## Evidence limits

Every result retains `actual_engine_run=false` and `operational_admission=false`.
No actor availability, resource lease, queue, physical contact or paid relocation
is certified. This package does not complete an N0-N4 engine comparison or admit
all cargo classes and ports. Actual relocation requires a later integrated runtime
and its independent physical and timing checks.

The method behind upstream `comparison_inputs_sha256` has not been established;
the adapter explicitly reports `comparison_inputs_sha256_verified=false`.
It verifies the known raw source bindings without claiming that unexplained digest.
The six output/input files are bound by the separate package manifest even where
an individual upstream document lacks a direct raw hash of another output.

Implementation began in Claude's isolated worktree. After an observed account
limit, Codex continued its independent review and found two source-boundary
defects: mutable baseline views, period type aliases, stale reconstructed packages,
mutable contexts and inconsistent row/module identity. Regression tests failed
before the corresponding fixes. Full repository integration and any CLI/API
registration remain separate from this bounded module package.
