# 0018. Local experiment API, immutable artifacts and one spawn worker

Status: accepted for the backend implementation; shared 2.1 contracts remain proposals.
Sources: 2026-11-07 PDF pages 6, 9–11; specification01 sections8–11; ADR0008 and0015–0016.

The P0 API runs on the demonstration machine. `python -m app.api` binds to `127.0.0.1:8000`.
Binding another address requires an explicit `--host`. This is a single-server local deployment,
not a multi-user authentication or distributed scheduling service.

## Inputs and routes

Request bodies forbid unknown keys and coercion. `schema_version` defaults to shared input2.0;
an explicit different version is rejected. `layout_version` is required and must match the
validated bundle captured at application creation. Horizon is an integer in1..604800seconds
(168hours); swap budget is an integer literal0,2 or8, never a boolean.

All externally supplied artifact references are lowercase64hex hashes in a typed namespace.
Human-readable scenario/assignment IDs stay inside their artifacts. No HTTP body supplies an
arbitrary local path or an arbitrary Python operation. Unknown/malformed input references,
quantities, versions and domain validation failures return422 without silent repair.

| Route | Request / result |
|---|---|
| GET /api/catalog | Active versions, fixedSKUcatalog, profiles and illustrative assignment reference |
| POST /api/scenarios/materialize | profile,horizon_s,optional assignment reference; immutable scenario/history references |
| POST /api/forecast | history_id,model(mean28/hgb); forecast semantic reference and evaluation |
| POST /api/plans | scenario_id,forecast_id,budget_swaps,optional assignment_id; ABC baseline and candidate plan/assignment references |
| POST /api/compare | scenario_id,plan_id; comparison artifact and both replay run references |
| GET /api/runs/{id}/manifest | Published manifest plus catalog_data, with the original catalog descriptor retained |
| GET /api/runs/{id}/chunks | from_s>=0,limit1..3; chunk descriptors and payloads, next_from_s or null |
| GET /api/runs/{id}/files/{sha256} | Exact referenced catalog/chunk bytes with the SHA256 ETag |
| POST /api/compares/{id}/explanation | Empty strict body; optional Mercury advisory from server-owned comparison facts |

Chunk responses are capped at8MB of raw referenced bytes. Larger windows return413 and can be
retried with a smaller limit; requesting all history at once is not supported. Missing valid
run IDs return404; malformed IDs return422. Exact uncompressed byte hashes and lengths remain
authoritative. Gzip is optional future transport, not a substitute for raw payload measurements.

`POST /api/compare` accepts `output_format=2.0` (default) or explicit `2.1-proposal`.
The proposal exporter includes wire version in run identity, so its manifest cannot collide
with a shared-v2 run. Proposal windows return event `chunks` plus `snapshots`: the latest full
checkpoint and every subsequent delta through `from_s`. The total byte cap includes this chain.
Missing/broken delta bases are artifact corruption, never silently repaired. Exact source bytes
are available through the file route because JSON response reserialization is not hash-preserving.

## Identity and immutable publication

Layout/config/actors are schema/model validated once and persisted as a frozen input bundle.
Jobs reconstruct their typed models from that stored bundle, rather than reading changing input
files midway through a request. Assignments and materialized scenarios are stored before any
simulation. Domain modules remain responsible for slot/stock/reference consistency.

Objects are named by SHA256 of exact bytes (canonical JSON for structured objects). A namespace
and validated hash determine the path. Resolved paths must remain inside the configured root.
Every read verifies its content hash. Files are written and fsynced to a same-directory temporary
file, then published using atomic create-if-absent hard-link semantics. Existing differing bytes
are an immutable-artifact conflict409. Failed publication removes the temporary file.

On Windows, confinement comparison normalizes equivalent resolved drive and UNC extended-length
prefixes on both root and candidate. The actual resolved path is retained for filesystem I/O;
different drives, shares and sibling directories remain outside the root. This prevents a
concurrent first-publication race in Path.resolve representation from rejecting a valid object.

