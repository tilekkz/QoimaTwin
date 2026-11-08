# Connected SMALL component CLI

From `backend/`, run the explicit source-bound example into a new directory:

```bash
uv run python -m app.cli v3 simulate-light --profile docs/proposals/adaptive-v3/light-flow-profile.example.json --out runs/v3-small
```

The profile names three units of one initial SMALL HU, the exact workers, source
access points, finite carrier and parcel materials, handling durations and the
horizon/end cap. The compiler binds source geometry and recipe data, rejects
unknown fields and overrides, and freezes canonical `inputs.json` before the
engine starts. An optional `--inputs DIR` selects a validated V3 source bundle;
it does not bypass its source-byte and semantic checks.

The command links paid picking, cart travel, physical belt reservations,
packaging and outbound service on one clock with one unit ledger. It publishes
actual events, captured mutable state and separate horizon/end metrics. Its
manifest is written last. An existing nonempty output directory is rejected.
A failed execution may retain frozen inputs for diagnosis without a success
manifest. A partial result preserves actual WIP and returns a nonzero exit code;
only a complete result returns zero.

## Reading the artifacts

`app.v3.flow_transport.read_flow_run` validates raw hashes, frozen input/run
identity and component semantics before exposing a run. `event_window` returns
a half-open interval of at most 60 seconds. `captured_checkpoint` requires an
exact recorded tick; it does not reconstruct an arbitrary requested timestamp.
Clock ticks are integer microseconds. Captured state includes all settled
effects at its tick; events remain independently sequenced.

Immutable recipes and token ancestry live in a catalog; checkpoints contain
mutable state and watermarks, not a copy of the event history. The reader
currently validates the full bundle before selecting a checkpoint or window.
This is not a streaming or bounded-memory replay implementation.

## Explicit capability limits

This is a connected component execution. It does not yet integrate new inbound
receipts, every cargo class/port, N0-N4 policies, arbitrary seek/interpolation or
the frontend action adapter. The carrier/package and handling choices are
declared synthetic inputs. Logical unit transfer does not prove mesh hand
contact. `full_v3`, `frontend_adapter`, `hand_contact_proof`, `arbitrary_seek`
and `interpolation` remain false. Shared contracts are unchanged.

See [profile compilation](adr/0048-v3-explicit-connected-small-profile.md),
[publication semantics](adr/0049-connected-flow-publication.md) and
[the latest audited Tilek revision](research/2026-11-08-tilek-v3-compatibility.md).
