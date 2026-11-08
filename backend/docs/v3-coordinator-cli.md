# Source-bound coordinator commands (proposal)

The coordinator uses the proposed namespace `qoima-staff-coordinator-v3-proposal-3`.
Its public commands accept ADR0064 source-bound choices. Analytical hand fixtures are not
public inputs. The six stations, twelve picker bindings, physical carts, whole/receipt jobs
and role plan remain in one compiled world. Canonical contracts and frontend adoption are
separate and remain unchanged by this proposal.

```powershell
uv run python -m app.cli v3 simulate-coordinator `
  --profile docs/proposals/adaptive-v3/coordinator-profile.example.json `
  --out artifacts/coordinator-example
```

Before constructing the engine, the command verifies the compiled input against pinned
raw sources and freezes normalized `profile.json`, `request.json` and `run/inputs.json`.
`result.json` retains actual complete/partial/failure status. The native manifest and its
hash identify the published run; a failed execution preserves the original request and
inputs. An occupied output directory is rejected. Changing the H/end or role plan changes
the complete input identity; the bounded registry hash is not physical common authority.

To assign explicit clocks to an existing finite job population, first materialize a
calendar. This step recompiles source authority and does not execute the engine:

```powershell
uv run python -m app.cli v3 materialize-coordinator-calendar `
  --profile docs/proposals/adaptive-v3/coordinator-profile.example.json `
  --calendar docs/proposals/adaptive-v3/coordinator-calendar.example.json `
  --out artifacts/coordinator-calendar
uv run python -m app.cli v3 simulate-coordinator `
  --profile artifacts/coordinator-calendar/profile.json `
  --out artifacts/coordinator-calendar-run
```

The supplied calendar is a sparse two-order illustration over one hour. It is not a V3
normal/peak budget, a benchmark, or the full C10 source port mix. ADR0068 documents the
integer half-open clock rule and the exact population-preservation boundary. To form an
A/B pair, materialize the same calendar on both choices and still apply ADR0067's full
physical input comparison; `offered_workload_hash` alone is insufficient.

For a bounded N0/N4 comparison, both source profiles must pass the complete input
comparison; only the N4 role plan may differ:

```powershell
uv run python -m app.cli v3 compare-coordinator `
  --baseline docs/proposals/adaptive-v3/coordinator-n4-baseline.example.json `
  --candidate docs/proposals/adaptive-v3/coordinator-n4-candidate.example.json `
  --scenario N4 --out artifacts/coordinator-pair
```

The pair command freezes both inputs before two independent executions, then publishes
separate native manifests under `baseline/` and `candidate/`. `result.json` keeps the
scenario verdict and both native metric sets. Command completion is distinct from
`comparison.verdict`: a finished experiment may legitimately be `not_demonstrated`.
Partial business completion remains `partial`; an execution/publication failure retains
the request and inputs with a failed result. N1/N2/N3 are not accepted by this command.

The proposed mixed N4 inputs retain the initial 530 HUs, 12,256 units and 24 actors. They
declare two SMALL orders plus one manual STANDARD receipt/whole shipment. Both sides
use the same synthetic K05/K06 break `[100,1600)s`; only the candidate requests P11/P12
at PK05/PK06, departure100s, return request1200s, restoration deadline1600s. These are
input assumptions, not source norms or observed completion times. H is1700s and the
observation cap1800s. The source compiler and actual paired execution must still pass;
no result or speedup was generated while authoring these examples.

The separate `coordinator-tilek-n4-baseline.example.json` and
`coordinator-tilek-n4-candidate.example.json` propose P01/P02 helper eligibility and
an explicit6/5m/s walking speed for those two workers, matching the synthetic
identity/speed convention in Tilek's476aacb P11 profile. Both sides preserve the
same choices; only role intents differ. The original P11/P12 experiment remains
separate. P01 already has picker work, so helping must wait for its actual clean
release; no observed N4 result is asserted. The frontend's0.8 packer skill has no
numeric equivalent in the current explicit station service-clock model. See the
[compatibility proposal](proposals/adaptive-v3/coordinator-tilek-helper-proposal.md).

Implementation and tests are currently drafted. Under the user's final-phase validation
instruction, these new commands have not yet been executed and are not claimed to pass.
