# Optional Mercury explanations

Mercury supplies AI-generated advisory observations for an already completed slotting A/B
comparison. Simulation, plans, metrics and run identity do not depend on Mercury. Missing or
blank credentials produce `ExplanationError(code="unavailable")`; ordinary project operations
remain available. The local API exposes an explicit explanation endpoint; see [the API guide](api.md).

## Backend configuration

Use [the example](../.env.example) as a reference. Set `INCEPTION_API_KEY` locally
through your backend process environment, secret manager, or an ignored local `backend/.env`.
Do not put credentials in source, HTTP requests, logs, artifacts or caches.

Exact settings signature:
`MercurySettings.from_env(*, env_file: Path | None = None) -> MercurySettings`.
The no-argument call reads only the process environment, preserving existing behavior.
Local file loading requires the API's explicit trusted server configuration path:

```python
from pathlib import Path

# backend_dir is resolved by the server, never from an HTTP field.
backend_dir: Path = ...
settings = MercurySettings.from_env(env_file=backend_dir / ".env")
```

Environment values override the four allowlisted file settings, including an empty key
that disables explanations. A missing optional file is allowed. Files are bounded to 16 KiB
and decoded as UTF-8 with optional Windows Notepad BOM. The format supports `KEY=VALUE`,
whitespace, blank lines, full-line `#` comments, and optional matching single/double quotes.
Values are literal: no interpolation, escape processing, shell execution, or dotenv dependency.
Unknown keys/lines are ignored for ordinary shared `.env` usage; malformed known assignments,
duplicate known settings, unreadable/invalid UTF-8 files and oversized files raise generic
`ValueError` messages without paths or values. The file is parsed before environment overrides;
overrides do not hide duplicate or syntactically malformed assignments. Effective model,
timeout and token values retain their existing validation. No file or environment settings
are read during import. Never accept a configuration path from an HTTP client.

| Variable | Default | Bounds |
| --- | --- | --- |
| `INCEPTION_API_KEY` | absent | backend secret; absent/blank disables feature |
| `MERCURY_MODEL` | `mercury-3` | 1..100 letters/digits/dots/underscores/hyphens; starts alphanumeric |
| `MERCURY_TIMEOUT_S` | `10` | finite, greater than 0 and at most 30 seconds per HTTP operation |
| `MERCURY_MAX_COMPLETION_TOKENS` | `1024` | integer 1..4096 |

