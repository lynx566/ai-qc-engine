"""IB document-form metadata semantics."""

from __future__ import annotations

import re

from core.metadata.schemas import DocTypeFieldPolicy, DocTypeRule

IB_DOC_TYPE_RULES: list[DocTypeRule] = [
    DocTypeRule(
        doc_type="IB",
        pattern=(
            r"(?:^|[/_\s-])ib(?:[_\s-]|$|\.)"
            r"|investigator'?s?[_\s-]?brochure"
            r"|研究者手册"
            r"|研究者资料"
        ),
        flags=re.IGNORECASE,
    ),
]

IB_FIELD_POLICY = DocTypeFieldPolicy(
    enabled_fields=[
        "study_drug",
        "sponsor",
        "investigator",
        "protocol_id",
        "version",
        "document_date",
        "cutoff_date",
    ],
    required_fields=[
        "study_drug",
    ],
)
