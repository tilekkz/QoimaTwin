# Architecture decision records

Each record freezes one backend decision. Records 0001-0009 were accepted on 2026-11-07 at H0.
They come from the spec review in `../research/` (Claude, Codex main, Codex edu).
Record 0007 changes the shared contract and needs Tilek's agreement before files in `contracts/` change.

| ADR | Decision |
|---|---|
| [0001](0001-simpy-as-clock-only.md) | SimPy is the time scheduler only; business state lives in dataclasses |
| [0002](0002-exact-integer-time.md) | Exact integer ticks, 3,000,000 per second |
| [0003](0003-phase-ordering.md) | Five phases inside one timestamp |
| [0004](0004-atomic-conveyor-tick.md) | Atomic conveyor tick with round-robin merges |
| [0005](0005-single-ledger-transaction.md) | One transactional inventory ledger |
| [0006](0006-pallet-state-machine.md) | Pallet state machine and timer generations |
| [0007](0007-contract-v2-1.md) | Contract v2.1 proposal for the run export |
| [0008](0008-run-identity-hashing.md) | Run identity from canonical JSON hashes |
| [0009](0009-spec-ambiguity-resolutions.md) | Resolutions of spec ambiguities |
| [0010](0010-replay-snapshots-and-chunks.md) | Settled replay snapshots and half-open event chunks |
| [0011](0011-metrics-boundaries.md) | Horizon/end observation windows and undefined statistics |
| [0012](0012-run-export-projection.md) | Schema-valid v2 projection and proposed run bundle |
| [0013](0013-status-and-observation-windows.md) | Ordered termination reasons, subsystem status and coherent metric windows |
| [0014](0014-runtime-publication-and-clock.md) | Live scheduler heap, exact short horizons and safe publication |
| [0015](0015-forecast-temporal-protocol.md) | Temporal validation, immutable mean28/HGB forecasts and cached history |
| [0016](0016-planning-and-comparison-protocol.md) | Frozen ABC, greedy swaps, paired comparison and semantic input identity |
| [0017](0017-proposed-replay-contract.md) | Proposed atomic cargo transitions, complete business replay and bounded transport |
| [0018](0018-local-api-and-immutable-artifacts.md) | Local experiment API, bounded workers and immutable artifact publication |
| [0019](0019-canonical-json-and-benchmark-processes.md) | Canonical byte parity and isolated benchmark processes |
| [0020](0020-optional-mercury-explanations.md) | Optional Mercury explanations from immutable comparison facts |
| [0021](0021-changed-sku-conservation-audits.md) | Full initial audit and conservation checks for changed SKUs |
| [0022](0022-persistent-history-artifact-cache.md) | Verified immutable history reuse across CLI processes |
| [0023](0023-derived-tote-resource-waits.md) | Shared resource waits derived from admissible orders and tote availability |
| [0024](0024-provenance-publication-identity.md) | Provenance participates in immutable publication identity |
| [0025](0025-tilek-visual-compatibility.md) | Explicit visual Run 2.0 projection for the existing Tilek loader |
| [0026](0026-v3-runtime-time-and-directed-graphs.md) | V3 microsecond operation policy and directed filtered routes |
| [0027](0027-v3-catalog-interface.md) | Separate V3 static catalog, source identity and interface capabilities |
| [0028](0028-v3-frozen-proposal-inputs.md) | Pinned V3 source package, exact compatibility and baseline conservation |
| [0029](0029-v3-independent-analytical-fixtures.md) | Independent F1/F2/F3 hand-oracle fixtures |
| [0030](0030-v3-static-admission-before-cost.md) | Exact static storage and route compatibility before scoring |
| [0031](0031-v3-whole-hu-manual-execution.md) | Explicit manual HU jobs, paid return routes and finite stage leases |
| [0032](0032-v3-manual-execution-profile.md) | Source-bound synthetic manual profile and charged staging connectors |
| [0033](0033-v3-manual-wire-replay.md) | Validated manual-run export, actual motions and settled replay chunks |
| [0034](0034-v3-manual-observation-metrics.md) | Settled business counts, cycle and time-weighted resource observations |
| [0035](0035-v3-manual-api-publication.md) | Registered manual profiles, shared spawn admission and immutable API runs |
| [0036](0036-v3-vehicle-evidence-prerequisites.md) | Pinned vehicle geometry, traffic and handling evidence prerequisites |
| [0037](0037-v3-conveyor-source-primitives.md) | Exact source conveyor topology, physical admission and timing primitives |
| [0038](0038-v3-profile-receipt-chain.md) | One received HU reused by outbound jobs and compiler admission parity |
| [0039](0039-v3-manual-admission-and-wait-reasons.md) | Static explicit-job admission, valid slot reuse and causal waits |
| [0040](0040-bounded-v3-conveyor-execution.md) | Finite conveyor execution with swept-cell and reversible-spur reservations |
| [0041](0041-v3-unit-and-packaging-ledger.md) | Exact unit ancestry, transactional stock and explicit packaging material |
| [0042](0042-v3-local-pallet-mesh-proof.md) | Actual GLB geometry, continuous local motion covers and finite support |
| [0043](0043-v3-explicit-timed-workload.md) | Exact source quotas and explicit frozen arrival calendars |
| [0044](0044-v3-conveyor-component-publication.md) | Frozen component profiles, actual traces and immutable CLI publication |
| [0045](0045-connected-light-flow.md) | One clock for SMALL picking, cart/belt handoffs, packaging and shipment |
| [0046](0046-v3-timed-local-pallet-cycle.md) | Paid local PALLET cycle with verified directed bridges and exclusive leases |
| [0047](0047-v3-connected-flow-observation-metrics.md) | Connected-flow business cycles, paid labor and time-weighted populations |
| [0048](0048-v3-explicit-connected-small-profile.md) | Strict explicit SMALL profiles, verified source authority and frozen inputs |
| [0049](0049-connected-flow-publication.md) | Frozen connected-flow inputs, actual checkpoint publication and validated artifact reads |
| [0050](0050-v3-single-inventory-authority.md) | Append-only receipt stock, shared unit/HU claims and transactional custody |
| [0051](0051-connected-light-api.md) | Registered connected SMALL runs, shared API worker and verified captured-state reads |
| [0052](0052-source-bound-receipt-profile.md) | Explicit receipt compiler, source-bound putaway and conservative manual permissions |
| [0053](0053-v3-shared-receipt-flow.md) | Inbound service, staging, putaway and paid return on the connected clock |
| [0054](0054-c11-planning-import.md) | Source-bound C11 planning proxy with explicit non-operational limits |
| [0055](0055-connected-receipt-publication.md) | Creation and claim journal, exact receipt inputs and immutable captured export |
| [0056](0056-v3-shared-manual-whole-flow.md) | Intact SMALL/STANDARD work on the shared inventory clock |
| [0058](0058-connected-whole-publication.md) | Native whole-HU publication and strict captured-state reads |
| [0060](0060-registered-receipt-api.md) | Registered receipt HTTP runs with one owned API worker |
| [0061](0061-public-whole-profile-cli.md) | Explicit whole-HU profiles and bound CLI request receipts |
