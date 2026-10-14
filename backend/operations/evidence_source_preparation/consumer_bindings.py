"""Neutral Evidence Source Preparation consumer bindings for routed semantic modules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationStageExecutor,
)


def _require_non_empty_str(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty, trimmed string")
    return stripped


@dataclass(frozen=True, slots=True)
class EvidenceSourcePreparationConsumerBinding:
    """Installed ESP consumer requirements for one routed semantic module."""

    semantic_module_id: str
    required_route_output_kind: str
    evidence_form_id: str
    stage_executor: EvidenceSourcePreparationStageExecutor

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "semantic_module_id",
            _require_non_empty_str(
                self.semantic_module_id,
                field_name="semantic_module_id",
            ),
        )
        object.__setattr__(
            self,
            "required_route_output_kind",
            _require_non_empty_str(
                self.required_route_output_kind,
                field_name="required_route_output_kind",
            ),
        )
        object.__setattr__(
            self,
            "evidence_form_id",
            _require_non_empty_str(
                self.evidence_form_id,
                field_name="evidence_form_id",
            ),
        )


@dataclass(frozen=True, slots=True)
class EvidenceSourcePreparationConsumerBindings:
    """Maps one routed semantic module id to at most one installed ESP consumer."""

    bindings: Mapping[str, EvidenceSourcePreparationConsumerBinding]

    def __post_init__(self) -> None:
        for key, binding in self.bindings.items():
            module_key = _require_non_empty_str(key, field_name="bindings key")
            if not isinstance(binding, EvidenceSourcePreparationConsumerBinding):
                raise TypeError(
                    f"bindings[{module_key!r}] must be an "
                    "EvidenceSourcePreparationConsumerBinding"
                )
            if binding.semantic_module_id != module_key:
                raise ValueError(
                    "binding.semantic_module_id must match bindings key: "
                    f"{binding.semantic_module_id!r} != {module_key!r}"
                )

    def resolve_consumer_binding(
        self,
        semantic_module_id: str,
    ) -> EvidenceSourcePreparationConsumerBinding | None:
        if not isinstance(semantic_module_id, str) or not semantic_module_id.strip():
            raise ValueError("semantic_module_id must be a non-empty string")
        return self.bindings.get(semantic_module_id.strip())


__all__ = [
    "EvidenceSourcePreparationConsumerBinding",
    "EvidenceSourcePreparationConsumerBindings",
]
