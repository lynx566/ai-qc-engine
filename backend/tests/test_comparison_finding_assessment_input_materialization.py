"""LLM evidence-body rendering for clinical-safety Comparison Finding Assessment."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
    validate_aggregate_comparison_evidence,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.jobs import (
    ComparisonFindingAssessmentGroup,
    ComparisonFindingAssessmentJob,
)


def _evidence() -> dict:
    return build_aggregate_comparison_evidence(
        participants=[
            {
                "role_id": "source",
                "aggregate_evidence_source_bundle_id": "bundle_test",
                "doc_id": "doc_test",
                "file_hash": "sha256:test",
                "scopes": [
                    {
                        "scope_id": "HS0001",
                        "scope_alias": "H0001",
                        "heading_path": ["Overview", "Safety"],
                        "units": [
                            {
                                "unit_id": "TU0001",
                                "unit_alias": "U0001",
                                "sentences": [
                                    {
                                        "sentence_id": "C0001:S001",
                                        "sentence_alias": "T0001",
                                        "text": "Alpha",
                                    },
                                    {
                                        "sentence_id": "C0001:S002",
                                        "sentence_alias": "T0002",
                                        "text": "Beta",
                                    },
                                ],
                            },
                            {
                                "unit_id": "TU0002",
                                "unit_alias": "U0002",
                                "sentences": [
                                    {
                                        "sentence_id": "C0002:S001",
                                        "sentence_alias": "T0003",
                                        "text": "Gamma",
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "scope_id": "HS0002",
                        "scope_alias": "H0002",
                        "heading_path": ["Comparison"],
                        "units": [
                            {
                                "unit_id": "TU0003",
                                "unit_alias": "U0003",
                                "sentences": [
                                    {
                                        "sentence_id": "C0003:S001",
                                        "sentence_alias": "T0004",
                                        "text": "Delta",
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "scope_id": "HS0003",
                        "scope_alias": "H0003",
                        "heading_path": ["IB"],
                        "units": [
                            {
                                "unit_id": "TU0004",
                                "unit_alias": "U0004",
                                "sentences": [
                                    {
                                        "sentence_id": "C0004:S001",
                                        "sentence_alias": "T0005",
                                        "text": "Epsilon",
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ]
    )


def _job(
    comparison_mode_id: str,
    *groups: tuple[str, tuple[str, ...]],
) -> ComparisonFindingAssessmentJob:
    return ComparisonFindingAssessmentJob(
        comparison_mode_id=comparison_mode_id,  # type: ignore[arg-type]
        groups=tuple(
            ComparisonFindingAssessmentGroup(
                group_role=role,  # type: ignore[arg-type]
                scope_aliases=aliases,
            )
            for role, aliases in groups
        ),
    )


def _render(job: ComparisonFindingAssessmentJob) -> str:
    from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.input_materialization import (
        materialize_comparison_finding_assessment_llm_input,
    )

    return materialize_comparison_finding_assessment_llm_input(
        job=job,
        aggregate_comparison_evidence=_evidence(),
    )


def test_scope_local_renders_path_units_and_suffix_citations() -> None:
    rendered = _render(_job("scope_local", ("scope", ("H0001",))))

    assert rendered == (
        "Scope: Overview / Safety\n"
        "Unit U0001\n"
        "- Alpha [T0001]\n"
        "- Beta [T0002]\n"
        "Unit U0002\n"
        "- Gamma [T0003]"
    )
    assert "H0001" not in rendered
    assert "[T0001] Alpha" not in rendered
    assert "Sentence T0001:" not in rendered


def test_focus_rendering_preserves_group_and_scope_order() -> None:
    rendered = _render(
        _job(
            "focus_comparison",
            ("focus_scope", ("H0002",)),
            ("comparison_scopes", ("H0003", "H0001")),
        )
    )

    assert rendered == (
        "## Focus Scope\n"
        "Scope: Comparison\n"
        "Unit U0003\n"
        "- Delta [T0004]\n"
        "\n"
        "## Comparison Scopes\n"
        "Scope: IB\n"
        "Unit U0004\n"
        "- Epsilon [T0005]\n"
        "\n"
        "Scope: Overview / Safety\n"
        "Unit U0001\n"
        "- Alpha [T0001]\n"
        "- Beta [T0002]\n"
        "Unit U0002\n"
        "- Gamma [T0003]"
    )


def test_directional_group_roles_render_fixed_headings() -> None:
    rendered = _render(
        _job(
            "dsur_to_ib",
            ("dsur_scopes", ("H0001", "H0002")),
            ("ib_scopes", ("H0003",)),
        )
    )

    assert rendered.startswith("## DSUR Scopes\nScope: Overview / Safety")
    assert "\n\n## IB Scopes\nScope: IB" in rendered


def test_unknown_scope_alias_fails_fast() -> None:
    with pytest.raises(ValueError, match="unknown scope_alias.*H999999"):
        _render(_job("scope_local", ("scope", ("H999999",))))


def test_duplicate_scope_alias_in_one_group_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate scope_alias.*H0001"):
        _render(
            _job(
                "scope_local",
                ("scope", ("H0001", "H0001")),
            )
        )


def test_batch_materialization_validates_once_and_reuses_scope_index() -> None:
    from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
        input_materialization,
    )

    jobs = (
        _job("scope_local", ("scope", ("H0001",))),
        _job("scope_local", ("scope", ("H0002",))),
    )
    with patch.object(
        input_materialization,
        "validate_aggregate_comparison_evidence",
        wraps=validate_aggregate_comparison_evidence,
    ) as validate:
        rendered = (
            input_materialization.materialize_comparison_finding_assessment_llm_inputs(
                jobs=jobs,
                aggregate_comparison_evidence=_evidence(),
            )
        )

    assert validate.call_count == 1
    assert rendered == (
        (
            "Scope: Overview / Safety\n"
            "Unit U0001\n- Alpha [T0001]\n- Beta [T0002]\n"
            "Unit U0002\n- Gamma [T0003]"
        ),
        "Scope: Comparison\nUnit U0003\n- Delta [T0004]",
    )
