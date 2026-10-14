"""Configuration and installation tests for Clinical Safety Comparison Finding Assessment."""

from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS,
)
from application.clinical_trial_doc_consistency_qc.comparison_finding_assessment_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_CONFIGS,
    resolve_clinical_safety_comparison_finding_assessment_config,
    resolve_installed_comparison_finding_assessment_config,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentCapabilityDeclaration,
    DsurToIbComparisonModeBinding,
    HeadingSelectionProfile,
    IbToDsurComparisonModeBinding,
    ResolvedClinicalSafetyComparisonFindingAssessmentConfig,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.profiles import (
    DSUR_TO_IB_DSUR_HEADING_SELECTION_PROFILE,
    DSUR_TO_IB_IB_HEADING_SELECTION_PROFILE,
)


def _single_source_declaration() -> ComparisonFindingAssessmentCapabilityDeclaration:
    return ComparisonFindingAssessmentCapabilityDeclaration(
        enabled_comparison_modes=("scope_local", "focus_comparison"),
        participant_role_ids=("source",),
    )


def _cross_declaration() -> ComparisonFindingAssessmentCapabilityDeclaration:
    return ComparisonFindingAssessmentCapabilityDeclaration(
        enabled_comparison_modes=("ib_to_dsur", "dsur_to_ib"),
        participant_role_ids=("source_a", "source_b"),
        ib_to_dsur=IbToDsurComparisonModeBinding(
            focus_role_id="source_b",
            comparison_role_id="source_a",
        ),
        dsur_to_ib=DsurToIbComparisonModeBinding(
            dsur_role_id="source_a",
            ib_role_id="source_b",
            dsur_scope_selection=DSUR_TO_IB_DSUR_HEADING_SELECTION_PROFILE,
            ib_scope_selection=DSUR_TO_IB_IB_HEADING_SELECTION_PROFILE,
        ),
    )


@pytest.mark.parametrize(
    ("capability_id", "expected_views"),
    [
        ("internal_csr", ("scope_local", "focus_comparison")),
        ("internal_dsur", ("scope_local", "focus_comparison")),
        ("internal_ib", ("scope_local", "focus_comparison")),
        ("dsur_updated_ib", ("ib_to_dsur", "dsur_to_ib")),
    ],
)
def test_installed_capability_comparison_mode_mapping(
    capability_id: str,
    expected_views: tuple[str, ...],
) -> None:
    declaration = INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS[
        capability_id
    ]
    assert declaration.enabled_comparison_modes == expected_views

    resolved = resolve_installed_comparison_finding_assessment_config(capability_id)
    assert resolved.enabled_comparison_modes == expected_views


def test_cross_role_bindings_in_resolved_config() -> None:
    resolved = resolve_installed_comparison_finding_assessment_config("dsur_updated_ib")

    assert resolved.ib_to_dsur is not None
    assert resolved.ib_to_dsur.focus_role_id == "source_b"
    assert resolved.ib_to_dsur.comparison_role_id == "source_a"

    assert resolved.dsur_to_ib is not None
    assert resolved.dsur_to_ib.dsur_role_id == "source_a"
    assert resolved.dsur_to_ib.ib_role_id == "source_b"


def test_dsur_to_ib_selection_profiles_lock_semantic_targets() -> None:
    resolved = resolve_installed_comparison_finding_assessment_config("dsur_updated_ib")
    assert resolved.dsur_to_ib is not None

    dsur_terms = resolved.dsur_to_ib.dsur_scope_selection.include_terms
    ib_terms = resolved.dsur_to_ib.ib_scope_selection.include_terms

    assert "安全性参考信息" in dsur_terms
    assert "重要风险" in dsur_terms
    assert "研究者指南" in ib_terms
    assert "安全性参考信息" in ib_terms

    assert "4.安全性参考信息变更" not in dsur_terms
    assert "19.重要风险总结" not in dsur_terms
    assert "七、数据总结与研究者指南" not in ib_terms


def test_resolved_config_has_no_runtime_or_prompt_fields() -> None:
    resolved = resolve_installed_comparison_finding_assessment_config("dsur_updated_ib")
    field_names = {field.name for field in fields(resolved)}
    forbidden = {
        "capability_id",
        "document_type",
        "prompt_strategy_id",
        "prompt_id",
        "template_id",
    }
    assert forbidden.isdisjoint(field_names)

    payload = repr(resolved)
    assert "prompt_strategy_id" not in payload
    assert "document_type" not in payload


def test_installed_configs_cover_all_declarations() -> None:
    assert set(INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_CONFIGS) == set(
        INSTALLED_CLINICAL_TRIAL_DOC_COMPARISON_FINDING_ASSESSMENT_DECLARATIONS
    )


def test_ib_to_dsur_config_rejects_same_role_on_both_sides() -> None:
    with pytest.raises(
        ValueError,
        match="focus_role_id and comparison_role_id must differ",
    ):
        IbToDsurComparisonModeBinding(
            focus_role_id="source_a",
            comparison_role_id="source_a",
        )


