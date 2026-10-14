"""Targeted tests for Candidate Scope content-domain read model."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.clinical_trial_doc_consistency_qc.candidate_scope_content_domain import (
    build_candidate_scope_content_domain_groups,
)
from application.clinical_trial_doc_consistency_qc.capability_bindings import (
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
)
from application.clinical_trial_doc_consistency_qc.filter_output_projection_installation import (
    CLINICAL_SAFETY_SEMANTIC_MODULE_ID,
    INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS,
)
from application.clinical_trial_doc_consistency_qc.route_semantic_module_installation import (
    INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE,
)


def _build_groups(capability_id: str):
    return build_candidate_scope_content_domain_groups(
        capability_id=capability_id,
        filter_job_bindings=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_JOB_BINDINGS,
        filter_output_projection_jobs=INSTALLED_CLINICAL_TRIAL_DOC_FILTER_OUTPUT_PROJECTION_JOBS,
        route_semantic_module_sequence=(
            INSTALLED_CLINICAL_TRIAL_DOC_ROUTE_SEMANTIC_MODULE_SEQUENCE
        ),
    )


def test_internal_dsur_merges_overview_and_clinical_safety_filter_jobs() -> None:
    groups = _build_groups("internal_dsur")

    assert len(groups) == 1
    group = groups[0]
    assert group.content_domain_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    assert group.display_label == "临床安全性"
    assert group.filter_job_ids == ("dsur_clinical_safety", "dsur_overview")


def test_dsur_updated_ib_collects_dsur_and_ib_filter_jobs_in_one_domain() -> None:
    groups = _build_groups("dsur_updated_ib")

    assert len(groups) == 1
    group = groups[0]
    assert group.content_domain_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
    assert group.filter_job_ids == (
        "dsur_clinical_safety",
        "dsur_overview",
        "ib_clinical_safety",
        "ib_overview",
    )


def test_internal_ib_and_csr_capabilities_share_clinical_safety_domain() -> None:
    for capability_id in ("internal_ib", "internal_csr"):
        groups = _build_groups(capability_id)
        assert len(groups) == 1
        assert groups[0].content_domain_id == CLINICAL_SAFETY_SEMANTIC_MODULE_ID
        assert "overview" in groups[0].filter_job_ids[1]
        assert "clinical_safety" in groups[0].filter_job_ids[0]
