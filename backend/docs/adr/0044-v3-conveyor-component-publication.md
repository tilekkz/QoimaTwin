# ADR 0044: Reproducible source-bound conveyor component publication

Status: accepted for a bounded backend component; shared contracts remain unchanged.

`v3 simulate-conveyor --profile FILE --out DIR` exposes ADR0040's actual finite
conveyor simulation. A strict profile binds the existing source revision and
layout hash, exact microsecond horizons, actual initial catalogue HU identities,
unique job/carrier identities, directed edge IDs and explicit station dwell.
No request can replace a catalogue HU's dimensions, gross mass or archetype.
Heavy, unsupported, malformed and disconnected routes reject through the same
source admission and plan compiler used by the component engine.

The caller explicitly offers each unchanged HU at its route's first node.
This does not remove it from the baseline warehouse ledger or prove a picker
moved it there. The component preserves that HU identity and physical recipe
through the route. There is no unit picking, wrapping, parcel transformation,
packer ownership or shipping confirmation. A dwell is an explicit stationary
component interval, not an inferred packing norm. No default tote or pool exists.

Before constructing the invariant-checked engine, persist `inputs.json` with
the normalized proposal, materialized jobs, complete source fingerprints and
the canonical conveyor source document. Reject nonempty output directories.
On failure the frozen inputs remain; no success manifest is written. At a
finite end cap, publish the actual partial state and return nonzero from CLI.

Successful execution writes `trace.json` and then `manifest.json`. The manifest
lists exact sizes and SHA256 hashes of inputs and trace. Native component ID is
the canonical SHA256 of `{engine_version, input_hash}`; the input hash covers
all frozen input bytes. Job order is a set-like choice normalized by stable ID;
route order remains significant. The initial component version is
`qoima-belt-component-v3-proposal-1`.

This experimental trace is `qoima.conveyor-component-trace.v3-proposal` version
0.1. It includes exact rational values, actual event order, leases, physical
progress, planned motion ends and separate settled H/end observations from
ADR0040. It is not the manual-run or shared warehouse transport schema and has
no general checkpoint seek/30-second chunk contract. Flags explicitly declare
`full_v3_warehouse=false`, `inventory_integration=false`, `frontend_adapter=false`
and `source_label=actual_engine_component_run`.

The reproducible example uses the unchanged SMALL HU DEMO_001:01, .32 x .24 x
.24m and .94kg, offered at intake and routed through PK06 to output. Its declared
station dwell is 2 seconds, H100/end200. Independent source-edge arithmetic gives
149170000 microseconds including both stopped pivots, with no cell-rounding drift.
This is a component fixture, not a completed order or shift throughput target.

Tests verify catalogue binding, strict input rejection, frozen inputs existing
before engine construction, raw artifact hashes, permutation-stable identity,
changed-dwell identity, partial exit status and retained failure evidence.
