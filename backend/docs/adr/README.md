# Architecture decision records

Each record freezes one backend decision. Records 0001-0009 were accepted on 2026-11-07 at H0.
They come from the spec review in `../research/` (Claude, Codex main, Codex edu).
Record 0007 changes the shared contract and needs Tilek's agreement before files in `contracts/` change.

| ADR | Decision |
|---|---|
| [0001](0001-simpy-as-clock-only.md) | SimPy is the time scheduler only; business state lives in dataclasses |
| [0002](0002-exact-integer-time.md) | Exact integer ticks, 3,000,000 per second |
| [0003](0003-phase-ordering.md) | Five phases inside one timestamp |
| [0004](0004-atomic-conveyor-tick.md) | Atomic conveyor tick with round-robin merges |
| [0005](0005-single-ledger-transaction.md) | One transactional inventory ledger |
| [0006](0006-pallet-state-machine.md) | Pallet state machine and timer generations |
| [0007](0007-contract-v2-1.md) | Contract v2.1 proposal for the run export |
| [0008](0008-run-identity-hashing.md) | Run identity from canonical JSON hashes |
| [0009](0009-spec-ambiguity-resolutions.md) | Resolutions of spec ambiguities |
| [0010](0010-replay-snapshots-and-chunks.md) | Settled replay snapshots and half-open event chunks |
| [0011](0011-metrics-boundaries.md) | Horizon/end observation windows and undefined statistics |
| [0012](0012-run-export-projection.md) | Schema-valid v2 projection and proposed run bundle |
