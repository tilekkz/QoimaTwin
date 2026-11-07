# 0023. One authoritative derived tote wait classification

Status: accepted for backend implementation; proposed wire contracts remain proposals.
Sources: specification01 sections6/10, PDF resource utilization requirement, ADR0011/0016.

## Problem and scope

The runtime journal records picker travel, service and induction blocking, but does not record
resource-wait actions. The proposed wire projection previously marked every idle picker as
waiting whenever any order queued and no tote was free. Core metrics/comparison consequently
reported zero wait while exported actions could report many workers waiting for one order.

`simulation.resource_waits.derive_resource_waits(engine, cutoff)` is now the shared read-only
source for core utilization, labor comparison and proposed wire actions. The initially supported
reason is exactly `tote_unavailable`. We do not infer receiver, shipper or other resource waits.
Scheduling, movements, inventory reservations and the raw event/action journal are unchanged.

## Classification

The derivation sweeps integer ticks at order/tote/reservation events and picker action boundaries.
Events at a tick are applied together through settled dispatch before classifying the next
half-open interval. `order_assigned` consumes one free tote; `order_packed` returns it.
Order arrival adds FIFO work; assignment and inventory rejection remove it. FIFO insertion
order follows the recorded arrival order, which is the dispatch order for equal arrival ticks.

An actor with a non-IDLE raw action is unavailable. Completed BLOCKED intervals and still-open
induction blocks are unavailable too. Planned actions crossing the observation cutoff remain
busy there; they do not create fictitious idle gaps. When no tote is free, choose at most
`min(admissible queued orders, idle pickers)` waiting actors, in sorted actor-ID order, matching
picker dispatch. Other idle actors remain IDLE. Waiting does not reserve a worker or stock and
can transfer to a lower-ID actor when that actor becomes idle.

Admissibility is a counterfactual FIFO pass using current free active pick-face stock. Start from
initial active lots and subtract recorded `stock_reserved` quantities. Picking reduces on-hand
and reservation together, so it does not change free availability again. Current receiving
places reserve stock and does not replenish active pick faces. The counterfactual pass debits
a private stock copy for each admissible queued order; unavailable orders are excluded, just as
dispatch rejects an unavailable head before considering the next. This prevents counting several
workers waiting for orders that cannot all reserve the remaining stock. It never mutates the
real ledger or predicts later demand. Future active replenishment/reservation-release semantics
must explicitly extend this derivation before those engine operations are introduced.

## Boundaries and measurement

`ResourceWait` contains actor_id, integer start_tick/end_tick, reason and open_ended. Adjacent
intervals for the same actor merge. At cutoff, process all events with tick<=cutoff and classify
the resulting state. A wait still present there is open_ended; a tote release/assignment that
ends it exactly there closes it. A new wait starting exactly at cutoff has a zero-width
descriptor. Such descriptors contribute zero measured time and are exported only as proposed
boundary_actions, never as a positive-duration action or a new journal event.

All duration measurements remain `[0,cutoff)` for both horizon and end. Strict-H order counts
and inclusive-end counts are separate and unchanged. WAIT_RESOURCE is reported independently
and excluded from active labor, which remains TRAVEL+BUSY_SERVICE. Role utilization adds the
IDLE residual so active+blocked+wait_resource+idle=1 for positive windows; zero-window fractions
remain undefined. No additional shared-contract files are modified.

## Independent checks

For one tote and two analytical fixture orders arriving at0: P01 finishes handoff at32.8,
is blocked until induction33, and packing[52,76.1) releases the tote. P02 therefore waits[0,33),
then the lower-ID idle P01 waits[33,76.1). Total wait is60seconds atH60 and76.1seconds at end,
regardless of the12-picker roster; P01 active labor atH60 remains32.8seconds. Cutoff0/33 tests
cover zero-width descriptors; cutoff76.1 closes the wait exactly. A partial run ending32.9
keeps P01 BLOCKED and P02 waiting. Two units of each SKU with three such orders leave only one
admissible queued order after the first reservation, so P03 must not be classified as waiting.
Core/comparison totals and unchanged raw journal hashes are checked separately.
