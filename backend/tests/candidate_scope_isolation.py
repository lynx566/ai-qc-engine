"""Shared filesystem isolation helpers for candidate-scope pytest."""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from application import build_installed_document_consistency_qc_application_composition
from application.clinical_trial_doc_consistency_qc import (
    execute_installed_clinical_trial_document_consistency_qc,
)
from application.clinical_trial_doc_consistency_qc.execution import (
    materialize_installed_evidence_comparison_execution_dependencies,
)
from application.document_consistency_qc import DocumentConsistencyQcExecutionRequest
from artifacts.document_consistency_qc_flow_run_summary import (
    FLOW_RUN_SUMMARY_FILENAME,
    build_flow_run_summary,
)
from bridge.candidate_scope.bridge_runtime import BridgeRuntimeConfig
from capability import DSUR_UPDATED_IB_CONSISTENCY_QC, INTERNAL_DSUR_CONSISTENCY_QC
from execution_flow.document_consistency_qc import CandidateScopeDecisionMode
from execution_flow.document_consistency_qc.candidate_scope_checkpoint import (
    automatic_candidate_scope_selections,
    build_candidate_scope_decision_payload,
    materialize_candidate_scope_zone_matches,
    persist_candidate_scope_decision,
)
from execution_flow.document_consistency_qc.execution_provenance import (
    DOCUMENT_CONSISTENCY_QC_FLOW_STAGE,
    FlowRunFilterJobProvenance,
)
from llm.providers.base import LLMRawResult
from operations.evidence_comparison.stage import (
    EvidenceComparisonExecutionDependencies,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies,
)
from runtime.io import load_json, save_json
from tests.document_consistency_qc_flow_helpers import admitted_source_bindings
from scripts.stage_runners.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_assessment_mock_provider import (
    ComparisonFindingAssessmentStandaloneMockProvider,
)
from scripts.stage_runners.evidence_comparison.clinical_trial_doc.clinical_safety.aggregate_evidence.comparison_finding_verification_mock_provider import (
    ComparisonFindingVerificationStandaloneMockProvider,
)
from scripts.stage_runners.filter_output_projection_overview_mock_provider import (
    OverviewStandaloneMockProvider,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SHOWCASE_DOCX = (
    BACKEND_ROOT
    / "samples"
    / "clinical_trial_doc"
    / "docx"
    / "zh"
    / "clinical_program_001_vt8802"
    / "demo"
    / "艾美妥珠单抗 研发期间安全性更新报告#2_错误模拟.docx"
)

SHOWCASE_SLOT_ID = "source"

MULTI_SLOT_SAMPLE_DOCX_A = SHOWCASE_DOCX
MULTI_SLOT_SAMPLE_DOCX_B = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "tag_integration"
    / "ib_safety_tag_integration_001.docx"
)

_HEADING_SCOPES_PROMPT_MARKER = "## Heading scopes\n"


def _model_scope_ids_from_esp_prompt(messages: list[dict[str, str]]) -> list[str]:
    user_content = messages[-1]["content"]
    if _HEADING_SCOPES_PROMPT_MARKER not in user_content:
        raise ValueError("expected Heading scopes section in ESP prompt")
    payload = json.loads(
        user_content.split(_HEADING_SCOPES_PROMPT_MARKER, 1)[1].strip()
    )
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


@dataclass(frozen=True, slots=True)
class CandidateScopeEligibleAggregateEspProvider:
    """Deterministic ESP provider that yields comparison-eligible scope assessments."""

    def generate(self, messages: list[dict[str, str]]) -> LLMRawResult:
        scope_assessments = [
            _eligible_aggregate_scope_assessment(scope_id)
            for scope_id in _model_scope_ids_from_esp_prompt(messages)
        ]
        return LLMRawResult(
            provider_name="candidate-scope-esp-mock",
            model="candidate-scope-esp-mock",
            raw_text=json.dumps(
                {"scope_assessments": scope_assessments},
                ensure_ascii=False,
            ),
        )


@dataclass(frozen=True, slots=True)
class ComparisonFindingConsolidationStandaloneMockProvider:
    """Deterministic no-group provider for candidate-scope integration tests."""

    def generate(self, _messages: list[dict[str, str]]) -> LLMRawResult:
        return LLMRawResult(
            provider_name="candidate-scope-consolidation-mock",
            model="candidate-scope-consolidation-mock",
            raw_text=json.dumps({"consolidated_groups": []}),
        )


def default_projection_runtime_dependencies() -> (
    FilterOutputProjectionRuntimeDependencies
):
    return FilterOutputProjectionRuntimeDependencies(
        llm_provider=OverviewStandaloneMockProvider(),
    )


