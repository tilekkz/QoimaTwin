# 0020. Optional Mercury comparison explanations

Status: implemented service and API integration; request protocol v3 verified with mocks and
the actual Mercury 3 API on 2026-11-07.

Completed A/B simulation results can benefit from readable advisory observations. Generated
language must not select plans, alter simulation inputs, recompute metrics, change run IDs,
or become authoritative numeric evidence. The entire project remains usable without a key.

Use the synchronous `app.explanations.explain_comparison` service with immutable local result
types. A separate allowlist extracts facts from a completed `qoima-compare-v1` slotting artifact.
Only explicit explanation requests may call the provider. API workers load immutable artifacts
and resolve provenance from server-owned scenario data before invoking the service; facts,
credentials, endpoint, model and transport are never HTTP request overrides.

A published comparison may contain `complete` or `partial` simulation outcomes. Require each
side's allowlisted status and primary `termination`; accept only known engine enum values
(`drained`, `deadlock`, `max_drain`, `unfulfilled_inventory`, `error`). Optional existing
`termination_reasons` are bounded known-enum lists. Reject failed/running/unknown outcomes
and unknown reasons with sanitized errors. No raw errors, notes, additional run records or
subsystem payloads enter the facts. Counts cannot prove all flow completed: receiving can
remain blocked after all orders dispatched. Prompts distinguish finished comparison
calculation from flow completion and require partial acknowledgement; returned advisories
also explicitly name partial sides. All numeric facts retain their previous meaning.

The provider endpoint is fixed to the official HTTPS chat completions endpoint. Backend
configuration contains `INCEPTION_API_KEY`, `MERCURY_MODEL`, a bounded timeout and a bounded
completion budget. Default model `mercury-3` follows the official current quickstart.
A complete local HTTP workflow produced a synthetic comparison, requested an explanation,
and received eight schema-validated Russian observations with known fact IDs (HTTP 200).
The repeated request returned the identical cached result without another provider request.

The later real application smoke reached the explanation endpoint after successful comparison
publication, but the API returned 502 `invalid_response`. The coordinating worker's sanitized
diagnostic found provider HTTP 200, `finish_reason="length"`, and null message content: the default
1,024-token completion budget was consumed before a visible answer. A tiny connectivity request
therefore did not establish that the actual explanation request would succeed.

Protocol v3 explicitly requests `reasoning_effort="instant"`, supported for Mercury 3 by the
[official reasoning documentation](https://docs.inceptionlabs.ai/capabilities/reasoning-efforts).
It also sends `response_format.type="json_schema"` with `strict=true`, following the
[official structured-output protocol](https://docs.inceptionlabs.ai/capabilities/structured-outputs).
The schema comes from `GeneratedObservations`, retains all required fields, closed objects,
string/array bounds, and adds a sorted enum of the current known fact IDs. The sole local
Observation reference is inlined, so this simple payload does not depend on provider `$ref`
resolution. Each request receives a fresh schema; fact IDs cannot leak between requests.
Empty facts fail locally before HTTP because no valid citation can be generated.
Observation prose is requested in Russian for the application's audience; fact IDs remain exact.

The default completion budget remains 1,024. The local decoder remains authoritative and rejects
unknown citations, extra fields, malformed JSON and every non-`stop` finish reason, even if a
truncated completion happens to contain parseable JSON. There is no token increase, automatic
retry or success fallback. Mocked schema/request tests verify the protocol and error paths;
the successful actual-model check establishes connectivity and schema compliance, not universal
accuracy of generated prose.

`MercurySettings.from_env(*, env_file: Path | None = None) -> MercurySettings` preserves
environment-only defaults. Only an explicitly supplied trusted server path enables optional
local file fallback; the API may pass its own `backend/.env`, never an HTTP-controlled path.
The parser permits only the four configuration keys, reads at most 16 KiB plus one detection
byte, handles UTF-8 BOM and matching quotes, ignores unknown keys, and rejects malformed known
assignments/duplicates with sanitized errors. Environment values override parsed file values.
No interpolation, shell execution, import-time configuration reads or dotenv dependency exist.

The system prompt treats facts as untrusted data, forbids unsupported numeric claims and
winning/performance guarantees, and requires advisory observations with citations. Validation
rejects malformed JSON, duplicate keys, empty observations, unknown fields, unknown fact IDs,
tool-call responses and incomplete completions. A recognized citation only proves the ID exists;
it does not establish that all generated prose is true or entails the cited facts. Consumers
must display AI labeling, the advisory and authoritative facts separately.

Provider failures become stable sanitized errors, never substitute explanations. There are no
tools, retries, provider-result files or local cache. Owned clients ignore environment proxies and never
follow redirects; injected clients are trusted backend/test dependencies. The deterministic
cache key includes comparison ID, canonical facts digest, model and prompt version, excluding
credentials, timeout and token budget. The API immutable artifact store owns cache publication
and concurrency. Every substantive prompt/allowlist/semantics change must bump prompt version.
This correction uses `qoima-mercury-explanations-v3` to invalidate earlier prompt/request identities.
Fixed reasoning and response-format options are part of that versioned protocol, even when the
natural-language prompt remains unchanged. Version v2 covered partial-outcome fact semantics.

Tradeoffs: synchronous network work belongs on the API worker, not the event loop. A strict
JSON response can be rejected even when prose would be readable; failure remains visible.
The existing pinned `httpx==0.28.1` dependency is declared in the runtime dependency group.

See [setup and service contract](../mercury.md) and the
[official quickstart](https://docs.inceptionlabs.ai/get-started).
