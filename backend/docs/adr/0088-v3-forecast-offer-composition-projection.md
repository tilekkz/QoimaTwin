# ADR 0088: Forecast composition under an explicit outbound offer budget

Status: accepted for a planning-input prerequisite; operational execution and
forecast-driven stock/placement decisions remain separate.

## Context and permitted scope

V3 requires comparable complete exogenous inputs and paid physical decisions.
An authenticated forecast predicts whole-HU offer composition; it does not grant
storage, stock, worker capability, service speed or throughput. ADR0087 owns the
history measure, temporal evaluation, model computation and fresh source boundary.
This ADR consumes that typed result and an explicit finite planning budget.

C10 remains the source of original stock, placement, cargo templates and port
permissions. Its unclocked expected moves are not hourly volumes. C11's declared
mix shift remains a separate scenario; neither C11 validators nor its public
OutboundShiftInputs/BoundOutboundStock types are weakened or reused under false
forecast metadata. V2's 28,800-second scaling and swap policies are not adopted.

## Public contract

`app.v3.offer_projection_inputs` provides:

```python
compile_offer_projection(
    forecast: OfferForecast, choices: OfferProjectionChoices,
) -> OfferProjectionInputs
load_offer_projection(raw: bytes) -> OfferProjectionInputs
verify_offer_projection(value: OfferProjectionInputs) -> OfferProjectionInputs
```

The compiler verifies the forecast using ADR0087's fresh reconstruction, then
reopens canonical C10 and compares its entire WorkloadSource to the forecast's
source. All 200 SKU templates, 530 initial HUs, original placements, cargo rules,
baseline demand weights and raw/document source fingerprints remain unchanged.
Stock is retained as authority; no physical HU is allocated or consumed.

OfferProjectionChoices requires a complete WorkloadPolicy: horizon in microsecond
ticks, outbound whole-HU budget, inbound budget, calendar and any burst windows.
There are no volume, horizon, shift, port, service or handling defaults. This P0
scope requires `inbound_hus == 0`. Nonzero input rejects rather than silently
discarding incoming offers. The API has no receipt roster or future actual test
stream parameter. A later mixed-flow extension needs its own preserved receipt
identity and availability contract.

## Explicit port composition

The caller chooses `port_mix_mode="source_c10"` with an empty override tuple, or
`port_mix_mode="explicit"` with exact DemandWeight rows interpreted as shares.

The explicit mix covers exactly every allowed `(source SKU, outgoing source port)`
pair, including zero shares. Each SKU's shares are nonnegative Fractions and sum
to exactly one. Duplicate, missing, unknown, inbound and cargo-forbidden pairs
reject, including cargo-forbidden pairs with zero shares. No new port grant is
inferred from a forecast.

For the explicit source-C10 choice, each SKU's original outbound weights are
divided by that SKU's unchanged total to recover its source shares. Any allowed
port omitted from the C10 mix is represented with share zero. This recovers only
the mix: C10 expected intensity is not substituted for a prediction. Both choices
retain all permitted zero-share pairs for audit and exact quota coverage.

## Arithmetic and identity

Predictions are a complete immutable unique `(sku_id, Fraction)` tuple, nonnegative
and source-bound. Each projected weight is `prediction[sku] * share[sku, port]`.
Existing exact Hamilton allocation distributes the explicit outbound budget over
those weights, with lexical SKU/port ties. Expected quota, integer count and signed
rounding delta are retained for every pair.

All-zero predictions plus budget zero produce genuinely empty jobs and zero
weights/quotas while preserving all source authority. All-zero predictions with a
positive budget reject. No dummy positive weights are introduced. The original
positive C10 WorkloadSource is validated as source; no projected zero-weight
WorkloadSource is constructed or passed to its positive-demand validator.

Existing normal/burst arrival arithmetic assigns the explicitly declared horizon
to the allocated offers. The budget controls count composition only; it is not a
measured capacity or predicted throughput claim. Independent oracle: weights 1:3,
budget 4 and H=4 seconds yield quotas 1/3 and arrivals 0, 1, 2, 3 seconds. For
equal weights and budget 3, lexical A wins the half-unit remainder: expected
1.5/1.5, counts 2/1, deltas +0.5/-0.5. No conversion by 28,800 seconds occurs.

Jobs use the distinct `v3:offer-projection:job:` namespace. Their HU and lot bindings
are null. Population identity binds version, authenticated forecast ID, unchanged
source, resolved mix, projected weights and outbound budget. Calendar/horizon are
bound in the complete projection identity; changing only arrival policy does not
silently regenerate a different composition population. The caller's mode and
normalized explicit choices are preserved even when two modes yield equal offers.

The projection stores the complete canonical forecast bytes and ID, which bind
history provenance/identity, model, evaluation and predictions. CPU observations
are not copied into the projection or its hash. It stores its own canonical bytes
and SHA256. Public load recomputes forecast and source rather than trusting a new
outer hash, then reproduces projection bytes exactly. Retained verify additionally
rejects equal-value scalar and mutable-container aliases and returns a fresh object.

## Limits and tests

`operational_admission`, `actual_test_stream` and `throughput_claim` are always
false. This artifact is predicted planning offers. It is not the actual held-out
materialized evaluation workload, an N1 input artifact, a stock allocation, a
placement decision, operational N2/N3 or a forecast-quality claim. Unsupported
classes and ports are not filtered out. Small budgets may have zero B2B integer
quota while its complete source rights and weight/rounding rows remain present.

The analytical materialize_projection helper exists only for small independent
arithmetic. Its caller source/port mapping cannot enter the public source boundary.
Tests cover hand quotas and burst clocks, complete/zero predictions, explicit
rights, nonzero inbound rejection, fresh source revalidation, immutable type
aliases, rehashed jobs/quotas, forecast binding and namespace separation. The 476
foundation files, shared contracts, frontend and ADR index remain untouched.
