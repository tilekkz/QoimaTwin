# ADR 0047: Connected light-flow observation metrics

Status: backend bounded proposal; shared contracts remain unchanged.

The connected SMALL workflow has separate business completion and paid actor
return. Its native observations already contain exact paid and assigned-wait
tick integrals. Metrics consume those settled observations; they never replace
them with planned durations or extend an unfinished operation to its future end.

As in ADR0034, business counts include transitions at the observed tick T.
Duration integrals use [0,T). At horizon and at end remain separate, including
when all work ends before the horizon. A longer idle horizon changes resource
utilization denominators but does not add labor or change completed cycles.

An order cycle begins at its offered arrival and ends at the actual outbound
business handoff. Unshipped orders contribute backlog and no completed cycle.
Mean and linear p95 reuse the existing exact-tick interpolation before converting
to seconds. A single completed observation has identical mean and p95; empty
samples are null. Completed units count the actual declared order placements.

Paid worker seconds exclude assigned resource waiting. Both are reported.
The fixed source roster remains P01-P12, K01-K06, R01-R02, S01-S02 and F01-F02.
Per-actor utilization divides paid ticks by T; role-pool utilization divides by
T times 12, 6, 2, 2 or 2 respectively. All inactive people remain in those
denominators, with zero paid time. Whole-roster utilization uses all 24 people.
This is explicitly `fixed_source_roster`, not a role-transition or N4 metric.
Zero-length observation windows have null utilization, not fabricated zero rates.

Queue integrals retain different physical meanings:

- Unadmitted orders integrate arrival until actual admission or observed T.
- Unfinished orders integrate arrival until business handoff or T, including
  execution and the unadmitted interval above. These populations overlap;
  they are not a partition. This is work in progress, not solely resource waiting.
- Assigned-worker wait integrates native worker queue ticks and uses person-seconds.
- Stopped belt carriers use the native physical occupancy counter. It includes
  holding at output during paid collection, because cells remain occupied until
  pickup completes. It is not automatically worker-idle or congestion time.

Mean populations divide each integral by T. They are not sums of periodic queue
samples. Observation/profile identity mismatches, negative or noninteger
exposures, impossible worker paid-plus-wait totals and future business effects
are rejected. Full engine invariants and publication replay validation remain
separate authorities; metric validation does not reconstruct a run from its end.

Independent hand observations use arrivals 0 and 4s, admissions 1 and 6s, and
business completions 8 and 18s. At T10: backlog 1; unadmitted area 1+2=3 order-s;
unfinished area 8+6=14 order-s. At T20: completed cycles 8 and 14s give mean 11s
and p95 8+0.95*(14-8)=13.7s. Paid times 3/2/1 person-s at T10 give 6/(24*10)
roster utilization. These tests construct their observations from those numbers;
no runtime output supplies an expected numerical value.

Independent review also reproduced nonzero stopped-carrier exposure at T0 and
a Boolean belt clock being accepted as integer zero. Both now reject with
separate RED-before-fix regressions; an empty interval has zero exposure.
