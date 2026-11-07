# ADR0041: exact unit ancestry and explicit packaging material inventory

Status: backend bounded implementation; no shared contract agreement implied.

## Context

C02 defines individually packed units separately from their outer handling-unit wrapper.
For SMALL_CARTON, each packed unit has 0.03 kg contents and 0.005 kg primary tare;
the original outer HU has 24 units and 0.10 kg additional tare. Removing three units
therefore leaves 21 * 0.035 + 0.10 = 0.835 kg in the original HU, not 21/24 of 0.94 kg.
Primary packaging follows its unit; the original outer packaging cannot follow every split.

The pinned `cargo-catalog-v3.json` and `baseline-assignment-v3.json` at 22296bc contain
530 HUs and 12256 units: 440 SMALL, 55 STANDARD, 6 HEAVY, 5 PALLET, 3 IBC,
8 LONG, 5 DRUM and 8 FRAGILE. Independent decimal arithmetic gives 8342.4 kg contents,
443.2 kg primary packaging and 618.25 kg outer packaging, total 9403.85 kg.

There is no approved operational picking/packing material pool. The visual tote heights
and old/new cart proposals cannot establish tare, capacity, usable internal volume or
availability. Latest P03.2 nominal upper deck height 0.62 m and tote outer height 0.34 m
also do not authorize the older 0.66 m deck proposal. STANDARD whole-HU dimensions do
not fit the proposed tote interior; visual scaling is not a handling recipe.

## Decision

Use immutable source unit tokens `(origin HU, SKU, lot, ordinal, packed unit recipe)`.
Every token occupies exactly one registered physical container. The original HU wrapper
is a container with a single immutable outer tare and original outer dimensions. Its
remaining gross mass is its tare plus the exact gross masses of remaining unit tokens.
Original full-HU packing is opaque validated source evidence; no initial unit coordinates
are invented. Every original wrapper remains registered even when empty or disposed.

New carriers and packages must be declared as initial material inventory before the ledger
is created. Each material ID has an explicit versioned recipe ID, provenance, outer and
inner dimensions, tare, maximum gross mass, maximum units, clearance and allowed classes.
The ledger chooses no global tote geometry, default pool, wrapping tare or packaging recipe.
Recipes with the same ID must be identical. New wrappers cannot be created by pick or pack.

The supported transaction grammar is source SMALL unit pick into a carrier; carrier-to-carrier
transfer; carrier units into an already registered empty package with an order ID and sealing;
sealed package shipment; material-container ownership relocation; and explicit empty-original-
wrapper disposition. Other source cargo classes remain represented but unit execution is
rejected. This preserves a safe boundary for a future explicit STANDARD direct handling path.
There is no nesting, opening sealed packages, reverse shipment or discarding units.

Each destination unit has an explicit exact upright placement. Only floor-supported units
are accepted; exact axis-aligned boxes may touch but may not overlap. Caller-declared side
and top clearance must hold; floor support uses zero vertical gap. No rotations, stacking,
epsilon tolerances or geometry scaling are inferred. A recipe is an explicit caller proposal,
not a claim that this layout fits a real cart or that equipment is available.

Owners are declared typed finite-capacity locations. Original storage slots each have one
position and only contain their original wrapper. Source wrappers cannot be relocated into
arbitrary slots through this API. Material relocation records an ownership effect only;
it proves no movement path, worker capability, travel time or source storage admission.
Shipment and disposal are terminal locations. Disposal accepts an empty original wrapper
and retains its tare in the disposed mass account; it never deletes physical mass.

Every mutation requires a unique transaction ID and the exact current revision. Validation
and full state checks run against staged immutable replacements before commit. A rejection
does not consume the transaction ID or revision and does not change history. A successful
transaction returns an immutable delta containing affected physical views before and after,
unit IDs, operation and revision. Views include unit ancestry/position, container recipe,
owner, seal/order identity and derived gross mass for later journaling or conveyor binding.

For every SKU, original units equal onsite plus shipped units. Contents, primary tare and
registered outer/material tare are separately conserved across onsite/shipped/disposed.
Fractions represent all ledger geometry and masses; the source adapter parses JSON decimals
directly as rational values. Boolean, float, negative and malformed physical quantities fail.
The checker retains the original frozen owner, token and material-recipe objects and requires
their identity, not value equality: Python considers `True == 1 == Fraction(1)`, which would
otherwise conceal forbidden type substitutions. Transactions never replace these authorities.
This requires no repeated source decoding and applies to the single serialized ledger owner.

## Consequences and limits

This is a pure transaction ledger without clocks, reservations, order allocation, receipt
credit, worker scheduling, conveyor ownership handoff or complete warehouse execution.
The existing whole-HU manual engine remains separate; running both against the same initial
stock without a future single ownership authority would double-account it and is unsupported.
Timed inbound workload intents do not create units here; unallocated outbound intents remain
unallocated until an explicit allocator selects stock. No implicit receipt or replenishment
is used to satisfy normal/peak workloads.

Tests use explicit synthetic material recipes and independent decimal/box arithmetic. The
complete source inventory test checks all 530 original wrappers and 12256 units; focused
failure tests verify rollback, exact geometry boundaries, exclusive owner capacity, immutable
ancestry, unsupported paths, terminal shipment and retained disposed tare. This is not a
validation of a real material fleet, an approved v3 wire schema or a throughput benchmark.
