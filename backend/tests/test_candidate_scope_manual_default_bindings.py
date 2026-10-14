"""Targeted tests for installed Candidate Scope manual-default bindings."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from application.clinical_trial_doc_consistency_qc import (
    execute_installed_clinical_trial_document_consistency_qc,
)
from application.clinical_trial_doc_consistency_qc.capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
)
from application.document_consistency_qc import DocumentConsistencyQcExecutionRequest
from artifacts.candidate_scope_decision import CANDIDATE_SCOPE_DECISION_FILENAME
from artifacts.effective_candidate_scope import RESOLVED_ZONE_MATCH_BUNDLE_FILENAME
from bridge.candidate_scope.bridge_runtime import BridgeRuntimeConfig
from bridge.candidate_scope.state_service import load_candidate_scope_state
from capability import INTERNAL_DSUR_CONSISTENCY_QC, INTERNAL_IB_CONSISTENCY_QC
from core.document.structure.headings import is_heading
from execution_flow.document_consistency_qc import (
    CandidateScopeDecisionMode,
    FilterJobCandidateScopeSelection,
)
from execution_flow.document_consistency_qc.candidate_scope_checkpoint import (
    automatic_candidate_scope_selections,
)
from execution_flow.document_consistency_qc.candidate_scope_selection import (
    canonicalize_anchor_ids_for_job,
)
from runtime.io import load_json
from tests.document_consistency_qc_flow_helpers import admitted_source_bindings
from tests.candidate_scope_isolation import (
    SHOWCASE_DOCX,
    SHOWCASE_SLOT_ID,
    bridge_test_resume_dependencies,
    prepare_paused_multi_slot_canonical_flow,
)
from tests.test_document_consistency_qc_candidate_scope_resume import (
    _paused_slot_provenance,
    _resume_flow,
    _run_flow,
)

IB_SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "tag_integration"
    / "ib_safety_tag_integration_001.docx"
)
IB_MANUAL_ADD_SAMPLE_DOCX = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "clinical_trial_doc"
    / "extract"
    / "ib_extract_heading_001.docx"
)


def _analysis_heading_ids(analysis_bundle_path: Path) -> set[str]:
    bundle = load_json(analysis_bundle_path)
    return {
        str(block.get("block_id"))
        for block in bundle.get("content_blocks") or []
        if isinstance(block, dict) and is_heading(block) and block.get("block_id")
    }


def _automatic_anchor_ids(slot_record: dict) -> set[str]:
    automatic = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )
    return {anchor for item in automatic for anchor in item.anchor_block_ids}


def _slot_state(config: BridgeRuntimeConfig, flow_run_id: str, slot_id: str):
    state = load_candidate_scope_state(config=config, flow_run_id=flow_run_id)
    return next(item for item in state.slots if item.slot_id == slot_id)


def _manual_add_anchor_for_job(
    *,
    analysis_bundle_path: Path,
    automatic_by_job: dict[str, set[str]],
    filter_job_id: str,
) -> str:
    bundle = load_json(analysis_bundle_path)
    automatic_all = set().union(*automatic_by_job.values())
    for block in bundle.get("content_blocks") or []:
        if not isinstance(block, dict) or not is_heading(block):
            continue
        anchor = str(block.get("block_id") or "").strip()
        if not anchor or anchor in automatic_all:
            continue
        desired = set(automatic_by_job[filter_job_id]) | {anchor}
        canonical = canonicalize_anchor_ids_for_job(
            anchor_ids=desired,
            analysis_bundle=bundle,
        )
        if anchor in canonical:
            return anchor
    raise AssertionError(
        f"no manual-add anchor found for {filter_job_id!r} in {analysis_bundle_path}"
    )


def _prepare_paused_internal_ib_flow(
    tmp_path: Path,
) -> tuple[BridgeRuntimeConfig, str, dict]:
    assert IB_SAMPLE_DOCX.is_file()
    project_root = tmp_path / "internal_ib_project"
    project_root.mkdir(parents=True, exist_ok=True)
    composition = build_installed_document_consistency_qc_application_composition()
    resume_dependencies = bridge_test_resume_dependencies()
    request = DocumentConsistencyQcExecutionRequest(
        capability_id=INTERNAL_IB_CONSISTENCY_QC.capability_id,
        project_root=project_root,
        participant_inputs=admitted_source_bindings(
            {SHOWCASE_SLOT_ID: IB_SAMPLE_DOCX}
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
    config = BridgeRuntimeConfig(
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
    )
    execution = load_json(
        project_root
        / "runs"
        / "document_consistency_qc"
        / result.flow_report.flow_run_id.removeprefix("document_consistency_qc_")
        / "flow_run_summary.json"
    )
    slot_record = next(
        item for item in execution["slots"] if item["slot_id"] == SHOWCASE_SLOT_ID
    )
    return config, result.flow_report.flow_run_id, slot_record


def test_installed_manual_default_bindings_cover_all_filter_job_slots() -> None:
    for (
        binding_key,
        filter_job_ids,
    ) in INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS.items():
        assert (
            binding_key
            in INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS
        )
        manual_default = INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS[
            binding_key
        ]
        assert manual_default in filter_job_ids


def test_internal_dsur_catalog_equals_all_analysis_headings(
    paused_flow: tuple,
) -> None:
    config, flow_run_id, slot_id = paused_flow
    slot = _slot_state(config, flow_run_id, slot_id)
    execution = load_json(
        config.runs_root
        / "document_consistency_qc"
        / flow_run_id.removeprefix("document_consistency_qc_")
        / "flow_run_summary.json"
    )
    slot_record = next(
        item for item in execution["slots"] if item["slot_id"] == slot_id
    )
    analysis_path = Path(slot_record["analysis_bundle_path"])
    expected_headings = _analysis_heading_ids(analysis_path)
    automatic = _automatic_anchor_ids(slot_record)

    assert {heading.anchor_block_id for heading in slot.headings} == expected_headings
    assert set(slot.automatic_anchor_block_ids) == automatic
    assert set(slot.current_anchor_block_ids) == automatic
    assert len(automatic) < len(expected_headings)


def test_internal_ib_catalog_equals_all_analysis_headings(tmp_path: Path) -> None:
    config, flow_run_id, slot_record = _prepare_paused_internal_ib_flow(tmp_path)
    slot = _slot_state(config, flow_run_id, SHOWCASE_SLOT_ID)
    expected_headings = _analysis_heading_ids(Path(slot_record["analysis_bundle_path"]))
    automatic = _automatic_anchor_ids(slot_record)

    assert {heading.anchor_block_id for heading in slot.headings} == expected_headings
    assert set(slot.automatic_anchor_block_ids) == automatic
    assert len(automatic) < len(expected_headings)


def test_internal_ib_manual_add_materializes_manual_resolved_zone(
    tmp_path: Path,
) -> None:
    assert IB_MANUAL_ADD_SAMPLE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_IB_CONSISTENCY_QC,
        uploads={SHOWCASE_SLOT_ID: IB_MANUAL_ADD_SAMPLE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, SHOWCASE_SLOT_ID)
    automatic = {
        item.filter_job_id: set(item.anchor_block_ids)
        for item in automatic_candidate_scope_selections(
            filter_job_ids=tuple(slot_record["filter_job_ids"]),
            filter_jobs=slot_record["filter_jobs"],
        )
    }
    analysis_bundle_path = Path(slot_record["analysis_bundle_path"])
    manual_anchor = _manual_add_anchor_for_job(
        analysis_bundle_path=analysis_bundle_path,
        automatic_by_job=automatic,
        filter_job_id="ib_clinical_safety",
    )
    catalog_owners = {
        heading.anchor_block_id: heading.filter_job_id
        for heading in _slot_state(
            BridgeRuntimeConfig(
                workspace_root=tmp_path,
                runs_root=tmp_path / "runs",
                git_root=BACKEND_ROOT.parent,
            ),
            paused.flow_run_id,
            SHOWCASE_SLOT_ID,
        ).headings
    }
    assert catalog_owners[manual_anchor] == "ib_clinical_safety"
    selection_by_job = {
        filter_job_id: set(anchor_ids)
        for filter_job_id, anchor_ids in automatic.items()
    }
    selection_by_job["ib_clinical_safety"].add(manual_anchor)

    _resume_flow(
        capability_config=INTERNAL_IB_CONSISTENCY_QC,
        paused_report=paused,
        slot_id=SHOWCASE_SLOT_ID,
        selections=tuple(
            FilterJobCandidateScopeSelection(
                filter_job_id=filter_job_id,
                anchor_block_ids=tuple(sorted(anchor_ids)),
            )
            for filter_job_id, anchor_ids in selection_by_job.items()
        ),
        project_root=tmp_path,
    )

    resolved_path = (
        paused.flow_run_summary_path.parent
        / "participants"
        / SHOWCASE_SLOT_ID
        / "candidate_scope"
        / "ib_clinical_safety"
        / RESOLVED_ZONE_MATCH_BUNDLE_FILENAME
    )
    effective_bundle = load_json(resolved_path)
    zone = next(
        item
        for item in effective_bundle.get("matched_zones") or []
        if (item.get("match") or {}).get("matched_heading_block_id") == manual_anchor
    )
    assert zone["match"]["match_type"] == "manual"


def test_dsur_updated_ib_both_slots_return_all_headings(tmp_path: Path) -> None:
    config, flow_run_id, slot_ids = prepare_paused_multi_slot_canonical_flow(tmp_path)
    execution = load_json(
        config.runs_root
        / "document_consistency_qc"
        / flow_run_id.removeprefix("document_consistency_qc_")
        / "flow_run_summary.json"
    )
    for slot_id in slot_ids:
        slot_record = next(
            item for item in execution["slots"] if item["slot_id"] == slot_id
        )
        slot = _slot_state(config, flow_run_id, slot_id)
        expected_headings = _analysis_heading_ids(
            Path(slot_record["analysis_bundle_path"])
        )
        assert {
            heading.anchor_block_id for heading in slot.headings
        } == expected_headings


def test_dsur_updated_ib_slot_ownership_isolated(tmp_path: Path) -> None:
    config, flow_run_id, _slot_ids = prepare_paused_multi_slot_canonical_flow(tmp_path)
    source_a = _slot_state(config, flow_run_id, "source_a")
    source_b = _slot_state(config, flow_run_id, "source_b")
    owners_a = {
        heading.anchor_block_id: heading.filter_job_id for heading in source_a.headings
    }
    owners_b = {
        heading.anchor_block_id: heading.filter_job_id for heading in source_b.headings
    }

    assert set(owners_a) != set(owners_b)
    assert owners_a["C0006"] == "dsur_overview"
    assert owners_a["C0015"] == "dsur_clinical_safety"
    assert all(owner.startswith("ib_") for owner in owners_b.values())
    overview_anchor = next(
        anchor for anchor, owner in owners_b.items() if owner == "ib_overview"
    )
    unmatched_b = next(
        anchor
        for anchor, owner in owners_b.items()
        if owner == "ib_clinical_safety"
        and anchor not in set(source_b.automatic_anchor_block_ids)
    )
    assert owners_b[unmatched_b] == "ib_clinical_safety"
    assert owners_a.get(overview_anchor) != "ib_overview"


def test_per_job_isolation_overview_adjustment_leaves_clinical_unchanged(
    tmp_path: Path,
) -> None:
    assert SHOWCASE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={SHOWCASE_SLOT_ID: SHOWCASE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, SHOWCASE_SLOT_ID)
    automatic = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )
    overview_job_id = "dsur_overview"
    overview_anchors = next(
        item.anchor_block_ids
        for item in automatic
        if item.filter_job_id == overview_job_id
    )
    assert len(overview_anchors) >= 2
    adjusted_overview = tuple(overview_anchors[:-1])
    selections = tuple(
        FilterJobCandidateScopeSelection(
            filter_job_id=item.filter_job_id,
            anchor_block_ids=(
                adjusted_overview
                if item.filter_job_id == overview_job_id
                else item.anchor_block_ids
            ),
        )
        for item in automatic
    )

    _resume_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        paused_report=paused,
        slot_id=SHOWCASE_SLOT_ID,
        selections=selections,
        project_root=tmp_path,
    )

    decision = load_json(
        paused.flow_run_summary_path.parent
        / "participants"
        / SHOWCASE_SLOT_ID
        / "candidate_scope"
        / CANDIDATE_SCOPE_DECISION_FILENAME
    )
    by_job = {item["filter_job_id"]: item for item in decision["candidate_selections"]}
    assert by_job["dsur_overview"]["resolution"]["kind"] == "review_adjusted"
    assert by_job["dsur_clinical_safety"]["resolution"]["kind"] == "automatic_unchanged"


def test_per_job_isolation_manual_add_only_adjusts_clinical_job(tmp_path: Path) -> None:
    assert SHOWCASE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={SHOWCASE_SLOT_ID: SHOWCASE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, SHOWCASE_SLOT_ID)
    automatic = {
        item.filter_job_id: set(item.anchor_block_ids)
        for item in automatic_candidate_scope_selections(
            filter_job_ids=tuple(slot_record["filter_job_ids"]),
            filter_jobs=slot_record["filter_jobs"],
        )
    }
    manual_anchor = _manual_add_anchor_for_job(
        analysis_bundle_path=Path(slot_record["analysis_bundle_path"]),
        automatic_by_job=automatic,
        filter_job_id="dsur_clinical_safety",
    )
    selection_by_job = dict(automatic)
    selection_by_job["dsur_clinical_safety"].add(manual_anchor)

    _resume_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        paused_report=paused,
        slot_id=SHOWCASE_SLOT_ID,
        selections=tuple(
            FilterJobCandidateScopeSelection(
                filter_job_id=filter_job_id,
                anchor_block_ids=tuple(sorted(anchor_ids)),
            )
            for filter_job_id, anchor_ids in selection_by_job.items()
        ),
        project_root=tmp_path,
    )

    decision = load_json(
        paused.flow_run_summary_path.parent
        / "participants"
        / SHOWCASE_SLOT_ID
        / "candidate_scope"
        / CANDIDATE_SCOPE_DECISION_FILENAME
    )
    by_job = {item["filter_job_id"]: item for item in decision["candidate_selections"]}
    assert by_job["dsur_overview"]["resolution"]["kind"] == "automatic_unchanged"
    assert by_job["dsur_clinical_safety"]["resolution"]["kind"] == "review_adjusted"


def test_revert_to_automatic_is_unchanged(tmp_path: Path) -> None:
    assert SHOWCASE_DOCX.is_file()
    paused = _run_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        uploads={SHOWCASE_SLOT_ID: SHOWCASE_DOCX},
        project_root=tmp_path,
    )
    slot_record = _paused_slot_provenance(paused, SHOWCASE_SLOT_ID)
    selections = automatic_candidate_scope_selections(
        filter_job_ids=tuple(slot_record["filter_job_ids"]),
        filter_jobs=slot_record["filter_jobs"],
    )

    _resume_flow(
        capability_config=INTERNAL_DSUR_CONSISTENCY_QC,
        paused_report=paused,
        slot_id=SHOWCASE_SLOT_ID,
        selections=selections,
        project_root=tmp_path,
    )

    decision = load_json(
        paused.flow_run_summary_path.parent
        / "participants"
        / SHOWCASE_SLOT_ID
        / "candidate_scope"
        / CANDIDATE_SCOPE_DECISION_FILENAME
    )
    assert all(
        item["resolution"]["kind"] == "automatic_unchanged"
        for item in decision["candidate_selections"]
    )
