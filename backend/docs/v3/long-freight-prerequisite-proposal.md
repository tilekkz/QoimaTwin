# N3 LONG freight: bounded input and missing-proof handoff

This proposal implements ADR0084's static prerequisite interface. It is not a
runtime job or permission to move cargo. Existing C65/N1 publication and readers
are unchanged; a later operational/export interface needs its own version.

Use `app.v3.long_freight_binding` with an explicit request:

| Field | Value |
|---|---|
| hu_id | `v3:HU:initial:DEMO_180:01` |
| source_slot_id | `v3:slot:LONG_W:002:L1:B1` |
| target_slot_id | `v3:slot:LONG_W:001:L1:B1` |
| orientation_id | `upright_xyz` |
| port_id | `OUT_E_B2B` |
| pair_id / actor_id / vehicle_id | `OUTBOUND_FORKLIFT_PAIR` / `F02` / `FL02` |

Supply a separate explicit `WorkloadPolicy`; the interface supplies no count,
horizon, speed or handling defaults. It freshly materializes C10 and preserves the
complete offered stream and530 original HUs. It does not select an offer for this
HU or credit a future receipt. A separate downstream step must bind exact customer
work and current custody before claiming a supported N3 scenario.

The known candidate meets static source storage and C08 design prerequisites:
200 kg HU plus separate40 kg cradle, `(4.3,.62,.75)` required dimensions against
`(4.4,.65,.9)`, source B2B gate6×4.5 m and declared210 s port-service component.
Stored inventory mass remains200 kg. Original pose/axes and assignment bytes are
preserved; no new frame, tilted orientation, gate, attachment or worker is invented.

`static_rejected` explains incompatible known choices. A source-consistent choice
returns `prerequisites_only`, seven structured missing-proof obligations and false
operational/full-N3 flags. Missing authority includes actual pickup/cradle lock/
retention/setdown, loaded route and gate sweeps, initial actor/vehicle state,
joint reservations, clocks, finite customer staging and handoff. These blockers
cannot be cleared by setting a Boolean or supplying a hash.

Freeze `frozen_bytes` and `input_hash` together. Public load/verify reopens pinned
raw source, rematerializes all offers and reconstructs every derived value. An
artifact whose hash has been recomputed after changing source facts, result flags,
arrival rows or static evidence remains invalid.

The next physical task must select one precise obligation and preserve its original
HU identity, actual meshes and signed transforms. The existing PALLET/F02 proofs
are related prerequisites, not substitutes for LONG cradle/contact or gate travel.
