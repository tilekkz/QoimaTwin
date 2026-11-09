# V3 explicit timed workload proposal

This pure materializer freezes whole-HU offers before any engine runs. C10's
1500 expected inbound and outbound moves describe an unclocked planning period.
The caller supplies the horizon and offered counts; no hourly rate or implicit
peak multiplier is inferred. ADR0043 defines the exact policy and rounding.

From backend, publish a frozen policy, workload and file-hash manifest:

```powershell
uv run python -m app.cli v3 materialize-workload `
  --policy docs/proposals/adaptive-v3/workload-policy.example.json `
  --out D:/QoimaTwin-runs/workload-example-new
```

The output directory must be empty. The command performs no simulation or stock
allocation. The same source and policy produce identical output bytes across
different output directories. The Python interface is also available:

```python
from pathlib import Path

from app.storage.canonical_json import canonical_bytes, parse_json
from app.v3.inputs import load_v3_bundle
from app.v3.workload_materialize import materialize_workload
from app.v3.workload_policy import parse_workload_policy
from app.v3.workload_source import load_workload_source

bundle = load_v3_bundle(Path("data/v3-proposal"))
source = load_workload_source(bundle)
policy_text = Path("docs/proposals/adaptive-v3/workload-policy.example.json").read_text(
    encoding="utf-8"
)
policy = parse_workload_policy(parse_json(policy_text))
workload = materialize_workload(source, policy)
encoded = canonical_bytes(workload.to_dict())
```

The example's 10 offers per direction over 60 seconds demonstrate the format.
They are neither a source rate nor a recommended operational load. The policy
schema is in `docs/proposals/adaptive-v3/workload-policy.schema.json`; parsing
also checks exact integer tokens, interval ordering and horizon bounds.

`WorkloadSource` retains all 200 SKU templates, eight cargo classes, six ports,
530 initial HU references, C02 recipe hashes and all 14 raw/canonical input
fingerprints. Rational measurements, expectations and rounding deltas use
reduced `[numerator, denominator]` arrays in JSON. A job's `template_id` is the
canonical SHA256 of its matching source template projection.

Inbound jobs have new deterministic offered-HU and lot IDs, outside the stock
ledger. Outbound jobs have `hu_id=None` and `lot_id=None`: actual stock allocation
and genealogy remain a separate workflow. No HU is admitted, moved, replenished,
packed or shipped by materialization. Unsupported classes remain visible.

For a normal/burst comparison, keep the source and both budgets equal and change
only `calendar` (and, if explicitly intended, the horizon). The same population
and job IDs survive; `workload_id` changes with the timing policy. Normal arrival
ordinal `i` is at `floor(i*H/N)`. Bursts allocate the same offers to explicit
weighted windows, then distribute each window's offers uniformly in its
half-open interval. Duplicate timestamps are permitted. Output order is arrival
tick, direction, then stable job ID; it is not a dispatch priority policy.

The output is immutable, deterministic and `operational_admission=false`.
JSON projection returns a fresh tree. An orchestrator must separately bind
admissible workflows, allocate stock and enforce finite resources. This proposal
does not close N0 or claim full-shift throughput, heavy handling or replay.
