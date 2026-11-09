# N2 heavy inbound: complete offered-stream handoff

Use `app.v3.heavy_inbound_binding` to compile an explicit `WorkloadPolicy` and
nonempty tuple of `HeavyInboundReceipt` declarations. Each declaration names a
new job/HU, a consistent lot, a source SKU, a permitted source inlet and its exact
arrival tick. Quantity, mass, dimensions and orientation permission come only from
the fresh C10 source template. There are no timing or capacity defaults.

An illustrative declaration uses PALLET SKU `DEMO_172`, `IN_W_BULK`, two distinct
job/HU IDs and one shared lot. Each source HU contains24 units and weighs455 kg.
Two additions therefore offer910 kg. This is a declared synthetic input example,
not received stock or a throughput promise. The source initial530 HUs do not move.

The result retains complete immutable C10 input/assignment bytes, baseline
TimedWorkload/bytes and all baseline offered jobs. `postshift_jobs` appends the
new receipts while retaining every old identity, arrival and quantity. It records
per-class/inlet count increments and added mass. It does not rerun quota allocation
to replace unrelated offers. Future baseline/candidate arms must use identical
postshift offered bytes and common physical/resource assumptions.

The public compile/load/verify boundary reopens raw pinned source and reconstructs
all values. Caller-modified templates, counts, offered rows or flags do not become
authoritative after rehashing. The analytical augmentation helper is suitable for
the independent2→4 PALLET oracle but cannot supply public source authority.

Every artifact keeps accepted receipt count0, operational admission false and
full N2 acceptance false. Source orientation is a permission, not an actual staged
pose. Shared lot consistency is not receipt acceptance or readiness. Heavy-compatible
FLEX is absent from current source; this proposal grants none. Physical intake,
support, pickup, routing, target placement, resource ownership and paid runtime
must be completed separately before any operational comparison.

See ADR0086 for exact identity, source and comparison boundaries. No existing
publication namespace, reader, source package, frontend or shared contract changes.
