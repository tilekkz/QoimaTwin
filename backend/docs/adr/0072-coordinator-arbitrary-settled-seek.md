# ADR0072: arbitrary settled-state seek for coordinator namespace3

Status: code-only implementation draft; tests written first, execution deferred by user.

## Decision

`replay_coordinator(run, *, inputs: bytes, tick: int)` returns a frozen native
CoordinatorSnapshot at any exact integer tick from0 through observed_until_tick.
It first invokes the C65 strict native authority, rebinds canonical inputs, then
reduces every recorded event with tick <=T in actual sequence order. All phases at
the cutoff are included. The watermark is the last applied seq, or-1 for an empty
prefix. Boolean/noninteger/negative or future ticks fail explicitly.

Replay creates a fresh data-only journal from the original frozen stock and
definitions on every call. It never executes or restores CoordinatorEngine, a
scheduler, callback, random generator, arrival stream or future completion.
Full-run verification may inspect later facts for authenticity; only prefix events
mutate requested state. Current captures are consistency anchors, not inventory
bootstrap inputs. Their intentionally compact mutable contents do not carry
transaction history needed to safely manufacture a resumed authority.

## State and time

The projection retains the actual common inventory, registered receipts and ancestry,
claim generation/claims, all24workers, every physical cart, unit contexts/progress,
packing and waits, receipt/whole handovers, role assignment/exposure and all current
resources. The old default-cart field remains an alias of its actual map member.
At movement cuts, worker node is None and its real operation/route/planned end
remain explicit. No future observed end is fabricated. Paid and waiting counters
and role exposure integrate only[0,T); counts and handovers include settled events atT.

Conveyor pose uses the existing source-compiled BeltMotion and exact Fraction
observation model. Replay adds no world-coordinate interpolation, worker animation,
forklift chord/tangent, mesh/contact proof or caller transform. New receipt units
are absent before actual service credit even though their immutable definitions
exist in inputs. Backward seek reconstructs a new authority and cannot retain them.

Projection uses the same journal structures as C65 and is checked against its
invariants. Existing captured ticks, H and end must match original observations.
A small readonly `UnitJournal.progress()` delegates existing progress arithmetic;
the validator uses that helper without changing its behavior. No existing codec,
run identity, namespace, output manifest, captured API route or runtime changes.

## Verification plan and limits

Prewritten hand tests cover role outward102/104/105 and paid return158/160,
receipt credit12/putaway23/return33, whole shipment47/return52, two current carts
and picks83..86, all original captured cuts, repeated/backward seek, raw-input
immutability, strict tamper rejection and a guard against calling Engine.run.
The numbers come from declared hand geometry/operations; no replay execution has
supplied expected values. An independent adjacent picker/cart return case may
be added by the separate reviewer.

This initial implementation revalidates the full native input/run and reduces the
prefix from initial authority. It makes no latency, bounded-memory, source-scale
throughput or checkpoint-acceleration claim. A future certified journal cursor is
a separate design. API/CLI arbitrary-cut admission is a later explicit integration;
current routes keep their captured-only contract until then.

All new runtime/static checks are NOT_RUN_USER_DEFERRED. This draft is not full V3,
frontend adoption, physical motion certification or a successful execution gate.
