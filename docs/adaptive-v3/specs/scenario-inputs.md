# Preregistered W09/W10 visual input streams

Prepared result only; parent W09/W10 remain unaccepted. These files do not execute a workflow, register a supported frontend fixture, select an adapted placement, establish a no-op result or produce performance metrics. `source_kind: visual_fixture`, `engine_operation: false`, `execution_ready: false` and `execution_state: not_scheduled` are explicit throughout.

## Sources and immutable state

The accepted W01 fixture is pinned to SHA256 `52aac1c73e9352b9e08ef3c370061932de3abd98c9e2a56beb121ebb70267a91`. Both scenarios retain all original 530 HU identities, 200 SKUs, 12,256 packaged units, 9,403.85 kg gross mass, dimensions, upright orientations, scale 1, original storage placements, 24 workers, two driver/vehicle pairs and six configured ports. Existing W01 source hashes bind the layout, cargo/SKU catalogues, ports, finite buffers/service rules, worker profiles and frozen base request stream.

Every scenario has 16 concrete requests: eight incoming and eight outgoing, with one of each cargo archetype in each direction. All request/HU/lot/SKU IDs, packaged-unit quantities, absolute release/deadline seconds and the 1,800-second illustrative horizon remain exactly those of W01. The eight incoming HUs remain upstream, outside the 530-HU initial stock. Request release is not receipt or dispatch completion.

`W09-normal-input-v3.json` retains every W01 request and port assignment. It permits a future justified no-op but leaves the adaptation decision unevaluated. No relocation or artificial benefit is forced.

`W10-port-mix-input-v3.json` declares four changes before any comparison:

| Request | Cargo | Fixed W01 port | W10 port |
|---|---|---|---|
| inbound:02 | STANDARD_CARTON | IN_N_STANDARD | IN_E_PARCEL |
| outbound:02 | STANDARD_CARTON | OUT_W_RETAIL | OUT_S_EXPRESS |
| outbound:04 | PALLET_LOAD | OUT_W_RETAIL | OUT_E_B2B |
| outbound:07 | DRUM | OUT_W_RETAIL | OUT_E_B2B |

All four target ports have the correct direction and allow the cargo class in the unchanged source port configuration. This is an input-level compatibility check; actual loaded paths, physical actions, shared handlers, traffic and resource admission remain required before execution. Outbound request counts change from retail/express/B2B = 3/1/4 to 0/2/6. The western retail port remains physically configured even though this small shifted stream does not request it. These four illustrative choices are not a conversion of C11 expected HU-move weights or unclocked planning periods into seconds.

## Paired comparison contract

`scenario-inputs-manifest-v3.json` gives each scenario exactly two variants, baseline and adaptive. Both variants reference the exact same input file, raw SHA256 and frozen payload hash. They have no per-variant request, staff, equipment, service or port override mechanism.

The first comparison is `slotting_only`. It may differ only in admitted HU placement and an explicit admitted relocation sequence with its cost. Roles, staff count and port assignments remain identical within each pair. Both start from the same original W01 stock before any priced relocation. A staffing or mixed comparison requires a separate declaration and registration; it cannot be introduced through these input records.

The workflow/action timing source is not yet registered here. Before either run, W05/W14 must freeze the same workflow implementation and timing assumptions for both variants, admit physical cargo/handler actions, construct finite-buffer/exclusive-resource intervals and provide actual scene/replay evidence. `required_before_execution` preserves these gates. No claim that all runnable comparison inputs are finished follows from this preparatory result.

## Actual checks

The deterministic builder refuses replacing an existing preregistered file with different bytes. Its `--check-only` compares all three current output files with their deterministic source derivation. The independent verifier does not import the builder: it checks original W01 source bytes, immutable component equality, C02 cargo dimensions/mass/counts, stock conservation, every request identity/time/quantity, port direction/class/open window, the four declared changes and exact A/B input identity.

Fifty negative cases pass. Scenario mutations recompute generic input and payload hashes before validation. Rejected cases include extra/changed people and vehicle pairs, service/buffer/gate changes, missing/duplicate HUs or requests, quantity/mass/dimension/scale changes, unpriced initial relocation, wrong/forbidden ports, hidden request overrides, changed times, upstream/stock confusion, a fabricated action/completion/no-op/throughput, mixed staffing/slotting settings and unequal baseline/adaptive input references.

Commands from the repository root:

```powershell
.venv/Scripts/python.exe tools/visual/v3/build_warehouse_scenario_inputs.py --check-only
.venv/Scripts/python.exe tools/visual/v3/verify_warehouse_scenario_inputs.py --check-only
```

Actual frozen raw hashes:

- W09 input: `8bfd657665c614e0ac0f1db00ecf83191eb70a073af05c89fe5cc3d7623ae88d`
- W10 input: `b8ad34e25ff27cd40e4656bef541e6a69aee475f3257b4af8b5695b87d0998b5`
- Paired manifest: `ecfef20d4791a75511a1bcb77b6505982b4e9879b90e1d3a2ca61bfec0d267ac`

Evidence: `docs/adaptive-v3/evidence/scenario-inputs-checks.json`. No browser or Blender was launched, no canonical/backend/shared contract or accepted source artifact was changed, and no parent task state was updated.

Suggested bounded children for root registration: W09.1 normal request/control materialization, W10.1 shifted request materialization and exact paired input contract. Each parent still needs a connected workflow, actual pause/replay/scene proof and a truthful comparison/adaptation decision before PASS.
