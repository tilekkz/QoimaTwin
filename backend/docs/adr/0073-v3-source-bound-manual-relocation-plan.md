# ADR0073: explicit source-bound manual relocation inputs and paid plan

Status: bounded backend proposal. This decision defines admission and immutable planning inputs, not completed N1 comparison, native publication, source execution or frontend acceptance.

## Decision and immutable contract

Add a separate `qoima-manual-relocation-proposal-1` input envelope. Existing coordinator/N0/N4 classes, versions and serialized bytes remain unchanged. `bind_relocation_source(common_inputs: bytes, choices: RelocationChoices)` first reconstitutes the existing coordinator from its exact canonical frozen bytes through `load_coordinator_inputs`. Callers cannot replace the original graph, stock, actors, capacities, receipts or common clocks through relocation choices.

The new frozen/slotted values are:

- `RelocationJob`: job ID, arrival tick, original HU ID, source/destination slot IDs, existing actor ID, positive take/place ticks.
- `RelocationChoices`: explicit profile ID/provenance, zero or one job, S01/S02 permission tuple, exact route-policy identifier and positive Fraction corridor width/height.
- `RelocationPlace`: existing ReceiptPlace fields plus source module ID, module payload and HU ceiling.
- `RelocationProfile`: unchanged `CoordinatorProfile`, choices and derived place descriptors.
- `RelocationPlan`: job, exact existing FlowActor, source/target bindings, original ContainerRecipe, original unit IDs/SKU/lot/mass and five immutable HumanSteps.
- `BoundRelocation`: profile, plans, choices, exact common input bytes, canonical extension bytes and SHA256.

`load_relocation_inputs` independently reloads/rebinds the common inputs and source-derived plan, then requires exact full canonical bytes. `validate_bound_relocation` additionally compares nested runtime types and values, using the existing source-authority helper. The envelope includes the complete common input object and hash, choices, all source slot/module bindings, complete three-route plan, route policy, duration rounding, H and end cap. The unchanged original common bytes are retained in BoundRelocation; they are not rewritten into a relocated initial stock snapshot.

Source loading is offline and pinned at22296bc. All776 source slot descriptors are retained for complete live module membership; only the selected pair receives manual-transfer admission. Extra descriptors do not grant access to reserve, upper, heavy or incompatible addresses.

## Admission before the route plan

Allow at most one original intact SMALL_CARTON/STANDARD_CARTON HU. Its current initial container owner must match the declared source; its full original recipe, ordinal range, unique unit IDs, SKU, lot and exact mass must remain present. No future receipt can masquerade as original stock. No stock command, claim, worker, cart, material, vehicle or scheduler is created by this binding.

Require distinct source/destination, L1 ground-accessible support, source manual flags, no reserve/retrieval block, one HU per slot, matching typed pedestrian service anchor and existing manual-hand-carry handler option. Reuse `SourceAdmissionCatalog.evaluate` for storage-family/archetype, upright orientation mapping, exact dimensions plus two per-side clearances, slot/module mass, occupancy and handler access. Both original source and destination must pass. Floor accessibility means the accepted L1 support plane, not Y=0.

The destination must be initially vacant and absent from every declared receipt target. Module mass and count include all original stock and all promised receipts without assuming an earlier shipment. A cross-module transfer adds the original gross mass and one HU to the target; a same-module transfer counts the original HU once. Module ceiling records must agree across places. A later runtime must check actual occupancy/reservations and keep the destination unavailable through paid return.

Only explicit S01/S02 grants are accepted, and the selected existing worker must have declared ship eligibility. Actual actor home, speed, mass limit and availability tick come from the common coordinator. Exact Fraction and integer rules reject Boolean/float aliases; arrival must be before common H. Mass must not exceed `min(15kg, actor.max_gross_kg)`. Static capability does not prove the worker is currently free or in the effective role ship.

