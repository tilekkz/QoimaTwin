"""Baseline/candidate slotting comparison (01 §10, 05 §9, ADR 0016).

- `compare_slotting(baseline_inputs, plan)`: validated pair, two invariant-checked runs and a
  JSON-ready `ComparisonArtifact` with labor at H and at end, net of relocation labor.
- `validate_slotting_pair(baseline, candidate, plan)`: input equality only.
- `labor_breakdown(...)`: pure labor accounting by actor and role.
"""

from app.comparison.compare import RunCallback, compare_slotting
from app.comparison.errors import ComparisonInputError
from app.comparison.labor import LaborEntry, LaborSummary, labor_breakdown
from app.comparison.models import ComparisonArtifact, RunSide, WindowComparison
from app.comparison.validation import validate_slotting_pair

__all__ = [
    "ComparisonArtifact",
    "ComparisonInputError",
    "LaborEntry",
    "LaborSummary",
    "RunCallback",
    "RunSide",
    "WindowComparison",
    "compare_slotting",
    "labor_breakdown",
    "validate_slotting_pair",
]
