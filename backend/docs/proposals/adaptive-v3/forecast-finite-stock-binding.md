# Forecast offers bound to finite original stock

The ADR0089 proposal supplies finite planning inputs for a future decision
adapter. It authenticates an ADR0088 `OfferProjectionInputs` and creates a new
`ForecastBoundStock`; C11 stock-binding APIs keep their own namespace.

```python
from app.v3.forecast_stock_binding import bind_forecast_stock, verify_forecast_stock

# projection is an authenticated ADR0088 forecast projection with inbound budget 0.
stock = bind_forecast_stock(projection)
fresh = verify_forecast_stock(stock)
```

Consumers receive the original source stock and initial placements, every
predicted offer's allocation or explicit shortage, and an empty receipt tuple.
An HU can occur in at most one successful allocation. The complete original
stock remains unchanged. Forecast and projection IDs are separate fields in the
canonical record, whose bytes also embed the complete authenticated projection.

This does not authorize actual work, stock credit, cargo handling, port service,
replenishment or execution. B2B and physically unsupported cargo remain visible
planning demand. A consumer must preserve shortages and separately establish
decision, resource, physical and runtime authority. There is no positive-benefit
claim. See [ADR0089](../../adr/0089-v3-forecast-finite-stock-binding.md) for source,
identity, finite allocation and compatibility rules.