def default_evidence_source_preparation_execution_dependencies() -> (
    ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies
):
    return ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies(
        llm_mode="api",
        llm_profile="candidate_scope_bridge_mock",
        provider=CandidateScopeEligibleAggregateEspProvider(),
    )


def default_evidence_comparison_execution_dependencies(
    *,
    capability_id: str = INTERNAL_DSUR_CONSISTENCY_QC.capability_id,
) -> EvidenceComparisonExecutionDependencies:
    composition = build_installed_document_consistency_qc_application_composition()
    return materialize_installed_evidence_comparison_execution_dependencies(
        composition=composition,
        capability_id=capability_id,
        assessment_provider=ComparisonFindingAssessmentStandaloneMockProvider(),
        assessment_second_pass_provider=(
            ComparisonFindingAssessmentStandaloneMockProvider()
        ),
        verification_provider=ComparisonFindingVerificationStandaloneMockProvider(),
        consolidation_provider=(
            ComparisonFindingConsolidationStandaloneMockProvider()
        ),
    )


@dataclass(frozen=True, slots=True)
class PausedCanonicalFlowBaseline:
    """Immutable paused canonical flow workspace for per-test cloning."""

    project_root: Path
    flow_run_id: str
    slot_id: str


def bridge_runtime_config_for_project(project_root: Path) -> BridgeRuntimeConfig:
    resume_dependencies = bridge_test_resume_dependencies()
    return BridgeRuntimeConfig(
        workspace_root=project_root,
        runs_root=project_root / "runs",
        git_root=BACKEND_ROOT.parent,
        participant_privacy_paths={SHOWCASE_SLOT_ID: None},
        projection_runtime_dependencies=resume_dependencies[
            "projection_runtime_dependencies"
        ],
        evidence_source_preparation_execution_dependencies=resume_dependencies[
            "evidence_source_preparation_execution_dependencies"
        ],
        evidence_comparison_execution_dependencies=resume_dependencies[
            "evidence_comparison_execution_dependencies"
        ],
    )


def minimal_bridge_runtime_config(tmp_path: Path) -> BridgeRuntimeConfig:
    """Minimal bridge config for HTTP boundary tests that do not need a paused flow."""

    project_root = tmp_path / "empty_project"
    runs_root = project_root / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    return BridgeRuntimeConfig(
        workspace_root=project_root,
        runs_root=runs_root,
        git_root=BACKEND_ROOT.parent,
        projection_runtime_dependencies=default_projection_runtime_dependencies(),
    )


def bridge_test_resume_dependencies() -> dict[str, object]:
    """Return full injected resume dependencies for Candidate Scope bridge tests."""

    return {
        "projection_runtime_dependencies": default_projection_runtime_dependencies(),
        "evidence_source_preparation_execution_dependencies": (
            default_evidence_source_preparation_execution_dependencies()
        ),
        "evidence_comparison_execution_dependencies": (
            default_evidence_comparison_execution_dependencies()
        ),
    }


def prepare_paused_canonical_flow(
    tmp_path: Path,
    *,
    git_root: Path | None = None,
) -> tuple[BridgeRuntimeConfig, str, str]:
    """Run one canonical paused flow under an isolated project root."""

    assert SHOWCASE_DOCX.is_file(), f"showcase docx missing: {SHOWCASE_DOCX}"
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    composition = build_installed_document_consistency_qc_application_composition()
    resume_dependencies = bridge_test_resume_dependencies()
    request = DocumentConsistencyQcExecutionRequest(
        capability_id=INTERNAL_DSUR_CONSISTENCY_QC.capability_id,
        project_root=project_root,
        participant_inputs=admitted_source_bindings(
            {SHOWCASE_SLOT_ID: SHOWCASE_DOCX}
        ),
        participant_privacy_paths={SHOWCASE_SLOT_ID: None},
        source_language="zh",
        candidate_scope_decision_mode=CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE,
    )
    result = execute_installed_clinical_trial_document_consistency_qc(
        composition=composition,
        request=request,
        projection_runtime_dependencies=resume_dependencies[
            "projection_runtime_dependencies"
        ],
        evidence_source_preparation_execution_dependencies=resume_dependencies[
            "evidence_source_preparation_execution_dependencies"
        ],
    )
    assert result.flow_report.result.paused_at_candidate_scope is True

    config = bridge_runtime_config_for_project(project_root)
    return config, result.flow_report.flow_run_id, SHOWCASE_SLOT_ID


