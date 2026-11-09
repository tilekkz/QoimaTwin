# ADR 0097: Fresh bulk mass projection for relocation replay capacity

Status: Accepted backend design; release verification is recorded against the exact candidate freeze.

## Observed problem

On 9 November 2026 three nonblocking py-spy 0.4.3 samples of the already running
source N1 process showed strict relocation publication validation in
`RelocationResources.check_capacity`. Two samples were in `StockLedger.contents`
and `contents_view`, which sorts and filters the complete unit-location map for
each placed container. The source process, its inputs and its outputs were not
changed or restarted. The samples establish a concrete hot path, not a duration
or speedup measurement for the proposed change.

A hand operation-count regression uses three original HUs with 72 total units.
The preimage performs three `contents_view` calls, each with all 72 locations,
for one capacity check. This is independent of wall time and invokes no engine.

## Decision

Add `StockLedger.gross_masses() -> dict[str, Fraction]`, a fresh detached physical
projection of every current container, including empty material tare. The ledger
passes its current containers, locations and tokens to `stock_state.gross_masses`.
One existing `_MassPass` groups current unit recipes by their present container;
it retains exact recipe validation and exists only until that call returns.
The projection verifies location membership/identity and exact container tare.
It does not use original HU mass, snapshots without tokens, rounding, persistent
indexes or cross-revision memoization. Returned dictionaries are not stock authority.

`RelocationResources.check_capacity` requests this projection once, then performs
the same module membership/count/mass checks. Base resource capacity checks,
relocation target promises, receipt promises and their exact comparison remain.
Completed picks, packing, receipts and transfers therefore affect the next call;
rejected commands and idempotent retries do not add mass. Nothing grants admission,
creates goods, changes clocks/events or bypasses causal native validation.

The method is a mass view, like `contents` and `balance`, not a replacement for
`check_invariants`, geometry checks or source authority. Existing ledger commands
and replay validation still perform their original full correctness checks.

## Verification and limits

Owner hand tests cover operation count, exact per-container parity with `contents`,
mixed recipes, empty tare, picks/packing/shipping, whole receipts/transfers/retries,
failed operations, fresh calls after mutations and equal-valued numeric aliases.
Capacity checks retain exact boundaries and future receipt reservations.
The external owner packet records RED/GREEN, static checks and frozen raw bytes.

No source engine, source publication, benchmark, HTTP or full suite is run for
this bounded patch. Source timing, peak memory and end-to-end compatibility remain
separate final release evidence. No quantitative acceleration is claimed here.
