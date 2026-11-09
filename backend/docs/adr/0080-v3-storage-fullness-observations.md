# ADR 0080: Source storage fullness as a separately identified observation

Status: proposed backend read model. Shared contracts and frontend adoption are unchanged.

## Context

V3 design sections 2 and 5 require actual occupied places and separate volume and mass
utilization. The coordinator already preserves current inventory and source capacities.
Its material-pool free-place metric is not warehouse storage fullness. A physically empty
slot can be blocked, reserve-only, or held by an admitted placement operation.

The pinned initial source has 776 physical slots, 588 active geometric candidates, 530
occupied slots and 188 blocked reserve slots. Therefore 246 physical empty slots and 58
active empty slots are different quantities. None grants a cargo-specific operation.

## Decision

Introduce `qoima-storage-fullness-observation-0.1.0` as an opt-in read model, without changing
existing native coordinator run bytes, metrics policy or shared schemas. Its source adapter
reloads and authenticates the pinned raw V3 bundle, checks the profile revision and exact
immutable source fingerprint pairs, and matches every source storage owner and HU capacity.
Dimensions and masses use exact rational values. Usable volume is the product of the three
usable dimensions; a rounded reported source volume is not used as the denominator.

For each observed settled state, count physical containers at each source storage owner.
An empty retained wrapper still occupies its slot and its full outer bounding volume.
Units, packaging and contents mass come from the existing inventory reducer and must match
native stock balance. Non-slot custody, including workers, vehicles, buffers, the belt,
shipped owners and material pools, is excluded from storage totals. A completed physical
ownership change changes fullness; a proposed assignment or future receipt does not.

Publish slot, module, zone and total rows. `occupied_fraction` uses all physical slots;
`active_occupied_fraction` uses active geometric slots. Mass uses exact occupied cargo gross
mass divided by summed slot payload limits; module payload and HU ceilings remain separate
constraints and separate module ratios. Volume uses container outer volume divided by
usable slot volume, without adding unit volumes already inside those containers. A missing
denominator produces null, not a synthetic zero fraction. Ratios are fractions, not rounded
percentages; clients may multiply by 100 for display.

Current `receipt:place:`, `whole:place:` and `relocation:place:` leases identify reserved
storage slots. Occupied and reserved may overlap while an action retains its lease. Those
counts must not be summed as disjoint categories. `unreserved_active_empty_slots` subtracts
held placement reservations from physically empty active slots. Unknown source slot leases,
unrecognized storage place namespaces, duplicate leases and conflicting placement claims
are rejected. This quantity does not establish dimensions, handling, path or actor admission.

The low-level reducer accepts explicit analytical capacities. The coordinator adapter
requires an already validated native observation and does not itself validate event
causality. The public report builder first performs full native coordinator validation,
then computes `at_horizon` and `at_end` independently. Its report identity hashes the entire
report body, including policy version, source run identity, input hash and canonical native
run hash. The report validator reconstructs the whole result and compares canonical bytes;
rehashing altered metadata, extra fields or Boolean/numeric aliases cannot certify it.

Analytical profiles without authoritative warehouse capacities return unavailable. No V2
864-address denominator is silently applied. Source interpretation and operational admission
remain unchanged; every report declares `operational_admission=false`.

## Validation and limits

Independent hand arithmetic covers physical versus active denominators, empty wrappers,
occupied/reserved overlap, multiple zones/modules, module ceilings, exact types, ordering
and zero active capacity. Source tests use raw pinned counts and explicit ledger transfers,
not expected numbers copied from a simulator. Peer tests reproduced mutable inner source
fingerprints and string-subclass aliases; the exact pair/string guard closes both cases.

Native report tests retain the original run and reject corrupted source identity and
rehashed summary forgeries. A geometry-volume ratio never proves packing fit, orientation
or route feasibility. This addition supplies a backend read model; exposing it through an
agreed frontend adapter/API remains a separate delivery step. No source DES, frontend
integration, full V3 acceptance or existing publication migration is implied by these tests.
