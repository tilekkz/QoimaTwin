# ADR0095: Forecast-bound relocation through the existing local API worker

Status: Implemented bounded HTTP orchestration; actual source/process acceptance and release gate pending.

The planning API publishes authenticated forecast/stock/placement decisions, and ADR0093 binds a
saved decision to separately frozen actual common inputs. This increment makes that existing bridge
available through the same `JobService` and `ProcessProcessor`. It adds no engine, scheduler, worker
pool, allocation algorithm, native schema field or economic rule.

`GET /api/v3/forecast-relocation-profiles` performs an uncached read job. Inside the owned worker it
compiles the same allowlisted `coordinator-profile.example.json` used by the coordinator API, freezes
its existing registration evidence and common inputs, and publishes an immutable outer profile
handle in CAS. The response includes the recipe hash, registration identity, original bounded
metadata (including H/cap and synthetic choices), required acknowledgement and an explicit absence
of engine execution. The recipe's currently declared H is 900 seconds. No caller override of that
recipe, source path, H, cap, staffing, timing or future workload is accepted.

`POST /api/v3/forecast-relocation-runs` requires the new schema version, an existing offer-plan
`request_id`, the returned `actual_profile_id`, explicit `job_id` and `arrival_tick`, pinned source
and layout, and exact `acknowledge_bounded_manual=true`. The offer request ID is distinct from the
public planning ID and from predicted offer IDs. Arrival retains the existing bridge/native rules.
The HTTP admission path only checks closed declarations and raw CAS/source bindings; source
compilation, forecast numerical validation and execution occur in the existing worker.

The worker recompiles the current allowlisted recipe and compares the entire resulting handle with
the requested one. A separately valid, repinned common profile cannot substitute for that recipe.
It then freshly authenticates the saved planning bundle, obtains its exact decision bytes, and
freezes request, decision, actual common and registered profile evidence before dispatch. The
existing `prepare_forecast_relocation` checks source, H, all original stock/placements, selected
actor home/speed/capacity and permissions, customer choices and priced route/handling facts. A
planning H of 1000 seconds and actual H of 900 seconds is rejected; this endpoint does not silently
retime the forecast or the actual workload. It does not join a predicted offer ID to an actual job
or reprice against future actual demand. All predicted offers, B2B and shortages remain in the exact
decision/outer input, including legitimate negative/no-op decisions. A no-op creates empty
relocation jobs in both arms through the existing bridge.

`compare_forecast_relocation` claims a fresh output and freezes the outer input before invoking
the existing normal pair executor. The executor remains the only owner of the two existing native
arms. The API publishes only after validating their complete closed raw inventory, strict native
readers, exact correlated input bytes and rebuilt comparison report. It also checks the CLI outer
manifest. Both ordinary empty-job/base outcomes and explicit relocation outcomes use their existing
typed restore functions. Native payloads and identities stay unchanged: distinct forecast no-ops
may share physical native IDs, while the outer experiment/request identity remains distinct.

`GET /api/v3/forecast-relocation-runs/{run_id}/result` and `/files/{artifact_id}` use fresh worker
read jobs. They repeat current profile, planning, bridge and native authority checks. File return
requires exact membership and raw hashes and returns original bytes without JSON/base64 rewriting.
Repeated POSTs use the planning v2 `cached_read` admission path, return fresh typed authority and
retain one producer. If publication survived a lost request receipt, recovery authenticates it
without running the pair again. Reads never publish request-cache receipts and retain the existing
cancellation/shutdown ownership rules.

Calculation completion is separate from the comparison's `complete` or `partial` status. The
complete unfiltered comparison is retained, including both arms' raw business/resource boundaries
and paid-cost accounting. No partial result is promoted to completed business work or positive
gain. Failed attempts retain frozen inputs and partial files without publishing a successful run.
The endpoint explicitly claims neither operational admission nor full N1 acceptance.

Short tests use finite profile/registration/bridge/producer/native-reader doubles with all real
source/forecast/engine entrypoints guarded before application creation. Their H-rejection control
verifies error propagation; real source H/actor/stock binding remains the existing bridge's
authority, not a new numerical oracle. Initial route controls read unrelated legacy bootstrap
contracts; final controls replace that bootstrap with a finite `ApiContext` double. No real source
load, HGB, DES, process worker, live HTTP server, full suite or benchmark is claimed here. Those
acceptance checks remain final-phase work. Existing frontend/contracts and frozen release roots
are unchanged.
