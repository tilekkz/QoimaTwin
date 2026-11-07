# FIX01.1 — Inward neutral palms on both worker templates

- Owner: root
- Status: PASS
- Depends on: none
- Ownership: tools/blender/v3 worker/source builders, frontend/src/adaptive-v3/motion and seatedDriver.ts; affected V3 GLB/blend/stats, local QA tools, specs and evidence. No backend or protected contracts.

## Result and inputs

Apply the direct user correction from USER_CORRECTIONS_2026-11-08.md and the three saved screenshots to existing assets. Preserve body mesh volume, dimensions, actor identity and original accepted source snapshots.

## PASS and verification

Measure palm directions and actual contacts/solid clearance on editable meshes and exported GLBs. Recheck affected rest/reset/release, gait/seek and driver poses. Inspect bounded headless captures. Carton: fixed four walls, four distinct hinged top flaps, clear access, unchanged closed HU/catalog and supported contents. Record failures and retests before PASS.

## Actual / evidence

Diagnosing and correcting existing worker rest-palm orientation; sources backed up under work/v3/corrections-2026-11-08/before. Next: add explicit axial pronation controls, preserve wrist limits and validate both templates.

## Defects

No material unresolved defect for this result; fixes and retest evidence are recorded in checkpoints.

## Checkpoint 2026-11-07T22:23:34.916793+00:00

Diagnosing and correcting existing worker rest-palm orientation; sources backed up under work/v3/corrections-2026-11-08/before. Next: add explicit axial pronation controls, preserve wrist limits and validate both templates.

## Checkpoint 2026-11-07T22:31:31.893142+00:00

Both existing neutral templates now have inward axial palm rolls; unchanged 50 native body solids, connected cuffs, 1.7m height and no hand/leg triangle intersections. Export geometry and 0/0 validation pass. Four bounded headless views inspected; five-role material/identity regression passes. Evidence assets/v3/iterations/worker-base/FIX01.1 and current role QA.

## Reviewed result

Both templates side and quarter inspected: palm channels face legs, cuffs connected, body height/volume preserved. All five roles share corrected template with isolated materials.

Evidence: `../evidence/FIX01.1.json`.
