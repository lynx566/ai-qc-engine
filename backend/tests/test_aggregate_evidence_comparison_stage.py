"""Canonical clinical-safety aggregate Evidence Comparison stage runtime tests."""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.comparison_finding_assessment_installation import (
    resolve_installed_comparison_finding_assessment_config,
)
from application.clinical_trial_doc_consistency_qc.comparison_finding_consolidation_installation import (
    resolve_installed_comparison_finding_consolidation_config,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    AGGREGATE_COMPARISON_EVIDENCE_FILENAME,
    FINAL_FINDINGS_FILENAME,
    FINDINGS_FILENAME,
    FINDINGS_SCHEMA_VERSION,
    validate_aggregate_comparison_evidence,
    validate_final_findings,
    validate_findings,
)
from llm.execution_configs import (
    CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID,
    resolve_llm_execution_config,
)
from llm.providers.base import LLMRawResult
from operations.evidence_comparison.participants import (
    EvidenceComparisonParticipantReference,
)
from operations.evidence_comparison.stage import (
    EvidenceComparisonExecutionDependencies,
    EvidenceComparisonStageContext,
    EvidenceComparisonStageInput,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence import (
    CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR,
    AggregateEvidenceComparisonFinalizationError,
    AggregateEvidenceComparisonFinalizationFailure,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment.planner import (
    plan_comparison_finding_assessment_jobs,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.persistence import (
    COMPARISON_FINDING_CONSOLIDATION_DIRNAME,
    RUN_SUMMARY_FILENAME,
    persist_unified_aggregate_evidence_comparison_execution,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_STAGE_EXECUTOR_ID,
    ClinicalTrialAggregateEvidenceComparisonExecutionDependencies,
    build_aggregate_evidence_comparison_invocation_from_stage_input,
    build_clinical_trial_aggregate_evidence_comparison_stage_executor,
    execute_clinical_trial_aggregate_evidence_comparison_stage,
)
from runtime.io import load_json
from tests.current_evidence_comparison_test_helpers import (
    write_current_ec_source_fixture,
)

_PLUGIN_ROOT = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_comparison"
    / "clinical_safety"
    / "aggregate_evidence"
)
_RUNTIME_AGGREGATE_ROOT = (
    BACKEND_ROOT
    / "runtime"
    / "evidence_comparison"
    / "clinical_trial_doc"
    / "clinical_safety"
    / "aggregate_evidence"
)


def _participant(*, role_id: str, slot_id: str, path: Path):
    return EvidenceComparisonParticipantReference(
        role_id=role_id,
        slot_id=slot_id,
        semantic_module_id="aggregate_evidence",
        declared_output_path=path,
    )


def _execution_dependencies(
    *,
    capability_id: str = "internal_dsur",
    assessment_provider,
    assessment_second_pass_provider=None,
    verification_provider=None,
    consolidation_provider=None,
):
    if assessment_second_pass_provider is None:
        assessment_second_pass_provider = assessment_provider
    if verification_provider is None:
        verification_provider = assessment_provider
    if consolidation_provider is None:
        consolidation_provider = _EmptyConsolidationProvider()
    return ClinicalTrialAggregateEvidenceComparisonExecutionDependencies(
        capability_id=capability_id,
        assessment_config=resolve_installed_comparison_finding_assessment_config(
            capability_id
        ),
        consolidation_config=resolve_installed_comparison_finding_consolidation_config(
            capability_id
        ),
        assessment_provider=assessment_provider,
        assessment_second_pass_provider=assessment_second_pass_provider,
        verification_provider=verification_provider,
        consolidation_provider=consolidation_provider,
        max_concurrency=1,
    )


class _EmptyConsolidationProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        self.calls.append(messages)
        return LLMRawResult(
            provider_name="consolidation-stage-mock",
            model="consolidation-stage-mock",
            raw_text=json.dumps({"consolidated_groups": []}),
        )


def _focus_jobs_only(**kwargs):
    return tuple(
        job
        for job in plan_comparison_finding_assessment_jobs(**kwargs)
        if job.comparison_mode_id == "focus_comparison"
    )[:2]


def _single_focus_job_only(**kwargs):
    return _focus_jobs_only(**kwargs)[:1]


class _FocusPipelineProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        user_content = messages[-1]["content"]
        if "## Findings" in user_content:
            finding_ids = _extract_verification_finding_ids(user_content)
            payload = {
                "finding_verifications": [
                    {
                        "finding_id": finding_id,
                        "verification_result": "confirmed",
                    }
                    for finding_id in finding_ids
                ],
                "additional_findings": [],
            }
        else:
            aliases = tuple(dict.fromkeys(re.findall(r"\[(T\d{4})\]", user_content)))
            payload = {
                "candidates": [
                    {
                        "candidate_focus": "candidate spanning both focus sides",
                        "label": "fail",
                        "trigger_sentence_aliases": list(aliases),
                    }
                ]
            }
        return LLMRawResult(
            provider_name="focus-stage-mock",
            model="focus-stage-mock",
            raw_text=json.dumps(payload),
        )


class _ConsolidationResultProvider:
    def __init__(self, outcome: str = "success") -> None:
        self.outcome = outcome

    def generate(self, _messages: list[dict[str, str]]) -> LLMRawResult:
        if self.outcome == "provider_failure":
            raise RuntimeError("forced consolidation provider failure")
        if self.outcome == "parse_failure":
            raw_text = "not-json"
        elif self.outcome == "validation_failure":
            raw_text = json.dumps(
                {
                    "consolidated_groups": [
                        {
                            "conclusion_aliases": ["C001"],
                            "unified_conclusion": "invalid singleton",
                            "combined_sentence_aliases": ["T0001"],
                        }
                    ]
                }
            )
        else:
            raw_text = json.dumps(
                {
                    "consolidated_groups": [
                        {
                            "conclusion_aliases": ["C001", "C002"],
                            "unified_conclusion": "unified conclusion",
                            "combined_sentence_aliases": ["T9999"],
                        }
                    ]
                }
            )
        return LLMRawResult(
            provider_name="consolidation-stage-mock",
            model="consolidation-stage-mock",
            raw_text=raw_text,
        )


def _stage_input(
    tmp_path: Path,
    provider,
    *participants: EvidenceComparisonParticipantReference,
    capability_id: str = "internal_dsur",
) -> EvidenceComparisonStageInput:
    return EvidenceComparisonStageInput(
        participants=tuple(participants),
        context=EvidenceComparisonStageContext(
            output_dir=tmp_path / "evidence_comparison" / "stage_run",
            run_id="20260908_stage_test",
        ),
        execution_dependencies=_execution_dependencies(
            capability_id=capability_id,
            assessment_provider=provider,
        ),
    )


def _first_alias(messages: list[dict[str, str]]) -> str:
    match = re.search(r"\[(T\d{4})\]", messages[-1]["content"])
    if match is None:
        raise AssertionError("expected sentence alias in prompt")
    return match.group(1)


def _extract_verification_finding_ids(user_content: str) -> list[str]:
    marker = "## Findings\n"
    marker_index = user_content.find(marker)
    if marker_index == -1:
        return []
    findings_section = user_content[marker_index + len(marker) :]
    finding_ids: list[str] = []
    for line in findings_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("L") and len(stripped) == 4 and stripped[1:].isdigit():
            finding_ids.append(stripped)
    return finding_ids


class _FullPipelineProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        user_content = messages[-1]["content"]
        if "## Findings" in user_content:
            finding_ids = _extract_verification_finding_ids(user_content)
            return LLMRawResult(
                provider_name="stage-mock",
                model="stage-mock",
                raw_text=json.dumps(
                    {
                        "finding_verifications": [
                            {
                                "finding_id": finding_id,
                                "verification_result": "confirmed",
                            }
                            for finding_id in finding_ids
                        ],
                        "additional_findings": [],
                    }
                ),
            )
        alias = _first_alias(messages)
        return LLMRawResult(
            provider_name="stage-mock",
            model="stage-mock",
            raw_text=json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_focus": f"candidate for {alias}",
                            "label": "fail",
                            "trigger_sentence_aliases": [alias],
                        }
                    ]
                }
            ),
        )


