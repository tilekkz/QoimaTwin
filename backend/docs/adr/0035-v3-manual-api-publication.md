# ADR 0035: Registered V3 manual runs in the shared local API worker

Status: accepted for the bounded backend manual proposal; shared contracts remain unchanged.

Expose the existing actual manual CLI pipeline through `/api/v3/manual-runs`.
The client selects the registered `manual-whole-hu-demo-v1` profile and echoes
its exact layout version and source revision. The server supplies all source
and proposal files. Filesystem paths, arbitrary events, rates, horizon overrides,
materialized bypasses and unknown profiles are not request capabilities.
`/api/v3/manual-profiles` exposes the frozen synthetic choices and restrictions.

At application creation, verify the immutable input package and store its raw
source/proposal bytes by SHA256. The job references that frozen bundle, so later
filesystem edits cannot change admitted work. The worker restores those verified
bytes, materializes inputs before creating the engine, enables invariants and
publishes only a fully validated actual run. A failed attempt retains local
input and sanitized failure evidence without a successful run/request reference.

Reuse the same single spawn worker and `JobService` admission slot as V2.
The V2 request-key construction is unchanged. An uncached competing V2 or V3
calculation receives 409; cached results remain available. Client cancellation
does not cancel admitted work or release its slot, and shutdown drains it.
Heavy computation does not run in the ASGI event loop. File validation and
replay reads use threads; they do not start another simulation worker.

The domain is `qoima-v3-manual-api-1`. Request identity binds the raw frozen
bundle, canonical profile, source layout, manual engine version and export
protocol. The public API run ID additionally binds the native run ID, frozen
input bundle and export version. It is distinct from the native run identity.
General immutable store namespaces are reused with explicit domain tags;
manual routes reject references from another domain.

Publication writes content-addressed input, metrics and transport files first,
then the domain-bound run index, then the cached request response. Reads verify
raw hashes. The public run ID must recompute from the index. The manifest must
be schema valid and belong to that native run; every transport descriptor must
match exactly one indexed path, raw size and hash. Extra input and metrics
files are allowed, duplicate index paths are not.

A repeated POST validates the referenced native run and reconstructs the exact
response. Status, input/native/public IDs, source label, capabilities and route
must agree with the cached response and the requested frozen bundle. A coherent
checksum envelope alone cannot establish these semantic bindings.

Keep a bounded process-local cache of successful semantic validation, keyed by
the resolved store root and complete canonical run index. Store only immutable
response bytes in that cache. Every reuse still validates the index/manifest
relations and rehashes every indexed raw file before looking up that cache;
changed indexes require fresh full validation and corrupt bytes always reject.
This avoids repeating expensive full replay on unchanged artifacts. It never
caches errors, ignores source changes or reuses a mutable caller response.

Seek retains ADR0033's bounded read: restore the metadata, selected checkpoint
part and intersecting event parts, then use the existing transport reader.
It never restores the graph or all historical chunks just to seek. The response
contains settled state at an exact integer tick; out-of-range cutoffs reject.

The only registered workload has four synthetic whole-HU jobs over two ports,
one declared buffer each, H600/end900, 530 initial HUs, 200 SKU and all24 actors.
Published runs say `source_label=actual_engine_run`, `full_v3_warehouse=false`
and `frontend_adapter=false`. This API does not implement N0-N4, heavy handling,
picking/packing, conveyors or a reader for Tilek's V2 frontend.

Evidence includes an actual source spawn-worker request, immutable restart
reuse, raw-file hashes and repeated seek; hand-fixture regressions cover shared
admission/cancellation, failed publication, bounded reads and independently
reproduced coherent-but-wrong ID/cache/manifest/index combinations.
