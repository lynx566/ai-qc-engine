"""Installed composition for Clinical Trial Documents × Document Consistency QC."""

from __future__ import annotations

from task.clinical_trial_doc_qc.definitions import PRODUCT_TASK_DEFINITION_BY_ID
from task.clinical_trial_doc_qc.installation import (
    INSTALLED_PRODUCT_TASKS,
    validate_installed_product_task_installations,
)

from application.document_consistency_qc.binding_validation import (
    validate_candidate_scope_manual_default_filter_job_bindings,
    validate_capability_slot_bindings,
    validate_filter_job_bindings_against_installed_filter_jobs,
    validate_prepare_analysis_bindings_against_installed_registry,
)
from application.document_consistency_qc.composition import (
    DocumentConsistencyQcApplicationComposition,
)

from .capabilities import INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES
from .capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
)
from .doc_meta_installation import resolve_installed_doc_meta_dependencies
from .evidence_comparison_consumer_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS,
    validate_evidence_comparison_consumer_installation,
)
from .evidence_source_preparation_consumer_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_SOURCE_PREPARATION_CONSUMER_BINDINGS,
)
from .expected_document_type_installation import (
    validate_expected_document_type_installation,
)
from .extract_installation import (
    build_installed_clinical_trial_doc_extract_bindings,
)
from .filter_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
)
from .filter_output_projection_facade_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_FACADE_BUILDER,
)
from .filter_output_projection_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS,
    validate_filter_output_projection_installation,
)
from .llm_binding_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS,
    validate_llm_dependency_bindings,
)
from .prepare_analysis_installation import (
    build_current_clinical_prepare_analysis_config_registry,
    load_clinical_prepare_request_options,
)
from .projected_source_route_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_PROJECTED_SOURCE_ROUTE_EXECUTOR,
)
from .route_semantic_module_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE,
)


def build_clinical_trial_doc_consistency_qc_application_composition() -> (
    DocumentConsistencyQcApplicationComposition
):
    """Build the currently installed clinical-trial application assembly."""

    extract_bindings = build_installed_clinical_trial_doc_extract_bindings(
        INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES
    )

    validate_installed_product_task_installations(
        installed_tasks=INSTALLED_PRODUCT_TASKS,
        product_task_definitions=PRODUCT_TASK_DEFINITION_BY_ID,
        installed_dcqc_capabilities=INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES,
    )

    validate_expected_document_type_installation(
        expected_document_type_bindings=(
            INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS
        ),
    )
    validate_capability_slot_bindings(
        capabilities=INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES,
        extract_bindings=extract_bindings,
        prepare_analysis_bindings=INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
        filter_job_bindings=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
        expected_document_type_bindings=(
            INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS
        ),
    )

    installed_filter_job_ids = frozenset(
        config.filter_job_id
        for config in INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS.values()
    )
    validate_filter_job_bindings_against_installed_filter_jobs(
        filter_job_bindings=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
        installed_filter_job_ids=installed_filter_job_ids,
    )
    validate_candidate_scope_manual_default_filter_job_bindings(
        manual_default_filter_job_bindings=(
            INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS
        ),
        filter_job_bindings=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
    )

    prepare_analysis_config_registry = (
        build_current_clinical_prepare_analysis_config_registry()
    )
    validate_prepare_analysis_bindings_against_installed_registry(
        prepare_analysis_bindings=INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
        prepare_analysis_config_registry=prepare_analysis_config_registry,
    )

    validate_filter_output_projection_installation(
        installed_filter_job_ids=installed_filter_job_ids,
        filter_output_projection_jobs=(
            INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS
        ),
    )
    validate_llm_dependency_bindings(
        llm_dependency_bindings=INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS,
    )
    validate_evidence_comparison_consumer_installation(
        consumer_bindings=INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS,
    )

    doc_meta = resolve_installed_doc_meta_dependencies()

    return DocumentConsistencyQcApplicationComposition(
        capabilities=INSTALLED_CLINICAL_TRIAL_DOC_CONSISTENCY_QC_CAPABILITIES,
        extract_bindings=extract_bindings,
        prepare_analysis_bindings=INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
        filter_job_bindings=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
        candidate_scope_manual_default_filter_job_bindings=(
            INSTALLED_CLINICAL_TRIAL_DOC_CANDIDATE_SCOPE_MANUAL_DEFAULT_FILTER_JOB_BINDINGS
        ),
        expected_document_type_bindings=(
            INSTALLED_CLINICAL_TRIAL_DOC_EXPECTED_DOCUMENT_TYPE_BINDINGS
        ),
        prepare_analysis_config_registry=prepare_analysis_config_registry,
        load_prepare_request_options=load_clinical_prepare_request_options,
        doc_meta_profile=doc_meta.profile,
        doc_meta_summary_builder=doc_meta.summary_builder,
        filter_configs=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS,
        filter_job_variants=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_VARIANTS,
        filter_output_projection_jobs=(
            INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS
        ),
        filter_output_projection_facade_builder=(
            INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_FACADE_BUILDER
        ),
        projected_source_route_executor=(
            INSTALLED_CLINICAL_TRIAL_DOC_PROJECTED_SOURCE_ROUTE_EXECUTOR
        ),
        route_semantic_module_sequence=(
            INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE
        ),
        evidence_source_preparation_consumer_bindings=(
            INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_SOURCE_PREPARATION_CONSUMER_BINDINGS
        ),
        evidence_comparison_consumer_bindings=(
            INSTALLED_CLINICAL_TRIAL_DOC_EVIDENCE_COMPARISON_CONSUMER_BINDINGS
        ),
        llm_dependency_bindings=INSTALLED_CLINICAL_TRIAL_DOC_LLM_DEPENDENCY_BINDINGS,
    )


__all__ = [
    "build_clinical_trial_doc_consistency_qc_application_composition",
]
