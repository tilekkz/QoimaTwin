# 0017. Explicit 2.1 replay proposal, finite places and compact transport

Status: proposed, not approved by Tilek. Date: 2026-11-07.

The owner confirmed that there is no agreed 2.1 contract or scene-decision file. This backend
proposal therefore lives under backend code/documentation and never replaces shared contracts/
or changes frontend/. Legacy 2.0 remains the default. The proposal uses schema_version 2.1 plus
contract_status proposal, and adds wire_version 2.1-proposal to the run identity. Thus publishing
two formats cannot overwrite one run namespace. The input identity contains all nine hashes.

## Locations and current ownership

Scene anchors were read from origin/codex/twin-environment at commit
10496fd4ccd748676c036c371dd1a29881f046d1. That branch's BACKEND_HANDOFF explicitly does not approve
this proposal. Open pallet [64.92,0,6], dock-out pallet [71.08,0,2], receiving pallet [4,0,36.92]
and reserve pallet [4,0,14.92] are presentation anchors, not replacement forklift service nodes.
FO_PICK/FO_DROP and FI_PICK/FI_DROP remain the authoritative motion graph. Presentation offsets
do not add travel time. Induction and pack input/output anchors come from the existing layout.

Queue grids beyond the observed first anchors are explicitly marked proposed_queue_grid. Their
spacing, orientations and final queue footprints need Tilek's approval. They are not claimed to
be existing scene geometry. Physical admission area includes service/claim until pickup, while
the receiving queue KPI excludes service; ADR0013 records the eight-position capacity decision.

Finite cargo places use the lowest currently free slot index. The place remains occupied through
claim and is released only at physical pickup. cargo_placed/cargo_removed records retain exact
indices; cargo_attached/cargo_detached identify the vehicle. Snapshots retain only current
placements, including the hole left by a freed lower slot. Completed outbound deliveries are
removed instead of becoming a location history. Buffer input containers are conveyor sinks;
induction and pack-output containers are named sources. These identifiers are not cells.

## Time, actions and event replay

One cell_moved carries the authoritative cargo/from/to transition. All cell moves within a
tick/phase replay atomically: remove all sources, then occupy all destinations. This is required
even with one record per move: sequential in-place updates can overwrite a following cargo.
The event envelope owns at_tick and at_s, and seq covers domain plus derived public records.

Operations use one schema enum; carrying_cargo_id is explicit. load means forklift pickup,
unload means drop, and travel_empty/travel_loaded describe attachment state. WAIT_RESOURCE is
issued only where queued eligible work lacks a finite resource; ordinary idle and active work
are not labelled as waiting. Its reason and covering action remain available in snapshots.
The first fraction of a conveyor admission block before the next conveyor tick is labelled
awaiting_conveyor_tick. Only continued blockage after an attempted grid tick is labelled
induction_full or pack_output_full. Splitting a reason does not reset blocked_since_tick or change
the physical BLOCKED duration. The bounded assignment of resource waits is specified in ADR0023.

An operation can start exactly at the run cutoff and have zero observed duration. Positive
executed intervals stay in actions. Such a newly started operation is instead represented in
boundary_actions, with start_s equal to ended_at_s, end_s null, open_ended true, a fixed current
position and its known scheduled endpoint where one exists. This is a state descriptor, not an
invented future executed interval. The same rule covers a block begun exactly at the cutoff.
Actor state records reference either a positive action or this boundary descriptor. An action's
scheduled_end_s and destination_node_id preserve an authoritative plan when the executed action
was clipped; they never claim that the planned work completed.

picked_last occurs when the final requested unit finishes picking. stock_transferred records
preserve SKU, lot, quantity and typed source/destination inventory locations, including receipt
boundary admission and inbound vehicle movement. actor_state_changed records expose action
boundaries and reasons. receipt_arrived makes external waiting reconstructible. Nested snapshot
state and every event payload have explicit schemas and reject unknown properties or enums.

Public snapshots are after all events with tick <= T, with last_seq inclusive and a canonical
state_hash over their complete public state. They exclude scheduler callback/timer descriptors
and completed order status history, retaining cumulative counts. The public reducer uses only
the selected snapshot, subsequent events, immutable replay parameters and action geometry.
Its full resulting state is compared with independently captured engine checkpoints, including
multi-order/receiving blockage scenarios and exact 32.8/52/68.1/124/432/440-second cutoffs. It does
not restore Python callbacks or implement Engine.restore; live-engine restart remains outside
the public replay contract.

## Bounded transport and integrity

The writer validates once, publishes one chunk at a time and writes the manifest last. Inline
run.json is opt-in. Event chunks use the configured half-open windows through the shared
split_events implementation. Actions crossing a boundary can appear in adjacent chunks; a
reader deduplicates them by action_id. Catalog, event and snapshot references include exact raw
byte length and SHA-256; timebase and both configured intervals are explicit in the manifest.

Snapshot files carry a complete snapshot every ten checkpoints (300 seconds with defaults).
Between them, balances_delta contains absolute quantities keyed by SKU/lot/location-kind/ref;
zero removes a row. Other mutable state remains present. base_at_s/base_state_hash identify the
immediate predecessor, and full_base_at_s identifies the nearest full checkpoint. A reader seeks
by loading that full checkpoint and its bounded delta chain, verifies each reconstructed
state_hash, then replays subsequent events. Noncanonical balance ordering or pre-existing zero
rows force a full snapshot so compression never changes the decoded inline hash.

The 30 MB hourly raw-payload limit applies to catalog + event chunks + snapshot chunks + manifest,
without optional duplicate inline output. Performance is measured on actual generated runs;
synthetic compression tests establish only codec correctness and relative compression.

## Pending decisions with Tilek

| Decision | Backend proposal | Approval |
| --- | --- | --- |
| Format activation | explicit 2.1-proposal opt-in; 2.0 unchanged | pending |
| Queue footprints and yaw | observed first anchors plus labelled proposed grids | pending |
| Input/output container IDs | inlet:Ixx, PKxx sinks, output:PKxx sources, SHIPPING sink | pending |
| Forklift/cargo offsets | scene anchors; physical graph times unchanged | pending |
| Operation enum and carrying | load/unload, travel_empty/loaded, explicit cargo ID | pending |
| Snapshot boundary and hash | tick <= T, public last_seq, canonical complete-state hash | pending |
| Exact cutoff work | boundary_actions with null actual end, no future executed interval | pending |
| Compact checkpoint transport | full every ten plus checked balance delta chain | pending |
| Resource wait reasons | finite-resource cause, distinct from ordinary idle | pending |
