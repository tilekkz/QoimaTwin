# 0002. Exact integer time

Status: accepted, 2026-11-07.

## Context

Walk times such as 4 m / 1.2 m/s = 10/3 s are not exact in binary floating point.
Conveyor admissions happen only on integer seconds. A rounding error can move an admission to the wrong second
(a handoff ready at 32.8 s must be admitted at 33 s, never at 34 s).

## Decision

- Configuration numbers are parsed as `Fraction`.
- `TimeGrid` computes `ticks_per_second = lcm(1_000_000, denominators of all primitive durations)`.
  For the default layout and config this is 3,000,000.
- All runtime times are integers in ticks. A duration that is not exactly representable is a 422 error, never rounded silently.
- Conveyor ticks happen only when `tick % ticks_per_second == 0`. Admission after a timed completion uses an integer ceiling.
- The export carries `at_s` (seconds, for v2 compatibility) and `at_tick` (exact).
- The 1e-6 tolerance from the spec is used only in test assertions on exported seconds.
