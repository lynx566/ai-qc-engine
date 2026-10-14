"""Neutral Evidence Comparison Pipeline Step and stage-runtime tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from operations.evidence_comparison.contracts import (
    EvidenceComparisonInvocation,
    EvidenceComparisonResult,
)
from operations.evidence_comparison.handoff import (
    EvidenceComparisonParticipantReference,
)
from operations.evidence_comparison.stage import (
    EvidenceComparisonExecutionDependencies,
    EvidenceComparisonStageContext,
    EvidenceComparisonStageInput,
    EvidenceComparisonStageResult,
)
from steps.evidence_comparison import run_evidence_comparison
from runtime.evidence_comparison_stage import run_evidence_comparison_stage


class _Invocation(EvidenceComparisonInvocation):
    pass


class _Result(EvidenceComparisonResult):
    pass


def test_pipeline_step_delegates_once_to_evidence_comparison_executor() -> None:
    invocation = _Invocation()
    calls: list[EvidenceComparisonInvocation] = []

    def executor(*, invocation: EvidenceComparisonInvocation) -> EvidenceComparisonResult:
        calls.append(invocation)
        return _Result()

    result = run_evidence_comparison(invocation=invocation, executor=executor)

    assert isinstance(result, _Result)
    assert calls == [invocation]


def test_pipeline_step_rejects_non_comparison_result() -> None:
    def executor(*, invocation: EvidenceComparisonInvocation) -> object:
        return object()

    with pytest.raises(TypeError, match="EvidenceComparisonResult"):
        run_evidence_comparison(invocation=_Invocation(), executor=executor)


def test_generic_stage_runtime_delegates_without_loading_participant_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    participant = EvidenceComparisonParticipantReference(
        role_id="subject",
        slot_id="source",
        semantic_module_id="module_alpha",
        declared_output_path=tmp_path / "not-json.json",
    )
    stage_input = EvidenceComparisonStageInput(
        participants=(participant,),
        context=EvidenceComparisonStageContext(
            output_dir=tmp_path / "comparison",
            run_id="evidence_comparison",
        ),
        execution_dependencies=EvidenceComparisonExecutionDependencies(),
    )
    calls: list[EvidenceComparisonStageInput] = []

    def fail_read(*args, **kwargs):
        raise AssertionError("generic runtime must not load participant output")

    def stage_executor(
        *,
        stage_input: EvidenceComparisonStageInput,
    ) -> EvidenceComparisonStageResult:
        calls.append(stage_input)
        return EvidenceComparisonStageResult(
            output_dir=stage_input.context.output_dir,
            run_id="evidence_comparison",
            stage_executor_id="recording.executor",
            run_status="success",
            run_summary_path=stage_input.context.output_dir / "run_summary.json",
        )

    monkeypatch.setattr(Path, "read_text", fail_read)
    result = run_evidence_comparison_stage(
        stage_input=stage_input,
        stage_executor=stage_executor,
    )

    assert result.stage_executor_id == "recording.executor"
    assert calls == [stage_input]

