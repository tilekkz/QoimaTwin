# ADR0091: File-driven offer planning and closed evidence bundles

Status: implemented proposal; focused checks and publication status belong to the delivery packet.

## Decision and scope

Expose ADR0087–0090 through `python -m app.cli v3 plan-offers` and
`validate-offer-plan`. The new commands call the existing public history,
forecast, projection, finite-stock and placement-decision producers. Their
namespaces, fresh source checks, frozen bytes and numerical kernels are unchanged.
The only existing-file change is the command registration and dispatch in
`app/v3/cli.py`. No engine, API, frontend or shared contract changes are included.

The caller supplies raw whole-HU history CSV, three separate choice JSON files,
`mean28` or `hgb`, and a new or empty output directory. There is no future actual
test-stream argument, historical visits conversion, inferred clock, default
budget or implicit actor/handling declaration. Current history authority remains
explicitly `declared_synthetic`, not measured warehouse observations. Its exact
56-by-200 grid and local/UTC eight-hour window constraints remain ADR0087's.
Projection requires explicit zero inbound budget; all forecast offers, B2B
offers and finite-stock shortages remain present. A single optional manual
placement candidate retains the narrow permissions and limitations of ADR0090.

Use the existing strict closed choice decoders. History uses its native object;
projection fractions use `{numerator, denominator}` objects; placement fractions
use reduced `[numerator, denominator]` pairs. No cross-namespace coercion or
generic permissive schema is added. JSON object key order and insignificant
whitespace may vary in caller files; their exact raw bytes still enter identity.

## Evidence and failure handling

Read and save the four bounded regular input files, then write `request.json`
with raw descriptors, model and producer/protocol versions before calculation.
Preserve each completed producer's own exact frozen bytes under `history.json`,
`forecast.json`, `projection.json`, `stock.json` and `decision.json`. Reconcile
these five byte strings with the final authenticated nested decision chain.
Write observations next and `manifest.json` last. Files are created exclusively;
existing nonempty output is never reused or overwritten. Linked/junction paths
and shared hardlinked input files are rejected. This is a local evidence format,
not a concurrent writer or hostile filesystem protocol.

A failed attempt preserves all files already written and records `failure.json`
when possible. It has no valid final manifest. An interruption during the last
write may leave an invalid partial manifest; it still fails bundle validation.
No cleanup or retry silently converts such a directory into a valid bundle.

The manifest has a closed inventory and descriptors with exact paths, sizes and
SHA-256 values. `semantic_bundle_id` hashes the version and semantic record:
raw request descriptor, five exact producer descriptors, producer/protocol
versions, final plan ID, selection reason, shortage count and planning status.
CPU/elapsed observations are outside this semantic identity. Their descriptor
is included in the manifest, so changing valid observations changes the
manifest's raw SHA-256 but not `semantic_bundle_id`. Neither hash is a signature
or proof that timing values came from trusted measurements.

## Read validation

`validate_offer_plan(Path)` rejects unknown/missing files, noncanonical manifest,
request or observation metadata, wrong descriptor types/paths/hashes, invalid
timings and inconsistent explicit choices. It invokes the existing public
decision loader once; that loader freshly reconstructs the complete nested
producer/source authority. The validator compares each saved producer artifact
with that reconstructed chain and rebuilds the exact manifest. Rehashing an
altered stage, raw request or semantic field is insufficient for acceptance.

This is data-only validation in the sense of no engine calls or execution. It
can repeat numerical model fitting through the existing forecast verifier;
it is not a cheap JSON reader or a performance benchmark. No extra separate
history/forecast/projection/stock loads are performed by the CLI validator.

## Result semantics and focused acceptance

- `planned`: the producer selected a strictly beneficial supported proposal.
- `infeasible`: a nonempty candidate set has only producer `infeasible` evaluations.
- `no-op`: no selection, including no candidate, nonpositive cost or
  `not_evaluable` evidence. Exact reasons and producer evaluations remain saved.
- `failed`: malformed input, authority failure or incomplete calculation. CLI
  exit status is 1; valid planning statuses and successful validation return 0.

Every successful planning result explicitly reports `engine_calls: 0`,
`operational_admission: false`, `actual_test_stream: false` and
`full_n1_acceptance: false`. `planned` is not a runtime admission or execution
completion; `infeasible` is not an observed operational failure.

Focused tests cover the normal public mean28 source chain and guarded readback,
all four engine constructors/runners forbidden, raw failure preservation,
nonempty output, unknown fields, exact numeric types, malformed history,
rehashed metadata, closed inventory and timing/semantic identity separation.
The source example retains four offers, three shortages and a negative
55,360,003-tick net saving, hence `no-op`. It promises no positive gain, physical
execution, full N1 acceptance, HGB benchmark or successful future workload.
