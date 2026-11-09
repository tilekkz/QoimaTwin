# ADR 0077: Authenticated outbound-only N1 scenario and one offered stream

Status: Proposed; bounded source/input implementation, not full N1 acceptance.

## Context

The historical V3 brief at a54bead defines N1 as an announced retail/express/B2B
outbound shift after a legitimate fixed baseline. Original and adapted placements
must consume the same newly materialized stream. Paid intact relocation from
ADR0073–0076 is reusable infrastructure; its unrelated customer jobs do not prove N1.

The pinned C11 input has the legacy ID `N2_DECLARED_PORT_MIX_SHIFT` and uses
`unclocked_planning_period`. It also changes inbound shares for all 55 STANDARD
SKUs, DEMO_111–DEMO_165: E_PARCEL .3 to .9 and N_STANDARD .7 to .1. Renaming or
reusing that entire input would therefore change more than the N1 outbound mix.

## Exact projection decision

The new scenario version is `qoima-n1-outbound-shift-scenario-0.1.0`, with explicit
normative `scenario_id=N1` and policy `c10_intensities_c11_outbound_mix_only`.
The original source IDs, revisions and raw documents retain their original labels.

Rows are joined by exact `sku_id`; SKU sets and each `archetype_id` must match.
Only `skus[].outbound_port_mix` is selected from C11. Each projected row starts
with the complete C10 row, so the following remain C10 values:

- `expected_outbound_HU_moves` and `expected_inbound_HU_moves`;
- `inbound_port_mix`;
- `sku_id`, `archetype_id`, `home_storage_type`;
- `handling_unit_ids`, `lot_id`, `quantity_units`, `stock_handling_units`;
- every other C10 row field, if present in the authenticated pinned document.

C11 intensity, inbound and inventory fields are not substituted. Differing inbound
SKU IDs are recorded explicitly as excluded changes. The original C10 assignment
is independently loaded/validated and all 530 HU/slot/module bindings are retained;
no C11 final assignment, proxy saving or physical relocation is adopted.

Derived outbound weight is exactly C10 `expected_outbound_HU_moves` multiplied by
the corresponding C11 outbound share. The existing pure source-weight converter
checks exact unit-sum shares, known direction and actual port cargo permissions.
Fractions remain exact. A small independent test fixes 10 C10 moves with C11
shares 1/4 and 3/4 at 5/2 and 15/2, even when C11 declares 999 moves and a different
inbound mix. For the currently pinned data, C10 and C11 outbound intensities agree;
the derived retail/express/B2B unclocked totals are 203.5/1059.1/237.4. These are
not hourly rates, finite available stock or throughput.

The baseline `WorkloadSource` is unchanged C10. The postshift source retains its
templates, dimensions, masses, orientations, original HU/lot identities and inbound
weights, and substitutes only outbound weights. Its provenance additionally includes
the six pinned C11 raw/canonical fingerprints under distinct `c11/` paths. The base
source revision still identifies the physical C10 source; the separate legacy C11
revision identifies the mix provenance. No caller `WorkloadSource` is accepted or
silently overwritten by the public compiler.

## Public immutable contracts

`compile_outbound_shift(base_root, adaptation_root, policy)` requires an exact,
explicit `WorkloadPolicy`. It reloads the byte-pinned base and C11 packages and
validates the legitimate baseline. `load_outbound_shift_inputs(raw)` independently
recompiles from the repository's pinned packages. `verify_outbound_shift_inputs`
accepts only an exact `OutboundShiftInputs`, compares all nested runtime types and
values, and returns a freshly reconstructed authoritative object for stock binding.
Filesystem root paths do not affect identities. No mutable caller source object or
cached replacement authority is used.

The frozen `N1Scenario` retains exact original raw C10 input, C10 assignment and
C11 input bytes plus raw hashes. The wire representation preserves their UTF-8 text,
including original whitespace/newlines. It includes both full workload-source
projections, original placements, excluded inbound changes, legacy labels and its
own hash. `scenario_hash` hashes the complete canonical scenario record excluding
only that hash field itself. All source fingerprints remain bound and reverified;
this does not establish the legacy C11 `comparison_inputs_sha256` method or an
actual C11 execution.

The input version is `qoima-n1-outbound-shift-inputs-0.1.0`. `OutboundShiftInputs`
contains scenario, caller policy, one `TimedWorkload`, their separate canonical
bytes, the complete canonical envelope and its SHA-256. Parsing requires a closed
field inventory and exact canonical bytes. Independent reconstruction rejects changed
source text, source weights, jobs, clocks, versions, extra fields and typed aliases.

## One materialization, explicit clocks and coverage

Compilation invokes the existing workload materializer once. Hamilton quotas,
stable population/job IDs and normal/burst calendar semantics remain unchanged.
The caller supplies H, inbound/outbound offered counts and any burst windows; no
hours, volumes, periods-to-clock conversion, service times or end cap are invented.
The established workload clock is microsecond ticks. Future A/B arms must consume
the same retained `workload_bytes`; they must not rematerialize independently.

Every quota retains its exact expectation, integer count and signed rounding delta,
including zero counts. Every materialized job is kept, irrespective of whether a
runtime currently supports its cargo class or port. B2B permission is neither
broadened nor filtered. A tiny explicit workload may round B2B or another class to
zero; that remains visible and cannot establish three-port N1 acceptance. Zero
offered counts remain a legitimate input/no-work case, not a completed scenario.

Inbound job IDs/HU IDs and per-population/SKU lot IDs describe offered receipts.
They do not credit a ledger or prove arrival-time availability. Outbound HU/lot IDs
remain unallocated at this layer. The separately owned stock binder must preserve
every offer and its original clock, bind original identities or explicit receipt
dependencies, and retain shortage reasons rather than manufacture or truncate stock.

## Scope and validation

`operational_admission=false` and `full_n1_acceptance=false` are mandatory envelope
fields. This layer does not choose an adapted assignment, select a relocation,
allocate stock, run an engine, schedule F/S actors, expose an HTTP route or grant
any mechanical handling capability. B2B still requires its real source-bound
F02/FL02 plus S01/S02 process; input materialization does not supply that proof.

New tests first failed with missing implementation imports, then cover the
independent projection arithmetic, raw source identity, preserved C10 facts,
canonical deterministic readback, exact caller clocks and nested authority guards.
The owner report records the actual focused/static results and the protected
363-file foundation hashes. No full-suite, source DES or operational claim follows.
