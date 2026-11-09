# ADR0076: two actual N1 runs with observed paid differences

Status: bounded paired-execution proposal. Source-scale execution, full N1 acceptance and frontend/API delivery are separate checks. This decision does not modify the current coordinator CLI or any existing N0/N4 contract.

## Execution and frozen evidence

`execute_relocation_pair(pair: PreparedRelocationPair, out_dir: Path)` first calls the strict pair verifier from ADR0074. The same common frozen bytes determine the actual conveyor, H and end cap. Both source-bound and analytical pairs retain their explicit family; they cannot mix or substitute an altered common world.

Output must be a new or empty ordinary directory. Before either engine runs, write the complete pair bytes to `inputs.json` and exact arm bytes to `baseline/inputs.json` and `candidate/inputs.json`, using exclusive creation. An existing file or completed bundle is not overwritten. If execution or publication later fails, retain these frozen input files as attempt evidence.

Run two distinct `RelocationEngine` instances sequentially: baseline first, candidate second, each with its independently validated profile and the exact common H/end/conveyor. An empty candidate still executes the second real engine. Do not copy baseline events, substitute an analytical result, infer an outcome from the plan or skip a run because no benefit is expected.

Build each actual native relocation run, write its strict transport and immediately read it back. Require exact canonical equality with the actual observed run after native semantic validation. Publish `comparison.json` only after both actual runs and both strict native readbacks succeed. The successful report's `executions:2` follows these two direct calls; failed attempts do not receive a successful comparison report.

## Observed report and sign convention

Use report version `qoima-relocation-pair-report-0.1.0`, the explicit N1 pair policy and the complete pair input hash. Retain both actual operational statuses, both input/run IDs, exact event and observation hashes, source revision/pins, initial stock identity, common physical-profile identity, registry identity, actor/cart IDs and common H/end.

`no_op` means the authorized candidate contains no relocation jobs. Report actual event/observation equality separately; do not use the input label to manufacture equal outputs.

At H and at each arm's actual terminal observation, report:

- baseline and candidate observation ticks;
- baseline and candidate **common worker paid ticks**;
- `net_paid_ticks = baseline_common_paid_ticks - candidate_common_paid_ticks`;
- relocation paid subtotals as diagnostics already included in common paid labor;
- actual common unit/whole completed orders, completed units, backlog and completed-cycle samples, with count deltas defined as candidate minus baseline.

A positive net paid value means less candidate paid labor; a negative value means additional candidate paid labor. Do not subtract the relocation diagnostic again. Preserve zero, negative, no-benefit and partial results without an improvement filter.

H is the same observation boundary for both arms, with settled inclusive counts and `[0,H)` paid integration. At end, both runs have the same cap but may finish at different actual ticks; retain both ticks explicitly and do not present their raw totals as equal-duration throughput rates.

Keep `business_complete_tick`, `resource_drained_tick` and `observation_end_tick` as labelled raw boundaries. In this N1 engine, business completion includes relocation placement. It is therefore not a customer-throughput metric. Customer work is measured from actual common unit/whole handovers and their cycle samples.

## Independent hand expectations

Directed2/3/5m travel at1m/s with take2/place1 gives candidate13s total paid labor versus baseline0. At H10, candidate common paid is10s versus baseline0; net is-10s. At actual terminal observations, baseline tick10 and candidate tick13 produce net-13s. Neither net is doubled to-20/-26 by subtracting the diagnostic again.

With H5/end6, the candidate remains partial at tick6, the intact original HU is actually owned by `actor:S01` under its active claim, and net paid is-6s. Both source and destination input placements remain unchanged in their frozen original seeds.

An analytical empty-job pair still makes two observed engine calls and yields equal actual event/observation hashes with net0. Test instrumentation counts the calls and verifies all three input files exist before either invocation; production code directly performs the two calls without a testing hook.

## Standalone CLI only

The separate entry point is:

```text
python -m app.v3.relocation_cli compare --baseline INPUTS --candidate INPUTS --out DIR
```

It loads strict relocation input bytes, prepares explicit N1 and calls the same executor. Standard output is a compact JSON result with actual status, input family, comparison identity/path, no-op label and net paid ticks at both windows. Valid partial execution is a successful command with `status:partial`; malformed inputs or execution/publication failures return a nonzero code and structured error output. The complete observed comparison stays in `comparison.json` with two native arm bundles.

No existing core CLI registration or API route is changed. Tests invoke only analytical hand engines and one actual analytical subprocess. Source execution requires a separate explicit run and its own observed evidence.
