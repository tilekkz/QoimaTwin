# Visual replay v2

`index.ts` exports `createVisualFixture`, `adaptRunV2`, `createReplayController`, `createSfxController` and the frame/run types. Shared contracts are read-only.

```ts
const replay = createReplayController(createVisualFixture());
replay.play();
const frame = replay.advance(realDeltaSeconds);
// Apply logical pos/yaw, then cosmetic pose to the named rigid joints.
// Send frame.events to SFX only once, using this returned frame.
replay.pause();
const sought = replay.seek(120); // events=[], never replays sound
replay.setRun(adaptRunV2(parsedInlineRun));
```

Clock methods: `play`, `pause`, `seek`, `reset`, `setSpeed`, `setRun`, `setReducedMotion`, `advance`, `getFrame`, `getState`, `getRun`. `getFrame` is always silent. Actions use `[start,end)` and events use `at_s<=t`, sorted by time/phase/seq. Intervals, paths and cargo states are indexed; backward seek samples the same precompiled timelines rather than replaying side effects. Business snapshot payload remains opaque; its events are compiled once at load.

The 500-second **VISUAL DEMO** has 24 persistent actors and one scripted order. It uses the full 72×48 layout: existing picker/forklift graph edges, directed belt paths, 1.2m/s walking, 2m/s vehicle travel, 1m/s belt motion. A six-second scripted belt hold demonstrates a stopped tote. Shipping pallet sealing waits 300 seconds after first placement. This is neither DES nor an inventory ledger, optimizer, backend result or KPI comparison. Receiving/shipping manual connectors are explicitly marked `visual-service-connector` inside their zones. No shared graph edges are added.

Cargo has one explicit world/actor/vehicle/cargo attachment. A second pass resolves parent cargo, rotated offsets and inherited visibility independent of definition order. Tote base is Y=.553 on the cart floor; `anchor:'cart'` uses the last travel heading while the person turns toward a rack. `cartYaw` is available to the scene. Parcel remains visible at pallet-deck offset Y=.14. Asset fitting uses fork contact lift .071m and carriage lift .171m for pallet base Y=.10; it does not modify business coordinates or quantities.

Motion uses bind-relative runtime Euler XYZ on `torso`, `head`, `upper_arm_L/R`, `forearm_L/R`, `hand_L/R`, `thigh_L/R`, `shin_L/R`, `foot_L/R`. Picker arms retain the cart grip during walking. `pose.rootOffset` is a cosmetic world offset; the .55m pick reach and waist stoop for the low bin leave graph position unchanged. Wheel angle derives from cumulative path distance, so stops and seek preserve it. `pose.lift` is a mechanical carriage height in metres. Reduced motion removes decorative movement while preserving state and lift. Drivers remain seated in their two vehicles and are not extra pedestrians.

`adaptRunV2` supports actor intervals, ordered events and directed cell locations. Payload schema is currently generic; missing cargo placements/attachments are reported through `warnings` and remain hidden rather than being fabricated. Optional exporter payload `pos`, `stage`, `attachment` is supported. Metrics are never recalculated. This is an integration boundary, not a claim of complete ledger/snapshot/backend support.

SFX starts muted and requires an explicit user-gesture `unlock()` plus `setMuted(false)`. Volume and category preferences persist; startup still stays muted. Original procedural sine/triangle cues, seeded noise footsteps/tape and an aggregated quiet motor/belt loop use no external recordings. Categories: ambience/mechanical/feedback. The total bus, including its loop, is limited to four voices. Per-source cooldown, deduplication and accelerated-playback summary gating limit event floods. Pause, mute, seek/reset discontinuity and dispose stop voices; seek never emits old one-shots. Automated tests use mute or a fake AudioContext and produce no speaker output.

Pure deterministic tests (no browser or Vite server):

```powershell
npx.cmd playwright test --config src/replay/replay-core.config.ts
```

The suite covers clocks/seek, event boundaries, blocked cargo, graph routes, all actor IDs, parent cargo on loaded turns, fork contact, pallet timeout, cart anchoring, reduced motion, adapter boundaries and silent audio limits. Browser contact/animation review and device performance measurements are separate checks.