def prepare_paused_multi_slot_canonical_flow(
    tmp_path: Path,
) -> tuple[BridgeRuntimeConfig, str, tuple[str, ...]]:
    """Run one multi-slot canonical paused flow under an isolated project root."""

    assert MULTI_SLOT_SAMPLE_DOCX_A.is_file()
    assert MULTI_SLOT_SAMPLE_DOCX_B.is_file()
    project_root = tmp_path / "multi_slot_project"
    project_root.mkdir(parents=True, exist_ok=True)

    composition = build_installed_document_consistency_qc_application_composition()
    resume_dependencies = bridge_test_resume_dependencies()
    request = DocumentConsistencyQcExecutionRequest(
        capability_id=DSUR_UPDATED_IB_CONSISTENCY_QC.capability_id,
        project_root=project_root,
        participant_inputs=admitted_source_bindings(
            {
                "source_a": MULTI_SLOT_SAMPLE_DOCX_A,
                "source_b": MULTI_SLOT_SAMPLE_DOCX_B,
            }
        ),
        participant_privacy_paths={"source_a": None, "source_b": None},
        source_language="zh",
        candidate_scope_decision_mode=CandidateScopeDecisionMode.PAUSE_AT_CANDIDATE_SCOPE,
    )
    result = execute_installed_clinical_trial_document_consistency_qc(
        composition=composition,
        request=request,
        projection_runtime_dependencies=resume_dependencies[
            "projection_runtime_dependencies"
        ],
        evidence_source_preparation_execution_dependencies=resume_dependencies[
            "evidence_source_preparation_execution_dependencies"
        ],
    )
    from application.document_consistency_qc.create_flow_result import (
        build_document_consistency_qc_create_flow_result,
    )

    flow_result = build_document_consistency_qc_create_flow_result(result)
    assert flow_result.paused_at_candidate_scope is True
    assert flow_result.paused_slot_ids == ("source_a", "source_b")

    config = BridgeRuntimeConfig(
        workspace_root=project_root,
        runs_root=project_root / "runs",
        git_root=BACKEND_ROOT.parent,
        participant_privacy_paths={"source_a": None, "source_b": None},
        projection_runtime_dependencies=resume_dependencies[
            "projection_runtime_dependencies"
        ],
        evidence_source_preparation_execution_dependencies=resume_dependencies[
            "evidence_source_preparation_execution_dependencies"
        ],
        evidence_comparison_execution_dependencies=(
            default_evidence_comparison_execution_dependencies(
                capability_id=DSUR_UPDATED_IB_CONSISTENCY_QC.capability_id,
            )
        ),
    )
    return config, result.flow_report.flow_run_id, ("source_a", "source_b")


def build_paused_canonical_flow_baseline(
    cache_root: Path,
) -> PausedCanonicalFlowBaseline:
    """Build one immutable paused canonical workspace under cache_root."""

    marker = cache_root / ".baseline_ready"
    project_root = cache_root / "project"
    if not marker.is_file() or not project_root.is_dir():
        prepare_paused_canonical_flow(cache_root)
        marker.write_text("ready\n", encoding="utf-8")

    summary_root = project_root / "runs" / DOCUMENT_CONSISTENCY_QC_FLOW_STAGE
    flow_dirs = sorted(path for path in summary_root.iterdir() if path.is_dir())
    if not flow_dirs:
        raise RuntimeError("paused canonical baseline is missing flow output")
    summary = load_json(flow_dirs[0] / FLOW_RUN_SUMMARY_FILENAME)
    return PausedCanonicalFlowBaseline(
        project_root=project_root,
        flow_run_id=summary["flow_run_id"],
        slot_id=SHOWCASE_SLOT_ID,
    )


def clone_paused_canonical_flow_workspace(
    tmp_path: Path,
    baseline: PausedCanonicalFlowBaseline,
) -> tuple[BridgeRuntimeConfig, str, str]:
    """Copy immutable paused baseline into an isolated per-test project root."""

    dest = tmp_path / "project"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(baseline.project_root, dest)
    config = bridge_runtime_config_for_project(dest)
    return config, baseline.flow_run_id, baseline.slot_id


def _filter_job_provenance_from_record(record: dict[str, object]) -> FlowRunFilterJobProvenance:
    return FlowRunFilterJobProvenance(
        filter_job_id=str(record["filter_job_id"]),
        source_language=str(record["source_language"]),
        zone_config_name=str(record["zone_config_name"]),
        zone_config_version=str(record["zone_config_version"]),
        filter_run_id=str(record["filter_run_id"]),
        output_dir=str(record["output_dir"]),
        zone_match_bundle_path=str(record["zone_match_bundle_path"]),
        coverage_bundle_path=str(record["coverage_bundle_path"]),
        run_summary_path=str(record["run_summary_path"]),
    )


