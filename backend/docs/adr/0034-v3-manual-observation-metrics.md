# ADR 0034: V3 manual business and resource observation metrics

Status: accepted for the isolated synthetic manual execution proposal.

## Decision

Report independent `at_horizon` and `at_end` observations. V3 discrete counts agree with
settled snapshots: events with `tick <= T` are included, and every job was materialized with
arrival before H. Duration integrals use `[0,T)`, so work beginning exactly at T adds no
exposure. This V3 policy is versioned explicitly; V2's existing exported metric rules remain
unchanged. A completed handoff at T appears in both physical ownership and business counts.

One complete HU job is the business unit of this slice. Report inbound/outbound arrived,
completed and backlog HUs separately, with completed units and complete-HU gross kilograms.
An inbound job completes when the HU is put away; an outbound job completes at port handover.
Calendar cycle is arrival to that business event. The worker's paid return continues after
business completion. Operational status may therefore remain partial when business backlog
is zero. Do not derive shipping backlog or cycle from the job's resource-release timestamp.

Cycle mean and p95 use completed business jobs only. The p95 is linear interpolation at
`0.95 * (n - 1)` in sorted exact integer-tick observations. No completed jobs gives null.
Fraction arithmetic precedes conversion to display seconds. There is no nearest-rank rounding.

Worker busy exposure is the actual `worker:<actor_id>` lease duration, including approach,
handling, resource waits, movement and home return, clipped to the observation. Worker IDs
come from lease resource identifiers, because acquisition can precede the event's actor field.
The whole-roster utilization denominator is all 24 declared actors times T. Role-pool
utilization uses the union of eligible actor IDs on that direction's ports, intersected with
the explicit receive/ship skill; active time is assigned by the current job direction.
A skill on an actor assigned to no such port does not add capacity to that pool.
Shared skills do not create extra workers and pool fractions
are not additive. No availability calendars or effective-role changes are claimed in this
slice. An empty pool or zero observation duration gives null utilization.

Queue job-seconds integrate each arrived job's waiting/active-with-wait-reason intervals.
Group by actual port and reason, then divide job-seconds by T for mean queued jobs. Intervals
are truncated at the observation; same-tick transitions add zero duration. Unsupported
future profiles must not be inferred from these queues.

## Independent checks

The H-P-B-S hand graph has 2/3/5 m legs, speed 1 m/s, local service 10 s and pickup/place
1 s. Outbound handover is at 31 s and worker return at 33 s. At H=32 the outbound backlog
is zero, cycle is 31 s, busy labor is 32 person-seconds and operational status is partial.
Inbound putaway is at 23 s with the same 33 s worker return. A 10 s intake after a 2 s
approach cannot fit H=11; its queue exposure is 11 job-seconds and worker exposure zero.
For cycles 10/20 s, mean is 15 s and linear p95 is 19.5 s. These values are hand arithmetic,
not observations promoted from the engine into expected test results.
