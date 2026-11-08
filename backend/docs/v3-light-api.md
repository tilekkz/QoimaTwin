# Connected SMALL local API

Run `uv run python -m app.api --store-root D:/QoimaTwin-runs/api-store` from
`backend/`. The registered connected profile is separate from V2 and manual
V3 runs, while all three share the same single simulation-worker capacity.

| Method and route | Result |
| --- | --- |
| `GET /api/v3/light-profiles` | Registered profile, source identity and explicit choices |
| `POST /api/v3/light-runs` | Execute the registered frozen profile or retrieve its verified result |
| `GET /api/v3/light-runs/{run_id}` | Verified complete/partial status and capability limits |
| `GET /api/v3/light-runs/{run_id}/manifest` | Native transport manifest and public raw-file inventory |
| `GET /api/v3/light-runs/{run_id}/files/{sha256}` | Exact JSON bytes with their SHA256 ETag |
| `GET /api/v3/light-runs/{run_id}/checkpoint?tick=T` | State at an exactly captured integer microsecond tick |
| `GET /api/v3/light-runs/{run_id}/events?start_tick=A&end_tick=B` | Observed half-open interval, at most60 seconds |

POST accepts exactly `profile`, `layout_version` and `source_revision`, copied
from the profile listing. The registered profile is
`explicit-source-small-three-units-v1`; request filesystem paths and arbitrary
execution choices are rejected. Use the [CLI](v3-light-flow.md) for other
explicit validated profiles.

Registration compiles and stores immutable inputs before admission to the
worker. A repeated request uses the same public identity and verifies the
stored result. Simultaneous duplicate jobs share the existing calculation;
other calculations receive409 while capacity is occupied. Failed attempts
retain diagnostic inputs without a success reference. Partial results remain
partial and keep actual work/resource state.

The public run ID binds the registered bundle, compiler, engine, export version
and native run ID. Every read verifies the source registration and all raw file
hashes before reusing a bounded semantic cache. The cache stores a small summary,
not the whole expanded run. Initial validation still reads the full bundle;
this is not a streaming-memory guarantee.

Only captured checkpoints are available. For example, use recorded ticks in
the manifest rather than requesting an arbitrary `/seek` cutoff. A missing run
or file returns404; invalid input, oversized windows and uncaptured ticks return422.
Stored artifact corruption returns a typed500 response rather than a cached success.

Capabilities remain explicit: full V3, frontend adaptation, hand-contact proof,
arbitrary seek and interpolation are false. This endpoint executes the connected
SMALL component; it does not yet integrate receipt creation, all classes/ports
or N0-N4 policies. See [ADR0051](adr/0051-connected-light-api.md) and the
[actual CLI/HTTP evidence](research/2026-11-08-connected-light-http.md).
