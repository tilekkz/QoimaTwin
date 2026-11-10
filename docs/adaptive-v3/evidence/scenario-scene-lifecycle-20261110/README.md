# Native Scene lifecycle checkpoint

This is a bounded visual-fixture regression checkpoint, not engine admission, a new geometry certificate, or global H/Q completion.

Run from the repository root:

```text
node frontend/tools/check-warehouse-scenario-scene-lifecycle-v3.mjs
```

The checker uses the actual original 24 employees, 2 forklifts and 530 initial HU instances. Inputs come from canonical source/data/model paths; only generated caches and raw reports go under `work/`.

The 12 passing groups cover the existing six-workflow common-clock matrix, private factory/input guards, original 1800-second queue semantics, rejected wrong-SMALL/unprepared-Source rebinding with A still usable, cached route yaw/speed/points rejection, forward/reverse native route versus DTO parity, actual N1 shared-S02 ownership, and explicit not-ready/retry behavior after a later native constructor failure. Geometry, materials, original instance matrices and employee parent restoration are checked after disposal. Source hashes before/after the run are in `checks.json`.

`bind` now validates identities, prepared dependencies and every cached route before disposing/resetting controllers. If later native construction fails after teardown begins, readiness is explicitly cleared. Cached routes bind actor, points, initial yaw, speed and source-node identity.

Inactive native controllers apply before active owners. This matters when the unstarted SMALL factory and active STANDARD factory both retain the same original S02 object. The original N1 input sends both outbound requests to `OUT_S_EXPRESS`; it is not replaced by the separately tested optional retail variant. STANDARD retains its existing admission, SMALL queues honestly, and a refused SMALL case releases its provisional reservation hints. Actual finite leases and original deadlines remain unchanged.

The first raw failed checker attempt selected the unrelated R01 cached route while mutating a P01 request; it was retained under `work/`. The corrected test selects the actual P01 route. No runtime geometry or tolerance was changed to obtain a pass.

The existing separate contact, support, source LONG, tool and traffic proofs remain in their original scopes. These lifecycle checks do not extend the STD-only concurrency certificate to SMALL or claim arbitrary warehouse traffic clearance.
