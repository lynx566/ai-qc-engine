"""Canonical Filter-output projection step: pure in-memory orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from artifacts.prepare_analysis import validate_analysis_bundle
from artifacts.zone_match_bundle import assert_zone_match_bundle_safe
from core.document.doc_identity import validate_file_hash_format
from operations.filter_output_projection.contracts import (
    CanonicalSourceRef,
    FilterOutputProjectionFacade,
    FilterOutputProjectionInput,
    FilterOutputProjectionStepResult,
    ProjectedSource,
    ResolvedFilterOutputProjectionJob,
    SemanticProjectionOutcome,
)
from operations.filter_output_projection.projected_sentence import (
    validate_projected_source_sentences,
)
from operations.filter_output_projection.source_materialization import (
    materialize_projection_sources,
)

_LINEAGE_IDENTITY_KEYS = frozenset({"doc_id", "file_hash"})


def _canonical_ref_identity(ref: CanonicalSourceRef) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in ref.refs.items()))


def _source_refs_identity(
    source_refs: tuple[CanonicalSourceRef, ...],
) -> tuple[tuple[tuple[str, str], ...], ...]:
    return tuple(_canonical_ref_identity(ref) for ref in source_refs)


def _projected_source_identity(source: ProjectedSource) -> tuple[Any, ...]:
    return (source.semantic_module_id, _source_refs_identity(source.source_refs))


def _semantic_outcome_identity(outcome: SemanticProjectionOutcome) -> tuple[Any, ...]:
    return (outcome.semantic_module_id, _source_refs_identity(outcome.source_refs))


def _validate_projection_input_identity(
    projection_input: FilterOutputProjectionInput,
) -> str:
    normalized_file_hash = validate_file_hash_format(
        projection_input.file_hash,
        field="file_hash",
    )
    bundle = projection_input.zone_match_bundle
    assert_zone_match_bundle_safe(dict(bundle))

    zone_config_name = bundle.get("zone_config_name")
    if zone_config_name != projection_input.zone_key:
        raise ValueError(
            "zone_key must match zone_match_bundle.zone_config_name"
        )

    bundle_doc_id = bundle.get("doc_id")
    if bundle_doc_id is not None and str(bundle_doc_id) != projection_input.doc_id:
        raise ValueError("doc_id must match zone_match_bundle.doc_id")

    bundle_file_hash = bundle.get("file_hash")
    if (
        isinstance(bundle_file_hash, str)
        and bundle_file_hash.strip()
        and bundle_file_hash.strip() != normalized_file_hash
    ):
        raise ValueError("file_hash must match zone_match_bundle.file_hash")

    return normalized_file_hash


def _validate_analysis_bundle_identity(
    analysis_bundle: Mapping[str, Any],
    *,
    doc_id: str,
    file_hash: str,
) -> None:
    validate_analysis_bundle(analysis_bundle)

    bundle_doc_id = analysis_bundle.get("doc_id")
    if bundle_doc_id is not None and str(bundle_doc_id) != doc_id:
        raise ValueError("doc_id must match analysis_bundle.doc_id")

    bundle_file_hash = analysis_bundle.get("file_hash")
    if (
        isinstance(bundle_file_hash, str)
        and bundle_file_hash.strip()
        and bundle_file_hash.strip() != file_hash
    ):
        raise ValueError("file_hash must match analysis_bundle.file_hash")


def _with_materialized_projection_sources(
    projection_input: FilterOutputProjectionInput,
    *,
    analysis_bundle: Mapping[str, Any],
) -> FilterOutputProjectionInput:
    projection_sources = materialize_projection_sources(
        zone_match_bundle=projection_input.zone_match_bundle,
        analysis_bundle=analysis_bundle,
    )
    return FilterOutputProjectionInput(
        filter_job_id=projection_input.filter_job_id,
        doc_id=projection_input.doc_id,
        file_hash=projection_input.file_hash,
        zone_key=projection_input.zone_key,
        zone_match_bundle=projection_input.zone_match_bundle,
        projection_sources=projection_sources,
    )


def _validate_resolved_job_matches_input(
    *,
    projection_input: FilterOutputProjectionInput,
    job: ResolvedFilterOutputProjectionJob,
) -> None:
    if job.filter_job_id != projection_input.filter_job_id:
        raise ValueError(
            "job.filter_job_id must match projection_input.filter_job_id"
        )


def _validate_lineage_identity(
    lineage: Mapping[str, str],
    *,
    doc_id: str,
    file_hash: str,
    label: str,
) -> None:
    lineage_doc_id = lineage.get("doc_id")
    if lineage_doc_id is not None and str(lineage_doc_id) != doc_id:
        raise ValueError(f"{label}.lineage.doc_id must match projection doc_id")
    lineage_file_hash = lineage.get("file_hash")
    if lineage_file_hash is not None and str(lineage_file_hash) != file_hash:
        raise ValueError(f"{label}.lineage.file_hash must match projection file_hash")


def _validate_projected_source_lineage(
    source: ProjectedSource,
    *,
    doc_id: str,
    file_hash: str,
    index: int,
) -> None:
    _validate_lineage_identity(
        source.lineage,
        doc_id=doc_id,
        file_hash=file_hash,
        label=f"projected_sources[{index}]",
    )


def _reject_duplicate_identities(
    identities: list[tuple[Any, ...]],
    *,
    label: str,
) -> None:
    seen: set[tuple[Any, ...]] = set()
    for index, identity in enumerate(identities):
        if identity in seen:
            raise ValueError(f"duplicate {label} identity at index {index}")
        seen.add(identity)


def _validate_projection_step_result(
    result: FilterOutputProjectionStepResult,
    *,
    projection_input: FilterOutputProjectionInput,
    normalized_file_hash: str,
) -> None:
    if result.filter_job_id != projection_input.filter_job_id:
        raise ValueError(
            "result.filter_job_id must match projection_input.filter_job_id"
        )
    if result.doc_id != projection_input.doc_id:
        raise ValueError("result.doc_id must match projection_input.doc_id")
    if result.file_hash != normalized_file_hash:
        raise ValueError("result.file_hash must match projection_input.file_hash")
    if result.zone_key != projection_input.zone_key:
        raise ValueError("result.zone_key must match projection_input.zone_key")

    projected_identities = [
        _projected_source_identity(source)
        for source in result.projected_sources
    ]
    _reject_duplicate_identities(
        projected_identities,
        label="projected source",
    )

    outcome_identities = [
        _semantic_outcome_identity(outcome)
        for outcome in result.semantic_outcomes
    ]
    _reject_duplicate_identities(
        outcome_identities,
        label="semantic outcome",
    )

    for index, source in enumerate(result.projected_sources):
        _validate_projected_source_lineage(
            source,
            doc_id=projection_input.doc_id,
            file_hash=normalized_file_hash,
            index=index,
        )
        validate_projected_source_sentences(
            source,
            label=f"projected_sources[{index}]",
        )

    for index, outcome in enumerate(result.semantic_outcomes):
        for ref_index, ref in enumerate(outcome.source_refs):
            ref_lineage = {
                key: value
                for key, value in ref.refs.items()
                if key in _LINEAGE_IDENTITY_KEYS
            }
            if not ref_lineage:
                continue
            _validate_lineage_identity(
                ref_lineage,
                doc_id=projection_input.doc_id,
                file_hash=normalized_file_hash,
                label=f"semantic_outcomes[{index}].source_refs[{ref_index}]",
            )


def run(
    *,
    projection_input: FilterOutputProjectionInput,
    analysis_bundle: Mapping[str, Any],
    job: ResolvedFilterOutputProjectionJob,
    facade: FilterOutputProjectionFacade,
) -> FilterOutputProjectionStepResult:
    """Validate input, materialize sources, delegate to facade, validate result."""
    _validate_resolved_job_matches_input(
        projection_input=projection_input,
        job=job,
    )
    normalized_file_hash = _validate_projection_input_identity(projection_input)
    _validate_analysis_bundle_identity(
        analysis_bundle,
        doc_id=projection_input.doc_id,
        file_hash=normalized_file_hash,
    )
    materialized_input = _with_materialized_projection_sources(
        projection_input,
        analysis_bundle=analysis_bundle,
    )

    result = facade.project(
        projection_input=materialized_input,
        job=job,
    )
    if not isinstance(result, FilterOutputProjectionStepResult):
        raise TypeError(
            "facade.project must return a FilterOutputProjectionStepResult"
        )

    validate_file_hash_format(result.file_hash, field="file_hash")
    _validate_projection_step_result(
        result,
        projection_input=materialized_input,
        normalized_file_hash=normalized_file_hash,
    )
    return result


__all__ = ["run"]
