# 0001. SimPy is the time scheduler only

Status: accepted, 2026-11-07.

## Context

The spec requires a strict event order `(at_s, phase, seq)`, atomic conveyor ticks, snapshots every 30 s, and seek.
SimPy `Resource`/`Store` callbacks resume processes in insertion order. They do not know our phases.
SimPy generator frames cannot be serialized, so state inside them cannot be snapshotted.

## Decision

- SimPy owns only the future-event queue and the clock.
- Every scheduled item goes through `PhaseScheduler`, which calls `env.schedule(event, priority=phase, delay=ticks)`.
  SimPy 4.1.2 orders its heap by `(time, priority, eid)`, so the phase is the priority.
- Event callbacks call synchronous domain handlers. Handlers mutate plain `@dataclass(slots=True)` state only.
- Business resources (pickers, totes, buffers, pack posts, shippers, forklifts) are explicit state machines, not `simpy.Resource`.

## Consequences

- A snapshot is a serialization of dataclass state plus pending scheduler descriptors.
- Tests can drive handlers without SimPy.
- The `PhaseScheduler` adapter is the only SimPy-specific code and has its own unit tests.
