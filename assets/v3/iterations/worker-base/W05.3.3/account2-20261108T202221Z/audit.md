# Carry-only hip kinematics investigation

Result: **CARRY_ONLY_CANDIDATE_BOUNDED_NATIVE_GATE_PASS**. Existing bounded native gate: 176 body frames, 1450 contact/stance frames, 0 positive material witnesses, 0 refused frames. Targeted seven saved times: 0 positives, 0 solver errors. Production and historical evidence were read-only.

The original proposed three-variable hip X/Z and knee X solve was tested against the entire gate and retained all seven collisions. Its source and failing report are preserved as hip-xz-only.candidate.ts and hip-xz-only-checks.json. A four-value sign/magnitude probe on the original hip yaw freedom found the mirrored positive-left/negative-right bias removes these collisions. A fixed bias consumed too much foot yaw during turns; the final bias uses the continuous residual-yaw cap below. All original joint limits remain enforced.

Exact change: within the loaded compiler only, replace gait.sample(seconds) at the apply site with solveLoadedLegs(rig,gait.sample(seconds)). Keep every pure-gait root, timing, body drop and foot world position/yaw target. Keep all eight static carry arm rotations. For each native leg, let r=wrap(targetFootYaw-rootYaw), shinTwist=0.30*r and preferredHipYaw=sideSign*0.30*min(0.30,abs(sourceHipX)), with sideSign +1 on L and -1 on R. Clamp preferredHipYaw to [r-shinTwist-0.19,r-shinTwist+0.19]. Solve hip X, hip Z and knee X by Newton for q1*a+(q1*q2)*b=goal, using q1=EulerXYZ(hipX,hipYaw,hipZ), q2=EulerXYZ(kneeX,shinTwist,0). Compensate qFoot=inverse(q1*q2)*desiredFootQ. No extra pivots, geometry changes or epsilon/waiver changes. No hardcoded witness times.

The standalone kinematic probe passed 1458 samples. Maximum reconstructed foot error 9.869424392170359e-12 m; minimum original joint-limit margin 0.0014601836602549795 rad. Exact comparisons confirm root, timing, body drop, feet and nonleg pure rotations are unchanged. Both endpoint source leg rest quaternions match exactly; near-endpoint samples at 1e-12 through 1e-4 seconds also tend to source rest. Native maximum carry contact gap 3.873027934061635e-9 m; maximum sole error 9.869424392170359e-12 m; minimum native boot Y 1.490116072200287e-8 m. The original 2e-6 m thresholds and complete native edge/triangle control conditions are preserved.

The scratch checker is a source copy with canonical absolute front/repo paths, local cache/report destinations, absolute dependency imports, candidate-only source substitution before TypeScript transpilation, and candidate provenance in its report. Its native collision math, sampling and controls are unchanged. Production module hashes remain original in input_hashes; candidate bytes have their own honest SHA-256. Final source rechecks: all unchanged. No graph MCP was available; exact-source fallback was used without freshness claims or reindexing. No browser, Blender, builds, Git, authentication or configuration actions.

Candidate SHA-256: 0435b5e93d4d674ffc7b0f11c2b8c0af214380437cc2cce938dcef9a9586d2e8.

Source SHA-256 values:

- frontend/src/adaptive-v3/warehouseLoadedWalkCalibration.ts: cca20c003bf84d5747cfaddf484fc8ecf6799f9900f6e068e4e36373f85c2a7e
- frontend/src/adaptive-v3/warehouseWorkerGait.ts: 1909f2fcb42fad2de4776c98e2632f49609355669b0c25274227cbee184b79b3
- frontend/tools/check-warehouse-loaded-walk-calibration-v3.mjs: 117d8ef79c6e421d76f3adad355e9222518e20ada394820709e030c7639f04cb
- docs/adaptive-v3/evidence/W05.3.3-checks.json: d6de25573cd713d06aa3d938ff962f9f714effe51d8fa72b0f3e5c7958068378
- docs/adaptive-v3/evidence/W05.3.1-checks.json: c589584d503575a855c25060c38e2aa881e0cde849a66114d6838fa8b14b75ea
- docs/adaptive-v3/evidence/W05.3.4-checks.json: 2c2b2e6024357cfd849b55d938882c5ac41947c041a5ed0d2987d01d41c5c443
- frontend/public/data/v3/worker-base-carry-pose.json: f33bdb63db8fc78af68af173926a0a59267eda9f83b484a98e71ec4f375bac7b
- frontend/public/models/v3/worker-base.glb: 542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163
- frontend/public/models/v3/small-carton.glb: 10ae707579214c6ef87bf1897a04c35c59c913ca6093d5e511f8515c9354f317

Reproduce from the canonical repository: node work/v3/account2-loaded-hip-kinematics/20261108T202221Z/prepare.mjs, then node work/v3/account2-loaded-hip-kinematics/20261108T202221Z/kinematics.mjs, then node work/v3/account2-loaded-hip-kinematics/20261108T202221Z/probe.mjs. To regenerate targeted results run final-targeted-prepare.mjs then final-targeted.mjs. Run finalize.mjs last to refresh this audit and findings. Every write stays beneath this owned output directory. prepare.mjs regenerates a candidate from current exact source; compare source-hashes.json to the delivered findings before treating a rerun as equivalent.

Limitations: bounded source-native CPU sampling is not a continuous collision certificate, balance/force validation, source pickup, runtime Scene binding or operational admission. This is a scratch candidate for root to review and integrate; no production patch was applied.
