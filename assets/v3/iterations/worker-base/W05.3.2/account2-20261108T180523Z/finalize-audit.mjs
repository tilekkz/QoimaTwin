// Assemble portable W05.3.2 artifacts and take the final 21-input snapshot.
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const output = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(output, '../../../..');
const readJson = async p => JSON.parse((await readFile(p, 'utf8')).replace(/^\uFEFF/, ''));
const save = (name, data) => writeFile(path.join(output, name), JSON.stringify(data, null, 2) + '\n');
const before = await readJson(path.join(output, 'source-hashes-before.json'));
const check = await readJson(path.join(output, 'check-only-result.json'));
const native = await readJson(path.join(output, 'native-probe-result.json'));
const result = JSON.parse(check.stdout);
assert.equal(check.exit_code, 0);
assert.equal(result.check_only, true);
assert.equal(before.input_count, 21);
const inputs = [];
for (const prior of before.inputs) {
  const bytes = await readFile(path.join(repo, prior.path));
  const hash = createHash('sha256').update(bytes).digest('hex');
  inputs.push({ path: prior.path, sha256: hash, declared_sha256: prior.declared_sha256,
    matches_declared: prior.declared_sha256 === null ? null : hash === prior.declared_sha256,
    bytes: bytes.length, unchanged_since_before: hash === prior.sha256 });
}
const after = { schema_id: before.schema_id, phase: 'after', captured_at_utc: new Date().toISOString(), algorithm: 'sha256',
  input_count: inputs.length, unchanged_input_count: inputs.filter(i => i.unchanged_since_before).length,
  all_inputs_unchanged: inputs.every(i => i.unchanged_since_before), inputs };
await save('source-hashes-after.json', after);
assert(after.all_inputs_unchanged, 'Concurrent source drift detected; report must be revised');
assert.equal(inputs.filter(i => i.matches_declared === true).length, 20);

const finding = {
  id: 'W05.3.2-F01', severity: 'low',
  title: 'Sparse JavaScript joint arrays bypass omitted-axis validation',
  scope: 'Internal in-memory validatePose guard; frozen generated JSON candidate is unaffected',
  evidence_kind: 'executed_counterexample_against_extracted_exact_validator',
  source_witnesses: [
    { path: 'frontend/tools/solve-worker-base-carry-v3.mjs', line: 20, observation: 'vec requires length3 but v.every(finite) skips sparse holes' },
    { path: 'frontend/tools/solve-worker-base-carry-v3.mjs', line: 71, observation: 'joint range a.every also skips holes, so validatePose accepts omitted axes in sparse arrays' },
    { path: 'frontend/tools/solve-worker-base-carry-v3.mjs', line: 15, observation: 'q spreads axes into the Three Euler constructor' },
    { path: 'frontend/tools/solve-worker-base-carry-v3.mjs', line: 73, observation: 'apply invokes this validator before q; production apply itself was not invoked by the custom probe' },
    { path: 'frontend/node_modules/three/build/three.module.js', line: 6833, observation: 'undefined Euler constructor coordinates default to0' },
    { path: 'docs/adaptive-v3/specs/W05.3.1.md', line: 13, observation: 'Broad omitted-axis rejection claim exceeds this in-memory guard behavior' }
  ],
  reproduction: {
    command: 'node work/v3/account2-base-carry-audit/20261108T180523Z/probe-native.mjs',
    probe_source: 'probe-native.mjs', probe_source_lines: [34, 59, 60, 63], result: 'native-probe-result.json',
    cases: ['delete request.jointEulerXYZ.joint__upper_arm_L[1]', 'request.jointEulerXYZ.joint__upper_arm_L = new Array(3)'],
    observed: 'Both validate successfully; spreading the first array into the real Three Euler constructor suppliesY=0 instead of the frozen .55rad'
  },
  impact: 'The unconditional omitted-axis guard claim is too broad for JavaScript callers. This does not demonstrate an invalid frozen pose or a check-only acceptance bypass.',
  limitations: ['Sparse holes serialize to null and then fail validation.', 'The only current caller constructs dense finite arrays internally.', 'No counterexample against the saved candidate or full production apply was executed.'],
  suggested_followup: 'Root may require all three indices to exist and validate them explicitly, or narrow the guard claim to dense JSON arrays. No production change made.'
};
await save('findings.json', { schema_id: 'qoima.W05.3.2.findings.v1', audit_complete: true, finding_count: 1,
  severity_counts: { critical: 0, high: 0, medium: 0, low: 1 }, findings: [finding],
  frozen_candidate_failure_demonstrated: false, unresolved_material_candidate_concerns: [] });

