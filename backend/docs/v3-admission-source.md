# Static V3 source admission

`SourceAdmissionCatalog.from_bundle(load_v3_bundle(path))` adapts the immutable
V3 proposal package to the exact `storage_admission` rules. The package is pinned
to Tilek revision `22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`; this is a new V3
namespace, not a change to the shared V2 contracts.

```python
from decimal import Decimal
from pathlib import Path

from app.v3.admission_models import Handler
from app.v3.admission_source import SelectedCapability, SourceAdmissionCatalog
from app.v3.inputs import load_v3_bundle

catalog = SourceAdmissionCatalog.from_bundle(load_v3_bundle(Path("data/v3-proposal")))
placement = catalog.baseline[0]
selected = SelectedCapability(
    Handler("manual_operator", ("SMALL_CARTON",), Decimal(15), Decimal("1.25")),
    "manual_hand_carry",
    frozenset(),
)
result = catalog.evaluate(
    placement.handling_unit_id,
    placement.slot_id,
    selected,
    placements=catalog.baseline,
)
```

The caller must supply occupancy and the selected handler, transport mode and
equipment tags. Passing `None` grants no handler. `placements=()` explicitly
asks about empty storage; passing `catalog.baseline` checks the actual frozen
assignment. Only the HU being moved is excluded from occupancy. Duplicate HU
identities, unknown references and an already overfull address are invalid
state inputs, not reasons to silently correct the stock state.

The adapter reads decimal dimensions and masses from the canonical source JSON,
without float arithmetic or an epsilon. It retains full HU gross mass, including
packaging and integral support. External vehicle attachments are excluded from
stored HU mass: for example, C08's LONG cradle adds 40 kg to a 200 kg HU for a
240 kg lifting calculation, but does not add 40 kg to the stored inventory.

Storage family tags intersect the slot's allowed archetypes. A selected handler
must match both the cargo handling mode and a slot's conditional alternative,
including transport and equipment tags and manual mass limits. Ground STANDARD
forklift alternatives permit FRAGILE_CRATE only. STANDARD_CARTON does not gain
forklift permission merely because a caller declares a capable forklift.
Reserve, retrieval-blocked and inactive addresses remain inaccessible. Explicit
source upright aliases map to the generic model's `xyz`; no further orientation
is granted. Support height, service height and usable headroom stay distinct.

All source module HU capacities equal the sum of their slot capacities. The
adapter verifies this implication and validates input occupancy per slot. It
fails closed if a future source introduces a stricter aggregate module HU
limit; that requires an explicit new aggregate gate. Module payload is checked
using the sum of complete resident HU masses across all module addresses.

Positive results are **static storage compatibility**, with
`operational_admission=false` and `cost_evaluated=false`. The caller's capability
declaration is not actor availability, route proof, actual support/contact/lock
proof or a C08 moment-arm rating calculation. Those gates must be composed
before an operational job starts. No scheduling or event journal is introduced.

`tests/v3/test_admission_source.py` uses C04/C05 literal source counts and hand
arithmetic: 8 archetypes, 776 addresses, 530 placed HUs, 188 blocked addresses,
9403.85 kg; candidate counts 488/72/24/24/24/12/24/64. The candidate sets overlap
and must not be added as independent capacity. FRAGILE support .20 plus height
.95 gives top 1.15 and .10 headroom; height .95000000001 rejects. Occupied-slot,
module mass, equipment, handler-height, family and orientation gates are also
exercised. These are static checks, not measured warehouse throughput.

Sources: pinned `docs/adaptive-v3/specs/C04.md`, `C05.md`, `C08.md` and the
vendored `cargo-catalog-v3.json`, `storage-slots-v3.json`,
`baseline-assignment-v3.json` under `data/v3-proposal/docs/v3/contract-proposals`.
