"""Generic Comparison Finding Consolidation capability."""

from .alias_qc import (
    ComparisonFindingConsolidationAliasQcResult,
    ComparisonFindingConsolidationGroupAliasQcResult,
    compute_comparison_finding_consolidation_alias_qc,
)
from .config import (
    ComparisonFindingConsolidationCapabilityDeclaration,
    ResolvedComparisonFindingConsolidationConfig,
)
from .execution import (
    ComparisonFindingConsolidationExecution,
    execute_comparison_finding_consolidation,
)
from .input_materialization import (
    ComparisonFindingConsolidationFindingProjection,
    ComparisonFindingConsolidationInput,
    materialize_comparison_finding_consolidation_input,
    materialize_comparison_finding_consolidation_projections,
)
from .reconciliation import (
    ComparisonFindingConsolidationReconciliationError,
    ComparisonFindingConsolidationReconciliationResult,
    ConsolidatedFindingDraft,
    PassthroughFindingDraft,
    ReconciledFindingDraft,
    ReconciledFindingLabel,
    reconcile_mode_findings,
)
from .response_validation import (
    ComparisonFindingConsolidatedGroup,
    ComparisonFindingConsolidationParseError,
    ComparisonFindingConsolidationValidatedResponse,
    ComparisonFindingConsolidationValidationError,
    parse_and_validate_comparison_finding_consolidation_response,
)

__all__ = [
    "ComparisonFindingConsolidatedGroup",
    "ComparisonFindingConsolidationAliasQcResult",
    "ComparisonFindingConsolidationCapabilityDeclaration",
    "ComparisonFindingConsolidationExecution",
    "ComparisonFindingConsolidationFindingProjection",
    "ComparisonFindingConsolidationGroupAliasQcResult",
    "ComparisonFindingConsolidationInput",
    "ComparisonFindingConsolidationParseError",
    "ComparisonFindingConsolidationReconciliationError",
    "ComparisonFindingConsolidationReconciliationResult",
    "ComparisonFindingConsolidationValidatedResponse",
    "ComparisonFindingConsolidationValidationError",
    "ConsolidatedFindingDraft",
    "PassthroughFindingDraft",
    "ReconciledFindingDraft",
    "ReconciledFindingLabel",
    "ResolvedComparisonFindingConsolidationConfig",
    "compute_comparison_finding_consolidation_alias_qc",
    "execute_comparison_finding_consolidation",
    "materialize_comparison_finding_consolidation_input",
    "materialize_comparison_finding_consolidation_projections",
    "parse_and_validate_comparison_finding_consolidation_response",
    "reconcile_mode_findings",
]
