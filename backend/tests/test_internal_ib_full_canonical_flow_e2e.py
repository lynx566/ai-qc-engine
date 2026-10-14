"""Full canonical Flow E2E for installed INTERNAL_IB_CONSISTENCY_QC."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_consumer_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_SOURCE_PREPARATION_CONSUMER_BINDINGS,
)
from application.clinical_trial_doc_consistency_qc.evidence_source_preparation_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR,
)
from application.clinical_trial_doc_consistency_qc.execution import (
    execute_installed_clinical_trial_document_consistency_qc,
    materialize_installed_evidence_comparison_execution_dependencies,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
)
from application.clinical_trial_doc_consistency_qc.result_read import (
    load_document_consistency_qc_result,
)
from application.document_consistency_qc import (
    DocumentConsistencyQcApplicationResult,
    DocumentConsistencyQcExecutionRequest,
)
from application.document_consistency_qc.admitted_source import (
    admit_participant_source_path,
)
from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_RUN_SUMMARY_SCHEMA_VERSION,
    validate_flow_run_summary,
)
from artifacts.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence import (
    FINDINGS_FILENAME,
    validate_final_findings,
    validate_findings,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.aggregate_evidence_source_bundle import (
    AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME,
    validate_aggregate_evidence_source_bundle,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_compact import (
    ASSESSMENT_RUNTIME_CONTEXT_FILENAME,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.assessment_input_ids import (
    build_projected_fan_in_llm_input_bundle_id,
)
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import (
    validate_assessment_input,
)
from capability import INTERNAL_IB_CONSISTENCY_QC
from llm.providers.base import LLMRawResult
from operations.evidence_source_preparation.stage import (
    EvidenceSourcePreparationStageResult,
)
from runtime.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_STAGE_EXECUTOR_ID,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    CLINICAL_TRIAL_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR_ID,
    ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies,
)
from runtime.io import load_json
from tests.document_consistency_qc_flow_helpers import (
    flow_projection_runtime_dependencies,
)

IB_SAFETY_TAG_INTEGRATION_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "tag_integration"
    / "ib_safety_tag_integration_001.docx"
)
FLOW_PATH = BACKEND_ROOT / "execution_flow" / "document_consistency_qc" / "flow.py"
EXECUTION_PATH = (
    BACKEND_ROOT
    / "application"
    / "clinical_trial_doc_consistency_qc"
    / "execution.py"
)

_EXPECTED_FAN_IN_FILTER_JOB_IDS = (
    "ib_clinical_safety",
    "ib_overview",
)
_EXPECTED_FAN_IN_ZONE_KEYS = (
    "ib_clinical_safety_zh",
    "ib_overview_zh",
)
_SENTENCE_ALIAS_PATTERN = re.compile(r"\[(T\d{4})\]")


def _model_scope_ids_from_esp_prompt(messages: list[dict[str, str]]) -> list[str]:
    user_content = messages[-1]["content"]
    marker = "## Heading scopes\n"
    if marker not in user_content:
        raise ValueError("expected Heading scopes section in ESP prompt")
    payload = json.loads(user_content.split(marker, 1)[1].strip())
    scope_ids: list[str] = []
    for scope in payload:
        if not isinstance(scope, dict):
            continue
        scope_id = str(scope.get("scope_id") or "").strip()
        if scope_id:
            scope_ids.append(scope_id)
    if not scope_ids:
        raise ValueError("expected at least one model scope_id in ESP prompt")
    return scope_ids


def _eligible_aggregate_scope_assessment(scope_id: str) -> dict[str, object]:
    return {
        "scope_id": scope_id,
        "unit_form": "aggregate",
        "safety_role": "primary_safety_finding",
        "product_context_role": "target_study_drug",
        "route_qc": {
            "route_mismatch": False,
            "suggested_route": None,
            "reason": None,
        },
    }


class _EligibleAggregateEspProvider:
    """Return deterministic eligible aggregate scope assessments for E2E."""

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        scope_assessments = [
            _eligible_aggregate_scope_assessment(scope_id)
            for scope_id in _model_scope_ids_from_esp_prompt(messages)
        ]
        return LLMRawResult(
            provider_name="internal-ib-e2e-esp-mock",
            model="internal-ib-e2e-esp-mock",
            raw_text=json.dumps(
                {"scope_assessments": scope_assessments},
                ensure_ascii=False,
            ),
        )


def _first_sentence_alias(messages: list[dict[str, str]]) -> str:
    match = _SENTENCE_ALIAS_PATTERN.search(messages[-1]["content"])
    if match is None:
        raise AssertionError("expected sentence alias in Comparison assessment prompt")
    return match.group(1)


def _extract_verification_finding_ids(user_content: str) -> list[str]:
    marker = "## Findings\n"
    marker_index = user_content.find(marker)
    if marker_index == -1:
        return []
    finding_ids: list[str] = []
    for line in user_content[marker_index + len(marker) :].splitlines():
        stripped = line.strip()
        if stripped.startswith("L") and len(stripped) == 4 and stripped[1:].isdigit():
            finding_ids.append(stripped)
    return finding_ids


class _InternalIbComparisonProvider:
    """Deterministic Comparison Assessment / Verification provider for E2E."""

    def __init__(self) -> None:
        self.assessment_calls: list[list[dict[str, str]]] = []
        self.verification_calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        user_content = messages[-1]["content"]
        if "## Findings" in user_content:
            self.verification_calls.append(messages)
            finding_ids = _extract_verification_finding_ids(user_content)
            return LLMRawResult(
                provider_name="internal-ib-e2e-comparison-mock",
                model="internal-ib-e2e-comparison-mock",
                raw_text=json.dumps(
                    {
                        "finding_verifications": [
                            {
                                "finding_id": finding_id,
                                "verification_result": "confirmed",
                            }
                            for finding_id in finding_ids
                        ],
                        "additional_findings": [],
                    }
                ),
            )

        self.assessment_calls.append(messages)
        alias = _first_sentence_alias(messages)
        return LLMRawResult(
            provider_name="internal-ib-e2e-comparison-mock",
            model="internal-ib-e2e-comparison-mock",
            raw_text=json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_focus": f"candidate for {alias}",
                            "label": "fail",
                            "trigger_sentence_aliases": [alias],
                        }
                    ]
                }
            ),
        )


class _AssessmentResponseProvider:
    """Return empty or one-finding Assessment responses for closure coverage."""

    def __init__(self, *, include_finding: bool) -> None:
        self.include_finding = include_finding
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        self.calls.append(messages)
        candidates: list[dict[str, object]] = []
        if self.include_finding:
            alias = _first_sentence_alias(messages)
            candidates.append(
                {
                    "candidate_focus": f"second-pass candidate for {alias}",
                    "label": "fail",
                    "trigger_sentence_aliases": [alias],
                }
            )
        return LLMRawResult(
            provider_name="internal-ib-e2e-assessment-mock",
            model="internal-ib-e2e-assessment-mock",
            raw_text=json.dumps({"candidates": candidates}),
        )


class _UnexpectedVerificationProvider:
    """Fail if the second-pass terminal branch attempts Verification."""

    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        self.calls.append(messages)
        raise AssertionError("Verification must not run after second-pass Assessment")


class _EmptyConsolidationProvider:
    def generate(self, _messages: list[dict[str, str]]) -> LLMRawResult:
        return LLMRawResult(
            provider_name="internal-ib-e2e-consolidation-mock",
            model="internal-ib-e2e-consolidation-mock",
            raw_text=json.dumps({"consolidated_groups": []}),
        )


def _wire_internal_ib_e2e_test_mocks(
    monkeypatch: pytest.MonkeyPatch,
    *,
    assessment_provider,
    assessment_second_pass_provider,
    verification_provider,
) -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    original_materializer = (
        materialize_installed_evidence_comparison_execution_dependencies
    )

    def _materialize_with_test_providers(
        *,
        composition=composition,
        capability_id: str,
        assessment_provider=None,
        assessment_second_pass_provider=None,
        verification_provider=None,
    ):
        return original_materializer(
            composition=composition,
            capability_id=capability_id,
            assessment_provider=(assessment_provider or installed_assessment_provider),
            assessment_second_pass_provider=(
                assessment_second_pass_provider
                or installed_assessment_second_pass_provider
            ),
            verification_provider=(
                verification_provider or installed_verification_provider
            ),
            consolidation_provider=_EmptyConsolidationProvider(),
        )

    installed_assessment_provider = assessment_provider
    installed_assessment_second_pass_provider = assessment_second_pass_provider
    installed_verification_provider = verification_provider

    monkeypatch.setattr(
        "application.clinical_trial_doc_consistency_qc.execution."
        "materialize_installed_evidence_comparison_execution_dependencies",
        _materialize_with_test_providers,
    )


def _execute_internal_ib_installed_e2e_with_providers(
    tmp_path: Path,
    *,
    monkeypatch: pytest.MonkeyPatch,
    assessment_provider,
    assessment_second_pass_provider,
    verification_provider,
) -> DocumentConsistencyQcApplicationResult:
    assert IB_SAFETY_TAG_INTEGRATION_DOCX.is_file()
    _wire_internal_ib_e2e_test_mocks(
        monkeypatch,
        assessment_provider=assessment_provider,
        assessment_second_pass_provider=assessment_second_pass_provider,
        verification_provider=verification_provider,
    )
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    admitted = admit_participant_source_path(
        project_root=tmp_path,
        source_path=IB_SAFETY_TAG_INTEGRATION_DOCX,
    )
    request = DocumentConsistencyQcExecutionRequest(
        capability_id=INTERNAL_IB_CONSISTENCY_QC.capability_id,
        project_root=tmp_path,
        participant_inputs={"source": admitted},
        participant_privacy_paths={"source": None},
        source_language="zh",
    )
    return execute_installed_clinical_trial_document_consistency_qc(
        composition=composition,
        request=request,
        projection_runtime_dependencies=flow_projection_runtime_dependencies(),
        evidence_source_preparation_execution_dependencies=(
            ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies(
                llm_mode="api",
                llm_profile="internal_ib_e2e_mock",
                provider=_EligibleAggregateEspProvider(),
            )
        ),
    )


def _execute_internal_ib_installed_e2e(
    tmp_path: Path,
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    DocumentConsistencyQcApplicationResult,
    _InternalIbComparisonProvider,
    _InternalIbComparisonProvider,
    _InternalIbComparisonProvider,
]:
    assessment_provider = _InternalIbComparisonProvider()
    assessment_second_pass_provider = _InternalIbComparisonProvider()
    verification_provider = _InternalIbComparisonProvider()
    application_result = _execute_internal_ib_installed_e2e_with_providers(
        tmp_path,
        monkeypatch=monkeypatch,
        assessment_provider=assessment_provider,
        assessment_second_pass_provider=assessment_second_pass_provider,
        verification_provider=verification_provider,
    )
    return (
        application_result,
        assessment_provider,
        assessment_second_pass_provider,
        verification_provider,
    )


def _assert_comparison_path_executed(
    *,
    flow_report,
    assessment_provider: _InternalIbComparisonProvider,
    assessment_second_pass_provider: _InternalIbComparisonProvider,
    verification_provider: _InternalIbComparisonProvider,
) -> None:
    comparison_stage_result = flow_report.result.evidence_comparison_stage_result
    assert comparison_stage_result is not None
    assert comparison_stage_result.run_status == "success"
    assert (
        comparison_stage_result.stage_executor_id
        == CLINICAL_TRIAL_AGGREGATE_EVIDENCE_COMPARISON_STAGE_EXECUTOR_ID
    )
    assert comparison_stage_result.declared_output_path is not None
    assert comparison_stage_result.run_id == "evidence_comparison_internal_ib"

    expected_output_dir = (
        flow_report.flow_run_summary_path.parent
        / "participants"
        / "source"
        / "evidence_comparison"
    )
    assert comparison_stage_result.output_dir == expected_output_dir
    assert (comparison_stage_result.output_dir / FINDINGS_FILENAME).is_file()
    assert (
        comparison_stage_result.output_dir / "aggregate_comparison_evidence.json"
    ).is_file()
    assert (
        comparison_stage_result.output_dir / "comparison_finding_assessment_jobs.json"
    ).is_file()

    findings = load_json(comparison_stage_result.declared_output_path)
    validate_final_findings(findings)
    assert findings["findings"]
    validate_findings(
        load_json(comparison_stage_result.output_dir / FINDINGS_FILENAME)
    )

    job_dirs = sorted((comparison_stage_result.output_dir / "jobs").iterdir())
    assert job_dirs
    comparison_run_summary = load_json(comparison_stage_result.run_summary_path)
    assert comparison_run_summary["stats"]["assessment_success_count"] >= 1
    assert comparison_run_summary["stats"]["verification_success_count"] >= 1
    assert comparison_run_summary["stats"]["job_final_finding_count"] >= 1

    for job_dir in job_dirs:
        assessment_summary_path = job_dir / "assessment" / "validated_response.json"
        assert assessment_summary_path.is_file()
        job_summary = next(
            entry
            for entry in comparison_run_summary["jobs"]
            if Path(entry["assessment"]["job_dir"]) == job_dir
        )
        assert job_summary["assessment"]["status"] == "success"
        if job_summary["assessment_second_pass"] is None:
            assert job_summary["verification"]["status"] == "success"
            assert (job_dir / "verification" / "validated_response.json").is_file()
            assert not (job_dir / "assessment" / "second_pass").exists()
        else:
            assert job_summary["assessment_second_pass"]["status"] == "success"
            assert job_summary["verification"] is None
            assert (
                job_dir / "assessment" / "second_pass" / "validated_response.json"
            ).is_file()
            assert not (job_dir / "verification").exists()

    assert assessment_provider.assessment_calls
    assert assessment_second_pass_provider.assessment_calls
    assert verification_provider.verification_calls

    flow_summary = load_json(flow_report.flow_run_summary_path)
    evidence_comparison = flow_summary["evidence_comparison"]
    assert evidence_comparison["stage_executed"] is True
    assert evidence_comparison["run_status"] == "success"
    assert evidence_comparison["declared_output_path"] == (
        comparison_stage_result.declared_output_path.as_posix()
    )


def test_internal_ib_installed_application_executes_full_canonical_flow_e2e(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove INTERNAL_IB through installed application composition into real ESP."""

    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    assert INTERNAL_IB_CONSISTENCY_QC.capability_id in composition.capabilities
    installed_binding = INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_SOURCE_PREPARATION_CONSUMER_BINDINGS.resolve_consumer_binding(
        CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    )
    assert installed_binding is not None
    assert (
        installed_binding.stage_executor
        is INSTALLED_CLINICAL_TRIAL_DOC_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR
    )

    (
        application_result,
        assessment_provider,
        assessment_second_pass_provider,
        verification_provider,
    ) = _execute_internal_ib_installed_e2e(
        tmp_path,
        monkeypatch=monkeypatch,
    )
    flow_report = application_result.flow_report
    slot = flow_report.result.slots[0]

    assert slot.admitted_source.file_hash
    assert slot.admitted_source.original_file_name
    flow_root = flow_report.flow_run_summary_path.parent
    assert not (flow_root / "participants" / "source" / "intake").is_dir()
    standalone_intake_root = tmp_path / "runs" / "request_file_intake"
    assert standalone_intake_root.is_dir()
    assert any(standalone_intake_root.iterdir())
    assert slot.extract_report.result.run_id
    assert slot.extract_report.result.document.bundle_path.is_file()
    assert slot.prepare_analysis_report.status == "success"
    assert slot.doc_meta_report["run_summary_path"]
    assert len(slot.filter_results) == 2
    assert len(slot.projection_results) == 2

    expected_filter_jobs = INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS[
        (INTERNAL_IB_CONSISTENCY_QC.capability_id, "source")
    ]
    assert (
        tuple(job.filter_job_id for job in slot.filter_results) == expected_filter_jobs
    )
    assert (
        tuple(job.filter_job_id for job in slot.projection_results)
        == expected_filter_jobs
    )

    assert len(slot.route_semantic_module_results) == 1
    module_result = slot.route_semantic_module_results[0]
    assert module_result.semantic_module_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    assert module_result.route_invoked is True
    assert module_result.selected_projected_source_count >= 1
    assert module_result.stage_result is not None

    route_stage = module_result.stage_result
    routing_manifest = load_json(route_stage.routing_manifest_path)
    projection_refs = routing_manifest["source_refs"]["projection_input_refs"]
    assert [ref["filter_job_id"] for ref in projection_refs] == list(
        _EXPECTED_FAN_IN_FILTER_JOB_IDS
    )
    assert [ref["zone_key"] for ref in projection_refs] == list(
        _EXPECTED_FAN_IN_ZONE_KEYS
    )
    for ref in projection_refs:
        assert ref["filter_output_projection_bundle_id"]

    aggregate_bundle = load_json(route_stage.routed_bundle_paths["aggregate"])
    contributor_filter_job_ids = {
        unit.get("filter_job_id") for unit in aggregate_bundle.get("units", [])
    }
    assert contributor_filter_job_ids == set(_EXPECTED_FAN_IN_FILTER_JOB_IDS)
    for unit in aggregate_bundle.get("units", []):
        assert unit.get("source_zone_key")
        assert unit.get("filter_job_id") in _EXPECTED_FAN_IN_FILTER_JOB_IDS

    assert module_result.evidence_source_preparation_invoked is True
    stage_result = module_result.evidence_source_preparation_stage_result
    assert isinstance(stage_result, EvidenceSourcePreparationStageResult)
    assert stage_result.semantic_module_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    assert stage_result.stage_executor_id == (
        CLINICAL_TRIAL_AGGREGATE_EVIDENCE_SOURCE_PREPARATION_STAGE_EXECUTOR_ID
    )
    assert stage_result.declared_output_path.is_file()
    assert stage_result.run_summary_path.is_file()
    assert stage_result.output_dir.is_dir()
    assert not hasattr(stage_result, "prepare")
    assert not hasattr(stage_result, "assess")

    assessment_input_path = stage_result.output_dir / "assessment_input.json"
    assert assessment_input_path.is_file()
    assessment_input = load_json(assessment_input_path)
    runtime_context = load_json(
        stage_result.output_dir / ASSESSMENT_RUNTIME_CONTEXT_FILENAME
    )
    validate_assessment_input(assessment_input)

    assert (
        "zone_key" not in assessment_input
        or not str(assessment_input.get("zone_key") or "").strip()
    )
    assert "coverage_bundle_id" not in assessment_input
    assert "coverage_bundle_ref" not in (runtime_context.get("source_refs") or {})

    expected_llm_input_bundle_id = build_projected_fan_in_llm_input_bundle_id(
        file_hash=assessment_input["file_hash"],
        semantic_module_id=CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
        projection_input_refs=projection_refs,
        route="aggregate",
    )
    assert assessment_input["llm_input_bundle_id"] == expected_llm_input_bundle_id
    assert assessment_input["llm_input_bundle_id"].startswith(
        "llm_input_aggregate_projected_"
    )

    aggregate_evidence_bundle = load_json(stage_result.declared_output_path)
    validate_aggregate_evidence_source_bundle(aggregate_evidence_bundle)
    assert aggregate_evidence_bundle["heading_scopes"]
    assert (
        aggregate_evidence_bundle["doc_id"]
        == slot.extract_report.result.document.identity.doc_id
    )
    assert (
        aggregate_evidence_bundle["file_hash"]
        == slot.extract_report.result.document.identity.file_hash
    )
    assert aggregate_evidence_bundle["document_context"]["document_type"] == "ib"
    assert "zone_keys" not in aggregate_evidence_bundle
    assert "coverage_bundle_ids" not in aggregate_evidence_bundle

    flow_summary = load_json(flow_report.flow_run_summary_path)
    validate_flow_run_summary(flow_summary)
    assert flow_summary["schema_version"] == FLOW_RUN_SUMMARY_SCHEMA_VERSION
    assert flow_summary["capability_id"] == INTERNAL_IB_CONSISTENCY_QC.capability_id
    route_record = flow_summary["slots"][0]["route_semantic_modules"][0]
    assert route_record["evidence_source_preparation_invoked"] is True
    assert route_record["evidence_source_preparation_run_id"] == stage_result.run_id
    assert (
        route_record["evidence_source_preparation_stage_executor_id"]
        == stage_result.stage_executor_id
    )
    assert (
        route_record["evidence_source_preparation_declared_output_path"]
        == stage_result.declared_output_path.as_posix()
    )
    assert (
        route_record["evidence_source_preparation_run_summary_path"]
        == stage_result.run_summary_path.as_posix()
    )
    for forbidden_key in (
        "prepare",
        "assess",
        "eligibility",
        "assemble",
        "scope_assessments",
        "heading_scope_eligibility",
    ):
        assert forbidden_key not in route_record

    assert flow_report.flow_run_summary_path.is_file()
    assert route_stage.routing_manifest_path.is_file()
    assert route_stage.routed_bundle_paths["aggregate"].is_file()
    assert assessment_input_path.is_file()
    assert (
        stage_result.declared_output_path.name
        == AGGREGATE_EVIDENCE_SOURCE_BUNDLE_FILENAME
    )
    assert stage_result.run_summary_path.is_file()

    _assert_comparison_path_executed(
        flow_report=flow_report,
        assessment_provider=assessment_provider,
        assessment_second_pass_provider=assessment_second_pass_provider,
        verification_provider=verification_provider,
    )


