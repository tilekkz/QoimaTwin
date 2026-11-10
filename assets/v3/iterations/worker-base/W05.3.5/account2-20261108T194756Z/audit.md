# W05.3.5 — bounded original-native upper-stock feasibility

No clear endpoint at the actual source rack was established. Two-hand opposed native contact **is feasible in the isolated worker/HU pair at the exact source cargo pose**, but the first candidate and every rack-tested candidate in the bounded search have native rack penetration witnesses. This is a search result, not a proof that every original-joint solution is impossible. Root owns acceptance.

Source stock is DEMO_095:04 (SKU DEMO_095), slot SMALL_W:005:L2:B1, whole24units/.94kg/.32×.24×.24m. World bottom [17.7,1,42.62],yaw3π/2; P02 [17.14,0,42.62],yaw5π/2. Cargo stays worker-local [0,1,.56],yaw−π,scale1. Root, torso, head, legs and source feet remain unchanged. No manual shoulder-lift, swivel, finger pivot or invented transform was introduced.

## Executed native evidence

The first trial reused only f33 arm angles, then checked the changed cargo pose and actual GLTFLoader faces. Its reference points are [±.16,1.08,.44], not the coarse [±.16,1.12,.44] targets. Fresh hierarchy forward checks agree with analytic wrists to1.15e−16m; reference error4.95e−12m. Original upper-arm Y, forearm Y and wrist Z are at limits in this first trial; no limit was widened.

Each side has a finite native pad patch clipped wholly inside the .4712m grasp radius: area sum7.808029819e-5m² (about78.08mm²), maximum radius.4711990594m, opposed normal dot−1, maximum native pad gap6.257461e-9m (<2µm). These are summed triangle-overlap subpatches, not a force/stability proxy. Full overlap also contains points beyond the grasp radius; only the recorded clipped subpatches support the finite-budget claim. The20µm cargo-shift control gives20µm native gaps on both sides.

Initial native checks: both C-mouths clear (88 forearm triangles each); no body triangle inside the HU envelope shrunk2µm; no shared body/HU interior witness; no changed nonadjacent self-collision witness. The25 original/unchanged join observations are retained, not declared zero self-intersection. Both original soles remain atY1.49e−8m. Actual geometry:23 worker meshes/2848 triangles,4 cargo meshes/796 triangles.

Adding the SHA-matched original rack-small GLB at its actual module transform (world [18,0,43.5],yaw3π/2) rejects this candidate. Example right-forearm/post witness in worker frame: [0.291754628799311,1.0545821870914234,0.38245231250440276]; shared interior depths.00025m in forearm and.0124523220m in rack, solid angles≈4π in each. Hand/rack witnesses also exist. This is native shared-interior evidence, not just intersecting AABBs.

The subsequent fixed-root search executed168 target/orientation trials,336 side solves and34654 LM iterations: Y∈{1.12,1.16,1.20,1.08,1.04,1.02},Z∈{.44,.442,.438,.435},tangent∈{−1.4,−1.2,−1.6,−1,−1.8,−.8,−2}. Both sides converged in83;69 passed candidate contact checks;61 passed mouth/anatomy/HU checks and reached native rack testing. All61 had rack witnesses; none reached final rack-clear/self validation. Best weighted solve residual anywhere was2.672924e-15. The representative lowest-ranked rejected candidate (Y1.08,Z0.435,tangent-1.8) has no active joint bounds and residuals≈2.08e−14, yet four rack witness pairs remain. Its right forearm/post shared-interior depths are.00025m and.00218201857m at [0.29535710000135645,.9910287617575855,.37218200903325055]. Full coordinates, limits and witnesses are in findings.json and native-results-with-rack.json. The coarse-point reach margin alone therefore does not establish an actual source grip.

## Inferences and boundaries

This is local STOCK feasibility only. No canonical order requests DEMO_095; nothing fulfills DEMO_067 or admits a new order/source pickup. Directly applying the f33 cargo transform would shift the actual source4cm horizontally,4cm vertically and rotateπ. This probe retained the original source pose throughout.

Yaw-preserving withdrawal needs at least.32m root retreat along existing segment002:r (world−X):17.7−retreat+.12≤17.5. At exactly.32m the ideal HU only touches the rack-front clear plane; positive clearance needs more and native checking. No withdrawal pose or motion trace was executed because no rack-clear endpoint passed. No lower-stock crouch was attempted. C01 parked [16,0,44.38] still blocks P02’s canonical exit; no global approach/departure clearance is claimed.

The finite single-seed search is incomplete across native IK branches. Static CPU doubles do not validate shared-stock Float32 rendering (including old origin72 precision); Support’s dynamic render binding is outside this work. No force, strength, full continuous collision or runtime Scene certificate is claimed.

## Reproduction and integrity

Run probe.mjs, validate.mjs, search-rack.mjs, then finalize.mjs with Node from the canonical root. The first validator attempt stopped on an incorrect module-field name; it was corrected to world_pos and rerun successfully. The generated probe-with-rack.mjs and exact AST-extracted frozen helper source are retained. No production solver writer ran. The22 frozen inputs and10 additional inspected/helper sources have matching before/after SHA256. The declared HEAD was supplied by the user; no Git command verified it. All writes are in this audit folder. No production/model/Scene/contract/backend/fixture/order edit, browser, Blender, build, install, server, auth/config or graph/memory mutation occurred.
