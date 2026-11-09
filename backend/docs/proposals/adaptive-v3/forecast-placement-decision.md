# Forecast placement decision proposal

This planning-only boundary consumes ADR0089 `ForecastBoundStock`, never an actual
future test stream. A forecast-driven composition is not relabelled as C11 N1.

```python
from app.v3.forecast_placement_decision import (
    load_forecast_placement_decision,
    prepare_forecast_placement_decision,
    verify_forecast_placement_decision,
)

decision = prepare_forecast_placement_decision(verified_forecast_stock, explicit_choices)
loaded = load_forecast_placement_decision(decision.frozen_bytes)
fresh = verify_forecast_placement_decision(loaded)
```

The caller supplies the existing exact `PlacementChoices`: zero or one original
HU, source and free compatible L1 target, existing permitted actor, home, speed,
mass limit, transfer handling, route policy/clearances, affected predicted offer,
source port service and canonical source-compatible customer buffer. Missing facts
stay explicit reasons; there are no handling, speed or capacity defaults. The
inherited projection requires inbound budget zero; no receipt is synthesized.

The immutable result binds forecast_id, projection_id, stock_input_hash, complete
stock input bytes, choices, evaluation, all placements and its own canonical hash.
Original stock/placement and every predicted offer remain in the stock input.
Only a strictly positive full-cost net can select the one candidate; no-op wins
ties and negative results. Load/verify reconstruct forecast and source authority,
including numerical forecast verification, rather than trusting retained costs.

Reproducible bounded example: the complete declared-synthetic 56-day/200-SKU
history has daily one whole-HU offer for DEMO_113 and zero elsewhere. Use mean28,
H=1000 seconds, outbound budget 4, inbound budget 0, normal calendar, and a complete
explicit permitted per-SKU mix with DEMO_113 sent to OUT_S_EXPRESS. Keep all 200 SKU
and all original source rights. Test fixtures spell out the source cell08 connector
and S01 choices. The unique HU113 candidate costs 196160001 transfer ticks against
140799998 gross customer saving, yielding -55360003 and an unchanged placement.
This is an expected negative planning observation, not a failed execution.

`operational_admission=False`, `actual_test_stream=False`,
`full_n1_acceptance=False`. No public actual-workload parameter, arbitrary graph,
runtime claim, stock credit, API endpoint or frontend change is introduced.
