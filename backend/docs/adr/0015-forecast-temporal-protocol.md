# 0015. Forecast temporal protocol and immutable artifacts

Status: implemented for backend worker, 2026-11-07; integration pending.
Sources: new backend PDF (2026-11-07), technical specification sections8-11,
acceptance section9, ADR0008/0009. Contract2.1 remains a proposal.

`app.forecast.from_rows` and `read_csv` accept observations only, never scenario
or test-day orders. Require exactly 56 consecutive calendar days strictly before
explicit test_day and every explicitly expected SKU on every day. Production
defaults to the 200-SKU catalog. Tiny fixtures must explicitly supply their SKU
set. Reject missing/duplicate rows, wrong SKU/date grids, noncalendar timestamps,
negative/nonfinite/bool demand, malformed CSV widths/headers, and inconsistent
optional units/split fields. No zero filling or deduplication occurs here.

Offsets0..41 are training;42..55 validation;56 test_day. Targets0..27 are never
fit targets. Mean28 at t is the arithmetic mean of observations[t-28:t]. HGB
fits once on targets28..41 for validation42..55, then fits a fresh final model
on targets28..55 to predict56. Validation is rolling one-day-ahead evaluation:
features may consume earlier observed validation days, never the target or later
days. It is not an open-loop14-day forecast. No tuning or test evaluation occurs.

HGB inputs, in deterministic day-major then lexicographic SKU order, are lags
1/7/14/28, shifted means7/28, weekday (Monday0), then dense one-hot SKU columns
in sorted SKU order. Poisson loss,150 iterations,15 leaves,learning_rate0.06,
l2_regularization1,random_state42. `early_stopping=False` ensures the required
150 iterations even when a larger explicit catalog is used; no random validation
split. Other estimator defaults follow pinned sklearn1.9.1. Native thread pools
are limited to1 during fit/predict for bounded CPU use and stable summation.
For all-zero training targets the Poisson optimum is the constant-zero boundary;
sklearn rejects sum(y)==0, so this declared mathematical fallback returns zero.
No parameter selection follows evaluation. Model choice remains explicit.

ForecastHistory and forecast artifacts store nested tuples and frozen dataclasses;
constructors copy nested caller sequences. Mapping access is read-only; to_dict()
returns fresh JSON-ready containers. Returned snapshots retain predictions and
protocol/parameters, not a mutable sklearn estimator or a pickle. Reproduction
refits from the immutable history and pinned environment.

Snapshot.validation stores total absolute error, total actual visits, WAPE as their
ratio (null when actual total is0), eligible fit/validation row counts and dates.
Snapshots expose last observed date as cutoff and next calendar date as test_day.
CPU process time is reported for validation and final fit/prediction and total
forecast work; the total may include cold-import overhead. Timings are measurements,
never semantic identity inputs. No wall-clock/path value enters semantic identity.

history_hash is SHA256 of canonical normalized visits grid plus sorted SKU IDs,
test_day and `qoima-history-visits-1`. It is invariant to row order, numeric CSV
formatting, units and valid redundant split labels. `read_csv().source_sha256`
separately records the exact input file byte hash. These hashes are intentionally
different: compare source_sha256 with a materializer history_daily.csv manifest,
and use history_hash as forecast demand identity. Semantic snapshot ID hashes
semantic_dict(), including model/protocol, history_hash, dates, parameters/features,
predictions, validation and synthetic_training; all CPU fields are excluded.
Integration MUST hash semantic_dict() or semantic_id, never to_dict() with timing.

Both predictions.visits_by_sku and training_visits_by_sku are expected visits per
full8hday. The training baseline is the first42-day arithmetic mean, independent
of validation and model; it gives the same ABC ranking as first42 sums. Planner
integration consumes plain Mapping[str,float] and scales BOTH maps explicitly by
horizon_s/28800. Forecast code does not apply a promotion multiplier or infer a
scenario horizon. synthetic_training defaults true and is saved in each snapshot.

History cache is a separate seam in app/data/history.py: history_artifact() caches
immutable original CSV bytes once/process, addressed by its sha256;
history_by_hash(hash) verifies the reference and decodes a fresh defensive frame,
including calendar date objects. Existing generate_history() stays uncached for
instrumented generation tests. Materializer integration replaces only its history
CSV expression with history_artifact().csv_bytes, preserving exact original bytes.
No materializer, contracts, frontend, existing other app files or dependencies
are changed by this worker. Main owns forecast references in RunInputs/identity.
