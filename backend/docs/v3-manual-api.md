# Local V3 manual execution API

Launch the existing loopback API with a persistent store, from `backend`:

```powershell
uv run python -m app.api --store-root D:/QoimaTwin-runs/v3-api-store
```

Read `GET /api/v3/manual-profiles`, then send the returned `profile`,
`layout_version` and `source_revision` to `POST /api/v3/manual-runs`.
These are explicit registered server inputs. The request does not accept a local
file path, custom rate, horizon override or event stream. Review
`synthetic_choices` and `unsupported` in the profile metadata before running.

The completed response contains the public `run_id`, `native_run_id`,
`input_hash`, status, capabilities and an absolute API path in `manifest`.
Partial simulation status remains partial. Repeating the same request reuses
verified immutable artifacts, including after a server restart.

| Route | Result |
|---|---|
| `GET /api/v3/manual-profiles` | Registered profile and exact synthetic choices |
| `POST /api/v3/manual-runs` | Actual invariant-checked manual execution or verified reuse |
| `GET /api/v3/manual-runs/{run_id}/manifest` | Native transport plus indexed input, metrics and replay files |
| `GET /api/v3/manual-runs/{run_id}/files/{sha256}` | Exact authorized file bytes with a SHA256 ETag |
| `GET /api/v3/manual-runs/{run_id}/seek?cutoff_tick=80000000` | Settled state at80s on the1,000,000ticks/s clock |

Use returned IDs, not filesystem paths. The public API ID binds the native run,
frozen input bundle and export protocol; the nested transport keeps its native
run ID. Check raw byte sizes and SHA256 against descriptors. A seek reads one
checkpoint part and relevant event parts, without the graph or all history.
Forward/backward/repeated seeks preserve inventory and paid-return state.

V2 and V3 simulations share one calculation slot. A competing uncached job
receives409 `calculation_busy`. HTTP cancellation does not interrupt admitted
work; shutdown waits for it. Invalid requests return422, unknown run/files404,
and corrupt stored artifacts500 with structured errors. Provider credentials
are not part of this API and Mercury is never invoked by a manual simulation.

This is a separate proposal with `actual_engine_run=true`,
`full_v3_warehouse=false`, `frontend_adapter=false`. It executes only the frozen
four-job SMALL/STANDARD demo. The existing Tilek V2 reader and his local visual
forklift fixture do not consume this schema. See [ADR0035](adr/0035-v3-manual-api-publication.md)
and the [manual profile](v3-manual-profile.md) and [run transport](v3-manual-run.md)
guides for the scope and source bindings.
