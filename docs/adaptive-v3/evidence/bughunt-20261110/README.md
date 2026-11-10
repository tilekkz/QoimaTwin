# Additional desktop bug hunt — 2026-11-10

The additional tests exercise current `codex/twin-v3-adaptive` at base `713db76`, including its staged busy-shift demo. They do not change the already delivered verified ZIP or V2 branch. Original character/model files are unchanged.

## Fixed behavior

- Native NDJSON cancellation interrupts a pending read. Transfer records are limited by UTF-8 bytes; the initial header respects the retained-memory budget. Contradictory capture identities, motion endpoints and event times are rejected while nullable partial captures remain supported.
- Exact large and tiny rational values project to finite doubles with appropriate significant precision. Conveyor orientation interpolates the exact phase in integer ticks before periodic reduction. Seeking cannot mutate the geometry through a previously returned idle-worker position.
- Native Page exits the ready state on actual WebGL context loss, releases its scene and enables retry. Persisted lifecycle restoration recreates the scene. Retry/restoration uses the speed shown in the selector. An obsolete model-loading completion disposes its own scene rather than the active scene.
- TwinShift rejects invalid time before mutating reused frames and clamps finite time to the demo interval. Changing B's layout preserves A's seeded demand. Handoff no longer teleports a worker/cart by 1.8 m. The existing smoothed path helper now joins both sides of a corner and validates its inputs.

## Verification

The final index binds the raw failing witnesses and successful reports to exact source hashes. There are 76 additional check groups: 45 NativePair, 10 TwinShift, 11 scenario/scene, and 10 actual desktop-browser cases. The existing 20 NativePair checks also pass. Full TypeScript checking and production build pass.

Scenario coverage includes 1,127 shuffled boundary/epsilon/seeded samples and 154 native scene applications, with zero observed actor/vehicle coordinate discrepancy. Twin coverage includes 12,208 actor-job endpoint probes, repeat/reverse playback, incident boundaries and original 24-worker scene resource restoration. Browser coverage includes malformed files/models, cancellation/retry, actual context loss, explicitly dispatched persisted lifecycle events, overlapping scenario loads and an actual A/B section rebuild. Served production JS/CSS/HTML bytes are checked against this build; unexpected Page, console, HTTP and request errors fail the browser run. Intentional aborted requests are listed separately. The preview favicon is intercepted with 204 to match the delivered package server.

The independent second Codex reviewed a fixed source snapshot. Its tiny-fraction, huge-orientation and retained-speed findings are resolved by the later source epoch and covered by regressions.

## Run again

From `frontend`, with dependencies installed:

```powershell
npm run test:native-pair:adversarial -- --out ../work/native-pair-adversarial/NEW.json
npm run test:twin-shift:adversarial
npm run test:scenario:adversarial -- --out work/NEW_SCENARIO
npm run test:scenario:adversarial -- --lifecycle-only --out work/NEW_LIFECYCLE
npm run build
npm run preview -- --host 127.0.0.1 --port 4280 --strictPort
```

In another terminal, from `frontend`:

```powershell
$env:QOIMA_TEST_BASE_URL='http://127.0.0.1:4280'
npm run test:pages:adversarial
```

Use fresh output paths. Scenario output paths resolve from the repository root. Browser checks require installed Chrome and hardware WebGL; their Windows D3D11 setup does not certify other platforms. `QOIMA_PAGE_CASES` optionally selects exact comma-separated browser case names.

## Boundaries and historical failures

This is bounded regression coverage, not a proof that the entire repository has no bugs. Native streams in the new tests are synthetic fixtures with recomputed member hashes; no new backend capture or primary ADR0099 was available. Persisted `pagehide`/`pageshow` events are dispatched guard tests, not native BFcache navigation certification. Extra demo crew, vehicle traffic, pace and deadlines remain illustrative, with operational admission false.

The old `check-twin-scenario-v3.mjs` is not counted as passing: its Node import fails on the current busy-shift source epoch. Later old short-episode assumptions were source-reviewed only. Existing historical fixture-epoch limitations from the prior delivery remain separate.

Early browser harness startup waits and a global one-canvas assumption were corrected: Twin legitimately has separate river and minimap canvases, so the final assertion checks only `#tw-viewport canvas`. Early scenario checker assumptions and its first wall-time timeout are explicitly classified in `scenario-index.json`. Raw reports remain unchanged; these harness issues are not counted as product bugs.

The Codebase Memory graph was consulted at generation `2026-11-08T05:55:56Z`; relevant current files were not tracked. Exact source fallback was used. No extra graph or Obsidian update was triggered.
