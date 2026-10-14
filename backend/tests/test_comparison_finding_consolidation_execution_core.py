"""Tests for the generic consolidation execution core."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    build_aggregate_comparison_evidence,
)
from llm.providers.base import LLMRawResult
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation import (
    execute_comparison_finding_consolidation,
    materialize_comparison_finding_consolidation_input,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.comparison_finding_consolidation.prompts import (
    load_formal_prompt_definition,
)


def _evidence() -> dict:
    return build_aggregate_comparison_evidence(
        participants=[
            {
                "role_id": "source",
                "aggregate_evidence_source_bundle_id": "bundle",
                "doc_id": "doc",
                "file_hash": "sha256:test",
                "scopes": [
                    {
                        "scope_id": "scope",
                        "scope_alias": "H0001",
                        "heading_path": ["Safety"],
                        "units": [
                            {
                                "unit_id": "unit",
                                "unit_alias": "U0001",
                                "sentences": [
                                    {
                                        "sentence_id": "sentence-1",
                                        "sentence_alias": "T0001",
                                        "text": "First source.",
                                    },
                                    {
                                        "sentence_id": "sentence-2",
                                        "sentence_alias": "T0002",
                                        "text": "Second source.",
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    )


def _finding(index: int) -> dict:
    return {
        "finding_id": f"L{index:03d}",
        "conclusion": f"Conclusion {index}",
        "label": "fail",
        "source_sentence_aliases": [f"T{index:04d}"],
    }


def _input(finding_count: int):
    rows = []
    if finding_count:
        rows = [
            {
                "frozen_job_index": 1,
                "comparison_mode_id": "focus_comparison",
                "comparison_groups": [
                    {"group_role": "focus_scope", "scope_aliases": ["H0001"]}
                ],
                "findings": [_finding(index) for index in range(1, finding_count + 1)],
            }
        ]
    return materialize_comparison_finding_consolidation_input(
        comparison_mode_id="focus_comparison",
        aggregate_comparison_evidence=_evidence(),
        selected_job_final_rows=rows,
    )


class _Provider:
    def __init__(self, raw_text: str | None = None, error: Exception | None = None):
        self.raw_text = raw_text or json.dumps(
            {
                "consolidated_groups": [
                    {
                        "conclusion_aliases": ["C001", "C002"],
                        "unified_conclusion": "Unified",
                        "combined_sentence_aliases": ["T0001", "T0002"],
                    }
                ]
            }
        )
        self.error = error
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        return LLMRawResult(
            provider_name="consolidation-test",
            model="test-model",
            raw_text=self.raw_text,
            request_id="request-1",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )


@pytest.mark.parametrize("finding_count", [0, 1])
def test_fewer_than_two_findings_is_successful_noop(finding_count: int) -> None:
    provider = _Provider()

    execution = execute_comparison_finding_consolidation(
        consolidation_input=_input(finding_count),
        provider=provider,
    )

    assert execution.status == "success"
    assert execution.provider_called is False
    assert execution.finding_count == finding_count
    assert execution.group_count == 0
    assert execution.validated_response is not None
    assert execution.validated_response.consolidated_groups == ()
    assert execution.parse_status == "not_attempted"
    assert execution.validation_status == "not_attempted"
    assert provider.calls == []
    assert execution.llm_invocations == ()


def test_two_findings_calls_provider_and_records_prompt_and_metadata() -> None:
    provider = _Provider()
    consolidation_input = _input(2)

    execution = execute_comparison_finding_consolidation(
        consolidation_input=consolidation_input,
        provider=provider,
    )

    prompt = load_formal_prompt_definition(execution.prompt_id)
    assert execution.status == "success"
    assert execution.provider_called is True
    assert execution.prompt_id == "comparison_finding_consolidation.focus_comparison"
    assert execution.prompt_version == "0.1.0"
    assert execution.messages == (
        {"role": "system", "content": prompt.system_text},
        {"role": "user", "content": consolidation_input.user_input_text},
    )
    assert provider.calls == [list(execution.messages)]
    assert execution.parse_status == "success"
    assert execution.validation_status == "success"
    assert execution.group_count == 1
    assert execution.alias_qc is not None
    assert execution.alias_qc.all_groups_match is True
    assert len(execution.llm_invocations) == 1
    invocation = execution.llm_invocations[0]
    assert invocation.status == "success"
    assert invocation.provider == "consolidation-test"
    assert invocation.model == "test-model"
    assert invocation.request_id == "request-1"
    assert invocation.usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
    }


def test_alias_qc_mismatch_does_not_retry_or_fail_execution() -> None:
    provider = _Provider(
        json.dumps(
            {
                "consolidated_groups": [
                    {
                        "conclusion_aliases": ["C001", "C002"],
                        "unified_conclusion": "Unified",
                        "combined_sentence_aliases": ["T9999"],
                    }
                ]
            }
        )
    )

    execution = execute_comparison_finding_consolidation(
        consolidation_input=_input(2),
        provider=provider,
    )

    assert execution.status == "success"
    assert execution.validation_status == "success"
    assert execution.alias_qc is not None
    assert execution.alias_qc.all_groups_match is False
    assert execution.alias_qc.mismatch_count == 1
    assert len(provider.calls) == 1


def test_provider_failure_is_distinct_outcome() -> None:
    execution = execute_comparison_finding_consolidation(
        consolidation_input=_input(2),
        provider=_Provider(error=RuntimeError("provider unavailable")),
    )

    assert execution.status == "failed"
    assert execution.provider_called is True
    assert execution.parse_status == "not_attempted"
    assert execution.validation_status == "not_attempted"
    assert execution.error_message == "provider unavailable"
    assert execution.raw_response_text is None
    invocation = execution.llm_invocations[0]
    assert invocation.status == "failed"
    assert invocation.error_type == "RuntimeError"
    assert invocation.elapsed_ms >= 0


def test_parse_failure_is_distinct_outcome() -> None:
    execution = execute_comparison_finding_consolidation(
        consolidation_input=_input(2),
        provider=_Provider("not json"),
    )

    assert execution.status == "failed"
    assert execution.parse_status == "failed"
    assert execution.validation_status == "not_attempted"
    assert "not valid JSON" in (execution.error_message or "")
    assert execution.raw_response_text == "not json"
    assert execution.llm_invocations[0].status == "success"


def test_hard_validation_failure_is_distinct_outcome() -> None:
    provider = _Provider(
        json.dumps(
            {
                "consolidated_groups": [
                    {
                        "conclusion_aliases": ["C001"],
                        "unified_conclusion": "Invalid singleton",
                        "combined_sentence_aliases": ["T0001"],
                    }
                ]
            }
        )
    )

    execution = execute_comparison_finding_consolidation(
        consolidation_input=_input(2),
        provider=provider,
    )

    assert execution.status == "failed"
    assert execution.parse_status == "success"
    assert execution.validation_status == "failed"
    assert "at least two distinct" in (execution.error_message or "")
    assert execution.llm_invocations[0].status == "success"