await save('probe-results.json', {
  schema_id: 'qoima.W05.3.2.probe-results.v1', audit_complete: true,
  scope: 'Read-only correctness audit of the frozen static local P02 worker-base whole-HU candidate',
  graph: { evidence_kind: 'root_supplied_metadata', project: 'qoima-twin', generation: '2026-11-08T05:55:56Z', status: 'ready',
    scoped_solver_search: { results: 0, has_more: false },
    coverage: 'solver/spec/pose/report/manual seed not_tracked; workerRoles/Fixture and upstream contract/catalogue/stats metadata_changed; node_modules excluded',
    action: 'Exact-source fallback used; no completeness claim, graph verification rerun, or reindex performed' },
  source_snapshot: { before: 'source-hashes-before.json', after: 'source-hashes-after.json', inputs: 21,
    declared_pins_matching_before: 20, declared_pins_matching_after: 20, unchanged: 21 },
  commands: [
    { ...check, invocation_count: 1, evidence_kind: 'executed_original_cli', result,
      limitations: ['Recomputes the original solver; it is not an independent collision algorithm.', 'No normal write-mode execution.'] },
    { command: 'node work/v3/account2-base-carry-audit/20261108T180523Z/probe-native.mjs', cwd: '.',
      invocation_count: 3, exit_codes: [0, 0, 0],
      revisions: ['Initial native and extracted-validator probe', 'Added strict barycentric interior and original thumb component mapping', 'Added exact classification-expression truth table'],
      final_source: 'probe-native.mjs', final_result: 'native-probe-result.json',
      validation_mutations: 16, expected_invalid_mutations_rejected: 14, sparse_omitted_axis_mutations_unexpectedly_accepted: 2,
      json_roundtrip_sparse_rejected: true, native_contacts_reconstructed: 2,
      native_patch_normals_opposed: native.native_patch_checks.every(p => p.native_normal_dot === -1),
      patch_points_strictly_inside_both_triangles: native.native_patch_checks.every(p => [...p.hand_barycentric, ...p.cargo_barycentric].every(x => x > 0)),
      lost_contact_20um: native.lost_contact_after_20um, head_control: native.head_control,
      thumb_component_matches: native.thumb_witness_local_vertices.map(w => ({ triangle: w.triangle, source_parts: w.source_component_bounds_matches })),
      classification_truth_table_cases: native.changed_nonadjacent_classification_truth_table,
      limitations: native.limitations },
    { command: 'read-only source inspection using rg, PowerShell Get-Content/Get-FileHash, and Node JSON/GLB inspection',
      evidence_kind: 'source_inspection', scope: 'The21 declared inputs, relevant GLTF hierarchy/metadata and Euler implementation only; applicable AGENTS.md paths checked',
      failed_inspection_command: { kind: 'Node -e source-summary read', exit_code: 1, reason: 'An extra closing brace caused SyntaxError before execution; corrected read then succeeded' },
      limitations: ['No raw transcript or environment dump retained.', 'Not a whole-codebase exploration.'] }
  ],
  source_only_checks_without_mutation_experiment: [
    { topic: 'Stale edited pose/report rejection', witnesses: ['frontend/tools/solve-worker-base-carry-v3.mjs:43', 'frontend/tools/solve-worker-base-carry-v3.mjs:103', 'frontend/tools/solve-worker-base-carry-v3.mjs:110', 'frontend/tools/solve-worker-base-carry-v3.mjs:111'], result: 'Recompute precedes exact-byte comparison; saved pose/report are not used as candidate solve inputs. No edited-output counterexample executed.' },
    { topic: 'Input hash dependency direction', witnesses: ['frontend/tools/solve-worker-base-carry-v3.mjs:44', 'frontend/tools/solve-worker-base-carry-v3.mjs:101', 'frontend/tools/solve-worker-base-carry-v3.mjs:103', 'frontend/tools/solve-worker-base-carry-v3.mjs:104'], result: 'Pose embeds19 source hashes; report adds recomputed pose hash as20th. Report is not its own hash input. Fresh source hashing is consistency evidence, not independent historical source authorization.' },
    { topic: 'Original hierarchy, full mesh winding/depth and actual edge/triangle crossings', witnesses: ['frontend/tools/solve-worker-base-carry-v3.mjs:31', 'frontend/tools/solve-worker-base-carry-v3.mjs:32', 'frontend/tools/solve-worker-base-carry-v3.mjs:35', 'frontend/tools/solve-worker-base-carry-v3.mjs:36', 'frontend/tools/solve-worker-base-carry-v3.mjs:37', 'frontend/tools/solve-worker-base-carry-v3.mjs:88', 'frontend/tools/solve-worker-base-carry-v3.mjs:89', 'frontend/tools/solve-worker-base-carry-v3.mjs:91'], result: 'Component boxes prune only; whole-original-mesh tris determine winding/depth. Crossings use real native edges and Ray.intersectTriangle, followed by shared-interior tests. Candidate native checks executed through the original CLI; independent all-pair collision search not executed.' }
  ],
  explicit_limitations: [
    'No browser, renderer, Blender, server, installation, reindex, production edit, Git/auth/global settings change or warehouse mutation.',
    'Native collision probes are bounded; absence of detected witnesses is not full intersection or continuous-collision clearance.',
    'No force/friction stability, strength, ergonomics or manual-handling certification.',
    'Pickup, source approach/withdrawal, loaded walking/turning, same-HU setdown, packing and Scene integration remain unimplemented.',
    'Candidate correctness and audit completion are distinct; root retains visual review and acceptance authority.',
    'No coordinated source-and-output tampering experiment or adversarial installed-dependency substitution performed.',
    'Declared source pin set is not asserted to cover every transitive execution dependency.'
  ]
});

