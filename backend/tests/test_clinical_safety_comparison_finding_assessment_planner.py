"""Planner tests for Clinical Safety Comparison Finding Assessment."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.comparison_finding_assessment_installation import (
    resolve_installed_comparison_finding_assessment_config,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    DsurToIbComparisonModeBinding,
    HeadingSelectionProfile,
    IbToDsurComparisonModeBinding,
    ResolvedClinicalSafetyComparisonFindingAssessmentConfig,
    plan_comparison_finding_assessment_jobs,
    select_scope_aliases_by_heading_profile,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.profiles import (
    DSUR_TO_IB_DSUR_HEADING_SELECTION_PROFILE,
    DSUR_TO_IB_IB_HEADING_SELECTION_PROFILE,
)

_FIXTURE_ROOT = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "evidence_comparison"
    / "clinical_safety"
    / "aggregate_evidence"
)
_INTERNAL_ARTIFACT_PATH = (
    _FIXTURE_ROOT / "internal_dsur" / "aggregate_comparison_evidence.json"
)
_CROSS_ARTIFACT_PATH = (
    _FIXTURE_ROOT / "dsur_updated_ib" / "aggregate_comparison_evidence.json"
)


def _sentence(*, sentence_id: str, sentence_alias: str, text: str) -> dict:
    return {
        "sentence_id": sentence_id,
        "sentence_alias": sentence_alias,
        "text": text,
    }


def _unit(*, unit_id: str, unit_alias: str, sentence: dict) -> dict:
    return {
        "unit_id": unit_id,
        "unit_alias": unit_alias,
        "sentences": [sentence],
    }


def _scope(
    *,
    scope_id: str,
    scope_alias: str,
    heading_path: list[str],
    unit: dict,
) -> dict:
    return {
        "scope_id": scope_id,
        "scope_alias": scope_alias,
        "heading_path": heading_path,
        "units": [unit],
    }


def _participant(
    *,
    role_id: str,
    scopes: list[dict],
    participant_index: int,
) -> dict:
    return {
        "role_id": role_id,
        "aggregate_evidence_source_bundle_id": (
            f"aggregate_evidence_source_bundle_{participant_index:03d}"
        ),
        "doc_id": f"doc_{role_id}",
        "file_hash": f"sha256:{role_id}",
        "scopes": scopes,
    }


def _build_evidence(*participants: dict) -> dict:
    return build_aggregate_comparison_evidence(participants=participants)


def _single_scope_evidence(
    *,
    role_id: str,
    scope_aliases: tuple[str, ...],
    heading_paths: tuple[list[str], ...] | None = None,
) -> dict:
    scopes: list[dict] = []
    for index, alias in enumerate(scope_aliases):
        heading = (
            heading_paths[index] if heading_paths is not None else [f"Heading {alias}"]
        )
        scopes.append(
            _scope(
                scope_id=f"HS{index + 1:04d}",
                scope_alias=alias,
                heading_path=heading,
                unit=_unit(
                    unit_id=f"TU{index + 1:04d}",
                    unit_alias=f"U{index + 1:04d}",
                    sentence=_sentence(
                        sentence_id=f"C{index + 1:04d}:S001",
                        sentence_alias=f"T{index + 1:04d}",
                        text=f"text for {alias}",
                    ),
                ),
            )
        )
    return _build_evidence(
        _participant(role_id=role_id, scopes=scopes, participant_index=1)
    )


def _internal_config() -> ResolvedClinicalSafetyComparisonFindingAssessmentConfig:
    return ResolvedClinicalSafetyComparisonFindingAssessmentConfig(
        enabled_comparison_modes=("scope_local", "focus_comparison"),
        participant_role_ids=("source",),
    )


def _cross_ib_to_dsur_config(
    *,
    focus_role_id: str,
    comparison_role_id: str,
) -> ResolvedClinicalSafetyComparisonFindingAssessmentConfig:
    return ResolvedClinicalSafetyComparisonFindingAssessmentConfig(
        enabled_comparison_modes=("ib_to_dsur",),
        participant_role_ids=(focus_role_id, comparison_role_id),
        ib_to_dsur=IbToDsurComparisonModeBinding(
            focus_role_id=focus_role_id,
            comparison_role_id=comparison_role_id,
        ),
    )


def _cross_dsur_to_ib_config(
    *,
    dsur_role_id: str,
    ib_role_id: str,
    dsur_profile: HeadingSelectionProfile = DSUR_TO_IB_DSUR_HEADING_SELECTION_PROFILE,
    ib_profile: HeadingSelectionProfile = DSUR_TO_IB_IB_HEADING_SELECTION_PROFILE,
) -> ResolvedClinicalSafetyComparisonFindingAssessmentConfig:
    return ResolvedClinicalSafetyComparisonFindingAssessmentConfig(
        enabled_comparison_modes=("dsur_to_ib",),
        participant_role_ids=(dsur_role_id, ib_role_id),
        dsur_to_ib=DsurToIbComparisonModeBinding(
            dsur_role_id=dsur_role_id,
            ib_role_id=ib_role_id,
            dsur_scope_selection=dsur_profile,
            ib_scope_selection=ib_profile,
        ),
    )


def test_scope_local_generates_one_job_per_scope_in_order() -> None:
    evidence = _single_scope_evidence(
        role_id="source",
        scope_aliases=("H0001", "H0002", "H0003"),
    )
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=_internal_config(),
    )
    local_jobs = [job for job in jobs if job.comparison_mode_id == "scope_local"]
    assert len(local_jobs) == 3
    assert [job.groups[0].scope_aliases[0] for job in local_jobs] == [
        "H0001",
        "H0002",
        "H0003",
    ]
    assert all(job.groups[0].group_role == "scope" for job in local_jobs)


def test_focus_comparison_rotates_focus_and_preserves_comparison_order() -> None:
    evidence = _single_scope_evidence(
        role_id="source",
        scope_aliases=("H0001", "H0002", "H0003"),
    )
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=_internal_config(),
    )
    focus_jobs = [job for job in jobs if job.comparison_mode_id == "focus_comparison"]
    assert len(focus_jobs) == 3

    assert focus_jobs[0].groups[0].group_role == "focus_scope"
    assert focus_jobs[0].groups[0].scope_aliases == ("H0001",)
    assert focus_jobs[0].groups[1].scope_aliases == ("H0002", "H0003")

    assert focus_jobs[1].groups[0].scope_aliases == ("H0002",)
    assert focus_jobs[1].groups[1].scope_aliases == ("H0001", "H0003")

    assert focus_jobs[2].groups[0].scope_aliases == ("H0003",)
    assert focus_jobs[2].groups[1].scope_aliases == ("H0001", "H0002")


def test_focus_comparison_with_one_scope_generates_zero_jobs() -> None:
    evidence = _single_scope_evidence(role_id="source", scope_aliases=("H0001",))
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=ResolvedClinicalSafetyComparisonFindingAssessmentConfig(
            enabled_comparison_modes=("scope_local", "focus_comparison"),
            participant_role_ids=("source",),
        ),
    )
    assert [job.comparison_mode_id for job in jobs] == ["scope_local"]
    assert jobs[0].groups[0].scope_aliases == ("H0001",)


def test_enabled_view_ordering_scope_local_before_focus_comparison() -> None:
    evidence = _single_scope_evidence(
        role_id="source",
        scope_aliases=("H0001", "H0002"),
    )
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=_internal_config(),
    )
    assert [job.comparison_mode_id for job in jobs] == [
        "scope_local",
        "scope_local",
        "focus_comparison",
        "focus_comparison",
    ]


def test_ib_to_dsur_uses_config_role_bindings_not_hardcoded_roles() -> None:
    evidence = _build_evidence(
        _participant(
            role_id="role_alpha",
            participant_index=1,
            scopes=[
                _scope(
                    scope_id="HS0001",
                    scope_alias="H0001",
                    heading_path=["alpha one"],
                    unit=_unit(
                        unit_id="TU0001",
                        unit_alias="U0001",
                        sentence=_sentence(
                            sentence_id="C0001:S001",
                            sentence_alias="T0001",
                            text="alpha",
                        ),
                    ),
                ),
                _scope(
                    scope_id="HS0002",
                    scope_alias="H0002",
                    heading_path=["alpha two"],
                    unit=_unit(
                        unit_id="TU0002",
                        unit_alias="U0002",
                        sentence=_sentence(
                            sentence_id="C0002:S001",
                            sentence_alias="T0002",
                            text="alpha",
                        ),
                    ),
                ),
                _scope(
                    scope_id="HS0003",
                    scope_alias="H0003",
                    heading_path=["alpha three"],
                    unit=_unit(
                        unit_id="TU0003",
                        unit_alias="U0003",
                        sentence=_sentence(
                            sentence_id="C0003:S001",
                            sentence_alias="T0003",
                            text="alpha",
                        ),
                    ),
                ),
            ],
        ),
        _participant(
            role_id="role_beta",
            participant_index=2,
            scopes=[
                _scope(
                    scope_id="HS0004",
                    scope_alias="H0004",
                    heading_path=["beta one"],
                    unit=_unit(
                        unit_id="TU0004",
                        unit_alias="U0004",
                        sentence=_sentence(
                            sentence_id="C0004:S001",
                            sentence_alias="T0004",
                            text="beta",
                        ),
                    ),
                ),
                _scope(
                    scope_id="HS0005",
                    scope_alias="H0005",
                    heading_path=["beta two"],
                    unit=_unit(
                        unit_id="TU0005",
                        unit_alias="U0005",
                        sentence=_sentence(
                            sentence_id="C0005:S001",
                            sentence_alias="T0005",
                            text="beta",
                        ),
                    ),
                ),
            ],
        ),
    )
    config = _cross_ib_to_dsur_config(
        focus_role_id="role_beta",
        comparison_role_id="role_alpha",
    )
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=config,
    )
    assert len(jobs) == 2
    assert jobs[0].groups[0].scope_aliases == ("H0004",)
    assert jobs[0].groups[1].scope_aliases == ("H0001", "H0002", "H0003")
    assert jobs[1].groups[0].scope_aliases == ("H0005",)
    assert jobs[1].groups[1].scope_aliases == ("H0001", "H0002", "H0003")


def test_ib_to_dsur_on_real_cross_artifact_structure() -> None:
    evidence = json.loads(_CROSS_ARTIFACT_PATH.read_text(encoding="utf-8"))
    config = _cross_ib_to_dsur_config(
        focus_role_id="source_b",
        comparison_role_id="source_a",
    )
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=config,
    )
    assert len(jobs) == 5
    comparison_aliases = tuple(f"H{i:04d}" for i in range(1, 11))
    for index, job in enumerate(jobs, start=11):
        assert job.comparison_mode_id == "ib_to_dsur"
        assert job.groups[0].group_role == "ib_scope"
        assert job.groups[1].group_role == "dsur_scopes"
        assert job.groups[0].scope_aliases == (f"H{index:04d}",)
        assert job.groups[1].scope_aliases == comparison_aliases


def test_ib_to_dsur_input_headings_use_ib_and_dsur_vocabulary() -> None:
    from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
        materialize_comparison_finding_assessment_llm_input,
    )

    evidence = json.loads(_CROSS_ARTIFACT_PATH.read_text(encoding="utf-8"))
    config = _cross_ib_to_dsur_config(
        focus_role_id="source_b",
        comparison_role_id="source_a",
    )
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=config,
    )
    rendered = materialize_comparison_finding_assessment_llm_input(
        job=jobs[0],
        aggregate_comparison_evidence=evidence,
    )
    assert rendered.startswith("## IB Scope\n")
    assert "\n\n## DSUR Scopes\n" in rendered


def test_dsur_to_ib_selection_and_single_job_topology() -> None:
    evidence = _build_evidence(
        _participant(
            role_id="dsur_side",
            participant_index=1,
            scopes=[
                _scope(
                    scope_id="HS0001",
                    scope_alias="H0001",
                    heading_path=["无关章节"],
                    unit=_unit(
                        unit_id="TU0001",
                        unit_alias="U0001",
                        sentence=_sentence(
                            sentence_id="C0001:S001",
                            sentence_alias="T0001",
                            text="x",
                        ),
                    ),
                ),
                _scope(
                    scope_id="HS0002",
                    scope_alias="H0002",
                    heading_path=["4.安全性参考信息变更"],
                    unit=_unit(
                        unit_id="TU0002",
                        unit_alias="U0002",
                        sentence=_sentence(
                            sentence_id="C0002:S001",
                            sentence_alias="T0002",
                            text="x",
                        ),
                    ),
                ),
                _scope(
                    scope_id="HS0003",
                    scope_alias="H0003",
                    heading_path=["19.重要风险总结"],
                    unit=_unit(
                        unit_id="TU0003",
                        unit_alias="U0003",
                        sentence=_sentence(
                            sentence_id="C0003:S001",
                            sentence_alias="T0003",
                            text="x",
                        ),
                    ),
                ),
            ],
        ),
        _participant(
            role_id="ib_side",
            participant_index=2,
            scopes=[
                _scope(
                    scope_id="HS0004",
                    scope_alias="H0004",
                    heading_path=["七、数据总结与研究者指南"],
                    unit=_unit(
                        unit_id="TU0004",
                        unit_alias="U0004",
                        sentence=_sentence(
                            sentence_id="C0004:S001",
                            sentence_alias="T0004",
                            text="x",
                        ),
                    ),
                ),
                _scope(
                    scope_id="HS0005",
                    scope_alias="H0005",
                    heading_path=["八. 安全性参考信息"],
                    unit=_unit(
                        unit_id="TU0005",
                        unit_alias="U0005",
                        sentence=_sentence(
                            sentence_id="C0005:S001",
                            sentence_alias="T0005",
                            text="x",
                        ),
                    ),
                ),
            ],
        ),
    )
    config = _cross_dsur_to_ib_config(
        dsur_role_id="dsur_side",
        ib_role_id="ib_side",
    )
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=config,
    )
    assert len(jobs) == 1
    assert jobs[0].comparison_mode_id == "dsur_to_ib"
    assert jobs[0].groups[0].group_role == "dsur_scopes"
    assert jobs[0].groups[0].scope_aliases == ("H0002", "H0003")
    assert jobs[0].groups[1].group_role == "ib_scopes"
    assert jobs[0].groups[1].scope_aliases == ("H0004", "H0005")


def test_heading_profile_exclude_terms_override_include_match() -> None:
    scopes = [
        {
            "scope_alias": "H0001",
            "heading_path": ["重要风险总结"],
        },
        {
            "scope_alias": "H0002",
            "heading_path": ["重要风险总结（排除项）"],
        },
    ]
    profile = HeadingSelectionProfile(
        include_terms=("重要风险",),
        exclude_terms=("排除项",),
        match_mode="contains",
    )
    selected = select_scope_aliases_by_heading_profile(
        scopes=scopes,
        profile=profile,
    )
    assert selected == ("H0001",)


def test_dsur_to_ib_empty_selection_generates_zero_jobs() -> None:
    evidence = _single_scope_evidence(
        role_id="dsur_side",
        scope_aliases=("H0001",),
        heading_paths=(["无关章节"],),
    )
    evidence = build_aggregate_comparison_evidence(
        participants=[
            evidence["participants"][0],
            _participant(
                role_id="ib_side",
                participant_index=2,
                scopes=[
                    _scope(
                        scope_id="HS0002",
                        scope_alias="H0002",
                        heading_path=["八. 安全性参考信息"],
                        unit=_unit(
                            unit_id="TU0002",
                            unit_alias="U0002",
                            sentence=_sentence(
                                sentence_id="C0002:S001",
                                sentence_alias="T0002",
                                text="x",
                            ),
                        ),
                    )
                ],
            ),
        ]
    )
    config = _cross_dsur_to_ib_config(
        dsur_role_id="dsur_side",
        ib_role_id="ib_side",
    )
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=config,
    )
    assert jobs == ()


def test_ib_to_dsur_with_empty_comparison_scope_aliases_generates_zero_jobs() -> None:
    from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.planner import (
        _plan_ib_to_dsur_jobs,
    )

    assert (
        _plan_ib_to_dsur_jobs(
            focus_scope_aliases=("H0001",),
            comparison_scope_aliases=(),
        )
        == ()
    )


def test_missing_config_role_in_evidence_fails_clearly() -> None:
    evidence = _single_scope_evidence(role_id="source", scope_aliases=("H0001",))
    config = _cross_ib_to_dsur_config(
        focus_role_id="missing_focus",
        comparison_role_id="source",
    )
    with pytest.raises(
        ValueError,
        match="participant role_id='missing_focus' is not present in aggregate evidence",
    ):
        plan_comparison_finding_assessment_jobs(
            aggregate_comparison_evidence=evidence,
            config=config,
        )


def test_installed_dsur_updated_ib_config_plans_without_capability_id() -> None:
    evidence = json.loads(_CROSS_ARTIFACT_PATH.read_text(encoding="utf-8"))
    config = resolve_installed_comparison_finding_assessment_config("dsur_updated_ib")
    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=config,
    )
    ib_to_dsur_jobs = [job for job in jobs if job.comparison_mode_id == "ib_to_dsur"]
    dsur_to_ib_jobs = [job for job in jobs if job.comparison_mode_id == "dsur_to_ib"]
    assert len(ib_to_dsur_jobs) == 5
    assert len(dsur_to_ib_jobs) == 1
    assert dsur_to_ib_jobs[0].groups[0].scope_aliases == ("H0003", "H0009")
    assert dsur_to_ib_jobs[0].groups[1].scope_aliases == ("H0014", "H0015")


def test_installed_internal_dsur_config_preserves_twenty_job_topology() -> None:
    evidence = json.loads(_INTERNAL_ARTIFACT_PATH.read_text(encoding="utf-8"))
    config = resolve_installed_comparison_finding_assessment_config("internal_dsur")

    jobs = plan_comparison_finding_assessment_jobs(
        aggregate_comparison_evidence=evidence,
        config=config,
    )

    assert len(jobs) == 20
    assert [job.comparison_mode_id for job in jobs] == [
        *("scope_local" for _ in range(10)),
        *("focus_comparison" for _ in range(10)),
    ]
