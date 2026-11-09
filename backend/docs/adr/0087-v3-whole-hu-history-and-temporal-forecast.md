# ADR 0087: Source-bound whole-HU offer history and temporal forecast

Status: implemented for focused verification; no runtime or full N1 admission.

## Authority and declared measure

The V3 brief separates units, pick visits and HU movements. C10/C11 expected moves
belong to an unclocked planning period. They supply no historical daily/hourly
observations. Existing V2 synthetic history counts SKU order-line visits even though
it also uses DEMO_001..200; it is not a whole-HU history source.

New `compile_offer_history(raw_history, choices)` accepts mandatory immutable UTF-8
CSV bytes with exactly `date,sku_id,offered_hus`. Every count is a canonical
nonnegative integer no greater than 2**53, the contiguous exactly representable
binary64 integer range. Larger counts reject rather than silently lose precision
in the reused numerical kernel. No units-to-HU ceiling, line-visit conversion,
default generator, zero filling, deduplication or implicit source repin occurs.

Initial provenance is explicitly `declared_synthetic`, with nonempty dataset,
generator and version identifiers plus an explicit optional nonnegative integer
seed. This is a caller declaration, not proof of real warehouse observations or
of an arbitrary generator's truth. It is retained in the input identity. Actual
observed-dataset admission is outside this initial adapter. A legacy visits/units
CSV header is rejected; relabeling that dataset is not an authorized conversion.

The source loader freshly authenticates C10 and the source catalog on every public
compile/load/verify. All 200 source SKU identities, recipes, original HU references
and layout/source fingerprints remain intact in `WorkloadSource`. Predictions are
separate rows; they never replace the original source demand weights or stock.

## Time and the fixed temporal protocol

Caller choices explicitly supply target_unit=`outbound_whole_hu_offers`, calendar
test_day, IANA timezone and equal local window start/end seconds. The initial
adapter supports exactly eight local hours per observation date. Every window must
also span eight actual UTC hours. Ambiguous/nonexistent boundaries, unknown zones,
7/9-hour DST windows and any end at or after test_day local midnight reject. Thus
16:00–24:00 on the last history day is not accepted at the midnight cutoff. These
are declared adapter restrictions, not clocks inferred from C10 planning periods.
Actual UTC windows enter the normalized identity and are recomputed on load.

Exactly 56 consecutive complete calendar dates before test_day and every source
SKU on each date are required. Offsets0..41 are train and42..55 validation;0..27
are lag warmup, not fit targets. HGB validation fits once on targets28..41 and
evaluates42..55 with strictly earlier observed rolling features. Earlier observed
validation days may enter later lag features: this is rolling one-day-ahead
evaluation, not an open-loop14-day prediction. A fresh final model fits28..55 and
predicts56. No future/test-day rows or actual evaluation workload are inputs.

The existing numerical kernels are reused with explicit source SKU IDs/test_day:
mean28, or fixed Poisson HGB with lags1/7/14/28, shifted means7/28, weekday and sorted
one-hot SKU. HGB uses150 iterations,15 leaves, learning_rate0.06, L2=1, seed42,
early_stopping=false and one native thread. All-zero training uses the existing
declared zero boundary. Model choice is explicit; no tuning occurs in this adapter.
The first42 mean remains a demand reference, not permission to rebuild C10 layout.

## Numerical and artifact identity

`OfferHistoryInputs` retains original raw bytes/SHA, normalized observation hash,
complete integer grid, UTC windows, source and caller choices. Row reordering may
change raw/input identity while preserving normalized demand. The normalized hash
includes the measure/window/source templates; provenance remains in full identity.

`OfferForecast` exposes the authenticated source/history, complete200 predictions,
training baseline, evaluation, kernel identity and canonical frozen bytes/input hash.
It uses a new V3 protocol, never the V2 snapshot semantic ID or its default daily
unit. Finite nonnegative Python binary64 outputs convert with `Fraction(float)`:
exact binary value, no decimal rounding or tolerance. For example0.1 becomes
3602879701896397/36028797018963968, not1/10. NaN/infinity/negative/type aliases reject.
Conversion policy `binary64_prediction_error_exact_observed_count_v2` preserves
the kernel's finite prediction and aggregate absolute-error binary64 values as
exact Fractions. Actual offered-HU count is instead the exact integer sum of raw
validation observations, not the legacy kernel's rounded aggregate float. WAPE
uses that same exact count denominator, and is null when it is zero. For example,
14 days of two counts2**53 and1 sum to126100789566373902, even though the legacy
float aggregate returns126100789566373904. No artificial total-count limit is
added. The original pre-release output/code freeze remains preserved separately.
Row-count fields describe eligible
temporal targets; mean28 does not fit an estimator. HGB actually fits2800 validation
and5600 final target rows for this200-SKU boundary.

Semantic identity binds the raw kernel/adapter code, Python and numerical-library
versions, fixed temporal/conversion policy, input identities, output/evaluation and
model. CPU total/validation/final process observations are separate, `compare=False`,
and never enter semantic bytes/hash. They are typed finite nonnegative observations,
not stable numerical authority. Public verify returns newly observed CPU values;
it does not certify supplied old timings as a newly performed measurement.

Public forecast fit first revalidates history. Load/verify rebuild history/source,
re-execute the fixed numerical kernel, and compare complete canonical semantic
bytes and exact retained types. Rehashing altered forecasts, nested metadata or
source facts cannot confer authority. Reverification may perform a real HGB fit;
there is no cheap-load or trusted caller-cache promise. A forecast snapshot contains
values and provenance, not a pickled mutable estimator.

## Boundaries and validation

History and forecast remain `operational_admission=false`. They do not create stock,
receipts, time-dependent demand rates, a decision, a scheduler or runtime grants.
Projection has its own future authority/choices; existing C11 strict contracts are
unchanged. The actual held-out test stream must remain unavailable to forecasting
and plan selection and later be common to both actual A/B arms. No positive gain
is required, and one whole HU must never fund repeated visits.

Tests-first evidence covers constant1/3 and all-zero arithmetic, raw-versus-normalized
identity, grid/window/type/rehash/source controls and fresh roundtrips. A positive
uniform synthetic HGB case must actually invoke the estimator for both fit phases;
the all-zero shortcut alone does not prove model fitting. Independent review and
owner manifests record observed focused/static outcomes. These checks do not prove
real warehouse forecast quality, source-scale runtime, full N1 or UI integration.