const md = `W05.3.2 bounded independent read-only correctness audit — complete.

The frozen static local P02/unchanged worker-base candidate passed the original check-only command once (exit0, ${check.duration_ms}ms). No frozen-candidate correctness failure was demonstrated. One low-severity internal validation defect remains for root review. All21 source/pose/report hashes are unchanged; all20 declared pins match before and after. This audit does not grant runtime or physical acceptance.

- **F01 — LOW: sparse JavaScript axes bypass validation.** At \`frontend/tools/solve-worker-base-carry-v3.mjs:20\`, \`every(finite)\` skips holes; the range check at line71 does likewise. The exact extracted validator accepts both a deletedY entry and \`new Array(3)\`. The real Euler constructor defaults missingY to0 (solver line15; \`frontend/node_modules/three/build/three.module.js:6833\`). The probe observed0 replacing the frozen .55rad. See \`probe-native.mjs:59\`, \`probe-native.mjs:60\` and \`native-probe-result.json\`. This narrows the broad omitted-axis rejection claim in \`docs/adaptive-v3/specs/W05.3.1.md:13\`. Sparse holes become null in JSON and are rejected; the frozen generated pose is dense and finite. Production apply was not invoked by the custom probe. No saved candidate or check-only bypass was demonstrated. Root can tighten index-presence checks or narrow the claim; no fix was made.

| Audited requirement | Actual evidence and witnesses |
| --- | --- |
| Original native hierarchy and surfaces | GLTFLoader loads pinned GLBs; world triangles include each native mesh transform (solver lines57,58,31). Neither GLB contains skins, animations, textures or external buffers. Original role ink is hidden by workerRoles lines152,153; generated decorative ink is excluded, physical badge base remains (solver line65). |
| Contacts and grasp rule | Native lower-pad selection and triangle clipping enforce positive projected area, opposed normals and<2um gaps (solver lines83,84,86). Independent GLB reconstruction found both saved patch points strictly inside both referenced native triangles, normal dot=-1 and hand distances6.258nm. Both grasp references have radius .46818799643m and height1.08m; .52m is separately the cargo-centre distance. Report witnesses: \`docs/adaptive-v3/evidence/W05.3.1-checks.json:390\` and line484. |
| Limits and anatomy | All8 frozen joint arrays are finite and within original metadata; all6 XYZ-limit sets agree with dimension spec. Palm X/Z are fixed0 and Y uses the existing GLB range (solver lines68,71). Independent mutations rejected booleans, strings, null, explicit undefined, nonfinite values, extra/short arrays, forbidden palm axes and extra/missing joints; sparse exception is F01. Native elbow poleY=-.09266847m and signed bend=-1.33232698rad on both sides (solver line94; report line490). |
| Identity, conservation and restoration | Existing P02 picker,24 actors/2 vehicles/530 assignments, original whole HU24units/.94kg/.32x.24x.24m, scale1, fixed stance; no warehouse update (solver lines55,56,63,64,71,81,82,93,99,100). Restores original worker and cargo TRS and checks geometry/index/metadata identity. These guards executed in check-only; independent probe reads the original GLBs without Roles decoration. |
| HU envelope, mouth and self clearance | All2392 physical body triangles,22 meshes,88 body/HU pairs and231 body pairs participate. HU envelope clips real triangles against the explicitly required full envelope, not a substitute collision verdict from AABB overlap (solver line40). Mouth uses actual local forearm/cuff triangles plus whole-mesh containment (line88); HU additionally uses native shared-interior tests (line89). Whole original mesh winding and nearest depth determine witnesses; components only prune (lines31,32,35,36). Real edge/triangle ray intersections feed shared-interior probes (line37). No candidate HU/mouth/material witnesses. Probe coverage remains bounded. |
| Original joins cannot waive new nonadjacent penetration | Classification requires unchanged matrices, or linked physical bones plus an observed baseline pair (solver lines90,91,92). The24 current observations comprise16 unchanged and8 original adjacent pairs. Four extracted-logic cases with an artificial positive baseline label still classify changed forearm/torso, upper-arm/head and opposite-arm pairs as material. These are logic tests, not induced mesh collisions. |
| Controls are nonvacuous | Actual20um HU translation gives native gaps19.99613/19.99642um; independently reproduced. Actual moved-HU/head witness has whole-mesh winding4pi in both and depths35.33558mm/.164309mm; independently reproduced. The rejected central-HU control clips46 real hand triangles; its first4 saved witnesses map uniquely to the original mitten_L_thumb bounds. Solver lines96,97,98; report lines3631,3638,3664. |
| Check-only and source pins | Solve, geometry, constraints, controls and restoration run before exact expected pose/report-byte comparisons (solver lines43,103,104,110,111). Saved pose/report are not read as solve inputs. Pose embeds19 current source hashes; report adds the recomputed pose hash, with no report/self-hash cycle. In-run source rereads detect drift (line101); frozen provenance additionally needs the external host snapshot. No stale-output or coordinated-source-edit experiment was executed. Check-only proves consistency with current sources, not independent historical authorization. |

Execution details are in \`probe-results.json\`; raw geometry/guard results are in \`native-probe-result.json\`. The small CPU probe ran three times as inspection checks were added, all exit0; its final16 invalid-input mutations produced14 expected rejections and2 sparse-array counterexamples. The original CLI's36 negative cases passed. One malformed read-only Node inspection command initially exited1 on syntax and was corrected; it executed no source changes.

The root-supplied graph generation2026-11-08T05:55:56Z is ready, but solver search returned0 and relevant inputs were untracked or metadata-changed; node_modules was excluded. This audit used exact-source fallback, makes no graph-completeness claim and performed no reindex. Only audit-owned output and process-local scratch were written; check-only TMP/TEMP were redirected into this folder.

No browser/rendered/physical observation, exhaustive collision search, continuous collision, strength or ergonomic certificate was produced. Some checks above are source reasoning plus the original CLI, explicitly distinguished from independent native probes; no independent complete all-pair collision algorithm was run. Declared pins are not claimed to cover every transitive execution dependency. Pickup/withdrawal, actual source approach, loaded walking/turning, same-HU setdown, packing and Scene integration remain unimplemented. Root owns visual review and further acceptance. There are no additional unresolved material concerns against this frozen static candidate within the stated bounded audit; F01 remains open at its limited scope.
`;
await writeFile(path.join(output, 'audit.md'), md);
console.log(JSON.stringify({ audit_complete: true, required_outputs: ['audit.md', 'findings.json', 'probe-results.json', 'source-hashes-before.json', 'source-hashes-after.json'],
  findings: { low: 1, medium: 0, high: 0, critical: 0 }, check_only_invocations: 1, hashes_unchanged: `${after.unchanged_input_count}/21`,
  candidate_correctness: 'No failure demonstrated within the bounded frozen static scope; no runtime/physical acceptance' }));
