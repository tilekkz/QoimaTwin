# 0005. One transactional inventory ledger

Status: accepted, 2026-11-07.

- Stock is kept as integer quantities per `(sku_id, lot_id, location)`.
- Locations: Pickface, ReserveSlot, ReceivingArea, InboundVehicle, ReserveStaging, Tote, PackWip, Parcel, Dispatched.
- A pallet refers to its parcels. Units are counted only in parcels, never again in the pallet.
- A reservation is a claim on existing on-hand stock: `0 <= reserved <= on_hand`.
- `StateTransaction` is the only mutation path: validate, build the delta, apply, check conservation
  for the affected SKUs, then emit events.
- A whole-order reservation is all-or-nothing. A failed transaction leaves the state unchanged.
- For every SKU at every settled timestamp:
  `initial + accepted_receipts = pickface + reserve + receiving + reserve_staging + tote + pack_wip + parcel + dispatched`.
- Tote pool: the available and allocated sets are disjoint and their union is always `T001..T096`.
