# ADR 0062: Registered whole-HU HTTP execution and immutable evidence

Status: Proposed backend capability; no shared frontend contract approval.

## Context

ADR 0056 executes bounded SMALL/STANDARD whole-HU operations on the same clock,
workers and inventory as receipt and unit flow. ADR 0058 publishes their native
observations; ADR 0061 binds reviewable public choices to exact source-derived
inputs. The local API must preserve these identities and the existing single
owned calculation slot.

## Decision

Expose one server-registered `explicit-standard-receipt-whole-v1` profile under
`/api/v3/whole-profiles` and `/api/v3/whole-runs`. A request selects the profile,
source revision and layout version. Paths, clocks, material recipes, worker
settings, quantities and other overrides are rejected. Registration is lazy;
application startup does not run a compiler or simulation.

Registration stores exact source/provenance/conveyor bytes, normalized public
choices, the ADR 0061 request receipt and the ADR 0058 input envelope. Validation
recompiles choices against restored authoritative source inputs and requires
byte equality of choices/request/inputs plus native and physical input hashes.
Every access rehashes stored dependencies. A bounded cache holds only immutable
validated metadata bytes; it never authorizes changed source bytes or metadata.

The `whole-v3` job uses the existing `JobService` and owned worker process. Client
cancellation retains the shared slot until the job ends. The worker restores
registered source files, verifies their public/physical binding before the
engine, invokes the existing CLI pipeline and publishes the semantic reference
last. Failed attempts retain sanitized type-only failure evidence, with no
successful run/request cache entry. No second calendar or inventory is added.

The native publication remains nested under `run/`. Its original descriptors,
bytes, hashes and run ID are unchanged. The public index has separate native
`files` and outer `request_files` (`profile.json`, `request.json`, `result.json`).
The public run ID additionally binds the immutable registration and API,
engine, compiler and publication versions. The outer result must agree with
native status, metrics, capabilities, counts and input hashes. Recorded path
strings are provenance only and are never interpreted as read locations.

Readers rehash the full authorized inventory before using a bounded immutable
semantic-validation cache. They reconstruct and validate the strict native
whole publication and its outer evidence. Whole terminal status includes paid
return: shipping at a cap does not imply completion while a worker lease remains.
The HTTP interface offers exact captured checkpoints and observed half-open
event windows of at most 60 seconds. It provides no arbitrary seek or fabricated
interpolation. Raw file responses authorize only the registered run inventory
and return exact bytes with their SHA-256 as ETag.

## Scope and validation

This remains a bounded backend proposal: `operational_admission=false`, no
frontend adapter, no heavy handling admission and no full-V3 claim. The registered
example retains all 530 baseline HUs and 24 workers, and explicitly receives and
ships one 24-unit STANDARD HU. Tests use independently written hand timelines
and source compilation without a source DES. The saved ADR 0061 source artifact
may be read and published without rerunning its simulation; this is explicitly
artifact reuse, not an HTTP execution or determinism claim.

Shared API integration is limited to route attachment, the `whole-v3` job kind
and worker dispatch. Existing receipt/native namespaces and the three frozen
runtime/compiler/CLI packages remain unchanged.
