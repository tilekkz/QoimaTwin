# Seven-point loaded-walk hip diagnosis

Read-only CPU / Three.js native-geometry diagnosis. Production code, accepted reports, model geometry, source limits, probes and tolerances were not changed. Seven exact saved witness frames were replayed from the SHA-bound trace; this is not a new route acceptance or continuous-geometry certificate.

All seven points are inside both the posed native trouser-thigh and shirt solids, but outside the unchanged closed native `pelvis_cloth`. They are also outside the unchanged source-rest thigh volume. They therefore do not qualify for the existing point-local pelvis articulation-closure rule. No additional hip/cap volume exists among the 23 source mesh batches. Do not replace this test with the pelvis AABB: three points fall in its rotated world AABB while their whole-solid winding is approximately zero.

The original thigh source bounds reach actor Y=0.620300645 m, while the shirt begins at Y=0.639999986 m. The saved overlap points are at actor Y≈0.640005–0.640088 m, 19.704–19.787 mm above the original thigh maximum. Their nearest unchanged source-rest thigh surfaces are 20.630–21.802 mm away; these are rounded/oblique proximal surfaces, not a separate planar hip cap.

| t (s) | side | actor-local point (m) | pelvis-joint-local point (m) | thigh-joint-local point (m) | thigh / shirt depth (µm) | outside pelvis (mm) | nearest rest thigh (mm) |
|---:|:---:|---|---|---|---:|---:|---:|
| 0.609753 | L | [-0.179531753, 0.640004691, 0.075933124] | [-0.179531753, 0.020004686, 0.080933124] | [-0.084531754, 0.013270389, 0.091648715] | 4.705 / 4.705 | 4.532 | 21.799 |
| 1.059658 | R | [0.175515944, 0.640088019, 0.076925342] | [0.175515944, 0.020088014, 0.081925342] | [0.080515945, 0.021238592, 0.091069264] | 41.249 / 88.033 | 0.516 | 20.630 |
| 6.928333 | L | [-0.175817431, 0.640087814, 0.076868531] | [-0.175817431, 0.020087809, 0.081868531] | [-0.080817432, 0.020962017, 0.091082153] | 41.609 / 87.829 | 0.817 | 20.699 |
| 7.568333 | L | [-0.175817431, 0.640087814, 0.076868531] | [-0.175817431, 0.020087809, 0.081868531] | [-0.080817432, 0.020962017, 0.091082153] | 41.609 / 87.829 | 0.817 | 20.699 |
| 8.208333 | L | [-0.175817431, 0.640087814, 0.076868531] | [-0.175817431, 0.020087809, 0.081868531] | [-0.080817432, 0.020962017, 0.091082153] | 41.609 / 87.829 | 0.817 | 20.699 |
| 9.590536 | L | [-0.179535286, 0.640004683, 0.075909588] | [-0.179535286, 0.020004679, 0.080909588] | [-0.084535287, 0.012962628, 0.091671973] | 4.698 / 4.698 | 4.535 | 21.802 |
| 10.044683 | R | [0.175568344, 0.640087983, 0.076915404] | [0.175568344, 0.020087978, 0.081915404] | [0.080568345, 0.021190522, 0.091071504] | 41.311 / 87.998 | 0.568 | 20.642 |

Exact coordinates, nearest source-native triangle indices/points/normals, torso-local coordinates, original joint angles and all seven input frames are retained in `diagnosis.json` and `seven-input-frames.json`. Both thigh batches and shirt have the common direct pelvis parent through `joint__thigh_L/R` and `joint__torso`; this ancestry alone does not cover an external point.

The thigh local native bounds are L X=[−0.095353891,0.085353886], R X=[−0.085353886,0.095353891], both Y=[−0.255300695,0.025300617], Z=[−0.100484727,0.110484727] m. Hip joints are at actor [±0.094999999,0.595000029,−0.0049999999] m. Native pelvis actor bounds are X=[−0.174999997,0.174999997], Y=[0.550000004,0.690000005], Z=[−0.120000002,0.110000002] m.

Original source XYZ joint limits (radians):

| joint | X | Y | Z |
|---|---|---|---|
| thigh / hip | [−1.75,0.65] | [−0.2,0.2] | [−0.35,0.35] |
| shin / knee | [−0.08,2.35] | [−0.08,0.08] | [−0.08,0.08] |
| foot | [−0.4,0.4] | [−0.2,0.2] | [−0.15,0.15] |

The exact old W05.2 centroid-offset witness function returns no witness on all seven replayed frames; the exact current W05.3.3 edge/triangle function reproduces all seven. Both published input manifests pin the same gait source SHA 1909f2fcb42fad2de4776c98e2632f49609355669b0c25274227cbee184b79b3. W05.2 described its centroid sampling and did not claim exhaustive continuous absence of intersections. This is a narrower probe-method/sample-coverage gap, not a pelvis-classification-range exemption. Restoring the carry arms to their source pose leaves the thigh/shirt matrices exactly unchanged in all seven frames, so these witnesses are driven by leg gait, not the loaded arm pose.

Current IK uses hip X only and knee X/Y/Z, placing lateral correction in knee Z. A local alternative assigned lateral correction to hip Z with knee Z=0, retaining the original knee Y and targeting both original complete foot world matrices. All seven frames solved within source XYZ limits (maximum IK position error 1.109139e-11 m; maximum foot-world-matrix element change 1.098871e-11). Nevertheless, every frame still has a native thigh/shirt material witness; the three turn frames only reduce the reported depths to about 38.23 / 86.02 µm. Four straight frames have no original lateral knee correction, so hip-Z relocation alone cannot fix the root cause.

A minimal kinematic direction is to reduce required forward hip flexion using shorter foot advances and/or a lower swing trajectory, and use source-bounded hip lateral motion for stepped turns. The unchanged native vertex envelope gives a useful sufficient bound for the sagittal case: at hip Y=Z=0, hip X≥-0.225425242340 rad keeps the entire native thigh at least 2 µm below the shirt lower Y. Current implicated hip X is about −0.274 to −0.367 rad. This geometric envelope is not a new source joint limit or an accepted gait constraint; with hip Y/Z nonzero it must be recomputed. Merely moving the whole actor/pelvis vertically leaves relative thigh/shirt geometry unchanged unless IK/joint motion changes.

Any proposed fix still needs the unchanged full-body edge/triangle and whole-solid probes, source-limit checks, exact original endpoints, actual stance/swing foot proof, other foot/self pairs and fixed-obstacle gate. Neither the seven-frame hypothetical IK nor the Y-envelope accepts a route, certifies dynamic stability or justifies deleting probes/expanding the closure volume.

Graph context: parent Verify evidence used qoima-twin generation 2026-11-08T05:55:56Z, relevant V3 sources untracked. This continuation attempted index_status and exact-path check_index_coverage; both returned Transport closed. Exact source/AST extraction and SHA pins supply the bounded evidence; no fresh graph completeness claim.

Source SHA pins and source snapshots are in `provenance.json`; `source-inputs/*.txt` are byte-exact copies from the diagnosis epoch. The original full reports and trace remain unchanged, and their hashes are recorded even though only the seven required frame inputs are copied here.
