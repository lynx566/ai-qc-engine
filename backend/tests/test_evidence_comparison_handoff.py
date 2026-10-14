"""Neutral ESP-to-Evidence-Comparison fan-in handoff tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from operations.evidence_comparison.consumer_bindings import (
    EvidenceComparisonConsumerBinding,
)
from operations.evidence_comparison.handoff import (
    EvidenceComparisonHandoffResolutionStatus,
    EvidenceComparisonParticipantRequirement,
    ProducedEvidenceSourcePreparationOutputReference,
    resolve_evidence_comparison_handoff,
)
from operations.evidence_comparison.stage import (
    EvidenceComparisonStageInput,
    EvidenceComparisonStageResult,
)


class _RecordingStageExecutor:
    def __call__(
        self,
        *,
        stage_input: EvidenceComparisonStageInput,
    ) -> EvidenceComparisonStageResult:
        raise AssertionError("resolver must not invoke the stage executor")


def _binding(
    *requirements: EvidenceComparisonParticipantRequirement,
) -> EvidenceComparisonConsumerBinding:
    return EvidenceComparisonConsumerBinding(
        capability_id="capability_alpha",
        participant_requirements=tuple(requirements),
        stage_executor=_RecordingStageExecutor(),
    )


def _requirement(
    role_id: str,
    slot_id: str,
    semantic_module_id: str = "module_alpha",
) -> EvidenceComparisonParticipantRequirement:
    return EvidenceComparisonParticipantRequirement(
        role_id=role_id,
        slot_id=slot_id,
        semantic_module_id=semantic_module_id,
    )


def _produced(
    tmp_path: Path,
    slot_id: str,
    semantic_module_id: str = "module_alpha",
) -> ProducedEvidenceSourcePreparationOutputReference:
    return ProducedEvidenceSourcePreparationOutputReference(
        slot_id=slot_id,
        semantic_module_id=semantic_module_id,
        declared_output_path=tmp_path / f"{slot_id}.json",
    )


def test_resolver_distinguishes_absent_binding_from_incomplete_binding(
    tmp_path: Path,
) -> None:
    unbound = resolve_evidence_comparison_handoff(
        consumer_binding=None,
        produced_outputs=(_produced(tmp_path, "source"),),
    )
    incomplete = resolve_evidence_comparison_handoff(
        consumer_binding=_binding(_requirement("subject", "source")),
        produced_outputs=(),
    )

    assert unbound.status is EvidenceComparisonHandoffResolutionStatus.UNBOUND
    assert unbound.consumer_binding is None
    assert unbound.handoff is None
    assert unbound.missing_participant_requirements == ()

    assert incomplete.status is EvidenceComparisonHandoffResolutionStatus.INCOMPLETE
    assert incomplete.consumer_binding is not None
    assert incomplete.handoff is None
    assert incomplete.missing_participant_requirements == (
        _requirement("subject", "source"),
    )


def test_resolver_builds_single_participant_handoff(tmp_path: Path) -> None:
    binding = _binding(_requirement("subject", "source"))

    resolution = resolve_evidence_comparison_handoff(
        consumer_binding=binding,
        produced_outputs=(_produced(tmp_path, "source"),),
    )

    assert resolution.status is EvidenceComparisonHandoffResolutionStatus.READY
    assert resolution.handoff is not None
    assert resolution.handoff.consumer_binding is binding
    assert [participant.role_id for participant in resolution.handoff.participants] == [
        "subject"
    ]
    assert resolution.handoff.participants[0].declared_output_path == (
        tmp_path / "source.json"
    )


def test_resolver_preserves_application_order_for_two_participant_fan_in(
    tmp_path: Path,
) -> None:
    binding = _binding(
        _requirement("later", "source_b"),
        _requirement("earlier", "source_a"),
    )

    resolution = resolve_evidence_comparison_handoff(
        consumer_binding=binding,
        produced_outputs=(
            _produced(tmp_path, "source_a"),
            _produced(tmp_path, "source_b"),
        ),
    )

    assert resolution.handoff is not None
    assert [participant.role_id for participant in resolution.handoff.participants] == [
        "later",
        "earlier",
    ]
    assert [participant.slot_id for participant in resolution.handoff.participants] == [
        "source_b",
        "source_a",
    ]


def test_resolver_rejects_duplicate_produced_selector(tmp_path: Path) -> None:
    produced = _produced(tmp_path, "source")

    with pytest.raises(ValueError, match="duplicate produced ESP output selector"):
        resolve_evidence_comparison_handoff(
            consumer_binding=_binding(_requirement("subject", "source")),
            produced_outputs=(produced, produced),
        )


def test_binding_rejects_duplicate_requirement_selector() -> None:
    with pytest.raises(ValueError, match="duplicate participant selector"):
        _binding(
            _requirement("first", "source"),
            _requirement("second", "source"),
        )


def test_resolver_ignores_unrelated_esp_outputs(tmp_path: Path) -> None:
    resolution = resolve_evidence_comparison_handoff(
        consumer_binding=_binding(_requirement("subject", "source")),
        produced_outputs=(
            _produced(tmp_path, "unrelated_slot"),
            _produced(tmp_path, "source"),
            _produced(tmp_path, "source", semantic_module_id="unrelated_module"),
        ),
    )

    assert resolution.handoff is not None
    assert len(resolution.handoff.participants) == 1
    assert resolution.handoff.participants[0].slot_id == "source"
    assert resolution.handoff.participants[0].semantic_module_id == "module_alpha"


def test_resolver_does_not_read_declared_output_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "not-json.json"
    path.write_text("not json", encoding="utf-8")

    def fail_read(*args, **kwargs):
        raise AssertionError("neutral resolver must not read declared output")

    monkeypatch.setattr(Path, "read_text", fail_read)
    resolution = resolve_evidence_comparison_handoff(
        consumer_binding=_binding(_requirement("subject", "source")),
        produced_outputs=(
            ProducedEvidenceSourcePreparationOutputReference(
                slot_id="source",
                semantic_module_id="module_alpha",
                declared_output_path=path,
            ),
        ),
    )

    assert resolution.status is EvidenceComparisonHandoffResolutionStatus.READY

