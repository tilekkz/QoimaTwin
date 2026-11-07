# FIX01.2 — Top-down cart grip and affected pose regressions

- Owner: root
- Status: PASS
- Depends on: FIX01.1
- Ownership: tools/blender/v3 worker/source builders, frontend/src/adaptive-v3/motion and seatedDriver.ts; affected V3 GLB/blend/stats, local QA tools, specs and evidence. No backend or protected contracts.

## Result and inputs

Apply the direct user correction from USER_CORRECTIONS_2026-11-08.md and the three saved screenshots to existing assets. Preserve body mesh volume, dimensions, actor identity and original accepted source snapshots.

## PASS and verification

Measure palm directions and actual contacts/solid clearance on editable meshes and exported GLBs. Recheck affected rest/reset/release, gait/seek and driver poses. Inspect bounded headless captures. Carton: fixed four walls, four distinct hinged top flaps, clear access, unchanged closed HU/catalog and supported contents. Record failures and retests before PASS.

## Actual / evidence

Overhand pose solved with explicit axial roll, 22.5deg natural palm tilt from down and grip centres at X +/-195mm to clear posts. Native grip, 901 runtime/91 native gait frames for each template and seated driver regressions pass. Next inspect headless paired/grip and gait UI captures before checkpoint push.

## Defects

No material unresolved defect for this result; fixes and retest evidence are recorded in checkpoints.

## Checkpoint 2026-11-07T22:31:32.118636+00:00

Overhand pose solved with explicit axial roll, 22.5deg natural palm tilt from down and grip centres at X +/-195mm to clear posts. Native grip, 901 runtime/91 native gait frames for each template and seated driver regressions pass. Next inspect headless paired/grip and gait UI captures before checkpoint push.

## Checkpoint 2026-11-07T22:33:40.232964+00:00

Overhand cart grip reviewed in paired side/quarter and manual gait 3.5s headless captures. Six native glove/bar witnesses, no paired solid penetration; 901 runtime and 91 native poses per template, inward rest restored on release, wrist/cuff connections and palm-down direction throughout gait. Driver native/runtime and build pass. Headless UI pause/repeat/keyboard/seek/reduced-motion/error/stale-request/resource regressions pass with owned browsers terminated. Sources unchanged in volume and scale; only cart anchors moved inward40mm.

## Reviewed result

Paired side/quarter and manual 3.5s gait frame inspected: overhand palms, 22.5deg forward tilt from vertical down; original arm/wrist limits retained. Six actual glove/bar contacts and continuous native cuff/spine connections. Initial/dispose/release restore inward rest. Driver explicitly neutralizes added axial rolls while seated and restores rest on release.

Evidence: `../evidence/FIX01.2.json`.
