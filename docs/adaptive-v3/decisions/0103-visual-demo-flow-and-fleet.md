# ADR 0103 — Shared visual packing flow and additional fleet

## Status

Proposed for the frontend comparison branch on 2026-11-10. This proposal
replaces the carrier schedule and A/B packing cues in ADR 0101. [ADR 0101](0101-main-comparison-conveyor-work-in-progress.md)

## Context

The comparison needs visible congestion, a staffing decision and recovery on
one clock. Earlier sparse carrier clips and independent warning timestamps
provided separate presentation cues. A common finite flow makes the cause of
the displayed A/B difference inspectable.

## Decision

- Use 18 common jobs. Six pre-roll arrivals occur at −100, −94.5, −89, −83.5,
  −78 and −72.5 seconds. Twelve new arrivals occur every 5.5 seconds from 0
  through 60.5 seconds. Both variants use the same 7.5-second
  `packer_finish` explanatory work reference, with `full_packing_recipe=false`.
- Apply the common PK03 outage over `[30, 150)` seconds. B decides at 46
  seconds to assign eligible upstream goods to PK05/PK06 using directed
  reachability. Goods already committed to PK03 retain their assignment.
- Use source conveyor geometry, 0.55 m/s speed and 0.8-second transfer dwell.
  Reserve source cells and downstream space before movement. Each transfer pad
  and the entry curve have capacity one. Each reversible spur holds one carrier
  through inbound travel, work and return. [Flow implementation](../../../frontend/src/adaptive-v3/twin/twinFlowScenario.ts)
- B reassigns original packers K01 and K02 through their native pedestrian routes.
  Current PK05/PK06 readiness is approximately 106.8467/108.8467 seconds.
  Actual availability gates service and work gestures. Helper availability ends
  at 260 seconds, followed by their return routes. The current episode lasts 360 seconds,
  covering the staff return envelope, with a comparison cut at 240 seconds.
  A retains unfinished packing-line work at 360 seconds. [Staff response](../../../frontend/src/adaptive-v3/twin/twinStaffResponse.ts), [main motion](../../../frontend/src/adaptive-v3/twin/twinWarehouseMotion.ts)
- Define a common authored two-second collection clearance at the real conveyor
  output `[55.8, 0.92, 3]`. `packed` counts the visual finishing step.
  `completed` has scope `left_packing_line_at_declared_collection_boundary`.
  The external collection handoff is unmodelled and `shipping_admission=false`.
  [Flow assumptions](../../../frontend/src/adaptive-v3/twin/twinFlowScenario.ts)
- Add five extra visual forklifts, each with a green seated operator, plus one
  green pedestrian. Both variants receive the same extras. The canonical
  source counts are 24 people and two vehicles. Presentation totals become
  30 people and seven vehicles through six extra people and five extra vehicles.
  Extras use separate demo identities, native-scale instances and disjoint
  source-route segments, with `affects_packing_jobs=false` and
  `completed_jobs=0`. Canonical asset and registry bytes are preserved.
  [Additional fleet](../../../frontend/src/adaptive-v3/twin/twinFleetTraffic.ts)

## Consequences and scope

Absolute samples drive cargo, staff activity, queue counts, signals, history
and presenter steps. Reservation waits enter queue pressure after two seconds.
Outage, staff and upstream-feed waits enter immediately. Danger starts at three
waiting goods, SOS at eight, with a five-second recovery dwell.
The displayed quantities belong to this authored episode with
`source_kind=visual_fixture`, `engine_operation=false` and
`operational_admission=false`. [Runtime presenter](../../../frontend/src/adaptive-v3/twin/twinFlowPresenter.ts)

The two-second output boundary and explanatory work duration are explicit
presentation assumptions. Operational shipping, end-to-end packing validation
and physical or economic effectiveness require their own evidence.

CPU checks cover conservation, interval capacities, source trajectories,
staff-ready gates, disabled-decision equivalence, seek isolation and resource
cleanup. Presenter checks combine a manually specified fixture with runtime
projection checks. Browser acceptance covers the normal comparison entry,
visible queues, controls and viewport clipping. [Flow checks](../../../frontend/tools/check-twin-flow-scenario-v3.mjs), [motion checks](../../../frontend/tools/check-twin-warehouse-motion-v3.mjs), [presenter checks](../../../frontend/tools/check-twin-flow-presenter-v3.mjs)
