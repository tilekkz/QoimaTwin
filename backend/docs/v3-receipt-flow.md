# Connected SMALL receipt workflow

The receipt CLI runs inbound service, finite staging, putaway, unit picking,
cart/belt transport, packaging and shipment on one event calendar and unit
ledger. All 24 actors retain their identities. A received HU and its units are
created only when inbound service completes; declaring an offer does not add
future stock to the initial state.

From `backend/`, using a new or empty output directory:

```bash
uv run python -m app.cli v3 simulate-receipt --profile docs/proposals/adaptive-v3/receipt-flow-profile.example.json --out runs/v3-receipt
```

The explicit example uses the pinned V3 source package and one new 24-unit
SMALL receipt at `IN_E_PARCEL`, an initially free source slot and a three-unit
order. Its receiver, buffer connector, handling durations and packaging
materials are declared choices. The compiler validates geometry, mass, source
service windows and exact integer clocks before the shared runtime starts.
Schema and example remain backend proposals under `docs/proposals/adaptive-v3/`.

Inbound service must finish by both H and the source window close. A credited
receipt can finish putaway and paid return after H. Outbound orders are admitted
before H; admitted work can drain afterward. Putaway makes the received HU
available to a unit claim. HU claims and unit claims share one authority and
cannot promise the same stock concurrently. Shipment and worker return remain
separate facts; complete status requires cleared operational state.

Exact frozen `inputs.json` is published before engine construction. Failure
retains that evidence without a success manifest. Successful publication writes
the manifest last, with hashes and byte lengths for catalog, metadata, event and
checkpoint parts. The receipt run namespace is
`qoima.connected-receipt-small-run.v3-proposal/0.1.0`; the manifest has its own
receipt namespace. It is distinct from the existing light API and Run 2.0.

Checkpoints capture settled state at 0, every 30 seconds through the observed
end, exact H and exact end. They store current inventory, claims, custody,
workers, resources and belt state. Immutable recipes and planned receipt
descriptors stay in the catalog; history stays in ordered event chunks.
Transport uses half-open 60-second buckets, split into parts when necessary.
The 8 MiB part limit is not a total-export or reader-memory bound.

Both writer and reader validate creation against declared inputs, all journal
transitions, active claims, service actors, handling completion boundaries and
captured watermarks. Recomputing hashes does not make a semantically invalid
history valid. Counts and exposure metrics distinguish `at_horizon` from
`at_end`; this profile does not infer hourly workload from unclocked weights.

The local API exposes the same example at `GET /api/v3/receipt-profiles`. Submit
its `profile`, `layout_version` and `source_revision` to
`POST /api/v3/receipt-runs`. The request accepts no profile path or quantity/clock
overrides. Receipt jobs share the existing single calculation slot with the V2,
manual and light workflows. Repeated submissions reuse the same verified result.

The returned public run ID supports these reads:

- `GET /api/v3/receipt-runs/{run_id}`: actual complete or partial status.
- `GET /api/v3/receipt-runs/{run_id}/manifest`: native manifest and stored files.
- `GET /api/v3/receipt-runs/{run_id}/files/{sha256}`: exact CLI bytes with an ETag.
- `GET /api/v3/receipt-runs/{run_id}/checkpoint?tick=T`: an exact captured tick.
- `GET /api/v3/receipt-runs/{run_id}/events?start_tick=A&end_tick=B`: an observed
  half-open window of at most 60 seconds; tick values are integer microseconds.

The public ID includes the frozen server registration. Its native ID remains
the one in the CLI manifest. Reads rehash stored files and validate native
receipt history; warming the cache does not permit later byte tampering.

This is a bounded SMALL backend component. An adopted frontend adapter,
continuous hand contact, all cargo classes and ports,
dynamic role allocation and complete warehouse operation remain unsupported.
The synthetic carrier and material recipes are not resized or approved visual
assets. These limits remain explicit in exported capabilities.
