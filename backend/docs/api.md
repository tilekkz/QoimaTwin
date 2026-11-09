# Local experiment API

The API runs materialization, forecasting, planning and A/B comparison against the installed
contract bundle. Shared Run 2.0 is the default output. `2.1-proposal` is an explicit backend
proposal, not an agreed replacement for the shared contract. See [ADR0018](adr/0018-local-api-and-immutable-artifacts.md).

## Start locally

From PowerShell, with Python 3.12 and uv installed:

```powershell
Set-Location D:/QoimaTwin/backend
uv sync --frozen
uv run python -m app.api --store-root D:/QoimaTwin-runs/api-store
```

The default address is `http://127.0.0.1:8000`; `/docs` exposes the generated OpenAPI interface.
`--port 8001` changes the port. `--host` is an explicit bind choice; the default is loopback.
Without `--store-root`, objects are stored in `backend/artifacts/api`.

This local API has no user authentication or permissive CORS configuration. Use a same-origin
frontend or a development reverse proxy for `/api` to the loopback server. Different ports are
different origins; opening a frontend on another port does not automatically grant browser
access. Binding to another interface alone does not configure authentication or CORS.

## Reproducible request sequence

Use IDs returned by the server. IDs are 64 lowercase hexadecimal characters; they are not file
paths, display names or mutable aliases. All bodies reject unknown fields. The examples use a
short 600-second run; use `3600` for one hour or `28800` for eight hours. Longer calculations
take longer; this document does not claim timings for these example requests.

The following PowerShell helper sends JSON, preserving integer and string types:

