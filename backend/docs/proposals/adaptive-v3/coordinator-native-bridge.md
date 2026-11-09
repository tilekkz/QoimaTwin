# Proposed native coordinator bridge

Status: interface proposal for review. This document does not record Tilek's
agreement, enable a frontend reader, or certify an integrated demonstration.
The existing frontend and shared contracts are unchanged by this proposal.
Current backend execution evidence and remaining product scope belong in
[V3 delivery status](../../v3-delivery-status.md).

The frontend findings below are a **static source review dated 8 November 2026**
of commit `a54beadcae4c0d5561a943c24b80e7968099996f`, compared with
`476aacb90f06e2c0785ba86288f7b7644b2a4b0f`. They are not a claim about later
frontend work. The backend interface review covers the coordinator candidate
built over `0362cd4a667c3ed144e8c6413981cde930f84f5d`; it does not substitute
source inspection for the final verification results recorded in delivery status.

## Existing frontend boundary

At the reviewed frontend commit,
`frontend/src/adaptive-v3/warehouseAdapter.ts:43–47` rejects
`actual_engine_run` or `engine_operation:true` with `ACTUAL_V3_UNSUPPORTED`.
It accepts one registered visual input:

- ID: `v3:fixture:warehouse-base:001`.
- Raw SHA256: `52aac1c73e9352b9e08ef3c370061932de3abd98c9e2a56beb121ebb70267a91`.
- Empty actions and completion events, `not_scheduled`, `metrics_scope:none`,
  and `actual_v3_run_supported:false`.

The W05.1 visual interval catalogue and W05.5.1 browser source package retain
`physical_join:false` and `completed_jobs:0`. W05.5 scene-clock integration is
TODO at that commit. Stationary holder acceptance concerns mesh/contact state;
it does not admit native engine output. The existing C12 source-labelled schema
also excludes actual runs. A native consumer needs a separate explicit reader
registration rather than a changed source label.

## Source continuity and backend interface

The backend source authority remains revision
`22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`, layout version
`qoima-144x72-v3-proposal`, and semantic layout hash
`407642632968cbd0e3f5ce1879177921c6fb7daa3292ecf375938012a0de2b71`.
The dated raw Git review confirmed that all 14 entries in
[source provenance](../../../data/v3-proposal/provenance.json) and all 7 entries
in [mesh provenance](../../../data/v3-mesh-proof-proposal/provenance.json)
still match the reviewed frontend tree by blob, SHA256 and size. The delta does
not require an automatic backend source repin. The source and mesh provenance
retain their own declared revision identities.

| Layer | Declared identity |
| --- | --- |
| Engine | `qoima-staff-coordinator-v3-proposal-3` |
| Publication | `qoima-coordinator-run-0.2.0` |
| Transport | `qoima-coordinator-run-bundle-0.1.0` |
| Metrics | `qoima-staff-coordinator-metrics-v2` |
| API domain | `qoima-v3-coordinator-api-1` |

The native run ID binds engine, publication, metrics and the exact frozen input
hash. The public run ID is separate and also binds the registered source bundle.
Registry equality alone does not establish equality of the physical scenario.
See [native publication](../../adr/0065-coordinator-native-publication.md) and
[source profile admission](../../adr/0064-v3-source-bound-coordinator-profile.md).

The native bundle contains `manifest.json`, immutable `inputs.json`,
metadata/metrics `catalog.json`, nonempty `events/{index:08d}.json` chunks on
60,000,000-tick boundaries, and `snapshots/{tick:016d}.json`. The manifest binds
exact sizes/hashes, event sequence ranges and captured tick roles. API evidence
also retains `profile.json`, `request.json` and `result.json`. Native state keeps
stock, claims, every worker/cart, current operations, packing, role bindings,
resource leases and distinct business/resource/staffing outcomes.

The implementation exposes the following contract. This table describes the
source interface; it is not a report that a particular server or run passed.

| Request | Contract |
| --- | --- |
| `GET /api/v3/coordinator-profiles` | One server-owned source profile and identities |
| `POST /api/v3/coordinator-runs` | Strict `{profile,layout_version,source_revision}` through the shared job worker; no arbitrary profiles, paths or overrides |
| `GET /api/v3/coordinator-runs/{run_id}` | Native status, metrics and distinct completion boundaries |
| `GET .../manifest` | `{run_id,transport,files,request_files}` |
| `GET .../files/{artifact_id}` | Exact authorized bytes with hash ETag |
| `GET .../checkpoint?tick=T` | Exactly captured integer tick only |
| `GET .../replay?tick=T` | Any observed settled integer tick, after all events with tick ≤ T |
| `GET .../events?start_tick=A&end_tick=B` | Observed `[A,B)` events, at most 60,000,000 ticks |

The separate replay reader declares
`qoima-coordinator-settled-replay-api-0.1.0`. It reduces verified recorded events,
does not run or restore an engine, and does not interpolate worker/vehicle
geometry. Reads rehash evidence before semantic-cache reuse. Unknown public
resources are 404, invalid client bounds 422, and corrupt or missing evidence for
a known server resource 500. The reader validates the complete bundle; there is
no streaming, fast-seek or bounded-memory promise. See the
[registered API](../../v3-coordinator-api.md) and
[settled replay contract](../../v3-coordinator-replay-api.md).

## Seven mappings to agree

1. **Identity and admission.** Register a distinct native reader for the exact
   supported versions. Preserve native/public/input/source/layout identities and
   validated file inventories. Keep fixture ID/hash, native run ID and public
   run ID separate. Explicitly bind the frontend fixture's `qoima-144x72-v3`
   label to its verified geometry; spelling alone is not layout authority.

