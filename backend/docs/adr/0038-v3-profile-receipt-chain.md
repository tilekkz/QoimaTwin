# ADR 0038: Receipt-then-ship chains and compiler admission parity

Status: accepted for the bounded backend manual proposal. It extends ADR 0032
and does not change the frozen four-job demo or its bytes.

## Received HU, then outbound

ADR 0031 allows "the same received HU may have a later outbound job". The source compiler
now admits that chain:

- Each HU has exactly one origin: an initial placement or one timed receipt. Each HU has at
  most one job per direction.
- A receipt with `receipt_template_hu_id` creates one new HU identity. Its SKU, quantity,
  archetype, mass and geometry are copied once from the source template. A later outbound job
  names the same new HU ID and carries no template, so no second clone or quantity exists.
- The outbound slot must equal the HU origin slot: the initial slot or the receipt target.
- The outbound arrival tick must not precede the receipt arrival tick. Equal ticks are
  allowed. The engine then waits deterministically until the HU is in stock. Nothing is
  skipped and no time is invented.
- Receipt targets stay initially free and unique under the conservative ADR 0032 rule. There
  is no dynamic slot reassignment or replenishment.
- Source pools, conservative module payload (initial plus receipts) and exact connector and
  route admission are unchanged.

With the default demo boundaries (H = 600 s), adding a shipment of `synthetic:HU:receipt:1`
at 120 s ends honestly partial: both shippers are busy until about 401 s, and the service
cannot finish by H. The chain test therefore declares explicit test-only boundaries
(H = 3600 s). The default profile and workload are unchanged.

## Admission parity and numeric text

- `compile_manual_profile` runs the engine's `validate_profile` on its own output. A compiled
  profile can no longer pass the compiler and then fail engine construction. Example: a
  buffer place ID equal to a storage-slot ID.
- Synthetic numeric choices must be plain finite decimal text matching
  `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]{1,3})?`. Fraction, underscore, whitespace and
  leading-plus spellings are rejected. Exponents have at most three digits, so the text cannot
  force a huge exact integer. Ordinary decimal and exponent spellings remain valid.
- The input hash binds the exact explicit proposal text and provenance. Two legitimate
  spellings of one value may therefore have different IDs.

## Unchanged by this ADR

The ADR 0032 calendar ceiling stays as is: an arrival at 1.0000001 s becomes tick 1000001.
The fixed (tick, job ID) tie-break also stays. An earlier review recommendation to reject
off-grid timestamps is superseded and is not adopted. A strict-grid policy would need a
separately versioned proposal.
