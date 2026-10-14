"""Focused tests for projected fan-in primary-coverage residue cleanup."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_phase_harness_installation import (
    resolve_installed_aggregate_evidence_phase_harness_dependencies,
)
from operations.evidence_source_preparation.stage import (
    ProjectionInputRefRecord,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare_harness_resolver import (
    resolve_prepare_harness_inputs,
)
from runtime.run_summaries import build_aggregate_evidence_prepare_run_summary
from tests.test_projected_fan_in_aggregate_prepare_e2e import _build_fan_in_route_artifacts


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _filter_run_summary(*, analysis_bundle_path: Path, project_root: Path) -> dict:
    return {
        "doc_id": "doc_test",
        "inputs": {
            "input_analysis_bundle": analysis_bundle_path.resolve()
            .relative_to(project_root.resolve())
            .as_posix(),
        },
        "outputs": {"coverage_bundle": "coverage_bundle.json"},
    }


def _fan_in_run_summary_inputs(
    tmp_path: Path,
    *,
    coverage_order: tuple[tuple[str, Path], ...],
    projection_order: tuple[ProjectionInputRefRecord, ...],
) -> dict[str, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    for name in (
        "block_manifest.json",
        "doc_meta_bundle.json",
        "analysis_bundle.json",
        "routed_aggregate.json",
        "routing_manifest.json",
        "assessment_input.json",
        "assessment_input_preview.json",
    ):
        (tmp_path / name).write_text("{}", encoding="utf-8")

    filter_job_coverage_refs = tuple(
        {
            "filter_job_id": filter_job_id,
            "coverage_bundle": str(coverage_path),
        }
        for filter_job_id, coverage_path in coverage_order
    )
    projection_input_refs = tuple(
        {
            "filter_job_id": ref.filter_job_id,
            "zone_key": ref.zone_key,
            "filter_output_projection_bundle_id": ref.filter_output_projection_bundle_id,
        }
        for ref in projection_order
    )
    return build_aggregate_evidence_prepare_run_summary(
        run_id="fan_in_prepare_residue_test",
        doc_id="doc_test",
        zone_key="",
        filter_job_coverage_refs=filter_job_coverage_refs,
        projection_input_refs=projection_input_refs,
        block_manifest_path=tmp_path / "block_manifest.json",
        doc_meta_bundle_path=tmp_path / "doc_meta_bundle.json",
        analysis_bundle_path=tmp_path / "analysis_bundle.json",
        routed_aggregate_bundle_path=tmp_path / "routed_aggregate.json",
        routing_manifest_path=tmp_path / "routing_manifest.json",
        assessment_input_path=tmp_path / "assessment_input.json",
        assessment_input_preview_path=tmp_path / "assessment_input_preview.json",
    )["inputs"]


def test_fan_in_run_summary_records_all_contributor_coverage_refs_not_primary_only(
    tmp_path: Path,
) -> None:
    safety_path = tmp_path / "coverage" / "safety.json"
    overview_path = tmp_path / "coverage" / "overview.json"
    safety_path.parent.mkdir(parents=True, exist_ok=True)
    safety_path.write_text("{}", encoding="utf-8")
    overview_path.write_text("{}", encoding="utf-8")

    refs_forward = (
        ProjectionInputRefRecord(
            filter_job_id="ib_clinical_safety",
            zone_key="ib_clinical_safety_zh",
            filter_output_projection_bundle_id="bundle_safety",
        ),
        ProjectionInputRefRecord(
            filter_job_id="ib_overview",
            zone_key="ib_overview_zh",
            filter_output_projection_bundle_id="bundle_overview",
        ),
    )
    refs_reversed = tuple(reversed(refs_forward))

    forward_inputs = _fan_in_run_summary_inputs(
        tmp_path / "forward",
        coverage_order=(
            ("ib_clinical_safety", safety_path),
            ("ib_overview", overview_path),
        ),
        projection_order=refs_forward,
    )
    reversed_inputs = _fan_in_run_summary_inputs(
        tmp_path / "reversed",
        coverage_order=(
            ("ib_overview", overview_path),
            ("ib_clinical_safety", safety_path),
        ),
        projection_order=refs_reversed,
    )

    assert "coverage_bundle" not in forward_inputs
    assert "coverage_bundle" not in reversed_inputs

    forward_coverage = {
        ref["filter_job_id"]: ref["coverage_bundle"]
        for ref in forward_inputs["filter_job_coverage_refs"]
    }
    reversed_coverage = {
        ref["filter_job_id"]: ref["coverage_bundle"]
        for ref in reversed_inputs["filter_job_coverage_refs"]
    }
    assert forward_coverage == reversed_coverage == {
        "ib_clinical_safety": safety_path.as_posix(),
        "ib_overview": overview_path.as_posix(),
    }


def test_single_source_prepare_run_summary_still_records_coverage_bundle(
    tmp_path: Path,
) -> None:
    coverage_path = tmp_path / "coverage_bundle.json"
    coverage_path.write_text("{}", encoding="utf-8")
    for name in (
        "block_manifest.json",
        "doc_meta_bundle.json",
        "analysis_bundle.json",
        "routed_aggregate.json",
        "routing_manifest.json",
        "assessment_input.json",
        "assessment_input_preview.json",
    ):
        (tmp_path / name).write_text("{}", encoding="utf-8")

    summary = build_aggregate_evidence_prepare_run_summary(
        run_id="single_source_prepare_residue_test",
        doc_id="doc_test",
        zone_key="ib_clinical_safety_zh",
        coverage_bundle_path=coverage_path,
        block_manifest_path=tmp_path / "block_manifest.json",
        doc_meta_bundle_path=tmp_path / "doc_meta_bundle.json",
        analysis_bundle_path=tmp_path / "analysis_bundle.json",
        routed_aggregate_bundle_path=tmp_path / "routed_aggregate.json",
        routing_manifest_path=tmp_path / "routing_manifest.json",
        assessment_input_path=tmp_path / "assessment_input.json",
        assessment_input_preview_path=tmp_path / "assessment_input_preview.json",
    )
    assert summary["inputs"]["coverage_bundle"] == coverage_path.as_posix()
    assert "filter_job_coverage_refs" not in summary["inputs"]


def _setup_fan_in_filter_dirs(
    tmp_path: Path,
    artifacts: dict[str, object],
) -> tuple[Path, Path]:
    safety_dir = tmp_path / "filter" / "safety"
    overview_dir = tmp_path / "filter" / "overview"
    for filter_dir, coverage_path in (
        (safety_dir, artifacts["safety_coverage_path"]),
        (overview_dir, artifacts["overview_coverage_path"]),
    ):
        filter_dir.mkdir(parents=True, exist_ok=True)
        _write_json(
            filter_dir / "coverage_bundle.json",
            json.loads(Path(coverage_path).read_text(encoding="utf-8")),
        )
        _write_json(
            filter_dir / "run_summary.json",
            _filter_run_summary(
                analysis_bundle_path=artifacts["analysis_bundle_path"],
                project_root=tmp_path,
            ),
        )
    return safety_dir, overview_dir


def _resolve_fan_in_harness_from_artifacts(
    tmp_path: Path,
    artifacts: dict[str, object],
    *,
    filter_dir_order: tuple[Path, Path],
) -> object:
    routing_manifest = json.loads(
        Path(artifacts["route_result"].routing_manifest_path).read_text(encoding="utf-8")
    )
    resolved, _ = resolve_prepare_harness_inputs(
        routing_manifest=routing_manifest,
        filter_run_dirs=filter_dir_order,
        coverage_bundle=None,
        block_manifest=None,
        doc_meta_bundle_path=None,
        analysis_bundle=None,
        doc_meta_dir=Path(artifacts["doc_meta_bundle_path"]).parent,
        project_root=tmp_path,
    )
    return resolved


def test_fan_in_harness_shared_upstream_is_independent_of_filter_dir_order(
    tmp_path: Path,
) -> None:
    artifacts = _build_fan_in_route_artifacts(tmp_path)
    safety_dir, overview_dir = _setup_fan_in_filter_dirs(tmp_path, artifacts)
    forward = _resolve_fan_in_harness_from_artifacts(
        tmp_path,
        artifacts,
        filter_dir_order=(safety_dir, overview_dir),
    )
    reversed_dirs = _resolve_fan_in_harness_from_artifacts(
        tmp_path,
        artifacts,
        filter_dir_order=(overview_dir, safety_dir),
    )
    assert forward.block_manifest_path == reversed_dirs.block_manifest_path
    assert forward.doc_meta_bundle_path == reversed_dirs.doc_meta_bundle_path
    assert forward.analysis_bundle_path == reversed_dirs.analysis_bundle_path
    assert forward.coverage_bundle_path is None
    assert reversed_dirs.coverage_bundle_path is None
    assert len(forward.filter_job_coverage_refs) == 2
    assert {ref.filter_job_id for ref in forward.filter_job_coverage_refs} == {
        "ib_clinical_safety",
        "ib_overview",
    }


def test_fan_in_harness_rejects_disagreeing_contributor_upstream_paths(
    tmp_path: Path,
) -> None:
    artifacts = _build_fan_in_route_artifacts(tmp_path)
    routing_manifest = json.loads(
        artifacts["route_result"].routing_manifest_path.read_text(encoding="utf-8")
    )
    safety_dir = tmp_path / "filter" / "safety"
    overview_dir = tmp_path / "filter" / "overview"
    safety_dir.mkdir(parents=True)
    overview_dir.mkdir(parents=True)

    safety_coverage = json.loads(artifacts["safety_coverage_path"].read_text(encoding="utf-8"))
    overview_coverage = json.loads(artifacts["overview_coverage_path"].read_text(encoding="utf-8"))
    _write_json(safety_dir / "coverage_bundle.json", safety_coverage)

    alt_analysis = artifacts["analysis_bundle_path"].parent / "alt_analysis_bundle.json"
    _write_json(
        alt_analysis,
        {
            "analysis_bundle_id": "prepare_analysis_alt",
            "doc_id": safety_coverage["doc_id"],
            "file_hash": safety_coverage["file_hash"],
        },
    )
    overview_coverage_alt = dict(overview_coverage)
    overview_coverage_alt["analysis_bundle_ref"] = {
        "analysis_bundle_id": "prepare_analysis_alt",
    }
    _write_json(overview_dir / "coverage_bundle.json", overview_coverage_alt)
    _write_json(
        safety_dir / "run_summary.json",
        _filter_run_summary(analysis_bundle_path=artifacts["analysis_bundle_path"], project_root=tmp_path),
    )
    _write_json(
        overview_dir / "run_summary.json",
        _filter_run_summary(analysis_bundle_path=alt_analysis, project_root=tmp_path),
    )

    with pytest.raises(ValueError, match="disagree on 'analysis_bundle_path'"):
        resolve_prepare_harness_inputs(
            routing_manifest=routing_manifest,
            filter_run_dirs=(safety_dir, overview_dir),
            coverage_bundle=None,
            block_manifest=None,
            doc_meta_bundle_path=None,
            analysis_bundle=None,
            doc_meta_dir=artifacts["doc_meta_bundle_path"].parent,
            project_root=tmp_path,
        )
def test_fan_in_run_prepare_rejects_coverage_bundle_path(
    tmp_path: Path,
) -> None:
    from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare import (
        run_prepare,
    )

    artifacts = _build_fan_in_route_artifacts(tmp_path)
    safety_dir, overview_dir = _setup_fan_in_filter_dirs(tmp_path, artifacts)
    resolved, _ = resolve_prepare_harness_inputs(
        routing_manifest=json.loads(
            artifacts["route_result"].routing_manifest_path.read_text(encoding="utf-8")
        ),
        filter_run_dirs=(safety_dir, overview_dir),
        coverage_bundle=None,
        block_manifest=None,
        doc_meta_bundle_path=None,
        analysis_bundle=None,
        doc_meta_dir=Path(artifacts["doc_meta_bundle_path"]).parent,
        project_root=tmp_path,
    )
    phase_dependencies = resolve_installed_aggregate_evidence_phase_harness_dependencies()
    with pytest.raises(ValueError, match="coverage_bundle_path must be omitted"):
        run_prepare(
            run_prepare_phase=phase_dependencies.run_prepare_phase,
            prepare_semantic=phase_dependencies.semantic_binding.prepare,
            routed_aggregate_bundle_path=artifacts["route_result"].routed_bundle_paths["aggregate"],
            routing_manifest_path=artifacts["route_result"].routing_manifest_path,
            coverage_bundle_path=tmp_path / "should_not_be_used.json",
            block_manifest_path=resolved.block_manifest_path,
            doc_meta_bundle_path=resolved.doc_meta_bundle_path,
            analysis_bundle_path=resolved.analysis_bundle_path,
            output_dir=tmp_path / "prepare_out_reject",
            evidence_form_id="aggregate_evidence",
            projected_coverage_by_filter_job=resolved.projected_coverage_by_filter_job,
            projection_input_refs=resolved.projection_input_refs,
            filter_job_coverage_refs=resolved.filter_job_coverage_refs,
            semantic_module_id="clinical_safety",
        )


def test_fan_in_run_prepare_succeeds_without_primary_coverage_path(
    tmp_path: Path,
) -> None:
    from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare import (
        run_prepare,
    )

    artifacts = _build_fan_in_route_artifacts(tmp_path)
    safety_dir, overview_dir = _setup_fan_in_filter_dirs(tmp_path, artifacts)
    resolved, _ = resolve_prepare_harness_inputs(
        routing_manifest=json.loads(
            artifacts["route_result"].routing_manifest_path.read_text(encoding="utf-8")
        ),
        filter_run_dirs=(overview_dir, safety_dir),
        coverage_bundle=None,
        block_manifest=None,
        doc_meta_bundle_path=None,
        analysis_bundle=None,
        doc_meta_dir=Path(artifacts["doc_meta_bundle_path"]).parent,
        project_root=tmp_path,
    )
    assert resolved.coverage_bundle_path is None
    phase_dependencies = resolve_installed_aggregate_evidence_phase_harness_dependencies()
    result = run_prepare(
        run_prepare_phase=phase_dependencies.run_prepare_phase,
        prepare_semantic=phase_dependencies.semantic_binding.prepare,
        routed_aggregate_bundle_path=artifacts["route_result"].routed_bundle_paths["aggregate"],
        routing_manifest_path=artifacts["route_result"].routing_manifest_path,
        block_manifest_path=resolved.block_manifest_path,
        doc_meta_bundle_path=resolved.doc_meta_bundle_path,
        analysis_bundle_path=resolved.analysis_bundle_path,
        output_dir=tmp_path / "prepare_out_fan_in",
        evidence_form_id="aggregate_evidence",
        projected_coverage_by_filter_job=resolved.projected_coverage_by_filter_job,
        projection_input_refs=resolved.projection_input_refs,
        filter_job_coverage_refs=resolved.filter_job_coverage_refs,
        semantic_module_id="clinical_safety",
    )
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert "coverage_bundle" not in summary.get("inputs", {})
    assert summary["inputs"]["filter_job_coverage_refs"]


def test_single_source_run_prepare_requires_coverage_bundle_path(
    tmp_path: Path,
) -> None:
    from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare import (
        run_prepare,
    )
    from tests.route_runtime_test_helpers import (
        persist_route_artifacts_from_coverage,
        write_upstream_route_fixtures,
    )

    paths = write_upstream_route_fixtures(tmp_path)
    route_result = persist_route_artifacts_from_coverage(
        coverage_bundle_path=paths["coverage"],
        block_manifest_path=paths["block_manifest"],
        doc_meta_bundle_path=paths["doc_meta_bundle"],
        analysis_bundle_path=paths["analysis"],
        output_dir=tmp_path / "route_out",
        run_id="single_source_requires_coverage",
    )
    phase_dependencies = resolve_installed_aggregate_evidence_phase_harness_dependencies()
    with pytest.raises(ValueError, match="coverage_bundle_path is required"):
        run_prepare(
            run_prepare_phase=phase_dependencies.run_prepare_phase,
            prepare_semantic=phase_dependencies.semantic_binding.prepare,
            routed_aggregate_bundle_path=route_result.routed_bundle_paths["aggregate"],
            routing_manifest_path=route_result.routing_manifest_path,
            block_manifest_path=paths["block_manifest"],
            doc_meta_bundle_path=paths["doc_meta_bundle"],
            analysis_bundle_path=paths["analysis"],
            output_dir=tmp_path / "prepare_out_single",
            evidence_form_id="aggregate_evidence",
        )


def test_fan_in_persist_rejects_coverage_bundle_path_with_filter_job_refs(
    tmp_path: Path,
) -> None:
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.execution_types import (
        AggregateEvidencePrepareExecution,
    )
    from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.persistence import (
        persist_prepare_execution,
    )
    from operations.evidence_source_preparation.stage import FilterJobCoverageReference

    execution = AggregateEvidencePrepareExecution(
        assessment_input={"doc_id": "doc_test", "zone_key": ""},
        assessment_runtime_context={"runtime_context_id": "ctx_test", "unit_provenance": {}},
        assessment_input_preview={},
        unit_integrity_report={"status": "pass", "summary": {"error_count": 0}},
        semantic_result={},
        aggregate_unit_count=1,
        doc_id="doc_test",
        zone_key="",
    )
    refs = (
        FilterJobCoverageReference(
            filter_job_id="ib_clinical_safety",
            coverage_bundle_path=tmp_path / "coverage_a.json",
        ),
    )
    for path in (
        tmp_path / "block_manifest.json",
        tmp_path / "doc_meta.json",
        tmp_path / "analysis.json",
        tmp_path / "routed.json",
        tmp_path / "routing_manifest.json",
        tmp_path / "coverage_a.json",
    ):
        path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="coverage_bundle_path must be None"):
        persist_prepare_execution(
            execution=execution,
            output_dir=tmp_path / "persist_out",
            run_id="fan_in_persist_invariant",
            coverage_bundle_path=tmp_path / "coverage_a.json",
            block_manifest_path=tmp_path / "block_manifest.json",
            doc_meta_bundle_path=tmp_path / "doc_meta.json",
            analysis_bundle_path=tmp_path / "analysis.json",
            routed_aggregate_bundle_path=tmp_path / "routed.json",
            routing_manifest_path=tmp_path / "routing_manifest.json",
            filter_job_coverage_refs=refs,
            projection_input_refs=(),
        )
