"""Tests for full in-memory clinical-safety aggregate Evidence Comparison execution."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.comparison_finding_assessment_installation import (
    resolve_installed_comparison_finding_assessment_config,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.final_findings import (
    validate_final_findings,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.findings import (
    validate_findings,
)
from llm.providers.base import LLMRawResult
from steps import evidence_comparison as comparison_step
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence import (
    CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR,
    AggregateEvidenceComparisonExecutionInput,
    AggregateEvidenceComparisonInvocation,
    AggregateEvidenceComparisonParticipant,
    AggregateEvidenceComparisonScope,
    AggregateEvidenceComparisonSentence,
    AggregateEvidenceComparisonSourceProvenance,
    AggregateEvidenceComparisonUnit,
    execute_clinical_trial_aggregate_evidence_comparison,
)
from runtime.io import load_json

_FIXTURE_EVIDENCE = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "evidence_comparison"
    / "clinical_safety"
    / "aggregate_evidence"
    / "internal_dsur"
    / "aggregate_comparison_evidence.json"
)

_PLUGIN_ROOT = (
    BACKEND_ROOT
    / "plugins"
    / "clinical_trial_doc"
    / "evidence_comparison"
    / "clinical_safety"
    / "aggregate_evidence"
)


def _invocation_from_evidence(payload: dict) -> AggregateEvidenceComparisonInvocation:
    participants: list[AggregateEvidenceComparisonParticipant] = []
    for participant in payload["participants"]:
        scopes: list[AggregateEvidenceComparisonScope] = []
        for scope in participant["scopes"]:
            units: list[AggregateEvidenceComparisonUnit] = []
            for unit in scope["units"]:
                sentences = tuple(
                    AggregateEvidenceComparisonSentence(
                        source_sentence_id=sentence["sentence_id"],
                        text=sentence["text"],
                    )
                    for sentence in unit["sentences"]
                )
                units.append(
                    AggregateEvidenceComparisonUnit(
                        source_unit_id=unit["unit_id"],
                        sentences=sentences,
                    )
                )
            scopes.append(
                AggregateEvidenceComparisonScope(
                    source_scope_id=scope["scope_id"],
                    semantic_path=tuple(scope["heading_path"]),
                    units=tuple(units),
                )
            )
        participants.append(
            AggregateEvidenceComparisonParticipant(
                role_id=participant["role_id"],
                source_provenance=AggregateEvidenceComparisonSourceProvenance(
                    source_artifact_id=participant[
                        "aggregate_evidence_source_bundle_id"
                    ],
                    doc_id=participant["doc_id"],
                    file_hash=participant["file_hash"],
                ),
                scopes=tuple(scopes),
            )
        )
    return AggregateEvidenceComparisonInvocation(participants=tuple(participants))


def _first_alias(messages: list[dict[str, str]]) -> str:
    match = re.search(r"\[(T\d{4})\]", messages[-1]["content"])
    if match is None:
        raise AssertionError("expected sentence alias in prompt")
    return match.group(1)


class _FailingProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        raise RuntimeError("provider unavailable")


class _LabeledProvider:
    def __init__(self, *, label: str, delegate) -> None:
        self.label = label
        self.delegate = delegate
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        self.calls.append(messages)
        return self.delegate.generate(messages)


class _FullPipelineProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        user_content = messages[-1]["content"]
        if "## Findings" in user_content:
            finding_ids = _extract_verification_finding_ids(user_content)
            return LLMRawResult(
                provider_name="full-pipeline-mock",
                model="full-pipeline-mock",
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
            provider_name="full-pipeline-mock",
            model="full-pipeline-mock",
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


def _extract_verification_finding_ids(user_content: str) -> list[str]:
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


def test_full_in_memory_executor_end_to_end() -> None:
    evidence_payload = load_json(_FIXTURE_EVIDENCE)
    invocation = _invocation_from_evidence(evidence_payload)
    execution_input = AggregateEvidenceComparisonExecutionInput(
        invocation=invocation,
        assessment_config=resolve_installed_comparison_finding_assessment_config(
            "internal_dsur"
        ),
        assessment_provider=_FullPipelineProvider(),
        assessment_second_pass_provider=_FullPipelineProvider(),
        verification_provider=_FullPipelineProvider(),
        max_concurrency=2,
    )
    result = comparison_step.run_evidence_comparison(
        invocation=execution_input,
        executor=CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_EXECUTOR,
    )
    assert result.planned_job_count >= 1
    assert result.assessment_success_count >= 1
    assert result.verification_success_count >= 1
    assert result.run_status == "success"
    assert result.job_final_findings is not None
    validate_findings(result.job_final_findings)
    assert result.job_final_finding_count >= 1
    validate_final_findings(result.final_findings)
    assert result.final_finding_count >= 1


def test_executor_direct_call() -> None:
    evidence_payload = load_json(_FIXTURE_EVIDENCE)
    execution_input = AggregateEvidenceComparisonExecutionInput(
        invocation=_invocation_from_evidence(evidence_payload),
        assessment_config=resolve_installed_comparison_finding_assessment_config(
            "internal_dsur"
        ),
        assessment_provider=_FullPipelineProvider(),
        assessment_second_pass_provider=_FullPipelineProvider(),
        verification_provider=_FullPipelineProvider(),
    )
    result = execute_clinical_trial_aggregate_evidence_comparison(
        invocation=execution_input,
    )
    assert result.assessment_failed_count == 0
    assert result.verification_failed_count == 0


def test_assessment_all_failed_skips_verification() -> None:
    evidence_payload = load_json(_FIXTURE_EVIDENCE)
    execution_input = AggregateEvidenceComparisonExecutionInput(
        invocation=_invocation_from_evidence(evidence_payload),
        assessment_config=resolve_installed_comparison_finding_assessment_config(
            "internal_dsur"
        ),
        assessment_provider=_FailingProvider(),
        assessment_second_pass_provider=_FailingProvider(),
        verification_provider=_FailingProvider(),
    )
    result = execute_clinical_trial_aggregate_evidence_comparison(
        invocation=execution_input,
    )
    assert result.run_status == "failed"
    assert result.verification is None
    assert result.job_final_findings is None
    validate_final_findings(result.final_findings)
    assert result.final_findings["findings"] == []
    assert result.final_finding_count == 0


def test_assessment_and_verification_use_distinct_providers() -> None:
    evidence_payload = load_json(_FIXTURE_EVIDENCE)
    pipeline = _FullPipelineProvider()
    assessment_provider = _LabeledProvider(label="assessment", delegate=pipeline)
    verification_provider = _LabeledProvider(label="verification", delegate=pipeline)
    execution_input = AggregateEvidenceComparisonExecutionInput(
        invocation=_invocation_from_evidence(evidence_payload),
        assessment_config=resolve_installed_comparison_finding_assessment_config(
            "internal_dsur"
        ),
        assessment_provider=assessment_provider,
        assessment_second_pass_provider=assessment_provider,
        verification_provider=verification_provider,
    )
    result = execute_clinical_trial_aggregate_evidence_comparison(
        invocation=execution_input,
    )

    assert result.run_status == "success"
    assert assessment_provider.calls
    assert verification_provider.calls
    assert all(
        "## Findings" not in call[-1]["content"] for call in assessment_provider.calls
    )
    assert all(
        "## Findings" in call[-1]["content"] for call in verification_provider.calls
    )


def test_plugin_execution_files_have_no_runtime_imports() -> None:
    forbidden_prefixes = ("runtime", "scripts.stage_runners", "application")
    new_files = (
        _PLUGIN_ROOT / "execution.py",
        _PLUGIN_ROOT / "execution_types.py",
        _PLUGIN_ROOT / "executor.py",
        _PLUGIN_ROOT / "comparison_finding_assessment" / "execution.py",
        _PLUGIN_ROOT / "comparison_finding_verification" / "execution.py",
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
                if any(
                    imported == prefix or imported.startswith(prefix + ".")
                    for prefix in forbidden_prefixes
                ):
                    violations.append(f"{path.name} imports {imported}")
    assert not violations, "\n".join(violations)
