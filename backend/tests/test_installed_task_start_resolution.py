"""Targeted tests for Product Task Start resolution."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import build_installed_document_consistency_qc_application_composition
from artifacts.document_consistency_qc_flow_run_summary import (
    DOCUMENT_CONSISTENCY_QC_FLOW_ID,
)
from task.clinical_trial_doc_qc import (
    DSUR_UPDATED_IB_QC_TASK_ID,
    INSTALLED_PRODUCT_TASKS,
    INTERNAL_CSR_QC_TASK_ID,
    INTERNAL_DSUR_QC_TASK_ID,
    INTERNAL_IB_QC_TASK_ID,
)
from task.clinical_trial_doc_qc.installation import (
    INSTALLED_PRODUCT_TASK_BY_ID,
    InstalledChildFlowBinding,
    InstalledProductTask,
    TaskInputToFlowParticipantBinding,
)
from task.clinical_trial_doc_qc.installation import (
    INSTALLED_PRODUCT_TASK_BY_ID as CANONICAL_INSTALLED_PRODUCT_TASK_BY_ID,
)
from task.clinical_trial_doc_qc.start import (
    PlannedProductTaskStart,
    start_installed_product_task,
    validate_installed_task_start_intent,
)
from task.clinical_trial_doc_qc.start_resolution import (
    resolve_installed_task_start,
)


def test_installed_tasks_declare_document_consistency_qc_flow_binding() -> None:
    for task in INSTALLED_PRODUCT_TASKS:
        assert task.child_flow.flow_id == DOCUMENT_CONSISTENCY_QC_FLOW_ID


def test_resolved_flow_id_matches_installed_child_flow_binding() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    for task in INSTALLED_PRODUCT_TASKS:
        resolved = resolve_installed_task_start(task.task_id, composition=composition)
        canonical = CANONICAL_INSTALLED_PRODUCT_TASK_BY_ID[task.task_id]
        assert resolved.child_flow.flow_id == canonical.child_flow.flow_id
        assert resolved.child_flow.flow_id == DOCUMENT_CONSISTENCY_QC_FLOW_ID


def test_resolver_reads_child_flow_from_canonical_installation() -> None:
    resolution_source = (
        BACKEND_ROOT
        / "task"
        / "clinical_trial_doc_qc"
        / "start_resolution.py"
    ).read_text(encoding="utf-8")
    assert "child_binding.flow_id" in resolution_source
    assert "installed_task.child_flow" in resolution_source
    assert "flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID" not in resolution_source


def test_unsupported_installed_task_flow_id_rejected_at_resolution() -> None:
    from types import MappingProxyType

    composition = build_installed_document_consistency_qc_application_composition()
    unsupported_task = InstalledProductTask(
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        child_flow=InstalledChildFlowBinding(
            flow_id="unsupported_future_flow",
            capability_id="internal_dsur",
            input_bindings=(
                TaskInputToFlowParticipantBinding(
                    task_slot_id="source",
                    participant_slot_id="source",
                ),
            ),
        ),
    )
    patched_lookup = MappingProxyType(
        {
            **dict(CANONICAL_INSTALLED_PRODUCT_TASK_BY_ID),
            INTERNAL_DSUR_QC_TASK_ID: unsupported_task,
        }
    )
    with (
        patch(
            "task.clinical_trial_doc_qc.start_resolution.INSTALLED_PRODUCT_TASK_BY_ID",
            patched_lookup,
        ),
        pytest.raises(ValueError, match="not executable by this installation"),
    ):
        resolve_installed_task_start(INTERNAL_DSUR_QC_TASK_ID, composition=composition)


def test_internal_dsur_qc_resolves_child_flow_capability() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    resolved = resolve_installed_task_start(
        INTERNAL_DSUR_QC_TASK_ID,
        composition=composition,
    )

    assert resolved.task_definition.task_id == INTERNAL_DSUR_QC_TASK_ID
    assert resolved.child_flow.flow_id == DOCUMENT_CONSISTENCY_QC_FLOW_ID
    assert resolved.child_flow.capability_id == "internal_dsur"
    assert resolved.child_flow.capability_config.capability_id == "internal_dsur"


def test_start_intent_validation_returns_same_resolved_flow_binding() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    resolved = validate_installed_task_start_intent(
        composition=composition,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )

    assert resolved.child_flow.flow_id == DOCUMENT_CONSISTENCY_QC_FLOW_ID
    assert resolved.child_flow.capability_id == "internal_dsur"


@pytest.mark.parametrize(
    ("task_id", "capability_id"),
    [
        (INTERNAL_DSUR_QC_TASK_ID, "internal_dsur"),
        (INTERNAL_IB_QC_TASK_ID, "internal_ib"),
        (INTERNAL_CSR_QC_TASK_ID, "internal_csr"),
        (DSUR_UPDATED_IB_QC_TASK_ID, "dsur_updated_ib"),
    ],
)
def test_resolve_installed_task_start_maps_all_tasks(
    task_id: str,
    capability_id: str,
) -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    installed_task = INSTALLED_PRODUCT_TASK_BY_ID[task_id]
    resolved = resolve_installed_task_start(task_id, composition=composition)

    assert resolved.task_definition.task_id == task_id
    assert resolved.child_flow.flow_id == installed_task.child_flow.flow_id
    assert resolved.child_flow.flow_id == DOCUMENT_CONSISTENCY_QC_FLOW_ID
    assert resolved.child_flow.capability_id == capability_id
    assert resolved.child_flow.capability_config.capability_id == capability_id


def test_unknown_task_id_rejected_before_slot_validation() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    with pytest.raises(ValueError, match="unsupported task_id: not_a_task"):
        resolve_installed_task_start("not_a_task", composition=composition)


def test_canonical_start_rejects_capability_id_as_task_id() -> None:
    composition = build_installed_document_consistency_qc_application_composition()
    with pytest.raises(ValueError, match="unsupported task_id: internal_dsur"):
        validate_installed_task_start_intent(
            composition=composition,
            task_id="internal_dsur",
            upload_slot_ids={"source"},
        )


def test_create_flow_allocated_flow_id_matches_resolved_start_flow_id(
    tmp_path: Path,
) -> None:
    sample_docx = (
        BACKEND_ROOT
        / "tests"
        / "fixtures"
        / "clinical_trial_doc"
        / "extract"
        / "ib_extract_minimal_001.docx"
    )
    assert sample_docx.is_file()

    composition = build_installed_document_consistency_qc_application_composition()
    resolved = validate_installed_task_start_intent(
        composition=composition,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )
    planned = PlannedProductTaskStart(
        task_run_id="task_run_20260920T010203000000Z_resolution_test",
        task_id=resolved.task_definition.task_id,
        resolved=resolved,
    )
    prepared = SimpleNamespace(
        flow_id=DOCUMENT_CONSISTENCY_QC_FLOW_ID,
        flow_run_id="document_consistency_qc_test",
    )

    def _capture_execute(actual: object):
        assert actual is prepared
        raise RuntimeError("stop after flow allocation")

    with (
        pytest.raises(RuntimeError, match="stop after flow allocation"),
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            return_value=prepared,
        ),
        patch(
            "task.clinical_trial_doc_qc.start.execute_prepared_installed_clinical_trial_document_consistency_qc",
            side_effect=_capture_execute,
        ),
    ):
        start_installed_product_task(
            composition=composition,
            planned=planned,
            slot_inputs={"source": sample_docx},
            project_root=tmp_path,
        )

    assert prepared.flow_id == resolved.child_flow.flow_id


def test_create_flow_rejects_flow_id_mismatch_against_resolved_start(
    tmp_path: Path,
) -> None:
    sample_docx = (
        BACKEND_ROOT
        / "tests"
        / "fixtures"
        / "clinical_trial_doc"
        / "extract"
        / "ib_extract_minimal_001.docx"
    )
    assert sample_docx.is_file()

    composition = build_installed_document_consistency_qc_application_composition()
    resolved = validate_installed_task_start_intent(
        composition=composition,
        task_id=INTERNAL_DSUR_QC_TASK_ID,
        upload_slot_ids={"source"},
    )
    planned = PlannedProductTaskStart(
        task_run_id="task_run_20260920T010203000000Z_flow_mismatch",
        task_id=resolved.task_definition.task_id,
        resolved=resolved,
    )

    with (
        patch(
            "task.clinical_trial_doc_qc.start.prepare_and_allocate_installed_clinical_trial_document_consistency_qc",
            return_value=SimpleNamespace(
                flow_id="not_document_consistency_qc",
                flow_run_id="document_consistency_qc_test",
            ),
        ),
        patch(
            "task.clinical_trial_doc_qc.start.execute_prepared_installed_clinical_trial_document_consistency_qc",
            side_effect=AssertionError("execution must not start"),
        ),
        pytest.raises(ValueError, match="expected resolved Start flow_id"),
    ):
        start_installed_product_task(
            composition=composition,
            planned=planned,
            slot_inputs={"source": sample_docx},
            project_root=tmp_path,
        )
