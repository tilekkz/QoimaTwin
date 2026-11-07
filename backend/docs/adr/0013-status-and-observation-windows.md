# 0013. Completion reasons, subsystem status and coherent observation windows

Status: accepted for backend; 2026-11-07 PDF P0 items 1 and 3.

Overall status remains partial when receiving is irreversibly blocked, even if all orders have
been dispatched. The result reports the independent orders and receiving flows: arrived,
completed, rejected and pending totals, plus the start of receiving blockage. A complete orders
flow does not imply that the receiving flow completed. The primary reason follows ADR0009 A05:
error, deadlock, max_drain, unfulfilled_inventory, drained. Every applicable reason is retained.

In P0, reserve staging never empties. An unclaimed receipt with no reservable staging position
is a known receiving deadlock even if other scheduled work still exists at the drain deadline.
Orders or arrived receipts left unresolved with no future scheduled work are also a deadlock.
Arrival accounting is necessary for COMPLETE: dispatched + rejected must equal arrived; any rejection still makes
the overall result partial. Backlog continues to include rejected orders (GLOSSARY and 05):
dispatched + backlog = arrived. The disjoint equation is dispatched + pending + rejected = arrived.

Exceptions are not swallowed. Engine.run stores a failed last_outcome with the error type/message
and ordered reasons, then re-raises the original exception. Invariant failures retain fail-fast
behavior; callers can emit structured errors without claiming a successful run or using a traceback
as the public protocol.

Horizon counts and cycles use events strictly before H; end counts include events at end_tick.
Legacy v2 scalar throughput/cycle fields now all use the horizon window, alongside horizon backlog,
utilization and queues. Full at_horizon/at_end summaries remain available independently. This fixes
the misleading combination of end throughput and horizon backlog without changing the shared v2
schema. The main contract 2.1 proposal carries both windows explicitly.

The historical receiving_queue_capacity name means physical admission-area capacity, not the
waiting-only queue KPI. The eight positions include waiting, in-service, processed and claimed
pallets until forklift pickup. Section 01.7 explicitly includes receiving service in the staging
ledger; the bounded area in 01.6 has no agreed additional service positions. GLOSSARY excludes
service from a queue, so report receiving waiting separately from physical area occupancy. Do not
silently create eight waiting plus two service positions. Track staging-full, putaway-blocked and
external-admission-blocked times independently; none is hard-coded from a nominal receipt rate.

Checks use the analytical fixture and small explicit receipt streams. A one-place staging example
fills its reservation at 180, first blocks putaway at 360, and blocks external admission at 450 seconds.
These times follow arrivals 90/270/450, receive 90 and pickup 3+15 seconds; they are hand oracles.

## Complete KPI observation

The settled observer processes new domain events once: admitted means order_assigned, and picked
means all requested units have completed sku_picked. admitted_wip excludes dispatched orders;
pending_total excludes rejected orders. Their counts follow the same strict-H/inclusive-end rule.
Physical inventory for the horizon is captured once from the settled state immediately before H;
the end inventory is read once when projecting metrics. No per-tick ledger history is retained.
This KPI convention differs deliberately from replay snapshots, whose state includes tick H.

Resource integrals use piecewise-constant state after settled timestamps, clipped to [0,cutoff).
An initial sample covers time before the first event. Consecutive equal resource states coalesce.
Conveyor occupancy reports mean/max occupied cells and occupancy ratio. A capacity jam means that
an occupied cargo could not advance in a hypothetical legal one-hop tick under the settled buffer,
occupancy and merge state. The pure planner runs read-only; its proposed cursor changes are never
committed. Jam duration is time with at least one such cargo; blocked_cargo_seconds sums their
exposure. Ordinary waiting until the next integer tick is not labelled a capacity jam.

Tote availability is free-pool mean/min, mean allocated, availability ratio and time with no free
tote. Per-post load includes started/packed totals, active service, blocked output, waiting mean,
and reserved-WIP mean/max. Receiving reports physical area mean/max separately from waiting-only
queues and accepted/processed/putaway event counts. The existing staging_full_since_tick field
tracks exhausted reservations; staging_physical_full_since_tick tracks actual stored pallets.
The summary spells out both names. In the one-place example these are 180 and 224 seconds.

Picker distance integrates executed waypoint segments, clipping an edge at the cutoff. It does
not use the old distance_m accumulator, which is increased when a whole route is planned. Labor
per role includes travel, service, their active sum, blocked and WAIT_RESOURCE separately; every
roster actor remains in utilization denominators. Per-window total_active_labor_s and blocking
induction/output totals allow comparison without merging idle or blocked time into active labor.
