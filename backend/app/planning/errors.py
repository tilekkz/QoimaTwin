"""Planning input errors (reported as HTTP 422 by the future API)."""

from __future__ import annotations


class PlanningInputError(ValueError):
    """Planning inputs or a plan artifact are inconsistent; nothing is corrected silently."""
