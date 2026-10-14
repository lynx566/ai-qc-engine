"""Tests for Comparison Finding Assessment in-memory execution core."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
)
from llm.providers.base import LLMRawResult
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_assessment import (
    ComparisonFindingAssessmentGroup,
    ComparisonFindingAssessmentJob,
    execute_comparison_finding_assessment_job,
    execute_comparison_finding_assessment_jobs,
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
                            }
                        ],
                    },
                    {
                        "scope_id": "HS0002",
                        "scope_alias": "H0002",
                        "heading_path": ["Comparison"],
                        "units": [
                            {
                                "unit_id": "TU0002",
                                "unit_alias": "U0002",
                                "sentences": [
                                    {
                                        "sentence_id": "C0002:S001",
                                        "sentence_alias": "T0003",
                                        "text": "Delta",
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


def _first_alias(messages: list[dict[str, str]]) -> str:
    match = re.search(r"\[(T\d{4})\]", messages[-1]["content"])
    if match is None:
        raise AssertionError("expected sentence alias in prompt")
    return match.group(1)


class _AssessmentProvider:
    def __init__(self, *, handler=None) -> None:
        self._handler = handler or self._default_handler
        self.calls = 0

    def _default_handler(self, messages: list[dict[str, str]]) -> LLMRawResult:
        alias = _first_alias(messages)
        payload = {
            "candidates": [
                {
                    "candidate_focus": f"candidate for {alias}",
                    "label": "fail",
                    "trigger_sentence_aliases": [alias],
                }
            ]
        }
        return LLMRawResult(
            provider_name="assessment-mock",
            model="assessment-mock",
            raw_text=json.dumps(payload),
        )

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        self.calls += 1
        return self._handler(messages)


class _FailingProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        raise RuntimeError("provider unavailable")


def test_assessment_job_success() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    provider = _AssessmentProvider()
    execution = execute_comparison_finding_assessment_job(
        frozen_job_index=1,
        execution_index=1,
        job=job,
        aggregate_comparison_evidence=_evidence(),
        provider=provider,
    )
    assert execution.status == "success"
    assert execution.finding_count == 1
    assert execution.accepted_response is not None
    assert not hasattr(execution, "job_dir")


def test_assessment_provider_failure() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    execution = execute_comparison_finding_assessment_job(
        frozen_job_index=1,
        execution_index=1,
        job=job,
        aggregate_comparison_evidence=_evidence(),
        provider=_FailingProvider(),
    )
    assert execution.status == "failed"
    assert execution.parse_status == "not_attempted"
    invocation = execution.llm_invocations[0]
    assert invocation.status == "failed"
    assert invocation.attempt_index == 1
    assert invocation.error_type == "RuntimeError"
    assert invocation.error_message == "provider unavailable"
    assert invocation.elapsed_ms >= 0


def test_assessment_validation_failure() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))

    def handler(messages: list[dict[str, str]]) -> LLMRawResult:
        return LLMRawResult(
            provider_name="assessment-mock",
            model="assessment-mock",
            raw_text='{"candidates": [{"candidate_focus": "x", "label": "bad", "trigger_sentence_aliases": ["T9999"]}]}',
        )

    execution = execute_comparison_finding_assessment_job(
        frozen_job_index=1,
        execution_index=1,
        job=job,
        aggregate_comparison_evidence=_evidence(),
        provider=_AssessmentProvider(handler=handler),
    )
    assert execution.status == "failed"
    assert execution.parse_status == "failed"
    assert execution.llm_invocations[0].status == "success"


def test_assessment_candidate_partial_drop() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))

    def handler(messages: list[dict[str, str]]) -> LLMRawResult:
        return LLMRawResult(
            provider_name="assessment-mock",
            model="assessment-mock",
            raw_text=json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_focus": "good",
                            "label": "fail",
                            "trigger_sentence_aliases": [_first_alias(messages)],
                        },
                        {
                            "candidate_focus": "bad alias",
                            "label": "fail",
                            "trigger_sentence_aliases": ["T9999"],
                        },
                    ]
                }
            ),
        )

    execution = execute_comparison_finding_assessment_job(
        frozen_job_index=1,
        execution_index=1,
        job=job,
        aggregate_comparison_evidence=_evidence(),
        provider=_AssessmentProvider(handler=handler),
    )
    assert execution.status == "success"
    assert execution.candidate_count == 2
    assert execution.accepted_candidate_count == 1
    assert execution.dropped_candidate_count == 1


def test_assessment_all_candidates_dropped() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))

    def handler(_messages: list[dict[str, str]]) -> LLMRawResult:
        return LLMRawResult(
            provider_name="assessment-mock",
            model="assessment-mock",
            raw_text=json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_focus": "bad",
                            "label": "fail",
                            "trigger_sentence_aliases": ["T9999"],
                        }
                    ]
                }
            ),
        )

    execution = execute_comparison_finding_assessment_job(
        frozen_job_index=1,
        execution_index=1,
        job=job,
        aggregate_comparison_evidence=_evidence(),
        provider=_AssessmentProvider(handler=handler),
    )
    assert execution.status == "success"
    assert execution.finding_count == 0


def test_assessment_batch_partial_failure_and_ordering() -> None:
    jobs = (
        (1, _job("scope_local", ("scope", ("H0001",)))),
        (2, _job("focus_comparison", ("focus_scope", ("H0001",)), ("comparison_scopes", ("H0002",)))),
    )
    call_count = {"value": 0}

    def handler(messages: list[dict[str, str]]) -> LLMRawResult:
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise RuntimeError("second job failed")
        return _AssessmentProvider().generate(messages)

    batch = execute_comparison_finding_assessment_jobs(
        selected_jobs=jobs,
        aggregate_comparison_evidence=_evidence(),
        provider=_AssessmentProvider(handler=handler),
        max_concurrency=1,
    )
    assert batch.run_status == "partial_failure"
    assert batch.success_count == 1
    assert batch.failed_count == 1
    assert [item.frozen_job_index for item in batch.job_executions] == [1, 2]
    assert batch.findings_artifact is not None
    assert batch.finding_count == 1


def test_assessment_batch_all_failed() -> None:
    jobs = ((1, _job("scope_local", ("scope", ("H0001",)))),)
    batch = execute_comparison_finding_assessment_jobs(
        selected_jobs=jobs,
        aggregate_comparison_evidence=_evidence(),
        provider=_FailingProvider(),
    )
    assert batch.run_status == "failed"
    assert batch.findings_artifact is None


def test_assessment_job_invocation_defaults_response_format_applied_false() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))
    execution = execute_comparison_finding_assessment_job(
        frozen_job_index=1,
        execution_index=1,
        job=job,
        aggregate_comparison_evidence=_evidence(),
        provider=_AssessmentProvider(),
    )
    assert len(execution.llm_invocations) == 1
    invocation = execution.llm_invocations[0]
    assert invocation.status == "success"
    assert invocation.attempt_index == 1
    assert invocation.response_format_applied is False
    assert invocation.capabilities is None


def test_assessment_job_invocation_records_provider_applied_json_object() -> None:
    job = _job("scope_local", ("scope", ("H0001",)))

    def handler(messages: list[dict[str, str]]) -> LLMRawResult:
        result = _AssessmentProvider().generate(messages)
        return LLMRawResult(
            provider_name=result.provider_name,
            model=result.model,
            raw_text=result.raw_text,
            capabilities={"json_object_response_format": True},
            response_format_applied=True,
        )

    execution = execute_comparison_finding_assessment_job(
        frozen_job_index=1,
        execution_index=1,
        job=job,
        aggregate_comparison_evidence=_evidence(),
        provider=_AssessmentProvider(handler=handler),
    )
    invocation = execution.llm_invocations[0]
    assert invocation.capabilities == {
        "json_object_response_format": True,
    }
    assert invocation.response_format_applied is True
