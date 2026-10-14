"""Tests for the neutral Filter-output projection Step and contracts."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from operations.filter_output_projection.contracts import (
    RAW_SOURCE_REPRESENTATION_KIND,
    CanonicalSourceRef,
    FilterOutputProjectionInput,
    FilterOutputProjectionStepResult,
    ProjectedSource,
    ResolvedFilterOutputProjectionJob,
    SemanticProjectionOutcome,
)
from steps.project_filter_output import run as run_project_filter_output
from tests.projection_test_helpers import projected_sentence
from tests.test_filter_output_projection_direct import _analysis_bundle_for_zone_match

STEP_PATH = BACKEND_ROOT / "steps" / "project_filter_output.py"

LINEAGE_FILE_HASH = (
    "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
)

OTHER_FILE_HASH = (
    "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
)

FILTER_JOB_ID = "test_filter_job"
ZONE_KEY = "test_zone_zh"
DOC_ID = "doc_test"


def _fixture_projected_source(
    *,
    source_ref: CanonicalSourceRef,
    semantic_module_id: str = "module_alpha",
    lineage: dict[str, str] | None = None,
) -> ProjectedSource:
    block_id = source_ref.refs["block_id"]
    return ProjectedSource(
        semantic_module_id=semantic_module_id,
        source_refs=(source_ref,),
        representation_kind=RAW_SOURCE_REPRESENTATION_KIND,
        sentences=(
            projected_sentence(
                sentence_id=f"{block_id}:S001",
                text="sample semantic text",
                source_block_id=block_id,
            ),
        ),
        lineage=lineage or {"filter_job_id": FILTER_JOB_ID},
        payload={"kind": "paragraph"},
    )


def _minimal_zone_match_bundle(
    *,
    doc_id: str = DOC_ID,
    file_hash: str | None = LINEAGE_FILE_HASH,
    zone_key: str = ZONE_KEY,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "doc_id": doc_id,
        "zone_config_name": zone_key,
        "zone_config_version": "0.2.0",
        "language": "zh",
        "resolved_filter_strategy_id": "heading_zone",
        "matched_zone_count": 1,
        "matched_zones": [
            {
                "zone_id": "Z0001",
                "match": {"match_type": "heading_contains"},
                "blocks": [
                    {
                        "block_id": "C0001",
                        "kind": "paragraph",
                        "analysis_text": "sample semantic text",
                    }
                ],
                "table_blocks": [],
            }
        ],
    }
    if file_hash is not None:
        payload["file_hash"] = file_hash
    return payload


def _analysis_bundle_for_tests(
    zone_match_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = zone_match_bundle or _minimal_zone_match_bundle()
    return _analysis_bundle_for_zone_match(bundle)


def _projection_input(
    *,
    filter_job_id: str = FILTER_JOB_ID,
    doc_id: str = DOC_ID,
    file_hash: str = LINEAGE_FILE_HASH,
    zone_key: str = ZONE_KEY,
    zone_match_bundle: dict[str, Any] | None = None,
) -> FilterOutputProjectionInput:
    return FilterOutputProjectionInput(
        filter_job_id=filter_job_id,
        doc_id=doc_id,
        file_hash=file_hash,
        zone_key=zone_key,
        zone_match_bundle=zone_match_bundle or _minimal_zone_match_bundle(),
    )


def _resolved_job(
    *,
    filter_job_id: str = FILTER_JOB_ID,
    strategy_id: str = "test_strategy",
) -> ResolvedFilterOutputProjectionJob:
    return ResolvedFilterOutputProjectionJob(
        filter_job_id=filter_job_id,
        strategy_id=strategy_id,
        strategy_config={"mode": "fixture"},
    )


class _RecordingFakeFacade:
    def __init__(self, result: FilterOutputProjectionStepResult) -> None:
        self.result = result
        self.calls: list[tuple[FilterOutputProjectionInput, ResolvedFilterOutputProjectionJob]] = []

    def project(
        self,
        *,
        projection_input: FilterOutputProjectionInput,
        job: ResolvedFilterOutputProjectionJob,
    ) -> FilterOutputProjectionStepResult:
        self.calls.append((projection_input, job))
        return self.result


def _step_result_from_input(
    projection_input: FilterOutputProjectionInput,
    *,
    projected_sources: tuple[ProjectedSource, ...] = (),
    semantic_outcomes: tuple[SemanticProjectionOutcome, ...] = (),
) -> FilterOutputProjectionStepResult:
    return FilterOutputProjectionStepResult(
        filter_job_id=projection_input.filter_job_id,
        doc_id=projection_input.doc_id,
        file_hash=projection_input.file_hash,
        zone_key=projection_input.zone_key,
        projected_sources=projected_sources,
        semantic_outcomes=semantic_outcomes,
    )


def test_happy_path_delegates_to_facade_and_preserves_identity() -> None:
    projection_input = _projection_input()
    source_ref = CanonicalSourceRef(
        refs={"block_id": "C0001", "analysis_bundle_id": "prepare_analysis_test"},
    )
    projected_source = _fixture_projected_source(
        source_ref=source_ref,
        lineage={"filter_job_id": FILTER_JOB_ID},
    )
    outcome = SemanticProjectionOutcome(
        semantic_module_id="module_beta",
        source_refs=(source_ref,),
        strategy_result={"status": "classified"},
    )
    facade_result = _step_result_from_input(
        projection_input,
        projected_sources=(projected_source,),
        semantic_outcomes=(outcome,),
    )
    facade = _RecordingFakeFacade(facade_result)

    result = run_project_filter_output(
        projection_input=projection_input,
        analysis_bundle=_analysis_bundle_for_tests(),
        job=_resolved_job(),
        facade=facade,
    )

    assert len(facade.calls) == 1
    received_input = facade.calls[0][0]
    assert received_input.filter_job_id == projection_input.filter_job_id
    assert received_input.doc_id == projection_input.doc_id
    assert len(received_input.projection_sources) == 1
    assert received_input.projection_sources[0].block_id == "C0001"
    assert result is facade_result
    assert result.projected_sources == (projected_source,)
    assert result.semantic_outcomes == (outcome,)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda: (
                _projection_input(filter_job_id="job_a"),
                _resolved_job(filter_job_id="job_b"),
            ),
            "job.filter_job_id must match projection_input.filter_job_id",
        ),
        (
            lambda: (
                _projection_input(
                    doc_id="doc_a",
                    zone_match_bundle=_minimal_zone_match_bundle(doc_id="doc_b"),
                ),
                _resolved_job(),
            ),
            "doc_id must match zone_match_bundle.doc_id",
        ),
        (
            lambda: (
                _projection_input(
                    file_hash=LINEAGE_FILE_HASH,
                    zone_match_bundle=_minimal_zone_match_bundle(
                        file_hash=(
                            "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
                        )
                    ),
                ),
                _resolved_job(),
            ),
            "file_hash must match zone_match_bundle.file_hash",
        ),
        (
            lambda: (
                _projection_input(zone_key="zone_a"),
                _resolved_job(),
            ),
            "zone_key must match zone_match_bundle.zone_config_name",
        ),
    ],
)
def test_invalid_input_identity_rejected(
    mutator: Any,
    match: str,
) -> None:
    projection_input, job = mutator()
    facade = _RecordingFakeFacade(_step_result_from_input(projection_input))
    with pytest.raises(ValueError, match=match):
        run_project_filter_output(
            projection_input=projection_input,
            analysis_bundle=_analysis_bundle_for_tests(
                zone_match_bundle=projection_input.zone_match_bundle
                if hasattr(projection_input.zone_match_bundle, "get")
                else None
            ),
            job=job,
            facade=facade,
        )
    assert facade.calls == []


def test_invalid_strategy_result_identity_rejected() -> None:
    projection_input = _projection_input()
    facade = _RecordingFakeFacade(
        FilterOutputProjectionStepResult(
            filter_job_id="other_job",
            doc_id=projection_input.doc_id,
            file_hash=projection_input.file_hash,
            zone_key=projection_input.zone_key,
        )
    )
    with pytest.raises(ValueError, match="result.filter_job_id"):
        run_project_filter_output(
            projection_input=projection_input,
            analysis_bundle=_analysis_bundle_for_tests(),
            job=_resolved_job(),
            facade=facade,
        )

    facade.result = FilterOutputProjectionStepResult(
        filter_job_id=projection_input.filter_job_id,
        doc_id="doc_other",
        file_hash=projection_input.file_hash,
        zone_key=projection_input.zone_key,
    )
    with pytest.raises(ValueError, match="result.doc_id"):
        run_project_filter_output(
            projection_input=projection_input,
            analysis_bundle=_analysis_bundle_for_tests(),
            job=_resolved_job(),
            facade=facade,
        )

    facade.result = FilterOutputProjectionStepResult(
        filter_job_id=projection_input.filter_job_id,
        doc_id=projection_input.doc_id,
        file_hash=OTHER_FILE_HASH,
        zone_key=projection_input.zone_key,
    )
    with pytest.raises(ValueError, match="result.file_hash"):
        run_project_filter_output(
            projection_input=projection_input,
            analysis_bundle=_analysis_bundle_for_tests(),
            job=_resolved_job(),
            facade=facade,
        )


def test_duplicate_projected_source_identity_rejected() -> None:
    projection_input = _projection_input()
    source_ref = CanonicalSourceRef(
        refs={"block_id": "C0001", "analysis_bundle_id": "prepare_analysis_test"},
    )
    duplicate_source = _fixture_projected_source(source_ref=source_ref, lineage={})
    facade = _RecordingFakeFacade(
        _step_result_from_input(
            projection_input,
            projected_sources=(duplicate_source, duplicate_source),
        )
    )
    with pytest.raises(ValueError, match="duplicate projected source identity"):
        run_project_filter_output(
            projection_input=projection_input,
            analysis_bundle=_analysis_bundle_for_tests(),
            job=_resolved_job(),
            facade=facade,
        )


def test_projected_source_lineage_identity_mismatch_rejected() -> None:
    projection_input = _projection_input()
    source_ref = CanonicalSourceRef(
        refs={"block_id": "C0001", "analysis_bundle_id": "prepare_analysis_test"},
    )
    projected_source = _fixture_projected_source(
        source_ref=source_ref,
        lineage={"doc_id": "doc_other"},
    )
    facade = _RecordingFakeFacade(
        _step_result_from_input(
            projection_input,
            projected_sources=(projected_source,),
        )
    )
    with pytest.raises(ValueError, match="lineage.doc_id"):
        run_project_filter_output(
            projection_input=projection_input,
            analysis_bundle=_analysis_bundle_for_tests(),
            job=_resolved_job(),
            facade=facade,
        )


def test_step_import_boundary_excludes_runtime_route_and_clinical_plugins() -> None:
    tree = ast.parse(STEP_PATH.read_text(encoding="utf-8"), filename=str(STEP_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden_prefixes = (
        "runtime.",
        "scripts.",
        "plugins.clinical_trial_doc.",
    )
    forbidden_modules = {
        "runtime",
        "plugins.clinical_trial_doc",
    }
    for module in imported:
        if module in forbidden_modules:
            pytest.fail(f"project_filter_output step must not import {module!r}")
        for prefix in forbidden_prefixes:
            if module.startswith(prefix):
                pytest.fail(
                    f"project_filter_output step must not import {module!r}"
                )

    assert "core.tagging.providers" not in imported


def test_contract_rejects_canonical_source_ref_without_block_id() -> None:
    with pytest.raises(ValueError, match="block_id"):
        CanonicalSourceRef(refs={"analysis_bundle_id": "prepare_analysis_test"})


def test_step_allows_same_source_with_different_semantic_modules() -> None:
    projection_input = _projection_input()
    shared_ref = CanonicalSourceRef(
        refs={"block_id": "C0001", "analysis_bundle_id": "prepare_analysis_test"},
    )
    facade = _RecordingFakeFacade(
        FilterOutputProjectionStepResult(
            filter_job_id=projection_input.filter_job_id,
            doc_id=projection_input.doc_id,
            file_hash=projection_input.file_hash,
            zone_key=projection_input.zone_key,
            projected_sources=(
                _fixture_projected_source(
                    source_ref=shared_ref,
                    semantic_module_id="module_alpha",
                ),
                _fixture_projected_source(
                    source_ref=shared_ref,
                    semantic_module_id="module_beta",
                ),
            ),
        )
    )

    result = run_project_filter_output(
        projection_input=projection_input,
        analysis_bundle=_analysis_bundle_for_tests(),
        job=_resolved_job(),
        facade=facade,
    )

    assert len(result.projected_sources) == 2


def test_step_accepts_zone_match_bundle_without_optional_file_hash() -> None:
    projection_input = _projection_input(
        zone_match_bundle=_minimal_zone_match_bundle(file_hash=None),
    )
    facade = _RecordingFakeFacade(_step_result_from_input(projection_input))

    result = run_project_filter_output(
        projection_input=projection_input,
        analysis_bundle=_analysis_bundle_for_tests(),
        job=_resolved_job(),
        facade=facade,
    )

    assert result.doc_id == projection_input.doc_id
