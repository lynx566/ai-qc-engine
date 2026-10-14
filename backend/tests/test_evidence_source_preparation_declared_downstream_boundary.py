"""Declared downstream artifact boundary guards for Evidence Source Preparation (Slice D)."""

from __future__ import annotations

import ast
import importlib
import sys
from dataclasses import fields
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR,
)
from artifacts.document_consistency_qc_flow_run_summary import (
    _ROUTE_SEMANTIC_MODULE_OPTIONAL_KEYS,
    _ROUTE_SEMANTIC_MODULE_REQUIRED_KEYS,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME,
    AGGREGATE_EVIDENCE_SOURCE_BUNDLE_ARTIFACT_TYPE,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_PHASE,
)
from execution_flow.document_consistency_qc.execution_provenance import (
    FlowRunRouteSemanticModuleProvenance,
)
from operations.evidence_source_preparation.stage import EvidenceSourcePreparationStageResult
from runtime.evidence_source_preparation_stage import run_evidence_source_preparation_stage
from runtime.io import load_json
from tests.test_evidence_source_preparation_stage_runtime import (
    _build_route_stage,
    _build_stage_input,
)

ARTIFACTS_ROOT = BACKEND_ROOT / "artifacts"
ESP_ARTIFACTS_ROOT = ARTIFACTS_ROOT / "evidence_source_preparation"
OLD_PROCESS_ARTIFACTS_ROOT = ARTIFACTS_ROOT / "process"

STAGE_RESULT_ALLOWED_FIELDS = frozenset(
    {
        "output_dir",
        "run_id",
        "doc_id",
        "semantic_module_id",
        "stage_executor_id",
        "declared_output_path",
        "run_summary_path",
    }
)

ESP_FLOW_PROVENANCE_ALLOWED_KEYS = frozenset(
    {
        "semantic_module_id",
        "selected_projected_source_count",
        "route_invoked",
        "route_run_id",
        "output_dir",
        "routing_manifest_path",
        "run_summary_path",
        "evidence_source_preparation_invoked",
        "evidence_source_preparation_run_id",
        "evidence_source_preparation_stage_executor_id",
        "evidence_source_preparation_declared_output_path",
        "evidence_source_preparation_run_summary_path",
    }
)

FORBIDDEN_INTERNAL_DOWNSTREAM_TOKENS = (
    "assessment_input",
    "scope_assessments",
    "heading_scope_eligibility",
    "scope_assessment_review",
    "scope_assessment_trace",
    "pre_llm_review_state",
    "assessment_runtime_context",
)

UNIFIED_RUN_SUMMARY_FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "assessment_input",
        "assessment_input_preview",
        "assessment_runtime_context",
        "scope_assessments",
        "scope_assessment_review",
        "scope_assessment_trace",
        "heading_scope_eligibility",
        "pre_llm_review_state",
        "pre_llm_review_bundle",
        "pre_llm_audit_bundle_private",
        "unit_integrity_report",
    }
)


def test_esp_artifact_package_ownership_on_disk() -> None:
    assert ESP_ARTIFACTS_ROOT.is_dir()
    assert not OLD_PROCESS_ARTIFACTS_ROOT.exists()
    root_py_files = sorted(
        path.name
        for path in ESP_ARTIFACTS_ROOT.iterdir()
        if path.is_file() and path.suffix == ".py"
    )
    assert root_py_files == ["__init__.py", "schema.py"]
    concrete_root = (
        ESP_ARTIFACTS_ROOT
        / "clinical_trial_doc"
        / "clinical_safety"
        / "aggregate_evidence"
    )
    for rel in (
        "__init__.py",
        "schema.py",
        "aggregate_evidence_source_bundle.py",
        "assessment_input.py",
        "assessment_input_compact.py",
        "heading_scope_eligibility.py",
        "scope_assessment_review.py",
        "scope_assessment_enums.py",
        "scope_assessments.py",
    ):
        assert (concrete_root / rel).is_file(), rel


def test_old_process_artifacts_package_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("artifacts.process")


