# Original character and pose-only correction

User instruction: «ты чет персонажа воообще переделал, верни как было в самом начале, и меняй только его силуэт того как он держит коробку при движении».

The original `frontend/public/models/v3/worker-base.glb` remains byte-identical to HEAD: SHA256 `542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163`. Restore this representation as the motion-review default. Preserve its face, hat, vest, torso/limb proportions, mesh vertices, materials, node translations/scales, rig hierarchy and native joint limits. Subsequent hold changes use arm-joint rotations and the whole original HU pose only. No shoulder widening, torso narrowing, sleeve scaling, hem change, gusset or thumb geometry changes.

Prior `a719` joint-fit model and `e426` numerical report are historical technical evidence. The user rejected that character appearance; they are not the current visual target. W05.3.13 is reopened as FIX. Preserve its files and the Night archive, but do not promote its geometry again as the current default.

A bounded work-only search tested22 targeted poses on the unchanged original model. Ten solved their contact constraints; no new lower pose cleared the measured cuff/vest witnesses in this set. This is not a global infeasibility result. Details: `work/v3/original-body-hold-20261109/REPORT.md`, `probe-results.json`, `preservation.json`. No source model was edited.

The restoration fallback is the exact historical original carry pose `f33bdb63db8fc78af68af173926a0a59267eda9f83b484a98e71ec4f375bac7b`, HU position `[0,.96,.52]`. It is an appearance rollback, not acceptance of the requested lower/approximately90-degree hold. Its measured upper-arm tilt is60.28degrees and inner elbow103.27degrees; lower-pad overlap is82percent, upper-pad overlap0. Original adjacent clothing/joint interiors remain reported. Do not call it a full-palm or strict disjoint-solids pose.

Next pose work must improve the original character's hold without changing its design, and pass fresh native contact/HU/body/stance/limits and actual three-view review. Physical acquisition/release and whole-scene source jobs remain separate open results.

Git authority: origin `https://github.com/tilekkz/QoimaTwin.git`, canonical workspace `C:/Users/izbas/Documents/Codex/2026-11-06/new-chat/work/QoimaTwin`, feature branch `codex/twin-v3-adaptive`. Preserved V2 is `codex/twin-v2-polished`; main and Arman's backend history remain untouched.

## Desktop-only steering — 2026-11-09T06:44:23.044588+00:00

User: «телефонная версия не нужна ... не надо». Current work and acceptance target desktop only. Do not implement mobile adaptations or spend separate phone browser test runs now. Preserve historical mobile evidence without treating it as a current deliverable or required gate. Continue original-character hold, desktop animation/workflows and remaining visual priorities.

## Functional desktop continuation — 2026-11-09

The user explicitly prioritizes working correct animation over further ideal-pose polish. Current motion-review default is original_hold with the unchanged original542591 model and pose0aa1247d. Box position[0,.88,.42] is8cm lower/10cm closer than the f33 restoration fallback. The current2135-state native report b347f26d and actual desktop playback preserve source appearance, full lower-palm support and stance. Measured elbow100.74degrees/upperarm38.00degrees from down are recorded honestly; no exact90/down certificate or global disjoint-solids claim. Historical source-join interiors remain source geometry. The old a719 redesigned character remains historical. Full source pickup/cart release/operational cycle remain separate open results.
