"""Composition-time validation for capability bindings vs installed sets."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import application.clinical_trial_doc_consistency_qc.composition as clinical_composition
from application.clinical_trial_doc_consistency_qc import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
    INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
    build_clinical_trial_doc_consistency_qc_application_composition,
)
from application.clinical_trial_doc_consistency_qc.filter_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS,
)
from application.document_consistency_qc.binding_validation import (
    validate_filter_job_bindings_against_installed_filter_jobs,
    validate_prepare_analysis_bindings_against_installed_registry,
)
from operations.prepare_analysis.contracts import PrepareAnalysisConfigId
from plugins.clinical_trial_doc.prepare_analysis.config import (
    build_current_clinical_prepare_analysis_config_registry,
)


def _installed_filter_job_ids() -> frozenset[str]:
    return frozenset(
        config.filter_job_id
        for config in INSTALLED_CLINICAL_TRIAL_DOC_FILTER_CONFIGS.values()
    )


def test_installed_binding_validation_accepts_current_filter_and_prepare_bindings() -> None:
    validate_filter_job_bindings_against_installed_filter_jobs(
        filter_job_bindings=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
        installed_filter_job_ids=_installed_filter_job_ids(),
    )
    registry = build_current_clinical_prepare_analysis_config_registry()
    validate_prepare_analysis_bindings_against_installed_registry(
        prepare_analysis_bindings=INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS,
        prepare_analysis_config_registry=registry,
    )
    build_clinical_trial_doc_consistency_qc_application_composition()


def test_filter_job_binding_validation_rejects_unknown_filter_job_id() -> None:
    invalid_bindings = dict(INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS)
    invalid_bindings[("internal_dsur", "source")] = ("unknown_filter_job",)

    with pytest.raises(
        ValueError,
        match=(
            r"filter_job binding references unknown filter_job_id "
            r"'unknown_filter_job' for capability slot "
            r"\('internal_dsur', 'source'\)"
        ),
    ):
        validate_filter_job_bindings_against_installed_filter_jobs(
            filter_job_bindings=invalid_bindings,
            installed_filter_job_ids=_installed_filter_job_ids(),
        )


def test_prepare_binding_validation_rejects_unknown_prepare_config_id() -> None:
    invalid_bindings = dict(INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS)
    unknown_id = PrepareAnalysisConfigId("pacfg_not_installed")
    invalid_bindings[("internal_ib", "source")] = unknown_id
    registry = build_current_clinical_prepare_analysis_config_registry()

    with pytest.raises(
        ValueError,
        match=(
            r"prepare_analysis binding references unknown "
            r"prepare_analysis_config_id .*pacfg_not_installed.* "
            r"for capability slot \('internal_ib', 'source'\)"
        ),
    ):
        validate_prepare_analysis_bindings_against_installed_registry(
            prepare_analysis_bindings=invalid_bindings,
            prepare_analysis_config_registry=registry,
        )


def test_composition_rejects_unknown_filter_job_before_flow_execution() -> None:
    invalid_bindings = dict(INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS)
    invalid_bindings[("internal_csr", "source")] = ("missing_filter_job",)

    with (
        patch.object(
            clinical_composition,
            "INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS",
            invalid_bindings,
        ),
        patch(
            "execution_flow.document_consistency_qc.run_document_consistency_qc_flow",
        ) as flow,
    ):
        with pytest.raises(ValueError, match="unknown filter_job_id 'missing_filter_job'"):
            build_clinical_trial_doc_consistency_qc_application_composition()
        flow.assert_not_called()


def test_composition_rejects_unknown_prepare_config_before_flow_execution() -> None:
    invalid_bindings = dict(INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS)
    invalid_bindings[("internal_csr", "source")] = PrepareAnalysisConfigId(
        "pacfg_missing_in_registry"
    )

    with (
        patch.object(
            clinical_composition,
            "INSTALLED_CLINICAL_TRIAL_DOC_PREPARE_ANALYSIS_BINDINGS",
            invalid_bindings,
        ),
        patch(
            "execution_flow.document_consistency_qc.run_document_consistency_qc_flow",
        ) as flow,
    ):
        with pytest.raises(
            ValueError,
            match=r"prepare_analysis binding references unknown .*pacfg_missing_in_registry",
        ):
            build_clinical_trial_doc_consistency_qc_application_composition()
        flow.assert_not_called()
