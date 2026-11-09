# ADR0089: Finite original stock for forecast composition offers

Status: implemented proposal; focused verification is recorded in the delivery packet.

## Context

ADR0087 forecasts explicitly declared whole-HU offers. ADR0088 projects that signal
into a caller-declared fixed outbound budget, preserving C10 cargo/port rights.
These predicted offers are neither actual future orders nor an unlimited supply
of handling units. The ADR0078 public stock binder authenticates an outbound-shift
workload with C11 authority; it cannot accept a forecast projection by relabelling
one namespace as another.

## Decision

Add immutable `ForecastBoundStock` in `app/v3/forecast_stock_models.py` and public
`bind_forecast_stock`, `load_forecast_stock`, `verify_forecast_stock` in
`app/v3/forecast_stock_binding.py`. Its namespace is
`qoima-offer-forecast-stock-0.1.0`, scope
`predicted_outbound_whole_hu_finite_original_stock`, and policy
`original_only_visible_shortage`.

Every public entry reconstructs the ADR0088 projection, including its forecast
history and numerical verification, then freshly reads the canonical pinned C10
bundle. The projection's exact typed `source` and `initial_hus` must equal that
bundle. The original source seed supplies HU, lot, unit and slot identities,
quantity and exact rational gross mass. Initial placements retain the original
HU/SKU/slot/module values, sorted by HU ID. `BaselinePlacement` is reused as an
immutable value shape; it conveys no C11 authority.

The record retains the complete projection, separate `forecast_id` and
`projection_id`, all original stock and initial placements, every allocation,
an empty `declared_receipts`, and `source_stock_hash`. Canonical bytes and their
SHA-256 form its new identity. Load rejects extra fields, noncanonical encoding,
foreign namespace and any difference from fresh reconstruction. Retained-object
verification also rejects equal-value type aliases throughout nested values.

## Finite allocation and explicit limitations

The already-verified offers keep their original order, job IDs, SKU, cargo,
quantity, port and arrival tick. Original HUs are sorted lexicographically by HU
ID within each SKU pool. Each offer removes at most one matching original HU;
that identity can bind at most once. Exhausted pools retain the entire offer with
`unallocated` / `DECLARED_STOCK_EXHAUSTED`, no HU and no dependency. Unsupported
runtime cargo or B2B work is retained; allocation does not infer handling ability.

This P0 requires ADR0088's explicit inbound budget zero. It invents no receipt,
replenishment, repeat whole-HU visit, future stock credit or replacement offer.
No arrival is rewritten and no shortage is silently truncated. An allocation is
a planning association, not a stock claim, reservation, ledger mutation,
runtime admission, material movement or completed shipment. The entire original
stock and its original slots remain in the immutable input even when an HU is
associated with a predicted offer. Operational admission, actual test stream
and full N1 acceptance remain false. There is no predicted gain guarantee.

## Shared implementation and compatibility

Only two existing modules change. `outbound_stock_allocation.allocate_offers`
still performs `verify_pools`, including strict `verify_workload`, original-HU
coverage, receipt declarations and global unit uniqueness, then invokes the
private `_allocate_verified_offers` loop. The forecast binder invokes that loop
only after its own fresh public projection and original-source checks.

`outbound_stock_source.original_stock` retains its fresh C10 source and initial
placement checks, then calls a private pure seed builder. The new binder reuses
that builder after its own C10 checks. Neither private helper establishes source
authority. No fake `TimedWorkload`, forged `BoundOutboundStock`, cast or relaxed
legacy validator is introduced. Existing public C11 bind/load/verify and wire
schema are unchanged. Before/after byte snapshots cover empty, receipt-bearing
and shortage-bearing C11 bindings.

## Verification and consequences

Hand arithmetic uses three distinct original HUs and four offers, yielding three
bindings and one visible shortage without mutation or cloning. Source tests use
a complete declared-synthetic 56×200 history and the verified mean28 v2 adapter,
preserve the 530 original HUs / 12256 units, and retain B2B and shortage rows.
Negative cases cover forged stock, slots, receipts, repeated/dropped offers,
retiming, rehashed payloads, aliases, raw-source changes and old namespaces.

Load/verify reconstructs the forecast and can refit its numerical model. This is
not a cheap reader or a performance promise. Decision evaluation and execution
remain separate boundaries; this adapter itself runs neither an engine nor DES.
