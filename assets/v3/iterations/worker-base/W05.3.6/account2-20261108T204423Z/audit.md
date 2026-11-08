# Original-source bounded torso grip endpoint

No rack-clear two-hand endpoint was established. 103 new trials / 206 arm-side solves / 5789 LM iterations completed; all 103 converged, 83 reached native rack checks, and none was rack clear. No candidatepose.json was written. This bounded result does not prove impossibility.

Whole HU DEMO_095:04 remains 24 units / .94 kg / .32 × .24 × .24 m, scale 1. Frozen cargo world bottom [17.7,1,42.62], yaw 3π/2; P02 root [17.14,0,42.62], yaw 5π/2; worker-local cargo bottom [0,1,.56], yaw −π. Rack-small module SMALL_W:005 remains at [18,0,43.5], yaw 3π/2. Pelvis, legs, feet, root and all local translations/scales/native geometry remain at source rest. Head local Euler stays [0,0,0] and follows the original torso hierarchy. No manual-only pivots or bounds/epsilon/contact-budget changes.

Initial torso pitches were −.06,+.06,−.10,+.10,−.14,+.14 rad, with original torso limits [[-0.25,1.2],[-0.6,0.6],[-0.15,0.15]]. Two pitch refinements −.12 and −.08 followed. The first 26 contact refinements used Y 1.07–1.09, Z .433–.437, tangent −1.9 to −1.7, at pitch −.10. The final 69 distinct contact refinements used pitch −.06, Y {1.08,1.10}, Z {.429,.431,.433,.435,.437,.439,.441}, tangent {−1.76,−1.78,−1.80,−1.82,−1.84}; the already executed exact duplicate was skipped. No original fixed-torso IK trials were repeated. A single stored pose was reapplied as a collision control.

Targets and desired hand orientation were transformed through each actual moved upper-arm parent's inverse matrix/quaternion. Analytic shoulders use native parent-local translations. Fresh GLTFLoader validation compares the transformed analytic wrists and hand references against the actual original native chain. Maximum representative wrist discrepancy 2.482534153247273e-16 m; reference-target error 7.795559684776535e-12 m.

Representative rejection is trial 51: torso [-0.06,0,0], Y 1.08, Z 0.435, tangent -1.78. Selection ranks rack-pair witness count and largest recorded rack-side depth, not global feasibility. All eight original arm joints are listed exactly below (radians, XYZ); both upper-arm Y axes are at their original limits (+.55 and −.55 rad); all remaining arm axes are within their original bounds.

| Original joint | Euler XYZ rad |
|---|---|
| joint__torso | [-0.06,0,0] |
| joint__upper_arm_L | [-0.6497083437339597,0.55,-0.11070668657091032] |
| joint__forearm_L | [-1.055546941404688,-0.07343854875493862,-0.001791810911732871] |
| joint__palm_roll_L | [0,1.2330259693075505,0] |
| joint__hand_L | [0.4191810359597772,0.027716942406032497,-0.07756004645223842] |
| joint__upper_arm_R | [-0.6497084211856679,-0.55,0.1107059634476885] |
| joint__forearm_R | [-1.055547297093358,0.07343915134706519,0.0017927838380999738] |
| joint__palm_roll_R | [0,-1.233026160121444,0] |
| joint__hand_R | [0.4191805850596196,-0.02771809894131696,0.07755993262336479] |

Both finite opposed native subpatches pass: area sums 0.000023589791246973646 and 0.000023589791246974554 m². Every polygon vertex stays inside .4712 m horizontal radius and 1.25 m height, and native gaps stay below 2 µm. C-mouth, anatomy, whole-HU envelope and native body/HU checks pass for this rejected pose. All nine other source-module stock HUs were tested against the actual unchanged small-carton meshes, with no body/stock witness. Soles remain at original Y 1.4901161193847656e-8 m and exact original world matrices.

Native acceptance still refuses this pose: 3 rack witnesses and 5 new body witnesses. Full whole-mesh solid angles/depths, source triangles, source parts and edge-triangle probe counts remain in probe-results.json and independent-validation.json. AABBs only prune.

