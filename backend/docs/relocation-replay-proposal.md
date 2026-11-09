# N1 arbitrary settled-state reader

`app.v3.relocation_replay.replay_relocation_run(run, *, inputs, tick)` returns
a JSON frame for the exact nonnegative integer microsecond tick `T`. The run must
pass the complete strict N1 publication validator, including evidence after `T`.
`T` cannot exceed the actual `observed_until_tick`, even when the original requested
observation cap was later. Boolean, fractional, negative and future ticks fail.

The reader version is `qoima-relocation-settled-replay-0.1.0`. The frame includes the
native N1 `run_id`, exact input/common/registry hashes, canonical native outcome hash,
engine and publication versions, outcome kind, requested tick and last consumed
sequence. The native run ID is not a public transport/storage identifier.

The state boundary is after **all** recorded events with `event.tick <= T`. A fresh
journal is reconstructed from the immutable inputs for each request. It consumes
the full event prefix and settles every recorded event boundary, recorded capture
boundary and the requested cut. Existing captures are verification targets; they
never supply mutable state for a later or earlier cut. Repeated and backward reads
do not modify the run, inputs or an engine.

For a nonempty plan, `RelocationJournal` preserves the original inventory, motion,
roles, unit, goods, packing, belt, resource and constraint journals. The unchanged
`coordinator_seek_state.snapshot` builds the common frame from those actual states.
The reader adds independently replayed relocation progress and derived source slots,
then checks the complete typed frame against the journal. Compact encoding retains
the original input-bound recipe/unit definitions. For an empty plan, the frame is an
exact original `CoordinatorSnapshot` and compact base payload; no extension fields
are silently injected.

The reader capabilities are explicitly:

| Capability | Value |
| --- | --- |
| Arbitrary settled state | true |
| Engine restore | false |
| Geometric interpolation | false |
| Full V3 | false |

Active operations retain their declared route, start and planned end clocks. Paid
exposure at the requested cut comes from the original worker/view arithmetic. An
active moving worker keeps `node=None`; no geometric position or unobserved future
completion is invented. Actual take/place effects, claim generations, all leases,
all worker/cart/role/packing states and derived source ownership come from the prefix
ledger. Claims and relocation reservations remain until the observed paid return.

The N1 journal additionally requires an admitted, unreturned job to have its exact
next positive operation open at every settled cut. Its start equals admission plus
the preceding declared durations. Zero-duration steps must already be settled.
This prevents a forged partial publication from deleting the immediate operation
start and inventing an idle interval after admission, take or place.

The hand tests cover the independent 2/3/5-metre oracle at 0, 3, 4, 6, 8, 9,
12.999999 and 13 seconds; captured equality; repeated/backward reads; exact claims,
unit identities and balances; partial caps; prearrival state; downstream whole work
from the relocated slot; and zero travel durations. Scheduler entry points are
patched to fail during public reader calls. Strict future evidence and tick
rejections are checked directly.

This remains an opt-in native reader proposal. Each request validates the full run
and replays from initial authority; no checkpoint acceleration or source-scale
performance is claimed. HTTP/UI integration, source execution, A/B improvement,
engine resume and geometric playback are outside this bounded implementation.
