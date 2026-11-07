# ADR 0024: Bind public provenance to immutable run identity

Status: accepted for backend; shared run schema 2.0 is unchanged.

## Context

The API publishes provenance in the immutable run manifest. Two valid scenarios
with identical orders, receipts and simulation inputs but revised source notes
previously shared a run ID and produced different manifest bytes. Publishing the
second scenario correctly rejected the conflicting immutable artifact, making
that valid comparison unavailable.

## Decision

Use identity version `qoima-run-v2`. Include `provenance_sha256`, the canonical
hash of the complete scenario provenance, beside the nine semantic input hashes.
The nine input hashes remain independently comparable across provenance revisions.
Both shared 2.0 and proposed 2.1 use this fingerprint; the proposal additionally
includes its wire version. Engine version `qoima-engine-0.4.0` covers the new
forecast/planning/metrics integration, resource-wait interpretation and identity.

Do not discard provenance, overwrite an existing manifest or reuse old run IDs.
Old artifacts remain valid under their recorded engine and identity versions.
Runtime measurements and provider-generated text do not enter run identity.

## Validation

A regression test first failed because a source-note revision retained the same
fingerprint. The corrected fingerprint changes for the revision while all nine
simulation input hashes stay equal. Deep copies retain equal fingerprints.
API publication tests additionally verify two immutable manifests can coexist.
