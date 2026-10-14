"""Tests for clinical-trial Document Consistency QC LLM dependency bindings."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from unittest.mock import patch

from application.clinical_trial_doc_consistency_qc import (
    build_clinical_trial_doc_consistency_qc_application_composition,
    execute_installed_clinical_trial_document_consistency_qc,
)
from application.clinical_trial_doc_consistency_qc import execution as execution_module
from application.clinical_trial_doc_consistency_qc import (
    projection_runtime as projection_runtime_module,
)
from application.clinical_trial_doc_consistency_qc.llm_binding_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS,
    validate_llm_dependency_bindings,
)
from application.document_consistency_qc import DocumentConsistencyQcExecutionRequest
from capability import INTERNAL_DSUR_CONSISTENCY_QC
from llm.execution_configs import (
    CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID,
    CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID,
    resolve_llm_execution_config,
)
from operations.filter_output_projection.runtime_dependencies import (
    FilterOutputProjectionRuntimeDependencies,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.dependencies import (
    CLINICAL_SAFETY_AGGREGATE_LLM_SLOT,
)
from plugins.clinical_trial_doc.filter_output_projection.overview.dependencies import (
    OVERVIEW_SEMANTIC_LLM_SLOT,
)
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.stage import (
    ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies,
)
from plugins.clinical_trial_doc.evidence_comparison.clinical_safety.aggregate_evidence.dependencies import (
    CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT,
)
from tests.document_consistency_qc_flow_helpers import admitted_source_bindings


def test_overview_slot_is_owned_by_plugin_dependencies_module() -> None:
    from plugins.clinical_trial_doc.filter_output_projection.overview import (
        dependencies as overview_dependencies,
    )

    assert OVERVIEW_SEMANTIC_LLM_SLOT == "filter_output_projection.overview_semantic_llm"
    assert overview_dependencies.OVERVIEW_SEMANTIC_LLM_SLOT is OVERVIEW_SEMANTIC_LLM_SLOT


def test_operations_layer_does_not_define_overview_llm_slot() -> None:
    operations_dir = BACKEND_ROOT / "operations" / "filter_output_projection"
    assert not (operations_dir / "llm_dependency_slots.py").exists()
    for path in operations_dir.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "overview_semantic_llm" not in source, (
            f"operations layer must not own overview LLM slot: {path.name}"
        )


def test_installed_binding_maps_slots_to_step_owned_configs() -> None:
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_EVIDENCE_COMPARISON_CONSOLIDATION_LLM_SLOT
        ]
        == CLINICAL_TRIAL_DOC_EC_CONSOLIDATION_LLM_EXECUTION_CONFIG_ID
    )
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            OVERVIEW_SEMANTIC_LLM_SLOT
        ]
        == CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID
    )
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_LLM_SLOT
        ]
        == CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID
    )
    assert (
        INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[OVERVIEW_SEMANTIC_LLM_SLOT]
        != INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS[
            CLINICAL_SAFETY_AGGREGATE_LLM_SLOT
        ]
    )


def test_installed_binding_validation_rejects_unknown_config_id() -> None:
    with pytest.raises(Exception, match="unknown llm execution config"):
        validate_llm_dependency_bindings(
            llm_dependency_bindings={
                OVERVIEW_SEMANTIC_LLM_SLOT: "missing_config",
            }
        )


def test_composition_carries_installed_llm_dependency_bindings() -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()

    assert (
        composition.llm_dependency_bindings[
            OVERVIEW_SEMANTIC_LLM_SLOT
        ]
        == CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID
    )


def test_production_execution_materializes_installed_binding(tmp_path: Path) -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    source = tmp_path / "source.docx"
    source.write_bytes(b"doc")
    request = DocumentConsistencyQcExecutionRequest(
        capability_id=INTERNAL_DSUR_CONSISTENCY_QC.capability_id,
        project_root=tmp_path,
        participant_inputs=admitted_source_bindings({"source": source}),
        participant_privacy_paths={"source": None},
        source_language="zh",
    )
    sentinel_projection_provider = object()
    sentinel_esp_provider = object()
    expected_fop_config = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_FOP_OVERVIEW_LLM_EXECUTION_CONFIG_ID
    )
    expected_esp_config = resolve_llm_execution_config(
        CLINICAL_TRIAL_DOC_ESP_AGGREGATE_LLM_EXECUTION_CONFIG_ID
    )

    with (
        patch.object(
            projection_runtime_module,
            "materialize_llm_provider",
            return_value=sentinel_projection_provider,
        ) as projection_materialize,
        patch.object(
            execution_module,
            "materialize_llm_provider",
            return_value=sentinel_esp_provider,
        ) as esp_materialize,
        patch.object(
            execution_module,
            "prepare_and_allocate_document_consistency_qc_flow",
        ) as flow,
        patch.object(execution_module, "execute_prepared_document_consistency_qc_flow"),
        patch.object(
            execution_module,
            "build_document_consistency_qc_application_result",
            return_value=object(),
        ),
    ):
        execute_installed_clinical_trial_document_consistency_qc(
            composition=composition,
            request=request,
        )

    projection_materialize.assert_called_once_with(expected_fop_config)
    esp_materialize.assert_called_once_with(expected_esp_config)
    flow_kwargs = flow.call_args.kwargs
    deps = flow_kwargs["projection_runtime_dependencies"]
    assert isinstance(deps, FilterOutputProjectionRuntimeDependencies)
    assert deps.llm_provider is sentinel_projection_provider
    esp_deps = flow_kwargs["evidence_source_preparation_execution_dependencies"]
    assert esp_deps.provider is sentinel_esp_provider
    assert esp_deps.llm_mode == "api"


def test_explicit_provider_override_is_preserved(tmp_path: Path) -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    source = tmp_path / "source.docx"
    source.write_bytes(b"doc")
    request = DocumentConsistencyQcExecutionRequest(
        capability_id=INTERNAL_DSUR_CONSISTENCY_QC.capability_id,
        project_root=tmp_path,
        participant_inputs=admitted_source_bindings({"source": source}),
        participant_privacy_paths={"source": None},
        source_language="zh",
    )
    fake_provider = object()
    runtime_dependencies = FilterOutputProjectionRuntimeDependencies(
        llm_provider=fake_provider,
    )
    esp_runtime_dependencies = (
        ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies(
            llm_mode="mock",
            provider=fake_provider,
        )
    )

    with (
        patch.object(
            execution_module,
            "materialize_llm_provider",
        ) as materialize,
        patch.object(
            execution_module,
            "prepare_and_allocate_document_consistency_qc_flow",
        ) as flow,
        patch.object(execution_module, "execute_prepared_document_consistency_qc_flow"),
        patch.object(
            execution_module,
            "build_document_consistency_qc_application_result",
            return_value=object(),
        ),
    ):
        execute_installed_clinical_trial_document_consistency_qc(
            composition=composition,
            request=request,
            projection_runtime_dependencies=runtime_dependencies,
            evidence_source_preparation_execution_dependencies=esp_runtime_dependencies,
        )

    materialize.assert_not_called()
    deps = flow.call_args.kwargs["projection_runtime_dependencies"]
    assert deps is runtime_dependencies
    assert deps.llm_provider is fake_provider


def test_explicit_none_provider_override_is_preserved(tmp_path: Path) -> None:
    composition = build_clinical_trial_doc_consistency_qc_application_composition()
    source = tmp_path / "source.docx"
    source.write_bytes(b"doc")
    request = DocumentConsistencyQcExecutionRequest(
        capability_id=INTERNAL_DSUR_CONSISTENCY_QC.capability_id,
        project_root=tmp_path,
        participant_inputs=admitted_source_bindings({"source": source}),
        participant_privacy_paths={"source": None},
        source_language="zh",
    )
    runtime_dependencies = FilterOutputProjectionRuntimeDependencies(
        llm_provider=None,
    )
    esp_runtime_dependencies = (
        ClinicalTrialAggregateEvidenceSourcePreparationExecutionDependencies(
            llm_mode="mock",
            provider=None,
        )
    )

    with (
        patch.object(
            execution_module,
            "materialize_llm_provider",
        ) as materialize,
        patch.object(
            execution_module,
            "prepare_and_allocate_document_consistency_qc_flow",
        ) as flow,
        patch.object(execution_module, "execute_prepared_document_consistency_qc_flow"),
        patch.object(
            execution_module,
            "build_document_consistency_qc_application_result",
            return_value=object(),
        ),
    ):
        execute_installed_clinical_trial_document_consistency_qc(
            composition=composition,
            request=request,
            projection_runtime_dependencies=runtime_dependencies,
            evidence_source_preparation_execution_dependencies=esp_runtime_dependencies,
        )

    materialize.assert_not_called()
    deps = flow.call_args.kwargs["projection_runtime_dependencies"]
    assert deps is runtime_dependencies
    assert deps.llm_provider is None
