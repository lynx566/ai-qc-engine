"""Tests for Comparison Finding Verification in-memory execution core."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
    build_findings,
)
from llm.providers.base import LLMRawResult
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentGroup,
    ComparisonFindingAssessmentJob,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_verification import (
    execute_comparison_finding_verification_job,
    execute_comparison_finding_verification_jobs,
    materialize_comparison_finding_verification_input,
    materialize_comparison_finding_verification_inputs,
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
                                    }
                                ],
                            }
                        ],
                    }
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


def _findings_job(
    *,
    frozen_job_index: int,
    job: ComparisonFindingAssessmentJob,
    findings: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "frozen_job_index": frozen_job_index,
        "comparison_mode_id": job.comparison_mode_id,
        "comparison_groups": [
            {"group_role": group.group_role, "scope_aliases": list(group.scope_aliases)}
            for group in job.groups
        ],
        "findings": findings,
    }


class _VerificationProvider:
    def __init__(self, *, handler=None) -> None:
        self._handler = handler or self._default_handler

    def _default_handler(self, messages: list[dict[str, str]]) -> LLMRawResult:
        finding_ids = _extract_input_finding_ids(messages[-1]["content"])
        return LLMRawResult(
            provider_name="verification-mock",
            model="verification-mock",
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

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        return self._handler(messages)


def _extract_input_finding_ids(user_content: str) -> list[str]:
    marker = "## Findings\n"
    marker_index = user_content.find(marker)
    if marker_index == -1:
        return []
    findings_section = user_content[marker_index + len(marker) :]
    if not findings_section.strip():
        return []
    finding_ids: list[str] = []
    for line in findings_section.splitlines():
        stripped = line.strip()
        if stripped.startswith("L") and len(stripped) == 4 and stripped[1:].isdigit():
            finding_ids.append(stripped)
    return finding_ids


class _FailingProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        raise RuntimeError("provider unavailable")


def test_verification_confirmed_preservation() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    findings_job = _findings_job(
        frozen_job_index=1,
        job=job,
        findings=[
            {
                "finding_id": "L001",
                "conclusion": "Alpha check",
                "label": "fail",
                "source_sentence_aliases": ["T0001"],
            }
        ],
    )
    verification_input = materialize_comparison_finding_verification_input(
        job=job,
        aggregate_comparison_evidence=_evidence(),
        findings_job_envelope=findings_job,
        frozen_job_index=1,
    )
    execution = execute_comparison_finding_verification_job(
        verification_input=verification_input,
        frozen_job=job,
        aggregate_comparison_evidence=_evidence(),
        execution_index=1,
        provider=_VerificationProvider(),
    )
    assert execution.status == "success"
    assert execution.confirmed_finding_count == 1
    assert execution.job_reconciliation is not None


def test_verification_revised_replacement() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    findings_job = _findings_job(
        frozen_job_index=1,
        job=job,
        findings=[
            {
                "finding_id": "L001",
                "conclusion": "Alpha check",
                "label": "fail",
                "source_sentence_aliases": ["T0001"],
            }
        ],
    )
    verification_input = materialize_comparison_finding_verification_input(
        job=job,
        aggregate_comparison_evidence=_evidence(),
        findings_job_envelope=findings_job,
        frozen_job_index=1,
    )

    def handler(_messages: list[dict[str, str]]) -> LLMRawResult:
        return LLMRawResult(
            provider_name="verification-mock",
            model="verification-mock",
            raw_text=json.dumps(
                {
                        "finding_verifications": [
                            {
                                "finding_id": "L001",
                                "verification_result": "revised",
                                "conclusion": "Corrected",
                                "label": "fail",
                                "source_sentence_aliases": ["T0001"],
                            }
                        ],
                    "additional_findings": [],
                }
            ),
        )

    execution = execute_comparison_finding_verification_job(
        verification_input=verification_input,
        frozen_job=job,
        aggregate_comparison_evidence=_evidence(),
        execution_index=1,
        provider=_VerificationProvider(handler=handler),
    )
    assert execution.status == "success"
    assert execution.revised_finding_count == 1
    assert execution.job_reconciliation is not None
    assert execution.job_reconciliation.findings[0]["conclusion"] == "Corrected"


def test_verification_rejected_is_retained_in_validation_and_omitted_from_projection() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    findings_job = _findings_job(
        frozen_job_index=1,
        job=job,
        findings=[
            {
                "finding_id": "L001",
                "conclusion": "Alpha issue",
                "label": "fail",
                "source_sentence_aliases": ["T0001"],
            }
        ],
    )
    verification_input = materialize_comparison_finding_verification_input(
        job=job,
        aggregate_comparison_evidence=_evidence(),
        findings_job_envelope=findings_job,
        frozen_job_index=1,
    )

    def handler(_messages: list[dict[str, str]]) -> LLMRawResult:
        return LLMRawResult(
            provider_name="verification-mock",
            model="verification-mock",
            raw_text=json.dumps(
                {
                    "finding_verifications": [
                        {
                            "finding_id": "L001",
                            "verification_result": "rejected",
                        }
                    ]
                }
            ),
        )

    execution = execute_comparison_finding_verification_job(
        verification_input=verification_input,
        frozen_job=job,
        aggregate_comparison_evidence=_evidence(),
        execution_index=1,
        provider=_VerificationProvider(handler=handler),
    )

    assert execution.status == "success"
    assert execution.validated_response is not None
    assert execution.validated_response.finding_verifications[0].verification_result == "rejected"
    assert execution.job_reconciliation is not None
    assert execution.job_reconciliation.findings == ()
    assert execution.rejected_finding_count == 1


def test_verification_empty_findings_still_calls_provider() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    findings_job = _findings_job(frozen_job_index=1, job=job, findings=[])
    verification_input = materialize_comparison_finding_verification_input(
        job=job,
        aggregate_comparison_evidence=_evidence(),
        findings_job_envelope=findings_job,
        frozen_job_index=1,
    )
    provider = _VerificationProvider()
    execution = execute_comparison_finding_verification_job(
        verification_input=verification_input,
        frozen_job=job,
        aggregate_comparison_evidence=_evidence(),
        execution_index=1,
        provider=provider,
    )
    assert execution.status == "success"
    assert execution.input_finding_count == 0


def test_verification_provider_failure() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    findings_job = _findings_job(
        frozen_job_index=1,
        job=job,
        findings=[
            {
                "finding_id": "L001",
                "conclusion": "Alpha check",
                "label": "fail",
                "source_sentence_aliases": ["T0001"],
            }
        ],
    )
    verification_input = materialize_comparison_finding_verification_input(
        job=job,
        aggregate_comparison_evidence=_evidence(),
        findings_job_envelope=findings_job,
        frozen_job_index=1,
    )
    execution = execute_comparison_finding_verification_job(
        verification_input=verification_input,
        frozen_job=job,
        aggregate_comparison_evidence=_evidence(),
        execution_index=1,
        provider=_FailingProvider(),
    )
    assert execution.status == "failed"
    invocation = execution.llm_invocations[0]
    assert invocation.status == "failed"
    assert invocation.error_type == "RuntimeError"
    assert invocation.error_message == "provider unavailable"
    assert invocation.elapsed_ms >= 0


def test_verification_batch_partial_failure() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    assessment_findings = build_findings(
        jobs=[
            _findings_job(
                frozen_job_index=1,
                job=job,
                findings=[
                    {
                        "finding_id": "L001",
                        "conclusion": "Alpha check",
                        "label": "fail",
                        "source_sentence_aliases": ["T0001"],
                    }
                ],
            ),
            _findings_job(
                frozen_job_index=2,
                job=job,
                findings=[
                    {
                        "finding_id": "L002",
                        "conclusion": "Second",
                        "label": "fail",
                        "source_sentence_aliases": ["T0001"],
                    }
                ],
            ),
        ]
    )
    planned_jobs = (job, job)
    verification_inputs = materialize_comparison_finding_verification_inputs(
        planned_jobs=planned_jobs,
        aggregate_comparison_evidence=_evidence(),
        assessment_findings_artifact=assessment_findings,
        successful_frozen_job_indexes=frozenset({1, 2}),
    )
    call_count = {"value": 0}

    def handler(_messages: list[dict[str, str]]) -> LLMRawResult:
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise RuntimeError("second job failed")
        return _VerificationProvider().generate(_messages)

    batch = execute_comparison_finding_verification_jobs(
        verification_inputs=verification_inputs,
        planned_jobs_by_index={1: job, 2: job},
        aggregate_comparison_evidence=_evidence(),
        assessment_findings_artifact=assessment_findings,
        provider=_VerificationProvider(handler=handler),
        max_concurrency=1,
    )
    assert batch.run_status == "partial_failure"
    assert batch.success_count == 1
    assert batch.findings_artifact is not None


def test_verification_job_execution_has_no_path_fields() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    findings_job = _findings_job(
        frozen_job_index=1,
        job=job,
        findings=[
            {
                "finding_id": "L001",
                "conclusion": "Alpha check",
                "label": "fail",
                "source_sentence_aliases": ["T0001"],
            }
        ],
    )
    verification_input = materialize_comparison_finding_verification_input(
        job=job,
        aggregate_comparison_evidence=_evidence(),
        findings_job_envelope=findings_job,
        frozen_job_index=1,
    )
    execution = execute_comparison_finding_verification_job(
        verification_input=verification_input,
        frozen_job=job,
        aggregate_comparison_evidence=_evidence(),
        execution_index=1,
        provider=_VerificationProvider(),
    )
    assert not hasattr(execution, "job_dir")


def test_verification_job_invocation_defaults_response_format_applied_false() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    findings_job = _findings_job(
        frozen_job_index=1,
        job=job,
        findings=[
            {
                "finding_id": "L001",
                "conclusion": "Alpha check",
                "label": "fail",
                "source_sentence_aliases": ["T0001"],
            }
        ],
    )
    verification_input = materialize_comparison_finding_verification_input(
        job=job,
        aggregate_comparison_evidence=_evidence(),
        findings_job_envelope=findings_job,
        frozen_job_index=1,
    )
    execution = execute_comparison_finding_verification_job(
        verification_input=verification_input,
        frozen_job=job,
        aggregate_comparison_evidence=_evidence(),
        execution_index=1,
        provider=_VerificationProvider(),
    )
    assert execution.llm_invocations[0].response_format_applied is False


def test_verification_job_invocation_records_provider_applied_json_object() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    findings_job = _findings_job(
        frozen_job_index=1,
        job=job,
        findings=[
            {
                "finding_id": "L001",
                "conclusion": "Alpha check",
                "label": "fail",
                "source_sentence_aliases": ["T0001"],
            }
        ],
    )
    verification_input = materialize_comparison_finding_verification_input(
        job=job,
        aggregate_comparison_evidence=_evidence(),
        findings_job_envelope=findings_job,
        frozen_job_index=1,
    )

    def handler(messages: list[dict[str, str]]) -> LLMRawResult:
        result = _VerificationProvider().generate(messages)
        return LLMRawResult(
            provider_name=result.provider_name,
            model=result.model,
            raw_text=result.raw_text,
            capabilities={"json_object_response_format": True},
            response_format_applied=True,
        )

    execution = execute_comparison_finding_verification_job(
        verification_input=verification_input,
        frozen_job=job,
        aggregate_comparison_evidence=_evidence(),
        execution_index=1,
        provider=_VerificationProvider(handler=handler),
    )
    invocation = execution.llm_invocations[0]
    assert invocation.response_format_applied is True
    assert invocation.capabilities == {
        "json_object_response_format": True,
    }
