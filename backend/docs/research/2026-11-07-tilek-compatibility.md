# Backend compatibility with Tilek's latest branches

Verified on 2026-11-07 against these immutable GitHub commits:

| Branch | Commit | Backend implication |
|---|---|---|
| `codex/twin-environment` | `10496fd4ccd748676c036c371dd1a29881f046d1` | Original inline Run 2.0 reader |
| `codex/twin-v2-polished` | `cb5777f108478aabe3b7117a19d2b471ad79d2de` | Same reader; cargo-heading smoothing and visual refinements |
| `codex/twin-v3-adaptive` | `22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec` | Same operational replay; separate unfinished adaptive proposals |

All 21 canonical shared contract blobs are identical to the backend. The complete recursive
GitHub trees were checked with `truncated=false`; the ordinary compare response was capped at
300 files and therefore could not establish absence of runtime changes. A full asset fetch
failed with a connection reset; the review used pinned GitHub tree/blob responses instead.

`adapter.ts`, `types.ts` and `motion.ts` remain byte-identical to the original reader.
The polished replay core adds cargo-yaw smoothing. The latest adaptive commit changes mast
assets and evidence, with no changes to frontend source, frontend tests or shared contracts
relative to `948a1835d818c7536abd3727dacba3bc8fcfb5f9`.

## Verified visual projection

Use `simulate --format tilek-v2` and load the resulting `run.json` in the existing file picker.
The authoritative v2 export and the opt-in 2.1 proposal retain their own distinct identities.
The compatibility projection resolves pallet positions, vehicle ownership and forklift operation
names without changing simulation timing, stock, routes or metrics.

The actual TypeScript from the new branches was executed against analytical, multi-order,
receiving and cutoff exports:

```text
REAL TILEK TYPESCRIPT GREEN: 92 assertions; no npm/server
```

Checks include visibility, parcel-to-pallet ownership, attachment exactly at pickup completion,
unloading and putaway, empty forks, unchanged source metrics and deterministic reverse seek.
This is parser/core/motion evidence, not a browser, WebGL, FPS or client-memory measurement.
The hand-derived analytical milestones remain 32.8, 469 and 474 seconds.

The reader still does not load manifests/chunks or decode business snapshots, ignores exact
terminal/boundary state and heading hints, and treats real PKxx/SHIPPING containers as unknown
cells. New belt animation needs blocked segment IDs that the reader does not populate. These
limitations require frontend work; the exporter does not invent cells, epsilon durations or
completed actions to conceal them. See [the projection guide](../tilek-compatibility.md).

## Adaptive v3 is a separate model

The adaptive proposal describes a 144×72×8 m warehouse, 776 storage addresses, six conveyor
ports and different handling-unit/storage semantics. Its own manifest explicitly marks backend
adapter, scheduling and operational admission as unimplemented. Contract handoff C12 and
workflow/adapter tasks W01/W02 remain TODO at the pinned commit.

These files do not replace the accepted 72×48 v2 inputs. Implementing a v3 simulation requires
frozen scenario, port, handling-unit and role-execution definitions plus explicit migration
decisions. This review leaves shared contracts and Tilek's frontend unchanged.
