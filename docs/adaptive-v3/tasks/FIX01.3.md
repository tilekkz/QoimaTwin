# FIX01.3 — Four-flap outer SMALL carton opening

- Owner: root
- Status: PASS
- Depends on: FIX01.2
- Ownership: tools/blender/v3 worker/source builders, frontend/src/adaptive-v3/motion and seatedDriver.ts; affected V3 GLB/blend/stats, local QA tools, specs and evidence. No backend or protected contracts.

## Result and inputs

Apply the direct user correction from USER_CORRECTIONS_2026-11-08.md and the three saved screenshots to existing assets. Preserve body mesh volume, dimensions, actor identity and original accepted source snapshots.

## PASS and verification

Measure palm directions and actual contacts/solid clearance on editable meshes and exported GLBs. Recheck affected rest/reset/release, gait/seek and driver poses. Inspect bounded headless captures. Carton: fixed four walls, four distinct hinged top flaps, clear access, unchanged closed HU/catalog and supported contents. Record failures and retests before PASS.

## Actual / evidence

Root cause confirmed in source: whole front wall was raised180deg while top underflap geometry was only26mm long. Corrected builder keeps four walls fixed, folds four real top flaps outside, and extends two open-variant minor flaps to116.5mm. Next run native source/rack clearance and bounded headless top/quarter inspection before PASS.

## Defects

No material unresolved defect for this result; fixes and retest evidence are recorded in checkpoints.

## Checkpoint 2026-11-07T22:33:40.478344+00:00

Root cause confirmed in source: whole front wall was raised180deg while top underflap geometry was only26mm long. Corrected builder keeps four walls fixed, folds four real top flaps outside, and extends two open-variant minor flaps to116.5mm. Next run native source/rack clearance and bounded headless top/quarter inspection before PASS.

## Reviewed result

Open case quarter/top and assembled source quarter/top inspected. Four fixed walls and four distinct external folded-back top flaps. Two open-variant minor flaps corrected to 116.5mm; folded front/rear flaps offset beyond label/tape. Original closed HU/source/catalog unchanged. Four real contents remain supported; two targets accessible from above. No whole-wall flap.

Evidence: `../evidence/FIX01.3.json`.

## Checkpoint 2026-11-07T22:36:48.171610+00:00

Three user corrections complete and reviewed. Four fixed carton walls/four folded external flaps, unchanged closed HU/catalog. Native support/clearance, GLB 0/0 and four headless carton views pass. Evidence FIX01.1..3. Next P03.5.3: redesign top-entry reach/pick using same unit/actor instances; old front-entry plan is invalid.
