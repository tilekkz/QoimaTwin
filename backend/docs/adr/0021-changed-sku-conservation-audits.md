# ADR 0021: Check changed SKUs between full conservation audits

Status: accepted.

## Context

The November 7 specification requests checking only affected SKUs on settled ticks. Conveyor-only
ticks and actor travel do not change ledger stock, yet the previous invariant hook summed every
holding, scanned every reservation and checked all SKU totals on every tick.

## Decision

`Ledger.check_conservation()` remains the authoritative full audit. Its implementation and optional
SKU-filter behavior are unchanged; it reads the actual balance and reservation dictionaries and
does not depend on the new indexes or clear pending changes.

`Ledger.check_dirty_conservation(full=False)` performs a full audit on its first call. Later calls
check only SKUs changed by successful public mutations. `full=True` explicitly requests another
full independent audit. The dirty set is cleared only after a successful stock audit. Failed
initial and later audits retain their work for a repeat attempt. A successful stock audit does
not suppress subsequent tote, cell, capacity or pallet checks, which still run on every hook call.

Balance and reservation holdings have separate SKU indexes. Credit/debit paths maintain the
balance index and mark the SKU; the shared reservation-update helper maintains reservation indexes
and marks the SKU. Thus add_initial, accept_receipt, try_reserve, pick, release_order and
transfer_location all mark affected SKUs, including reservation-only changes. Validation failures
and empty releases do not create artificial work. A per-SKU scan checks conservation, positive
balances and all reservation bounds, including claims on a holding with no current stock.

Indexes and pending-audit flags are derived diagnostic state. Existing explicit snapshot payloads
remain unchanged. Event generation, stock mutations, reservation semantics and run identity do
not change, so this optimization does not require a canonicalization or engine-version change.

## Verification and limits

An observed integer test records addition of an untouched SKU quantity: the original hook reads it,
while the changed hook skips it and the independent full audit still reads it. Tests deliberately
corrupt each changed SKU after every public mutation, verify failed audits retry, detect initial
and forced-full corruption, and verify reservation/non-positive bounds. Generated mixed mutations
compare incremental and full audits. The existing independent ledger property model also passes.
The analytical fixture compares complete exported bytes and event hashes under incremental versus
forced-full-on-every-tick checking; the timeline regression remains 32.8 through 469 and 474 seconds.

Code must mutate inventory through the ledger's public operations. An out-of-band write to private
maps after a successful audit does not mark a SKU; the explicit full audit detects that corruption.
This is a stated limit of incremental checking, not permission to bypass the ledger API. Any future
restore/import implementation must populate through public operations or rebuild all indexes and
reset the initial-audit flag. No restore/import capability is introduced here.

An isolated 200-SKU/1,000-holding measurement with one changed SKU per operation showed fewer reads
and lower wall time. It is not a whole-engine performance guarantee. Full load runs and final
integration gates remain necessary after the broader PDF changes are combined.
