# ADR 0070: Source PALLET receipt obligations and a preconditioned putaway primitive

Status: Proposed; implementation/tests authored, execution deferred by user instruction.

## Evidence and scope

The pinned22296 C02/L03/C08/L07/L09 proposal contains enough information to preserve a future
PALLET receipt's identity and design permissions, choose a directed conditional route, and
identify the missing physical handoffs. It does not yet supply an actual source port/staging
pickup action. ADR0042/0046 prove a separate local pickup-return fixture; ADR0066 connects that
fixture's explicitly existing PALLET to the common ledger. None creates source receipt stock.

IN_W_BULK and IN_N_STANDARD allow PALLET_LOAD with one of R01/R02 and the same F01/FL01 pair.
Each has one bay; staging count ceilings are2 and4 respectively. Both declare30 seconds per HU
for intake/unload/check/release to reserved staging. Their windows are[0,28800) intersected withH.
These source assumptions exclude resource travel, queues and putaway. They are not speeds,
arrival rates, proof of staging fit or permission to credit inventory at a semantic service node.

The original530-HU/12256-unit stock remains unchanged. Template DEMO_172:01 is an existing
PALLET at HEAVY_E011. Its C02 recipe may describe a new receipt with a new HU and lot, but the
template itself is never moved. HEAVY_E001 is initially empty; its exact support height.18m,
usable1.4x1.5x1.2m, per-side clearance.05m and1000kg design limit admit the unchanged
1.2x1.35x1.0m,24-unit455kg recipe as a design prerequisite. It remains a separate geometry and
runtime obligation to place that new HU there.

## Source requirements composition

`compile_pallet_receipt_requirements(base_root, vehicle_root, request)` reloads and verifies
the original raw base and vehicle packages. Requests explicitly state new receipt/HU/lot IDs,
template HU, port, target slot, selected existing receiver, arrival,H,end. There are no generated
rates or hidden actors. The first target is the proved HEAVY_E001 platform; occupied targets,
unknown classes/ports, Boolean clocks and existing HU/lot reuse fail with typed reason codes.

The returned `ReceiptDefinition` is future metadata. It is not in a ledger, creates no tokens,
and does not add an initial531st HU. `requirements_hash` identifies this bounded preparation;
it is neither a run ID nor an admission grant. Revalidation recompiles from fresh pinned bytes
and compares exact nested runtime types and canonical values, never a caller-reported hash.

The route candidate intersects each directed arc's C08 cargo set, equipment-pair permissions,
and main/local loaded profiles. It minimizes source root-path metres, with deterministic arc-ID
tie ordering, from the semantic service pose to the target prehandle. It preserves analytic yaw,
motion direction, steering, clearance references and original/mixed traffic resources. Each
resource's source capacity remains explicit; no whole-route reservation or separate actor pool
is created. Changes of steering/curvature or motion direction become explicit stop obligations.
Missing `stop_allowed` stays unknown. Source metres never become elapsed job time implicitly.

This is explicitly a **conditional service-pose-to-prehandle candidate**. It is not the missing
staging pickup route. The compiled vehicle graph has service/prehandle poses but no named
staging-position vehicle nodes. `reject_credit` reads/checks the supplied common ledger and
existing target reservations and always refuses incomplete proof chains without mutation,
reservation, token creation or partial commit. No second runtime is introduced.

## Target putaway primitive

`compile_putaway_primitive(proof_root, proof, timing, source_bridge=...)` first independently
revalidates the complete raw-bound local geometry proof. It selects the unique already-loaded
`travel_approach` suffix of the proved action. Its precondition is an actual HU supported by FL01,
high/retracted at local[-1.05,.70,0], with the target empty and the action space reserved.
It is not an empty-vehicle pickup and never has an `attach` operation.

With explicit ADR0046 hand rates, approach1.05 + extend1 + lower1 + release.30 gives handover
after3.35s. Withdraw1.05 + raise1 + retract1 gives safe return at6.40s. This arithmetic predates
any invocation. The suffix retains the exact source sequence and positive per-operation ceiling
to microseconds; visual timestamp values never assign durations.

The optional prehandle connector is separately directed and0.05m long. The existing ADR0046
connector proof is EMPTY and cannot certify loaded entry. This implementation therefore calls
the actual rigid-mesh continuous segment verifier with `attached=True` for that entry, retaining
source pair/cargo/traffic bindings. Empty exit uses the existing separate proof. At the explicit
1m/s root rate, conditional offsets become3.40s handover and6.50s safe return. The returned
nonzero coverage count is populated only after successful computation, not from a supplied
Boolean or the old empty-entry count. The code and test are authored; no new sweep has yet run
in this authoring phase. Retained primitives can be recomputed and exactly compared.

The primitive does not execute a scheduler or mutate stock. A later common runtime may consume
its paid steps only after the actual loaded precondition and full source handoff chain are
proved. Source receipt credit, warehouse admission and complete source PALLET execution remain
false. The existing0066 and old whole/light publications are unchanged.

## Precise remaining evidence and policy

1. Each actual staging position needs a support ID/mesh binding, world position/yaw/contact
   height, actual HU pose, two usable fork channels, local action-space bounds, and continuous
   pickup/contact proof. Count ceilings and clear-floor rectangles do not supply these facts.
   C08 forbids assuming that forks pass through a solid floor/deck.
2. A staging position needs an actual vehicle pose and directed connector to the loaded graph,
   pair/cargo permission, loaded/empty clearance and shared traffic bindings. A port service
   node cannot substitute for this missing endpoint.
3. Travel needs actual model containment/retention authority for the accepted analytic turns
   and reverse legs. The source design certificate and local fixed-yaw fixture are distinct.
4. The future shared process must declare initial driver/vehicle pose and paid approach;
   forward/reverse speeds; stop/steering times; receiver participation/release; and how source
   30s intake excludes or includes mechanical subactions, avoiding double counting. Resource
   acquisition and credit must occur on the same real clock and StockLedger as existing work.

These are finite proof obligations, not a permanent external blocker. A new backend proof can
use raw-pinned meshes and sufficient source geometry plus explicitly proposed initial placement
and timing choices. If a necessary support or connector does not exist in the source, its fields
must be proposed openly; backend code must not silently add a support, carrier or warehouse HU.

## Deferred acceptance

Authored cases cover source530/12256 unchanged, future24/455 recipe, both ports'1 bay and2/4
staging ceilings, no-credit rollback, occupied/source-ID/class/port rejection, exact30s horizon
boundary, fresh raw pins and retained Boolean aliases, tiny directed route arithmetic, and the
loaded suffix/connector obligations. All execution/static checks are deferred. No new source
DES, HTTP lifecycle, throughput, operational PASS or computed loaded-sweep result is claimed.
