"""CSR document-form metadata semantics."""

from __future__ import annotations

import re

from core.metadata.schemas import DocTypeFieldPolicy, DocTypeRule, MetadataRule

from plugins.clinical_trial_doc.doc_meta.common import _DATE_VALUE

_TITLE_PAGE_SOURCES = ("title_block", "early_block")

CSR_DOC_TYPE_RULES: list[DocTypeRule] = [
    DocTypeRule(
        doc_type="CSR",
        pattern=(
            r"(?:^|[/_\s-])csr(?:[_\s-]|$|\.)"
            r"|clinical[_\s-]?study[_\s-]?report"
            r"|临床研究报告"
            r"|最终研究报告"
            r"|研究总结报告"
            r"|(?:安全性|有效性).{0,50}研究报告"
        ),
        flags=re.IGNORECASE,
    ),
]

# CSR title-page metadata. These are CSR-specific semantic fields. They may
# overlap with generic document_date/cutoff_date, but should be preserved
# separately so later tag post-processing can canonicalize CSR study_period
# deterministically.
CSR_FIELD_RULES: list[MetadataRule] = [
    MetadataRule(
        field_name="study_title",
        pattern=r"(?:研究标题|试验标题|研究题目|试验题目)[:：]\s*(?P<value>[^\n\r]+)",
        flags=re.IGNORECASE,
        source_types=_TITLE_PAGE_SOURCES,
    ),
    MetadataRule(
        field_name="drug_modality",
        pattern=r"(?:药物类别|药物类型|药品类别)[:：]\s*(?P<value>[^\n\r]+)",
        flags=re.IGNORECASE,
        source_types=_TITLE_PAGE_SOURCES,
    ),
    MetadataRule(
        field_name="indication",
        pattern=r"(?:适应症|适应证)[:：]\s*(?P<value>[^\n\r]+)",
        flags=re.IGNORECASE,
        source_types=_TITLE_PAGE_SOURCES,
    ),
    MetadataRule(
        field_name="study_phase",
        pattern=r"(?:研究分期|试验分期|临床分期|研究阶段)[:：]\s*(?P<value>[^\n\r]+)",
        flags=re.IGNORECASE,
        source_types=_TITLE_PAGE_SOURCES,
    ),
    MetadataRule(
        field_name="study_start_date",
        pattern=rf"(?:试验起始日期|研究起始日期|试验开始日期|研究开始日期)[:：]\s*(?P<value>{_DATE_VALUE})",
        flags=re.IGNORECASE,
        source_types=_TITLE_PAGE_SOURCES,
    ),
    MetadataRule(
        field_name="first_subject_dosed_date",
        pattern=rf"(?:首例试验参与者给药日期|首例受试者给药日期|首例给药日期|首例入组给药日期)[:：]\s*(?P<value>{_DATE_VALUE})",
        flags=re.IGNORECASE,
        source_types=_TITLE_PAGE_SOURCES,
    ),
    MetadataRule(
        field_name="dose_escalation_completion_date",
        pattern=rf"(?:剂量探索完成日期|剂量递增完成日期|剂量爬坡完成日期)[:：]\s*(?P<value>{_DATE_VALUE})",
        flags=re.IGNORECASE,
        source_types=_TITLE_PAGE_SOURCES,
    ),
    MetadataRule(
        field_name="study_completion_date",
        pattern=rf"(?:研究完成日期|试验完成日期|研究结束日期|试验结束日期)[:：]\s*(?P<value>{_DATE_VALUE})",
        flags=re.IGNORECASE,
        source_types=_TITLE_PAGE_SOURCES,
    ),
    MetadataRule(
        field_name="database_lock_date",
        pattern=rf"(?:数据库锁定日期|数据库锁库日期|锁库日期|数据锁定日期)[:：]\s*(?P<value>{_DATE_VALUE})",
        flags=re.IGNORECASE,
        source_types=_TITLE_PAGE_SOURCES,
    ),
    MetadataRule(
        field_name="report_date",
        pattern=rf"(?:报告日期|报告时间)[:：]\s*(?P<value>{_DATE_VALUE})",
        flags=re.IGNORECASE,
        source_types=_TITLE_PAGE_SOURCES,
    ),
]

CSR_FIELD_POLICY = DocTypeFieldPolicy(
    enabled_fields=[
        "study_drug",
        "sponsor",
        "protocol_id",
        "version",
        "document_date",
        "cutoff_date",
        # CSR title-page metadata
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
    ],
    required_fields=[
        "study_drug",
        "protocol_id",
    ],
)
