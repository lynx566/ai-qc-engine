"""Neutral fan-in and semantic-module selection for Filter-output projection results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from artifacts.filter_output_projection_bundle import (
    filter_output_projection_step_result_from_bundle,
)
from operations.filter_output_projection.contracts import (
    FilterOutputProjectionStepResult,
    ProjectedSource,
)


@dataclass(frozen=True, slots=True)
class ProjectionInputRef:
    """Formal identity of one Filter-output projection bundle that contributed sources."""

    filter_output_projection_bundle_id: str
    filter_job_id: str
    zone_key: str

    def to_dict(self) -> dict[str, str]:
        return {
            "filter_output_projection_bundle_id": self.filter_output_projection_bundle_id,
            "filter_job_id": self.filter_job_id,
            "zone_key": self.zone_key,
        }


@dataclass(frozen=True, slots=True)
class ProjectionFanInInput:
    """One persisted projection bundle paired with its in-memory step result."""

    step_result: FilterOutputProjectionStepResult
    filter_output_projection_bundle_id: str


@dataclass(frozen=True, slots=True)
class SemanticModuleSelectionResult:
    """Mechanical semantic-module selection over projected sources."""

    semantic_module_id: str
    selected_projected_sources: tuple[ProjectedSource, ...]
    unselected_projected_sources: tuple[ProjectedSource, ...]
    projection_input_refs: tuple[ProjectionInputRef, ...]


def _validate_projection_fan_in_inputs_identity(
    projection_fan_in_inputs: Sequence[ProjectionFanInInput],
) -> tuple[str, str]:
    if not projection_fan_in_inputs:
        raise ValueError("projection_fan_in_inputs must be non-empty")

    doc_ids: set[str] = set()
    file_hashes: set[str] = set()
    seen_bundle_ids: set[str] = set()
    for index, fan_in_input in enumerate(projection_fan_in_inputs):
        if not isinstance(fan_in_input, ProjectionFanInInput):
            raise TypeError(
                f"projection_fan_in_inputs[{index}] must be a ProjectionFanInInput"
            )
        result = fan_in_input.step_result
        if not isinstance(result, FilterOutputProjectionStepResult):
            raise TypeError(
                f"projection_fan_in_inputs[{index}].step_result must be a "
                "FilterOutputProjectionStepResult"
            )
        bundle_id = fan_in_input.filter_output_projection_bundle_id.strip()
        if not bundle_id:
            raise ValueError(
                f"projection_fan_in_inputs[{index}].filter_output_projection_bundle_id "
                "is required"
            )
        if bundle_id in seen_bundle_ids:
            raise ValueError(
                "projection_fan_in_inputs contains duplicate "
                f"filter_output_projection_bundle_id {bundle_id!r}"
            )
        seen_bundle_ids.add(bundle_id)
        doc_ids.add(result.doc_id)
        file_hashes.add(result.file_hash)

    if len(doc_ids) != 1:
        raise ValueError("projection_fan_in_inputs must share one doc_id")
    if len(file_hashes) != 1:
        raise ValueError("projection_fan_in_inputs must share one file_hash")
    return next(iter(doc_ids)), next(iter(file_hashes))


def build_projection_fan_in_inputs_from_bundles(
    bundles: Sequence[Mapping[str, Any]],
) -> tuple[ProjectionFanInInput, ...]:
    """Build fan-in inputs from persisted filter_output_projection_bundle payloads."""

    if not bundles:
        raise ValueError("bundles must be non-empty")

    fan_in_inputs: list[ProjectionFanInInput] = []
    for index, bundle in enumerate(bundles):
        if not isinstance(bundle, Mapping):
            raise TypeError(f"bundles[{index}] must be a mapping")

        bundle_id = bundle.get("filter_output_projection_bundle_id")
        if not isinstance(bundle_id, str) or not bundle_id.strip():
            raise ValueError(
                f"bundles[{index}].filter_output_projection_bundle_id is required"
            )

        step_result = filter_output_projection_step_result_from_bundle(bundle)
        fan_in_inputs.append(
            ProjectionFanInInput(
                step_result=step_result,
                filter_output_projection_bundle_id=bundle_id.strip(),
            )
        )

    return tuple(fan_in_inputs)


def select_projected_sources_for_semantic_module(
    *,
    projection_fan_in_inputs: Sequence[ProjectionFanInInput],
    semantic_module_id: str,
    enabled_route_semantic_module_ids: Mapping[str, object] | frozenset[str] | None = None,
) -> SemanticModuleSelectionResult:
    """Select projected sources for one enabled semantic module without mutating inputs."""

    _validate_projection_fan_in_inputs_identity(projection_fan_in_inputs)

    if not isinstance(semantic_module_id, str) or not semantic_module_id.strip():
        raise ValueError("semantic_module_id must be a non-empty string")
    semantic_module_id = semantic_module_id.strip()

    if enabled_route_semantic_module_ids is not None:
        if isinstance(enabled_route_semantic_module_ids, frozenset):
            enabled_ids = enabled_route_semantic_module_ids
        else:
            enabled_ids = frozenset(enabled_route_semantic_module_ids)
        if semantic_module_id not in enabled_ids:
            known = sorted(enabled_ids)
            raise ValueError(
                f"semantic_module_id {semantic_module_id!r} is not an installed "
                f"Route semantic module; known={known!r}"
            )

    selected: list[ProjectedSource] = []
    unselected: list[ProjectedSource] = []
    projection_input_refs: list[ProjectionInputRef] = []
    for fan_in_input in projection_fan_in_inputs:
        result = fan_in_input.step_result
        contributed = False
        for source in result.projected_sources:
            if source.semantic_module_id == semantic_module_id:
                selected.append(source)
                contributed = True
            else:
                unselected.append(source)
        if contributed:
            projection_input_refs.append(
                ProjectionInputRef(
                    filter_output_projection_bundle_id=(
                        fan_in_input.filter_output_projection_bundle_id
                    ),
                    filter_job_id=result.filter_job_id,
                    zone_key=result.zone_key,
                )
            )

    return SemanticModuleSelectionResult(
        semantic_module_id=semantic_module_id,
        selected_projected_sources=tuple(selected),
        unselected_projected_sources=tuple(unselected),
        projection_input_refs=tuple(projection_input_refs),
    )


def resolve_projection_fan_in_document_identity(
    projection_fan_in_inputs: Sequence[ProjectionFanInInput],
) -> tuple[str, str]:
    """Return the single shared doc_id and file_hash across fan-in inputs."""

    return _validate_projection_fan_in_inputs_identity(projection_fan_in_inputs)


__all__ = [
    "ProjectionFanInInput",
    "ProjectionInputRef",
    "SemanticModuleSelectionResult",
    "build_projection_fan_in_inputs_from_bundles",
    "resolve_projection_fan_in_document_identity",
    "select_projected_sources_for_semantic_module",
]