@pytest.mark.parametrize(
    ("second_pass_has_finding", "expected_problem_count_is_positive"),
    [(True, True), (False, False)],
    ids=("second-pass-non-empty", "second-pass-empty"),
)
def test_second_pass_persistence_closes_into_result_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    second_pass_has_finding: bool,
    expected_problem_count_is_positive: bool,
) -> None:
    primary_provider = _AssessmentResponseProvider(include_finding=False)
    second_pass_provider = _AssessmentResponseProvider(
        include_finding=second_pass_has_finding
    )
    verification_provider = _UnexpectedVerificationProvider()

    application_result = _execute_internal_ib_installed_e2e_with_providers(
        tmp_path,
        monkeypatch=monkeypatch,
        assessment_provider=primary_provider,
        assessment_second_pass_provider=second_pass_provider,
        verification_provider=verification_provider,
    )
    flow_report = application_result.flow_report
    comparison_stage_result = flow_report.result.evidence_comparison_stage_result
    assert comparison_stage_result is not None
    assert comparison_stage_result.run_status == "success"
    assert comparison_stage_result.declared_output_path is not None

    findings = load_json(comparison_stage_result.declared_output_path)
    validate_final_findings(findings)
    persisted_findings = findings["findings"]
    assert bool(persisted_findings) is second_pass_has_finding

    comparison_run_summary = load_json(comparison_stage_result.run_summary_path)
    assert all(
        job["assessment_second_pass"]["status"] == "success"
        for job in comparison_run_summary["jobs"]
    )
    assert all(job["verification"] is None for job in comparison_run_summary["jobs"])

    flow_summary = load_json(flow_report.flow_run_summary_path)
    result = load_document_consistency_qc_result(
        project_root=tmp_path,
        flow_run_id=flow_summary["flow_run_id"],
    )
    assert result.scope_results
    assert all(scope.execution_status == "complete" for scope in result.scope_results)
    assert len(result.findings) == len(persisted_findings)
    assert (len(result.findings) > 0) is expected_problem_count_is_positive
    assert primary_provider.calls
    assert bool(second_pass_provider.calls)
    assert verification_provider.calls == []


def test_canonical_e2e_path_does_not_import_legacy_esp_orchestration() -> None:
    for path in (FLOW_PATH, EXECUTION_PATH):
        source = path.read_text(encoding="utf-8")
        assert "sequence.py" not in source
        assert "pipeline_harness.py" not in source
        assert "scripts.stage_runners.evidence_source_preparation" not in source
        tree = ast.parse(source, filename=str(path))
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not any(
            module and "aggregate_evidence.sequence" in module for module in imported
        )


def test_flow_preserves_neutral_esp_stage_boundary() -> None:
    source = FLOW_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(FLOW_PATH))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
    for module in imported:
        assert module != "plugins.clinical_trial_doc"
        assert not module.startswith("plugins.clinical_trial_doc.")
    for token in (
        "AggregateEvidenceExecutionInput",
        "AggregateEvidenceExecution",
        "AggregateEvidenceSourcePreparationProcessor",
    ):
        assert token not in source
