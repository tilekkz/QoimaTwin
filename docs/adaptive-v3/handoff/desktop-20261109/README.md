# Desktop delivery · 2026-11-09

The desktop comparison now changes actual **sections and racks in B**. The original warehouse A remains unchanged; «Изменения» switches between structural reconfiguration and the earlier cargo-only comparison.

## Delivered behavior

- Native floor: 144 × 72 m, four right angles. Axis-aligned elevated overview and a top-plan control show a rectangular silhouette; framing accounts for the floating controls.
- Structural B: 132 → 164 racks, 32 new empty racks, 48 relocated SMALL modules. Rack footprint: 416 → 492.8 m². Other families keep their admitted source frames, including the heavy FRAGILE crates in STANDARD.
- The same 530 original HUs retain identities, quantities, masses and occupied slot IDs. Stock follows its module's rigid frame. Added racks contain no invented stock. Staff remains 24 people, two vehicles and six ports.
- New pedestrian/cart geometry, fresh checks of retained forklift trajectories, synchronized floor markings/minimap/picker homes, B-aware HU/slot/zone search, and exact A restoration when switching or picking.
- Staffing at `staff-v3.html#role-assignment`: original skills, available posts, nonzero handoff and walking/return time, retained unfinished work, role change on arrival and absolute seek/reset. Trained P01/P02 are accepted; P11/P12 are refused.
- `motion-v3.html`: byte-identical original character `542591db…`, box 8 cm lower and 10 cm closer than the historical hold, full lower-palm support. No geometry/proportion/material edits. The inherited vertical-preset model selector is repaired.
- Audio: gesture enable, muted default, cooldown/four-voice bound, failure recovery, silent seek/pause. A separate C11 analytical panel prices handling and return travel, allows a one-period no-op and labels unmodelled queues explicitly.

## Evidence

Nine production entries pass project type checking and build. Layout factory passes five refusals and revalidates the exact four source texts. Access passes 504 pedestrian endpoints at a conservative 0.44 m rest-body envelope and 482 cart endpoints at 0.95 m; all 35 HUs over 15 kg have directed gate/service access. Source-permitted swept vehicle arcs rechecked: bare 1,316, nonlong 1,282, LONG 434. All 695 native enclosures and 50 independently clipped paths pass.

Renderer checks cover all 2,551 original instance parts, 32 extra native rack prototypes, source geometry/material references, invalid-input refusal, minimap, 20 A/B cycles and disposal: 17 checks pass. The actual desktop browser passes 12 functional assertions for switching, conservation, searches, seek, hover, reload and deep links. Test Chrome required forced cleanup of its attested process tree; all owned PIDs are gone and raw attempts remain preserved in the canonical browser report.

Staffing passes 15 actual browser checks and 300 model seeks. Audio passes 14 focused controls and two native browser cases. Original carry retains its 2,135-state native proof and actual desktop playback review.

Canonical receipts: `docs/adaptive-v3/evidence/warehouse-layout-plan-b-164-*.json`. Active layout: `docs/adaptive-v3/fixtures/layout-plans/dense-manual-b-164-v1.json`; payload SHA `16ecd5ad77598238403279c803a0080ee3f13bb3a21709fa3b7040b46805e9dc`.

The asset snapshot records 36 served models with zero Khronos errors/warnings. One exact declared/native bounds metadata difference of 7.629 µm is recorded unchanged; model bytes and contact tolerances are unchanged.

## Scope and continuation

This is a comparison of planned configurations. It does not execute rack installation, move loaded racks, grant traffic reservations, or claim structural relocation cost. Full connected inbound/outbound cycles, source acquisition/cart release and the authoritative operational engine remain separate work. The C11 cost example does not price the new rack layout.

The published N2/N3 API handoff at `799ff93` remains unchanged for Arman. Development uses `codex/twin-v3-adaptive` in `tilekkz/QoimaTwin`. Preserved V2 remains `cb5777f108478aabe3b7117a19d2b471ad79d2de`. Phone adaptation is outside this delivery.

Build with `cd frontend` and `npm run build`. Extract the portable ZIP fully and run `Run_V3.cmd` with Node.js 22.12+. The source-packed historical native harness is evidence; its original absolute paths are not a portable CLI entry.
