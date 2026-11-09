# V3 static interface proposal

This backend-owned proposal exposes the frozen adaptive V3 source and initial
stock. It does not execute a warehouse simulation. The shared `contracts/`
schema and frontend are unchanged. See ADR 0027 and ADR 0028 for boundaries.

```python
from pathlib import Path

from app.v3.api import create_v3_router
from app.v3.export import build_static_export, write_static_export
from app.v3.inputs import load_v3_bundle

bundle = load_v3_bundle(Path("data/v3-proposal"))
value = build_static_export(bundle)
manifest = write_static_export(bundle, Path("out/v3-static"))
# FastAPI integration: app.include_router(create_v3_router(bundle))
```

`build_catalog` and `build_initial_state` are available in `app.v3.catalog`.
`validate_static_export` validates the combined document against the published
Draft 2020-12 schema and checks cross-document references and conservation.
Use the combined builder when publishing a standalone catalog/initial state.

| GET route | Result |
| --- | --- |
| `/api/v3/catalog` | Source-labelled geometry, cargo, ports and resource identities |
| `/api/v3/initial-state` | 530 HU with typed owners, floor-centre poses and unit quantities |
| `/api/v3/documents/{canonical_sha256}` | Exact canonical source JSON bytes |

Unknown document hashes return 404; malformed hashes return 422. Each response
has an ETag equal to its raw-byte SHA-256. Initialization validates the frozen
bundle; the parent application may cache the constructed router per process.
This router has no simulation or comparison POST routes.

The export directory contains `catalog.json`, `initial-state.json`, canonical
`sources/<sha256>.json` files and a manifest published last. Each descriptor has
`path`, `bytes` and `sha256`. The manifest contains no inline source duplication.
Raw upstream SHA-256/bytes in catalog provenance are distinct from the canonical
document hashes. Source revision, layout hash and all canonical contents affect
artifact identity. Publication refuses nonempty destinations and concurrent
file replacement; a failed partial directory must not be treated as published.

The checked schema is `proposals/adaptive-v3/static-export.schema.json`. Its
`$defs/catalog`, `$defs/initial_state` and `$defs/manifest` also describe the
standalone artifacts. `static-export.example.json` is generated from the actual
pinned 530-HU source package, with no simulated actions or performance claims.

The catalog reports 200 SKU, eight cargo archetypes, 776 physical slots, 132
modules, six ports and 24 actor identities. Initial stock has 530 occupied slots,
12,256 units and 9,403.85 kg. The source warehouse bounds are 144 x 8 x 72 metres;
unit and HU dimensions remain distinct. HU world poses use floor-centre origins,
source module yaw and exact quarter-turn transformations. Scale stays one.

Actor profiles and asset bindings are explicitly undefined/unbound. Their IDs
and policy membership are references, not timed role assignments or render asset
readiness. Static flags remain false for operational admission, actual execution,
timed materialization, comparison and replay. F1-F3 analytical artifacts and a
future operational run schema are separate outputs with their own evidence.
