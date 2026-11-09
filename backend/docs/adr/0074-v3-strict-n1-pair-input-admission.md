# ADR0074: strict N1 relocation-only pair input admission

Status: bounded comparison-input proposal. This decision admits and freezes two comparable input arms. It does not execute either arm, publish a comparison, assert an improvement or complete N1.

## Explicit comparison boundary

Use separate `qoima-relocation-pair-inputs-0.1.0` inputs with policy `n1-single-intact-manual-relocation-jobs-only-v1`. The only accepted scenario is the exact string `N1`. Current coordinator N0/N4 pair models, serialized inputs, source records and readers remain unchanged.

Each arm must independently pass the existing relocation run-input authority path: either exact source-bound `BoundRelocation` or exact analytical `HandRelocationInputs`. Reject mixed source/analytical families and unrecognized subclasses. Revalidate retained typed profiles, choices, plans, hashes and canonical bytes before comparing arms. Loading pair bytes independently reloads each complete arm through `load_run_inputs`; no scheduler or engine is created.

Baseline must contain zero relocation jobs. Candidate may contain zero or one. A zero-job candidate is a valid no-op. No expected improvement, throughput threshold or positive-savings filter belongs to admission.

The sole permitted input change is `RelocationChoices.jobs`. Both arms must retain exactly identical common input bytes, including all initial source stock, workers, actor rates/capacities/availability, graph, unit/whole workload, receipt offers, resource definitions, role intents, H and end cap. Changing any of these requires a different comparison policy; it cannot be hidden in N1 metadata.

All nonjob relocation choices remain identical: profile identity, provenance, explicit S01/S02 permission tuple, manual route policy, minimum corridor width and height. The complete ordered source place/module descriptor tuple remains identical too. Exact nested type comparison rejects Boolean/integer/Fraction aliases instead of relying on value equality alone. Different handling durations or actor choices are carried by the candidate's explicitly declared job and remain subject to its independent plan admission.

## Complete source authority for zero jobs

ADR0073 source binding now retains all 776 source slot/module descriptors for zero as well as one job. This is a narrow correction required by exact common-world comparison; selected-address transfer admission still occurs only for actual jobs. The previous plan manifest and all eleven previous file bytes are preserved externally, and the corrected plan has a separate v2 manifest.

Zero jobs create no relocation plan, stock command, derived placement, resource lease or worker. Merely carrying source descriptors must not inject them into the runtime's existing `whole_places` or other dynamic structures. The original coordinator canonical bytes and the existing one-job candidate source input bytes stay unchanged.

## Frozen pair and public APIs

`PreparedRelocationPair` is frozen/slotted and retains the exact N1 scenario, complete baseline and candidate input records, common input SHA256, canonical pair bytes and pair SHA256.

- `prepare_relocation_pair(baseline, candidate, *, scenario)` independently verifies both retained arms, applies N1 comparison rules and freezes the pair.
- `load_relocation_pair_inputs(raw)` requires exact immutable canonical bytes, closed envelope fields and the own schema/policy/scope versions. It reconstructs both complete input byte sequences, checks their hashes, reloads their authority and derives the expected entire pair envelope.
- `verify_relocation_pair(pair)` reconstitutes the pair from its canonical bytes and compares every retained field with exact nested runtime types.

The pair envelope includes schema, policy, scope, scenario, family, common hash, both arm hashes and both complete canonical input objects. These nested objects reconstruct the same original canonical bytes; the pair never strips the relocation extension or replaces original initial placements with a candidate-derived world. Unexpected fields, false family labels, altered versions or rehashed metadata cannot make differing inputs comparable.

## Independent expectations and remaining execution

Analytical tests use directed 2/3/5m travel with take2/place1 and the independent 13s total paid plan. They exercise a valid N1 pair, zero-job no-op, nonempty baseline rejection, unsupported scenarios, independently valid common clock/speed changes, nonjob permission/clearance/profile drift, place metadata drift, source/analytical family mismatch and retained/rehashed metadata rejection.

Source-only checks bind the declared original DEMO_113 HU pair, require identical 776-place descriptors and common SHA256 `47ea8d54101f63b7dd2f958a41174c716607019a6f43a7379d2b80b3f42b3f99`, and preserve the original one-job source-input SHA256 `a613b189fa64fac9f4544d0434e387d760c2735faccef7d767287e760e66d57a`. They do not execute source DES.

A later separately authorized executor must run two real engines and report observed outcomes, including no-benefit and unfinished-work cases. Candidate common paid labor already includes its relocation labor. Net paid difference must therefore compare the two total paid values once; subtracting relocation cost again would double-charge it. This input-admission module computes no performance result and creates no CLI/API path. Publication and semantic journal authority are separate work under their own versioned boundary.