class _FailingProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        raise RuntimeError("provider unavailable")


class _EmptyAssessmentProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        return LLMRawResult(
            provider_name="stage-empty-mock",
            model="stage-empty-mock",
            raw_text=json.dumps({"candidates": []}),
        )


class _AssessmentPartialProvider:
    def __init__(self) -> None:
        self._assessment_calls = 0

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        user_content = messages[-1]["content"]
        if "## Findings" in user_content:
            finding_ids = _extract_verification_finding_ids(user_content)
            return LLMRawResult(
                provider_name="stage-mock",
                model="stage-mock",
                raw_text=json.dumps(
                    {
                        "finding_verifications": [
                            {
                                "finding_id": finding_id,
                                "verification_result": "confirmed",
                            }
                            for finding_id in finding_ids
                        ],
                        "additional_findings": [],
                    }
                ),
            )
        self._assessment_calls += 1
        if self._assessment_calls == 2:
            raise RuntimeError("second assessment job failed")
        alias = _first_alias(messages)
        return LLMRawResult(
            provider_name="stage-mock",
            model="stage-mock",
            raw_text=json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_focus": f"candidate for {alias}",
                            "label": "fail",
                            "trigger_sentence_aliases": [alias],
                        }
                    ]
                }
            ),
        )


class _VerificationPartialProvider:
    def __init__(self) -> None:
        self._verification_calls = 0

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        user_content = messages[-1]["content"]
        if "## Findings" in user_content:
            self._verification_calls += 1
            if self._verification_calls == 2:
                raise RuntimeError("second verification job failed")
            finding_ids = _extract_verification_finding_ids(user_content)
            return LLMRawResult(
                provider_name="stage-mock",
                model="stage-mock",
                raw_text=json.dumps(
                    {
                        "finding_verifications": [
                            {
                                "finding_id": finding_id,
                                "verification_result": "confirmed",
                            }
                            for finding_id in finding_ids
                        ],
                        "additional_findings": [],
                    }
                ),
            )
        alias = _first_alias(messages)
        return LLMRawResult(
            provider_name="stage-mock",
            model="stage-mock",
            raw_text=json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_focus": f"candidate for {alias}",
                            "label": "fail",
                            "trigger_sentence_aliases": [alias],
                        }
                    ]
                }
            ),
        )