def test_stage_result_exposes_only_declared_output_contract_fields() -> None:
    actual = {field.name for field in fields(EvidenceSourcePreparationStageResult)}
    assert actual == STAGE_RESULT_ALLOWED_FIELDS
    for name in actual:
        for token in FORBIDDEN_INTERNAL_DOWNSTREAM_TOKENS:
            assert token not in name


def test_flow_provenance_esp_record_keys_exclude_internal_artifact_paths() -> None:
    allowed = _ROUTE_SEMANTIC_MODULE_REQUIRED_KEYS | _ROUTE_SEMANTIC_MODULE_OPTIONAL_KEYS
    assert allowed == ESP_FLOW_PROVENANCE_ALLOWED_KEYS
    for key in allowed:
        if not key.startswith("evidence_source_preparation_"):
            continue
        for token in FORBIDDEN_INTERNAL_DOWNSTREAM_TOKENS:
            assert token not in key


def test_flow_provenance_to_record_uses_only_declared_output_pointer() -> None:
    provenance = FlowRunRouteSemanticModuleProvenance(
        semantic_module_id="clinical_safety",
        selected_projected_source_count=1,
        route_invoked=True,
        route_run_id="route_run",
        output_dir="/tmp/route",
        routing_manifest_path="/tmp/route/routing_manifest.json",
        run_summary_path="/tmp/route/run_summary.json",
        evidence_source_preparation_invoked=True,
        evidence_source_preparation_run_id="esp_run",
        evidence_source_preparation_stage_executor_id="clinical_trial_doc.aggregate_evidence",
        evidence_source_preparation_declared_output_path=(
            "/tmp/esp/aggregate_evidence_source_bundle.json"
        ),
        evidence_source_preparation_run_summary_path="/tmp/esp/run_summary.json",
    )
    record = provenance.to_record()
    esp_keys = {
        key
        for key in record
        if key.startswith("evidence_source_preparation_")
    }
    assert esp_keys == {
        "evidence_source_preparation_invoked",
        "evidence_source_preparation_run_id",
        "evidence_source_preparation_stage_executor_id",
        "evidence_source_preparation_declared_output_path",
        "evidence_source_preparation_run_summary_path",
    }


def test_unified_stage_run_summary_declared_output_chain(tmp_path: Path) -> None:
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

    assert result.declared_output_path.name == AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME
    assert result.declared_output_path.resolve() == (
        result.output_dir / AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME
    ).resolve()

    summary = load_json(result.run_summary_path)
    assert summary.get("stats", {}).get("phase") == EVIDENCE_SOURCE_PREPARATION_ASSEMBLE_PHASE
    outputs = summary.get("outputs") or {}
    assert outputs.get("aggregate_evidence_source_bundle") == (
        AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME
    )
    assert set(outputs).intersection(UNIFIED_RUN_SUMMARY_FORBIDDEN_OUTPUT_KEYS) == set()

    bundle = load_json(result.declared_output_path)
    assert bundle.get("artifact_type") == AGGREGATE_EVIDENCE_SOURCE_BUNDLE_ARTIFACT_TYPE
    assert load_json(result.output_dir / outputs["aggregate_evidence_source_bundle"]) == bundle
    assert not (result.output_dir / "pre_llm_review_state.json").is_file()


def test_stage_runtime_source_binds_declared_output_to_bundle_path() -> None:
    source = (
        BACKEND_ROOT
        / "runtime/evidence_source_preparation/clinical_trial_doc/clinical_safety/aggregate_evidence/stage.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source))
    return_nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call)
    ]
    matching = [
        node
        for node in return_nodes
        if isinstance(node.value.func, ast.Name)
        and node.value.func.id == "EvidenceSourcePreparationStageResult"
    ]
    assert matching, "stage runtime must return EvidenceSourcePreparationStageResult"
    returned_source = ast.unparse(matching[-1].value)
    assert "aggregate_evidence_source_bundle_path" in returned_source
    assert "declared_output_path=" in returned_source