The [official quickstart](https://docs.inceptionlabs.ai/get-started), checked on 2026-11-07,
specifies `POST https://api.inceptionlabs.ai/v1/chat/completions`,
Bearer authentication, `model`, `messages` and `max_completion_tokens`. Its current model is
`mercury-3`. Keep the model configurable. A complete synthetic comparison through the local
HTTP API returned eight validated Russian observations from Mercury 3 on 2026-11-07.
The repeated explanation request returned the identical cached response.

The actual application explanation later returned `invalid_response`: the coordinating worker
observed provider HTTP 200 with `finish_reason="length"` and null content at the 1,024-token
default. Request protocol v3 therefore sets `reasoning_effort="instant"` explicitly and requests
strict `json_schema` structured output. See the official
[reasoning efforts](https://docs.inceptionlabs.ai/capabilities/reasoning-efforts) and
[structured outputs](https://docs.inceptionlabs.ai/capabilities/structured-outputs) documentation.
The schema is derived from the local observation model, with closed objects, existing bounds,
and citation IDs restricted to the current known facts. Its sole local reference is inlined.
Observation text is requested in Russian; citation IDs are preserved exactly.
These are fixed backend protocol options, not HTTP-client configuration fields.
The token budget remains unchanged. Local validation still rejects incomplete completions,
unknown citations and malformed output, without retries. The actual v3 request passed these
checks; schema compliance does not establish the truth of every generated sentence.

## Service contract

```python
from app.explanations import (
    MercurySettings,
    explain_comparison,
    explanation_cache_key,
    extract_comparison_facts,
)

# Stored server-owned comparison envelope, not a client-supplied facts object.
# scenario is loaded from the comparison's associated immutable scenario artifact.
facts = extract_comparison_facts(
    stored_envelope["comparison"],
    provenance=scenario.provenance.kind,
)
settings = MercurySettings.from_env()  # Or the explicit server-owned env_file path above.
cache_key = explanation_cache_key(stored_comparison_id, facts, settings=settings)
result = explain_comparison(stored_comparison_id, facts, settings=settings)
payload = result.model_dump(mode="json")
```

Exact synchronous entry point:
`explain_comparison(comparison_id: str, facts: ComparisonFacts, *, settings: MercurySettings,
client: httpx.Client | None = None) -> ExplanationResult`.
An injected client is a trusted backend dependency, useful with `httpx.MockTransport`.
Owned clients are closed automatically; borrowed clients remain owned by their caller.
No endpoint, key or arbitrary URL is accepted from HTTP clients. Run network work in a worker
or thread, avoiding blocking the API event loop. Never invoke this automatically during runs.

The returned object has `comparison_id`, unchanged `facts`, `observations` (each with `text`
and `fact_ids`), `model`, `prompt_version`, `cache_key`, `ai_generated=true` and an `advisory`.
Display the AI label and advisory with observations. Numeric comparison facts stay separately
authoritative. Valid citations do **not** prove every prose assertion true. No tools execute.

Load comparisons only after their completed job/artifact is published. The extractor accepts
the inner `qoima-compare-v1` artifact and accepts each side's outcome status `complete` or
`partial`. A finished comparison calculation is separate from simulation flow completion:
an 8-hour scenario may finish comparison calculation with blocked receiving or max-drain
outcomes. Failed, running, missing and unknown statuses are rejected. Each side must include
its primary `outcome.termination` from `drained`, `deadlock`, `max_drain`,
`unfulfilled_inventory`, or `error`. Unknown/missing primary termination is rejected with
`invalid_facts`. Optional `outcome.termination_reasons` must be a list of at most five known
enum strings; malformed/unknown reasons are rejected without reflecting their content.
The current comparison OutcomeView contains only primary termination; extra reasons are
extracted only when already present in a server artifact, never inferred from run records.
The ID argument should be the API's immutable stored comparison ID; it can differ from the
inner comparison digest. Explanation results never replace that artifact or its run references.

Error codes are `unavailable`, `invalid_facts`, `invalid_response`, `timeout`, `transport`,
`authentication` (401/403), `rate_limited` (429), `provider_unavailable` (5xx), and
`provider_rejected` (other unsuccessful statuses, including redirects). Error text includes
only the stable code; provider bodies and transport exception messages/chains are discarded.
Map these to API errors in the API worker. No retry or success fallback is performed.

## Privacy and metric meaning

Only the allowlisted summary is sent, and only on an explicit explanation request:

- Swap budget/count, no-op/equality flags, relocation seconds/metres.
- Each side's `baseline|candidate.outcome.status` and `.outcome.termination`;
  optional known `.outcome.termination_reasons.N` facts, without raw error strings or notes.
- Each side's horizon/end times; each window's gross/net labor savings, blocked/wait deltas,
  verdict, side cutoff and total labor seconds.
- When present: each side/window's arrived, packed, dispatched, rejected and backlog counts;
  completion rate, backlog maximum age, makespan and last dispatch; mean/p95 of cycle,
  packed cycle and backlog age. Undefined values remain `null`, never invented zeros.
- Provenance (`synthetic`, `synthetic_fixture`, `historical_partial_baskets`, or `unknown`),
  explicitly resolved from scenario metadata by the backend. Unknown is not assumed real.

The service excludes free-text notes, scenario identifiers, SKU/order/actor detail, raw plans,
raw histories, queues, arbitrary nested metrics, event streams and credentials. Comparison ID
is retained in the local result/cache identity but is not sent in provider messages.

At horizon, counts/cycles use `[0,H)`; at end they include events at the side's end time.
Duration integrals/labor use `[0, cutoff)`; side end cutoffs can differ. Labor is TRAVEL plus
BUSY_SERVICE. Net savings subtract pre-shift relocation once. Synthetic results are illustrative
and cannot establish production performance. Prompts require advisory wording and forbid
unsupported numbers, invented causes and guarantees.
The prompt requires acknowledgement of partial outcomes and supplied termination reasons.
Partial results also carry a deterministic advisory naming every partial side. Neither order
counts nor all orders dispatched establish that receiving or all simulation flow completed.
Numeric facts and KPI/window calculations are unchanged; no subsystem data is added.

## Caching and verification

`explanation_cache_key` hashes comparison ID, canonical facts digest, model and prompt version.
It excludes the key, timing, timeout and token budget. Caller-controlled timing/notes are not
extracted. Budget changes can reuse an existing result; bump prompt version for prompt or
fact-semantics or fixed provider-protocol changes. No filesystem cache exists here. The API store
must publish immutable results safely and handle concurrent requests without overwriting
comparison/run artifacts.
Cache hits may still be returned under the API's policy when a key is absent; cache misses
must not bypass the service's unavailable result. Do not cache credentials or provider failures.

Run focused local checks from `backend/` so strict repository configuration is loaded:

```powershell
uv run pytest tests/explanations -q
uv run mypy app/explanations tests/explanations
uv run ruff check app/explanations tests/explanations
uv run ruff format --check app/explanations tests/explanations
```

Prompt/request version is `qoima-mercury-explanations-v3`; previous cache entries must not be reused
under the new protocol identity. Version v2 introduced partial-outcome facts; v3 adds explicit
instant reasoning and strict cited structured output. `httpx==0.28.1` is a runtime dependency.
No real credentials or live requests are needed for these tests.
