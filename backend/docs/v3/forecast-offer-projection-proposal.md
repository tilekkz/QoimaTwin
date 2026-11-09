# Forecast offer projection — planning inputs only

Use the authenticated whole-HU-offer history/forecast API from ADR0087. Pass its
OfferForecast plus explicit choices to the separate projection compiler:

```python
from app.v3.offer_projection_inputs import compile_offer_projection, verify_offer_projection
from app.v3.offer_projection_models import OfferProjectionChoices
from app.v3.workload_models import WorkloadPolicy

# `forecast` is the result of fit_offer_forecast with explicitly supplied history.
choices = OfferProjectionChoices(
    policy=WorkloadPolicy(4_000_000, 0, 4, "normal"),
    port_mix_mode="source_c10",
    port_mix=(),
)
projection = compile_offer_projection(forecast, choices)
fresh = verify_offer_projection(projection)
assert fresh == projection
assert fresh is not projection
```

The horizon and budget above are a caller example, not an inferred source period
or warehouse capacity. Each resulting job is an unallocated predicted outbound
whole-HU offer. All initial stock and source placements remain unchanged.

The full forecast bytes are bound to the result. The compiler reconstructs the
forecast and original C10 source. CPU observations stay outside semantic identity.
There is no actual future workload parameter, no receipt truncation and no stock
or graph override. Nonzero inbound budget rejects in this P0 scope.

For a caller-defined mix, select `explicit` and supply exactly the full permitted
SKU/outgoing-port pair set, including zero shares, with each SKU summing to one.
The source-C10 choice recovers source shares and records allowed omitted pairs as
zero. Projected weights and all quotas/deltas remain distinct from C10 weights.

Zero forecast with zero budget produces empty jobs while retaining all 200 source
SKU templates and 530 original HUs. A positive budget cannot be distributed over
an all-zero forecast and rejects. The independent 1:3 / budget 4 / H=4 s oracle
has quotas 1/3 and four arrivals at seconds 0/1/2/3.

The artifact has its own version and `v3:offer-projection:job:` namespace. It must
not be cast to OutboundShiftInputs or BoundOutboundStock. Typed stock binding,
single-consumption allocation, physical placement decisions and paired execution
are later integrations. All operational/actual-test-stream/throughput flags remain
false. This proposal adds no runtime, API, CLI or full N1/N2/N3 claim.
