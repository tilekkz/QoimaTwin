# C12 engine adapter: backend-owned proposal, not adoption

**Status: proposal only; no consumer is enabled by this document.** The mapping was
first reviewed on 2026-11-08 against Tilek `050adaf3645831298ac5daea7aad1191c92dcb2e`
and the backend's frozen 41-file publication/API candidate over `00cabfa`, which was
subsequently published as `3cd634d`. These clarifications were prepared from main
`0d72f3b` for integration with a later receipt-capable feature candidate. Commit names
above are historical provenance only, not a statement about the final integrated tree.
No shared contract, frontend, source pin, reader registration or runtime was changed.

C12 `qoima.source-labelled-input.v3-proposal/0.1.0` accepts only its named
geometry, visual and analytical profiles, and requires `engine_operation=false`.
An actual backend result therefore **must still fail `ACTUAL_V3_UNSUPPORTED`**.
The proposed solution is a separately accepted adapter profile, preserving that
existing schema and its rejection behavior. This is not an extension of Run 2.0.

## Proposed envelope and exact mapping

Reserve `qoima.engine-adapter.v3-proposal/0.1.0`, with
`adapter_profile=connected-small-captured-v1`, as a new opt-in namespace.
These names and fields are design proposals, not implemented endpoints or a
positive C12 actual-run example. Keep native artifacts unchanged behind it.

| Proposed field | Authority and rule |
| --- | --- |
| `schema_id`, `schema_version`, `contract_status` | New namespace above; `proposal`. Require an explicitly supported adapter version. |
| `source_kind`, `engine_operation` | `actual_engine_run`, `true` only after trusted native publication verification. Neither the existing C12 examples nor a caller's label supplies this authority. |
| `adapter_profile` | `connected-small-captured-v1` accepts only `qoima.connected-small-run.v3-proposal/0.1.0`. Receipt output requires a different profile. |
| `producer.name` | Proposed fixed `qoimatwin.backend`; identity is corroborated by the registered backend publication path and producer evidence, not authenticated by this string. |
| `producer.engine_version` | Native `metadata.engine_version`: currently `qoima-light-flow-v3-proposal-1`. |
| `producer.compiler_version` | Exact frozen `inputs.compiler_version`: currently `qoima-light-flow-profile-0.1.0`. |
| `producer.export_version` | Native schema/version pair, not Git branch name or warehouse version. API currently uses `qoima.connected-small-run.v3-proposal/0.1.0`. |
| `producer.code_inventory_ref`, `producer.git_commit` | Hash-bound build inventory, and commit when it actually covers that build. The observed candidate is base `00cabfa` **plus** a frozen 41-file inventory; do not describe that execution as clean `00cabfa`. Producer/build attestation is not presently a native run field. |
| `native_run_id`, `input_hash` | Copy verified native values. Current native ID is SHA256 of canonical JSON `{"engine_version": ENGINE_VERSION, "input_hash": INPUT_HASH}`. Input hash is SHA256 of the exact canonical frozen input bytes. |
| `public_api_run_id`, `input_bundle_id` | Optional API binding, kept separate from native identity. Public ID hashes canonical `{domain, native_run_id, inputs: bundle_id, engine, compiler, export}`, with domain `qoima-v3-light-api-1`. Offline CLI has no invented API ID. |
| `payload_ref`, `payload_schema_id` | Native manifest `{path, bytes, sha256}` and `qoima.connected-small-manifest.v3-proposal/0.1.0`. The manifest references exact inputs, catalog, metadata, event and checkpoint parts. **Path root:** unlike C12's repository-relative artifact paths, which must resolve inside the Tilek repository, this `path` resolves only inside the verified native artifact root identified by `native_run_id`/`input_hash`, optionally reached through the separately verified `public_api_run_id` transport. It never resolves against a repository checkout. API transport URLs are obtained from that run's inventory, not inserted into the path field. No adopted frontend loader exists for this binding. |
| `source_revision`, `source_artifacts` | Frozen source revision and verified raw input inventory; current engine source is `22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec`. C12 publication commit `050adaf` is a separate provenance dimension and does not repin the engine. |
| `layout_version`, `layout_content_hash`, `layout_ref` | `qoima-144x72-v3-proposal`; semantic hash `407642632968cbd0e3f5ce1879177921c6fb7daa3292ecf375938012a0de2b71`; exact source `docs/v3/contract-proposals/layout-manifest-v3.json`, 8009 bytes, raw SHA256 `f85a4b840e06dc4285df6dbf8f4f39ec32f9fd8d826c18157ff3c27128c620a8`. Semantic layout hash is **not** raw artifact hash. |
| `frame_of_reference`, `units` | `warehouse_world`; metres, kg, right-handed Y-up, scale 1. Explicit local placement/asset frames must remain typed. No V2 72x48 coordinate or home-position reuse. |
| `clock` | Proposed `integer_engine_ticks`, `ticks_per_second=1000000`; copy `horizon_tick`, `end_tick_limit`, `observed_until_tick`. Preserve existing integer ticks, not re-round decimal seconds. Human operations use declared ceiling policy; belt uses its separately declared cumulative geometry policy. |
| `metrics_scope` | Proposed `bounded_connected_small_observations`; copy `metrics_version`, count boundary, integral window, role basis and separate H/end observations. Do not use C12's analytical route-proxy metric type. |
| `capabilities` | Copy verified native capability flags; add explicit adapter-level unsupported features. `operational_admission=false`, `backend_integration_complete=false` remain mandatory for this bounded proposal. |

