# Immutable V3 vehicle prerequisite supplement

These three files are byte-exact source proposals from
`tilekkz/QoimaTwin@22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`:

- `layout-conflicts-v3.json`: shared vehicle/pedestrian traffic resource references.
- `vehicle-graph-v3.json`: original L07 geometry and reservation groups.
- `vehicle-handling-v3.json`: C08 v0.2 load/rating/action-evidence restrictions.

`provenance.json` records raw SHA-256, Git blob SHA-1, size and pinned source URL
for each file. Its own SHA-256 is fixed in `app.v3.vehicle_package`. The source
revision and bytes are independent of later frontend visual fixtures.

The existing `../v3-proposal` package supplies layout links, storage slots and
fixed port resource policy. Its fourteen-file provenance pin is unchanged.
Do not merge these files into that package or silently rewrite either manifest.

Offline use from the backend repository:

```python
from pathlib import Path
from app.v3.vehicle_package import load_repository_vehicle_adapter

adapter = load_repository_vehicle_adapter(
    Path("data/v3-proposal"), Path("data/v3-vehicle-proposal")
)
```

The adapter verifies both manifests and all six referenced raw source files.
It preserves candidate geometry and declared evidence prerequisites only.
Actual model actions, mesh/contact/swept-motion verification, scheduling and
operational forklift admission remain unimplemented. ADR0036 defines the boundary.
