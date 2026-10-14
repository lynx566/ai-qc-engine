"""Regression guards for installed Doc Meta profile composition invariants."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from plugins.clinical_trial_doc.doc_meta.profile_zh import (
    CLINICAL_TRIAL_DOC_META_PROFILE,
)


def test_installed_profile_identity_and_context() -> None:
    profile = CLINICAL_TRIAL_DOC_META_PROFILE
    assert profile.name == "clinical_trial_doc.meta.zh.v0_1"
    assert profile.context.strategy == "metadata_sources_v0_1"
    assert profile.context.default_block_count == 20
    assert profile.context.doc_type_source_priority == (
        "file_name",
        "display_name",
        "title_block",
        "heading",
        "early_block",
    )
    assert profile.default_doc_type is None


def test_installed_profile_doc_type_rule_order() -> None:
    doc_types = [rule.doc_type for rule in CLINICAL_TRIAL_DOC_META_PROFILE.doc_type_rules]
    assert doc_types == ["CSR", "DSUR", "IB"]


def test_installed_profile_field_rule_order() -> None:
    field_names = [
        rule.field_name for rule in CLINICAL_TRIAL_DOC_META_PROFILE.field_rules
    ]
    assert field_names == [
        "study_drug",
        "study_drug",
        "study_drug",
        "sponsor",
        "investigator",
        "protocol_id",
        "protocol_id",
        "protocol_id",
        "version",
        "document_date",
        "study_title",
        "drug_modality",
        "indication",
        "study_phase",
        "study_start_date",
        "first_subject_dosed_date",
        "dose_escalation_completion_date",
        "study_completion_date",
        "database_lock_date",
        "report_date",
        "cutoff_date",
        "cutoff_date",
        "cutoff_date",
        "cutoff_date",
        "reporting_period",
    ]


def test_installed_profile_protocol_id_multi_rule() -> None:
    protocol_rules = [
        rule
        for rule in CLINICAL_TRIAL_DOC_META_PROFILE.field_rules
        if rule.field_name == "protocol_id"
    ]
    assert len(protocol_rules) == 3
    assert protocol_rules[2].multi is True


def test_installed_profile_form_field_policies() -> None:
    policies = CLINICAL_TRIAL_DOC_META_PROFILE.doc_type_field_policies

    assert policies["IB"].enabled_fields == [
        "study_drug",
        "sponsor",
        "investigator",
        "protocol_id",
        "version",
        "document_date",
        "cutoff_date",
    ]
    assert policies["IB"].required_fields == ["study_drug"]

    assert policies["DSUR"].enabled_fields == [
        "study_drug",
        "sponsor",
        "protocol_id",
        "version",
        "document_date",
        "cutoff_date",
        "reporting_period",
    ]
    assert policies["DSUR"].required_fields == ["study_drug", "reporting_period"]

    assert policies["CSR"].enabled_fields == [
        "study_drug",
        "sponsor",
        "protocol_id",
        "version",
        "document_date",
        "cutoff_date",
        "study_title",
        "drug_modality",
        "indication",
        "study_phase",
        "study_start_date",
        "first_subject_dosed_date",
        "dose_escalation_completion_date",
        "study_completion_date",
        "database_lock_date",
        "report_date",
    ]
    assert policies["CSR"].required_fields == ["study_drug", "protocol_id"]
