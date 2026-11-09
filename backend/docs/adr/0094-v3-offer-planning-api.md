# ADR0094: Explicit V3 offer planning through the existing owned API worker

Status: Implemented bounded planning API; release and actual source/HGB acceptance are pending.

The file-driven V3 planning pipeline existed without its required local HTTP entry point. This
increment publishes that complete planning capability through the existing `JobService` and
`ProcessProcessor`. The separately implemented forecast-to-relocation bridge remains available by
CLI. Its registered-common-profile execution endpoint is the next increment, not a partial route
or an execution capability claimed by this ADR.

`POST /api/v3/offer-plans` requires `schema_version=qoima-v3-offer-planning-api-1`, an explicit
`model` (`mean28` or `hgb`), the pinned V3 `layout_version` and `source_revision`, and exact boolean
`acknowledge_bounded_planning=true`. Four UTF-8 file strings are required: `history_csv`,
`history_choices_json`, `projection_choices_json`, and `placement_choices_json`. Their original
UTF-8 bytes, including JSON whitespace and CSV line endings, are retained in CAS. No server path,
implicit calendar, forecast future stream, buffer, actor, workload budget or economic rate is accepted
or invented. Existing closed choice decoders perform structural admission; full source and forecast
authentication remains in the worker. Source-semantic rejection is also a 422, without leaking the
internal exception text or filesystem paths.

The request snapshot binds the four raw file hashes, explicit source/model/acknowledgement and
producer versions. Its dedicated domain derives the public `planning_id`; legacy forecast/plan IDs
are not promoted into this namespace. The existing V3 `submit_job` path deliberately avoids the V2
layout and reference validators. The single owned process invokes the normal `plan_offer_files`,
then the normal typed `validate_offer_plan`. A closed twelve-file inventory and the exact original
API request are checked before immutable publication. The HTTP result includes logical file names
and content hashes, never server paths. B2B, all offered jobs, allocation shortages, no-op and
infeasible planning outcomes remain the producer's unfiltered result.

Repeated identical submissions reuse one producer result. The cached branch of `submit_job` selects
a fresh typed read in the existing worker and returns that authenticated result, after checking its
canonical equality with the saved receipt. This decision occurs inside admission, without a route
cache precheck or a mutable validation cache. A malformed receipt fails closed. The first producer
does not receive a second typed read; later submissions can increase validation calls without
increasing producer calls. The optional internal `cached_read` argument defaults to `None`, keeping
legacy callers' behavior. Every POST return also rechecks the saved raw inventory and result binding.
If a complete publication survives but the request-cache receipt was
not written, the worker freshly verifies that publication instead of producing a second bundle with
different CPU observations. A failed attempt retains its immutable request, caller files and partial
output under the existing store's private evidence directory; no successful result is published.

`GET /api/v3/offer-plans/{planning_id}/result` and
`GET /api/v3/offer-plans/{planning_id}/files/{artifact_id}` use a fresh read job. Unknown results and
nonmember files are refused. Every accepted GET rechecks CAS hashes, closed file/type/namespace and
request bindings, reconstructs a temporary ordinary bundle, and invokes `validate_offer_plan`.
That reader can numerically reconstruct the forecast, so it runs in the same process worker as
planning, never in the ASGI event loop. Raw files are returned as exact bytes; no JSON/base64
roundtrip or native schema change occurs.

The small `JobService.read_job` addition reuses its existing `active` task and `asyncio.shield`.
Reads are uncached, share the same busy admission policy, and never publish a `requests` receipt.
A canceled caller keeps the admission slot until the processor actually finishes; application
shutdown's existing `finish()` drains that task. There is no second worker pool, queue, semaphore
or detached task framework.

This planning API reports no engine execution, actual test stream, operational admission or full
N1 acceptance. HTTP routes, CAS boundaries and worker orchestration are covered by short tests with
explicit producer/typed-reader doubles and source/fit/engine guards. Actual process/source/HGB
smokes, full gates, relocation API execution and full N1/N2/N3 acceptance remain deferred to the
final phase. Existing frontend, contracts and native payloads are unchanged.
