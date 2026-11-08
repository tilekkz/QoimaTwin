# V3 contract proposal handoff — C12

This package makes the current visual/analytical interfaces reviewable in Git. It is an additive proposal, not an adopted Arman engine contract. Existing `contracts/**` and all root proposal JSON files are preserved by exact hashes. `manifest.json` binds this generation to its inputs; later additions require a new generation.

## What is available

| Interface | Source / scope |
|---|---|
| CargoArchetype and StorageSlots | Existing strict schemas, eight cargo records, packing recipes,132modules/776slots; original C01–C08 admission and conservation checks remain authoritative |
| PortView | Six exact port projections with original source references; class membership never grants loaded route/equipment admission |
| WorkerProfile | Draft P01 cross-training and F01/FL01 capability examples; original24IDs, no active registry/scheduler. P11/P12 still have to materialize and verify their whole registry and transitions |
| Source-labelled input | Geometry projection, isolated P04 visual clip and C11 analytical default. Explicit source/clock/frame/metric types; no automatic fallback between them |
| Slotting comparison | Same frozen N2 material flow/config for both alternatives in each of the1/2/4/8period cases. Default1 is a valid no-op; relocation is charged once. No throughput, complete-order duration, money or DES claim |

## Integration and migration boundary

Keep V2 readers and existing canonical schemas unchanged. V3 consumers select this proposal namespace/version explicitly, check exact content hashes and layout_content_hash, then resolve semantic IDs. Columnar numeric indices cannot be reused across layouts. Units are metres, seconds, kg, right-handed Y-up; entity scale stays1. A packaged unit, HU, lot, SKU, storage slot, workflow tote and parcel identity remain distinct.

The original C11 payload keeps its `synthetic_planning_fixture` label; the typed wrapper exposes it as `analytical_fixture` only after its known namespace/reference and false actual-run flags pass validation. The current envelope profiles cover the three named examples; another payload needs an explicit supported profile, never a guessed fallback.

`actual_engine_run` is deliberately unsupported by this proposal input envelope. There is no positive fabricated actual-run example. A future Arman-owned exporter and separately accepted adapter must supply canonical schema/version, genuine run/producer provenance, matching physical inputs, conservation and replay semantics before that mode is enabled. A JSON label/hash by itself cannot authenticate an engine result. Unsupported actual input fails visibly; it must never turn into a visual fixture silently.

Worker capability is not a job assignment or another employee. Resolve an existing ID, check its allowed role/equipment, acquire an existing free post and resources, account for its route/travel/transition, and change effective role on the source clock. Six existing packing stations do not become eight: if all six are occupied, an extra packer is inadmissible. Draft example speeds/skills are synthetic assumptions, not measured employee training or live availability. The V2 actor reference supplies IDs/baseline roles/equipment identity only; its old home coordinates are not adopted as V3 placement.

C10 supplies frozen baseline **placement**, not a comparable old-flow cost. Re-evaluate that placement under the same C11 N2 flows/horizon used for the candidate. Port weights/horizon/staff/physical inputs cannot drift between alternatives. `comparison_inputs_sha256` binds each pair; horizons have no measured clock duration. Staffing comparison is deferred and cannot be inferred from C11 slotting results.

Current limitations remain explicit: source-labelled fixtures are not operational admission; P03.5.3 pick access, remaining personnel/replay/UI/QA and scene density are still open. Geometry/data handoff does not close visual_complete or backend_integration_complete. Publication here does not record recipient acknowledgement or backend adoption; no external message is sent by these tools.

## Offline verification

From the repository: `.venv/Scripts/python.exe tools/visual/v3/validate_contract_handoff_v3.py --check-only`. It uses installed jsonschema Draft2020-12 and a local-only reference registry, validates old Cargo/Slot schema shapes and new examples, checks exact original input/protected-contract hashes, typed source/clock/frame boundaries, capabilities, port projections, conservation/comparison arithmetic and negative mutations. It performs no network request, backend write, browser launch or original-data regeneration.

To deliberately regenerate this additive package from reviewed current inputs: `.venv/Scripts/python.exe tools/visual/v3/build_contract_handoff_v3.py`, followed by the validator and a Git review/push. The manifest excludes its own hash to avoid a cycle; all other package files are bound by it. References are repository-relative and must resolve inside the repository.
