# ADR 0092: Request-owned coordinator native read context

Status: accepted backend design; release verification is recorded against the exact
candidate freeze.

## Problem and evidence

The registered replay and storage-fullness readers repeat strict validation of
the same immutable native evidence within one request. A saved analytical profile
previously measured approximately 20 seconds for strict reading and another
20 seconds for direct fullness publication under cProfile. Raw file IO was a small
part of that measurement. This is one diagnostic case, not a p50/p95/p99 benchmark.

Before this change, portable whole-HU hand tests observed two input loads for a
direct strict read or validation, and three for direct replay or fullness. A cold
registered replay performed eight input loads and three full outcome validations;
cold fullness performed seven and three. Both warm paths still performed two full
outcome validations. The tests forbid constructing or running an engine during
the measured reads. Their fixture executes only the existing analytical hand case.

## Decision

Retain one private `_NativeReadContext` for the duration of a request. It owns
canonical immutable native bytes, freshly reconstructed input/profile authority,
and the typed outcome decoded from the same checked evidence. No mutable native
dictionary, context, journal or profile is added to a shared cache. The context
is not a public admission token and no API accepts caller-supplied trusted facts.
There is no `validated` or `skip_checks` flag.

The private constructor still checks the closed native envelope, original exact
record/scalar types, fresh input reconstruction, full outcome projection and
causal validation, metrics, versions, clocks and complete canonical expected run.
Original objects are decoded before any JSON normalization could erase aliases.
The context's JSON accessor returns a detached view of its immutable bytes.

Transport restoration retains all existing canonical-byte, closed inventory,
raw SHA/length, event sequence/window, snapshot role/watermark and native identity
checks before the constructor returns. Public strict read, validation, replay,
fullness and retained-input build functions retain their strict contracts.

At the API boundary, both the existing immutable summary path and the new private
request path share the same raw-evidence checks: known public lookup, exact index,
registration binding, manifest inventory and rehash of every native/outer file.
The new path restores the files once and performs one strict native validation.
It also checks profile/request/input hashes and outer result metadata against
that exact context through the existing `evidence_files` authority. A correctly
rehashed false outer result is not accepted merely because its bytes are valid.

Existing status/checkpoint/event summary caching remains bytes-only. Replay and
fullness do not call that summary cache before creating their own context.
Unknown public IDs still fail before unrelated registration is initialized.

## Projection boundaries

Arbitrary settled replay creates a fresh prefix Journal, separate from the full
causal journal used for validation. Exact tick/future guards, captured-state
agreement and paid-return semantics remain unchanged. No engine state is restored.

Fullness derives its source run hash and report identity from the context's
immutable bytes, never a mutable caller object reread after validation. Fresh
source capacity authentication remains in the existing reducer at both H/end
boundaries. Analytical capacities remain explicitly unavailable.

## Validation and scope

Regression tests count actual loader and full causal-validator calls rather than
using environment-sensitive elapsed-time thresholds. The target is one input
load and one full causal validation per direct read and per registered replay or
fullness request, whether the existing summary cache is cold or warm. Prefix
reduction is an additional necessary operation, not counted as redundant full
validation.

Before/after canonical API bytes are compared on the exact saved hand artifact.
Corruption, numeric/record aliases, unknown and unavailable registration, detached
caller state, transport descriptors and fresh source authentication remain gates.
No source DES, live HTTP, browser, throughput, p95/p99 or full-V3 performance claim
is made by this change. Belt plan memoization and cross-request typed caching are
outside its scope. Publication versions and serialized native schemas are unchanged.
