# Carry gait naturalness: exact trace review and one stance adapter

The accepted carry motion has genuine hip/knee/ankle articulation and no sampled geometric knee backbend. Its main naturalness weaknesses are the very rapid, low-clearance flat-foot steps and the absence of positive-duration support transfer. My artistic inference from the kinematics is that it reads as a hurried shuffle with a rigid upper body; a collision/contact pass does not resolve those timing and stance qualities. This is a source/kinematic review, not a new rendered visual review or a human normative gait comparison.

Production, original gait, static carry pose, models, source joint limits, accepted reports and raw trace were read-only. Only this `work/v3/posture-naturalness` directory was written. No browser, Blender, build, Git, full native collision gate or engine-clock change was used. The Karpathy guidelines informed the bounded, surgical scratch implementation.

## Exact accepted-motion measurements

Recompiling the exact source rig and current loaded solver reproduces all 1,450 saved frames with **zero quaternion-component difference and zero root-component difference**. All eight carry-arm quaternions remain constant. Native sole FK error reproduces the accepted maximum **9.869424392e-12 m**. `accepted-six-leg-quaternions.csv` retains all 8,700 joint/frame rows with the exact saved quaternions, XYZ Euler interpretation, stance role and geometric knee bend. `measurements.json` also contains quaternion-component ranges, stage ranges, stance/swing ranges and every support interval.

| Portion | Interval (s) | Footfalls | Cruise interval per alternating footfall | Cruise footfalls/s | Same-foot cycle |
|---|---:|---:|---:|---:|---:|
| 4.75 m first leg | 0.350–5.808333 | 23 | 0.179924 s | 5.557895 | 0.359848 s |
| Stepped 90° turn | 5.808333–9.328333 | 11 | 0.320000 s | 3.125000 | 0.640000 s |
| 11 m second leg | 9.328333–19.995000 | 51 | 0.183333 s | 5.454545 | 0.366667 s |

The 0.35 s prepare and 0.35 s settle make the total **20.345 s**. Whole-leg average rates, including acceleration/deceleration, are 4.213740 and 4.781250 footfalls/s. There is no retreat. Exact phase times, root advances and foot travel are in `phase-timing.csv`.

The source upper/lower leg lengths are 0.230434391 and 0.225444000 m, totaling 0.455878392 m. The two root advances are 0.215909091 and 0.220000000 m per footfall; the same foot travels 0.431818182 and 0.440000000 m per interior swing. Swing clearance is only **18 mm**, or 3.95% of that two-segment chain. The quintic swing peaks at **4.5 m/s** horizontal foot velocity in both cruises (about 9.87 leg-chain lengths/s). Its analytic horizontal acceleration peak is 77.01 / 75.58 m/s². These are timing derivatives, not measured forces. The mismatch between that fast repositioning and the low lift is the basis of the shuffle judgment.

Actual accepted XYZ local joint-angle ranges, degrees:

| Joint | X | Y | Z |
|---|---:|---:|---:|
| Hip L | −20.9772 … 17.4570 | 0 … 5.1566 | −1.6403 … 1.1869 |
| Knee L | −0.3215 … 28.1306 | 0 … 4.5000 | 0 |
| Ankle L | −21.2752 … 17.2342 | −5.2749 … 9.3841 | −1.5500 … 1.6421 |
| Hip R | −20.0751 … 17.9444 | −5.1566 … 0 | −1.2029 … 1.6381 |
| Knee R | −1.3763 … 28.1306 | 0 … 4.5000 | 0 |
| Ankle R | −20.1887 … 16.9859 | 0 … 10.9650 | −1.9909 … 1.5916 |

Negative knee X is **not an anatomical backbend in this rig**. The unchanged source shin/ankle translations already form a +0.087866106 rad (**5.034357°**) sagittal knee bend at zero joint rotation. Measuring the angle between the actual upper/lower segment directions, in the thigh frame, gives accepted signed forward bend **L 4.712899–33.164919°, R 3.658079–33.164919°**. Only five L and seven R saved samples have negative knee joint X, all at the initial acceleration. A uniform 20,000-time-bin integration estimates about 0.0610 / 0.2085 s with negative joint X and zero time with geometric backbend. A separate 101-samples-per-phase source study reaches R knee joint X −0.030575297 rad, while geometric bend remains positive at 3.282522°. Do not clamp knee X to zero: that would alter valid native IK without fixing the actual naturalness issue.

The local ankles articulate substantially, but they compensate the leg chain to keep **every complete foot horizontal in world space** during both stance and swing. There is no heel strike, toe-off roll or foot pitch arc. Hip Y is the carry solver's mirrored yaw bias; hip Z is small lateral joint correction. Neither creates lateral root weight transfer.

The accepted root moves vertically from 0 to −18.277298 mm; the separate 101-samples-per-phase study reaches −18.502691 mm. The horizontal root has **zero lateral sway**. Each of the 85 open step intervals has exactly one planted foot; both are planted only at instantaneous boundaries. Thus moving/turning single support totals **19.645 s**, with **zero finite double support** inside those steps. The only positive-duration double support is prepare + settle = **0.700 s**. Cruise stance duty for each foot is 50% of its same-foot cycle.

The native sole contact rectangle is 184 × 284 mm. Straight stance centers are ±115 mm from the route center, and turn stance centers ±128 mm. The root's vertical projection consequently sits about **23 mm outside the straight stance sole**, reaching **36 mm** in the turn; there is no root shift toward the supporting foot. That projection is **not a center-of-mass measurement** and does not establish a balance failure. It does precisely identify the missing visible support transfer.

## One carry-only scratch candidate