def test_dsur_to_ib_config_rejects_same_role_on_both_sides() -> None:
    with pytest.raises(ValueError, match="dsur_role_id and ib_role_id must differ"):
        DsurToIbComparisonModeBinding(
            dsur_role_id="source_a",
            ib_role_id="source_a",
            dsur_scope_selection=DSUR_TO_IB_DSUR_HEADING_SELECTION_PROFILE,
            ib_scope_selection=DSUR_TO_IB_IB_HEADING_SELECTION_PROFILE,
        )


@pytest.mark.parametrize(
    ("declaration", "error_match"),
    [
        (
            ComparisonFindingAssessmentCapabilityDeclaration(
                enabled_comparison_modes=(),
                participant_role_ids=("source",),
            ),
            "enabled_comparison_modes must be a non-empty tuple",
        ),
        (
            ComparisonFindingAssessmentCapabilityDeclaration(
                enabled_comparison_modes=("unknown_view",),
                participant_role_ids=("source",),
            ),
            "unknown comparison mode id",
        ),
        (
            ComparisonFindingAssessmentCapabilityDeclaration(
                enabled_comparison_modes=("scope_local", "scope_local"),
                participant_role_ids=("source",),
            ),
            "duplicate comparison mode id",
        ),
        (
            ComparisonFindingAssessmentCapabilityDeclaration(
                enabled_comparison_modes=("ib_to_dsur", "dsur_to_ib"),
                participant_role_ids=("source_a", "source_b"),
            ),
            "ib_to_dsur comparison mode requires ib_to_dsur configuration",
        ),
        (
            ComparisonFindingAssessmentCapabilityDeclaration(
                enabled_comparison_modes=("ib_to_dsur",),
                participant_role_ids=("source",),
                ib_to_dsur=IbToDsurComparisonModeBinding(
                    focus_role_id="source_b",
                    comparison_role_id="source_a",
                ),
            ),
            "cross comparison modes require at least two participant role IDs",
        ),
        (
            ComparisonFindingAssessmentCapabilityDeclaration(
                enabled_comparison_modes=("ib_to_dsur",),
                participant_role_ids=("source_a", "source_b"),
            ),
            "ib_to_dsur comparison mode requires ib_to_dsur configuration",
        ),
        (
            ComparisonFindingAssessmentCapabilityDeclaration(
                enabled_comparison_modes=("dsur_to_ib",),
                participant_role_ids=("source_a", "source_b"),
            ),
            "dsur_to_ib comparison mode requires dsur_to_ib configuration",
        ),
        (
            ComparisonFindingAssessmentCapabilityDeclaration(
                enabled_comparison_modes=("dsur_to_ib",),
                participant_role_ids=("source_a", "source_b"),
                dsur_to_ib=DsurToIbComparisonModeBinding(
                    dsur_role_id="source_a",
                    ib_role_id="source_b",
                    dsur_scope_selection=HeadingSelectionProfile(
                        include_terms=("安全性参考信息",),
                    ),
                    ib_scope_selection=HeadingSelectionProfile(
                        include_terms=("研究者指南",),
                    ),
                ),
                ib_to_dsur=IbToDsurComparisonModeBinding(
                    focus_role_id="source_b",
                    comparison_role_id="source_a",
                ),
            ),
            "ib_to_dsur configuration requires ib_to_dsur comparison mode",
        ),
        (
            ComparisonFindingAssessmentCapabilityDeclaration(
                enabled_comparison_modes=("ib_to_dsur",),
                participant_role_ids=("source_a", "source_b"),
                ib_to_dsur=IbToDsurComparisonModeBinding(
                    focus_role_id="missing_role",
                    comparison_role_id="source_a",
                ),
            ),
            "ib_to_dsur.focus_role_id",
        ),
        (
            ComparisonFindingAssessmentCapabilityDeclaration(
                enabled_comparison_modes=("scope_local", "ib_to_dsur"),
                participant_role_ids=("source_a", "source_b"),
                ib_to_dsur=IbToDsurComparisonModeBinding(
                    focus_role_id="source_b",
                    comparison_role_id="source_a",
                ),
            ),
            "single-source and cross comparison modes cannot be enabled together",
        ),
    ],
)
def test_resolve_rejects_invalid_declarations(
    declaration: ComparisonFindingAssessmentCapabilityDeclaration,
    error_match: str,
) -> None:
    with pytest.raises((ValueError, TypeError), match=error_match):
        resolve_clinical_safety_comparison_finding_assessment_config(declaration)


def test_heading_selection_profile_rejects_empty_include_terms() -> None:
    with pytest.raises(ValueError, match="include_terms must be a non-empty tuple"):
        HeadingSelectionProfile(include_terms=())


def test_resolve_accepts_valid_single_and_cross_declarations() -> None:
    single = resolve_clinical_safety_comparison_finding_assessment_config(
        _single_source_declaration()
    )
    assert isinstance(single, ResolvedClinicalSafetyComparisonFindingAssessmentConfig)
    assert single.ib_to_dsur is None
    assert single.dsur_to_ib is None

    cross = resolve_clinical_safety_comparison_finding_assessment_config(
        _cross_declaration()
    )
    assert cross.ib_to_dsur is not None
    assert cross.dsur_to_ib is not None


def test_resolve_installed_rejects_unknown_capability() -> None:
    with pytest.raises(KeyError, match="unknown capability_id"):
        resolve_installed_comparison_finding_assessment_config("unknown_capability")
