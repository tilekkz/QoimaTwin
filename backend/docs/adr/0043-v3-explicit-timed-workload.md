# ADR0043: explicit synthetic V3 whole-HU workload materialization

Status: backend proposal. This is a frozen input materializer, not N0 acceptance,
an execution profile, an operational admission decision or a shared run contract.

## Source and clock boundary

C10 at source revision `22296bcf2c6bac5ade4cefc7c05c2b97831ec6ec` fixes 200 SKU,
530 initial HUs, unchanged C02 recipes and normal port mixes before comparison.
Turnover cycles 16/8/4/2 over sorted SKU: 50 × (16+8+4+2) = 1500 expected HU
moves per direction per **unclocked** planning period. Neither an hourly rate,
peak multiplier nor a replenishment calendar is supplied. No V2 arrival rate,
tote pool, service time or packing recipe is transplanted.

Introduce an explicit versioned `WorkloadPolicy`: positive integer microsecond
horizon, nonnegative integer offered-HU budgets for inbound and outbound,
calendar kind and, for bursts, ordered disjoint half-open windows with positive
exact rational weights. The caller chooses the horizon and budgets independently.
There are no execution-dependent draws, seeds, hidden default rates or end caps.
An engine's drain limit is a separate execution input.

## Whole-HU population and source identity

`load_workload_source(bundle)` consumes an already verified immutable V3 loader
bundle. It preserves every source SKU, all eight classes, all initial physical
HU references, lot references, all raw/canonical source fingerprints and exact
C02 dimensions, whole-HU units and gross mass. Cargo-record and packing-recipe
hashes identify unchanged source recipes; the original pinned package remains
the resolver for complete recipe geometry. No interior unit becomes extra stock.

Expected SKU × port weights are exact `Fraction(str(source_number))` values:
the source turnover multiplied by its port share. Port direction and class
permission are checked against the source ports. No unsupported heavy class or
port is removed merely because the current execution engines cannot handle it.
Even a zero-budget result retains the complete source templates and zero quotas.

Materialization creates typed whole-HU **intents**. Each inbound intent has a new
stable offered-HU ID and a new population/SKU lot ID. These offers are outside
the warehouse and are not credited to a ledger. Outbound intents explicitly
have no allocated HU or lot ID: they request a whole source template and its
unchanged unit quantity. Reusing a baseline HU ID repeatedly to pretend that
15000 shipments have stock would be false. Stock allocation, replenishment,
arrival admission, slots and source/parent genealogy belong to separate ledger
and workflow integration. The materializer never modifies the initial 530 HUs.

## Integer quotas and deterministic ordering

Allocate each direction's explicit budget globally over its SKU × port weights
using exact Hamilton largest remainder. For weight `w`, total `W` and budget `N`,
the expected quota is `N*w/W`; floor all quotas, then assign the remaining HUs
by descending exact remainder, with lexical `(sku_id, port_id)` ties. Preserve
expected count, integer count and signed rounding delta for every pair.
Zero budgets and zero weights are supported; positive budgets require positive
total weight. Duplicate pairs, malformed identities and non-finite/inexact
weights reject. This is not separate SKU-first rounding. At small budgets,
per-SKU inbound/outbound integer totals may differ despite equal source turnover;
the published deltas expose that fact and do not authorize stock creation.

Each quota's local ordinal `j` receives the exact ordering key `(2*j+1)/(2*count)`.
Sort all ordinals by that key, then SKU, port and ordinal. This deterministic
interleaving spreads each quota over the offered sequence without RNG or a
dispatch-dependent choice. Job IDs bind population, direction, SKU, port and
ordinal. HU/template IDs preserve the same bindings across calendar variants.

## Explicit normal and controlled burst calendars

For `normal`, sequence ordinal `i` among `N` direction offers arrives at
`floor(i*H/N)`. Thus every timestamp is in `[0,H)`; a single offer is at zero,
and several offers may share a tick when `N > H`. This is a synthetic deterministic
calendar, not a Poisson process or an observed source arrival rate.

For `burst`, first allocate the same `N` offers to explicit window weights by
the same exact largest-remainder rule, with earlier windows winning ties. Within
window `[a,b)` holding `n` offers, ordinal `i` arrives at `a+floor(i*(b-a)/n)`.
An empty allocated window contributes no arrivals. Windows must be ordered,
nonoverlapping, positive-length and wholly inside the horizon. No implicit
"2× peak" multiplier exists. A controlled peak changes only these explicit times;
the whole-HU population, ports, recipes and IDs remain unchanged.

## Hashes and format

`population_id` hashes materializer version, stock-binding policy, canonical
source projection and the two offered budgets. It excludes the horizon and
calendar. `workload_id` hashes the complete canonical workload excluding only
its own ID: policy, exact quotas/deltas, sorted actual arrival jobs and source
identity. Timing changes therefore change workload identity without changing
population identity. Set-like source arrays are canonicalized by explicit IDs;
the emitted job sequence is sorted by arrival tick, direction and job ID.

Exact rationals are serialized as reduced `[numerator, denominator]` arrays.
All values are frozen dataclasses and tuples; JSON projection returns a fresh
tree. The output says `synthetic_timed_workload`, retains source design provenance
and always has `operational_admission=false`. It is not an actual-engine run.

The CLI `v3 materialize-workload --policy FILE --out DIR` persists normalized
policy and materialized workload in an empty output directory, then writes a
manifest with raw SHA256 and byte size for each file. Publication grants no
stock credit or execution capability. Unknown or malformed policy rejects
before output publication; nonempty destinations are never overwritten.

The proposed policy schema is structural. The parser also enforces exact integer
types, window order/overlap, horizon bounds and the calendar-specific rules;
JSON Schema's mathematical integer type alone cannot distinguish a decoded1.0
from an integer token. Unknown fields and schema versions reject.

## Source arithmetic and acceptance boundary

One unclocked source period has inbound totals E957.6/N304.4/W238 and outbound
retail787.7/express560.7/B2B151.6 HU expectations. The smallest exact multiplier
for every inbound SKU × port share is5, for outbound10, and jointly10. For example,
STANDARD turnover2 × inbound.7 =7/5, while outbound.45 gives9/10. A common ten-period
population therefore has15000 offers in each direction and all pair deltas zero.
These counts are not15000 per hour and are not a recommended first engine run.

Tests derive tiny quotas, ties, calendar endpoints and source port totals from
hand arithmetic/source values, never engine output. Normal/burst identity,
input-order invariance, canonical hashing and malformed input cases are required.
No engine, unsupported heavy flow, replenishment, full-shift performance result
or N0–N4 closure follows from successful materialization.

Sources: C10, `baseline-input-v3.json`, `cargo-catalog-v3.json`, source port JSON;
adaptive brief `02_DESIGN_V3.md` comparison and N0–N4 sections. Shared V2 contracts
and existing manual/profile implementations remain unchanged.