def persist_candidate_scope_decision_for_slot_summary(
    *,
    bridge_config: BridgeRuntimeConfig,
    flow_run_id: str,
    slot: dict[str, object],
    flow_root: Path,
) -> str:
    """Materialize one slot's persisted Candidate Scope decision artifacts."""

    slot_id = str(slot["slot_id"])
    filter_job_ids = tuple(str(item) for item in slot["filter_job_ids"])
    filter_jobs = [
        _filter_job_provenance_from_record(job)
        for job in slot["filter_jobs"]
    ]
    analysis_bundle = load_json(Path(str(slot["analysis_bundle_path"])))
    block_manifest = load_json(Path(str(slot["block_manifest_path"])))
    selections = automatic_candidate_scope_selections(
        filter_job_ids=filter_job_ids,
        filter_jobs=filter_jobs,
    )
    resolved_jobs = materialize_candidate_scope_zone_matches(
        filter_job_ids=filter_job_ids,
        filter_jobs=filter_jobs,
        selections=selections,
        analysis_bundle=analysis_bundle,
        block_manifest=block_manifest,
        flow_root=flow_root,
        slot_id=slot_id,
        doc_id=str(slot["doc_id"]),
        project_root=bridge_config.workspace_root,
    )
    payload = build_candidate_scope_decision_payload(
        flow_run_id=flow_run_id,
        slot_id=slot_id,
        filter_job_ids=filter_job_ids,
        resolved_jobs=resolved_jobs,
    )
    decision_path = persist_candidate_scope_decision(
        flow_root=flow_root,
        slot_id=slot_id,
        payload=payload,
    )
    return decision_path.as_posix()


def mark_canonical_flow_completed(
    bridge_config: BridgeRuntimeConfig,
    flow_run_id: str,
    *,
    persist_decision: bool = False,
    flow_status: str = "success",
) -> Path:
    """Persist a completed flow_run_summary without running resume."""

    session_dir = flow_run_id.removeprefix(f"{DOCUMENT_CONSISTENCY_QC_FLOW_STAGE}_")
    flow_root = (
        bridge_config.runs_root / DOCUMENT_CONSISTENCY_QC_FLOW_STAGE / session_dir
    )
    summary_path = flow_root / FLOW_RUN_SUMMARY_FILENAME
    summary = load_json(summary_path)
    completed_at = summary.get("completed_at") or summary["created_at"]
    slots = []
    for slot in summary["slots"]:
        slot_copy = dict(slot)
        if slot_copy["status"] == "paused_at_candidate_scope":
            if persist_decision:
                slot_copy["candidate_scope_decision_path"] = (
                    persist_candidate_scope_decision_for_slot_summary(
                        bridge_config=bridge_config,
                        flow_run_id=flow_run_id,
                        slot=slot_copy,
                        flow_root=flow_root,
                    )
                )
            slot_copy["status"] = "partial"
        slots.append(slot_copy)
    validated = build_flow_run_summary(
        flow_run_id=summary["flow_run_id"],
        capability_id=summary["capability_id"],
        source_language=summary["source_language"],
        status="partial" if not persist_decision else flow_status,
        created_at=summary["created_at"],
        completed_at=completed_at,
        slots=slots,
        evidence_comparison=summary.get("evidence_comparison"),
        candidate_scope_decision_mode=summary.get("candidate_scope_decision_mode"),
    )
    save_json(summary_path, validated)
    return summary_path


def assert_no_candidate_scope_execution_artifacts(runs_root: Path) -> None:
    stage_root = runs_root / "candidate_scope_execution"
    assert not stage_root.exists() or not any(stage_root.iterdir())


def assert_no_standalone_projection_artifacts(runs_root: Path) -> None:
    stage_root = runs_root / "filter_output_projection"
    assert not stage_root.exists() or not any(stage_root.iterdir())


__all__ = [
    "MULTI_SLOT_SAMPLE_DOCX_A",
    "MULTI_SLOT_SAMPLE_DOCX_B",
    "SHOWCASE_DOCX",
    "SHOWCASE_SLOT_ID",
    "CandidateScopeEligibleAggregateEspProvider",
    "PausedCanonicalFlowBaseline",
    "assert_no_candidate_scope_execution_artifacts",
    "assert_no_standalone_projection_artifacts",
    "bridge_runtime_config_for_project",
    "bridge_test_resume_dependencies",
    "build_paused_canonical_flow_baseline",
    "clone_paused_canonical_flow_workspace",
    "default_evidence_comparison_execution_dependencies",
    "default_evidence_source_preparation_execution_dependencies",
    "default_projection_runtime_dependencies",
    "mark_canonical_flow_completed",
    "minimal_bridge_runtime_config",
    "persist_candidate_scope_decision_for_slot_summary",
    "prepare_paused_canonical_flow",
    "prepare_paused_multi_slot_canonical_flow",
]
