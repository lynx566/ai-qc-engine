"""Clinical trial document routing processor."""

from plugins.clinical_trial_doc.routing.inference import (
    RouteDecision,
    infer_route_from_heading,
    is_text_candidate_kind,
    is_text_unit_assembly_kind,
)
from plugins.clinical_trial_doc.routing.projected_sources import (
    route_prepare_units_from_projected_sources,
    validate_projected_sources_semantic_module,
)

__all__ = [
    "RouteDecision",
    "infer_route_from_heading",
    "is_text_candidate_kind",
    "is_text_unit_assembly_kind",
    "route_prepare_units_from_projected_sources",
    "validate_projected_sources_semantic_module",
]
