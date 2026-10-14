"""Installed clinical-trial Doc Meta profile composition (zh)."""

from __future__ import annotations

from core.metadata.schemas import MetadataContextConfig, MetadataProfile

from plugins.clinical_trial_doc.doc_meta.common import (
    COMMON_CUTOFF_RULES,
    COMMON_PREFIX_RULES,
)
from plugins.clinical_trial_doc.doc_meta.csr import (
    CSR_DOC_TYPE_RULES,
    CSR_FIELD_POLICY,
    CSR_FIELD_RULES,
)
from plugins.clinical_trial_doc.doc_meta.dsur import (
    DSUR_DOC_TYPE_RULES,
    DSUR_FIELD_POLICY,
    DSUR_FIELD_RULES,
)
from plugins.clinical_trial_doc.doc_meta.ib import IB_DOC_TYPE_RULES, IB_FIELD_POLICY

CLINICAL_TRIAL_DOC_META_PROFILE = MetadataProfile(
    name="clinical_trial_doc.meta.zh.v0_1",
    context=MetadataContextConfig(
        strategy="metadata_sources_v0_1",
        default_block_count=20,
        doc_type_source_priority=(
            "file_name",
            "display_name",
            "title_block",
            "heading",
            "early_block",
        ),
    ),
    default_doc_type=None,
    doc_type_rules=[
        *CSR_DOC_TYPE_RULES,
        *DSUR_DOC_TYPE_RULES,
        *IB_DOC_TYPE_RULES,
    ],
    field_rules=[
        *COMMON_PREFIX_RULES,
        *CSR_FIELD_RULES,
        *COMMON_CUTOFF_RULES,
        *DSUR_FIELD_RULES,
    ],
    doc_type_field_policies={
        "IB": IB_FIELD_POLICY,
        "DSUR": DSUR_FIELD_POLICY,
        "CSR": CSR_FIELD_POLICY,
    },
)
