# Natural carry preset: bounded independent review

No material source/math defect was found in the reviewed epoch. This is a code and source-native FK review, not final visual naturalness, force/balance acceptance or a repeated full native scan.

Current Loaded source SHA-256: `4427558f1214541cda0dd57e8455d835971478d8ec9014069e602d1b7612857b`. Current dual checker: `10291c6df9a4e9e7e84b9a3e8d441afa3fd5920649c246b5ce8004eeec5f1d1f`. Accepted old Loaded snapshot: `0435b5e93d4d674ffc7b0f11c2b8c0af214380437cc2cce938dcef9a9586d2e8`. The unchanged common gait remains `1909f2fcb42fad2de4776c98e2632f49609355669b0c25274227cbee184b79b3`.

Default compatibility is concrete: `motion_style` defaults to `source`, still compiles at the original 1.2 m/s source profile and runs the byte-identical accepted carry leg solver. All **1450 archived accepted `trace.frames` equal current baseline `trace.frames` exactly**, including root/joint/cargo matrices. Frame JSON SHA-256 is `98094c3107af79703e2de4e1aa275cd620426d74765dd1d5f828878a5de5bdd7`. The current trace file hash matches the current W05.3.3 report; only intentionally excluded schema/source metadata differs from the archived epoch. New motion metadata is additive.

For `grounded_carry`, the .7 m/s cap is explicitly separate from the unchanged P02 1.2 m/s source profile. The optional style does not edit profile bytes, the common gait, route, assets, accepted static arms, or cargo frame. It compiles a genuine slower trajectory with duration **28.47 s**, then changes the actual swing foot targets: first 6% hold the old footfall, middle 88% move the foot, final 6% hold the new footfall. Both the position blend and lift have zero first derivative at liftoff/landing; foot yaw follows the same shortened swing window. The opposite foot remains planted. It restores the original pelvis reference height, recomputes body drop for the changed feet using source reach geometry, then invokes the original hip solver with the original XYZ limits. It does not freeze complete frames or merely relabel stance flags while old feet move.

The exact helper was compared numerically with `candidateSample` at `work/v3/posture-naturalness/analyze.mjs:116–127`. In **1051 independently selected source-native FK samples** across phase/hold boundaries and interior support windows, the two implementations are exactly equal. The actual module's fixed bounds and the study's empty-bound route yield identical phases for this prescribed path. The existing 87351-sample study was read; it was not rerun or presented as this independent probe.

| Bounded independent observation | Result |
|---|---:|
| Maximum reconstructed sole-target error | 8.67144e-12 m |
| Maximum complete foot-orientation error | 2.25898e-16 rad |
| Minimum native boot bottom Y | +1.49011e-8 m |
| Minimum sampled original XYZ limit margin | .001305439 rad |
| Maximum recomputed root-Y change from the slower pure gait | .006458513 m |
| Held foot-target slip in both-support windows | exactly 0 |
| Translating both-planted windows / turning both-planted windows | 148 / 12 |

Root X/Z, heading, time and horizontal speed match the .7 m/s gait in every selected sample, including double support; source-native FK still reaches each planted foot. Thus slowing the preset does not add pauses between ordinary steps. The summed finite double-support duration is **4.0324 s**, including prepare/settle; single support is **24.4376 s**. Each foot's cruise stance fraction over a same-foot cycle is .56. These are the implemented 6/88/6 target timings, not a claim of a measured physiological gait or centre-of-mass transfer.

The archived and current checker have byte-identical definitions for all 12 critical geometry/conservation functions: components, geometry, winding, nearest, interior, witness, coveredByClosure, pelvisClosure, closedSolid, nativeGate, partNative and conservation. Original edge/triangle and whole-solid tests, point-local closed-pelvis rule and 2 µm guards remain. The new mode adds both support-window endpoints to native sampling and includes extra nearby contact/FK samples; the old default sampling remains. The actual `observe` contact/ground guards are unchanged except added motion metadata. `live`, native triangle extraction, cargo delta, rollback helpers, reset and disposal remain unchanged.

Both existing proof reports bind the current source epoch. All **85 shared input pins** were checked with zero mismatches. W05.3.3 records 1450 contact frames / 176 body frames; W05.3.7 records 2135 / 346; both have zero material witnesses and zero contact refusals. These are root's existing completed native runs, not newly executed collision results from this review. No input drift occurred during the independent probe.

Force, lateral centre-of-mass/weight transfer, heel-toe articulation, dynamic stability and final character naturalness remain unproven. The code's `lateral_root_transfer:false` and `force_balance_certified:false`, and the proof's `final_naturalness_certificate:false`, reflect those limits honestly. Whole soles remain flat; the bounded refinement should not be described as the final natural human gait.

Evidence and reproduction: run `node work/v3/natural-carry-review/probe.mjs` from the canonical repo. It writes only this owned scratch scope, extracts current exact helpers and compares the preserved traces; it does not run the full native gate or load a renderer. `checks.json` SHA-256: `805ba4338c432aaf588413a347e97f5f6f3e4ce7ae82a45bcbe967842a522958`; probe SHA-256: `102a3c0d117afa1c467257535dcb6b35a493799cc3d6670f2cc3bf17a8b64c55`.

Graph context: supplied Tier 2 qoima-twin generation 2026-11-08T05:55:56Z, relevant V3 paths not_tracked and no relevant new-symbol matches. One exact-path coverage call for the current/archived helpers, checker, study and probe returned Transport closed. Exact source and SHA-bound archived artifacts supply the bounded review; no reindex or current graph-completeness claim. Production source, task state, Git, browser, Blender and builds were untouched.
