# V3 delivery scope, 8 November 2026

This is the implementation and acceptance scope of the assembled coordinator.
Execution evidence belongs to the exact candidate freeze and its retained check
reports; source review and file-copy checks do not establish runtime acceptance.
The published baseline `0362cd4` recorded 2,376 passing tests and 92.59% coverage.
Those historical results do not validate this composition or expand its scope.

## Assembled candidate

| Component | Behavior authored | Required final evidence |
| --- | --- | --- |
| Source profile and calendar | Explicit worker/cart/station choices, source binding, immutable offered work and downtime | Profile rejection, input identity and CLI tests |
| Shared coordinator | Concurrent unit work, receipt/whole work, actual helper transitions, finite leases and one stock authority | Hand cases, conservation, paid return, source run |
| Native publication | Exact inputs, ordered events, compact captures, strict semantic reader and immutable transport | Corruption tests, source publication/readback |
| Metrics | Horizon/end accounting, paid distance, role exposure versus labor, station/material/WIP/inventory observations | Independent arithmetic and boundary tests |
| Replay | Mutable state after all events with `tick <= T`, for integer `0 <= T <= observed_tick` | Backward/repeated cuts, same-tick effects and corrupted evidence |
| Registered API | One ordinary source profile on the shared worker, verified files, captured checkpoints and separate replay route | Real worker lifecycle, one attempt, cached repeat and HTTP reads |
| N0/N4 comparison | Common frozen inputs, role-intents-only change, actual helper work and paid return | Valid pair artifacts, truthful partial/not-demonstrated outcome |
| Local PALLET component | Shared local cycle and source receipt prerequisites | Dedicated component tests; no warehouse inbound claim |

Publication policy is `qoima-coordinator-run-0.2.0`. Native identity includes the
engine, publication and `qoima-staff-coordinator-metrics-v2` policy versions plus
the exact compiled input hash. The publication bump also invalidates the outer
CLI/API request-cache identity. Transport shape remains version0.1.0. These are
separate version domains, not a shared-contract migration.

The ordinary registered API profile has two SMALL unit orders, H900s and no receipt
or whole-HU order. The mixed N4 CLI examples add one24-unit STANDARD receipt and
shipment, H1700s and an end cap1800s. Both N4 sides explicitly reserve terminal
capacity3 for two parcels plus the intact HU. P11/P12 and Tilek-aligned P01/P02
helper families are separate proposal examples. Their speed/material/handling
choices are declared assumptions, not measured worker productivity.

The mixed complete quantity oracle is `12256 + 24 = 12250 onsite + 30 shipped`.
Its mass oracle is `9404.35 + 6.35 = 9404.04 onsite + 6.66 shipped` kg, including
declared carrier/package tare. Apply these only when the corresponding work
actually completes; partial outcomes retain actual credits and shipments. Route
times and improvement are observed results, never acceptance constants.

## Remaining product requirements

- Executable paid relocation and an assignment-changing N1 comparison remain absent
  from this coordinator. The existing C11 planning adapter is an unclocked proxy.
- Full N2/N3 and V3 forecast-driven adaptation are not implemented by N4 helper work.
  Existing V2 forecasting and optional Mercury explanations do not establish that link.
- Warehouse workflows for all eight cargo classes, heavy ports and loaded PALLET
  receipt still require operational admission, geometry and shared-runtime integration.
- The frontend must adopt an agreed native-engine adapter. Source geometry and
  visual prototype screenshots do not prove playback of these native bundles.
  Shared contracts and Tilek's frontend files are unchanged by this candidate.
  The [native bridge proposal](proposals/adaptive-v3/coordinator-native-bridge.md)
  specifies the initial ordinary SMALL case and the mappings still to agree.
- Source-scale normal/peak repeats, throughput/export-size measurements and the
  browser memory/FPS targets need current measured evidence and an agreed profile.
- Replay validates the complete bundle and reduces journal prefixes. It makes no
  low-latency, bounded-memory, geometric interpolation or engine-restore promise.
  Unobserved metric dimensions remain unavailable rather than synthetic zeroes.

## Final evidence to attach

Preserve the exact source pin, code tree and candidate hashes, original profiles,
compiled inputs, request/result files, native bundles, checks and process exits.
Run the required suite, both mypy target platforms, Ruff/format, contract validation
and the existing optimized process probe on the frozen candidate. Keep new failures
and repairs distinct from historical evidence. Commit and push only after these
checks pass.

One mixed pair executes two engines; one ordinary API request executes one worker
attempt. Reuse their exact saved bundles for reader/seek checks. A cached repeat is
not a second deterministic run. Publish actual complete/partial/failed status,
N4 verdict, accounting and limitations without changing inputs to force a benefit.
