"""Comparison input errors (reported as HTTP 422 by the future API)."""

from __future__ import annotations


class ComparisonInputError(ValueError):
    """Baseline and candidate inputs differ beyond assignment and paid relocation."""
