# V3 ownership and adapter boundary — I05

Tilek owns the visual product: independent references, modular Blender/GLB assets, layout visualization, frontend adapter, visual fixtures, actions, cameras and visual/performance QA. Arman owns forecasting, planner, DES, inventory ledger, API/exporter and operational metrics. Existing backend/shared wire contracts remain authoritative for V2.

## Isolated writable scope

- `assets/references/v3/**`: generated independent concepts, exact prompts, provenance and reviews.
- `assets/v3/**`, `frontend/public/models/v3/**`, `tools/blender/v3/**`: new geometry, editable sources, manifests, previews and builders.
- `frontend/src/adaptive-v3/**`: separate V3 component, mount, catalog/layout inputs and adapter.
- `frontend/tests/v3-*.spec.ts`, `frontend/tools/*-v3.*`: bounded V3 checks and capture tools.
- `docs/adaptive-v3/**`: execution cards/evidence/README/RESUME; root owns central board/state/checkpoints, agents own only assigned cards/artifacts.
- `docs/v3/contract-proposals/**`: namespaced proposed Cargo/Slot/Port/Worker/Scenario types and examples, migration notes. These are proposals rather than accepted canonical engine contracts.
- `work/v3/**`: scratch work and verified original-file backup.

`frontend/src/main.ts` and frontend build/launch configuration may receive a small explicit V3 selection entry in W02/H06, owned by root. The default V2 launch/importer stays reviewable. No silent substitution of current V2 Run/layout files. Existing V2 geometry/builders/replay are preserved as baseline; any later bug fix requires a scoped card and verification.

## Protected shared state

`contracts/**`, backend/forecast/planner/simulation/ledger/API implementation and data stay unchanged by this visual work. Snapshot hashes for current `contracts/**` are in `work/v3/protected-contracts.json`. Read-only fetch found `origin/arman/backend-core@dd6e7ba`; it was not merged. New engine integration is a separate accepted handoff, not implied by an import button.

V3 adapter inputs: explicit versioned layout/port/slot/cargo catalogs, 200 synthetic SKU bindings, original24 actor profiles, role assignments, source-labelled run/events and asset bindings. Output: absolute-clock visual state. Unit/handling unit/lot/slot/port identities remain distinct. Incompatible input produces a visible reason and retains actual dimensions; presentation does not create inventory/operations or recompute backend KPI.

Visual fixture, analytical fixture and actual engine run labels remain separate. `visual_complete` and `backend_integration_complete` are independent statuses. Same-input comparison hashes and admitted plan differences accompany comparisons. Baseline ports/staff remain fixed for slotting-only comparisons; staffing comparisons retain stock/layout/orders.

## Parallel execution

One ACTIVE card per executor, exact owned paths in its card, preserved foreign edits. Only root writes central task state and owns the live Blender/browser benchmark. Background Blender tasks use distinct output files; no concurrent benchmark/render overload. Root reviews each material artifact before PASS. Current33model inventory and3fresh V2 captures establish baseline, not V3 acceptance.

Evidence: `FRONTEND_MAP.md`, I01 Git snapshot and current shared contracts hashed at I05. No backend implementation or old contract was changed.
