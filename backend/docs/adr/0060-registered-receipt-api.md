# ADR 0060: Registered receipt runs through the shared API worker

Status: accepted for the bounded backend proposal, not an adopted frontend contract.

The receipt compiler and CLI already freeze explicit source choices and publish a
verified creation/claim history. HTTP access must use those same inputs, runtime
and immutable files. A second executor or a request-controlled file path would
introduce a different admission boundary.

Register `explicit-received-small-three-units-v1` lazily from the checked-in
receipt profile. Registration validates the original typed JSON before storing
canonical choices, exact compiled bytes, and every pinned source/conveyor file
by content hash. Requests contain only the registered profile, layout version and
source revision. Quantity, clocks, paths and other overrides are rejected.

Use the existing `JobService` and owned process processor with a `receipt-v3`
job kind. V2, manual, light and receipt jobs share one active calculation slot.
A disconnected client does not cancel the calculation or free its slot. The
child restores verified input files, invokes `simulate_receipt_file`, and checks
the resulting native run against the registered input hash before publication.
Failed attempts retain frozen evidence and a sanitized failure record.

Expose `/api/v3/receipt-profiles`, `POST /api/v3/receipt-runs`, and reads for
status, manifest, content-addressed files, exact captured checkpoints and
observed half-open event windows of at most 60 seconds. No arbitrary replay or
interpolation is implied. Native run bytes stay identical to CLI output. A
separate public run ID binds the native run, frozen registration, engine,
compiler and export versions under `qoima-v3-receipt-api-1`.

Before serving results, rehash the registration and complete artifact inventory,
check exact native/public/input identities, and invoke the receipt reader's
schema and semantic validation. A bounded cache retains only immutable summary
bytes. Every request still checks raw stored bytes; previously validated history
does not authorize changed files. Cached submission responses must equal the
actual verified result, including partial status and capability flags.

This reuses the existing registered API pattern without broadening the old
manual or light namespaces. It adds no credentials, inference requests, source
geometry changes or inventory mutation outside the single simulation. The
profile remains an explicit bounded SMALL receipt-to-unit example. Other cargo
classes, general physical human handling, full warehouse operation and an
agreed C12 adapter require their own evidence and remain unclaimed.
