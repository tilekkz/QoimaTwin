# ADR 0049: Publish actual connected SMALL traces and captured checkpoints

Status: accepted backend implementation decision; separate V3 proposal namespace.

## Context

ADR0045 supplies a connected logical SMALL workflow with a shared clock and conserved stock.
ADR0048 supplies strict, source-bound public inputs. ADR0047 supplies separate business and
resource metrics at H/end. Native events do not describe every internal state mutation needed
for arbitrary replay, so a publication must expose actual observations without implying seek
capabilities that have not been implemented and tested.

## Decision

`simulate_light_file(bundle_path, profile_path, out)` is a callable backend boundary. It rejects
nonempty output, parses JSON with duplicate-key rejection, loads verified sources, and compiles
the explicit public profile before creating output. It publishes canonical `inputs.json` before
constructing `LightFlowEngine`. Failure during construction or execution retains these inputs;
no success manifest is published. CLI route registration and API integration are separate work.

The native run identity is SHA-256 of canonical `{engine_version, input_hash}`. The explicit
engine version is `LIGHT_FLOW_ENGINE_VERSION`; input hash covers the frozen choices, source
fingerprints, source documents, graph, materialized profile and initial stock. The builder checks
that its typed profile and clock still match the frozen input record. The writer/reader bind the
immutable catalog and clock back to those exact canonical bytes. Changing a choice changes identity;
permuting set-like input arrays preserves the compiler's canonical inputs and published bytes.

The run uses `qoima.connected-small-run.v3-proposal`, version `0.1.0`; its manifest uses
`qoima.connected-small-manifest.v3-proposal`. These backend proposals do not modify or claim
agreement on shared contracts or frontend formats. Explicit capabilities declare an actual engine
component run and internal inventory integration. Full V3, frontend adaptation, hand-contact proof,
arbitrary seek and interpolation are false.

Immutable inputs and `catalog.json` hold source graph, recipe definitions, actor/owner catalogs,
container recipe references and immutable source unit ancestry. A captured checkpoint holds only
mutable container IDs/owners/seals, unit locations, revision, balances, orders, workers, cart,
belt poses/open motions, resource leases and exposure counters. It does not repeat container
recipes, unit recipes, origin tokens or journal history. Native stock deltas are similarly projected
to mutable before/after contents and unit IDs; their immutable ancestry remains in the catalog.

Checkpoints come from actual native observations at zero, each settled 30 seconds, H and actual
end/cap. Duplicate observations at the same tick must agree. A checkpoint's `last_seq` is the last
actual event with tick less than or equal to that checkpoint tick; its state hash covers the full
mutable state. H may be later than actual completed end, in which case H is a separately captured
unchanged observation. Open operation/motion plans retain their planned endpoints, while validation
requires their observation to lie inside the unfinished interval. Plans are not future completions.

`build_flow_run` validates by default. The public file boundary builds with validation deferred to
the writer, which performs the run schema and semantic checks once before artifact publication.
Draft 2020-12 JSON Schema checks strict run, manifest, event and checkpoint envelopes and mutable
state fields. Semantic validation checks identity, source revision, contiguous event sequences,
observed time bounds, cadence, inclusive checkpoint watermarks/state hashes, H/end agreement,
all 24 actors, unit conservation/reference membership, and open motion timing. Immutable detailed
catalog values must equal frozen input values; metrics retain ADR0047's separately validated form.
Scalar mass and SKU balances are recomputed from immutable unit/tare recipes and captured locations.
Owner capacity and delta selected-unit/before-after consistency are checked independently of hashes;
H/end business counts must agree with captured conserved shipments and order states. Frozen input
comparisons use canonical bytes so Python's `False == 0` equality cannot hide a JSON type change.

Events are split into half-open 60-second buckets `[k*60,(k+1)*60)`.
A size split may create multiple
files in a bucket. Raw canonical JSON chunk bytes are bounded by an explicit limit, at most 8 MiB;
a single item exceeding it fails publication. Checkpoints use the same bounded transport but retain
their own exact capture ticks. Descriptors contain relative path, raw byte length/hash, bucket and
actual first/last ticks. Hashes cover exact file bytes, not filenames or decoded/re-encoded objects.

Files are published exclusively through a temporary file and an atomic hard link. Existing files
are never overwritten. The writer accepts only an empty directory or the one exact prewritten
`inputs.json`; a partial publication is retained for diagnosis and is not silently resumed. The
validated manifest is published last. Its presence marks complete publication, not complete
warehouse business processing: a valid artifact may have operational status `partial`.

The reader verifies strict descriptors, relative paths, byte bounds, file sizes/hashes, run/input
identity, source/catalog binding and semantic observations. It rejects traversal and duplicated
paths. `captured_checkpoint(root, tick)` returns only an exactly captured tick and rejects all
others. `event_window(root, start, end)` returns a half-open interval of at most 60 seconds.
The current reader validates the whole bundle before these selections; it does not claim bounded
total memory or instant streaming seek. Raw chunk bounds are independent of that reader behavior.

## Evidence and limits

Hand-derived publication tests retain the single-order 192.17-second shipment and 197.17-second
paid-return end, while H50 has no completed units. An arrival shifted to second47 deposits at
exactly second60: that actual event belongs to the next bucket, and the settled second60 checkpoint
already contains its effect. At cap61, ongoing belt motion remains open and no shipment exists.

Tests also cover inputs-before-construction, constructor/runtime failures, nonempty output,
set-permutation determinism, choice identity, corrupted raw files and descriptor traversal,
too-small byte limits, forged sequences/watermarks, duplicated immutable data in state and invalid
open motion timing. Expected timelines remain the pre-engine ADR0045 arithmetic, not measured
engine output. A source demonstration is execution evidence, not a performance benchmark.

No arbitrary replay is reconstructed from final state or inferred task schedules. Future replay
needs a complete settled mutation journal and tested interpolation/exposure semantics. No live
frontend animation, M07 tote, finger contact, all-eight-class workload, replenishment or heavy
workflow claim follows from this connected SMALL artifact. The explicit material recipes and
logical service assumptions remain visible in frozen inputs and ADR0045.
