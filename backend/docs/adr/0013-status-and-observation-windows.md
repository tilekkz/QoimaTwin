# 0013. Completion reasons, subsystem status and coherent observation windows

Status: accepted for backend; 2026-11-07 PDF P0 items 1 and 3.

Overall status remains partial when receiving is irreversibly blocked, even if all orders have
been dispatched. The result reports the independent orders and receiving flows: arrived,
completed, rejected and pending totals, plus the start of receiving blockage. A complete orders
flow does not imply that the receiving flow completed. The primary reason follows ADR0009 A05:
error, deadlock, max_drain, unfulfilled_inventory, drained. Every applicable reason is retained.

In P0, reserve staging never empties. An unclaimed receipt with no reservable staging position
is a known receiving deadlock even if other scheduled work still exists at the drain deadline.
Orders left unresolved with no future scheduled work are also a deadlock. Arrival accounting
is necessary for COMPLETE: dispatched + rejected must equal arrived; any rejection still makes
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
fills its reservation at180, first blocks putaway at360, and blocks external admission at450 seconds.
These times follow arrivals90/270/450, receive90 and pickup3+15 seconds; they are hand oracles.
