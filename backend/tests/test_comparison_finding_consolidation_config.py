"""Tests for generic Comparison Finding Consolidation configuration."""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.config import (
    ComparisonFindingConsolidationCapabilityDeclaration,
    ResolvedComparisonFindingConsolidationConfig,
)


@pytest.mark.parametrize(
    "config_type",
    [
        ComparisonFindingConsolidationCapabilityDeclaration,
        ResolvedComparisonFindingConsolidationConfig,
    ],
)
def test_consolidation_config_is_immutable_and_accepts_enabled_modes(
    config_type,
) -> None:
    config = config_type(enabled_comparison_modes=("focus_comparison",))

    assert config.enabled_comparison_modes == ("focus_comparison",)
    with pytest.raises(FrozenInstanceError):
        config.enabled_comparison_modes = ()


@pytest.mark.parametrize(
    "config_type",
    [
        ComparisonFindingConsolidationCapabilityDeclaration,
        ResolvedComparisonFindingConsolidationConfig,
    ],
)
def test_consolidation_config_accepts_empty_modes_for_identity_capability(
    config_type,
) -> None:
    config = config_type(enabled_comparison_modes=())

    assert config.enabled_comparison_modes == ()


@pytest.mark.parametrize(
    "config_type",
    [
        ComparisonFindingConsolidationCapabilityDeclaration,
        ResolvedComparisonFindingConsolidationConfig,
    ],
)
def test_consolidation_config_rejects_duplicate_modes(config_type) -> None:
    with pytest.raises(ValueError, match="duplicate comparison mode id"):
        config_type(
            enabled_comparison_modes=("focus_comparison", "focus_comparison")
        )


@pytest.mark.parametrize(
    "config_type",
    [
        ComparisonFindingConsolidationCapabilityDeclaration,
        ResolvedComparisonFindingConsolidationConfig,
    ],
)
def test_consolidation_config_rejects_unknown_modes(config_type) -> None:
    with pytest.raises(ValueError, match="unknown comparison mode id"):
        config_type(enabled_comparison_modes=("unknown",))