| Bone | Native mesh pair | Worker-local witness m | Shared-interior depths m |
|---|---|---|---|
| joint__hand_L | worker-base__batch_12 / rack-small__batch_00 | [-0.16281099484247533,1.0262473212005974,0.3945934063207003] | [0.0002499999999998386,0.004593414441833699] |
| joint__hand_R | worker-base__batch_15 / rack-small__batch_00 | [0.1628109948424756,1.0262473212005974,0.39459340632070045] | [0.0002499999999996866,0.004593414441833865] |
| joint__hand_R | worker-base__batch_15 / rack-small__batch_02 | [0.2471889965282548,1.037021381935941,0.44534024063602057] | [0.00024999999999999355,0.004659792742579938] |
| joint__forearm_L / joint__torso | worker-base__batch_11 / worker-base__batch_06 | [-0.1982202586794416,1.033241629530673,0.08803448946321484] | [0.0002499999999999901,0.0017797443007906422] |
| joint__forearm_L / joint__torso | worker-base__batch_11 / worker-base__batch_20 | [-0.20996289484505964,0.9814128456033859,0.10556569995334814] | [0.00019627967652890968,0.00003709859842943031] |
| joint__upper_arm_L / joint__torso | worker-base__batch_13 / worker-base__batch_17 | [-0.1474232209587904,1.0401028951702302,0.11694963386344637] | [0.0001598647973678758,0.00025000000000000846] |
| joint__forearm_R / joint__torso | worker-base__batch_14 / worker-base__batch_06 | [0.1982201892794539,1.0332416541718996,0.08803449548407433] | [0.0002500000000000013,0.0017798137007783432] |
| joint__forearm_R / joint__torso | worker-base__batch_14 / worker-base__batch_20 | [0.20805727925778647,0.9863305428154275,0.10422166856710864] | [0.00024999999999996314,0.0006937503434449405] |

The torso hypothesis is only partly supported: negative pitches remove the old right-forearm/post witness at unchanged hand targets. They retain three hand/rack witnesses and introduce other body witnesses. Full checks for initial pitches (pitch, rack witnesses, new body witnesses): [-0.06,3,5]; [0.06,5,4]; [-0.1,3,3]; [0.1,5,4]; [-0.14,3,2]; [0.14,5,4]. Original adjacent and unchanged model joins are retained explicitly (25 observations in the representative); none of the new body witnesses is waived.

Controls: native 20 µm cargo shift produces [{"side":"L","gap_m":0.000019999999999992246},{"side":"R","gap_m":0.000019999999999992246}]. The first validator sampled a contact-border vertex and failed its control assertion; interior-polygon centroids corrected the measurement, without changing threshold or accepting that failure. Raw corner gaps are recorded. An intentionally moved HU/head positive collision control is detected; cargo TRS restores exactly. Reapplying the stored fixed-torso rejection reproduces all four rack pairs and the right-forearm/post depth .002182018569994282 m at [0.29535710000135645,0.9910287617575855,0.37218200903325055].

Source SHA256:

| Input | SHA256 |
|---|---|
| worker-base.glb | 542591db818c349e60cb33006415a865347bd9e57ef0d128a36aaf0a34b0f163 |
| small-carton.glb | 10ae707579214c6ef87bf1897a04c35c59c913ca6093d5e511f8515c9354f317 |
| rack-small.glb | c7e80d1c799fd51ff25592b72defdd48724775934cd12f41f1a901ce130da4e7 |
| frozen original solver helper source | 5ba9e5ec5856ee8dccd5788223152582feda9e893614d41d2861be70baf6150d |

All 37 source inputs/helper/evidence files have matching captured/current SHA256; complete paths and hashes are in findings.json and search/validation hash snapshots. Original helper functions are AST-extracted without importing or running the production solver writer.

Run from the canonical repository root: node work/v3/account2-source-torso-grip/20261108T204423Z/solve.mjs, then solve.mjs --refine, validate.mjs, finalize.mjs (same directory prefix for each). Builders regenerate the standalone executable solver/validator from the frozen prior probe plus the retained scratch tails. Search saved progressive probe-results.json after every trial and ended 2026-11-08T20:48:31.706Z, before nine minutes from the first observed task clock 20:44:36 UTC. The recorded started_at timestamp in probe-results is the final resumed batch's start, not the first batch.

Every write is confined to this owned directory. No production/historical evidence, Git, browser, Blender, build, install, auth/config, model, graph index or memory mutation. No MCP access or freshness claim. No canonical order requests DEMO_095; no pickup, withdrawal, order fulfilment, loaded gait, route or Scene claim. The seven carry hip witnesses and C01 exit blockage remain separate root-owned work. Root owns acceptance.
