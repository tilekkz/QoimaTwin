# Bounded native moving-crew refinement

This work-only certificate refines the existing coarse moving-source-vehicle/crew test for the issued original STANDARD manual case starting at exactly 240 s, against the unchanged e248a703 original-LONG source plan. It does not change product files, collision tolerance, speed, crew routes, inventory, or source geometry.

The two requested coarse failures have no native AABB overlap. K01 at 362.224609375 s has 1.9903115966 m native component AABB distance to F01+driver. P02 at 880.0583698545 s, using the separate 397.8298542295 s candidate start, has 5.6503058157 m to F01+driver+held bridge. The second witness is diagnostic only; the full positive certificate is for start 240 s.

All existing coarse-positive intervals retain their original proof. Only coarse-negative intervals are refined. Each original native coordinate component gets a world AABB. For moving workers, each mesh is enclosed about its first actually animated torso/thigh joint; the immutable pelvis height is not incorrectly converted into horizontal radius. Descendant translation norms plus native vertex radii bound every emitted leg/arm rotation, so no sampled IK angular-velocity assumption is used. Maximum horizontal component support is 1.189594 m. K01's source-compiled fixed waiting interval is treated precisely, with explicit phase cuts.

Human root motion retains the previous 3 m/s bound. Source component movement has a conservative 32 m/s bound: original source root <=2 m/s, yaw <=2 rad/s, all native attachment/body chain radii <8 m, wheel spin <=12 rad/s with native radius <.5 m, rear steering <=2 rad/s, holder controls <=4 m/s, and fork translation <=1 m/s. The rounded total is larger than the 30 m/s sum. Original arcs/phase derivatives, wheel radii, chain radii, and rear-steering derivative inequality are checked. Raw unitish transforms receive a further STRICT 0.1 mm human-enclosure enlargement. This enlarges geometry; it does not relax the unchanged 2 um native tolerance or 0.25 m padding.

The result covers 240..1186.503390912233 s, with source phase cuts, source gait-derived K01 wait cuts, absolute manual phase cuts, and adaptive temporal subdivision. All refined leaves exceed 0.25 m + 2 um after temporal and numerical enlargement. There are zero unresolved intervals. Source pins are byte-identical before/after. Three negative controls reject physical worker/vehicle proximity, dropping numerical enlargement, and dropping temporal inflation.

## Proposed integration boundary

Consume the exact-byte certificate only for matching issued source and full-manual factory handles, original request/HU/participants, exact 240 s start, complete duration/phase signatures, canonical bundle/native model epoch, and every listed source pin. Store its hash in the acceptance receipt. A caller-supplied boolean or arbitrary certificate object must not grant admission. Other starts/cases retain the existing coarse refusal or need their own proof.

This is a scoped relative moving-source-vehicle/STD-crew enclosure certificate. It does not certify unrestricted movement of the other 22 crew, structural hardware strength, or arbitrary scheduler traffic. Original static-layout and individual manual/attachment action checks remain separate evidence. Stationary new stow props are not newly certified against arbitrary moving crew by this certificate.

Reproduce: `node work/v3/full-tz-closeout-20261109/long-source-operation/moving-crew-native-refinement.mjs 240`. All compilation/output paths are owned `moving-crew-native-refinement*`; no canonical runtime/evidence output is overwritten.
