"""Neutral Route-to-ESP handoff resolution tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from operations.evidence_source_preparation.consumer_bindings import (
    EvidenceSourcePreparationConsumerBinding,
)
from operations.evidence_source_preparation.route_handoff import (
    resolve_evidence_source_preparation_route_handoff,
)
from operations.projected_source_route.output_contract import route_unit_count_key


class _RecordingStageExecutor:
    def __call__(self, *, stage_input: object) -> object:
        return stage_input


def _consumer_binding(
    *,
    required_route_output_kind: str,
) -> EvidenceSourcePreparationConsumerBinding:
    return EvidenceSourcePreparationConsumerBinding(
        semantic_module_id="module_alpha",
        required_route_output_kind=required_route_output_kind,
        evidence_form_id="form_alpha",
        stage_executor=_RecordingStageExecutor(),
    )


def test_route_handoff_returns_none_without_consumer_binding(tmp_path: Path) -> None:
    route_counts = {route_unit_count_key("table"): 2, "total_routed_unit_count": 2}
    routed_bundle_paths = {"table": tmp_path / "routed_units_table.json"}

    handoff = resolve_evidence_source_preparation_route_handoff(
        route_counts=route_counts,
        routed_bundle_paths=routed_bundle_paths,
        consumer_binding=None,
    )

    assert handoff is None


def test_route_handoff_matches_required_produced_output(tmp_path: Path) -> None:
    route_counts = {route_unit_count_key("table"): 2, "total_routed_unit_count": 2}
    routed_bundle_paths = {"table": tmp_path / "routed_units_table.json"}

    handoff = resolve_evidence_source_preparation_route_handoff(
        route_counts=route_counts,
        routed_bundle_paths=routed_bundle_paths,
        consumer_binding=_consumer_binding(required_route_output_kind="table"),
    )

    assert handoff is not None
    assert handoff.consumer_binding.required_route_output_kind == "table"
    assert handoff.selected_route_output.route_output_kind == "table"
    assert handoff.selected_route_output.unit_count == 2


def test_route_handoff_returns_none_when_required_output_not_produced(
    tmp_path: Path,
) -> None:
    route_counts = {route_unit_count_key("table"): 1, "total_routed_unit_count": 1}
    routed_bundle_paths = {"table": tmp_path / "routed_units_table.json"}

    handoff = resolve_evidence_source_preparation_route_handoff(
        route_counts=route_counts,
        routed_bundle_paths=routed_bundle_paths,
        consumer_binding=_consumer_binding(required_route_output_kind="case"),
    )

    assert handoff is None
