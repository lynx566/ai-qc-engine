"""Concrete Aggregate Evidence Comparison transport tests."""

from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    build_aggregate_evidence_source_bundle,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_adapter import (
    build_aggregate_evidence_comparison_invocation,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceComparisonInvocation,
    AggregateEvidenceComparisonParticipant,
    AggregateEvidenceComparisonParticipantEvidence,
    AggregateEvidenceComparisonScope,
    AggregateEvidenceComparisonSentence,
    AggregateEvidenceComparisonSourceProvenance,
    AggregateEvidenceComparisonUnit,
)
from operations.evidence_comparison.contracts import (
    EvidenceComparisonInvocation,
    EvidenceComparisonResult,
)
from operations.evidence_comparison.participants import (
    EvidenceComparisonParticipantReference,
)
from operations.evidence_comparison.stage import (
    EvidenceComparisonExecutionDependencies,
    EvidenceComparisonStageContext,
    EvidenceComparisonStageInput,
)
from steps import evidence_comparison as comparison_step
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.source_adapter import (
    adapt_clinical_safety_aggregate_source_bundle,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    execute_aggregate_evidence_comparison_transport,
)
from runtime.io import save_json


class _RecordingResult(EvidenceComparisonResult):
    pass


def _scope(*, text: str, block_id: str) -> dict:
    return {
        "scope_id": "HS0001",
        "scope_order": 0,
        "heading_path": ["Aggregate evidence"],
        "units": [
            {
                "unit_id": "TU0001",
                "unit_order": 0,
                "text": text,
                "source": {"block_ids": [block_id]},
                "sentences": [
                    {
                        "sentence_id": "S0001",
                        "sentence_order": 0,
                        "text": text,
                        "source_block_ids": [block_id],
                    }
                ],
            }
        ],
    }


def _bundle(*, doc_id: str, document_type: str, text: str) -> dict:
    return build_aggregate_evidence_source_bundle(
        doc_id=doc_id,
        file_hash=f"sha256:{doc_id}",
        document_type=document_type,
        heading_scopes=[_scope(text=text, block_id=f"B-{doc_id}")],
    )


def _participant(*, role_id: str, slot_id: str, path: Path):
    return EvidenceComparisonParticipantReference(
        role_id=role_id,
        slot_id=slot_id,
        semantic_module_id="aggregate_evidence",
        declared_output_path=path,
    )


def _stage_input(
    tmp_path: Path,
    *participants: EvidenceComparisonParticipantReference,
) -> EvidenceComparisonStageInput:
    return EvidenceComparisonStageInput(
        participants=tuple(participants),
        context=EvidenceComparisonStageContext(output_dir=tmp_path / "comparison"),
        execution_dependencies=EvidenceComparisonExecutionDependencies(),
    )


def _run_recording(
    stage_input: EvidenceComparisonStageInput,
    *,
    source_adapter=adapt_clinical_safety_aggregate_source_bundle,
) -> tuple[EvidenceComparisonResult, list[EvidenceComparisonInvocation]]:
    calls: list[EvidenceComparisonInvocation] = []

    def executor(
        *, invocation: EvidenceComparisonInvocation
    ) -> EvidenceComparisonResult:
        calls.append(invocation)
        return _RecordingResult()

    result = execute_aggregate_evidence_comparison_transport(
        stage_input=stage_input,
        evidence_comparison_executor=executor,
        source_adapter=source_adapter,
    )
    return result, calls


def test_single_participant_is_loaded_into_specialization_invocation(
    tmp_path: Path,
) -> None:
    source_bundle = _bundle(doc_id="doc_ib", document_type="ib", text="IB text")
    source_path = tmp_path / "ib.json"
    save_json(source_path, source_bundle)

    result, calls = _run_recording(
        _stage_input(
            tmp_path,
            _participant(role_id="subject", slot_id="source", path=source_path),
        )
    )

    assert isinstance(result, _RecordingResult)
    assert len(calls) == 1
    invocation = calls[0]
    assert isinstance(invocation, AggregateEvidenceComparisonInvocation)
    assert invocation.participants == (
        AggregateEvidenceComparisonParticipant(
            role_id="subject",
            source_provenance=(
                adapt_clinical_safety_aggregate_source_bundle(
                    source_bundle
                ).source_provenance
            ),
            scopes=adapt_clinical_safety_aggregate_source_bundle(source_bundle).scopes,
        ),
    )


def test_two_participants_preserve_handoff_role_and_order(tmp_path: Path) -> None:
    ib_bundle = _bundle(doc_id="doc_ib", document_type="ib", text="IB text")
    dsur_bundle = _bundle(doc_id="doc_dsur", document_type="dsur", text="DSUR text")
    ib_path = tmp_path / "ib.json"
    dsur_path = tmp_path / "dsur.json"
    save_json(ib_path, ib_bundle)
    save_json(dsur_path, dsur_bundle)

    _, calls = _run_recording(
        _stage_input(
            tmp_path,
            _participant(role_id="second", slot_id="source_b", path=ib_path),
            _participant(role_id="first", slot_id="source_a", path=dsur_path),
        )
    )

    invocation = calls[0]
    assert isinstance(invocation, AggregateEvidenceComparisonInvocation)
    assert tuple(item.role_id for item in invocation.participants) == (
        "second",
        "first",
    )
    assert tuple(item.source_provenance.doc_id for item in invocation.participants) == (
        "doc_ib",
        "doc_dsur",
    )


