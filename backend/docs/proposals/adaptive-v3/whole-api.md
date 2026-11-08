# Registered whole-HU local API proposal

This API selects the checked-in explicit STANDARD receipt/whole-HU profile. It
preserves the source baseline of 530 HUs and 12,256 units and all 24 worker IDs.
Its one new 24-unit STANDARD HU uses the shared receipt/whole calendar and ledger.
Synthetic homes, materials and handling times remain visible in profile metadata.
This is not a frontend contract, heavy-handler admission or full-V3 claim.

Start the existing local server with `uv run python -m app.api`. Its common
calculation worker serves V2, manual, light, receipt and whole jobs. The following
PowerShell selects the registered identity; it does not upload arbitrary choices:

```powershell
$base = 'http://127.0.0.1:8000'
$profile = (Invoke-RestMethod "$base/api/v3/whole-profiles").profiles[0]
$request = @{
    profile = $profile.profile
    layout_version = $profile.layout_version
    source_revision = $profile.source_revision
} | ConvertTo-Json
$run = Invoke-RestMethod "$base/api/v3/whole-runs" -Method Post `
    -ContentType 'application/json' -Body $request
$manifest = Invoke-RestMethod "$base$($run.manifest)"
```

`GET /api/v3/whole-profiles` performs lazy source registration. Subsequent exact
requests reuse the immutable result after checking its actual publication.
Concurrent calculations share one slot and return busy status 409. Disconnecting
or cancelling a client does not release that slot while its owned worker runs.
Source/layout mismatches, unknown profiles and clock/path/quantity overrides are
422 responses. Corrupt stored artifacts are failures, not successful cached runs.

The result has distinct public `run_id`, native `native_run_id`, `input_hash`,
`physical_input_hash` and `request_sha256`. Its status includes paid return and
shared resource release. A shipment at the end cap may therefore remain `partial`.

The manifest wraps the unchanged native transport. `files` are rooted at native
`run/`; `request_files` are the separate outer `profile.json`, `request.json` and
`result.json`. `GET /api/v3/whole-runs/{run_id}/files/{sha256}` returns only an
authorized file, with exact bytes and a quoted SHA-256 ETag. Recorded CLI path
strings are provenance, never API filesystem locations.

Use `GET /api/v3/whole-runs/{run_id}` for the verified result,
`.../checkpoint?tick=T` for an exactly captured integer microsecond tick, and
`.../events?start_tick=A&end_tick=B` for an observed half-open interval of at most
60 seconds. An event at the final observed tick is available with an exclusive
upper bound of that tick plus one. Uncaptured states and arbitrary seek are not
provided; the API does not interpolate a warehouse state.

Verification separates three forms of evidence: hand-fixture HTTP tests, actual
source compiler/identity checks, and no-DES publication/readback of the saved
source CLI bundle. The last is artifact reuse, not a new HTTP-to-engine execution
or a two-run determinism claim. See ADR 0062 for ownership and cache semantics.