Semantic references (request cache entries and run manifests) contain a content checksum and are
also create-if-absent. All run catalog/chunk/inline objects publish before the run manifest.
A retry never replaces an old run or leaves stale chunks mixed into a new export.

Forecast storage uses `semantic_dict()`: model/protocol/history/parameters/values participate in
the ID; CPU timings do not. The response may expose timing observations outside that semantic
object. Raw source CSV SHA256 and normalized forecast history identity are distinct, explicit
concepts. Plans/comparisons contain no wall-clock measurements in semantic identity.

Before planning, both full-day forecast and training visits are multiplied by horizon/28800.
Only the declared horizon is passed from the scenario to the planner; observed test orders are
never ranking or selection inputs. FrozenABC comes from training visits. The stored plan binds
its scenario and input bundle so compare cannot silently substitute another test workload.

Comparison validates shared layout/config/actors/orders/receipts/initial inventory through the
real comparison module. Both sides share the forecast semantic snapshot; only assignment and
paid relocation plan differ. The `on_run` callback publishes the same two completed simulations,
not two additional simulations. All engines enable invariants. Shared v2.0 remains the default
export; any2.1 transport must be explicitly opted into and marked `contract_status=proposal`.

## Process ownership, admission and errors

FastAPI lifespan owns one `ProcessPoolExecutor(max_workers=1,mp_context=spawn)`. Materialization,
forecasting, planning and comparison execute there, not in BackgroundTasks or the event loop.
Injectable processors are a test seam; the production implementation calls actual domain modules.

P0 admits one calculation at a time, including at most one compare. A second uncached calculation
returns409busy; catalog and replay reads remain available. Completed request results are reused
by a canonical key containing request, bundle, assignment and engine identities. Server restart
can reuse these immutable results. This admission rule is per server; multiple servers against
one root are outside P0 scope.

The HTTP waiter is shielded from the task. A client disconnect cannot cancel already running
process work or release the admission slot early. Shutdown awaits the owned task and closes the
pool. Failed jobs do not populate the completed request cache. A computed comparison may contain
partial runs: HTTP200 means the calculation produced an artifact, not that every subsystem drained.
Explicit run status/reasons remain in each side's outcome and manifest.

The runtime `AppError` envelope is shared with CLI: `status=failed`, issues, error.code/message.
Request validation uses422, busy/immutable conflicts409, missing runs404, oversized windows413,
and unexpected calculation failures500. No raw traceback is returned as the HTTP response.

Unexpected exceptions receive a fixed public execution_error message; their original diagnostic
contents remain server-side. Request validation returns only violation codes, without submitted
values or internal source paths. Catalog exposes bundle/version references, not contracts_dir.

Mercury runs only on the explicit explanation route. Facts and synthetic provenance come from
stored server artifacts, never client prose. Backend settings load lazily from the trusted
backend `.env` path with process environment precedence; there is no HTTP credential/path field.
The synchronous provider executes with `asyncio.to_thread`. Same-key concurrent requests share
one task; a disconnected waiter does not cancel it. Results publish immutably under the service's
comparison/facts/model/prompt cache key and survive application restart. Failed calls are not
cached and can be retried. Secrets and provider responses are absent from API errors: sanitized
codes map invalid facts422, unavailable503, timeout504, rate limiting429, other provider errors502.
Explanation artifacts do not modify authoritative comparison facts or metrics.

## Verification and limits

Tests cover every required HTTP route, repeat-request reuse, invalid versions/quantities/refs,
artifact corruption/atomic failure, bounded windows and cancellation/admission. A real spawned
process fits mean28 to a complete hand-constructed56day200SKU constant history: prediction2 and
WAPE0 are manual oracles. ParentPID differs from workerPID; CPU timings do not enter stored IDs.

Final integration must exercise materialize→forecast→plans→compare with real modules, publish
both runs and retrieve their windows. It also verifies the new RunInputs identity fields and
comparison on_run seam. Full CI and final schema/export integration belong to the main agent.

References: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/),
[Python3.12 ProcessPoolExecutor](https://docs.python.org/3.12/library/concurrent.futures.html#processpoolexecutor),
[FastAPI error handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/).