def test_build_invocation_rejects_invalid_participant_bundle(
    tmp_path: Path,
) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{not-json", encoding="utf-8")
    stage_input = EvidenceComparisonStageInput(
        participants=(
            _participant(role_id="source", slot_id="source", path=invalid_path),
        ),
        context=EvidenceComparisonStageContext(output_dir=tmp_path / "comparison"),
        execution_dependencies=EvidenceComparisonExecutionDependencies(),
    )

    with pytest.raises(json.JSONDecodeError):
        build_aggregate_evidence_comparison_invocation_from_stage_input(
            stage_input=stage_input,
        )


def test_stage_executor_rejects_wrong_execution_dependencies(
    tmp_path: Path,
) -> None:
    stage_input = EvidenceComparisonStageInput(
        participants=(
            _participant(
                role_id="source",
                slot_id="source",
                path=tmp_path / "unused.json",
            ),
        ),
        context=EvidenceComparisonStageContext(
            output_dir=tmp_path / "evidence_comparison" / "stage_run",
        ),
        execution_dependencies=EvidenceComparisonExecutionDependencies(),
    )

    with pytest.raises(
        TypeError, match="ClinicalTrialAggregateEvidenceComparisonExecutionDependencies"
    ):
        execute_clinical_trial_aggregate_evidence_comparison_stage(
            stage_input=stage_input,
            evidence_comparison_executor=CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR,
        )


def test_canonical_stage_success_persists_and_declares_final_findings(
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="internal_dsur",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    stage_input = _stage_input(
        tmp_path,
        _FullPipelineProvider(),
        _participant(
            role_id="source",
            slot_id="source",
            path=source_bundle,
        ),
    )
    captured_execution = {}

    def recording_executor(*, invocation):
        execution = CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR(
            invocation=invocation
        )
        captured_execution["result"] = execution
        return execution

    stage_executor = build_clinical_trial_aggregate_evidence_comparison_stage_executor(
        evidence_comparison_executor=recording_executor,
    )

    persisted = {}

    def recording_persist(**kwargs):
        persist_result = persist_unified_aggregate_evidence_comparison_execution(
            **kwargs
        )
        persisted["result"] = persist_result
        return persist_result

    with patch(
        "runtime.evidence_comparison.clinical_trial_doc.clinical_safety."
        "aggregate_evidence.stage."
        "persist_unified_aggregate_evidence_comparison_execution",
        side_effect=recording_persist,
    ):
        result = stage_executor(stage_input=stage_input)

    assert result.stage_executor_id == (
        CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_STAGE_EXECUTOR_ID
    )
    assert result.run_status == "success"
    assert result.run_id == "20260908_stage_test"
    assert result.declared_output_path == result.output_dir / FINAL_FINDINGS_FILENAME
    assert result.declared_output_path.is_file()

    run_summary = load_json(result.run_summary_path)
    assert run_summary["run_status"] == "success"
    assert run_summary["stats"]["planned_job_count"] >= 1
    assert run_summary["stats"]["assessment_success_count"] >= 1
    assert run_summary["stats"]["verification_success_count"] >= 1
    assert run_summary["stats"]["job_final_finding_count"] >= 1
    assert run_summary["stats"]["final_finding_count"] == (
        captured_execution["result"].final_finding_count
    )
    assert run_summary["outputs"]["job_final_findings"] == FINDINGS_FILENAME
    assert run_summary["outputs"]["final_findings"] == FINAL_FINDINGS_FILENAME
    assert "findings" not in run_summary["outputs"]
    assert run_summary["finalization"] == {
        "status": captured_execution["result"].final_findings[
            "finalization_status"
        ],
        "fallback_comparison_modes": captured_execution["result"].final_findings[
            "fallback_comparison_modes"
        ],
    }
    assert run_summary["finalization"]["status"] == "completed"
    verification_job_count = 0
    for job_summary in run_summary["jobs"]:
        job_root = Path(job_summary["assessment"]["job_dir"])
        assert len(job_summary["assessment"]["llm_invocations"]) == 1
        assert job_summary["assessment"]["llm_invocations"][0]["status"] == (
            "success"
        )
        assert job_summary["assessment"]["llm_invocations"][0][
            "attempt_index"
        ] == 1
        assert (job_root / "assessment" / "result.txt").is_file()
        if job_summary["assessment_second_pass"] is None:
            verification_job_count += 1
            assert job_summary["verification"] is not None
            assert "adopted_finding_count" in job_summary["verification"]
            assert "final_finding_count" not in job_summary["verification"]
            assert len(job_summary["verification"]["llm_invocations"]) == 1
            assert job_summary["verification"]["llm_invocations"][0][
                "status"
            ] == "success"
            assert not (job_root / "assessment" / "second_pass").exists()
            assert (job_root / "verification" / "result.txt").is_file()
        else:
            assert job_summary["verification"] is None
            assert len(job_summary["assessment_second_pass"]["llm_invocations"]) == 1
            assert job_summary["assessment_second_pass"]["llm_invocations"][0][
                "attempt_index"
            ] == 1
            assert (job_root / "assessment" / "second_pass" / "result.txt").is_file()
    assert verification_job_count >= 1

    aggregate_payload = load_json(
        result.output_dir / AGGREGATE_COMPARISON_EVIDENCE_FILENAME
    )
    validate_aggregate_comparison_evidence(aggregate_payload)
    findings_payload = load_json(result.output_dir / FINDINGS_FILENAME)
    validate_findings(findings_payload)
    assert findings_payload == captured_execution["result"].job_final_findings
    final_findings_path = result.declared_output_path
    final_findings_payload = load_json(final_findings_path)
    validate_final_findings(final_findings_payload)
    assert final_findings_payload == captured_execution["result"].final_findings
    persist_result = persisted["result"]
    assert persist_result.job_final_findings_path == result.output_dir / FINDINGS_FILENAME
    assert persist_result.final_findings_path == final_findings_path
    assert persist_result.final_findings_path.is_file()
    assert findings_payload["schema_version"] == FINDINGS_SCHEMA_VERSION == "0.2.0"
    assert {
        finding["label"]
        for job in findings_payload["jobs"]
        for finding in job["findings"]
    } <= {"fail", "need_review"}
    assert load_json(result.output_dir / COMPARISON_FINDING_ASSESSMENT_JOBS_FILENAME)
    assert (result.output_dir / "jobs").is_dir()


def test_canonical_stage_assessment_partial_failure(
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="assessment_partial",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    stage_input = _stage_input(
        tmp_path,
        _AssessmentPartialProvider(),
        _participant(
            role_id="source",
            slot_id="source",
            path=source_bundle,
        ),
    )
    result = execute_clinical_trial_aggregate_evidence_comparison_stage(
        stage_input=stage_input,
        evidence_comparison_executor=CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR,
    )

    assert result.run_status == "partial_failure"
    assert result.declared_output_path is not None
    validate_final_findings(load_json(result.declared_output_path))

    run_summary = load_json(result.run_summary_path)
    assert run_summary["run_status"] == "partial_failure"
    assert run_summary["stats"]["assessment_failed_count"] >= 1
    assert run_summary["stats"]["job_final_finding_count"] >= 1


def test_canonical_stage_persists_empty_second_pass_and_job_final_findings(
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="second_pass_empty",
        document_type="dsur",
        heading_paths=(("Safety findings",),),
    )
    provider = _EmptyAssessmentProvider()
    stage_input = EvidenceComparisonStageInput(
        participants=(
            _participant(
                role_id="source",
                slot_id="source",
                path=source_bundle,
            ),
        ),
        context=EvidenceComparisonStageContext(
            output_dir=tmp_path / "evidence_comparison" / "second_pass_empty_run",
            run_id="20260908_second_pass_empty",
        ),
        execution_dependencies=_execution_dependencies(
            assessment_provider=provider,
            assessment_second_pass_provider=provider,
            verification_provider=_FailingProvider(),
        ),
    )

    result = execute_clinical_trial_aggregate_evidence_comparison_stage(
        stage_input=stage_input,
        evidence_comparison_executor=CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR,
    )

    assert result.run_status == "success"
    findings = load_json(result.output_dir / FINDINGS_FILENAME)
    validate_findings(findings)
    assert findings["schema_version"] == FINDINGS_SCHEMA_VERSION == "0.2.0"
    assert all(job["findings"] == [] for job in findings["jobs"])
    run_summary = load_json(result.run_summary_path)
    assert run_summary["stats"]["assessment_second_pass_success_count"] >= 1
    assert run_summary["stats"]["verification_success_count"] == 0
    for job_summary in run_summary["jobs"]:
        assert job_summary["assessment_second_pass"] is not None
        assert job_summary["verification"] is None
        job_root = Path(job_summary["assessment"]["job_dir"])
        assert (job_root / "assessment" / "result.txt").is_file()
        assert (job_root / "assessment" / "validated_response.json").is_file()
        assert (job_root / "assessment" / "second_pass" / "result.txt").is_file()
        assert (
            job_root / "assessment" / "second_pass" / "validated_response.json"
        ).is_file()
        assert not (job_root / "verification").exists()


def test_canonical_stage_persists_non_empty_second_pass_with_current_contract(
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="second_pass_non_empty",
        document_type="dsur",
        heading_paths=(("Safety findings",),),
    )
    stage_input = EvidenceComparisonStageInput(
        participants=(
            _participant(
                role_id="source",
                slot_id="source",
                path=source_bundle,
            ),
        ),
        context=EvidenceComparisonStageContext(
            output_dir=tmp_path / "evidence_comparison" / "second_pass_non_empty_run",
            run_id="20260908_second_pass_non_empty",
        ),
        execution_dependencies=_execution_dependencies(
            assessment_provider=_EmptyAssessmentProvider(),
            assessment_second_pass_provider=_FullPipelineProvider(),
            verification_provider=_FailingProvider(),
        ),
    )

    result = execute_clinical_trial_aggregate_evidence_comparison_stage(
        stage_input=stage_input,
        evidence_comparison_executor=CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR,
    )

    assert result.run_status == "success"
    findings = load_json(result.output_dir / FINDINGS_FILENAME)
    validate_findings(findings)
    assert findings["schema_version"] == FINDINGS_SCHEMA_VERSION == "0.2.0"
    active_findings = [
        finding for job in findings["jobs"] for finding in job["findings"]
    ]
    assert active_findings
    assert {finding["label"] for finding in active_findings} <= {
        "fail",
        "need_review",
    }
    run_summary = load_json(result.run_summary_path)
    assert run_summary["stats"]["verification_success_count"] == 0
    assert all(job["verification"] is None for job in run_summary["jobs"])


def test_canonical_stage_verification_partial_failure(
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="verification_partial",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    stage_input = _stage_input(
        tmp_path,
        _VerificationPartialProvider(),
        _participant(
            role_id="source",
            slot_id="source",
            path=source_bundle,
        ),
    )
    result = execute_clinical_trial_aggregate_evidence_comparison_stage(
        stage_input=stage_input,
        evidence_comparison_executor=CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR,
    )

    assert result.run_status == "partial_failure"
    assert result.declared_output_path is not None
    validate_final_findings(load_json(result.declared_output_path))

    run_summary = load_json(result.run_summary_path)
    assert run_summary["run_status"] == "partial_failure"
    assert run_summary["stats"]["verification_failed_count"] >= 1
    assert run_summary["stats"]["job_final_finding_count"] >= 1


def test_canonical_stage_all_failed_declares_empty_final_product(
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="all_failed",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    stage_input = _stage_input(
        tmp_path,
        _FailingProvider(),
        _participant(
            role_id="source",
            slot_id="source",
            path=source_bundle,
        ),
    )
    result = execute_clinical_trial_aggregate_evidence_comparison_stage(
        stage_input=stage_input,
        evidence_comparison_executor=CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR,
    )

    assert result.run_status == "failed"
    assert result.declared_output_path == result.output_dir / FINAL_FINDINGS_FILENAME
    assert not (result.output_dir / FINDINGS_FILENAME).exists()
    final_findings_path = result.declared_output_path
    final_findings = load_json(final_findings_path)
    validate_final_findings(final_findings)
    assert final_findings["findings"] == []

    run_summary = load_json(result.run_summary_path)
    assert run_summary["run_status"] == "failed"
    assert run_summary["outputs"]["job_final_findings"] is None
    assert run_summary["outputs"]["final_findings"] == FINAL_FINDINGS_FILENAME
    assert run_summary["stats"]["assessment_success_count"] == 0
    assert run_summary["stats"]["job_final_finding_count"] == 0
    assert run_summary["stats"]["final_finding_count"] == 0
    assert run_summary["finalization"] == {
        "status": "completed",
        "fallback_comparison_modes": [],
    }
    assert run_summary["stats"]["planned_job_count"] >= 1


def test_stage_validates_final_findings_before_writing(
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="invalid_product_final",
        document_type="dsur",
        heading_paths=(("Safety findings",),),
    )
    stage_input = _stage_input(
        tmp_path,
        _FullPipelineProvider(),
        _participant(
            role_id="source",
            slot_id="source",
            path=source_bundle,
        ),
    )

    def invalid_final_findings_executor(*, invocation):
        execution = CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR(
            invocation=invocation
        )
        return replace(
            execution,
            final_findings={
                "artifact_type": "final_findings",
                "schema_version": "0.1.0",
            },
        )

    with pytest.raises(ValueError, match="root keys mismatch"):
        execute_clinical_trial_aggregate_evidence_comparison_stage(
            stage_input=stage_input,
            evidence_comparison_executor=invalid_final_findings_executor,
        )

    assert not (
        stage_input.context.output_dir.resolve() / FINAL_FINDINGS_FILENAME
    ).exists()


def test_canonical_stage_persists_failed_job_summaries(
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="failed_job_summaries",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    stage_input = _stage_input(
        tmp_path,
        _AssessmentPartialProvider(),
        _participant(
            role_id="source",
            slot_id="source",
            path=source_bundle,
        ),
    )
    result = execute_clinical_trial_aggregate_evidence_comparison_stage(
        stage_input=stage_input,
        evidence_comparison_executor=CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR,
    )

    run_summary = load_json(result.run_summary_path)
    failed_assessment_jobs = [
        job for job in run_summary["jobs"] if job["assessment"]["status"] != "success"
    ]
    assert failed_assessment_jobs
    assert any(job["assessment"].get("error_message") for job in failed_assessment_jobs)
    failed_invocation = failed_assessment_jobs[0]["assessment"]["llm_invocations"][0]
    assert failed_invocation["status"] == "failed"
    assert failed_invocation["error_type"] == "RuntimeError"
    assert isinstance(failed_invocation["elapsed_ms"], int)


def test_plugin_execution_does_not_import_runtime_persistence() -> None:
    forbidden_prefixes = ("runtime", "scripts.stage_runners", "application")
    new_files = (
        _PLUGIN_ROOT / "execution.py",
        _PLUGIN_ROOT / "execution_types.py",
        _PLUGIN_ROOT / "executor.py",
        _PLUGIN_ROOT / "comparison_finding_assessment" / "execution.py",
        _PLUGIN_ROOT / "comparison_finding_verification" / "execution.py",
    )
    persistence_module = (
        "runtime.evidence_comparison.clinical_trial_doc.clinical_safety."
        "aggregate_evidence.persistence"
    )
    violations: list[str] = []
    for path in new_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for imported in modules:
                if imported == persistence_module or imported.endswith(".persistence"):
                    violations.append(f"{path.name} imports {imported}")
                if any(
                    imported == prefix or imported.startswith(prefix + ".")
                    for prefix in forbidden_prefixes
                ):
                    violations.append(f"{path.name} imports {imported}")
    assert not violations, "\n".join(violations)


def test_stage_persistence_module_does_not_implement_alias_generation() -> None:
    forbidden_tokens = (
        "scope_counter",
        "unit_counter",
        "sentence_counter",
        '"scope_alias"',
        '"unit_alias"',
        '"sentence_alias"',
    )
    persistence_path = _RUNTIME_AGGREGATE_ROOT / "persistence.py"
    source = persistence_path.read_text(encoding="utf-8")
    violations = [token for token in forbidden_tokens if token in source]
    assert not violations, "\n".join(violations)


def test_stage_persistence_does_not_import_standalone_dev_plan_runtime() -> None:
    persistence_path = _RUNTIME_AGGREGATE_ROOT / "persistence.py"
    source = persistence_path.read_text(encoding="utf-8")
    assert "comparison_finding_assessment_plan" not in source


def test_stage_run_summary_filename_contract() -> None:
    assert RUN_SUMMARY_FILENAME == "run_summary.json"


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=_focus_jobs_only,
)
def test_stage_persists_consolidation_runtime_diagnostics(
    _mock_plan,
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="consolidation_persistence",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    stage_input = EvidenceComparisonStageInput(
        participants=(
            _participant(role_id="source", slot_id="source", path=source_bundle),
        ),
        context=EvidenceComparisonStageContext(
            output_dir=tmp_path / "evidence_comparison" / "consolidation_run",
            run_id="20261003_consolidation_persistence",
        ),
        execution_dependencies=_execution_dependencies(
            assessment_provider=_FocusPipelineProvider(),
            verification_provider=_FocusPipelineProvider(),
            consolidation_provider=_ConsolidationResultProvider(),
        ),
    )

    result = execute_clinical_trial_aggregate_evidence_comparison_stage(
        stage_input=stage_input,
        evidence_comparison_executor=(
            CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR
        ),
    )

    mode_dir = (
        result.output_dir
        / COMPARISON_FINDING_CONSOLIDATION_DIRNAME
        / "focus_comparison"
    )
    assert {path.name for path in mode_dir.iterdir()} == {
        "consolidation_input.txt",
        "prompt.txt",
        "result.txt",
        "validated_response.json",
        "alias_mapping.json",
        "alias_qc.json",
    }
    assert (mode_dir / "prompt.txt").read_text(encoding="utf-8") != (
        mode_dir / "consolidation_input.txt"
    ).read_text(encoding="utf-8")
    summary = load_json(result.run_summary_path)
    assert result.declared_output_path == result.output_dir / FINAL_FINDINGS_FILENAME
    assert summary["outputs"]["consolidation_dir"] == (
        COMPARISON_FINDING_CONSOLIDATION_DIRNAME
    )
    assert summary["stats"]["consolidation_execution_count"] == 1
    assert summary["stats"]["consolidation_success_count"] == 1
    assert summary["stats"]["consolidation_alias_qc_mismatch_count"] == 1
    assert summary["stats"]["job_final_finding_count"] > (
        summary["stats"]["final_finding_count"]
    )
    assert summary["outputs"]["final_findings"] == FINAL_FINDINGS_FILENAME
    assert summary["finalization"] == {
        "status": "completed",
        "fallback_comparison_modes": [],
    }
    validate_final_findings(
        load_json(result.output_dir / FINAL_FINDINGS_FILENAME)
    )
    assert summary["consolidation"][0]["status"] == "success"
    assert summary["consolidation"][0]["alias_qc_all_groups_match"] is False
    assert summary["consolidation"][0]["llm_invocations"][0]["provider"] == (
        "consolidation-stage-mock"
    )
    assert summary["consolidation"][0]["llm_invocations"][0]["model"] == (
        "consolidation-stage-mock"
    )


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=_focus_jobs_only,
)
def test_stage_preserves_pre_final_artifacts_and_reraises_finalization_failure(
    _mock_plan,
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="fatal_finalization_persistence",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    output_dir = tmp_path / "evidence_comparison" / "fatal_finalization"
    output_dir.mkdir(parents=True)
    stale_final_findings = output_dir / FINAL_FINDINGS_FILENAME
    stale_final_findings.write_text('{"stale": true}', encoding="utf-8")
    stage_input = EvidenceComparisonStageInput(
        participants=(
            _participant(role_id="source", slot_id="source", path=source_bundle),
        ),
        context=EvidenceComparisonStageContext(
            output_dir=output_dir,
            run_id="20261003_fatal_finalization",
        ),
        execution_dependencies=_execution_dependencies(
            assessment_provider=_FocusPipelineProvider(),
            verification_provider=_FocusPipelineProvider(),
            consolidation_provider=_ConsolidationResultProvider(),
        ),
    )
    finalization_error = AggregateEvidenceComparisonFinalizationError(
        "forced deterministic finalization failure"
    )

    with patch(
        "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
        "aggregate_evidence.execution.finalize_aggregate_evidence_comparison",
        side_effect=finalization_error,
    ), pytest.raises(
        AggregateEvidenceComparisonFinalizationFailure,
        match="forced deterministic finalization failure",
    ) as exc_info:
        execute_clinical_trial_aggregate_evidence_comparison_stage(
            stage_input=stage_input,
            evidence_comparison_executor=(
                CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR
            ),
        )

    failure = exc_info.value
    assert failure.finalization_error is finalization_error
    assert failure.__cause__ is finalization_error
    assert failure.pre_final_state.job_final_findings is not None
    assert (output_dir / FINDINGS_FILENAME).is_file()
    assert not stale_final_findings.exists()

    mode_dir = (
        output_dir
        / COMPARISON_FINDING_CONSOLIDATION_DIRNAME
        / "focus_comparison"
    )
    assert {path.name for path in mode_dir.iterdir()} == {
        "consolidation_input.txt",
        "prompt.txt",
        "result.txt",
        "validated_response.json",
        "alias_mapping.json",
        "alias_qc.json",
    }

    summary = load_json(output_dir / RUN_SUMMARY_FILENAME)
    assert summary["run_status"] == "failed"
    assert summary["failure_reason"] == "execution_exception"
    assert summary["failure_message"] == str(finalization_error)
    assert summary["outputs"]["job_final_findings"] == FINDINGS_FILENAME
    assert summary["outputs"]["final_findings"] is None
    assert summary["stats"]["job_final_finding_count"] >= 1
    assert "final_finding_count" not in summary["stats"]
    assert summary["consolidation"][0]["status"] == "success"
    assert "finalization" not in summary

    for job_summary in summary["jobs"]:
        job_root = Path(job_summary["assessment"]["job_dir"])
        assert (job_root / "assessment" / "result.txt").is_file()
        verification = job_summary["verification"]
        if verification is not None:
            assert (job_root / "verification" / "result.txt").is_file()


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=_single_focus_job_only,
)
def test_fatal_persistence_preserves_completed_second_pass_artifacts(
    _mock_plan,
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="fatal_second_pass_persistence",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    stage_input = EvidenceComparisonStageInput(
        participants=(
            _participant(role_id="source", slot_id="source", path=source_bundle),
        ),
        context=EvidenceComparisonStageContext(
            output_dir=tmp_path / "evidence_comparison" / "fatal_second_pass",
            run_id="20261003_fatal_second_pass",
        ),
        execution_dependencies=_execution_dependencies(
            assessment_provider=_EmptyAssessmentProvider(),
            assessment_second_pass_provider=_FocusPipelineProvider(),
            verification_provider=_FailingProvider(),
            consolidation_provider=_EmptyConsolidationProvider(),
        ),
    )

    with patch(
        "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
        "aggregate_evidence.execution.finalize_aggregate_evidence_comparison",
        side_effect=AggregateEvidenceComparisonFinalizationError(
            "forced deterministic finalization failure"
        ),
    ), pytest.raises(AggregateEvidenceComparisonFinalizationFailure):
        execute_clinical_trial_aggregate_evidence_comparison_stage(
            stage_input=stage_input,
            evidence_comparison_executor=(
                CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR
            ),
        )

    summary = load_json(stage_input.context.output_dir / RUN_SUMMARY_FILENAME)
    job_summary = summary["jobs"][0]
    assert job_summary["assessment_second_pass"] is not None
    job_root = Path(job_summary["assessment"]["job_dir"])
    assert (job_root / "assessment" / "second_pass" / "result.txt").is_file()
    assert (
        job_root / "assessment" / "second_pass" / "validated_response.json"
    ).is_file()


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=_focus_jobs_only,
)
def test_fatal_persistence_reuses_consolidation_stale_cleanup(
    _mock_plan,
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="fatal_consolidation_cleanup",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    output_dir = tmp_path / "evidence_comparison" / "fatal_cleanup"
    mode_dir = (
        output_dir
        / COMPARISON_FINDING_CONSOLIDATION_DIRNAME
        / "focus_comparison"
    )
    mode_dir.mkdir(parents=True)
    for file_name in ("result.txt", "validated_response.json", "alias_qc.json"):
        (mode_dir / file_name).write_text("stale", encoding="utf-8")
    stage_input = EvidenceComparisonStageInput(
        participants=(
            _participant(role_id="source", slot_id="source", path=source_bundle),
        ),
        context=EvidenceComparisonStageContext(
            output_dir=output_dir,
            run_id="20261003_fatal_cleanup",
        ),
        execution_dependencies=_execution_dependencies(
            assessment_provider=_FocusPipelineProvider(),
            verification_provider=_FocusPipelineProvider(),
            consolidation_provider=_ConsolidationResultProvider(
                "provider_failure"
            ),
        ),
    )

    with patch(
        "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
        "aggregate_evidence.execution.finalize_aggregate_evidence_comparison",
        side_effect=AggregateEvidenceComparisonFinalizationError(
            "forced deterministic finalization failure"
        ),
    ), pytest.raises(AggregateEvidenceComparisonFinalizationFailure):
        execute_clinical_trial_aggregate_evidence_comparison_stage(
            stage_input=stage_input,
            evidence_comparison_executor=(
                CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR
            ),
        )

    assert {path.name for path in mode_dir.iterdir()} == {
        "consolidation_input.txt",
        "prompt.txt",
        "alias_mapping.json",
    }
    summary = load_json(output_dir / RUN_SUMMARY_FILENAME)
    assert summary["consolidation"][0]["status"] == "failed"
    assert summary["consolidation"][0]["parse_status"] == "not_attempted"
    assert summary["consolidation"][0]["validation_status"] == "not_attempted"


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=_single_focus_job_only,
)
def test_stage_persists_consolidation_noop_without_provider_result_artifact(
    _mock_plan,
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="consolidation_noop_persistence",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    consolidation_provider = _EmptyConsolidationProvider()
    stage_input = EvidenceComparisonStageInput(
        participants=(
            _participant(role_id="source", slot_id="source", path=source_bundle),
        ),
        context=EvidenceComparisonStageContext(
            output_dir=tmp_path / "evidence_comparison" / "consolidation_noop_run",
            run_id="20261003_consolidation_noop_persistence",
        ),
        execution_dependencies=_execution_dependencies(
            assessment_provider=_FocusPipelineProvider(),
            verification_provider=_FocusPipelineProvider(),
            consolidation_provider=consolidation_provider,
        ),
    )

    result = execute_clinical_trial_aggregate_evidence_comparison_stage(
        stage_input=stage_input,
        evidence_comparison_executor=(
            CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR
        ),
    )

    mode_dir = (
        result.output_dir
        / COMPARISON_FINDING_CONSOLIDATION_DIRNAME
        / "focus_comparison"
    )
    assert {path.name for path in mode_dir.iterdir()} == {
        "consolidation_input.txt",
        "prompt.txt",
        "alias_mapping.json",
        "validated_response.json",
        "alias_qc.json",
    }
    assert not (mode_dir / "result.txt").exists()
    assert consolidation_provider.calls == []

    summary = load_json(result.run_summary_path)
    phase = summary["consolidation"][0]
    assert phase["status"] == "success"
    assert phase["provider_called"] is False
    assert phase["finding_count"] == 1
    assert phase["parse_status"] == "not_attempted"
    assert phase["validation_status"] == "not_attempted"


@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=_focus_jobs_only,
)
def test_stage_reused_output_dir_removes_stale_consolidation_artifacts(
    _mock_plan,
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="consolidation_reused_output",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    output_dir = tmp_path / "evidence_comparison" / "reused_consolidation_run"

    def _run(consolidation_provider):
        stage_input = EvidenceComparisonStageInput(
            participants=(
                _participant(
                    role_id="source",
                    slot_id="source",
                    path=source_bundle,
                ),
            ),
            context=EvidenceComparisonStageContext(
                output_dir=output_dir,
                run_id="20261003_reused_consolidation",
            ),
            execution_dependencies=_execution_dependencies(
                assessment_provider=_FocusPipelineProvider(),
                verification_provider=_FocusPipelineProvider(),
                consolidation_provider=consolidation_provider,
            ),
        )
        return execute_clinical_trial_aggregate_evidence_comparison_stage(
            stage_input=stage_input,
            evidence_comparison_executor=(
                CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR
            ),
        )

    successful = _run(_ConsolidationResultProvider())
    mode_dir = (
        successful.output_dir
        / COMPARISON_FINDING_CONSOLIDATION_DIRNAME
        / "focus_comparison"
    )
    assert (mode_dir / "result.txt").is_file()
    assert (mode_dir / "validated_response.json").is_file()
    assert (mode_dir / "alias_qc.json").is_file()

    failed = _run(_ConsolidationResultProvider("provider_failure"))

    assert failed.run_status == "partial_failure"
    assert not (mode_dir / "result.txt").exists()
    assert not (mode_dir / "validated_response.json").exists()
    assert not (mode_dir / "alias_qc.json").exists()


@pytest.mark.parametrize(
    ("outcome", "parse_status", "validation_status", "has_result"),
    [
        ("provider_failure", "not_attempted", "not_attempted", False),
        ("parse_failure", "failed", "not_attempted", True),
        ("validation_failure", "success", "failed", True),
    ],
)
@patch(
    "plugins.clinical_trial_doc.evidence_comparison.clinical_safety."
    "aggregate_evidence.execution.plan_comparison_finding_assessment_jobs",
    side_effect=_focus_jobs_only,
)
def test_stage_freezes_consolidation_failures_in_runtime_summary(
    _mock_plan,
    tmp_path: Path,
    outcome: str,
    parse_status: str,
    validation_status: str,
    has_result: bool,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label=f"consolidation_{outcome}",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    stage_input = EvidenceComparisonStageInput(
        participants=(
            _participant(role_id="source", slot_id="source", path=source_bundle),
        ),
        context=EvidenceComparisonStageContext(
            output_dir=tmp_path / "evidence_comparison" / outcome,
            run_id=f"20261003_{outcome}",
        ),
        execution_dependencies=_execution_dependencies(
            assessment_provider=_FocusPipelineProvider(),
            verification_provider=_FocusPipelineProvider(),
            consolidation_provider=_ConsolidationResultProvider(outcome),
        ),
    )

    result = execute_clinical_trial_aggregate_evidence_comparison_stage(
        stage_input=stage_input,
        evidence_comparison_executor=(
            CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR
        ),
    )

    summary = load_json(result.run_summary_path)
    phase = summary["consolidation"][0]
    mode_dir = Path(phase["output_dir"])
    assert result.run_status == "partial_failure"
    assert result.declared_output_path == result.output_dir / FINAL_FINDINGS_FILENAME
    final_findings_path = result.output_dir / FINAL_FINDINGS_FILENAME
    final_findings = load_json(final_findings_path)
    validate_final_findings(final_findings)
    assert summary["outputs"]["final_findings"] == FINAL_FINDINGS_FILENAME
    assert summary["stats"]["final_finding_count"] == len(
        final_findings["findings"]
    )
    assert summary["finalization"] == {
        "status": "completed_with_fallback",
        "fallback_comparison_modes": ["focus_comparison"],
    }
    assert phase["status"] == "failed"
    assert phase["parse_status"] == parse_status
    assert phase["validation_status"] == validation_status
    assert phase["error_message"]
    assert (mode_dir / "result.txt").exists() is has_result
    assert not (mode_dir / "validated_response.json").exists()
    assert not (mode_dir / "alias_qc.json").exists()


def test_stage_run_summary_records_split_llm_execution_configs(
    tmp_path: Path,
) -> None:
    source_bundle = write_current_ec_source_fixture(
        tmp_path,
        label="llm_execution_configs",
        document_type="dsur",
        heading_paths=(("Safety findings",), ("Additional safety findings",)),
    )
    provider = _FullPipelineProvider()
    stage_input = EvidenceComparisonStageInput(
        participants=(
            _participant(
                role_id="source",
                slot_id="source",
                path=source_bundle,
            ),
        ),
        context=EvidenceComparisonStageContext(
            output_dir=tmp_path / "evidence_comparison" / "llm_metadata_run",
            run_id="20260908_stage_llm_metadata",
        ),
        execution_dependencies=ClinicalTrialAggregateEvidenceComparisonExecutionDependencies(
            capability_id="internal_dsur",
            assessment_config=resolve_installed_comparison_finding_assessment_config(
                "internal_dsur"
            ),
            assessment_provider=provider,
            assessment_second_pass_provider=provider,
                verification_provider=provider,
                consolidation_config=resolve_installed_comparison_finding_consolidation_config(
                    "internal_dsur"
                ),
                consolidation_provider=_EmptyConsolidationProvider(),
            assessment_llm_execution_config=resolve_llm_execution_config(
                CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID
            ).to_provenance_record(),
            assessment_second_pass_llm_execution_config=resolve_llm_execution_config(
                CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID
            ).to_provenance_record(),
                verification_llm_execution_config=resolve_llm_execution_config(
                    CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID
                ).to_provenance_record(),
                consolidation_llm_execution_config=resolve_llm_execution_config(
                    CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID
                ).to_provenance_record(),
        ),
    )
    result = execute_clinical_trial_aggregate_evidence_comparison_stage(
        stage_input=stage_input,
        evidence_comparison_executor=CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR,
    )

    run_summary = load_json(result.run_summary_path)
    assert run_summary["llm_execution"]["comparison_finding_assessment"] == (
        resolve_llm_execution_config(
            CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID
        ).to_provenance_record()
    )
    assert run_summary["llm_execution"]["comparison_finding_verification"] == (
        resolve_llm_execution_config(
            CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID
        ).to_provenance_record()
    )
    assert run_summary["llm_execution"]["comparison_finding_consolidation"] == (
        resolve_llm_execution_config(
            CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID
        ).to_provenance_record()
    )
    assert run_summary["llm_execution"][
        "comparison_finding_assessment_second_pass"
    ] == resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID
    ).to_provenance_record()

    assessment_job = next(
        job
        for job in run_summary["jobs"]
        if job["assessment"]["status"] == "success"
    )
    assert (
        run_summary["llm_execution"]["comparison_finding_assessment"]["response_format"]
        is None
    )
    assert assessment_job["assessment"]["response_format_applied"] is False
    primary_invocation = assessment_job["assessment"]["llm_invocations"][0]
    assert primary_invocation["config_id"] == (
        CLINICAL_TRIAL_DOC_EC_ASSESSMENT_LLM_EXECUTION_CONFIG_ID
    )
    assert primary_invocation["attempt_index"] == 1
    if assessment_job["assessment_second_pass"] is not None:
        assert (
            run_summary["llm_execution"][
                "comparison_finding_assessment_second_pass"
            ]["response_format"]
            is None
        )
        assert (
            assessment_job["assessment_second_pass"]["response_format_applied"] is False
        )
        second_pass_invocation = assessment_job["assessment_second_pass"][
            "llm_invocations"
        ][0]
        assert second_pass_invocation["config_id"] == (
            CLINICAL_TRIAL_DOC_EC_ASSESSMENT_SECOND_PASS_LLM_EXECUTION_CONFIG_ID
        )
        assert second_pass_invocation["attempt_index"] == 1
    if assessment_job["verification"] is not None:
        assert (
            run_summary["llm_execution"]["comparison_finding_verification"][
                "response_format"
            ]
            is None
        )
        assert assessment_job["verification"]["response_format_applied"] is False
        verification_invocation = assessment_job["verification"][
            "llm_invocations"
        ][0]
        assert verification_invocation["config_id"] == (
            CLINICAL_TRIAL_DOC_EC_VERIFICATION_LLM_EXECUTION_CONFIG_ID
        )
        assert verification_invocation["attempt_index"] == 1
