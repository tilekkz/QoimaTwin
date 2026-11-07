# ADR 0039: Explicit manual job admission and causal wait reasons

Status: accepted for the manual backend proposal.

Directly constructed execution profiles receive the same basic physical job
checks as compiled profiles. An outbound job names its HU's single origin slot,
either initial stock or the target of its sole inbound job. Each job has at least
one eligible actor with the required receive/ship skill and sufficient gross
mass capacity. Reject an inbound target occupied initially by a different HU
that has no outbound job from that slot. These are static input errors, not
temporary resource contention.

The last check considers initial occupants only. Future receipts are not present
at tick0. A valid sequence can receive HU1, ship HU1 and later receive HU2 into
the freed slot, even when HU2 remains in stock. Treating every future origin as
an initial blocker would reject this valid sequence. Other dynamic waits and
horizon-limited partial outcomes remain runtime observations; this validation
does not claim to prove every possible schedule or eliminate all deadlocks.

When candidate worker/buffer combinations fail for different reasons, report
the closest feasible candidate's actual blocker: an otherwise valid candidate
blocked on resource leases takes priority over a candidate missing a service
window, which takes priority over a candidate with no directed route. No eligible
free candidates retains `resources`. Actor ordering must not overwrite an actual
bay/slot contention reason with an unrelated candidate's missing route.
This rule changes reason attribution, not dispatch order, routes or durations.
The observable reason correction increments `MANUAL_ENGINE_VERSION` to
`qoima-manual-engine-v3-proposal-2`. Native run IDs and API request keys therefore
separate previous results from this implementation. V2's engine version and
analytical fixture remain unchanged.

Independent checks cover invalid origin/capability/permanent initial occupancy,
a received-then-shipped HU, and the valid receive0/ship60/receive120 slot reuse
sequence. A separate hand graph with H-P2m, P-B3m and B-S5m includes an isolated
worker X and two routable workers H. The first intake occupies the shared bay
through2+10=12s; the second's actual blocker is the bay lease regardless of which
worker ID sorts first. These checks use source rules and hand arithmetic.

The source compiler remains conservatively narrower about initially occupied
receipt targets under ADR0032. Its explicit microsecond calendar ceiling is
unchanged. This ADR does not introduce a strict-grid arrival policy or automatic
replenishment/slot reassignment.
