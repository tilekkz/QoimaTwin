# ADR 0051: Register connected SMALL runs in the shared local API

Status: accepted backend implementation decision; local V3 proposal endpoint.

## Decision

The local API exposes one explicitly registered profile, `explicit-source-small-three-units-v1`,
from the backend proposal example. Requests name this profile and its layout/source revision;
they cannot supply paths, graph overrides, arbitrary profile JSON, timings, horizon or material
recipes. Strict Pydantic requests reject unknown fields. The existing loopback launch and
same-origin/proxy deployment policy remain unchanged; no frontend adapter is added.

Registration is lazy once per application instance, protected by an asynchronous lock. Unrelated
V2/manual calls do not compile the light profile. On the first light request, the server verifies
the pinned source bundle/conveyor and strictly compiles the raw profile before normalizing its
canonical choices. This ordering is essential: normalization must not turn a boolean rational
numerator into an accepted integer. Registration freezes source files, canonical choices and
compiled input bytes into the immutable store before any execution job is queued.

The profile cannot drift during that application instance. A job restores the registered source
files and choices, verifies the registered conveyor bytes against the pinned server supplement,
and calls the real `simulate_light_file` pipeline. Canonical inputs therefore precede engine
construction exactly as in ADR0049. Unique attempt directories retain source/input evidence on
failure; sanitized errors contain no original exception message or local file path. Failed attempts
publish no successful run/request reference. A valid operationally partial run remains `partial`.

`light-v3` is an additional handler in the existing process worker. V2, manual and connected jobs
share the same `JobService` admission slot and the same owned single-worker `ProcessPoolExecutor`.
No new executor, background task or simulation thread is introduced. Concurrent uncached jobs
receive the existing 409 busy error; client cancellation does not release the slot before actual
completion. Repeat POSTs reuse the immutable request/run result and do not start another simulation.

The request cache key binds the registered bundle, compiled input hash, compiler version, explicit
connected engine version and export version. The public run ID separately binds the native ID and
exact registered bundle in the connected API domain. A domain-scoped run index holds native/public
identity, input bundle/hash, and a complete relative-path/raw-hash/size inventory. Readers reject
foreign profile bundles and native IDs even when the generic reference checksum is self-consistent.

## Routes

| Route | Meaning |
| --- | --- |
| `GET /api/v3/light-profiles` | Registered choices, source/hash/version and capability metadata |
| `POST /api/v3/light-runs` | Execute or reuse the registered profile in the shared worker |
| `GET /api/v3/light-runs/{id}` | Verified published operational status and identity |
| `GET /api/v3/light-runs/{id}/manifest` | Verified transport manifest and API file inventory |
| `GET /api/v3/light-runs/{id}/files/{sha256}` | Exact immutable raw bytes with SHA-based ETag |
| `GET /api/v3/light-runs/{id}/events` | Observed half-open window, at most 60s |
| `GET /api/v3/light-runs/{id}/checkpoint?tick=T` | Only an exactly captured native checkpoint |

POST body:

```json
{
  "profile": "explicit-source-small-three-units-v1",
  "layout_version": "use the value returned by light-profiles",
  "source_revision": "use the value returned by light-profiles"
}
```

The events route takes `start_tick=A&end_tick=B`.
Tick query values are canonical nonnegative integer strings with a bounded length; decimal,
boolean and negative forms are rejected. An event window must lie within the observed event
timeline, with an exclusive end allowing the final observed event at `end_tick - 1`.
Captured H remains available even when H is later than actual completed end. Unknown runs/files
return 404; invalid profiles/windows or uncaptured ticks return 422. Known corrupt artifacts return
the existing typed artifact-corruption error. There is no light `/seek` route.

## Verification and caching

Before serving a run, readers check its registered bundle, native/public identity, exact file
inventory, confined relative paths, raw sizes and SHA-256 values. The registered source/profile
objects and every run file are rehashed on every read/reuse, including files outside a requested
early window. Corruption after warming a cache therefore cannot hide behind a cached response.

A bounded eight-entry semantic cache stores only a small validated response, manifest and captured
tick list, keyed by store root and canonical immutable index. It does not retain full snapshots or
whole-run objects. Cache misses reconstruct a temporary bundle and invoke the final ADR0049 reader,
including exact scalar mass/SKU checks, owner capacities, delta consistency, frozen type identity,
captured business counts and checkpoint validation. Operational status must also agree with actual
orders, workers, conveyor and leases. In particular, an empty worker order ID does not prove
completion while its operation or waiting interval remains open. A completed cart must have no
order/operation, and a completed belt carrier must have no motion or occupied cells.
Raw verification always precedes semantic-cache reuse.

After verification, an exact checkpoint request reads its captured chunk; an event request reads
intersecting event chunks and filters the requested half-open interval. This is not arbitrary
replay or interpolation. First semantic validation still loads the complete native bundle; no
streaming memory or client 64MiB claim is made. Public responses retain
`operational_admission=false`,
and native capabilities keep full V3, frontend adaptation and hand-contact proof false.

## Evidence boundary

Tests use the public profile and one actual source artifact. `QOIMA_TEST_LIGHT_ARTIFACT` may point
to an existing verified artifact for focused checks; absent that test-only setting, the fixture
creates it once and reuses it across HTTP boundary tests. The injected test processor publishes
those real bytes; production uses the actual spawned worker and real simulation pipeline.
TestClient verifies HTTP contracts but is not evidence of a real listening server. A separate
loopback lifecycle check after integration is required before claiming live HTTP proof.

No shared contract, frontend, Mercury setting, paid provider or existing manual replay semantics
are changed. This endpoint publishes the bounded logical SMALL workflow, preserving the source
stock and all 24 identities. It does not establish full-warehouse execution or physical hand
contact.
