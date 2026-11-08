# Public manual whole-HU proposal

Run from `backend` with Python 3.12:

```powershell
uv run python -O -m app.cli v3 simulate-whole `
  --profile docs/proposals/adaptive-v3/whole-flow-profile.example.json `
  --out D:/QoimaTwin-runs/my-whole-run
```

Choose an absent or empty output directory. A partial run returns exit code 1 and
still publishes its actual captured state. A retry needs another empty directory.
The exact manifest path is returned in stdout; it is `OUT/run/manifest.json`.

The checked-in example uses one STANDARD receipt and the same intact HU outbound,
all 24 original actor identities, one shared stock authority and one calendar.
H is 2000 seconds, the end cap is 4000 seconds, and one second is 1,000,000 ticks.
Its source-derived service times are 18 seconds for IN_N_STANDARD and 35 seconds
for STANDARD at OUT_W_RETAIL. The original 530 HUs are unchanged before receipt.
All homes, speeds, handling durations, local buffer geometry, finite owner
capacities and synthetic packaging recipes are visible in the JSON.

`whole-flow-profile.schema.json` defines exact required choices. Rationals use
`{"numerator": 1, "denominator": 2}`, not decimals. Unknown fields, Boolean
quantities, source overrides, duplicate identities and arrivals at/after H reject.
Source-derived slots, anchors, graph, service times and windows cannot be supplied
by the caller. Local connectors must satisfy existing source geometry checks.
No omitted role, material pool, packaging recipe or operation duration is inferred.

`whole_ports` selects allowed finite buffer owner IDs and explicit S01/S02 actors.
`receipt_ports` selects explicit R01/R02 actors. Each buffer has one port and a
visible directed path inside its declared source staging zone. Physical actor
owners must be named `actor:ID`, have kind `worker` and capacity 1. An inbound
port serves one declared class in this proposal; multiple same-class receipts are
allowed when all source slot, geometry and module capacity checks pass.

Whole jobs can select original or explicitly received SMALL/STANDARD HUs. Unit
orders select original baseline SMALL stock only; future-unit picking and unit
splitting of STANDARD are rejected by this compiler. Other classes remain inert
baseline inventory and are not granted physical handling by their presence.

The output contains:

- `profile.json`: normalized author choices, preserving path/placement order.
- `request.json`: compiler version, choices hash, compiled input and physical
  hashes, and exact clocks, written before engine construction.
- `run/inputs.json`: the frozen source-bound publication envelope, also written
  before execution.
- `run/manifest.json`: the validated whole bundle with raw-hashed chunks and
  captured checkpoints. It is published last by the existing writer.
- `result.json`: actual status, manifest/run identity and request hash; failures
  retain the existing input evidence and a structured result when writable.

The request hash is not the native run ID. Equivalent rational notation and
unordered table permutations normalize identically. Source and public compiler
versions remain separately visible. No success is inferred from a file existing;
the strict whole reader validates byte hashes and physical journal semantics.

Before any source execution the example's accounting oracle is 12,256 +24 =12,280
total units, ending with 12,256 onsite and 24 shipped. Total mass is 9,403.85 +.20
carrier +.05 parcel +6.35 received =9,410.45 kg, ending with 9,404.10 onsite and
6.35 shipped. The .32/.24/.24 carrier is an explicit synthetic object, not a
resized M07 asset; no worker contact or forklift proof is claimed. Route timings
are observations. This proposal is a bounded connected manual component, not a
full N0-N4, six-port/eight-class operational implementation.
