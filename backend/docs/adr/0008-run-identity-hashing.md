# 0008. Run identity

Status: accepted, 2026-11-07.

- Canonical JSON: UTF-8, sorted keys, no NaN or Infinity, set-like arrays sorted by ID, ordered arrays kept in order,
  no wall-clock time and no file paths.
- `run_id = sha256(canonical_json(...))` over: canonicalization version, engine version, timebase, and the hashes of
  layout, config, actors, orders, receipts, stock quantities by SKU and lot, assignment, relocation plan,
  forecast snapshot, and experiment type.
- Stock quantities are hashed separately from their placement. A slot swap changes only the assignment hash,
  so A/B input equality still holds.
- The same inputs always give the same run ID and the same event stream.
