"""Evidence Source Preparation stage runtime and coverage resolution tests."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SEMANTIC_BINDING,
    INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR,
    INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR,
)
from artifacts.routing.types import ROUTES
from llm.providers.base import LLMRawResult
from operations.evidence_source_preparation.contracts import (
    EvidenceSourcePreparationExecutor,
)
from operations.evidence_source_preparation.coverage_resolution import (
    load_projection_input_refs_from_routing_manifest,
    resolve_projected_coverage_bundles_by_filter_job_id,
    resolve_unique_coverage_bundle_path,
)
from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationExecutionDependencies,
    EvidenceSourcePreparationStageContext,
    EvidenceSourcePreparationStageExecutor,
    EvidenceSourcePreparationStageInput,
    EvidenceSourcePreparationStageResult,
    EvidenceSourcePreparationUpstreamReferences,
    FilterJobCoverageReference,
    ProjectionInputRefRecord,
    RouteStageReference,
    SelectedRouteOutputReference,
)
from operations.projected_source_route.output_contract import resolve_route_unit_count
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.clinical_safety_semantic_binding import (
    CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING,
    CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.input_types import (
    AggregateEvidenceExecutionInput,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    CLINICAL_TRIAL_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR_ID,
    ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies,
    execute_clinical_trial_aggregate_evidence_source_preparation_stage,
)
from runtime.evidence_source_preparation_stage import (
    run_evidence_source_preparation_stage,
)
from runtime.io import load_json
from tests.route_runtime_test_helpers import (
    persist_route_artifacts_from_coverage,
    write_upstream_route_fixtures,
)

STAGE_CONTRACT_PATH = (
    BACKEND_ROOT / "operations/evidence_source_preparation/stage.py"
)
RUNTIME_ADAPTER_PATH = (
    BACKEND_ROOT
    / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/stage.py"
)
APPLICATION_RUNTIME_PATH = (
    BACKEND_ROOT
    / "application/clinical_trial_doc_consistency_qc/evidence_source_preparation_runtime.py"
)


def _selected_route_output_from_route_stage(
    route_stage: RouteStageReference,
) -> SelectedRouteOutputReference:
    for route_output_kind in ROUTES:
        unit_count = resolve_route_unit_count(route_stage.route_counts, route_output_kind)
        if unit_count <= 0:
            continue
        return SelectedRouteOutputReference(
            route_output_kind=route_output_kind,
            unit_count=unit_count,
            routed_bundle_path=route_stage.routed_bundle_paths[route_output_kind],
        )
    raise ValueError("route_stage must include at least one produced route output")


def _build_route_stage(tmp_path: Path) -> tuple[RouteStageReference, Path, dict[str, Path]]:
    paths = write_upstream_route_fixtures(tmp_path)
    route_result = persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=tmp_path / "route_out",
        run_id="esp_stage_route",
    )
    routing_manifest = load_json(route_result.routing_manifest_path)
    routing_manifest.setdefault("source_refs", {})["projection_input_refs"] = [
        {
            "filter_job_id": "ib_clinical_safety",
            "zone_key": "ib_clinical_safety_zh",
            "filter_output_projection_bundle_id": "projection_bundle_test",
        }
    ]
    route_result.routing_manifest_path.write_text(
        __import__("json").dumps(routing_manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    route_stage = RouteStageReference(
        output_dir=route_result.output_dir,
        run_id=route_result.run_id,
        doc_id=route_result.doc_id,
        semantic_module_id="clinical_safety",
        route_counts=dict(route_result.route_counts),
        routed_bundle_paths=dict(route_result.routed_bundle_paths),
        routing_manifest_path=route_result.routing_manifest_path,
    )
    return route_stage, paths["coverage"], paths


def _build_stage_input(
    tmp_path: Path,
    *,
    coverage_path: Path,
    route_stage: RouteStageReference,
    upstream_paths: dict[str, Path],
    filter_job_id: str = "ib_clinical_safety",
) -> EvidenceSourcePreparationStageInput:
    return EvidenceSourcePreparationStageInput(
        route_stage=route_stage,
        projection_input_refs=(
            ProjectionInputRefRecord(
                filter_job_id=filter_job_id,
                zone_key="ib_clinical_safety_zh",
                filter_output_projection_bundle_id="projection_bundle_test",
            ),
        ),
        filter_job_coverage_refs=(
            FilterJobCoverageReference(
                filter_job_id=filter_job_id,
                coverage_bundle_path=coverage_path,
            ),
        ),
        upstream=EvidenceSourcePreparationUpstreamReferences(
            block_manifest_path=upstream_paths["block_manifest"],
            doc_meta_bundle_path=upstream_paths["doc_meta_bundle"],
            analysis_bundle_path=upstream_paths["analysis"],
        ),
        context=EvidenceSourcePreparationStageContext(
            output_dir=tmp_path / "esp_out",
            run_id="esp_stage_test",
        ),
        execution_dependencies=(
            ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies(
                llm_mode="mock",
            )
        ),
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        selected_route_output=_selected_route_output_from_route_stage(route_stage),
    )


def test_neutral_stage_contract_has_no_aggregate_types() -> None:
    source = STAGE_CONTRACT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(STAGE_CONTRACT_PATH))
    imported: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    for forbidden in (
        "AggregateEvidenceExecutionInput",
        "AggregateEvidenceExecution",
        "plugins.clinical_trial_doc",
        "steps",
        "runtime.",
    ):
        assert forbidden not in source
    assert imported <= {"__future__", "collections.abc", "dataclasses", "pathlib", "typing"}


class _SyntheticStageExecutor:
    def __call__(
        self,
        *,
        stage_input: EvidenceSourcePreparationStageInput,
    ) -> EvidenceSourcePreparationStageResult:
        return EvidenceSourcePreparationStageResult(
            output_dir=stage_input.context.output_dir,
            run_id=stage_input.context.run_id or "synthetic_run",
            doc_id=stage_input.route_stage.doc_id,
            semantic_module_id=stage_input.route_stage.semantic_module_id,
            stage_executor_id="synthetic.executor",
            declared_output_path=stage_input.context.output_dir / "output.json",
            run_summary_path=stage_input.context.output_dir / "run_summary.json",
        )


def test_synthetic_stage_executor_satisfies_neutral_contract(tmp_path: Path) -> None:
    route_stage, coverage_path, upstream_paths = _build_route_stage(tmp_path)
    stage_input = _build_stage_input(
        tmp_path,
        coverage_path=coverage_path,
        route_stage=route_stage,
        upstream_paths=upstream_paths,
    )
    result = run_evidence_source_preparation_stage(
        stage_input=stage_input,
        stage_executor=_SyntheticStageExecutor(),
    )
    assert isinstance(result, EvidenceSourcePreparationStageResult)
    assert result.stage_executor_id == "synthetic.executor"


def test_resolve_unique_coverage_from_route_provenance(tmp_path: Path) -> None:
    coverage_a = tmp_path / "coverage_a.json"
    coverage_b = tmp_path / "coverage_b.json"
    coverage_a.write_text("{}", encoding="utf-8")
    coverage_b.write_text("{}", encoding="utf-8")
    refs = (
        ProjectionInputRefRecord(
            filter_job_id="job_a",
            zone_key="zone_a",
            filter_output_projection_bundle_id="bundle_a",
        ),
        ProjectionInputRefRecord(
            filter_job_id="job_a",
            zone_key="zone_a",
            filter_output_projection_bundle_id="bundle_a_dup",
        ),
    )
    resolved = resolve_unique_coverage_bundle_path(
        projection_input_refs=refs,
        filter_job_coverage_refs=(
            FilterJobCoverageReference(
                filter_job_id="job_a",
                coverage_bundle_path=coverage_a,
            ),
        ),
    )
    assert resolved == coverage_a.resolve()


def test_resolve_unique_coverage_deduplicates_same_source(tmp_path: Path) -> None:
    coverage = tmp_path / "coverage.json"
    coverage.write_text("{}", encoding="utf-8")
    refs = (
        ProjectionInputRefRecord(
            filter_job_id="job_a",
            zone_key="zone_a",
            filter_output_projection_bundle_id="bundle_a",
        ),
        ProjectionInputRefRecord(
            filter_job_id="job_b",
            zone_key="zone_b",
            filter_output_projection_bundle_id="bundle_b",
        ),
    )
    resolved = resolve_unique_coverage_bundle_path(
        projection_input_refs=refs,
        filter_job_coverage_refs=(
            FilterJobCoverageReference(
                filter_job_id="job_a",
                coverage_bundle_path=coverage,
            ),
            FilterJobCoverageReference(
                filter_job_id="job_b",
                coverage_bundle_path=coverage,
            ),
        ),
    )
    assert resolved == coverage.resolve()


def test_resolve_unique_coverage_fails_when_missing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing coverage_bundle_path"):
        resolve_unique_coverage_bundle_path(
            projection_input_refs=(
                ProjectionInputRefRecord(
                    filter_job_id="missing_job",
                    zone_key="zone",
                    filter_output_projection_bundle_id="bundle",
                ),
            ),
            filter_job_coverage_refs=(),
        )


def test_resolve_projected_coverage_bundles_multiple_sources(tmp_path: Path) -> None:
    coverage_a = tmp_path / "coverage_a.json"
    coverage_b = tmp_path / "coverage_b.json"
    coverage_a.write_text("{}", encoding="utf-8")
    coverage_b.write_text("{}", encoding="utf-8")
    refs = (
        ProjectionInputRefRecord(
            filter_job_id="job_a",
            zone_key="zone_a",
            filter_output_projection_bundle_id="bundle_a",
        ),
        ProjectionInputRefRecord(
            filter_job_id="job_b",
            zone_key="zone_b",
            filter_output_projection_bundle_id="bundle_b",
        ),
    )
    resolution = resolve_projected_coverage_bundles_by_filter_job_id(
        projection_input_refs=refs,
        filter_job_coverage_refs=(
            FilterJobCoverageReference(
                filter_job_id="job_a",
                coverage_bundle_path=coverage_a,
            ),
            FilterJobCoverageReference(
                filter_job_id="job_b",
                coverage_bundle_path=coverage_b,
            ),
        ),
    )
    assert resolution.ordered_filter_job_ids == ("job_a", "job_b")
    assert resolution.paths_by_filter_job_id["job_a"] == coverage_a.resolve()
    assert resolution.paths_by_filter_job_id["job_b"] == coverage_b.resolve()


def test_resolve_projected_coverage_rejects_ambiguous_filter_job_mapping(
    tmp_path: Path,
) -> None:
    coverage_a = tmp_path / "coverage_a.json"
    coverage_b = tmp_path / "coverage_b.json"
    coverage_a.write_text("{}", encoding="utf-8")
    coverage_b.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="ambiguous coverage_bundle_path"):
        resolve_projected_coverage_bundles_by_filter_job_id(
            projection_input_refs=(
                ProjectionInputRefRecord(
                    filter_job_id="job_a",
                    zone_key="zone_a",
                    filter_output_projection_bundle_id="bundle_a",
                ),
            ),
            filter_job_coverage_refs=(
                FilterJobCoverageReference(
                    filter_job_id="job_a",
                    coverage_bundle_path=coverage_a,
                ),
                FilterJobCoverageReference(
                    filter_job_id="job_a",
                    coverage_bundle_path=coverage_b,
                ),
            ),
        )


def test_resolve_unique_coverage_fails_when_multiple_distinct_sources(
    tmp_path: Path,
) -> None:
    coverage_a = tmp_path / "coverage_a.json"
    coverage_b = tmp_path / "coverage_b.json"
    coverage_a.write_text("{}", encoding="utf-8")
    coverage_b.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="multiple distinct coverage_bundle_path"):
        resolve_unique_coverage_bundle_path(
            projection_input_refs=(
                ProjectionInputRefRecord(
                    filter_job_id="job_a",
                    zone_key="zone_a",
                    filter_output_projection_bundle_id="bundle_a",
                ),
                ProjectionInputRefRecord(
                    filter_job_id="job_b",
                    zone_key="zone_b",
                    filter_output_projection_bundle_id="bundle_b",
                ),
            ),
            filter_job_coverage_refs=(
                FilterJobCoverageReference(
                    filter_job_id="job_a",
                    coverage_bundle_path=coverage_a,
                ),
                FilterJobCoverageReference(
                    filter_job_id="job_b",
                    coverage_bundle_path=coverage_b,
                ),
            ),
        )


def test_load_projection_input_refs_from_routing_manifest() -> None:
    refs = load_projection_input_refs_from_routing_manifest(
        {
            "source_refs": {
                "projection_input_refs": [
                    {
                        "filter_job_id": "ib_clinical_safety",
                        "zone_key": "ib_clinical_safety_zh",
                        "filter_output_projection_bundle_id": "bundle_1",
                    }
                ]
            }
        }
    )
    assert refs[0].filter_job_id == "ib_clinical_safety"


def test_installed_stage_executor_runs_canonical_path(tmp_path: Path) -> None:
    route_stage, coverage_path, upstream_paths = _build_route_stage(tmp_path)
    stage_input = _build_stage_input(
        tmp_path,
        coverage_path=coverage_path,
        route_stage=route_stage,
        upstream_paths=upstream_paths,
    )
    captured: dict[str, Any] = {}
    original_run = __import__(
        "steps.evidence_source_preparation",
        fromlist=["run_evidence_source_preparation"],
    ).run_evidence_source_preparation

    def _recording_run(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return original_run(**kwargs)

    with patch(
        "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stage.esp_step.run_evidence_source_preparation",
        side_effect=_recording_run,
    ):
        result = run_evidence_source_preparation_stage(
            stage_input=stage_input,
            stage_executor=(
                INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR
            ),
        )

    assert captured["executor"] is (
        INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR
    )
    assert isinstance(captured["invocation"], AggregateEvidenceExecutionInput)
    assert captured["invocation"].route_artifacts.route_counts == route_stage.route_counts
    assert captured["invocation"].evidence_form_id == AGGREGATE_EVIDENCE_FORM_ID
    assert result.declared_output_path.is_file()
    assert result.run_summary_path.is_file()
    assert not hasattr(result, "prepare")
    assert not hasattr(result, "assess")


def test_stage_runtime_persists_outputs_without_pipeline_or_plugin_io(
    tmp_path: Path,
) -> None:
    route_stage, coverage_path, upstream_paths = _build_route_stage(tmp_path)
    stage_input = _build_stage_input(
        tmp_path,
        coverage_path=coverage_path,
        route_stage=route_stage,
        upstream_paths=upstream_paths,
    )
    result = run_evidence_source_preparation_stage(
        stage_input=stage_input,
        stage_executor=(
            INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR
        ),
    )
    output_dir = result.output_dir
    assert (output_dir / "assessment_input.json").is_file()
    assert (output_dir / "scope_assessments.json").is_file()
    assert (output_dir / "heading_scope_eligibility.json").is_file()
    assert result.declared_output_path.name == "aggregate_evidence_source_bundle.json"
    bundle = load_json(result.declared_output_path)
    assert bundle["artifact_type"] == "aggregate_evidence_source_bundle"


def test_clinical_safety_is_explicitly_installed_not_default_singleton() -> None:
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SEMANTIC_BINDING
        is CLINICAL_SAFETY_AGGREGATE_SEMANTIC_BINDING
    )
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SEMANTIC_BINDING.prepare
        is CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING
    )


def test_application_has_no_production_esp_stage_runtime_module() -> None:
    assert not APPLICATION_RUNTIME_PATH.is_file()


def test_stage_runtime_does_not_use_sequence_module() -> None:
    source = RUNTIME_ADAPTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(RUNTIME_ADAPTER_PATH))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "sequence" not in source
    assert not any("sequence" in module for module in imported if module)
    assert "run_pre_assemble_sequence" not in source
    assert "RouteArtifactsRef" not in source
    assert 'routed_bundle_paths["aggregate"]' not in source
    assert "evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID" not in source


def test_stage_runtime_loads_route_artifacts_from_explicit_handoff_refs(
    tmp_path: Path,
) -> None:
    route_stage, coverage_path, upstream_paths = _build_route_stage(tmp_path)
    stage_input = _build_stage_input(
        tmp_path,
        coverage_path=coverage_path,
        route_stage=route_stage,
        upstream_paths=upstream_paths,
    )
    captured: dict[str, Any] = {}

    def _recording_loader(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        captured.update(kwargs)
        return load_json(kwargs["selected_route_bundle_path"]), load_json(
            kwargs["routing_manifest_path"]
        )

    with patch(
        "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stage.load_route_artifact_set",
        side_effect=_recording_loader,
    ), patch(
        "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stage.esp_step.run_evidence_source_preparation",
        side_effect=AssertionError("pipeline should not run in loader contract test"),
    ):
        with pytest.raises(AssertionError, match="pipeline should not run"):
            execute_clinical_trial_aggregate_evidence_source_preparation_stage(
                stage_input=stage_input,
                evidence_source_preparation_executor=INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR,
            )

    assert captured["selected_route_bundle_path"] == (
        stage_input.selected_route_output.routed_bundle_path.resolve()
    )
    assert captured["routing_manifest_path"] == (
        stage_input.route_stage.routing_manifest_path.resolve()
    )
    assert "sibling_route_bundle_paths" not in captured


def test_stage_runtime_runs_without_sibling_route_bundle_files(tmp_path: Path) -> None:
    route_stage, coverage_path, upstream_paths = _build_route_stage(tmp_path)
    for route in ("table", "case", "unknown"):
        sibling_path = route_stage.routed_bundle_paths[route]
        if sibling_path.is_file():
            sibling_path.unlink()

    stage_input = _build_stage_input(
        tmp_path,
        coverage_path=coverage_path,
        route_stage=route_stage,
        upstream_paths=upstream_paths,
    )
    result = run_evidence_source_preparation_stage(
        stage_input=stage_input,
        stage_executor=(
            INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR
        ),
    )
    assert result.declared_output_path.is_file()
    assert result.run_summary_path.is_file()


def test_stage_runtime_does_not_discover_route_artifacts_from_parent_dir() -> None:
    source = RUNTIME_ADAPTER_PATH.read_text(encoding="utf-8")
    assert ".parent" not in source
    assert "ROUTING_MANIFEST_FILENAME" not in source
    assert "ROUTED_UNITS_ROUTE_FILENAMES" not in source
    assert "sibling_bundles" not in source
    assert "sibling_route_bundle_paths" not in source


def test_aggregate_esp_production_has_no_sibling_contract_consumers() -> None:
    production_paths = (
        BACKEND_ROOT
        / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/prepare.py",
        BACKEND_ROOT
        / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/stage.py",
        BACKEND_ROOT
        / "plugins/clinical_trial_doc/evidence_source_preparation/clinical_safety/aggregate_evidence/input_types.py",
        BACKEND_ROOT
        / "plugins/clinical_trial_doc/evidence_source_preparation/clinical_safety/aggregate_evidence/executor.py",
        BACKEND_ROOT
        / "plugins/clinical_trial_doc/evidence_source_preparation/clinical_safety/aggregate_evidence/phase_facade.py",
    )
    forbidden = ("sibling_bundles", "sibling_route_bundle_paths")
    for path in production_paths:
        assert path.is_file(), f"missing production module: {path}"
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{path.name} must not reference {token!r}"


def test_stage_runtime_calls_pipeline_exactly_once(tmp_path: Path) -> None:
    route_stage, coverage_path, upstream_paths = _build_route_stage(tmp_path)
    stage_input = _build_stage_input(
        tmp_path,
        coverage_path=coverage_path,
        route_stage=route_stage,
        upstream_paths=upstream_paths,
    )
    call_count = {"count": 0}
    original_run = __import__(
        "steps.evidence_source_preparation",
        fromlist=["run_evidence_source_preparation"],
    ).run_evidence_source_preparation

    def _counting_run(**kwargs: Any) -> Any:
        call_count["count"] += 1
        return original_run(**kwargs)

    with patch(
        "runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stage.esp_step.run_evidence_source_preparation",
        side_effect=_counting_run,
    ):
        run_evidence_source_preparation_stage(
            stage_input=stage_input,
            stage_executor=(
                INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR
            ),
        )
    assert call_count["count"] == 1


class _FailingApiProvider:
    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        raise TimeoutError("scope assessment timed out")


@pytest.mark.parametrize("transport_retry", [False, True])
def test_stage_provider_failure_persists_invocation_before_reraising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transport_retry: bool,
) -> None:
    from tests.test_bailian_transient_retry import provider, timeout
    import openai

    failing_provider = _FailingApiProvider()
    expected_error = TimeoutError
    expected_message = "scope assessment timed out"
    if transport_retry:
        failing_provider, create, _ = provider(monkeypatch, [timeout(), timeout()])
        ticks = iter([0., 300., 300., 600.])
        monkeypatch.setattr("llm.invocation.perf_counter", lambda: next(ticks))
        expected_error = openai.APITimeoutError
        expected_message = "Request timed out"
    route_stage, coverage_path, upstream_paths = _build_route_stage(tmp_path)
    stage_input = _build_stage_input(
        tmp_path,
        coverage_path=coverage_path,
        route_stage=route_stage,
        upstream_paths=upstream_paths,
    )
    stage_input = replace(
        stage_input,
        execution_dependencies=(
            ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies(
                llm_mode="api",
                llm_profile="qwen3_7_plus_2026_05_26",
                provider=failing_provider,
                llm_execution_config={
                    "config_id": "clinical_trial_doc_esp_aggregate",
                    "profile_id": "qwen3_7_plus_2026_05_26",
                },
            )
        ),
    )

    with pytest.raises(expected_error, match=expected_message):
        run_evidence_source_preparation_stage(
            stage_input=stage_input,
            stage_executor=(
                INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR
            ),
        )

    summary = load_json(stage_input.context.output_dir / "run_summary.json")
    assert summary["status"] == "failed"
    if transport_retry:
        assert create.call_count == 2
        assert [r["attempt_index"] for r in summary["llm_invocations"]] == [1, 2]
        assert [r["elapsed_ms"] for r in summary["llm_invocations"]] == [300000, 300000]
        assert [r["error_type"] for r in summary["llm_invocations"]] == ["APITimeoutError"] * 2
        assert [r["status"] for r in summary["llm_invocations"]] == ["failed"] * 2
        return
    invocation = summary["llm_invocations"][0]
    assert invocation["status"] == "failed"
    assert invocation["error_type"] == "TimeoutError"
    assert invocation["error_message"] == "scope assessment timed out"
    assert isinstance(invocation["elapsed_ms"], int)


def test_stage_result_contract_is_neutral(tmp_path: Path) -> None:
    route_stage, coverage_path, upstream_paths = _build_route_stage(tmp_path)
    stage_input = _build_stage_input(
        tmp_path,
        coverage_path=coverage_path,
        route_stage=route_stage,
        upstream_paths=upstream_paths,
    )
    result = run_evidence_source_preparation_stage(
        stage_input=stage_input,
        stage_executor=(
            INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR
        ),
    )
    assert isinstance(result, EvidenceSourcePreparationStageResult)
    assert result.stage_executor_id == (
        CLINICAL_TRIAL_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR_ID
    )
    assert result.semantic_module_id == "clinical_safety"


def test_clinical_safety_behavior_unchanged_through_stage_runtime(tmp_path: Path) -> None:
    route_stage, coverage_path, upstream_paths = _build_route_stage(tmp_path)
    stage_input = _build_stage_input(
        tmp_path,
        coverage_path=coverage_path,
        route_stage=route_stage,
        upstream_paths=upstream_paths,
    )
    result = run_evidence_source_preparation_stage(
        stage_input=stage_input,
        stage_executor=(
            INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR
        ),
    )
    assessment_input = load_json(result.output_dir / "assessment_input.json")
    assert (
        assessment_input["assessment_profile_ref"]
        == CLINICAL_SAFETY_AGGREGATE_PREPARE_SEMANTIC_BINDING.assessment_profile_ref
    )


def test_installed_stage_executor_is_protocol_instance() -> None:
    assert isinstance(
        INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR,
        EvidenceSourcePreparationStageExecutor,
    )
    assert isinstance(
        INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR,
        EvidenceSourcePreparationExecutor,
    )


def test_stage_runtime_rejects_non_clinical_execution_dependencies(
    tmp_path: Path,
) -> None:
    route_stage, coverage_path, upstream_paths = _build_route_stage(tmp_path)

    @dataclass
    class _BadDependencies(EvidenceSourcePreparationExecutionDependencies):
        token: str = "bad"

    stage_input = EvidenceSourcePreparationStageInput(
        route_stage=route_stage,
        projection_input_refs=(
            ProjectionInputRefRecord(
                filter_job_id="ib_clinical_safety",
                zone_key="ib_clinical_safety_zh",
                filter_output_projection_bundle_id="projection_bundle_test",
            ),
        ),
        filter_job_coverage_refs=(
            FilterJobCoverageReference(
                filter_job_id="ib_clinical_safety",
                coverage_bundle_path=coverage_path,
            ),
        ),
        upstream=EvidenceSourcePreparationUpstreamReferences(
            block_manifest_path=upstream_paths["block_manifest"],
            doc_meta_bundle_path=upstream_paths["doc_meta_bundle"],
            analysis_bundle_path=upstream_paths["analysis"],
        ),
        context=EvidenceSourcePreparationStageContext(
            output_dir=tmp_path / "esp_out",
        ),
        execution_dependencies=_BadDependencies(),
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
        selected_route_output=_selected_route_output_from_route_stage(route_stage),
    )
    with pytest.raises(TypeError, match="ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies"):
        execute_clinical_trial_aggregate_evidence_source_preparation_stage(
            stage_input=stage_input,
            evidence_source_preparation_executor=(
                INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_EXECUTOR
            ),
        )