If an adapter artifact gets its own identity, domain-separate it from both run IDs:
hash canonical `{schema_id, schema_version, adapter_profile, native_run_id,
input_hash, payload_sha256, layout_content_hash, producer_evidence_sha256}`.
This formula is proposed, not a third existing run ID. Bytes/hashes prove content
identity; they do not prove that an arbitrary producer actually ran the engine.

## Identity, geometry and worker semantics

Use semantic IDs and hash-qualified references, never a reused array index.
Keep SKU, lot, packaged unit, original HU, workflow carrier and parcel distinct.
The observed run uses SKU `DEMO_001`, original HU
`v3:HU:initial:DEMO_001:01`, unit
`v3:HU:initial:DEMO_001:01:unit:0001`, carrier `C1`, parcel `P1`, order `O1`.
Unit catalog entries retain `origin_hu`, `ordinal`, SKU/lot and recipe. Current
`stock.locations` identifies the unit's container; that container's owner is its
custody. Carrying is not a second copy in stock.
C12 `bundle.schema.json` declares `inventory_facts` as JSON Schema **constants**:
actors 24, ports 6, handling units 530, SKUs 200, quantity units 12,256 and gross mass
9403.85kg. They describe the frozen source baseline, not runtime checkpoint totals.
Explicit material inventory and actual receipt credits change the registered run
totals. A receipt run registers 12,280 units and 9405.04kg, so it can never validate as
the existing C12 bundle; this is one reason it needs its own native namespace and a
separately accepted adapter profile.

| Native reference | C12 adapter interpretation / remaining work |
| --- | --- |
| `catalog.actors[].actor_id`; checkpoint `workers[].actor_id` | Preserve all 24 existing identities: P01-P12, K01-K06, R01-R02, S01-S02, F01-F02. Idle workers stay present. Native actor records provide explicit profile home/speed/mass, not C12 skill-level or cross-training facts. The native runtime speed (V3 pedestrian 1.3m/s profile choice, ADR0032) is authoritative; the C12 example `walk_speed_m_s: 1.2` never overrides it. |
| C12 P01/F01 WorkerProfile examples | Examples only: P01's packer skill 0.8 and F01's FL01 permission do not create role assignments, employees or vehicle jobs. Baseline fixed roles may be resolved from the pinned roster; current role may only equal that fixed role in this profile. Never infer dynamic roles from an operation name. N4/P11/P12 transitions are unsupported. |
| `catalog.owners`; container `owner_id` | Resolve `slot`, actor, cart, belt, bench, pool, shipped/disposed owners by their typed definitions. Distinguish material-pool inventory from geometry-only fixtures. |
| `operation.source_node/target_node/route` | Preserve directed graph ID, node IDs, arc IDs, length/cost and carrying/cart IDs. Native catalog currently contains node IDs and arcs, **not a complete node-position table**. Join verified frozen `source.documents[layout-links-v3.json]`; new synthetic nodes require explicit compiler connector provenance and positions. Unknown spatial bindings must fail or remain explicitly unavailable. |
| `worker.node=null` with active operation | In transit, not home, hidden completion or a teleport to target. Exact continuous human/cart poses, hands and attachment transforms are not supplied by current native publication. First adapter supports captured semantic observations; visual interpolation needs a separate accepted profile. |
| Belt `pose={edge_id,progress,yaw_quarters}`, `motion`, `occupied_cells` | Resolve the exact frozen conveyor source and geometry, including curves, pivots and reversible spurs. Do not render it as arbitrary linear interpolation or drop occupied/guard cells. |
| C12 PortView | Preserve all six geometry IDs and source references. `IN_E_PARCEL` service node is `v3:service:IN_E_PARCEL` at [138,0,54]; `OUT_S_EXPRESS` service node is at [48,0,6]. Wall openings [144,0,54] / [48,0,0] are different points. Allowed families alone do not grant a loaded route, equipment or service window. |

There are six packing stations, not one per allowed worker. Current connected
profile uses its explicit station/packer; it does not schedule cross-trained
workers across six posts. Frozen synthetic carrier/material recipes remain
declared choices; the narrow carrier is not a resized/approved M07 asset, and a
P04 finishing clip cannot substitute for pack handling or hand-contact proof.