The recommendation is the **actual-target stance adapter implemented at `analyze.mjs:113`**, as a next animation task. It calls the unchanged native gait compiler at an explicit **0.70 m/s carry-calibration / geometry-artistic style cap**, leaves the canonical worker profile at 1.2 m/s, and changes only the carry's foot timing and the required leg solve. There is no global engine-clock rescaling or lateral root offset.

During each source step, keep the swinging foot planted at `feet_from` for the first **6%** of phase time, run the existing quintic position/yaw interpolation and `18 mm × sin²(πv)` lift over the middle **88%**, then keep it planted at `feet_to` for the final **6%**. The horizontal root and root heading continue through these windows on the compiled 0.70 m/s profile. Recompute the source reach-based body drop from **those actual changed targets**, then apply the existing loaded native hip X/Y/Z + knee X/twist solver and compensating foot quaternion. The original pure foot targets are explicitly changed; this is not scalar pose decoration or a claim of unchanged accepted geometry.

The originally requested 8% / 84% / 8% window was rejected by the unchanged source ankle limit at six sampled times. Worst observed L ankle X was −0.404729939 rad versus the original −0.4 limit, at 12.381964235 s. `rejected-8pct-boundary.json` retains that boundary. Shortening only the end windows to 6% passes; no joint value was clamped and no source limit, tolerance, model or pelvis rule was changed.

| Quantity | Accepted | Scratch candidate |
|---|---:|---:|
| Peak horizontal carry speed | 1.20 m/s | **0.70 m/s explicit calibration cap** |
| Duration | 20.345 s | **28.470 s**, +8.125 s |
| Cruise footfalls/s, first / second | 5.557895 / 5.454545 | **3.242105 / 3.181818** |
| Cruise swing duration, first / second | 179.924 / 183.333 ms | **271.429 / 276.571 ms** |
| Finite double support per cruise transfer | 0 | **37.013 / 37.714 ms** |
| Root progress during that double support | 0 support interval | **25.909 / 26.400 mm** |
| Each foot's cruise stance duty | 50% | **56%** |
| Total double support, including prepare/settle | 0.700 s | **4.0324 s** |
| Peak horizontal swing velocity | 4.500 m/s | **2.982955 m/s** |

The turn keeps the original 0.32 s phases and gains 38.4 ms of double support per interior transfer; heading continues, with no root-position stop added at footfalls. Candidate preparation/settle remain 0.35 s each.

**Joint/FK feasibility: 87,351 samples pass**, using 1,000 subdivisions per phase plus both sides of support boundaries. Maximum reconstructed sole-target error is **1.000075e-11 m**; target foot orientation remains horizontal. Root X/Z and yaw match the 0.70 m/s compiled profile exactly. Changed feet differ by up to **15.151057 mm** from its original pure targets; recomputed body drop differs by up to **6.465338 mm**, with a maximum drop of **22.369278 mm**. Signed geometric knees stay forward: **L ≥4.513174°, R ≥3.274372°**. All six native XYZ joint ranges pass. The narrowest sampled original-limit margin is **0.000750104 rad**, from shin Y twist during turns (maximum 0.079249896 vs 0.08 rad); final L ankle X minimum is −0.396107920 rad.

Across ±10 ns at phase boundaries, the maximum root displacement is 1.400001e-8 m, foot-target displacement is zero, and joint quaternion angle difference is 3.24e-7 rad. This is consistent with continuous root travel and planted footfalls, not a freeze-and-jump root. The existing eight-arm static carry override and the common rigid root transform of hands/cargo are retained; no arm, cargo attachment or model change is proposed.

This candidate improves measured cadence and supplies genuine support-transfer time, but it still uses flat feet and no lateral weight shift. It is a **joint/kinematic-feasible scratch recommendation**, not native material/foreign-collision acceptance, rendered approval or dynamic balance validation. Because its actual targets and poses change, the next integration must run the unchanged native gate and preserve the already accepted W05.3.3 evidence as a separate 20.345 s proof. A new controller must expose 28.470 s duration and the candidate's actual support times rather than retaining the old duration or labeling old pure targets as current.

## Reproduction and provenance

From the canonical repository, run `node work/v3/posture-naturalness/analyze.mjs`. It reads and SHA-verifies the exact native rig, source files, carry pose, accepted report and trace before work, reproduces the accepted frames, runs only FK/joint/timing calculations, then rechecks every pin. All generated modules, CSV and JSON remain under this owned scratch directory. No dependencies are installed. `timing-study.json` is the single final candidate result; `measurements.json` also includes all baseline evidence and the same result.

| Input | SHA-256 |
|---|---|
| `warehouseLoadedWalkCalibration.ts` | `0435b5e93d4d674ffc7b0f11c2b8c0af214380437cc2cce938dcef9a9586d2e8` |
| `warehouseWorkerGait.ts` | `1909f2fcb42fad2de4776c98e2632f49609355669b0c25274227cbee184b79b3` |
| Accepted `W05.3.3-checks.json` | `c2c56f4585305f4f5f7066c574914d6bc9e8b4b423d023491275b17024e2b118` |
| Accepted `replay-trace.json` | `29215652964588876a6f3af06da37d8c09111445ae8ccde15a0111708092379a` |
| Native `worker-base.glb` | `542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163` |
| Frozen carry pose | `f33bdb63db8fc78af68af173926a0a59267eda9f83b484a98e71ec4f375bac7b` |

Graph Verify context: qoima-twin ready generation 2026-11-08T05:55:56Z; bounded exact-symbol query returned 0, `has_more:false`. Coverage of the two exact sources and report recorded no issue but marked freshness `not_tracked`. Full direct source fallback and exact hashes supply this bounded evidence. No reindex or graph completeness/freshness claim was made.
