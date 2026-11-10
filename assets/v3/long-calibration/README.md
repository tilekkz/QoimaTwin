# Portable LONG calibration asset generator

This is a proposed canonical build stage for the reviewed cap correction, front 240 / rear 168 tyre refinement, and two native exterior apron slabs. Generated assets remain unaccepted. Canonical promotion belongs to root; this stage adds no loader registration, calibration API, warehouse scene, source action, workflow permission or W12 acceptance.

Run from a fresh checkout after these staged files have been promoted into their matching repository paths. Use the checkout's existing `frontend/node_modules` containing Three 0.169.0 and Khronos gltf-validator 2.0.0-dev.3.10. No install, Blender, browser or renderer is involved. The successful verification used Node 24.19.0; the repository declares Node >=22.12.0.

```powershell
node tools/visual/v3/build_long_calibration_assets.mjs --out ./local-long-assets
node tools/visual/v3/build_long_calibration_assets.mjs --out ./local-long-assets --check-only
```

The script locates the repository and data relative to its own location, so the current directory may differ. `--out` is mandatory and resolves relative to the current directory. `--source-root C:/path/to/checkout` explicitly selects another source checkout and its existing frontend dependencies. During stage review, invoke the staged script with this flag pointing to the canonical checkout and use a new authorized output directory.

The only authoritative runtime inputs are:

| Input | SHA256 |
| --- | --- |
| `frontend/public/models/v3/forklift-loaded-long-bundle.glb` | `f7f320796cb0b85c45f52cb06e4cf617043e70c686516944fe2fc7f0582b1c60` |
| `frontend/public/models/v3/environment-shell.glb` | `2580e0988d5d25d07dd90a9ffe9452130f555ccb0954d3ee07db0018fa796f70` |

The generated products are:

| Product | Bytes | SHA256 |
| --- | ---: | --- |
| `forklift-loaded-long-bundle.calibrated.glb` | 1547892 | `27bb0fee20fb673de4aeb8f094cf8d77862ab1013df514babbfd5fa9c3d2a77d` |
| `optional-long-approach-floor.glb` | 4084 | `b3f3c7348ca40c37b63179c85fe424e50920623d063c31fcecb3662805dcb6ce` |
| `long-calibration-build.json` | deterministic report | Generator/data/source pins, exact cap float deltas, profiles, preserved invariants and validator issues |

## Native generation and exact serialization

The cap routine uses the original POSITION/NORMAL accessors and index graph. It retains original vertex splits, lowers the underside rim to a 14.2 mm radius, places its seat at the reviewed binary32 plane, starts the full 16 mm cap radius at the reviewed higher chamfer station, and recomputes area-weighted normals only on affected original graph vertices. The original 8 mm shaft, cap top, joints and other geometry remain. The intermediate GLB must equal the corrected `ffa995ce5d4ca666393e558f2661e1cddde4dc0623b8b57461a873b5caa4cf5e` epoch exactly. The report includes all 2609 changed float words with original/replacement bits, decoded values, accessor IDs and BIN offsets. Reversing them must restore the complete canonical source GLB.

The tyre routine derives six axial/radial stations from the actual original 24-station native mesh. It copies every original angular station exactly, inserts 240 front / 168 rear angular stations, constrains Float32 positions to each original ring's maximum radius, preserves the annular hole and bevel profile, and generates flat quad normals and native triangle indices. The 528768 appended bytes must match their expected per-view and aggregate hashes. Original accessors and buffer views remain in place; only the four tyre primitive references and radial-segment metadata change.

`tyre-json-edits.json` is an explicit raw JSON edit recipe, with complete original/replacement strings and bounded source offsets. Keeping those original records avoids changing unrelated JSON formatting or metadata. `recipe.json` binds original and replacement native view records/hashes and output hashes. These are checks on analytic generation; they contain no appended tyre payload, whole source GLB or whole replacement GLB.

The apron is generated as two closed six-face boxes with the reviewed outward-rounded Float32 world bounds. `apron-document.json` retains the exact historical document metadata and number spelling, including its design digest. Its BIN is generated afresh; each view hash is checked. Concrete must exactly equal the pinned source environment's `V3_Shell_floor` material. The document is small explicit serialization data, not a Blender source file.

Meters, canonical Y-up / +Z-forward coordinates, all unit scales, original wheel X spin axes, distinct 0.300 m / 0.225 m radii, 4.2 / 0.52 / 0.65 m HU dimensions, 200 kg HU and 40 kg cradle are preserved. Generated outputs retain the reviewed bounds, materials and joint records. This is native analytic generation with exact serialization data. No binary patch is presented as parametric Blender source.

## Failure and publication behavior

Both canonical source SHA256 values are checked before geometry generation or output-directory creation, and rechecked immediately before publication. The generator anchors the recipe hash; the recipe pins the two serialization data files. All accessors, strides, buffer views, indices, JSON edits and append boundaries are checked against their expected records and bytes with safe-integer bounds.

Both GLBs are fully constructed, output-hash checked and validated by the installed Khronos validator before any destination write. Each must have zero errors and zero warnings. The model retains exactly nine `UNUSED_OBJECT` infos for original accessors 35, 36, 37, 42, 43, 54, 55, 60 and 61; the apron has zero infos. The report preserves that distinction.

All existing targets are compared before creating temporary files. Identical targets are skipped without mtime changes; a changed target rejects the complete batch. There is no force/overwrite option. Select a new explicit destination to build another batch. `--check-only` requires matching existing products and performs no writes or directory creation.

Publication creates temporary files only after validation and preflight, then uses exclusive hard-link creation. A competing destination cannot be overwritten; a handled publication failure rolls back only newly published links owned by this attempt. A power loss or process termination between links is not a multi-file filesystem transaction. Source files, existing changed targets and symlink output paths are never deliberately rewritten. A filesystem without hard-link support rejects publication; use a supported local destination.

## Evidence and remaining scope

The stage handoff's external checks record two deterministic fresh destinations, a checkout with no prototype directory, unchanged check-only mtimes, wrong source/environment SHA controls, corruption/overflow/expected-old controls, changed-target refusal, and an injected second-output validator failure with no partial publication. Native preservation checks compare the original/generated bounds, 104 transforms and unit scales, HU dimensions/masses and exact changed-byte allowlist. Prior cab, corridor, floor and rolling geometry proofs are inherited bounded evidence and are not rerun by this generator.

An editable inspection `.blend` is optional and was not executed for this stage because the new root release file was absent. Any later inspection must import these exact generated GLBs in an isolated factory background process after the required release and toolkit instructions. It must retain meter/canonical-axis provenance, verify `(x,y,z)` Y-up to `(x,-z,y)` Z-up mapping and label the file an inspection artifact. The native generator and exact GLBs remain authoritative; a Blender re-export is not a byte-exact source.
