# ADR 0075: Separate native publication for paid manual relocation

Status: accepted for the bounded backend extension; not frontend/shared-contract agreement.

## Context

ADR0073 introduces one paid, intact SMALL/STANDARD transfer on the existing
coordinator clock, workers and stock ledger. ADR0074 permits a jobs-only N1 pair
over exactly equal common inputs. Original coordinator publication has closed
types, resources and effect rules. Its successful validation does not establish
the meaning of an additional relocation event or derived storage location.

## Decision

Keep original coordinator models, constants, payloads and input bytes unchanged.
Publish this extension under `qoima-relocation-run-0.1.0`, with transport
`qoima-relocation-run-bundle-0.1.0` and metrics
`qoima-manual-relocation-metrics-v1`. Native identity includes the complete input
hash and the relocation engine, publication and metrics policy versions.

Source inputs retain their verified common coordinator bytes, explicit actor
grant, job, source-derived place definitions, three directed paths, handling
clocks, rounding rule and H/end boundaries. Analytical inputs use the separate
`qoima-relocation-hand-inputs-0.1.0` envelope and must contain analytical common
inputs. Neither a hand fixture nor its caller-supplied flag can impersonate
source-bound admission. Loading validates and reconstructs the immutable plan;
it does not execute the scheduler.

An empty job list preserves the exact original `CoordinatorOutcome` and uses an
explicit `base_noop` discriminator. A nonempty plan requires exact relocation
event, snapshot and outcome types and the `relocation` discriminator. There is
no implicit downcast that can discard the extension and pass the old reader.

Compact snapshots contain mutable stock/custody, claims, resource leases,
workers, relocation progress and derived source locations. Immutable HU recipes
and unit ancestry are reconstructed from the original input authority. The
codec validates exact scalar and record types, including rejection of Boolean
aliases for integer clocks. This format check is separate from causal acceptance.

The data-only journal preserves the complete coordinator checks for inventory,
workers, roles, units, goods, belts and resource capacity. Its extension couples
every take/place delta to a unique completed declared operation, checks the exact
claim and resource set, derives subsequent storage locations from completed
transfers, and retains custody and reservations through a paid return. It checks
all captures and completion boundaries. Rehashing forged events or captures does
not replace this validation. Native readers do not call an engine.

Admission removes every service gate for the declared relocation sequence. At
each settled boundary, the next positive-duration operation must therefore
already be open at its planned start, including after take and place. A forged
idle interval cannot postpone this work while retaining the valid claim, stock
owner and leases. Zero-duration steps must already have settled at that tick.

Publication recomputes identity, metadata and metrics from those validated facts.
Canonical-byte equality is required for derived metadata; Python equality alone
would treat Boolean `true` as integer `1` and `false` as `0`.

Relocation metrics report separate H/end counts and clipped paid intervals on
`[0,T)`. Their paid total is a labelled subset of the common workers' labor, not
an additional charge. Pair net labor must compare the two common paid totals;
it must not subtract the relocation subset a second time. No-op, partial and
worse outcomes remain valid and must retain their observed status.

Transport keeps 60-second half-open event chunks, settled captures, exact file
sizes/hashes, a closed file inventory and manifest-last publication. It uses its
own version admission and the complete native reader, even where generic byte
IO and chunk descriptor checks are shared with the coordinator implementation.

## Acceptance and limits

The independent hand example has directed travel of 2, 3 and 5 metres at 1 m/s,
take time 2 seconds and place time 1 second. Thus take completes at 4 seconds,
place at 8 and paid return at 13. Cuts before and after each boundary retain the
actual owner, claim and reservations. At H10 the common paid total and relocation
subset are both 10 seconds; at return both are 13, not 26. A competing whole job
must use the actual new source after return, while an earlier whole claim blocks
relocation. These are hand arithmetic expectations, not source-run measurements.

Tests cover exact-type mutation, omitted/reordered effects and resource facts,
unknown immutable references, changed plans and metadata, no-op payload equality,
and retained source authority. Source execution, measured transport size, A/B
outcomes and frontend adoption require their own evidence. This extension does
not add swap, heavy/long cargo handling, trained forecasting, interpolation,
engine restore or full V3 completion.