```powershell
$apiBase = 'http://127.0.0.1:8000'
function Invoke-QoimaPost([string]$route, [hashtable]$body) {
    Invoke-RestMethod -Method Post -Uri "$apiBase/api/$route" `
        -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 20)
}
$catalog = Invoke-RestMethod "$apiBase/api/catalog"
$layoutVersion = $catalog.layout_version
```

`GET /api/catalog` returns `schema_version`, `layout_version`, `engine_version`, `bundle_id`,
the default `assignment_id`, `sku_ids`, and profile definitions. It does not expose server paths.

### Materialize a scenario

```json
{
  "schema_version": "2.0",
  "layout_version": "qoima-72x48-v2",
  "profile": "large-normal",
  "horizon_s": 600
}
```

Send this to `POST /api/scenarios/materialize`:

```powershell
$materialized = Invoke-QoimaPost 'scenarios/materialize' @{
    schema_version = '2.0'; layout_version = $layoutVersion
    profile = 'large-normal'; horizon_s = 600
}
```

The response supplies `scenario_id`, `history_id`, `assignment_id`, `scenario_name`, `horizon_s`,
`shortened_run`, `orders`, and `receipts`. Profiles are `large-normal`, `large-peak`, and
`promotion`; horizon is an integer from 1 through 604800 seconds. Optional `assignment_id`
must refer to an existing valid assignment. No request-side quantity correction is performed.

### Forecast with mean28 or HGB

`POST /api/forecast` takes the returned history ID:

```powershell
$meanForecast = Invoke-QoimaPost 'forecast' @{
    schema_version = '2.0'; layout_version = $layoutVersion
    history_id = $materialized.history_id; model = 'mean28'
}
$hgbForecast = Invoke-QoimaPost 'forecast' @{
    schema_version = '2.0'; layout_version = $layoutVersion
    history_id = $materialized.history_id; model = 'hgb'
}
```

Equivalent JSON shape: `{"schema_version":"2.0","layout_version":"qoima-72x48-v2",
"history_id":"<history_id from materialize>","model":"mean28"}`. Angle-bracket values in
this explanatory shape must be replaced; they are not valid literal IDs.

Responses contain `forecast_id`, `source_history_id`, and `forecast`. The stored semantic
forecast excludes CPU timings; timing variation does not define a different forecast artifact.
Forecast visits use the declared full-day temporal protocol; the planner scales them to the
scenario horizon. Forecasts are fitted from history, not the held-out scenario orders.

### Plan budgets 0, 2 and 8

`POST /api/plans` uses a scenario, forecast, and integer swap budget:

```powershell
$plans = @{}
foreach ($budget in @(0, 2, 8)) {
    $plans[$budget] = Invoke-QoimaPost 'plans' @{
        schema_version = '2.0'; layout_version = $layoutVersion
        scenario_id = $materialized.scenario_id
        forecast_id = $meanForecast.forecast_id
        assignment_id = $materialized.assignment_id
        budget_swaps = $budget
    }
}
```

Only integer `0`, `2`, or `8` is accepted, including budget 0 for a no-op. Use
`$hgbForecast.forecast_id` to plan from HGB instead. The result includes top-level `plan_id`,
`scenario_id`, `forecast_id`, `baseline_assignment_id`, `candidate_assignment_id`, and `plan`.
Use **top-level `plan_id`** in the comparison request: it identifies the stored plan envelope;
the nested domain `plan.plan_id` is not its storage reference. The frozen ABC baseline is built
from training demand. Plans are evaluated on the same scenario with unchanged shared inputs.

### Compare and publish both runs

`POST /api/compare`:

```powershell
$comparison = Invoke-QoimaPost 'compare' @{
    schema_version = '2.0'; layout_version = $layoutVersion
    scenario_id = $materialized.scenario_id; plan_id = $plans[2].plan_id
    output_format = '2.0'
}
$proposalComparison = Invoke-QoimaPost 'compare' @{
    schema_version = '2.0'; layout_version = $layoutVersion
    scenario_id = $materialized.scenario_id; plan_id = $plans[2].plan_id
    output_format = '2.1-proposal'
}
```

Omitting `output_format` selects `2.0`. The request's `schema_version` stays `2.0` even when
proposal output is requested. The response contains `comparison_id`, `comparison`, and
`runs.baseline` / `runs.candidate` run IDs. Baseline and candidate are simulated once each per
uncached comparison request; changing output format is a distinct request and may simulate again.
The proposal format uses its own run identity namespace.

HTTP 200 and envelope `status: "passed"` mean the calculation returned a valid result. They do
not imply that all warehouse work completed. Inspect each run's complete/partial status,
termination reasons, subsystems and both `at_horizon` / `at_end` summaries. A completed comparison
may legitimately contain partial runs, including blocked receiving, and may report a worsened
plan. Those results are retained rather than retried until they look favorable.

## Read bounded replay data

```powershell
$runId = $proposalComparison.runs.candidate
$manifest = Invoke-RestMethod "$apiBase/api/runs/$runId/manifest"
$window = Invoke-RestMethod "$apiBase/api/runs/$runId/chunks?from_s=80&limit=1"
```

The manifest response contains the manifest plus parsed `catalog_data`. Shared2.0 manifests
have `chunks`; proposal manifests have `event_chunks` and `snapshot_chunks`. Follow descriptors,
not assumed filenames. A descriptor contains `path`, `bytes`, and `sha256`, with time-range or
checkpoint metadata where applicable.

The window response is `{run_id, from_s, chunks:[{descriptor,payload}],
snapshots:[{descriptor,payload}], next_from_s}`. `from_s` is finite and nonnegative; `limit` is
1–3. Chunks overlap the requested start. For proposal seek, snapshots contain the nearest full
checkpoint and the required deltas through `from_s`. Decode the chain, then replay ordered
events to the target. Use `next_from_s` for the next window until it is null. The raw referenced
files selected for a window are capped at 8,000,000 bytes; oversized requests return 413. Parsed
HTTP envelope size is not the raw bundle-byte measurement.

To download a referenced file with its original bytes:

```powershell
$descriptor = $manifest.catalog
$downloadPath = Join-Path $env:TEMP 'qoima-catalog.json'
Invoke-WebRequest "$apiBase/api/runs/$runId/files/$($descriptor.sha256)" -OutFile $downloadPath
$actualHash = (Get-FileHash -LiteralPath $downloadPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $descriptor.sha256) { throw 'Replay file hash mismatch' }
if ((Get-Item -LiteralPath $downloadPath).Length -ne $descriptor.bytes) {
    throw 'Replay file length mismatch'
}
```

`path: "events/000001.json"` is a bundle-relative path, **not** an API route or artifact ID.
For HTTP use `/api/runs/{run_id}/files/{sha256}`. For a static bundle resolve `path` relative to
its manifest URL. Hash the exact uncompressed file bytes; JSON reserialization may change the
hash. The raw endpoint returns an ETag containing that SHA256 and enforces the same 8 MB limit.
Only catalog/event-chunk/snapshot-chunk references belonging to the selected run are exposed.
An optional `inline` descriptor does not make the inline file available through this endpoint.

## Optional Mercury explanation

Only this explicit request calls the configured explanation provider:

```powershell
$explanation = Invoke-QoimaPost "compares/$($proposalComparison.comparison_id)/explanation" @{}
```

The body is exactly `{}`; it accepts no credentials, endpoint, filesystem path, custom prompt or
client-authored numerical facts. The server extracts facts from the stored comparison and sends
those facts for advisory explanation. Complete and partial simulation results are supported;
failed or running results are rejected. Simulation/forecast/planning never require this call.

Set `INCEPTION_API_KEY` only in the server process environment or the ignored `backend/.env`.
The API reads that trusted path; clients cannot select it. Process environment takes precedence.
Optional server settings are `MERCURY_MODEL` (default `mercury-3`), `MERCURY_TIMEOUT_S` (default10,
maximum30), and `MERCURY_MAX_COMPLETION_TOKENS` (default1024, maximum4096). No key belongs in a
request, frontend configuration, run artifact, log, or source-controlled file.

Explanation requests run off the event loop in a thread. Identical requests share an in-flight
task and reuse the persisted result keyed by comparison, facts, model and prompt semantics.
Provider errors use sanitized codes; provider response bodies and credentials are not returned.
The explanation is advisory; measured comparison facts remain authoritative.

## Admission, cancellation, persistence and errors

Materialize/forecast/plans/compare use one owned spawn-process worker. Only one uncached heavy
calculation is admitted at a time; another receives HTTP409 `calculation_busy`. These are
synchronous HTTP requests that await completion, not202 job handles. Retry after the running
request finishes. Repeated completed requests reuse immutable results; the request-cache key
includes the engine version and input bundle. A cached request can succeed while another job runs.

Disconnecting or cancelling the HTTP waiter does not stop the worker or free its admission slot.
Its result may still be published and recovered by repeating the request. Graceful shutdown waits
for owned calculations and explanation tasks, then shuts down the process pool. There is no
public cancellation endpoint or progress stream.

Objects are content-addressed and published atomically without overwriting existing bytes.
Referenced run files are published before the immutable manifest. Keep the store to reuse IDs
across server restarts; IDs from a different empty store are unknown references.

Errors use the same JSON envelope shape as the CLI:

```json
{
  "status": "failed",
  "issues": ["request validation failed: extra_forbidden"],
  "error": {
    "code": "invalid_input",
    "message": "request validation failed: extra_forbidden"
  }
}
```

| HTTP | Typical condition |
|---|---|
| 422 | Unknown/malformed input reference, schema/layout mismatch, unknown fields, invalid horizon/budget or plan/scenario mismatch |
| 404 | Unknown run or file not referenced by that run |
| 409 | `calculation_busy` or conflicting immutable publication |
| 413 | Requested replay file/window exceeds the raw-byte bound |
| 500 | Unexpected backend failure (`execution_error`) or artifact integrity failure |
| 429/502/503/504 | Optional explanation rate limit/provider failure/unavailable/timeout |

## Historical V2 frontend boundary

At inspected Tilek frontend commit `10496fd4ccd748676c036c371dd1a29881f046d1`, the entry point
loads one inline Run2.0 JSON file. Visual seek is implemented, but there is no API/manifest/chunk
loader or proposal full/delta business-state decoder. This API does not change that frontend.
It needs an agreed loader and handlers before streamed proposal runs can be replayed there.
Renaming `schema_version` is not an adapter. Shared2.0 remains the default until that agreement.
This paragraph describes the inspected V2 commit only. The newer V3 source geometry
and visual prototype have a separate native-engine integration boundary described in
[the V3 delivery scope](v3-delivery-status.md).

## V3 manual execution

The [connected receipt API](v3-receipt-flow.md) registers one explicit source profile
at `/api/v3/receipt-profiles` and executes it through `/api/v3/receipt-runs` on the
same owned calculation worker. Its separate native/public identities, immutable
files and exact captured-state reads preserve the connected receipt journal.
It does not expose arbitrary seek or adopt the proposed V3 frontend contract.

The [registered whole-HU API](proposals/adaptive-v3/whole-api.md) adds
`/api/v3/whole-profiles` and `/api/v3/whole-runs` for the explicit STANDARD
receipt/whole-HU profile. It uses that same worker slot and preserves separate
public/native identities, bound request evidence and the native `run/` inventory.
Readers expose verified files, exact captured ticks and observed half-open event
windows; terminal status includes paid return and shared resource release.
Caller clocks, paths and physical overrides are rejected. This backend proposal
does not enable a V3 frontend adapter or general heavy handling.

The [registered coordinator API](v3-coordinator-api.md) adds source-bound multi-resource
execution through `/api/v3/coordinator-profiles` and `/api/v3/coordinator-runs` on
the same worker. It preserves native namespace3 identity, actual staffing, horizon/end
metrics and paid resource return. Captured checkpoints remain exact-only; the separate
[`/replay?tick=T` reader](v3-coordinator-replay-api.md) reconstructs settled state through
any observed integer tick after full evidence validation, without another simulation.
The ordinary registered profile contains two unit orders. Mixed receipt/shipment N4
experiments remain separate explicit CLI profiles; arbitrary profile submission is rejected.
The assembled implementation and prewritten tests await final verification.

The separate [V3 manual API guide](v3-manual-api.md) documents registered frozen
profiles, actual manual simulation, immutable files and bounded seek under
`/api/v3/manual-runs`. It shares this API's calculation worker. Its proposal
schema and limited capabilities are separate from the V2 endpoints above.