## Captured state and event rules

Preserve the global contiguous `seq` starting at zero and nondecreasing `tick`.
Same-tick events keep native order; never sort by kind or merge the embedded
belt's local sequence into a second independent clock. Checkpoint `last_seq` is
the last event with `tick <= checkpoint.tick`; state is settled after that prefix.
Capture 0, each 30s through observed end, exact H and exact end, deduplicating equal
ticks. A complete run can end before H; the captured H state is a later settled
observation, not fabricated activity until H.

Mutable checkpoint state is `stock` revision/containers/locations, balances,
workers, cart, orders, finite leases and belt state. Recipes, unit ancestry,
source documents and graph belong to immutable catalog/inputs; history belongs
to event chunks. `operation.planned_end_tick` and motion endpoint are plans:
at a cap, retain open operation/current custody/leases; do not emit a future
completion. Business shipment and paid return have separate meanings. Counts
are settled-inclusive; exposure integrals use `[0,T)`. Belt stopped exposure can
include paid output pickup and must not be renamed human WAIT_RESOURCE.

The current light publication contains stock deltas and physical leases, but
does **not** publish the shared receipt inventory/claim-generation schema. It
cannot claim replay of future receipt creation or whole-HU/unit claims.
Native receipt publication is a separate backend namespace,
`qoima.connected-receipt-small-run.v3-proposal/0.1.0` with manifest schema
`qoima.connected-receipt-small-manifest.v3-proposal`, described in
[ADR0055](../../adr/0055-connected-receipt-publication.md). Registered receipt HTTP
transport is implemented in the receipt feature candidate (ADR0060), with an actual
source HTTP proof, also in its own native namespace.
Neither is C12 support: this adapter proposal still has **no accepted
receipt-capable frontend profile**, and the `connected-small-captured-v1` profile
above does not accept receipt runs. A receipt adapter profile must satisfy:

- Declared receipt descriptors and future token recipes are immutable plans,
  absent from initial registered inventory, balances and claims.
- Actual completed receipt service emits `receipt_credited` with a creation
  delta: empty before, one declared new HU, exact newly created token set,
  matching SKU/lot/recipe/quantity, positive next stock revision.
- Replay claim acquire/release/consumption in global event order. Claim
  generation is separate from stock revision; claims promise existing units,
  never create or duplicate them. Compare captured state only after the settled
  prefix, including same-tick claim release and subsequent transfer/admission.
- Whole-HU custody, unit transfer, pack and shipment keep ancestry. Empty C1 and
  P1 material already exist in the light initial inventory; packing moves and
  seals units, not minting them. Receipt does add a genuinely new wrapper/tokens.
- At every captured boundary: initial + actually credited units = onsite +
  shipped by SKU. Include all primary/wrapper/material tare and disposed empty
  packaging separately. Putaway completes receipt business; paid home return
  completes its worker use. `complete` requires no unfinished work, open
  worker/cart/belt operation, active claims or finite leases.

## Transport and explicit unsupported capabilities

Existing HTTP routes remain `/api/v3/light-profiles`, POST `/api/v3/light-runs`,
then `/{run_id}`, `/manifest`, `/files/{artifact_id}`, `/checkpoint?tick=...` and
`/events?start_tick=...&end_tick=...`. The request selects the registered profile
and exact layout/source revision; it cannot override graph, stock or timings.
Public manifest returns `{run_id,transport,files}`; nested transport is native.
Every cached read rechecks file bytes, registered bundle and native/public IDs.

Use native half-open 60,000,000-tick buckets and raw `{path,bytes,sha256}`
descriptors, including split parts within a bucket; preserve file order and
global seq. Raw event/checkpoint part maximum is 8,388,608 bytes. It is **not** a
bound on inputs, catalog, total export, a whole 60s window, or client memory.
Manifest is published last with exclusive files; missing manifest is not a
successful run. Resolve paths inside the artifact root and reject escaping or
hash/length-inconsistent files. Current readers validate the whole bundle before
selection; they do not promise streaming/bounded memory.

Currently true: actual bounded component execution, internal inventory,
captured-checkpoint retrieval. Currently false: accepted C12 adapter, full V3,
arbitrary seek, interpolation, hand-contact proof, general loaded admission,
N4 dynamic roles/staffing, all-class/all-port workflow. Receipt shared inventory
has a real native proof and its own native publication namespace. Its registered
HTTP transport belongs to that native namespace too. A C12 receipt adapter profile
and any frontend agreement remain unsupported.
Do not fill absent capabilities with a visual fixture or claim that C11's
unclocked periods are workload hours or DES performance.

## Evidence, rejection and agreement boundary