Work IDs may not collide with unit orders, whole jobs, receipt IDs or role intents. The first slice explicitly rejects any relocation HU also referenced by a unit-picking order. Unit source anchors are fixed in the current coordinator; a later opt-in derived-placement adapter is required to lift this restriction. Whole-HU overlap is allowed for the cooperating relocation runtime's shared claims and completed-placement adapter: whole-first can block relocation, and relocation-first can make a later whole job use its completed destination. This plan alone does not implement that adapter.

## Routes and operation clocks

Reuse only the explicitly named `c09-manual-small-standard-source-mode-projection-v1` already bound by the common source compiler. It adds SMALL/STANDARD permission only where both cargo metadata fields are absent; explicit false, empty or nonmatching permissions stay denied. This is a backend policy decision, not an additional source fact.

Compute three directed paths: actor home→source worker anchor, source→destination loaded, destination→actor home empty. No inferred reverse arcs, Euclidean fallback or free return. All paths require pedestrian mode and explicit corridor clearances. Loaded requirements also include cargo width+2×common path margin and cargo height+margin. Reuse the immutable DirectedGraph and `operation_ticks`; round each complete travel operation once with `ceil_each_positive_operation`. Take/place must be positive integer ticks. Zero-distance travel remains an explicit zero-duration route.

Plan step names are `relocation_approach`, `relocation_take`, `relocation_carry`, `relocation_place`, `relocation_return`. The original HU ID is carried in take/carry/place steps. The plan is not an observed event stream or a resource lease.

## Explicit source example and independent expectations

`relocation-n1-single.example.json` selects existing `v3:HU:initial:DEMO_113:01`, STANDARD24units/6.35kg, from `v3:slot:STANDARD_W:004:L1:B1` to free `v3:slot:FLEX_W:003:L1:B1`. Both preserve upright XYZ and the same module yaw. Source usable1.25×1.05×1.10m and destination1.40×0.60×1.00m contain the0.60×0.40×0.30m carton plus0.05m on each side. Source module begins2HUs/12.70kg; target begins0 and ends1HU/6.35kg, with8.65kg payload headroom and no free HU position.

Bind that example to the inspected common `coordinator-profile.example.json`: S01 homeOUT_S_EXPRESS, speed1m/s, max10kg, available_tick0. Proposed take/place1s each match that profile's whole handling choices. Corridor0.70m/1.80m is the already documented conservative ADR0032 bound. These are explicit profile choices, not measured source norms. Do not substitute historical ADR0032's different1.3m/s/15kg/2s configuration. No new cross-training or role transition is silently added.

The pure-data source survey independently derived10/14/6 directed arcs and approximate85.74/93.08/15.34m. Exact decimal tails produce travel ticks85,740,000 +93,080,000 +15,340,001 at1m/s. Conditional no-wait milestones: take86,740,000; place180,820,000; paid return196,160,001. Original530HUs/12,256units/9403.85kg remain unchanged at input. Source assignment planning proxy84.9m is not the worker-anchor approach85.74m.

Independent analytical acceptance uses a directed2/3/5m triangle, speed1m/s, take2s/place1s: milestones4/8/13s. Tests cover no-op, exact typed inputs, permission/ID rejection, absent loaded permission, source/destination admission, actor and module ceilings, promised receipt capacity and same-module counting. These checks do not run an engine.

## Publication and remaining integration

Current C65 intentionally rejects the extended inputs/outcomes. Do not strip the relocation extension or coerce it into current N0/N4 bytes. A separate native codec, semantic reader, resource/claim journal and metrics/version boundary must retain completed take/place and paid return, source-derived placement and every capture. A separate N1 pair policy must preserve common offered inputs and count relocation labor exactly once; no positive effect is required.

The cooperating runtime may subclass CoordinatorEngine and use the common clock/ledger, but actual source execution, public/API delivery and N1 completion are not established by this ADR or the preflight tests. No frontend/shared contracts or pinned source files are changed.
