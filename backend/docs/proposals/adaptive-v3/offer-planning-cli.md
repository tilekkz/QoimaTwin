# Offer planning CLI

Run from the backend directory with the pinned Python environment. The command
creates a forecast-based planning bundle; it does not execute warehouse work.

```powershell
python -m app.cli v3 plan-offers `
  --history caller/history.csv `
  --history-choices caller/history-choices.json `
  --model mean28 `
  --projection-choices caller/projection-choices.json `
  --placement-choices caller/placement-choices.json `
  --out output/offer-plan

python -m app.cli v3 validate-offer-plan --bundle output/offer-plan
```

Choose `hgb` explicitly to use the existing HGB producer. There is no future
actual workload option and no silent substitution for missing inputs. Validation
reconstructs the authenticated producer chain, including numerical verification;
it does not start a simulation or call an external service.

## Explicit caller inputs

`history.csv` uses `date,sku_id,offered_hus`. Supply every current source SKU for
each of the 56 complete dates immediately before `test_day`: 11,200 rows for
the pinned 200-SKU source. Counts must be canonical nonnegative integers, no
more than 2^53 individually. Missing observations are errors, not implicit
zeros. Visits, units, receipts and repeated uses of the same stock HU are
different measures. Current history support is explicitly declared synthetic.

Example `history-choices.json` (caller declarations, not source-derived hours):

```json
{
  "target_unit": "outbound_whole_hu_offers",
  "test_day": "2026-11-09",
  "timezone_name": "Etc/UTC",
  "window_start_second": 32400,
  "window_end_second": 61200,
  "provenance": {
    "kind": "declared_synthetic",
    "dataset_id": "my-explicit-synthetic-example",
    "generator_id": "my-generator",
    "generator_version": "1",
    "seed": null
  }
}
```

Every observation window must be eight local hours and eight actual UTC hours,
with unambiguous local endpoints; the last closes strictly before the local
test-day midnight cutoff. The dates/timezone/window/provenance are mandatory.

Example `projection-choices.json` declares four outbound offers over 1,000
seconds, no inbound offers and the existing source C10 outbound port mix:

```json
{
  "policy": {
    "horizon_tick": 1000000000,
    "inbound_hus": 0,
    "outbound_hus": 4,
    "calendar": "normal",
    "windows": []
  },
  "port_mix_mode": "source_c10",
  "port_mix": []
}
```

One tick is one microsecond. These are explicit caller clock/budget choices;
C10's unclocked periods do not imply them. For `port_mix_mode: "explicit"`,
provide every allowed source SKU/outgoing-port pair, including zero shares.
Each row has `sku_id`, `port_id` and reduced `weight` as
`{"numerator": 1, "denominator": 2}`; shares sum to one per SKU. Unsupported
cargo is not dropped and a shortage is not filled by cloning a HU.

Example `placement-choices.json` deliberately requests no relocation candidate:

```json
{
  "policy_id": "explicit-no-candidate-example",
  "candidates": [],
  "permitted_actor_ids": [],
  "route_policy": "c09-manual-small-standard-source-mode-projection-v1",
  "min_width_m": [1, 1],
  "min_height_m": [2, 1],
  "path_clearance_m": [0, 1],
  "receipt_targets": []
}
```

ADR0090 supports zero or one explicit original SMALL/STANDARD whole-HU manual
candidate. To request one, supply `hu_id`, `from_slot_id`, `to_slot_id`,
`actor`, positive `take_ticks`, positive `place_ticks` and `customer` (or null).
Actor fields are `actor_id`, `home_node_id`, `speed_m_s`, `max_gross_kg`;
permissions and physical source checks remain mandatory. Placement fractions
use reduced integer pairs. Customer fields are `offer_id`, `port_id`,
`buffer_choice` (a canonical JSON string), positive `pickup_ticks`, `place_ticks`
and `service_ticks`. The offer must match the newly projected stream; do not
reuse an ID from a different history or choices. Missing downstream evidence
remains `not_evaluable`, not an invented benefit. No receipts are admitted by
this projection. The explicit source example is
`tests/v3/offer_planning_cli_example.json`. Its saved customer ID belongs to
the generating kernel environment. Forecast identity includes the Python patch,
dependency versions and kernel source hashes. Bind the chosen HU's customer to
its currently authenticated projected offer. The test writer
`arguments(root, output, stock)` checks matching explicit history and projection
choices, then takes that offer ID from the supplied `ForecastBoundStock`.

## Saved bundle and result

The output must be new or empty. It contains the exact four caller files under
`raw/`, `request.json`, the five producer JSON artifacts, `observations.json`
and the final `manifest.json`. The request and raw hashes are frozen before
calculation. A failure preserves partial files plus `failure.json` where
possible; use a different output directory for a retry. Do not delete evidence
or treat an incomplete directory as a valid plan.

`plan_id` identifies the final producer decision. `semantic_bundle_id` also
binds the raw caller bytes, exact five artifacts, producer/protocol versions
and planning summary. `manifest_sha256` hashes the entire manifest, including
the separately hashed timing observations. CPU changes therefore affect the
manifest hash but not semantic identity. Timings are observations, not a
benchmark or trusted attestation.

`planned`, `no-op` and `infeasible` are planning results, all with engine calls
zero and operational admission false. Inspect `selection_reason`, the saved
candidate evaluations and `unallocated_offers`; a no-op can be the correct
result. The focused source example has three shortages and negative net saving
of 55,360,003 ticks, so it remains a no-op. Validation rejects extra files,
altered hashes, incompatible producer/source authority and correlated metadata
tampering. See [ADR0091](../../adr/0091-v3-offer-planning-cli.md) for exact scope.
