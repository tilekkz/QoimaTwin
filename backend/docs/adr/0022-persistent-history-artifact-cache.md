# 0022. Persistent immutable synthetic history cache

Status: implemented in forecast worktree, 2026-11-07; main integration pending.
Extends ADR0015. PDF dated 2026-11-07, page8 performance item7 explicitly says
history is regenerated at every simulate and requests immutable input by hash.

`generate_history()` remains pure/uncached. `history_artifact()` keeps its existing
zero-argument API, immutable `HistoryArtifact`, and process-local LRU. Its cold
process path now resolves a disk reference before invoking the original generator
and original CSV serialization. No parsing/reserialization occurs in disk storage.
`history_by_hash()` still checks raw byte identity and returns independent frames.

The trusted, server-controlled `QOIMA_HISTORY_CACHE_DIR` is an absolute directory
outside this checkout. Default Windows location is the current user's
`AppData/Local/QoimaTwin/history-cache-v1`; other platforms use
`~/.cache/qoimatwin/history-cache-v1`. No home environment variable is reassigned.
The operator owns this directory and its ancestors/ACLs. It is never an uploaded
path or a CLI client parameter. `load_or_generate(root, input_sha256, generate)`
is the explicit trusted-path/bytes-generator API for tests and application callers;
those callers are responsible for selecting an external, trusted directory.

Identity has two levels. A generator-input SHA256 selects `<input>.json`.
It fingerprints relative labels and exact source bytes for history, store, catalog,
orders, seeds, scenario/base models, explicit seed/stream/date/split/catalog inputs,
Python version/implementation/machine, and NumPy/pandas/Pydantic/core versions.
No absolute checkout path, timing or source mtime enters identity. Source edits
invalidate even without a manual version bump; dependency source additions must
extend this declared closure. Source access is required, so source-less packaging
needs a future explicit build fingerprint. In-process instrumentation must use an
isolated directory; runtime monkeypatches are not production source versions.

The manifest has exactly `version` (integer1), `input`, and `sha256`. Content lives
at `<raw-SHA256>.csv`. Every disk resolution verifies the raw byte digest. References
are bounded to4096 bytes, content to16MiB. Lowercase64-hex digests prevent traversal.
Duplicate JSON keys, malformed/schema-invalid references, wrong input identity,
missing referenced content, nonregular files, symlink entries, and hash mismatches
fail closed with `HistoryCacheError(ValueError)` and a generic message containing
no paths or cached text. A missing manifest is a cold miss; existing bad entries
are never silently repaired, overwritten or deleted. Operators inspect the trusted
directory and explicitly relocate/remove affected entries before retrying.

Each publication flushes/fsyncs a private same-directory temporary inode, then
uses an exclusive hard link to the final name. A competing existing file is
accepted only when its complete bytes equal the intended bytes. No replace/write
to a final path occurs. Content is published first; the manifest is published last.
Readers cannot observe a partially written final file. Crashed writers can leave
unreferenced content/temp files; correct orphan content can be reused. Cleanup
only removes this invocation's exact temporary pathname; there is no pruning or
broad deletion. Filesystems without hard-link support and permission/disk failures
fail closed. Concurrent cold processes may redundantly generate, but cannot
silently overwrite one another or publish inconsistent references.

Limits: this is content integrity in a trusted cache, not authentication against an
attacker who can rewrite both content and manifest. Parent symlinks/ACLs are the
operator's trust boundary; entry checks do not defend hostile concurrent directory
mutation. Published files are logically immutable; OS read-only flags are not set.
The LRU trusts already verified immutable in-memory bytes until cleared/process
exit. Per-file fsync does not promise directory durability across power loss;
restart treats absent references as misses and broken references as errors.
No eviction, multi-process single-flight lock, or new dependency is introduced.

Tests set a session temporary cache environment before session history fixtures,
clear process memory between tests, and give instrumented-generator tests distinct
directories. Main's HistoryArtifact fixture substitutions remain authoritative.
Independent cold/warm CLI materialize processes use fabricated tiny CSV data, with
the warm generator forbidden. This proves the shared CLI publication cache seam
without running heavy56-day generation or claiming new cold timing measurements.
