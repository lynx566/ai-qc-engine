"""Neutral Evidence Source Preparation consumer binding contract tests."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from operations.evidence_source_preparation.consumer_bindings import (
    EvidenceSourcePreparationConsumerBinding,
    EvidenceSourcePreparationConsumerBindings,
)

CONSUMER_BINDINGS_PATH = (
    BACKEND_ROOT
    / "operations"
    / "evidence_source_preparation"
    / "consumer_bindings.py"
)


class _RecordingStageExecutor:
    def __call__(self, *, stage_input: Any) -> Any:
        return stage_input


def _binding(
    *,
    semantic_module_id: str = "module_alpha",
    required_route_output_kind: str = "table",
    evidence_form_id: str = "form_alpha",
) -> EvidenceSourcePreparationConsumerBinding:
    return EvidenceSourcePreparationConsumerBinding(
        semantic_module_id=semantic_module_id,
        required_route_output_kind=required_route_output_kind,
        evidence_form_id=evidence_form_id,
        stage_executor=_RecordingStageExecutor(),
    )


def test_consumer_binding_requires_non_empty_fields() -> None:
    with pytest.raises(ValueError, match="required_route_output_kind"):
        EvidenceSourcePreparationConsumerBinding(
            semantic_module_id="module_alpha",
            required_route_output_kind="",
            evidence_form_id="form_alpha",
            stage_executor=_RecordingStageExecutor(),
        )


def test_consumer_bindings_rejects_key_semantic_module_mismatch() -> None:
    with pytest.raises(ValueError, match="must match bindings key"):
        EvidenceSourcePreparationConsumerBindings(
            bindings={
                "module_alpha": _binding(semantic_module_id="module_beta"),
            }
        )


def test_resolve_consumer_binding_returns_installed_binding() -> None:
    binding = _binding()
    bindings = EvidenceSourcePreparationConsumerBindings(
        bindings={"module_alpha": binding},
    )

    resolved = bindings.resolve_consumer_binding("module_alpha")

    assert resolved is binding
    assert resolved.required_route_output_kind == "table"
    assert resolved.evidence_form_id == "form_alpha"


def test_consumer_bindings_exposes_only_full_consumer_resolution() -> None:
    binding = _binding()
    bindings = EvidenceSourcePreparationConsumerBindings(
        bindings={"module_alpha": binding},
    )

    resolved = bindings.resolve_consumer_binding("module_alpha")

    assert resolved is binding
    assert resolved.stage_executor is binding.stage_executor
    assert not hasattr(bindings, "resolve_stage_executor")


def test_consumer_bindings_module_has_no_route_selection_imports() -> None:
    tree = ast.parse(
        CONSUMER_BINDINGS_PATH.read_text(encoding="utf-8"),
        filename=str(CONSUMER_BINDINGS_PATH),
    )
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden_prefixes = (
        "operations.projected_source_route.consumer_selection",
        "operations.projected_source_route.output_contract",
        "application.",
        "plugins.",
        "runtime.",
    )
    for module in imported:
        for prefix in forbidden_prefixes:
            assert not module.startswith(prefix), (
                f"consumer_bindings must not import {module!r}"
            )