2. **Coordinates.** Retain metres, bounds `[0,0,0]..[144,8,72]`, Y-up and scale 1.
   Resolve semantic node/arc/slot/station/cell IDs through the exact layout hash;
   compact table indices are local to that hash. Native graph state has IDs/arcs,
   not a complete pose table. Preserve declared connector provenance. A moving
   worker can have `node:null` with an actual route and planned end: display that
   state without inventing a completed node or unapproved interpolation. Static
   P01/cart/vehicle holder frames do not replace runtime coordinates.

3. **Time and event boundaries.** One second is 1,000,000 integer ticks. Query
   ticks are strict decimal strings; retain exact integer/Fraction values until
   presentation conversion. Native event windows are `[A,B)`, replay applies
   tick ≤ T, and W05 visual advance cues use `(previous,new]`. Specify sequence
   ordering, tick zero, repeated/backward seek and final-boundary behavior before
   connecting them. Visual clip durations do not replace native service times.

4. **Actors and roles.** Preserve all 24 source actor IDs and driver pairs
   F01/FL01 and F02/FL02. Map `pick/pack/receive/ship/forklift` to
   `picker/packer/receiver/shipper/forklift_driver`. Distinguish baseline role,
   eligibility, effective role and paid transitions. Actor `K01` and station
   `PK01` are separate identities. The first demo has no helper intents:
   frontend P01/P02 skill 0.8 does not grant packing or alter service time.

5. **Resources.** Preserve `CART01`/`CART02`, six `PK01`–`PK06` stations, their
   ownership and lease state. The visual `C01/upper-tote` is one separately
   declared holder; do not collapse two backend carts into it or silently equate
   their load limits. Represent unsupported geometry explicitly until its scene
   mapping is agreed.

6. **Cargo and custody.** Map source HU, exact unit IDs, carrier, parcel and
   material container separately. A full 24-unit SMALL HU is not a three-unit
   pick, parcel or four-unit P03 clip. Preserve partial quantities, ancestry,
   claims and custody. Holder selection cannot create stock, grant a lease or
   complete a task. Receipt definitions become stock only at observed credit,
   even though the first demo has no receipts.

7. **State and results.** Bind display to verified observations and retain
   `partial` when appropriate. Keep business completion, resource drain,
   observation end, staffing validity and violations separate. Planned return
   is not observed return. Preserve metric scope/version; visual interval
   acceptance, profile skill and static contact do not establish operational
   throughput or completion.

## First fixture: ordinary registered SMALL profile

Use the existing `explicit-two-cart-six-station-source-proposal` in
[coordinator-profile.example.json](coordinator-profile.example.json). At the
source review its raw SHA256 is
`de57900a05e9e8bd82527c1b804f78dd480c05e0b6b1d41e9a2dfbab7d95d8d0`.
This is the ordinary public profile. Mixed N4/helper proposals and patched
analytical test registries are separate inputs.

Both orders use HU `v3:HU:initial:DEMO_001:01`; unit suffixes below follow the
prefix `v3:HU:initial:DEMO_001:01:unit:`.

| Order | Offered time | Exact unit suffixes | Assignment |
| --- | ---: | --- | --- |
| O1 | 80 s | `0001`, `0002`, `0003` | P01, CART01, PK05, S01, OUT_S_EXPRESS |
| O2 | 98 s | `0004`, `0005`, `0006` | P02, CART02, PK06, S01, OUT_S_EXPRESS |

The horizon is 900,000,000 ticks and the end limit 1,800,000,000 ticks. Receipts,
whole orders and role intents are empty. All source workers, six station bindings
and the original 530 HUs/12,256 units remain the initial authority. Declared
actor/cart speeds are 1 m/s here, distinct from the frontend's synthetic 1.2 m/s
convention. No efficiency-0.8 conversion is proposed.

The first acceptance target is identity, custody/resources and exact settled-state
display for this bounded case. Unsupported poses may remain explicit state
markers. Physical pick/pack choreography, heavy/LONG workflows, N4 benefit and
full V3 remain outside this fixture's acceptance scope.

## Fixture and API acceptance sequence

1. Agree the seven mappings, distinct reader registration and ordinary profile
   bytes. Identify missing scene representations before implementation.
2. Define expected state/custody/event-boundary cases from frozen inputs. Preserve
   the prewritten oracles; do not derive expected completion times from new output.
3. Use the real registered source profile through the source-only
   [CLI](../../v3-coordinator-cli.md)/API verification path. Record actual complete,
   partial or failed outcomes and the exact attempt. Public registration must not
   be replaced with a hand or mixed fixture.
4. Bind the fixture to its actual code revision, source versions, native bundle
   and raw profile/request/result inventory. Attach final native validation and
   CLI/HTTP byte-read evidence in delivery status. An input hash or document alone
   is not an execution certificate.
5. Exercise the future frontend reader on those unchanged artifacts: initial
   state, offered orders, observed pick/packing/shipping/paid-return boundaries,
   captured equality, adjacent event windows, repeated/backward replay and refusal
   beyond the observed end. Reject stale versions/layouts, changed bytes, unknown
   IDs and missing resources explicitly.
6. Compare browser/API views with the same verified native state, then review
   scene geometry and physical action joins separately. Record accepted versions
   and remaining unsupported fields. Explicit review establishes adoption;
   publication of a commit alone does not.

This proposal contains no demo run ID or claimed frontend pass. It documents the
interface and acceptance work; [delivery status](../../v3-delivery-status.md)
remains the scope and evidence reference for the assembled backend.