Observed CLI/real HTTP evidence, rehashed in this review:

| Fact | Value |
| --- | --- |
| Native ID | `3d160cd54bbd3ff68a092fac2df345444514593089e2b9b6f22c47e1779a5cd7` |
| Public ID | `fc78912a5d2234c5566b50934eab20abedb7200eb0b07c2fe1d708372d5d23da` |
| Input SHA256 | `b1c62e61f80afe0e1e31fd0590f245080ad06423ffcff4898f8ee27189ae2ce6` |
| Native manifest | 3514 bytes; SHA256 `ae38c49a1ab42182b486c4a738629d33bef0a587d400e890fc5759c62d382717` |
| Raw files | 17; 46,127,485 bytes; CLI and stored HTTP files identical |
| Receipt proof only | Input `259d9488c52c6c3309b5b1f1352af1521a5ea43a3b731f878ff86272229b77c7`; engine `qoima-receipt-flow-v3-proposal-1`; canonical native outcome SHA256 `ed0f380ccff79bcaa3bc6818b0cf635a9b1d35993107455aa27e3c2d34083e0d` |
| Native receipt publication | Native run ID `2126f9494fb757a6df1a12cae3b0001c00cdfab9b167040ce4e473e8a382b7f3`; manifest 5895 bytes, SHA256 `b10f5437118e60d0dc2f968b2351b9b0e669b46ff58402178befedd4e395a0b8`; 28 files, 71,959,075 bytes. Native evidence only, not C12 receipt support. |

Receipt source observation (not a new test oracle): new HU `RECEIVED-SMALL-1`
is credited at tick 10,000,000, seq10; its whole-HU claim is acquired at seq11.
At tick241,760,000, putaway seq31 precedes receipt-claim release seq32 and
`pick:O1` acquisition seq36. These are real provenance examples, **not a fabricated
C12 run**. Prewritten arithmetic was 12,256+24=12,280 registered, 12,277 onsite+3
shipped; 9405.04kg=9404.885+.155. Original530 wrappers and all24 actors remain.

Reject visibly: unsupported namespace/version/profile; untrusted producer;
wrong raw or semantic layout/source binding; public/native/bundle disagreement;
missing or extra files; unknown semantic IDs; unordered/duplicated seq; future
completion; noncaptured tick; excessive event window; inconsistent balances,
creation, claims or terminal state. Never retry as `visual_fixture`, invent
poses, reuse V2 geometry, or turn `partial` into `complete`. Current HTTP proof
observed uncaptured tick422, arbitrary-seek404 and oversized-window422; proposed
C12 error vocabulary still needs agreement.

Separate agreement is needed on: (1) opt-in namespace/version/producer trust and
artifact acquisition; (2) native vs API vs adapter identities and source/layout
binding; (3) semantic IDs, exact captured-only clock/state/event/receipt rules;
(4) spatial/catalog bindings and the explicit unsupported pose/contact features;
(5) worker registry versus future effective-role transitions, six-post leases
and metric meanings; (6) rejection/error behavior and review fixtures. These are
reviewable integration decisions, not reasons to stop independent backend work.
First frontend acceptance can be captured native inspection; continuous rendering,
receipt API and dynamic-role support require later explicit profiles and tests.

Local check output (no DES, HTTP restart or upstream script execution):

```text
C12_HANDOFF_FILES_VERIFIED=15 SCHEMAS=6 EXAMPLES=7 ACTUAL_ENGINE_REJECTED=True
CLI_HTTP_IDENTICAL_FILES=17 RAW_BYTES=46127485
RECEIPT_RAW_ARTIFACTS_VERIFIED=5 MAIN_FROZEN_FILES_VERIFIED=41
NEW_DES=False UPSTREAM_SCRIPT_EXECUTED=False ADOPTION=False
C12_NATIVE_SHARED_SOURCE_BINDINGS=14
SEMANTIC_LAYOUT_MATCH=True
```

Schema checks here are structural Draft2020-12 checks with local-only references,
not a rerun of Tilek's semantic validator. Detailed inventory and observed IDs:
[`c12-engine-adapter-evidence.json`](c12-engine-adapter-evidence.json).
Sources: [C12 README](https://github.com/tilekkz/QoimaTwin/blob/050adaf3645831298ac5daea7aad1191c92dcb2e/docs/v3/contract-proposals/handoff/README.md),
[audit](../../research/2026-11-08-tilek-v3-compatibility.md),
[HTTP evidence](../../research/2026-11-08-connected-light-http.md),
[receipt publication plan](../../adr/0055-connected-receipt-publication.md),
[receipt proof](../../research/2026-11-08-connected-receipt-proof.md).
All native field mappings were checked against frozen main `app/v3/flow_run*`,
`flow_transport*`, `api_light*`, `flow_profile_wire.py` and `runtime_time.py`.
