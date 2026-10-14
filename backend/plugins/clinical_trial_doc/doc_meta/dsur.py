"""DSUR document-form metadata semantics."""

from __future__ import annotations

import re

from core.metadata.schemas import DocTypeFieldPolicy, DocTypeRule, MetadataRule

from plugins.clinical_trial_doc.doc_meta.common import _DATE_RANGE

DSUR_DOC_TYPE_RULES: list[DocTypeRule] = [
    DocTypeRule(
        doc_type="DSUR",
        pattern=(
            r"(?:^|[/_\s-])dsur(?:[_\s-]|$|\.)"
            r"|development[_\s-]?safety[_\s-]?update(?:[_\s-]?report)?"
            r"|研发期间安全性更新报告"
            r"|研发安全性更新报告"
            r"|安全性更新报告"
        ),
        flags=re.IGNORECASE,
    ),
]

DSUR_FIELD_RULES: list[MetadataRule] = [
    MetadataRule(
        field_name="reporting_period",
        pattern=(
            rf"(?:涵盖周期|报告周期|报告期间|Reporting Period)[:：]\s*"
            rf"(?P<value>{_DATE_RANGE})"
            rf"(?=\s*(?:报告日期|报告时间|申办者|申办方|Sponsor|版本|Version|$))"
        ),
        flags=re.IGNORECASE,
    ),
]

DSUR_FIELD_POLICY = DocTypeFieldPolicy(
    enabled_fields=[
        "study_drug",
        "sponsor",
        "protocol_id",
        "version",
        "document_date",
        "cutoff_date",
        "reporting_period",
    ],
    required_fields=[
        "study_drug",
        "reporting_period",
    ],
)
