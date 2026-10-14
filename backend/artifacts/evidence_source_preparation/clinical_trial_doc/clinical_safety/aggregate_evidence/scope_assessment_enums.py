"""Canonical enum and nested-object field contracts for scope_assessments.json.

These values are shared with legacy ``tag_output.json`` tagged-item QC slots
where scope assessment reuses the same closed enum sets. Scope-assessment
artifact code must import from this module, not from ``core.tagging.schema.tag_output``.
"""

from __future__ import annotations

UNIT_FORM_VALUES = frozenset(
    {
        "aggregate",
        "case_like",
        "listing_like",
        "mixed",
        "non_safety",
        "table_like",
        "unknown",
    }
)

SAFETY_ROLE_VALUES = frozenset(
    {
        "not_applicable",
        "primary_safety_finding",
        "safety_context",
        "unknown",
    }
)

SUGGESTED_ROUTE_VALUES = frozenset(
    {
        "aggregate",
        "case",
        "efficacy",
        "exclude",
        "non_safety",
        "pk",
        "table",
        "unknown",
    }
)

PRODUCT_CONTEXT_ROLE_VALUES = frozenset(
    {
        "background_only",
        "class_background",
        "comparator",
        "reference_product",
        "target_combination",
        "target_study_drug",
        "unknown",
    }
)

ROUTE_QC_OBJECT_FIELDS = frozenset(
    {
        "reason",
        "route_mismatch",
        "suggested_route",
    }
)
