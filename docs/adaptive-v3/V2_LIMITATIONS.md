# V2 baseline and V3 deltas — I06

Reviewed inputs: `ASSET_INVENTORY.md`, `FRONTEND_MAP.md`, fresh `evidence/v2-overview.png`, `v2-worker.png`, `v2-forklift.png` and `viewer-capture.json`. Root opened all three PNGs. Current `frontend/src/scene/largeWarehouse.ts` source confirms the quoted constants/placement logic; graph generation2026-11-06T22:22:36Z has metadata_changed, so current source and actual images carry the claims.

| Observed V2 behavior | Evidence | Required V3 change |
|---|---|---|
| Main physical envelope72×48×8,288rack modules and864slots | Current canonical layout mapped in I04; visible UI and overview; mount guard `qoima-72x48-v2` |144×72×8:10368m² and82944m³, exactly3×; retain ordinary people/equipment scale and derive address count from new layout |
| Dense, similar tall rack rows dominate overview | Fresh overview viewed; current rack physical4.65m vs logical envelope5.4m explicitly inventoried | Five distinct storage types, multiple separated compatible regions per major class, clear empty circulation and finite flex bays |
| Lot markers use one crate family with deterministic presentation variations | `largeWarehouse.ts` buildOverview uses SKU-character/index seed, scale/pairs/stacks; not fresh randomness each frame | Stable catalog of eight cargo archetypes; explicit physical dimensions/mass/orientation/handler and units vs handling unit vs lot |
| Two dock instances: receiving `[0,0,36]`, shipping `[72,0,3]` | Current buildOverview placements and overview | Three inbound and three outbound ports with individual restrictions/buffers/shared finite resources and loaded approach clearance |
| Five muted role colors already supported | roleColor picker#3C6469,packer#566e85,receiver#926e4c,shipper#60705b,driver#ac8034; batch/rig tint in current map | Stronger prescribed vest palette, numericID, badge and persistent legend; effective role derives from assignment event, instance materials, original24people retained |
| Current near assets follow detailed industrial miniature style | Actual worker/forklift closeups and independent source reference inventory | New cuboid cartoon reference first: square head/body/limbs, planar masses, small stepped bevels, matte finish, restrained functional detail |
| General scene occupies modest portion of useful canvas | Actual1440×900overview shows wide empty margins and dense visual texture | Composition reference before final assembly; useful-frame overview, zone cameras, follow and detailed stands |
| Replay/seek, models/stands, LOD, source labels and muted SFX already exist | I04 source map; fresh screenshots and buildscript index-DOPf_3RA.js, zero browser errors | Reuse verified principles through a separate V3 boundary and re-test all V3 geometry/state/attachments/performance |
| Inline V2 file adapter exists; snapshot business state opaque to visual restoration | Exact adapter limits documented in I04 | Namespaced V3 proposals/adapter and handoff; separate visual_complete/backend_integration_complete, no claim of integrated new DES |

V2's current polished production build passed33checks before this transition; that result is baseline evidence only. Current33model inventory proves file presence/hashes, not V3 quality. A completed High V2 performance series and an interrupted Low series do not count as V3 performance. Existing night MP4 does not show V3.

Protected baseline: `work/v3/backup-manifest.json` contains240verified original dirty-file copies. Current21shared contracts hashed in `work/v3/protected-contracts.json`. No old backend/shared contract was changed to satisfy this audit.

PASS: every delta above has a current source or viewed artifact. Existing capabilities are acknowledged. R01 may now create an independent new style board; no V3 model has started.
