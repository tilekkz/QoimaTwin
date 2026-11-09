# ADR 0099 Saved N1 pair publication and arm bundle stream

Status. Backend namespace and stream proposal implemented for separate focused review.
Release and source-run evidence belong to the exact subsequently verified candidate.

## Saved pair authority

The host command imports one completed standard N1 pair directory.

```text
python -m app.v3.relocation_pair_publication publish --pair DIR --store-root DIR
```

The importer captures a closed, bounded tuple of relative paths and immutable raw bytes.
Resolved source and store paths must be disjoint in both directions before capture or output.
Root and ancestor paths use the existing link/junction rejection helper. Members require
ordinary unshared files, safe relative paths, stable file metadata across capture and a
closed directory inventory. Bounds are 20,000 combined files/directories, 128 MiB per file,
and two native 1 GiB bundles plus four 128 MiB outer/manifest allowances in aggregate.
The native manifests determine the exact baseline and candidate transport membership.

A private temporary directory restores only captured bytes. Validation calls the existing
strict `load_relocation_pair_inputs` and both `read_relocation_run` entry points. Each arm's
frozen input bytes, input hash, common identity and manifest/native identity must match.
Outcome reconstruction follows `outcome_kind`. `base_noop` uses the coordinator projection
and `relocation` uses the relocation projection. Existing `build_pair_report` rebuilds the
comparison, whose canonical bytes must equal the saved `comparison.json` exactly.
Partial outcomes, observation boundaries, integer ticks and negative/no-op comparisons
retain the original native values and paid-labor accounting.

Publication provenance is `verified_saved_native_pair`. The response explicitly carries
`producer_attestation=false` and `full_n1_acceptance=false`. Execution-count fields remain
part of the original saved report. The import checks saved native evidence and input
correlation. Process-exit evidence and full N1 acceptance remain separate evidence.

## Immutable publication

Domain `qoima-saved-relocation-pair-publication-0.1.0` uses existing ArtifactStore `run_files`
CAS objects and publishes one `runs` index last. The public `pair_id` hashes the domain,
pair-input hash, comparison hash and sorted complete member descriptors. Both raw native
manifests participate as members. Every descriptor carries `path`, `bytes` and `sha256`.
Validation completes before store creation. An interrupted CAS write can leave immutable
unreferenced members, while publication-last controls accepted pair visibility. Repeating
an identical import uses the existing atomic CAS/reference idempotence rules.

## Read namespace

The backend provides five read entry points.

- `GET /api/v3/relocation-pairs/{pair_id}/result`
- `GET /api/v3/relocation-pairs/{pair_id}/arms/{arm}/manifest`
- `GET /api/v3/relocation-pairs/{pair_id}/arms/{arm}/files/{artifact_id}`
- `GET /api/v3/relocation-pairs/{pair_id}/arms/{arm}/bundle`
- `GET /api/v3/relocation-pairs/{pair_id}/arms/{arm}/replay?tick=T`

Unknown pair/domain/arm/member checks precede native numerical work and return 404.
Canonical nonnegative decimal ticks and observed replay boundaries return 422 on invalid
input. Arm file IDs are opaque content hashes selected only from the requested arm.
Raw file bodies retain their original bytes. `X-Qoima-*` headers bind `pair-id`, `arm`,
`native-run-id`, `input-hash`, `pair-input-hash`, `common-input-hash` and
`registry-common-hash`. JSON responses include the corresponding explicit identities.

Every accepted GET invokes shared `JobService.read_job` and the existing owned processor.
The worker rereads and rehashes the complete stored pair, restores a private snapshot and
performs fresh strict pair/native/report validation. Shared-slot 409, cancellation shielding
and shutdown draining follow the existing JobService policy. This read path uses the
saved-pair domain directly and performs fresh validation on each request.

## Arm stream proposal

The bundle response uses `application/x-ndjson` with version
`qoima-saved-relocation-arm-ndjson-0.1.0`. One shared-worker request fully validates the pair,
then returns the selected arm's captured immutable bytes. Streaming starts after validation.
A stream generator serializes those captured bytes, preserving its accepted snapshot through
subsequent store changes and avoiding any per-record revalidation or filesystem read.

The first record has `record_type=header`, the stream `schema_version`, all explicit pair/arm/
native/input/common identities, provenance, the complete `transport_manifest` and exact
`stream_descriptors`. The default stream contains the native manifest, catalog, event chunks
and captured snapshots. Its transport manifest retains the validated `inputs.json` descriptor.
The inputs payload is available through the member GET endpoint. Each later record has
`record_type=file`, `path`, `bytes`, `sha256` and `body_base64`, which encodes the exact original
member bytes. Header descriptors allow consumers to check complete stream membership and
individual file hashes before using native events or snapshots.

This is an arm-bound backend seam for client prefetch and local native playback. Arbitrary
settled-state replay uses the existing relocation reader at selected observed ticks. Native
BeltPose, events, deltas and captures retain their recorded values. Frontend scene consumption,
carry-frame agreement and browser acceptance remain a joint integration deliverable.

## Focused evidence scope

Two new test modules use tiny closed transports and explicit semantic doubles for paired
input loading, strict native reads, outcome projection, report construction and replay.
The real native manifest descriptor validator and real ArtifactStore remain exercised.
These checks cover publication behavior and API ownership. Actual source/native semantic
acceptance and complete release verification have their own independently recorded gates.
