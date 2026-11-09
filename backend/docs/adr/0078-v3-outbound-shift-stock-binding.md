# ADR0078: Source-bound whole-HU allocation for N1 outbound offers

Status: Accepted for offline compilation; operational admission remains false.

Date: 2026-11-09

## Context

ADR0077 defines one authenticated, explicitly clocked N1 OUTBOUND SHIFT workload.
It preserves C10 stock, templates and inbound demand, and projects only the
declared C11 outbound mix. Timed offers alone do not establish which existing HU
or future receipt could supply an outbound offer. Reusing an initial HU for
several offers, crediting an offered receipt at arrival, or deleting unsupported
B2B demand would produce a different physical problem.

This decision adds allocation metadata to that exact workload. It does not add a
runtime, stock transaction, route, lease, receipt completion, or shipping action.
It is a prerequisite for full N1, not full N1 acceptance.

## Decision and public boundary

`app/v3/outbound_stock_binding.py` exposes:

- `bind_outbound_stock(inputs: OutboundShiftInputs) -> BoundOutboundStock`;
- `load_outbound_stock(raw: bytes) -> BoundOutboundStock`;
- `verify_outbound_stock(value: BoundOutboundStock) -> BoundOutboundStock`.

Binding first reauthenticates ADR0077 inputs from canonical pinned local sources.
It separately reloads the original V3 bundle, checks the complete C10 workload
source and initial placements, and derives all original container/unit ancestry
through `stock_source.source_seed`. Each original HU retains its exact HU, SKU,
cargo class, lot, unit IDs, quantity, gross mass and original slot owner. The
original input and the original owner remain immutable even when later execution
would move that HU.

The result retains the entire authenticated shift input, every original HU,
every declared inbound HU, and one allocation row for every outbound offer.
Its schema is `qoima-n1-outbound-stock-0.1.0`; its fixed policy identifier is
`original_first_declared_receipt_dependency_visible_shortage`. There is no caller
stock replacement parameter. Pure helpers in `outbound_stock_allocation.py` admit
small declared hand fixtures for arithmetic tests; they establish no pinned-source
authority and cannot produce an authenticated `BoundOutboundStock` themselves.

## Deterministic finite allocation policy

Outbound offers retain their materialized order `(arrival_tick, direction,
job_id)` and their complete original fields, including port, template, class,
quantity and arrival. For each offer, use a whole HU of the same SKU:

1. Select the first unused original HU in ascending exact HU-ID order.
2. If originals are exhausted, select the first unused declared inbound HU in
   `(receipt_arrival_tick, receipt_job_id)` order, including a receipt offered
   after the outbound offer. This is a dependency declaration only.
3. If both finite pools are exhausted, retain the offer as `unallocated` with
   reason `DECLARED_STOCK_EXHAUSTED`.

An HU can supply at most one offer. Whole HUs are not split, cloned or combined.
All original HUs must be present exactly once in the source pool, including
unused stock. Every incoming declaration must exactly match an inbound offer
from the same authenticated workload. Incoming HU and job IDs are unique; an
incoming lot may legitimately be shared by multiple HUs of the same SKU.
Declared unit IDs follow the existing receipt ancestry convention
`{hu_id}:unit:{ordinal:04d}` and do not instantiate `UnitToken` or a stock ledger.

Rows have `original_bound`, `receipt_dependency` or `unallocated` status. An
original row carries the source slot and no receipt reference. A receipt row
carries the exact incoming job ID and offered arrival, has no initial stock
owner, and records the factual boolean `receipt_arrives_after_offer`. This flag
does not express availability: arrival before, at, or after the outbound offer
never proves completed receipt credit. The outbound arrival is never shifted.
No fabricated receipt or duration resolves a shortage or dependency.

Class and port do not filter this allocation. In particular, PALLET/B2B offers
remain present. A row's allocation status does not certify that its class has an
implemented handler, service, vehicle, path, or downstream runtime.

## Allocation is not a runtime claim

All rows and the complete result report `operational_admission = false`; the
complete result also reports `full_n1_acceptance = false`. Original stock is
not reserved by compilation. Future receipt declarations do not increase
on-site inventory, occupancy, capacity, or available stock. Unallocated offers
are visible, finite unmet declarations, not successful completions or omitted
demand.

A subsequent runtime boundary must retain this exact shared workload and enforce
physical single ownership, whole-HU claims, actual receipt completion before
credit/claim, and downstream process/route/service/resource availability. It must
explicitly handle pending dependencies and no-stock offers. This decision does
not invent those admission rules, clocks, resource reservations, or an ordinary
PALLET/B2B process. Baseline and candidate must consume the same allocation bytes;
allocation cannot silently absorb a relocation-specific stock rewrite.

## Integrity and failure policy

The canonical envelope includes exact shift input bytes as a JSON value, its
hash, all original stock, all incoming declarations, all allocation rows, and a
canonical original-stock hash. The result hash is SHA256 of the entire canonical
envelope. Loading rejects noncanonical or duplicate-key JSON, changed source
bytes, unsupported schema/policy, missing or extra fields, and any byte-level
disagreement with a freshly reconstructed result. Retained-object validation
additionally compares exact recursive Python types, rejecting bool/int and
float/Fraction aliases under unchanged hashes.

Malformed identities, duplicate or missing original HUs, invented or omitted
receipts, altered clocks, and identity/source mismatches raise `ValueError`.
Ordinary finite supply exhaustion is preserved as an `unallocated` row rather
than making the whole compilation disappear. This distinction keeps infeasibility
reviewable without claiming executable demand.

## Verification scope

`tests/v3/test_outbound_stock_allocation.py` uses independent small hand cases for
original-first ordering, unique consumption, future dependencies, shared receipt
lots, visible shortage, zero offers, PALLET/B2B retention, and malformed identities.
`tests/v3/test_outbound_stock_binding.py` checks authentic source compilation,
byte-identical roundtrip, retained-object aliases, altered ancestry/clock/rows,
and a changed raw assignment in a disposable source copy after a successful read.
These checks invoke no warehouse engine, source DES, HTTP, or operational run.