def test_transport_rejects_invalid_json_before_executor(tmp_path: Path) -> None:
    source_path = tmp_path / "invalid.json"
    source_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        _run_recording(
            _stage_input(
                tmp_path,
                _participant(role_id="subject", slot_id="source", path=source_path),
            )
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    [
        ("artifact_type", "wrong_artifact", "artifact_type"),
        ("schema_version", "999.0.0", "schema_version"),
    ],
)
def test_transport_reuses_formal_bundle_validation(
    tmp_path: Path,
    field_name: str,
    invalid_value: str,
    message: str,
) -> None:
    invalid_bundle = copy.deepcopy(
        _bundle(doc_id="doc_ib", document_type="ib", text="IB text")
    )
    invalid_bundle[field_name] = invalid_value
    source_path = tmp_path / "invalid-bundle.json"
    save_json(source_path, invalid_bundle)

    with pytest.raises(ValueError, match=message):
        _run_recording(
            _stage_input(
                tmp_path,
                _participant(role_id="subject", slot_id="source", path=source_path),
            )
        )


def test_role_adapter_does_not_leak_transport_or_raw_source_identity() -> None:
    source_bundle = _bundle(doc_id="doc_ib", document_type="ib", text="IB text")
    canonical_evidence = adapt_clinical_safety_aggregate_source_bundle(source_bundle)

    invocation = build_aggregate_evidence_comparison_invocation(
        participants=(("subject", canonical_evidence),)
    )

    assert tuple(invocation.__dataclass_fields__) == ("participants",)
    participant = invocation.participants[0]
    assert tuple(participant.__dataclass_fields__) == (
        "role_id",
        "source_provenance",
        "scopes",
    )
    assert not hasattr(participant, "source_bundle")
    assert not hasattr(participant, "slot_id")
    assert not hasattr(participant, "semantic_module_id")
    assert not hasattr(participant, "declared_output_path")


def test_transport_calls_canonical_pipeline_step_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "ib.json"
    save_json(
        source_path,
        _bundle(doc_id="doc_ib", document_type="ib", text="IB text"),
    )
    real_step = comparison_step.run_evidence_comparison
    step_calls: list[EvidenceComparisonInvocation] = []
    executor_calls: list[EvidenceComparisonInvocation] = []

    def recording_step(*, invocation, executor):
        step_calls.append(invocation)
        return real_step(invocation=invocation, executor=executor)

    def executor(*, invocation):
        executor_calls.append(invocation)
        return _RecordingResult()

    monkeypatch.setattr(comparison_step, "run_evidence_comparison", recording_step)
    execute_aggregate_evidence_comparison_transport(
        stage_input=_stage_input(
            tmp_path,
            _participant(role_id="subject", slot_id="source", path=source_path),
        ),
        evidence_comparison_executor=executor,
        source_adapter=adapt_clinical_safety_aggregate_source_bundle,
    )

    assert len(step_calls) == 1
    assert executor_calls == step_calls


def test_transport_uses_injected_adapter_for_a_nonclinical_raw_mapping(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "custom.json"
    save_json(source_path, {"producer_payload": "custom"})
    canonical_evidence = AggregateEvidenceComparisonParticipantEvidence(
        source_provenance=AggregateEvidenceComparisonSourceProvenance(
            source_artifact_id="custom-artifact",
            doc_id="custom-doc",
            file_hash="custom-hash",
        ),
        scopes=(
            AggregateEvidenceComparisonScope(
                source_scope_id="custom-scope",
                semantic_path=("Custom",),
                units=(
                    AggregateEvidenceComparisonUnit(
                        source_unit_id="custom-unit",
                        sentences=(
                            AggregateEvidenceComparisonSentence(
                                source_sentence_id="custom-sentence",
                                text="custom text",
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    def adapt_custom_source(source):
        assert source == {"producer_payload": "custom"}
        return canonical_evidence

    _, calls = _run_recording(
        _stage_input(
            tmp_path,
            _participant(role_id="custom", slot_id="source", path=source_path),
        ),
        source_adapter=adapt_custom_source,
    )

    invocation = calls[0]
    assert isinstance(invocation, AggregateEvidenceComparisonInvocation)
    assert invocation.participants[0].source_provenance.source_artifact_id == (
        "custom-artifact"
    )


def test_concrete_runtime_has_no_prompt_or_private_strategy_imports() -> None:
    runtime_path = (
        BACKEND_ROOT
        / "runtime/evidence_comparison/clinical_trial_doc/clinical_safety/"
        "aggregate_evidence/stage.py"
    )
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert not any("prompt" in module for module in imported_modules)
    assert not any("strategy" in module for module in imported_modules)
    assert not any("evidence_source_preparation" in module for module in imported_modules)
